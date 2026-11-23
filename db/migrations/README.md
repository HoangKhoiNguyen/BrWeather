# Migration cơ sở dữ liệu

`scripts/db/migrate.sh` (service `migrate` trong Docker Compose) chạy mỗi lần môi trường khởi động:

1. Áp `db/schema.sql`. File này chỉ dùng `CREATE ... IF NOT EXISTS`, nên **chỉ tạo được bảng/index mới**, không sửa được bảng đã có dữ liệu.
2. Chạy các file `db/migrations/*.sql` chưa chạy, theo thứ tự tên. File nào chạy xong được ghi vào bảng `schema_migrations` và không chạy lại.

## Khi nào cần viết migration

| Thay đổi | Làm ở đâu |
|---|---|
| Thêm bảng mới | Thêm `CREATE TABLE IF NOT EXISTS` vào `schema.sql` là đủ |
| Thêm cột, đổi kiểu, thêm ràng buộc vào bảng **đã có** | Sửa `schema.sql` (để db mới tạo đúng) **và** thêm file migration (để db đang chạy được cập nhật) |
| View, hàm, trigger | **Chỉ** trong migration, dùng `CREATE OR REPLACE` / `DROP ... IF EXISTS`. Không đặt trong `schema.sql`: file đó chạy trước migration, view dùng cột do migration thêm sẽ lỗi trên db đang chạy |

Vì db mới tạo sẽ chạy `schema.sql` (đã có cột) rồi mới chạy migration, nên migration phải **chạy được cả khi thay đổi đã có sẵn**: dùng `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `DROP ... IF EXISTS`.

## Quy ước

- Tên file: `NNN_mo_ta_ngan.sql`, số tăng dần, ví dụ `001_weather_current_fields.sql`.
- Không sửa file migration đã merge vào `main`; cần đổi thì viết file mới.
- Mỗi file chạy trong một transaction. Lỗi thì không có gì được ghi, service `migrate` báo lỗi và backend/pipeline sẽ không khởi động cho tới khi sửa xong.

Ví dụ `001_weather_current_fields.sql`:

```sql
ALTER TABLE weather_snapshots ADD COLUMN IF NOT EXISTS raw_payload_id BIGINT REFERENCES raw_payloads(id);
```

## Danh sách migration

| File | Task | Nội dung |
|---|---|---|
| `001_weather_snapshot_current.sql` | T1.1-2 | Cột `current_*` của thời tiết hiện tại |
| `002_weather_current_raw_link.sql` | T1.1-2 | `raw_payload_id` liên kết dữ liệu thô; view `v_weather_current_latest` |
| `003_weather_daily_forecast.sql` | T1.3-2 | `precipitation_prob_max_pct`; view `v_weather_daily_latest` (7 ngày + `issued_at`) |
| `004_pm25_clean_latest.sql` | T2.1-2 | Ràng buộc giá trị `quality_flag`; view `v_pm25_latest` |
| `005_pm25_forecasts_append_only.sql` | T3.1-1 | Trigger chặn UPDATE dự báo; chỉ mục `(station_id, target_time)`; view `v_pm25_forecast_latest` |
| `006_pm25_hourly_series.sql` | T2.3-2 | Hàm `pm25_hourly_series(station, from, to)`: đủ lịch giờ, giờ thiếu NULL |
| `007_reliability_details.sql` | T4.1-3 | Cột `details` của `reliability_scores`; view `v_reliability_latest` |
| `008_ingest_run_errors.sql` | T2.1-1, C-06 | Cột `errors` của `ingest_runs` (lỗi nguồn / lỗi nội bộ theo trạm) |

Kiểm thử: `bash db/tests/run.sh` (CI chạy sau migration). Các file `db/tests/test_*.sql` tự ROLLBACK, không để lại dữ liệu.
