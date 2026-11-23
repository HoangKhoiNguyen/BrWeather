# SP-02 – Nguồn điểm cháy và cảnh báo thiên tai chính thức

Spike Sprint 2, người nhận: hungpvc. Bản nháp do Claude soạn ngày 23/11/2026 để Hưng rà soát và kết luận.
Câu hỏi: nguồn nào đạt **tiêu chí nguồn uy tín** (product-backlog mục 5) để làm US10.1 (điểm cháy) và US10.2 (cảnh báo thiên tai)?

Tiêu chí: (1) đơn vị vận hành rõ ràng; (2) có tài liệu API và điều khoản cho lưu trữ/hiển thị lại có ghi nguồn; (3) cập nhật đều, có thời điểm; (4) phân biệt số đo/mô hình/dự báo; (5) đã kiểm tra thực tế phủ Hà Nội.

## Kết luận ngắn

| Nguồn | Dùng cho | (1) | (2) | (3) | (4) | (5) | Kết luận |
|---|---|---|---|---|---|---|---|
| NASA FIRMS (VIIRS/MODIS NRT) | US10.1 điểm cháy | Đạt | Đạt | Đạt | Đạt (điểm phát hiện từ vệ tinh) | **Chưa kiểm** | **Đạt có điều kiện**: làm T10.1-1 sau khi chạy thử 1 lần cho vùng Hà Nội |
| Trung tâm Dự báo KTTV quốc gia (kttv.gov.vn / nchmf.gov.vn) | US10.2 cảnh báo | Đạt | **Không đạt**: chưa tìm thấy API công khai; bản tin là PDF | Đạt | Đạt (là bản tin cảnh báo) | Đạt (phủ cả nước) | **Chưa đạt để tự động hóa**. Chỉ nên hiển thị liên kết tới bản tin gốc |
| VNDMS (Hệ thống giám sát thiên tai Việt Nam) | US10.2 | Đạt | Không đạt: là ứng dụng web, chưa thấy API công khai | – | – | – | Không đạt |
| GDACS (LHQ – EC JRC) | Tham khảo | Đạt | Đạt (API + RSS, chỉ yêu cầu ghi nguồn) | Đạt | Đạt | Chỉ sự kiện lớn tầm quốc tế | **Không dùng cho US10.2**: không phải cơ quan chính thức của Việt Nam, không có cảnh báo cấp địa phương |

**Đề xuất cho PO:** giữ US10.1 (Could) và làm T10.1-1/T10.1-2 nếu còn thời gian ở Sprint 4. US10.2 thu hẹp thành "liên kết tới bản tin cảnh báo mới nhất của Trung tâm Dự báo KTTV quốc gia". Không trích hay tóm tắt nội dung bản tin, không tự tạo cảnh báo (đúng tiêu chí "app không tự tạo cảnh báo thiên tai").

## 1. NASA FIRMS

- **Đơn vị vận hành:** FIRMS do dự án ESDIS của NASA vận hành, thuộc hệ thống dữ liệu gần thời gian thực LANCE.
- **API:** endpoint vùng `/api/area/csv/[MAP_KEY]/[SOURCE]/[AREA_COORDINATES]/[DAY_RANGE]` trả dữ liệu mới nhất từ hôm nay lùi về `DAY_RANGE − 1` ngày; có thể thêm `[DATE]` để lấy một ngày cụ thể. MAP_KEY miễn phí, đăng ký bằng email. Giới hạn mỗi MAP_KEY là 5.000 giao dịch trong 10 phút; yêu cầu nhiều ngày (ví dụ 7 ngày) có thể tính thành nhiều giao dịch. Với 1 lượt/giờ cho vùng Hà Nội, 1–2 ngày, mức dùng rất xa giới hạn.
- **Điều khoản:** NASA chủ trương chia sẻ dữ liệu mở và đề nghị bên cung cấp lại dữ liệu FIRMS cho người khác ghi nhận nguồn theo hướng dẫn. Theo chính sách ESDIS, dữ liệu của sứ mệnh do NASA dẫn dắt mặc định theo giấy phép CC0 nếu không gắn hạn chế riêng. Như vậy được lưu vào kho và hiển thị lại, kèm dòng ghi nhận nguồn FIRMS/LANCE/ESDIS theo hướng dẫn của NASA.
- **Bản chất dữ liệu:** mỗi điểm là một *điểm nóng phát hiện từ vệ tinh* (có thời điểm quét, độ tin cậy, FRP), không phải đám cháy đã xác nhận. Mây che có thể làm sót điểm. Điều này khớp với yêu cầu US10.1: ghi "điểm cháy phát hiện từ vệ tinh" và không khẳng định là nguyên nhân gây bụi.
- **Phủ Hà Nội: chưa kiểm.** Việc cần làm trước khi đóng spike (khoảng 15 phút):
  1. Đăng ký MAP_KEY bằng email cá nhân, lưu trong `.env` (`FIRMS_MAP_KEY`), không commit.
  2. Gọi `https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/VIIRS_SNPP_NRT/105.3,20.5,106.3,21.5/2`. Vùng ghi theo thứ tự tây, nam, đông, bắc, bao Hà Nội và các tỉnh lân cận khoảng 50 km.
  3. Ghi số điểm, khoảng `acq_date`/`acq_time`, và thời gian trễ so với lúc gọi. Có thể không có điểm nào ngoài mùa đốt rơm rạ sau thu hoạch, nên thử thêm `[DATE]` của một ngày cũ trong mùa thu hoạch để chắc API trả đúng vùng.

