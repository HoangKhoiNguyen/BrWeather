# Bộ quy tắc khuyến cáo (T6.2-1) và bảng ca kiểm thử (T6.2-4)

**Trạng thái: bản nháp chờ nhóm duyệt.** Claude soạn ngày 23/11/2026 cho kiennt (T6.2-1) và hieund (T6.2-4).

- Quy tắc, máy đọc được: `rules/recommendation_rules.json`. Đây là nguồn duy nhất cho cả backend lẫn pipeline.
- Bảng ca kiểm thử: `rules/recommendation_cases.json` (27 ca). Chạy tự động bằng `data-pipeline/tests/test_recommendations.py`.
- Bộ đánh giá tham chiếu: `data-pipeline/src/brweather_data/recommendations.py`. Bộ máy thật ở backend là việc của nguyenhk (T6.2-2), chỉ cần cho kết quả giống bảng ca.

## Nguyên tắc

1. **Không tính AQI.** Ngưỡng PM2.5 dùng nồng độ µg/m³. Các mốc 50/80/150/250 là điểm gãy PM2.5 trong QĐ 1459/QĐ-TCMT, dùng để gắn với các mức khuyến cáo của Bộ Y tế (vốn được nêu theo AQI).
2. **Thiếu dữ liệu không thành 0.** Đầu vào thiếu hoặc PM2.5 cũ quá 3 giờ thì backend truyền `null`. Quy tắc dùng đầu vào đó bị bỏ qua, và chủ đề hoàn toàn không có dữ liệu được báo trong `missing_topics` để app ghi "Không đủ dữ liệu".
3. **Mỗi khuyến cáo nói rõ số liệu dẫn tới** (trường `evidence`), đúng tiêu chí US6.2.
4. **Trong một nhóm chỉ hiện mức nặng nhất.** Ví dụ PM2.5 = 160 chỉ hiện "hạn chế tối đa", không hiện thêm "hạn chế".
5. **Luôn kèm dòng** "Khuyến cáo chung, không thay thế tư vấn y tế."
6. Không có lời khuyên về thuốc, chẩn đoán hay điều trị; AI (US6.1) chỉ diễn đạt lại.

## Bảng quy tắc

| Mã | Điều kiện | Khuyến cáo | Căn cứ |
|---|---|---|---|
| PM_MASK | PM2.5 > 50 µg/m³ | Đeo khẩu trang đạt chuẩn, đeo đúng cách khi ra ngoài | Bộ Y tế khuyến cáo đeo khẩu trang bảo đảm chất lượng khi ra khỏi nhà; mốc 50 = giới hạn 24 giờ QCVN 05:2023 (45 từ 2026) và mốc bắt đầu mức "Kém" trong QĐ 1459. **Mốc 50 là lựa chọn của nhóm** |
| PM_LIMIT_OUTDOOR | PM2.5 > 80 | Hạn chế hoạt động ngoài trời, chọn thời điểm ít ô nhiễm; có triệu chứng thì đến cơ sở y tế | Bộ Y tế, mức "Xấu" |
| PM_MINIMIZE_OUTDOOR | PM2.5 > 150 | Hạn chế tối đa hoạt động ngoài trời; đóng cửa sổ nếu gần nơi ô nhiễm | Bộ Y tế, mức "Rất xấu" |
| PM_AVOID_OUTDOOR | PM2.5 > 250 | Tránh hoạt động ngoài trời, chuyển vào trong nhà | Bộ Y tế, mức "Nguy hại" |
| RAIN_COAT | Khả năng mưa cao nhất 6 giờ tới ≥ 50% | Mang theo áo mưa | Product backlog, Phụ lục C (ngưỡng nhóm chọn) |
| RAIN_HEAVY | Mưa dự báo 12 giờ tới > 25 mm | Có thể mưa to: mang áo mưa, hạn chế đi lại | `docs/weather-thresholds.md` (SP-04) |
| THUNDERSTORM | Mã thời tiết 95/96/99 trong 6 giờ tới | Hạn chế ra ngoài, tránh trú dưới cây cao | SP-04 |
| HEAT | Nhiệt độ cao nhất hôm nay > 35°C | Tránh ra ngoài giờ trưa, uống đủ nước, che nắng | QĐ 18/2021 (SP-04) |
| HEAT_SEVERE | ≥ 37°C | Như trên + chú ý người già, trẻ nhỏ | SP-04 (chờ mentor xác nhận) |
| HEAT_EXTREME | ≥ 39°C | Hạn chế ra ngoài từ trưa đến chiều… | SP-04 (chờ mentor xác nhận) |
| UV_PROTECT | UV cao nhất hôm nay ≥ 3 | Che nắng: áo dài tay, mũ, kem chống nắng; tìm bóng râm buổi trưa | WHO: cần che nắng khi UV từ 3 trở lên |
| UV_AVOID_MIDDAY | UV ≥ 8 | Tránh ra ngoài giữa trưa, tìm bóng râm | WHO: mức 8 trở lên |

