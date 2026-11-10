# Danh sách chức năng

Một gói WBS phục vụ nhiều chức năng; tổng WBS vẫn là 336 giờ (mỗi người 112 giờ).

| Mã | Tính năng | Cần làm để xong | Phụ thuộc | Gói WBS | Ưu tiên |
|---|---|---|---|---|---|
| F00 | Thu thập và làm sạch dữ liệu | Job mỗi giờ lấy OpenAQ (5 trạm đang hoạt động) và Open-Meteo; backfill lịch sử, gồm trạm 7441 (2016–2025); chống trùng; lưu UTC; log lượt chạy; ≥ 95% lượt chạy thành công trong 7 ngày | Khóa OpenAQ | W02 | Must |
| F01 | Bản đồ và tổng quan | Danh mục trạm có tọa độ; API bản ghi mới nhất mỗi trạm; thẻ PM2.5 có giá trị, đơn vị, nguồn, thời điểm, khoảng cách, nhãn số đo/mô hình, mức tin cậy; bốn trạng thái tải, lỗi, thiếu, cũ | F00, F08, F11 | W03, W04 | Must |
| F02 | Lịch sử và xu hướng | API chuỗi theo giờ lọc theo trạm và khoảng thời gian; biểu đồ tách số đo và dữ liệu mô hình; khoảng thiếu để trống | F00 | W03, W04 | Must |
| F03 | Dự báo PM2.5 24 giờ | Job dự báo theo lịch; lưu thời điểm phát hành, phiên bản, nguồn; baseline persistence và seasonal naive; mô hình cây dùng đặc trưng thời tiết (gió, mưa, độ ẩm, lớp biên) là ứng viên; chỉ phát cho chuỗi đủ điều kiện | F00, F09, cổng dữ liệu | W05, W03 | Must |
| F04 | Phát hiện bất thường | Quy tắc biến động + cửa sổ trượt chỉ nhìn quá khứ; phân loại bất thường dữ liệu / môi trường; nhãn "cần kiểm tra" khi không có trạm đối chiếu; đánh giá trên ≥ 20 ca có người rà soát | F00 | W05 | Must |
| F05 | Giải thích bằng AI | Schema vào/ra; kiểm tra từng con số đầu ra; nêu được lý do do thời tiết; văn bản mẫu dự phòng; hạn mức chi phí; bộ 30 ca kiểm thử; giao diện hiển thị | F03, F06 | W06 | Must |
| F06 | Chọn giờ ra ngoài | Nhập địa điểm, thời lượng, khoảng giờ; xếp hạng có trọng số theo PM2.5, khả năng mưa, nhiệt độ trên toàn thời lượng; tối đa 3 lựa chọn có lý do; loại khung thiếu dữ liệu | F03, F09, F11 | W07 | Must |
| F07a | Cảnh báo trong app | Lưu địa điểm theo dõi và ngưỡng theo mã thiết bị ẩn danh; bộ đánh giá chống lặp 60 phút; giao diện cảnh báo; lý do gửi | F01, F11 | W08 | Must |
| F07b | Push Android | Firebase Cloud Messaging; đăng ký token thiết bị; kiểm thử thiết bị thật | F07a | W09 | Should |
| F08 | Độ tin cậy và kiểm chứng | Bốn kiểm tra (phạm vi, đứng yên, độ trễ, so với lân cận) cho điểm Cao/Trung bình/Thấp; độ mới, độ phủ; báo cáo sai số dự báo so với quan trắc | F00 | W02, W05 | Must |
| F09 | Thời tiết đầy đủ | Hiện tại: nhiệt độ, cảm giác như, độ ẩm, mưa, gió, UV, trạng thái; theo giờ 24 giờ; 7 ngày (cao/thấp, tổng mưa, mặt trời mọc/lặn); snapshot có valid_time, fetched_at; null không thành 0 | Open-Meteo | W12 | Must |
| F10 | Lớp điểm cháy | Điểm cháy FIRMS quanh Hà Nội làm bối cảnh, không gán nguyên nhân | Khóa FIRMS | Không có giờ | Could |
| F11 | Chọn địa điểm và cài đặt | GPS hoặc chọn tay; lưu địa điểm yêu thích; tìm trạm gần nhất; xin quyền vị trí đúng lúc, không theo dõi chạy nền | — | W04 | Must |

## Thứ tự theo phụ thuộc

```
F00 Dữ liệu ─┬─► F08 Độ tin cậy ─┐
             ├─► F01 Tổng quan ◄─┤◄── F11 Chọn địa điểm
             ├─► F02 Lịch sử     │
F09 Thời tiết┼─► F03 Dự báo ─────┼─► F06 Chọn giờ ─► F05 AI giải thích
             └─► F04 Bất thường  └─► F07a Cảnh báo ─► F07b Push
```

## Quyết định còn mở

- Cảnh báo lưu theo mã thiết bị ẩn danh (mặc định trong repo) hay có tài khoản đăng nhập (+10–15 giờ).
- F09 mở rộng 7 ngày (+~6 giờ của C) bù bằng giảm F07b.
