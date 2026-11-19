# Kết luận cổng dữ liệu OpenAQ tuần 1

**Ngày chạy:** 16/11/2026 (Asia/Bangkok)  
**Script:** `scripts/check_data_gate.ps1`  
**Phạm vi:** 5 trạm đang hoạt động và trạm lịch sử 7441  
**Cửa sổ tải:** 730 ngày gần nhất; riêng trạm mới dùng từ bản ghi đầu tiên, trạm đã dừng dùng đến bản ghi cuối cùng  
**Kết quả gốc:** `scripts/data_gate_result.csv`  
**SHA-256 CSV:** `2B02D83AB7DD73F4D365E1888E873CCBB45A77FC6F2CD7CAAC9C49F17AE3D79C`

## Tiêu chí

- **Mức 1 — đủ chạy pipeline:** lịch sử ít nhất 90 ngày và có dữ liệu ít nhất 80% số giờ trong 90 ngày cuối của trạm.
- **Mức 2 — đủ phân tích mô hình:** lịch sử ít nhất 180 ngày, có dữ liệu ít nhất 80% số giờ trong cửa sổ kiểm tra và có ít nhất 720 giờ vào các tháng 11–3.

## Kết quả từng trạm

| Location ID | Trạm | Trạng thái sử dụng | Coverage 90 ngày cuối | Coverage cửa sổ | Giờ tháng 11–3 | Gap dài nhất | Mức 1 | Mức 2 |
|---:|---|---|---:|---:|---:|---:|---|---|
| 2161306 | Minh Khai – Bắc Từ Liêm | Đang cập nhật | 21,9% | 24,7% | 1.916 | 3.850 giờ | **FAIL** | **FAIL** |
| 2161292 | Số 46 Lưu Quang Vũ | Đang cập nhật | 22,7% | 64,9% | 4.866 | 860 giờ | **FAIL** | **FAIL** |
| 4946812 | Công viên Nhân Chính – Khuất Duy Tiến | Đang cập nhật | 99,9% | 96,4% | 3.898 | 87 giờ | **PASS** | **PASS** |
| 4946813 | Số 1 Giải Phóng – Bạch Mai (ĐHBK) | Đang cập nhật | 92,7% | 92,8% | 3.706 | 137 giờ | **PASS** | **PASS** |
| 6123215 | Dragon | Đang cập nhật | 98,3% | 97,2% | 3.730 | 120 giờ | **PASS** | **PASS** |
| 7441 | Hanoi | Đã dừng ngày 09/04/2025 | 98,0%* | 82,4% | 2.648 | 557 giờ | **PASS** | **PASS** |

\* Coverage 90 ngày của 7441 được tính lùi từ bản ghi cuối của trạm, không phải 90 ngày tính từ ngày chạy.

## Kết luận Mức 1

**CONDITIONAL PASS.** Pipeline có thể chạy với ba trạm đang cập nhật đạt Mức 1: `4946812`, `4946813` và `6123215`.

Hai trạm `2161306` và `2161292` không đạt do coverage 90 ngày chỉ khoảng 22%; không nên coi chúng là nguồn đầu vào liên tục hoặc đưa vào đánh giá chung mà không công bố rõ giới hạn. Trạm `7441` đạt về lịch sử nhưng đã dừng cập nhật, vì vậy chỉ dùng cho backfill/nghiên cứu, không dùng cho dữ liệu live.

Nếu tiêu chí nghiệm thu yêu cầu **cả 5 trạm đang hoạt động** cùng đạt, Mức 1 của toàn bộ phạm vi là **FAIL**. Nếu MVP cho phép dùng tập trạm đạt gate, kết luận là **CONDITIONAL PASS**.

## Kết luận Mức 2

**CONDITIONAL PASS.** Ba trạm đang cập nhật `4946812`, `4946813`, `6123215` và trạm lịch sử `7441` đạt các ngưỡng định lượng của Mức 2.

Kết quả mô hình chỉ được kết luận cho từng sensor và giai đoạn có dữ liệu hợp lệ. Không được tổng quát sang `2161306`, `2161292` hoặc toàn Hà Nội. Các gap dài 87–137 giờ ở ba trạm đang hoạt động và 557 giờ ở 7441 phải được loại khỏi mẫu đi xuyên gap hoặc được báo cáo riêng.

Mức 2 trong báo cáo này chỉ là **cổng độ đầy đủ dữ liệu**. Nó không tự xác nhận giấy phép, cấp thiết bị hay tư cách ground truth. Theo audit riêng của dự án, giấy phép của hai trạm mạng Hà Nội `4946812` và `4946813` vẫn chưa xác minh; Dragon là cảm biến cộng đồng `is_monitor=false`.

## Quyết định gửi nhóm

1. Dùng `4946812`, `4946813`, `6123215` cho pipeline thử nghiệm; gắn phạm vi theo từng sensor.
2. Giữ `2161306`, `2161292` ở trạng thái không đạt gate; không dùng cho huấn luyện/đánh giá chuỗi liên tục.
3. Dùng `7441` cho dữ liệu lịch sử có giới hạn, không đưa vào luồng live.
4. Chỉ huấn luyện hoặc đánh giá khi feature và target không đi qua các khoảng thiếu; chia tập theo thời gian.
5. Không tuyên bố kết quả đại diện cho toàn Hà Nội; xử lý giấy phép và provenance là cổng riêng trước khi công bố.
