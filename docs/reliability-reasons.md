# Câu lý do mức tin cậy (T4.1-4)

Dùng cho US4.1. Mã nguồn: `data-pipeline/src/brweather_data/quality/reliability_text.py`. Kiểm thử: `tests/test_reliability_text.py`.
Bản nháp do Claude soạn ngày 23/11/2026, kiennt duyệt.

## Nhãn mức

| Mức (`level`) | Nhãn trên app | Ghi chú |
|---|---|---|
| `high` | Cao | |
| `medium` | Trung bình | |
| `low` | Thấp – cần kiểm tra | US4.1: không dùng màu đỏ hay lời lẽ báo động |

## Câu cho từng lý do

Số trong ngoặc nhọn lấy từ `reliability_scores.details`, viết số kiểu Việt Nam (`48,2`).

| Mã lý do | Câu hiển thị | Ví dụ |
|---|---|---|
| `out_of_range` | Số đo {giá trị} µg/m³ nằm ngoài khoảng hợp lý (0–1000 µg/m³), có thể do lỗi cảm biến. | Số đo 1500 µg/m³ nằm ngoài khoảng hợp lý… |
| `flatline` | Số đo không đổi ({giá trị} µg/m³) trong {số giờ} giờ liên tiếp, cảm biến có thể đang bị kẹt. | Số đo không đổi (30 µg/m³) trong 7 giờ liên tiếp… |
| `stale` | Số đo mới nhất cách đây {số giờ} giờ nên có thể chưa phản ánh hiện tại. | …cách đây 4,5 giờ… |
| `stale` (không có số đo trong 24 giờ) | Không có số đo nào trong 24 giờ qua. | |
| `neighbour_deviation` | Số đo ({giá trị} µg/m³) khác nhiều so với {n} trạm lân cận trong bán kính 10 km (trung vị khu vực {trung vị} µg/m³). | Số đo (150 µg/m³) khác nhiều so với 2 trạm lân cận… |
| không có lý do, có trạm lân cận | Số đo mới, trong khoảng hợp lý và gần với {n} trạm lân cận. | |
| không có lý do, không có lân cận | Số đo mới, trong khoảng hợp lý và có thay đổi theo thời gian. | |

Nhiều lý do cùng lúc: dòng hiển thị dưới nhãn (`details.summary`) là lý do nặng nhất theo thứ tự ngoài khoảng → đứng yên → cũ → lệch lân cận. Toàn bộ danh sách nằm ở `details.messages`.

## Cho backend (T4.1-5)

Job `compute_reliability` đã lưu sẵn câu, API chỉ cần đọc `v_reliability_latest`:

```json
"reliability": {
  "level": "low",
  "label": "Thấp – cần kiểm tra",       // details.level_label
  "reason": "Số đo không đổi (30 µg/m³) trong 7 giờ liên tiếp, cảm biến có thể đang bị kẹt.",  // details.summary
  "reasonCodes": ["flatline"],             // reasons
  "computedAt": "2026-11-23T08:10:00Z"
}
```

Cần thêm các trường này vào `docs/api-contract.md` (việc của nguyenhk).

## Điểm cần chốt

- Ví dụ ban đầu của PO là "không đổi trong 5 giờ", còn ngưỡng trong code là 6 giờ (`FLATLINE_HOURS`). Câu luôn ghi số giờ thật, nên chỉ cần chốt ngưỡng.
- Câu được thử với 5 người ở T4.1-7 (kịch bản: `docs/qa/t4.1-7-thu-nhan-tin-cay.md`). Sửa câu thì sửa `TEMPLATES` và kiểm thử đi kèm.
