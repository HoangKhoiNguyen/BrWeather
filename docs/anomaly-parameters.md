# Phát hiện bất thường PM2.5: tham số và lý do chọn (T5.1-2)

Dùng cho US5.1 và US5.2. Claude soạn ngày 23/11/2026 cho kiennt. **Bản chọn ban đầu: cần chạy lại bước kiểm tra ở mục 3 trên dữ liệu thật sau khi backfill xong (T2.3-1), rồi chốt.**

Mã nguồn: `ml/anomaly.py` (phát hiện), `quality/anomaly_classifier.py` (phân loại), `jobs/detect_anomalies.py` (job mỗi giờ).

## 1. Phương pháp

Mỗi giờ `t` so với **72 giờ trước nó** (không dùng dữ liệu sau `t`):

```
trung vị m, độ lệch tuyệt đối trung vị MAD của 72 giờ trước
z(t) = (giá trị(t) − m) / (1,4826 × MAD)
```

Một giờ bị gắn cờ khi **cả hai** điều kiện đúng: |z| > 4,3 **và** |giá trị − m| ≥ 15 µg/m³. Các giờ liên tiếp cùng hướng (cho phép hở 1 giờ) gộp thành một sự kiện. Sự kiện được lưu kèm đỉnh, trung vị nền và điểm z.

## 2. Tham số đã chọn

| Tham số | Giá trị | Lý do |
|---|---|---|
| Cửa sổ nền | 72 giờ | Đủ dài để bỏ qua chu kỳ ngày đêm (3 chu kỳ), đủ ngắn để theo kịp thay đổi theo mùa. Đã dùng trong đánh giá Dragon (`reports/pm25_anomaly_detection_evaluation.md`) |
| Số giờ tối thiểu có dữ liệu | 36/72 | Trạm thiếu quá nửa cửa sổ thì trung vị không đáng tin, nên không kết luận |
| Ngưỡng \|z\| | 4,3 | Phân vị 0,99 của \|z\| trên tập train Dragon (đến 01/09/2026) là 4,28, tức khoảng 1% số giờ bình thường vượt ngưỡng. Làm tròn lên 4,3 |
| Lệch tối thiểu | 15 µg/m³ | Không khí sạch có MAD rất nhỏ, chỉ cần 5 → 12 µg/m³ cũng ra z lớn. Mức 15 µg/m³ trùng với ngưỡng lệch tuyệt đối khi so trạm lân cận (T4.1-2) |
| Gộp sự kiện | hở tối đa 1 giờ | Một đợt bụi bị đứt 1 giờ dữ liệu vẫn tính là một sự kiện |

Ngưỡng chỉ được chọn trên tập train (không nhìn tập kiểm tra), đúng nguyên tắc của báo cáo đánh giá trước đó.

**Giới hạn:** ngưỡng 4,28 được tính trên **một cảm biến cộng đồng** (Dragon, 180 ngày). Hai trạm 4946812 và 4946813 có thể có độ nhiễu khác, nên cần kiểm tra ở mục 3.

## 3. Kiểm tra trên dữ liệu thật (chạy trên VPS sau T2.3-1)

```bash
docker compose exec pipeline python -m brweather_data.jobs.anomaly_review tune --days 30
```

Lệnh in bảng số sự kiện mỗi trạm mỗi tuần, ứng với từng cặp (ngưỡng |z| ∈ {3,5; 4; 4,3; 5}, lệch tối thiểu ∈ {0; 10; 15; 20}). Tiêu chí chốt:

- **Khoảng 1–4 sự kiện mỗi trạm mỗi tuần** ở cặp (4,3; 15). Nhiều hơn thì người dùng bị "báo động giả" liên tục và bỏ qua nhãn; ít hơn thì gần như không có gì để xem.
- Nếu vượt khoảng này, chọn cặp gần nhất nằm trong khoảng và ghi lại lý do ở mục 5.
- Sau đó xem độ chính xác thực tế qua 20 ca rà soát (T5.1-5, T5.1-6). Báo cáo phải nêu tỷ lệ người rà soát đồng ý là bất thường. Không nêu precision/recall đầy đủ vì không có nhãn chuẩn.

## 4. Phân loại (US5.2, T5.2-1)

Áp dụng theo thứ tự, gặp quy tắc khớp đầu tiên thì dừng:

| # | Điều kiện | Kết quả | Mã lý do |
|---|---|---|---|
| 1 | Trong sự kiện (±1 giờ) có giá trị bị cờ `out_of_range`, hoặc có ≥ 6 giờ liên tiếp cùng một giá trị | Có thể do lỗi đo | `flagged_values` / `flatline` |
| 2 | Không có trạm nào trong 10 km có dữ liệu trong lúc xảy ra sự kiện | Cần kiểm tra | `no_neighbour` |
| 3 | Ít nhất một trạm lân cận đổi cùng hướng: lệch ≥ 7,5 µg/m³ và ≥ 50% mức lệch tương đối của trạm | Biến động thật | `neighbour_confirms` |
| 4 | Lân cận đứng yên, và sự kiện là nhảy vọt 1 giờ rồi về ngay, hoặc bắt đầu ngay sau ≥ 3 giờ mất tín hiệu | Có thể do lỗi đo | `isolated_spike` / `after_signal_gap` |
| 5 | Lân cận đứng yên, thay đổi kéo dài nhiều giờ | Cần kiểm tra | `neighbours_disagree` |

Quy tắc 5 không gắn "lỗi đo" vì có thể là nguồn bụi rất gần trạm. App không tự gán nguyên nhân phát thải (US5.2).

Kiểm thử bằng 10 ca giả lập có nhãn (T5.2-2): `quality/synthetic_cases.py` và `tests/fixtures/anomaly_synthetic_cases.json`. Bộ ca gồm đứng yên, nhảy vọt, mất tín hiệu, tăng/giảm thật, không có lân cận, tăng cục bộ, ngoài khoảng và bình thường.

Lưu ý hiện tại: theo SP-01 chỉ 3 trạm đạt cổng dữ liệu. Trong số đó, Dragon (6123215, tọa độ 20,9933; 105,9441) nằm ở phía đông, có thể cách hai trạm còn lại khoảng 10 km trở lên. Nếu đúng vậy thì các sự kiện ở Dragon sẽ thường là "cần kiểm tra". Hãy xem `details.neighbour_count` của các sự kiện thật để kiểm chứng. Nếu nhóm muốn, có thể tăng bán kính cho riêng phần phân loại. Nên chốt sau khi xem 20 ca thật.

## 5. Nhật ký quyết định

| Ngày | Quyết định | Người |
|---|---|---|
| 23/11/2026 | Bản ban đầu: 72 giờ / 36 giờ / \|z\| > 4,3 / ≥ 15 µg/m³ | Claude soạn, chờ kiennt duyệt |
| | (Sau khi chạy `tune` trên dữ liệu thật) | |
