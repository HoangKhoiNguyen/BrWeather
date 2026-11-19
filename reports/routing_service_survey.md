# Khảo sát dịch vụ tính tuyến cho brWeather

**Ngày truy cập:** 16/11/2026  
**Sprint:** 1 — 13/11/2026 đến 19/11/2026  
**Phạm vi:** prototype học tập phi thương mại tại Hà Nội; ưu tiên tuyến đi bộ, xe đạp và lái xe  
**Giới hạn thực hiện:** 4 giờ

## Tóm tắt

| Dịch vụ | Miễn phí | Chi phí vượt mức | Hạn mức tốc độ | Phủ Hà Nội | Điều khoản chính cần lưu ý |
|---|---:|---:|---:|---|---|
| **Mapbox Directions API** | 100.000 request/tháng | 100.001–500.000: **2 USD/1.000 request**; 500.001–1 triệu: 1,60 USD/1.000 | 300 request/phút | Có khả năng tốt cho driving, walking, cycling dựa trên mạng đường Mapbox/OSM; traffic tự fallback về driving khi khu vực không có traffic | Cần access token; phải ghi nguồn Mapbox ngay cạnh nội dung tuyến nếu không dùng bản đồ Mapbox; phải công bố cảnh báo an toàn khi cung cấp chỉ đường |
| **openrouteservice Standard** | 2.000 Directions/ngày, 40/phút; khoảng 60.000/tháng nếu dùng đều | 0 EUR cho Standard; Collaborative cũng 0 EUR nếu đủ điều kiện. Không có giá pay-as-you-go công khai; nhu cầu cao hơn phải xin Collaborative, liên hệ hoặc self-host | 40 request/phút | Dùng dữ liệu OpenStreetMap toàn cầu và có profile driving, walking, cycling; Hà Nội phụ thuộc chất lượng OSM tại từng phố/ngõ | Cần API key và ghi nguồn openrouteservice/HeiGIT + OpenStreetMap. Tài liệu công khai đang có khác biệt giữa CC BY 4.0 và thông tin hỗ trợ 2026 nói CC BY-SA 4.0; phải xác nhận ToS trong tài khoản trước khi phát hành |
| **Google Routes API Essentials** | 10.000 request/tháng | 10.001–100.000: **5 USD/1.000 request**; các bậc cao giảm dần | 3.000 query/phút | Bảng coverage chính thức xác nhận Việt Nam có driving, traffic và walking chất lượng tốt; cycling không có/không đủ | Bắt buộc bật billing và dùng API key/OAuth; không được kết hợp Google Routes content với bản đồ không phải Google; cache tọa độ tối đa 30 ngày theo điều khoản dịch vụ |

## Chi tiết

### 1. Mapbox Directions API

- Hỗ trợ `driving`, `driving-traffic`, `walking`, `cycling`; tối đa 25 tọa độ/request.
- Free tier 100.000 request/tháng. Sau đó tính theo request: 2 USD/1.000 ở bậc 100.001–500.000.
- Rate limit mặc định 300 request/phút.
- Nếu `driving-traffic` không có traffic coverage tại khu vực, API trả kết quả theo profile `driving` thay vì lỗi.
- Nền dữ liệu đường dựa đáng kể trên OpenStreetMap và các nguồn bổ sung. Không có cam kết riêng theo thành phố cho Hà Nội trong trang Directions; cần kiểm thử tuyến thực tế.
- Attribution phải hiển thị rõ ngay cạnh kết quả Directions nếu không hiển thị trên bản đồ Mapbox.
- Điều khoản yêu cầu cảnh báo người dùng tuân thủ biển báo, luật giao thông và điều kiện thực tế.

**Ước tính:** 10.000 hoặc 100.000 request/tháng đều 0 USD; 150.000 request/tháng khoảng 100 USD.

### 2. openrouteservice

- Standard plan miễn phí: 2.000 Directions/ngày và 40/phút; tối đa 50 waypoint và 3 tuyến thay thế.
- Collaborative plan miễn phí cho một số dự án học thuật, phi lợi nhuận hoặc chính phủ: 10.000 Directions/ngày, 60/phút, nhưng phải đăng ký/xét duyệt.
- Dùng mạng OpenStreetMap, hỗ trợ driving, foot, cycling và wheelchair. Với Hà Nội, độ phủ phụ thuộc dữ liệu OSM; không có cam kết city-level hoặc traffic thời gian thực.
- Endpoint mới phải là `https://api.heigit.org/openrouteservice/v2/...`. Host `api.openrouteservice.org` đã bị ngừng trong tháng 11/2026.
- API result cần attribution cho openrouteservice và OpenStreetMap.
- Có bất nhất trong tài liệu công khai về giấy phép result: trang Terms được index là CC BY 4.0, trong khi trả lời chính thức tháng 10/2026 nói CC BY-SA 4.0. Cần chụp/xác nhận ToS hiển thị trong HeiGIT Account trước khi đưa vào app.