Mốc trong ngoặc: ">" là lớn hơn hẳn, "≥" là từ mốc đó trở lên. Mỗi mốc có một ca kiểm thử đúng biên trong bảng ca.

## Căn cứ đã tra (23/11/2026)

- **Bộ Y tế:** theo Báo Nhân Dân, Bộ Y tế khuyến cáo đeo khẩu trang bảo đảm chất lượng khi ra khỏi nhà và có biện pháp riêng cho từng mức AQI. Theo Báo Đại biểu Nhân dân, ở mức xấu (AQI 151–200) người dân cần hạn chế hoạt động ngoài trời. Ở mức nguy hại (AQI 301–500), Bộ Y tế khuyên tránh các hoạt động ngoài trời và chuyển vào trong nhà. **Chưa tìm được văn bản gốc trên cổng Bộ Y tế**, cần bổ sung trước khi chốt.
- **QCVN 05:2023/BTNMT:** giới hạn PM2.5 trung bình 24 giờ là 50 µg/m³, trung bình năm là 25 µg/m³. Có thêm giá trị 45 kèm chú thích áp dụng từ 01/01/2026. Bản trích văn bản không cho biết rõ con số 45 thuộc cột nào. Suy luận là cột 24 giờ, vì 45 lớn hơn giới hạn năm 25 nên không thể là mức siết của cột năm. **Cần mở bản PDF gốc để xác nhận.**
- **WHO 2021:** ngưỡng hướng dẫn PM2.5 là 15 µg/m³ (24 giờ) và 5 µg/m³ (năm). Mức này thấp hơn nhiều so với PM2.5 thường gặp ở Hà Nội, nên nếu dùng làm ngưỡng khuyến cáo thì gần như ngày nào app cũng cảnh báo. Vì vậy chỉ ghi để tham chiếu.
- **WHO, chỉ số UV:** cần che nắng khi UV từ 3 trở lên. Từ 8 trở lên nên tránh ra ngoài giữa trưa và tìm bóng râm.

## Điểm cần nhóm quyết định

1. Mốc khẩu trang 50 µg/m³ hay 45 µg/m³ (giới hạn 24 giờ mới của QCVN từ 2026)? Lưu ý: QCVN là giới hạn trung bình 24 giờ, còn app so với giá trị theo giờ.
2. Mốc nắng nóng gay gắt 37°C và 39°C đang chờ mentor (theo SP-04).
3. Đổi một mốc thì sửa ở `recommendation_rules.json` **và** ca biên tương ứng trong `recommendation_cases.json`. Kiểm thử sẽ báo nếu một mốc thiếu ca biên.

## Nguồn

- Bộ Y tế khuyến cáo (Báo Nhân Dân): https://nhandan.vn/bo-y-te-khuyen-cao-phong-chong-anh-huong-cua-o-nhiem-khong-khi-toi-suc-khoe-post792870.html
- Bộ Y tế theo mức AQI (Báo Đại biểu Nhân dân): https://daibieunhandan.vn/ha-noi-o-nhiem-khong-khi-nghiem-trong-bo-y-te-dua-ra-khuyen-cao-10398175.html
- QCVN 05:2023/BTNMT: https://tnmt.langson.gov.vn/upload/105376/20240404/01-btnmt-qc05_22dbf.pdf
- QĐ 1459/QĐ-TCMT: https://vea.mae.gov.vn/Data/files/QD%201459%20TCMT%20ngay%2012_11_2019%20AQI%281%29.pdf
- WHO AQG 2021 (Santé publique France): https://www.santepubliquefrance.fr/en/les-actualites/air-pollution-who-revises-its-guideline-values-major-air-pollutants
- WHO, UV index: https://www.who.int/news-room/q-a-detail/radiation-the-ultraviolet-(uv)-index
