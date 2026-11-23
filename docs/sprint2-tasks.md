# Sprint 2 (20–26/11): các task còn lại, trừ phần của nguyenhk

Nhánh `claude/sprint2-rest`, dựng trên `claude/data-sprint1-2` (phần thu thập/lưu trữ, xem `docs/data-tasks-sprint1-2.md`).
Claude viết theo yêu cầu của kiennt ngày 23/11/2026. Mỗi người review phần của mình trước khi merge; code phần AI của kiennt cần người khác review (product-backlog mục 12).

## Tóm tắt

| Task | Người | Làm gì trên nhánh | Còn phải làm (người thật) |
|---|---|---|---|
| T5.1-1 Phát hiện bất thường mỗi giờ | kiennt | `jobs/detect_anomalies.py` chạy trong scheduler sau mức tin cậy; robust z chỉ nhìn quá khứ, gộp giờ thành sự kiện, ghi `anomalies` (migration 009), chạy lại không trùng, giữ phân loại đã rà soát | Merge; xem bảng `anomalies` sau 1 ngày trên VPS |
| T5.1-2 Chọn cửa sổ và ngưỡng | kiennt | `docs/anomaly-parameters.md` (72 giờ, \|z\| > 4,3, lệch ≥ 15 µg/m³, có lý do); lệnh `anomaly_review tune` | Chạy `tune` trên dữ liệu thật sau backfill, chốt và ghi vào nhật ký quyết định |
| T5.1-5 Trích 20 ca thật | kiennt | Lệnh `anomaly_review export` (rải đều loại và trạm, kèm số đo 24 giờ trước/sau) | Chạy trên VPS sau backfill (`docs/qa/t5.1-6-ra-soat-bat-thuong.md`) |
| T5.1-6 Rà soát 20 ca | kiennt + người ngoài | Hướng dẫn rà soát + lệnh `anomaly_review summary` | Ngồi rà soát với một người ngoài nhóm |
| T5.2-1 Phân loại lỗi đo / biến động thật / cần kiểm tra | hieund | `quality/anomaly_classifier.py`: 5 quy tắc theo thứ tự, so với trạm lân cận 10 km, không gán nguyên nhân | Review, merge |
| T5.2-2 Ca lỗi giả lập có nhãn | hungpvc | `quality/synthetic_cases.py` + `tests/fixtures/anomaly_synthetic_cases.json`: 10 ca (đứng yên, nhảy vọt, mất tín hiệu, tăng/giảm thật, không lân cận, tăng cục bộ, ngoài khoảng, bình thường) | Review, merge |
| T4.1-4 Câu lý do dễ hiểu | kiennt | `quality/reliability_text.py` + `docs/reliability-reasons.md`; job tin cậy lưu sẵn nhãn và câu vào `details` | Duyệt câu; chốt 5 hay 6 giờ "đứng yên" |
| T4.1-7 Thử với 5 người | kiennt | Kịch bản và phiếu chấm `docs/qa/t4.1-7-thu-nhan-tin-cay.md` | Thử với 5 người (cần ≥ 4/5 hiểu đúng) |
| T6.2-1 Bộ quy tắc khuyến cáo | kiennt | `rules/recommendation_rules.json` + `docs/recommendation-rules.md`: 12 quy tắc (khẩu trang, hoạt động ngoài trời, áo mưa, mưa to, dông, nắng nóng, UV), mỗi quy tắc có nguồn | Nhóm duyệt; quyết định mốc khẩu trang 50 hay 45 µg/m³; mở PDF gốc QCVN 05:2023 để xác nhận cột 45 µg/m³; tìm văn bản gốc của Bộ Y tế |
| T6.2-4 Bảng ca kiểm thử khuyến cáo | hieund | `rules/recommendation_cases.json` (27 ca: mọi biên ngưỡng, thiếu dữ liệu, giá trị 0, ngày tổng hợp) chạy tự động qua `tests/test_recommendations.py` | Review; nguyenhk dùng lại bảng này trong JUnit cho T6.2-2 |
| T1.3-5 Kiểm thử nghiệm thu US1.3 | hungpvc | Biên bản mẫu 10 bước `docs/qa/acceptance-us1.3-us2.3.md` | Kiểm trên emulator khi FE T1.3-4 xong |
| T2.3-5 Kiểm thử nghiệm thu US2.3 | hieund | Biên bản mẫu 8 bước (cùng file) | Kiểm khi FE T2.3-4 xong |
| C-05 Tuyển 5 người UAT | kiennt | Tin nhắn mời, câu sàng lọc, lời đồng ý, bảng theo dõi `docs/qa/c05-tuyen-uat.md` | Gửi tin, chốt 5 người và lịch trước 26/11 |
| SP-02 | hungpvc | Đã có bản nháp từ nhánh trước | Gọi thử FIRMS, chốt |
| (CI) | kiennt | `tests/conftest.py`: test nghiên cứu cần thư mục `data/` (không có trong repo) chuyển thành **skipped** kèm đường dẫn file thiếu, không còn làm đỏ CI | — |

## Kiểm thử đã chạy (23/11/2026)

- pytest: **162 đạt, 15 bỏ qua** (thiếu dữ liệu nghiên cứu cục bộ), 0 lỗi.
- Migration 001–009 chạy 2 lần trên db cũ (schema của `main`) và db mới; `db/tests/test_storage.sql` đạt, kể cả kiểm thử mới cho `anomalies` (chống trùng sự kiện, hướng hợp lệ).
- Chạy end-to-end trên Postgres 16: nạp 10 ca giả lập vào `air_measurements` rồi chạy `compute_reliability` và `detect_anomalies` 2 lần.
  - Cả 10 ca ra đúng loại và lý do mong đợi; lượt 2 chỉ cập nhật, không trùng.
  - Sự kiện đã đánh dấu `reviewed` giữ nguyên phân loại.
  - Mức tin cậy lưu kèm nhãn và câu.
- Chưa chạy với dữ liệu OpenAQ thật (cần VPS + backfill). Ngưỡng bất thường cần kiểm tra lại bằng `anomaly_review tune`.

## Cho nguyenhk (không làm trên nhánh này, chỉ ghi lại để nối)

- T4.1-5: đọc `details.level_label`, `details.summary`, `reasons` từ `v_reliability_latest` (mẫu JSON trong `docs/reliability-reasons.md`).
- T5.1-3: `anomalies` có thêm `direction`, `peak_value`, `baseline_value`, `details.category_label`. Dùng chỉ mục `(station_id, start_time DESC)`.
- T6.2-2: đọc `rules/recommendation_rules.json`, chạy `rules/recommendation_cases.json` trong JUnit. Truyền `null` khi thiếu dữ liệu hoặc PM2.5 cũ quá 3 giờ.
