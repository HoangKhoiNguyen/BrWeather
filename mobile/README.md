# brWeather mobile (React Native + TypeScript, Android)

Thư mục này mới có phần mã của nhóm (`src/`). Khung dự án React Native được tạo bằng công cụ chính thức để có đủ cấu hình Android:

```bash
cd mobile
npx @react-native-community/cli init BrWeather --directory app --skip-git-init
```

Sau đó chuyển `src/` vào `app/src/` (hoặc trỏ `App.tsx` tới `../src`) và chạy:

```bash
cd app
npm run android
```

## Cấu trúc `src/`

| Thư mục | Nội dung |
|---|---|
| `api/` | `types.ts` theo `docs/api-contract.md`; `client.ts` gọi backend, có chế độ dữ liệu giả để làm UI trước khi backend xong |
| `screens/` | Tổng quan (F01), Chi tiết trạm (F02–F04), Thời tiết (F09), Chọn giờ (F06), Cảnh báo (F07a), Cài đặt (F11) |
| `components/` | Thẻ PM2.5, nhãn độ tin cậy, thẻ thời tiết, biểu đồ |

## Quy tắc hiển thị

- Mọi số liệu ghi nguồn, thời điểm và loại (số đo / mô hình / dự báo).
- Giá trị `null` hiển thị "Không có dữ liệu", không bao giờ hiển thị 0.
- Bản đồ: chọn MapLibre + OpenStreetMap nếu không muốn đăng ký khóa Google Maps.
