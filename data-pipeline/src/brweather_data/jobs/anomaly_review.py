"""Tools for choosing anomaly parameters and reviewing real cases (T5.1-2, T5.1-5, T5.1-6).

    # T5.1-2: how many events each parameter set would raise on real history (read-only)
    python -m brweather_data.jobs.anomaly_review tune --days 30

    # T5.1-5: export 20 real anomalies, spread over categories and stations, as a review sheet
    python -m brweather_data.jobs.anomaly_review export --days 14 --n 20 --out review_20.csv

    # T5.1-6: after the reviewer filled in the sheet, summarise agreement
    python -m brweather_data.jobs.anomaly_review summary review_20_filled.csv

Inside Docker on the shared server, write the CSV under /tmp and copy it out with `docker compose cp`.
"""
import argparse
import csv
import itertools
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from brweather_data import db
from brweather_data.config import load_settings
from brweather_data.ml.anomaly import WINDOW, detect_events
from brweather_data.quality.anomaly_classifier import CATEGORY_LABELS

VN = timezone(timedelta(hours=7))
TUNE_GRID = {"threshold": [3.5, 4.0, 4.3, 5.0], "min_abs": [0.0, 10.0, 15.0, 20.0]}

SERIES_SQL = "SELECT hour, raw_value, quality_flag FROM pm25_hourly_series(%s, %s, %s)"
EXPORT_SQL = """
    SELECT a.id, a.station_id, s.name, a.start_time, a.end_time, a.direction, a.peak_value,
           a.baseline_value, a.category, a.description, a.details->>'reason' AS reason
    FROM anomalies a JOIN stations s ON s.id = a.station_id
    WHERE a.start_time >= %s
    ORDER BY a.start_time
"""
EXPORT_COLUMNS = ["id", "station_id", "name", "start_time", "end_time", "direction", "peak_value",
                  "baseline_value", "category", "description", "reason"]
REVIEW_COLUMNS = [
    "stt", "anomaly_id", "station_id", "station_name", "start_vn", "end_vn", "direction", "peak_value",
    "baseline_value", "category", "category_label", "reason", "description", "context_24h_before_after",
    # filled by the reviewer (T5.1-6)
    "reviewer_is_anomaly", "reviewer_category", "reviewer_notes",
]


# ---------------------------------------------------------------- T5.1-2
def tune_table(series_by_station: dict[int, tuple[list, list]], hours: int) -> list[dict]:
    """For every grid point: events and flagged hours per station-week. Pure, testable."""
    rows = []
    weeks = hours / 168
    for threshold, min_abs in itertools.product(TUNE_GRID["threshold"], TUNE_GRID["min_abs"]):
        events = flagged = 0
        for times, values in series_by_station.values():
            found = detect_events(times, values, WINDOW, threshold, min_abs)
            events += len(found)
            flagged += sum(len(e.hours) for e in found)
        n = max(len(series_by_station), 1)
        rows.append({"threshold": threshold, "min_abs": min_abs,
                     "events_per_station_week": round(events / n / weeks, 2) if weeks else 0.0,
                     "flagged_hours_pct": round(100 * flagged / max(n * hours, 1), 2)})
    return rows


def run_tune(conn, days: int) -> None:
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days, hours=WINDOW)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM stations WHERE is_active ORDER BY id")
        ids = [r[0] for r in cur.fetchall()]
    data = {}
    for sid in ids:
        with conn.cursor() as cur:
            cur.execute(SERIES_SQL, (sid, start, end))
            rows = cur.fetchall()
        data[sid] = ([r[0] for r in rows],
                     [r[1] if r[1] is not None and r[2] != "out_of_range" else None for r in rows])
    print(f"{len(ids)} trạm, {days} ngày đến {end:%Y-%m-%d %H:%M} UTC (cửa sổ nền {WINDOW} giờ)")
    print(f"{'ngưỡng |z|':>10} {'lệch tối thiểu':>15} {'sự kiện/trạm/tuần':>18} {'% giờ bị gắn cờ':>16}")
    for r in tune_table(data, days * 24):
        print(f"{r['threshold']:>10} {r['min_abs']:>15} {r['events_per_station_week']:>18} {r['flagged_hours_pct']:>16}")


