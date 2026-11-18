# brWeather backend

Spring Boot 3.3, Java 21, PostgreSQL 16. API: `/api/v1/...`, xem [docs/api-contract.md](../docs/api-contract.md).

## Endpoint đã có (Sprint 1)

| Đường dẫn | Ghi chú |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `GET /stations?lat=&lon=` | Sắp xếp gần → xa, có `distanceKm`. Không gửi `lat`/`lon` thì tính từ trung tâm Hà Nội |
| `GET /stations/nearest?lat=&lon=` | Bắt buộc `lat`, `lon`. App cảnh báo khi `distanceKm > 10` |
| `GET /stations/{id}/forecast` | `available:false` + các trường `null` khi chưa có dự báo; 404 khi trạm không tồn tại |
| `GET /stations/{id}/detail` | `history` luôn 24 ô theo giờ (giờ thiếu = `null`), forecast, anomalies 14 ngày |
| `GET /weather?lat=&lon=` | Lấy snapshot Open-Meteo gần nhất trong 25 km; `daily` tính theo ngày giờ Việt Nam; 404 nếu không có |

Lỗi luôn là JSON `{"error","message","time"}`: 400 khi tham số sai, 404 khi không có dữ liệu.

## Chạy trên máy

```bash
cp .env.example .env          # ở thư mục gốc repo, KHÔNG commit .env
docker compose up -d db migrate
docker compose exec -T db psql -U brweather -d brweather < db/seed/dev-sample.sql   # dữ liệu mẫu, tuỳ chọn
cd backend && mvn spring-boot:run
```

Hoặc trong IntelliJ: chạy `BrWeatherApplication`, đặt biến môi trường `POSTGRES_USER`, `POSTGRES_PASSWORD`
(và `POSTGRES_PORT` nếu đổi `DB_HOST_PORT` trong `.env`).

Dữ liệu mẫu là trạm giả id 990001–990004, tên có tiền tố `[Mẫu]`: một trạm `ok`, một trạm thiếu 2 giờ,
một trạm `stale`, một trạm `missing`, kèm dự báo, bất thường và 7 ngày thời tiết. Chạy lại file seed để làm mới.

## Lỗi hay gặp trên Windows

- **`bind: An attempt was made to access a socket...` khi `docker compose up`**: cổng 5432 bị Windows giữ.
  Đặt `DB_HOST_PORT=55432` trong `.env` và chạy backend với `POSTGRES_PORT=55432`.
- **`Unable to establish loopback connection`**: thư mục TEMP có đường dẫn lạ. Đặt `TMP`/`TEMP` sang thư mục
  ngắn, ví dụ `F:\tmp`, hoặc thêm `-Djdk.net.unixdomain.tmpdir=F:\tmp`.
- Múi giờ: app ép JVM về UTC khi khởi động (Windows để giờ VN báo `Asia/Saigon`, PostgreSQL 16 từ chối).

## Test

```bash
mvn test
```
