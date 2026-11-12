# Ngưỡng thời tiết bất thường

Dùng cho: phát hiện thời tiết bất thường (US5.3) và khuyến cáo (US6.2). Kết quả của spike SP-04.

Duyệt: kiennt (Product Owner), 12/11/2026. Ngưỡng gió trên đất liền và hai mức "gay gắt", "đặc biệt gay gắt" chờ mentor xác nhận.

## Nguyên tắc

- Dùng ngưỡng trong văn bản chính thức của Việt Nam khi có. Chỗ văn bản không quy định thì ghi rõ là ngưỡng nhóm chọn.
- App chỉ hiển thị "theo dự báo của Open-Meteo, vượt ngưỡng …" kèm thời điểm phát hành.
- App không công bố cấp độ rủi ro thiên tai và không thay cảnh báo của cơ quan chức năng.
- Ngày tính theo giờ Việt Nam (`timezone=Asia/Ho_Chi_Minh`).

## Bảng ngưỡng

| Hiện tượng | Mức | Ngưỡng | Căn cứ | Biến Open-Meteo |
|---|---|---|---|---|
| Nắng nóng | Nắng nóng | Nhiệt độ cao nhất ngày > 35°C | QĐ 18/2021/QĐ-TTg, Điều 5 khoản 21 | `temperature_2m_max` (theo ngày) |
| | Nắng nóng gay gắt | 37–39°C | Mốc trong cấp độ rủi ro nắng nóng, QĐ 18/2021, Điều 47 | `temperature_2m_max` |
| | Nắng nóng đặc biệt gay gắt | ≥ 39°C | Như trên | `temperature_2m_max` |
| | Đợt nắng nóng | > 35°C liên tiếp từ 3 ngày | QĐ 18/2021, Điều 47 | Đếm ngày liên tiếp trong dự báo 7 ngày |
| Rét | Rét đậm | Nhiệt độ trung bình ngày < 15°C | TT 25/2022/TT-BTNMT, Điều 3 khoản 6 | Trung bình 24 giá trị `temperature_2m` theo giờ |
| | Rét hại | Nhiệt độ trung bình ngày < 13°C | QĐ 18/2021, Điều 5 khoản 18 | Như trên |
| Mưa | Mưa to | > 50 đến 100 mm/24 giờ | QĐ 18/2021, Điều 5 khoản 17 | `precipitation_sum` (theo ngày) |
| | Mưa rất to | > 100 mm/24 giờ | QĐ 18/2021, Điều 5 khoản 17 | `precipitation_sum` |
| | Mưa to trong thời gian ngắn | > 25 mm/12 giờ | Phân cấp mưa theo Trung tâm KTTV quốc gia | Tổng trượt 12 giờ của `precipitation` |
| Gió | Gió mạnh | Trung bình ≥ cấp 6 (≥ 39 km/h) | Bảng cấp gió, Phụ lục III QĐ 18/2021 (ngưỡng cho đất liền do nhóm chọn) | `wind_speed_10m` |
| | Gió giật mạnh | Giật ≥ cấp 7 (≥ 50 km/h) | Như trên | `wind_gusts_10m` |
| Dông | Có dông | Mã thời tiết dông | TT 25/2022, Điều 3 khoản 8 | `weather_code` 95; 96, 99 (kèm mưa đá, chỉ một số mô hình có) |
| Sương mù | Sương mù | Tầm nhìn < 1 km | QĐ 18/2021, Điều 5 khoản 20 | `visibility` < 1000 m hoặc `weather_code` 45, 48 |

Cấp gió (Phụ lục III, QĐ 18/2021): cấp 5 = 29–38 km/h; cấp 6 = 39–49 km/h; cấp 7 = 50–61 km/h; cấp 8 = 62–74 km/h.

Đơn vị mặc định của Open-Meteo: gió km/h, tầm nhìn mét. Theo ngày không có `temperature_2m_mean`, nên nhiệt độ trung bình ngày tính từ dữ liệu theo giờ.

## Khuyến cáo đi kèm

| Điều kiện | Khuyến cáo |
|---|---|
| Nắng nóng trở lên | Tránh ra ngoài giờ trưa, uống đủ nước, che nắng |
| Rét đậm, rét hại | Giữ ấm, chú ý người già và trẻ nhỏ |
| Mưa to, mưa rất to, dông | Mang áo mưa; hạn chế đi lại khi có dông |
| Gió mạnh, gió giật mạnh | Cẩn thận khi đi xe máy, tránh đứng gần cây và biển quảng cáo |
| Sương mù | Đi chậm, bật đèn khi lái xe |

Khuyến cáo luôn kèm dòng "không thay thế tư vấn y tế" (theo tiêu chí US6.2).

## Giới hạn

- Văn bản dựa trên số đo tại trạm; app dùng dự báo mô hình nên có thể lệch.
- Cấp độ rủi ro thiên tai cần số ngày kéo dài và phạm vi nhiều huyện, xã; app không tính.
- Khi viết connector, kiểm tra lại tên biến với endpoint Open-Meteo thực tế.

## Căn cứ

- Quyết định 18/2021/QĐ-TTg quy định về dự báo, cảnh báo, truyền tin thiên tai và cấp độ rủi ro thiên tai.
- Thông tư 25/2022/TT-BTNMT quy định quy trình kỹ thuật dự báo, cảnh báo hiện tượng khí tượng thủy văn nguy hiểm.
- Phân cấp mưa theo Trung tâm Khí tượng Thủy văn quốc gia (Báo Đại biểu Nhân dân, "Hỏi – đáp về các hiện tượng khí tượng thủy văn").
- Open-Meteo, tài liệu biến và bảng mã thời tiết WMO: https://open-meteo.com/en/docs