**Ước tính:** 0 EUR ở Standard; 150.000 request/tháng vượt Standard và chưa có đơn giá hosted công khai.

### 3. Google Routes API

- Essentials gồm Compute Routes và Compute Route Matrix; free cap 10.000 request/tháng.
- Giá bậc đầu sau free cap là 5 USD/1.000 request; billing account phải được bật ngay cả khi dùng trong free cap.
- Rate limit Compute Routes là 3.000 query/phút.
- Coverage chính thức cho Việt Nam đánh dấu tốt đối với driving/Snap to Roads, traffic và walking; cycling không được hỗ trợ tốt.
- Điều khoản cho phép Routes API hoạt động không có Google Map, nhưng không được ghép content của Routes với bản đồ không phải Google.
- Chỉ được cache latitude/longitude từ Routes tối đa 30 ngày; phải bảo vệ API key và đặt quota cứng để tránh phát sinh phí.

**Ước tính:** 10.000 request/tháng là 0 USD; 100.000 request/tháng khoảng 450 USD; 150.000 request/tháng khoảng 650 USD theo các bậc giá hiện tại.

## Đề xuất

**Chọn Mapbox Directions API cho prototype Sprint 1.**

Lý do:

1. Free tier 100.000 request/tháng lớn nhất trong ba lựa chọn và không cần tự vận hành routing server.
2. Có đủ walking, cycling và driving cho bài toán gợi ý hoạt động ngoài trời; Google không hỗ trợ tốt cycling tại Việt Nam theo bảng coverage hiện tại.
3. Có traffic-aware driving nhưng tự fallback khi traffic chưa phủ, phù hợp prototype hơn việc phụ thuộc cứng vào traffic.
4. Giá vượt mức rõ ràng, dễ đặt quota ứng dụng; rẻ hơn Google ở bậc đầu.
5. Tích hợp mobile và hiển thị polyline thuận tiện hơn openrouteservice, trong khi openrouteservice vừa đổi host và còn điểm chưa rõ về giấy phép result.

### Điều kiện trước khi tích hợp

- Tạo token riêng cho prototype và giới hạn scope/domain hoặc ứng dụng.
- Kiểm thử thủ công ít nhất 5–10 cặp tuyến Hà Nội: trung tâm, ngõ nhỏ, cầu qua sông, tuyến đi bộ và tuyến xe đạp.
- Kiểm tra route snapping, đường cấm, thời gian ước tính và hành vi `driving-traffic` fallback.
- Ghi attribution “Directions powered by Mapbox” gần kết quả tuyến và thêm cảnh báo tuân thủ điều kiện giao thông thực tế.
- Đặt quota nội bộ thấp hơn free tier; không tự động chuyển sang chi phí trả phí nếu chưa được nhóm duyệt.
- Chỉ lưu dữ liệu tuyến trong phạm vi điều khoản Mapbox hiện hành; rà lại ToS trước khi publish.

## Nguồn chính thức

- Mapbox Directions API: https://docs.mapbox.com/api/navigation/directions/
- Mapbox pricing: https://www.mapbox.com/pricing
- Mapbox attribution: https://docs.mapbox.com/help/dive-deeper/attribution/
- Mapbox Terms: https://www.mapbox.com/legal/tos
- openrouteservice plans: https://openrouteservice.org/plans/
- openrouteservice restrictions: https://openrouteservice.org/restrictions/
- openrouteservice Terms: https://openrouteservice.org/terms-of-service/
- HeiGIT endpoint migration: https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912/
- Google Routes pricing: https://developers.google.com/maps/billing-and-pricing/pricing
- Google Routes usage/billing: https://developers.google.com/maps/documentation/routes/usage-and-billing
- Google Maps coverage: https://developers.google.com/maps/coverage
- Google Maps service-specific terms: https://cloud.google.com/maps-platform/terms/maps-service-terms

## Giới hạn khảo sát

Chưa gọi API thực vì project chưa có token Mapbox/openrouteservice hoặc billing Google. Đánh giá phủ Hà Nội của Mapbox và openrouteservice dựa trên phạm vi/profile chính thức cùng nguồn dữ liệu OSM; cần smoke test thực địa trước khi coi là đạt.
