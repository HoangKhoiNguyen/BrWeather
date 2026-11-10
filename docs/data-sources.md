# Nguồn dữ liệu

| Nguồn | Dùng cho | Khóa | Lưu trữ được không | Ghi chú |
|---|---|---|---|---|
| OpenAQ API v3 | Số đo PM2.5 tại trạm (nguồn chính) | Có, mỗi người một khóa | Có, ghi nguồn | 60 lượt/phút, 2.000 lượt/giờ mỗi khóa. Không chia sẻ khóa. |
| Open-Meteo Weather | Thời tiết hiện tại, theo giờ, 7 ngày; lịch sử để huấn luyện | Không | Có, ghi nguồn (CC BY 4.0) | Phi thương mại, dưới 10.000 lượt/ngày |
| Open-Meteo Air Quality | PM2.5 từ mô hình (nền, dự phòng) | Không | Có, ghi nguồn | Độ phân giải toàn cầu khoảng 45 km: không dùng để nói khác biệt giữa các phố |
| aqicn (WAQI) | Đối chiếu, hiển thị trực tiếp | Có (token) | **Không**: điều khoản cấm phân phối lại dưới dạng cache/lưu trữ | Bắt buộc ghi nguồn World Air Quality Index Project và cơ quan gốc |
| NASA FIRMS | Lớp điểm cháy (F10, Could) | Có (MAP_KEY) | Có | Chỉ đăng ký khi làm F10 |

## Trạm OpenAQ quanh Hà Nội (kiểm tra 31/10/2026, bán kính 25 km)

Đang hoạt động (dùng cho MVP):

| id | Trạm | Bắt đầu |
|---|---|---|
| 2161306 | Minh Khai – Bắc Từ Liêm | 2024-01 |
| 2161292 | Số 46 Lưu Quang Vũ | 2024-01 |
| 4946812 | Công viên Nhân Chính – Khuất Duy Tiến | 2025-07 |
| 4946813 | Số 1 Giải Phóng – Bạch Mai (ĐHBK) | 2025-07 |
| 6123215 | Dragon | 2025-11 |

Đã ngừng, dùng làm lịch sử: 7441 "Hanoi" (2016-11 → 2025-04), 4946811 "556 Nguyễn Văn Cừ" (2025-07 → 2026-07), nhóm 2161xxx còn lại (2024 → 2025).

Chưa kiểm tra: tỷ lệ giờ có số đo bên trong mỗi khoảng. Chạy `scripts/check_data_gate.ps1`.

## Quy tắc chung

- Mỗi bản ghi lưu: nguồn, mã trạm/tọa độ, chất đo, giá trị, đơn vị, thời điểm đo (UTC), thời điểm lấy, loại dữ liệu (số đo/mô hình/dự báo), cờ chất lượng.
- Không nội suy rồi trình bày như số đo.
- Không tự quy đổi PM2.5 sang AQI bằng công thức chưa xác minh; AQI hiển thị phải ghi tên thang.