# ---------------------------------------------------------------- T5.1-5
def pick_cases(rows: list[dict], n: int) -> list[dict]:
    """Round-robin over (category, station) so the sheet is not 20 copies of one station's events.
    Deterministic: within a bucket, newest first."""
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["start_time"], reverse=True):
        buckets[(r["category"], r["station_id"])].append(r)
    order = sorted(buckets, key=lambda k: (list(CATEGORY_LABELS).index(k[0]) if k[0] in CATEGORY_LABELS else 9, k[1]))
    picked = []
    while len(picked) < n and any(buckets[k] for k in order):
        for k in order:
            if buckets[k] and len(picked) < n:
                picked.append(buckets[k].pop(0))
    return sorted(picked, key=lambda r: r["start_time"])


def context(conn, station_id: int, start: datetime, end: datetime) -> str:
    with conn.cursor() as cur:
        cur.execute(SERIES_SQL, (station_id, start - timedelta(hours=24), end + timedelta(hours=25)))
        rows = cur.fetchall()
    return " ".join(f"{h.astimezone(VN):%d/%m %Hh}={'—' if v is None else round(v)}" for h, v, _ in rows)


def run_export(conn, days: int, n: int, out: str) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute(EXPORT_SQL, (since,))
        rows = [dict(zip(EXPORT_COLUMNS, r)) for r in cur.fetchall()]
    picked = pick_cases(rows, n)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: Excel shows Vietnamese correctly
        w = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS)
        w.writeheader()
        for i, r in enumerate(picked, 1):
            w.writerow({
                "stt": i, "anomaly_id": r["id"], "station_id": r["station_id"], "station_name": r["name"],
                "start_vn": r["start_time"].astimezone(VN).strftime("%d/%m/%Y %H:%M"),
                "end_vn": r["end_time"].astimezone(VN).strftime("%d/%m/%Y %H:%M"),
                "direction": "tăng" if r["direction"] == "up" else "giảm",
                "peak_value": r["peak_value"], "baseline_value": r["baseline_value"],
                "category": r["category"], "category_label": CATEGORY_LABELS.get(r["category"], r["category"]),
                "reason": r["reason"], "description": r["description"],
                "context_24h_before_after": context(conn, r["station_id"], r["start_time"], r["end_time"]),
                "reviewer_is_anomaly": "", "reviewer_category": "", "reviewer_notes": "",
            })
    print(f"Đã ghi {len(picked)}/{n} ca vào {out} (có {len(rows)} bất thường trong {days} ngày)")
    if len(picked) < n:
        print("Chưa đủ ca: chạy lại sau khi có thêm dữ liệu hoặc tăng --days.")


# ---------------------------------------------------------------- T5.1-6
YES = {"đúng", "dung", "có", "co", "yes", "y", "1", "x"}


def summarize(rows: list[dict]) -> dict:
    reviewed = [r for r in rows if (r.get("reviewer_is_anomaly") or "").strip()]
    is_anomaly = [r for r in reviewed if r["reviewer_is_anomaly"].strip().lower() in YES]
    with_cat = [r for r in is_anomaly if (r.get("reviewer_category") or "").strip()]
    label_to_code = {v.lower(): k for k, v in CATEGORY_LABELS.items()}

    def code(text: str) -> str:
        t = text.strip().lower()
        return label_to_code.get(t, t)

    agree = [r for r in with_cat if code(r["reviewer_category"]) == r["category"]]
    return {
        "cases": len(rows), "reviewed": len(reviewed),
        "confirmed_anomaly": len(is_anomaly),
        "precision_pct": round(100 * len(is_anomaly) / len(reviewed), 1) if reviewed else None,
        "category_agreement_pct": round(100 * len(agree) / len(with_cat), 1) if with_cat else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tune")
    p.add_argument("--days", type=int, default=30)
    p = sub.add_parser("export")
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--out", default="anomaly_review_20.csv")
    p = sub.add_parser("summary")
    p.add_argument("csv")
    args = parser.parse_args()

    if args.cmd == "summary":
        with open(args.csv, encoding="utf-8-sig") as f:
            s = summarize(list(csv.DictReader(f)))
        print(f"{s['reviewed']}/{s['cases']} ca đã rà soát; {s['confirmed_anomaly']} ca người rà soát xác nhận là bất thường "
              f"({s['precision_pct']}%); phân loại khớp {s['category_agreement_pct']}%")
        return
    settings = load_settings(require_openaq_key=False)
    with db.connect(settings.db_dsn) as conn:
        if args.cmd == "tune":
            run_tune(conn, args.days)
        else:
            run_export(conn, args.days, args.n, args.out)


if __name__ == "__main__":
    main()
