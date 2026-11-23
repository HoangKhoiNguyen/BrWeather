"""Read-only reports on the shared database, used as evidence for the data tasks.

    python -m brweather_data.jobs.data_report runs --hours 24     # T2.1-1 / C-06: every run logged?
    python -m brweather_data.jobs.data_report weather             # T1.2-1: 24 continuous UTC hours per point
    python -m brweather_data.jobs.data_report pm25 --days 14      # T2.3-1: hours stored per station

Inside Docker on the shared server:
    docker compose exec pipeline python -m brweather_data.jobs.data_report runs
Only SELECT statements are run.
"""
import argparse
from datetime import datetime, timedelta, timezone

from brweather_data import db
from brweather_data.config import load_settings

RUNS_SQL = """
    SELECT run_id, job, started_at, finished_at, status, records,
           COALESCE(jsonb_array_length(errors), 0) AS n_errors,
           (SELECT count(*) FROM jsonb_array_elements(errors) e WHERE e->>'kind' = 'source') AS n_source,
           (SELECT count(*) FROM jsonb_array_elements(errors) e WHERE e->>'kind' = 'internal') AS n_internal
    FROM ingest_runs
    WHERE job = %s AND started_at >= %s
    ORDER BY started_at
"""

# For the latest snapshot of each point: rows in [hour of fetch, +24h) and whether they are continuous.
WEATHER_SQL = """
    WITH latest AS (
        SELECT DISTINCT ON (lat, lon) snapshot_id, lat, lon, fetched_at
        FROM weather_snapshots
        ORDER BY lat, lon, fetched_at DESC, snapshot_id DESC
    )
    SELECT l.snapshot_id, l.lat, l.lon, l.fetched_at,
           count(h.valid_time) AS hours,
           min(h.valid_time) AS first_hour,
           max(h.valid_time) AS last_hour,
           count(*) FILTER (WHERE h.temperature_c IS NULL OR h.precipitation_prob_pct IS NULL
                             OR h.weather_code IS NULL OR h.wind_speed_kmh IS NULL) AS rows_with_null
    FROM latest l
    LEFT JOIN weather_hourly h
      ON h.snapshot_id = l.snapshot_id
     AND h.valid_time >= date_trunc('hour', l.fetched_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
     AND h.valid_time <  date_trunc('hour', l.fetched_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' + interval '24 hours'
    GROUP BY l.snapshot_id, l.lat, l.lon, l.fetched_at
    ORDER BY l.lat, l.lon
"""

PM25_SQL = """
    SELECT s.id, s.name,
           count(*) FILTER (WHERE p.status <> 'missing') AS stored,
           count(*) FILTER (WHERE p.status = 'ok') AS usable,
           count(*) AS expected,
           min(p.hour) FILTER (WHERE p.status = 'ok') AS first_ok,
           max(p.hour) FILTER (WHERE p.status = 'ok') AS last_ok
    FROM stations s
    CROSS JOIN LATERAL pm25_hourly_series(s.id, %s, %s) p
    WHERE s.is_active
    GROUP BY s.id, s.name
    ORDER BY s.id
"""


def summarize_runs(rows: list[tuple], hours: int, now: datetime) -> dict:
    """Success rate and the hours of the window that have no run at all (scheduler down)."""
    statuses = [r[4] for r in rows]
    started_hours = {r[2].astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0) for r in rows}
    end = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    window = [end - timedelta(hours=i) for i in range(1, hours + 1)]
    return {
        "runs": len(rows),
        "success": statuses.count("success"),
        "partial": statuses.count("partial"),
        "failed": statuses.count("failed"),
        "running": statuses.count("running"),
        "success_pct": 100.0 * statuses.count("success") / len(rows) if rows else 0.0,
        "source_errors": sum(r[7] for r in rows),
        "internal_errors": sum(r[8] for r in rows),
        "hours_without_run": sorted(h for h in window if h not in started_hours),
    }


def report_runs(conn, job: str, hours: int) -> None:
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(RUNS_SQL, (job, now - timedelta(hours=hours)))
        rows = cur.fetchall()
    for r in rows:
        print(f"{r[0]:>7} {r[2]:%Y-%m-%d %H:%M} {r[4]:<8} records={r[5]:<5} errors={r[6]} "
              f"(source {r[7]}, internal {r[8]})")
    s = summarize_runs(rows, hours, now)
    print(f"\n{job}, {hours} giờ qua: {s['runs']} lượt | success {s['success']} | partial {s['partial']} | "
          f"failed {s['failed']} | running {s['running']} | tỷ lệ success {s['success_pct']:.1f}%")
    print(f"Lỗi nguồn: {s['source_errors']}, lỗi nội bộ: {s['internal_errors']}")
    missing = s["hours_without_run"]
    print("Giờ không có lượt chạy nào: " + (", ".join(f"{h:%d/%m %H}h" for h in missing) if missing else "không có"))


def report_weather(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(WEATHER_SQL)
        rows = cur.fetchall()
    print(f"{'snapshot':>9} {'lat,lon':>18} {'fetched_at (UTC)':>17} {'giờ':>4} {'liên tục':>9} {'dòng có null':>13}")
    for sid, lat, lon, fetched, hours, first, last, nulls in rows:
        continuous = hours == 24 and first is not None and (last - first) == timedelta(hours=23)
        print(f"{sid:>9} {lat:>8.4f},{lon:<9.4f} {fetched:%Y-%m-%d %H:%M} {hours:>4} "
              f"{'đạt' if continuous else 'KHÔNG':>9} {nulls:>13}")


def report_pm25(conn, days: int) -> None:
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute(PM25_SQL, (start, end))
        rows = cur.fetchall()
    print(f"PM2.5 {start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M} UTC ({days} ngày)")
    print(f"{'Trạm':>10} {'Tên':<40} {'Có':>5} {'Dùng được':>10} {'Cần':>5} {'%':>6}  Giờ đầu / cuối dùng được")
    for sid, name, stored, usable, expected, first_ok, last_ok in rows:
        pct = 100.0 * usable / expected if expected else 0.0
        span = f"{first_ok:%d/%m %H}h / {last_ok:%d/%m %H}h" if first_ok else "-"
        print(f"{sid:>10} {name[:40]:<40} {stored:>5} {usable:>10} {expected:>5} {pct:>5.1f}%  {span}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_runs = sub.add_parser("runs")
    p_runs.add_argument("--hours", type=int, default=24)
    p_runs.add_argument("--job", default="ingest_hourly")
    sub.add_parser("weather")
    p_pm = sub.add_parser("pm25")
    p_pm.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    # Reports only read the database; the OpenAQ key is not needed.
    settings = load_settings(require_openaq_key=False)
    with db.connect(settings.db_dsn) as conn:
        if args.cmd == "runs":
            report_runs(conn, args.job, args.hours)
        elif args.cmd == "weather":
            report_weather(conn)
        else:
            report_pm25(conn, args.days)


if __name__ == "__main__":
    main()
