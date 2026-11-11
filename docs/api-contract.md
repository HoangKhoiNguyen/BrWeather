# Hợp đồng API (backend → app)

Base URL: `http://<host>:8080/api/v1`. Thời gian trả về theo ISO 8601 UTC; app tự đổi sang giờ Việt Nam. Giá trị thiếu là `null`, không bao giờ là `0`.

Mọi số liệu đều kèm `source`, `kind` (`observed` | `modelled` | `forecast`) và thời điểm.

| Phương thức | Đường dẫn | Chức năng | Mô tả |
|---|---|---|---|
| GET | `/stations` | F01 | Danh sách trạm, tọa độ, bản ghi PM2.5 mới nhất, độ tin cậy, trạng thái (`ok` / `stale` / `missing`) |
| GET | `/stations/nearest?lat=&lon=` | F01, F11 | Trạm gần nhất và khoảng cách (m) |
| GET | `/stations/{id}/detail` | F02–F04 | Gộp cho màn hình chi tiết: `history` 24 giờ, `forecast`, `forecastIssuedAt`, `modelVersion`, `anomalies` |
| GET | `/stations/{id}/history?from=&to=` | F02 | Chuỗi PM2.5 theo giờ; giờ thiếu trả `null` |
| GET | `/stations/{id}/forecast` | F03 | Dự báo 24 giờ, `issuedAt`, `modelVersion` |
| GET | `/stations/{id}/anomalies?days=14` | F04 | Danh sách bất thường, loại `data` / `environment` / `needs_review` |
| GET | `/weather?lat=&lon=` | F09 | Hiện tại, 24 giờ, 7 ngày; `fetchedAt`, `validTime` |
| POST | `/recommendations` | F06 | Body: `durationMinutes`, `windowStartHour`, `windowEndHour` (giờ Việt Nam, ngày mai), sau này thêm `lat`, `lon`. Trả `options` (tối đa 3 khung giờ, lý do), `explanation`, `usedFallback` |
| POST | `/explanations` | F05 | Body: loại (`current` / `forecast` / `recommendation`) + id. Trả đoạn giải thích, cờ `fallback` nếu dùng văn bản mẫu |
| PUT | `/devices/{deviceId}/subscriptions` | F07a | Địa điểm theo dõi và ngưỡng của thiết bị ẩn danh |
| GET | `/devices/{deviceId}/alerts` | F07a | Cảnh báo đã sinh, kèm lý do |

Ví dụ phần tử của `/stations`:

```json
{
  "id": 2161306,
  "name": "Minh Khai - Bắc Từ Liêm",
  "lat": 21.07, "lon": 105.76,
  "distanceKm": 7.3,
  "latest": {
    "pm25": 48.2, "unit": "µg/m³",
    "measuredAt": "2026-11-10T03:00:00Z",
    "source": "OpenAQ", "kind": "observed",
    "reliability": "high", "status": "ok"
  }
}
```
