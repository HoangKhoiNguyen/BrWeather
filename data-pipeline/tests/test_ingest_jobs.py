"""T2.1-1 (every run logged, one failing station does not stop the others), T2.3-1 (backfill chunks),
reports used as evidence, and the scheduler."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

from brweather_data.connectors.openaq import SourceError
from brweather_data.jobs import backfill_pm25, data_report, ingest_hourly, scheduler

NOW = datetime(2026, 11, 20, 7, 10, tzinfo=timezone.utc)


# ---------------------------------------------------------------- error classification and status
def test_error_kind_separates_source_and_internal_errors():
    assert ingest_hourly.error_kind(requests.HTTPError("503")) == "source"
    assert ingest_hourly.error_kind(requests.Timeout()) == "source"
    assert ingest_hourly.error_kind(SourceError("rate limit")) == "source"
    assert ingest_hourly.error_kind(KeyError("coordinates")) == "internal"


def test_run_status():
    assert ingest_hourly.run_status(10, []) == "success"
    assert ingest_hourly.run_status(9, [{"kind": "source"}]) == "partial"
    assert ingest_hourly.run_status(0, [{"kind": "source"}]) == "failed"


# ---------------------------------------------------------------- run() with fake OpenAQ, Open-Meteo, db
class FakeConn:
    def __init__(self):
        self.commits = self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeClient:
    def __init__(self, failing: set[int]):
        self.failing = failing

    def location(self, sid):
        if sid in self.failing:
            raise requests.HTTPError(f"503 for {sid}")
        return {"id": sid, "name": f"S{sid}", "coordinates": {"latitude": 21.0, "longitude": 105.8}}

    @staticmethod
    def pm25_sensor_id(location):
        return location["id"] * 10

    def hourly(self, sensor_id, start, end, on_page=None):
        if on_page:
            on_page(f"/sensors/{sensor_id}/hours", {"results": []})
        yield NOW.replace(minute=0) - timedelta(hours=1), 42.0
        yield NOW.replace(minute=0), -5.0  # out of range: stored with a flag


@pytest.fixture
def fake_env(monkeypatch):
    log = SimpleNamespace(runs=[], raw=[], pm25=[], snapshots=[], conn=FakeConn())
    fake_db = SimpleNamespace(
        connect=lambda dsn: log.conn,
        start_run=lambda conn, job: 1,
        finish_run=lambda conn, run_id, status, records, error=None, errors=None:
            log.runs.append((status, records, error, errors)),
        save_raw=lambda conn, source, request, payload, run_id: log.raw.append((source, request)) or len(log.raw),
        upsert_station=lambda conn, location, sensor: None,
        latest_measurement=lambda conn, sid: None,
        insert_pm25=lambda conn, sid, rows: log.pm25.append((sid, rows)) or len(rows),
        station_coords=lambda conn, sid: (21.1, 105.9),
        insert_weather_snapshot=lambda conn, lat, lon, data, raw_payload_id=None:
            log.snapshots.append((lat, lon, raw_payload_id)) or 99,
    )
    monkeypatch.setattr(ingest_hourly, "db", fake_db)
    monkeypatch.setattr(ingest_hourly, "load_settings",
                        lambda: SimpleNamespace(openaq_api_key="k", station_ids=[1, 2, 3], db_dsn=""))
    monkeypatch.setattr(ingest_hourly, "fetch_weather", lambda lat, lon: {"hourly": {}, "daily": {}})
    return log


def test_all_stations_ok_gives_success(fake_env, monkeypatch):
    monkeypatch.setattr(ingest_hourly, "OpenAQClient", lambda key: FakeClient(set()))
    assert ingest_hourly.run() == 6
    status, records, error, errors = fake_env.runs[-1]
    assert (status, records, error, errors) == ("success", 6, None, [])
    assert len(fake_env.snapshots) == 3
    # every snapshot points to its raw payload; OpenAQ pages are kept raw too
    assert all(raw_id is not None for _, _, raw_id in fake_env.snapshots)
    assert any(src == "openaq" and "/hours" in req for src, req in fake_env.raw)
    # values are flagged, never dropped or zeroed
    rows = fake_env.pm25[0][1]
    assert [(v, f) for _, v, f in rows] == [(42.0, "ok"), (-5.0, "out_of_range")]


def test_one_station_down_is_partial_and_others_are_saved(fake_env, monkeypatch):
    monkeypatch.setattr(ingest_hourly, "OpenAQClient", lambda key: FakeClient({2}))
    ingest_hourly.run()
    status, records, _, errors = fake_env.runs[-1]
    assert status == "partial"
    assert records == 4  # stations 1 and 3
    assert errors == [{"station_id": 2, "stage": "pm25", "kind": "source", "message": "HTTPError: 503 for 2"}]
    # station 2 still gets weather, using the coordinates already stored
    assert len(fake_env.snapshots) == 3
    assert (21.1, 105.9) in [(lat, lon) for lat, lon, _ in fake_env.snapshots]
    assert fake_env.conn.rollbacks == 1


def test_everything_down_is_failed_and_raises(fake_env, monkeypatch):
    monkeypatch.setattr(ingest_hourly, "OpenAQClient", lambda key: FakeClient({1, 2, 3}))

    def no_weather(lat, lon):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(ingest_hourly, "fetch_weather", no_weather)
    with pytest.raises(RuntimeError):
        ingest_hourly.run()
    status, _, _, errors = fake_env.runs[-1]
    assert status == "failed"
    assert len(errors) == 6 and {e["kind"] for e in errors} == {"source"}


def test_database_error_is_internal(fake_env, monkeypatch):
    monkeypatch.setattr(ingest_hourly, "OpenAQClient", lambda key: FakeClient(set()))

    def broken_insert(conn, sid, rows):
        raise ValueError("column does not exist")

    monkeypatch.setattr(ingest_hourly.db, "insert_pm25", broken_insert)
    ingest_hourly.run()
    status, _, _, errors = fake_env.runs[-1]
    assert status == "partial"
    assert {(e["stage"], e["kind"]) for e in errors} == {("pm25", "internal")}


# ---------------------------------------------------------------- backfill
def test_backfill_chunks_cover_the_range_without_gaps():
    end = datetime(2026, 11, 23, tzinfo=timezone.utc)
    parts = backfill_pm25.chunks(end - timedelta(days=14), end, 6)
    assert [b - a for a, b in parts] == [timedelta(days=6), timedelta(days=6), timedelta(days=2)]
    assert all(parts[i][1] == parts[i + 1][0] for i in range(len(parts) - 1))
    assert parts[0][0] == end - timedelta(days=14) and parts[-1][1] == end


def test_backfill_chunks_reject_naive_datetimes():
    with pytest.raises(ValueError):
        backfill_pm25.chunks(datetime(2026, 11, 1), datetime(2026, 11, 2), 7)


def test_coverage_percentage():
    assert backfill_pm25.Coverage(1, 336, 330, 320).usable_pct == pytest.approx(95.238, 0.01)
    assert backfill_pm25.Coverage(1, 0, 0, 0).usable_pct == 0.0


# ---------------------------------------------------------------- data_report
def test_summarize_runs_counts_statuses_and_hours_without_run():
    now = datetime(2026, 11, 20, 12, 30, tzinfo=timezone.utc)

    def row(hour, status, source=0, internal=0):
        start = datetime(2026, 11, 20, hour, 10, tzinfo=timezone.utc)
        return (hour, "ingest_hourly", start, start, status, 5, source + internal, source, internal)

    rows = [row(8, "success"), row(9, "partial", source=1), row(11, "failed", internal=2)]
    s = data_report.summarize_runs(rows, hours=4, now=now)
    assert (s["runs"], s["success"], s["partial"], s["failed"]) == (3, 1, 1, 1)
    assert s["source_errors"] == 1 and s["internal_errors"] == 2
    assert s["hours_without_run"] == [datetime(2026, 11, 20, 10, tzinfo=timezone.utc)]


# ---------------------------------------------------------------- scheduler
def test_scheduler_runs_next_job_when_one_fails():
    called = []

    def bad():
        called.append("ingest")
        raise RuntimeError("boom")

    scheduler.run_hourly_jobs((("ingest", bad), ("reliability", lambda: called.append("reliability"))))
    assert called == ["ingest", "reliability"]


def test_scheduler_includes_reliability_after_ingest():
    assert [name for name, _ in scheduler.HOURLY_JOBS] == ["ingest_hourly", "compute_reliability", "detect_anomalies"]