## 2. Cảnh báo thiên tai chính thức

- **Cơ quan có thẩm quyền:** Quyết định 18/2021/QĐ-TTg quy định về dự báo, cảnh báo, truyền tin thiên tai và cấp độ rủi ro thiên tai. Bản tin khí tượng thủy văn do Trung tâm Dự báo KTTV quốc gia phát hành và đăng trên kttv.gov.vn. Bản tin là file PDF có giờ phát và giờ phát tin tiếp theo, ví dụ tin cảnh báo mưa dông ngày 28/8/2026 ghi giờ phát 15h30 và giờ phát tin tiếp theo 21h00.
- **API:** trong thời gian spike chưa tìm thấy API hay tài liệu điều khoản tái sử dụng công khai cho các bản tin này. Đọc tự động file PDF là cách mong manh (định dạng có thể đổi) và không đạt tiêu chí (2).
- **Ràng buộc pháp lý khi đăng lại:** theo dự thảo nghị định xử phạt được Cổng thông tin Hà Tĩnh đưa tin, truyền phát bản tin dự báo/cảnh báo KTTV không ghi rõ nguồn có thể bị phạt 3–5 triệu đồng, truyền phát không đầy đủ nội dung bản tin cảnh báo thiên tai bị phạt 10–20 triệu đồng. Đây mới là dự thảo, nhưng hướng an toàn cho một dự án sinh viên là **không cắt, không tóm tắt, không diễn giải lại** bản tin. Chỉ hiển thị tiêu đề, giờ phát và liên kết tới bản gốc.
- **VNDMS:** do Trung tâm Chính sách và Kỹ thuật phòng, chống thiên tai vận hành, là hệ thống web cho cơ quan quản lý. Chưa thấy API công khai, nên không đạt.
- **GDACS:** có API và RSS, điều khoản chỉ yêu cầu ghi nguồn "Global Disaster Alert and Coordination System, GDACS". Tuy nhiên GDACS chỉ báo các thảm họa lớn có thể cần hỗ trợ quốc tế, không phải cảnh báo chính thức của Việt Nam cho Hà Nội, nên không dùng cho US10.2.

## 3. Việc nối tiếp

| Task | Đề xuất |
|---|---|
| T10.1-1 (hungpvc) | Làm nếu bước kiểm tra phủ Hà Nội ở mục 1 cho thấy API trả dữ liệu đúng vùng. Connector theo mẫu `connectors/openaq.py`, lưu thô vào `raw_payloads` |
| T10.1-2 (hieund) | Bảng `fire_hotspots` (nguồn, vệ tinh, `acq_time` UTC, lat, lon, confidence, frp, `fetched_at`, `raw_payload_id`), khóa chống trùng `(source, satellite, acq_time, lat, lon)` |
| T10.2-1 (hungpvc) | Đổi phạm vi thành "liên kết tới trang bản tin cảnh báo của Trung tâm Dự báo KTTV quốc gia", hoặc bỏ khỏi MVP. **PO quyết định** |
| docs/data-sources.md | Cập nhật dòng NASA FIRMS (giới hạn 5.000 giao dịch/10 phút, CC0, ghi nhận nguồn) sau khi Hưng xác nhận |

## Nguồn

- NASA FIRMS API, endpoint vùng: https://firms.modaps.eosdis.nasa.gov/api/area/csv ; đăng ký MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key
- NASA Earthdata, FIRMS (ghi nhận và miễn trừ): https://www.earthdata.nasa.gov/learn/find-data/near-real-time/firms
- NASA ESDIS, chính sách sử dụng dữ liệu: https://www.earthdata.nasa.gov/learn/use-data/data-use-policy
- NASA Applied Sciences, hỏi đáp FIRMS 2025 (giới hạn MAP_KEY): https://appliedsciences.nasa.gov/sites/default/files/2025-05/Part%203%20FIRMS%202025%20Q&A%20Session.docx.pdf
- Quyết định 18/2021/QĐ-TTg: https://vupc.mae.gov.vn/Data/files/18_2021_QD-TTg.doc
- Bản tin mẫu của Trung tâm Dự báo KTTV quốc gia: https://kttv.gov.vn//upload/thoitiet/2026/8/28/dbqg_mlcb_20260828_1530.pdf
- Dự thảo xử phạt truyền phát bản tin KTTV: https://hatinh.gov.vn/vi/bai-viet/truyen-phat-sai-lech-ban-tin-du-bao-canh-bao-thien-tai-khi-tuong-thuy-van-bi-phat-den-100-trieu-dong
- VNDMS: https://dmc.gov.vn/news-detail/introducing-the-vietnam-natural-disaster-monitoring-system-vndms-to-the-delegation-of-asean-timor-lester-and-aha-center-cd14516-32.html?lang=en-US
- GDACS API quickstart: https://data.gdacs.org/Documents/2025/GDACS_API_quickstart_v1.pdf
