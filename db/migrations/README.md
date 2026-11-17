# Migration cơ sở dữ liệu

`scripts/db/migrate.sh` (service `migrate` trong Docker Compose) chạy mỗi lần môi trường khởi động:

1. Áp `db/schema.sql`. File này chỉ dùng `CREATE ... IF NOT EXISTS`, nên **chỉ tạo được bảng/index mới**, không sửa được bảng đã có dữ liệu.
2. Chạy các file `db/migrations/*.sql` chưa chạy, theo thứ tự tên. File nào chạy xong được ghi vào bảng `schema_migrations` và không chạy lại.

## Khi nào cần viết migration

| Thay đổi | Làm ở đâu |
|---|---|
| Thêm bảng mới | Thêm `CREATE TABLE IF NOT EXISTS` vào `schema.sql` là đủ |
| Thêm cột, đổi kiểu, thêm ràng buộc vào bảng **đã có** | Sửa `schema.sql` (để db mới tạo đúng) **và** thêm file migration (để db đang chạy được cập nhật) |

Vì db mới tạo sẽ chạy `schema.sql` (đã có cột) rồi mới chạy migration, nên migration phải **chạy được cả khi thay đổi đã có sẵn**: dùng `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `DROP ... IF EXISTS`.

## Quy ước

- Tên file: `NNN_mo_ta_ngan.sql`, số tăng dần, ví dụ `001_weather_current_fields.sql`.
- Không sửa file migration đã merge vào `main`; cần đổi thì viết file mới.
- Mỗi file chạy trong một transaction. Lỗi thì không có gì được ghi, service `migrate` báo lỗi và backend/pipeline sẽ không khởi động cho tới khi sửa xong.

Ví dụ `001_weather_current_fields.sql`:

```sql
ALTER TABLE weather_snapshots ADD COLUMN IF NOT EXISTS raw_payload_id BIGINT REFERENCES raw_payloads(id);
```
