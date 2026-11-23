# Bàn giao: task thu thập và lưu trữ dữ liệu (Sprint 1 còn dở + Sprint 2)

Nhánh `claude/data-sprint1-2`, dựng trên `fix/weather-snapshot-current-columns` của nguyenhk (migration 001).
Code do Claude viết theo yêu cầu của kiennt. **hungpvc và hieund review và tự merge** phần của mình.

## Tóm tắt theo task

| Task | Người | Trạng thái trên nhánh | Còn phải làm (người thật) |
|---|---|---|---|
| T1.1-1 Connector thời tiết hiện tại | hungpvc | Đã xong từ PR #172; chỉ thêm mẫu payload đầy đủ `tests/sample_payloads.py` | Đóng issue #42 |
| T1.1-2 Lưu thời tiết hiện tại + nguồn + liên kết dữ liệu thô | hieund | Migration 001 (của nguyenhk) + 002: `raw_payload_id`, view `v_weather_current_latest` | Merge, kiểm tra trên VPS |
| T1.2-1 Kiểm tra 24 giờ trong snapshot | hungpvc | `quality/weather_checks.py::check_hourly_window`; pipeline ghi cảnh báo vào log; báo cáo `data_report weather` | Chạy báo cáo trên VPS, dán kết quả vào issue #48 |
| T1.3-1 Dự báo 7 ngày | hungpvc | Thêm `precipitation_probability_max` (khả năng mưa theo ngày, trước đây **thiếu**); `check_daily` | Merge |
| T1.3-2 Lưu dự báo theo ngày theo snapshot | hieund | Migration 003: cột `precipitation_prob_max_pct`, view `v_weather_daily_latest` (7 ngày + `issued_at`) | Merge |
| T2.1-1 Job thu thập 5 trạm mỗi giờ, có log | hungpvc | Một trạm lỗi không còn làm hỏng cả lượt; trạng thái `success/partial/failed`; lỗi tách `source`/`internal` (migration 008); lưu thô cả trang OpenAQ; báo cáo `data_report runs` | **Chạy 24 giờ trên VPS** rồi dán `data_report runs --hours 24` vào issue #52 |
| T2.1-2 Bảng số đo sạch + view mới nhất | hieund | Migration 004: ràng buộc giá trị `quality_flag`, view `v_pm25_latest`; kiểm thử chống trùng trong `db/tests` | Merge |
| T3.1-1 Dự báo không ghi đè + chỉ mục | hieund | Migration 005: trigger chặn UPDATE (kể cả upsert), chỉ mục `(station_id, target_time)`, view `v_pm25_forecast_latest` | Merge |
| T2.3-1 Backfill 14 ngày | hungpvc | Job `jobs/backfill_pm25.py` (chia khúc, chạy lại an toàn, in độ phủ từng trạm) | **Chạy trên VPS**: `docker compose exec pipeline python -m brweather_data.jobs.backfill_pm25 --days 14`, dán bảng độ phủ vào issue #72 |
| T2.3-2 Chuỗi theo giờ đủ lịch, giờ thiếu null | hieund | Migration 006: hàm `pm25_hourly_series(station, from, to)` | Merge; BE (T2.3-3) có thể dùng hàm này thay cho tự lấp giờ trong Java |
| T4.1-1 Ba kiểm tra phạm vi / đứng yên / độ trễ | hieund | `quality/reliability.py` hoàn thiện, kiểm thử biên trong `tests/test_reliability.py` | Merge |
| T4.1-2 So với trạm lân cận | hieund | Bán kính 10 km, lệch giờ ≤ 2 giờ, so với median cục bộ (gồm chính trạm), ngưỡng ≥ 50% **và** ≥ 15 µg/m³ | Nhóm xác nhận ngưỡng |
| T4.1-3 Job mức tin cậy mỗi giờ | hieund | `jobs/compute_reliability.py`, chạy sau ingest trong scheduler; lưu `reasons` + `details` (migration 007); gắn cờ `flatline` cho giờ cảm biến kẹt | Merge; xem kết quả 1 ngày trên VPS |
| SP-02 Nguồn cháy và thiên tai | hungpvc | Bản nháp `reports/sp02_fire_disaster_sources.md` | Hưng chạy thử FIRMS cho vùng Hà Nội (mục 1 của báo cáo) và chốt kết luận; PO quyết định phạm vi US10.2 |
| C-03 Môi trường chung | hieund | Code đã merge (PR #171) | Dựng VPS theo `docs/shared-environment.md` (việc của người giữ tài khoản Oracle) |

## Lỗi phát hiện khi làm

- **Trên `main`, mọi lượt lưu thời tiết đều lỗi.** `db.py` ghi các cột `current_*` nhưng `schema.sql` chưa có. nguyenhk đã sửa ở nhánh `fix/weather-snapshot-current-columns` nhưng chưa mở PR. Nhánh này dựng trên đó, nên **merge nhánh của nguyenhk trước**.
- **Dự báo 7 ngày thiếu "khả năng mưa"** mà US1.3 yêu cầu. Đã thêm (T1.3-1, T1.3-2).
- **Trước đây một trạm lỗi làm rollback cả lượt chạy**, các trạm khác cũng mất dữ liệu giờ đó. Đã tách theo trạm và theo bước.
- **So với lân cận:** median của 2 lân cận bị một trạm ngoại lai kéo lệch, làm cả trạm bình thường bị đánh lệch. Đã đổi sang median cục bộ gồm chính trạm đó (có kiểm thử).
- 11 test fail và 4 test error trong `test_pm25_*`/`test_air_quality_assessments` có sẵn trên `main` vì cần file trong `data/` (không có trong repo). Không do nhánh này gây ra, nhưng CI job `data-pipeline` sẽ đỏ vì chúng. Cần người phụ trách các file đó xử lý (đánh dấu skip khi thiếu dữ liệu).

## Điểm cần nhóm quyết định

1. **Ngưỡng tin cậy** (giá trị khởi đầu, xem lại sau 1 tuần dữ liệu thật): đứng yên 6 giờ (ví dụ của PO ở T4.1-4 ghi "5 giờ", cần chốt một số); cũ sau 3 giờ; không có số đo quá 24 giờ thì `low`; lân cận 10 km.
2. **Gắn cờ `flatline` vào `air_measurements`**: job tin cậy *chỉ đổi cờ*, không đổi giá trị. Nhờ vậy quy tắc đủ dữ liệu dự báo (T3.1-2) tự loại giờ cảm biến kẹt. Nếu nhóm muốn bảng số đo chỉ do ingest ghi thì bỏ đoạn `UPDATE` trong `compute_reliability.py`.
3. **`reasons` lưu mã** (`flatline`, `stale`…). Câu tiếng Việt do T4.1-4 (kiennt) làm; `details` có sẵn số liệu cho câu kiểu "số đo không đổi trong 7 giờ".

## Cách kiểm tra

Trên máy cá nhân (cần Docker):

```bash
docker compose up -d db migrate                     # áp schema + migration 001–008
docker compose run --rm migrate                     # chạy lại lần hai: phải báo "Migration mới áp dụng: 0"
PGHOST=localhost PGUSER=brweather PGPASSWORD=... PGDATABASE=brweather bash db/tests/run.sh
cd data-pipeline && pip install -e ".[dev]" && pytest tests/test_weather_checks.py tests/test_db_weather.py \
    tests/test_ingest_jobs.py tests/test_reliability.py tests/test_quality_and_ml.py tests/test_open_meteo.py
```

Trên VPS chung, sau khi merge và `git pull && scripts/env/up.sh`:

```bash
docker compose exec pipeline python -m brweather_data.jobs.data_report runs --hours 24   # T2.1-1
docker compose exec pipeline python -m brweather_data.jobs.data_report weather           # T1.2-1
docker compose exec pipeline python -m brweather_data.jobs.backfill_pm25 --days 14       # T2.3-1
docker compose exec pipeline python -m brweather_data.jobs.data_report pm25 --days 14    # T2.3-1
```

Truy vấn nhanh trong DBeaver/psql:

```sql
SELECT * FROM v_pm25_latest;                                   -- T2.1-2
SELECT * FROM pm25_hourly_series(2161306, now() - interval '3 days', now());   -- T2.3-2
SELECT * FROM v_weather_current_latest;                        -- T1.1-2
SELECT * FROM v_weather_daily_latest ORDER BY lat, lon, day;   -- T1.3-2
SELECT * FROM v_reliability_latest;                            -- T4.1-3
SELECT run_id, job, status, records, errors FROM ingest_runs ORDER BY run_id DESC LIMIT 20;
```

## Đã kiểm thử những gì

- Migration 001–008 chạy trên **db cũ tạo từ `schema.sql` của `main`** và trên **db mới**, mỗi db chạy 2 lần, không lỗi.
- `db/tests/test_storage.sql` (CI đã thêm bước chạy) đạt trên cả hai db: nạp lại cùng lô không trùng; cờ lạ bị từ chối; view trả đủ 5 trạm; chuỗi giờ có NULL đúng chỗ và không phụ thuộc múi giờ phiên làm việc; phát hành 2 lần giữ 2 bản, UPDATE/upsert bị chặn; thời tiết hiện tại trỏ về dữ liệu thô; 7 ngày kèm `issued_at`. Khi bỏ trigger thì kiểm thử báo lỗi, tức là kiểm thử bắt được lỗi thật.
- 58 kiểm thử pytest cho phần mới đạt.
- Chạy thử end-to-end trên Postgres 16 với nguồn OpenAQ/Open-Meteo giả (không gọi API thật): 5 trạm, lượt 2 không sinh bản mới, mức tin cậy đúng cho trạm khỏe / kẹt / nhảy vọt / cũ, báo cáo `data_report` chạy được.
- **Chưa chạy với API thật** (máy làm việc của Claude không có mạng ra ngoài và không dùng khóa OpenAQ của nhóm). Lần chạy đầu trên VPS là bước kiểm tra thật.
