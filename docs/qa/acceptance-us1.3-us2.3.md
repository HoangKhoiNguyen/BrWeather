# Biên bản kiểm thử nghiệm thu US1.3 (T1.3-5) và US2.3 (T2.3-5)

Người kiểm: US1.3: hungpvc; US2.3: hieund. Chạy khi FE xong T1.3-4 và T2.3-4 (nguyenhk). Mẫu do Claude soạn 23/11/2026.
Ghi kết quả vào cột "Kết quả" (Đạt / Không đạt + mã lỗi GitHub). Không đạt thì mở issue `type:bug`, gắn số issue vào đây.

## Chuẩn bị chung

- App bản build mới nhất trên emulator Android (ghi: model emulator, Android version, commit).
- Backend trỏ tới db **có dữ liệu đã biết**: máy cá nhân với dữ liệu mẫu `db/seed/dev-sample.sql`, hoặc server chung (ghi rõ dùng cái nào).
- Đối chiếu số trên app với db bằng các truy vấn dưới mỗi bảng. Giờ trên app là giờ Việt Nam, trong db là UTC (+7).

---

## US1.3 – Thời tiết 7 ngày (T1.3-5)

Tiêu chí: mỗi ngày có cao/thấp, tổng mưa, khả năng mưa, trạng thái, mặt trời mọc/lặn; ghi thời điểm phát hành dự báo.

```sql
-- Số liệu đúng để so (điểm gần địa điểm đã chọn nhất)
SELECT day, temperature_max_c, temperature_min_c, precipitation_sum_mm, precipitation_prob_max_pct,
       weather_code, sunrise AT TIME ZONE 'Asia/Ho_Chi_Minh' AS sunrise_vn,
       sunset AT TIME ZONE 'Asia/Ho_Chi_Minh' AS sunset_vn, issued_at
FROM v_weather_daily_latest ORDER BY lat, lon, day;
```

| # | Bước | Kết quả mong đợi | Kết quả |
|---|---|---|---|
| 1.1 | Mở màn 7 ngày cho một địa điểm ở Hà Nội | Có đúng 7 dòng, ngày đầu là hôm nay (giờ VN) | |
| 1.2 | So cao/thấp của 3 ngày bất kỳ với truy vấn | Khớp (làm tròn hiển thị ≤ 0,5°C), đơn vị °C | |
| 1.3 | So tổng mưa và khả năng mưa | Khớp; đơn vị mm và %; khả năng mưa **không** viết thành "mưa X% thời gian" | |
| 1.4 | Trạng thái (biểu tượng/chữ) | Đúng bảng mã WMO cho `weather_code` | |
| 1.5 | Mặt trời mọc/lặn | Giờ VN, khớp truy vấn (± 1 phút) | |
| 1.6 | Thời điểm phát hành | Hiện "Cập nhật lúc …" khớp `issued_at` (đổi sang giờ VN) | |
| 1.7 | Nguồn | Ghi "Dữ liệu mô hình – Open-Meteo" | |
| 1.8 | Thiếu một giá trị: trên db **máy cá nhân** chạy `UPDATE weather_daily SET precipitation_prob_max_pct = NULL WHERE snapshot_id = (SELECT max(snapshot_id) FROM weather_snapshots) AND day = current_date + 1;` | Ngày mai hiện "Không có dữ liệu" cho khả năng mưa, **không** hiện 0% | |
| 1.9 | Dữ liệu cũ: trên db máy cá nhân dừng pipeline, đổi `fetched_at` của snapshot mới nhất lùi 4 giờ | App gắn nhãn "cũ" | |
| 1.10 | Tắt mạng/tắt backend rồi mở lại màn | App không sập; hiện bản đã lưu kèm nhãn hoặc thông báo lỗi rõ ràng | |

## US2.3 – Diễn biến PM2.5 (T2.3-5)

Tiêu chí: chọn 1, 3, 7 ngày; biểu đồ theo giờ; giờ thiếu để trống, không nối, không vẽ 0; số đo và dữ liệu mô hình vẽ khác nét.

Dữ liệu mẫu `dev-sample.sql`: trạm **[Mẫu] Hoàn Kiếm (990001)** thiếu 2 giờ (6 và 7 giờ trước). Trên server chung dùng:

```sql
SELECT hour AT TIME ZONE 'Asia/Ho_Chi_Minh' AS gio_vn, value, status
FROM pm25_hourly_series(<station_id>, now() - interval '3 days', now())
WHERE status <> 'ok';          -- các giờ phải hiện trống trên biểu đồ
```

| # | Bước | Kết quả mong đợi | Kết quả |
|---|---|---|---|
| 2.1 | Mở chi tiết một trạm, chọn 1 ngày | Biểu đồ 24 điểm giờ, trục thời gian giờ VN | |
| 2.2 | Chọn 3 ngày, rồi 7 ngày | Đổi đúng khoảng; không treo khi 168 điểm | |
| 2.3 | Tìm các giờ có `status <> 'ok'` từ truy vấn | Các giờ đó **để trống**, đường không nối qua, không có điểm ở 0 | |
| 2.4 | So 3 giờ bất kỳ có số đo | Khớp `value` (µg/m³) | |
| 2.5 | Số đo và dữ liệu mô hình/dự báo cùng biểu đồ | Khác nét (ví dụ liền và đứt), có chú giải | |
| 2.6 | Trạm không có số đo trong khoảng chọn | Hiện "Không có dữ liệu", không vẽ đường 0 | |
| 2.7 | Nguồn và đơn vị | Ghi OpenAQ, µg/m³ | |
| 2.8 | Xoay màn hình / quay lại | Không mất lựa chọn khoảng ngày, không sập | |

## Kết luận

| Story | Số bước đạt | Lỗi mở | Đạt nghiệm thu? | Người kiểm, ngày |
|---|---|---|---|---|
| US1.3 | /10 | | | |
| US2.3 | /8 | | | |
