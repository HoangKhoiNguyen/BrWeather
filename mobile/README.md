# brWeather mobile (React Native + TypeScript, Android)

Mã nguồn app nằm trong `app/`. Hiện app chạy bằng **dữ liệu mẫu** (`USE_MOCK = true` trong `app/src/api/client.ts`).

## Cần cài

Node.js 22 trở lên, JDK 21, Android Studio (có Android SDK và một máy ảo).

## Chạy lần đầu

```bash
cd mobile/app
npm install
```

Mở máy ảo trong Android Studio (**Device Manager → ▶**), rồi chọn một trong hai cách.

**Cách 1: bằng dòng lệnh**

```bash
npm run android
```

Lệnh này tự mở Metro (bộ phục vụ mã JavaScript), build và cài app.

**Cách 2: bằng Android Studio**

1. Trong terminal, chạy Metro và để cửa sổ đó mở:
   ```bash
   npm start
   ```
2. Trong Android Studio: **Open** → chọn thư mục `mobile/app/android`, đợi Gradle Sync xong.
3. Vào **Settings → Build, Execution, Deployment → Build Tools → Gradle → Gradle JDK**, chọn **JDK 21**.
4. Chọn máy ảo trên thanh công cụ, bấm **Run ▶**.

**Trên Windows chỉ cần bấm Run.** Bản debug tự gọi `scripts/start-metro.cmd` (task `startMetro` trong `android/app/build.gradle`): nếu Metro chưa chạy, nó mở Metro trong cửa sổ riêng "Metro - brWeather". Giữ cửa sổ đó mở trong lúc làm việc. Trên macOS/Linux vẫn chạy `npm start` như bước 1.

Nếu mở app trên máy ảo mà thấy màn hình đỏ "Unable to load script", Metro đã bị tắt: bấm **Run** lại, hoặc chạy `scripts\start-metro.cmd`, rồi bấm **R** hai lần trên máy ảo.

Sửa code trong `src/` rồi lưu, màn hình tự cập nhật (Fast Refresh). Chỉ cần build lại khi đổi phần native trong `android/` hoặc thêm thư viện native.

## Cấu trúc `app/src/`

| Thư mục | Nội dung |
|---|---|
| `api/` | `types.ts` theo `docs/api-contract.md`; `mock.ts` dữ liệu mẫu; `client.ts` chọn giữa dữ liệu mẫu và backend |
| `screens/` | Không khí (F01), Chi tiết trạm (F02–F04), Thời tiết (F09), Chọn giờ (F05, F06), Cảnh báo (F07a) |
| `components/` | Thẻ, nhãn độ tin cậy, nút chọn, biểu đồ cột, định dạng giờ Việt Nam |

Chưa làm: bản đồ (F01), chọn địa điểm bằng GPS (F11), kết nối backend thật.

## Quy tắc hiển thị

- Mọi số liệu ghi nguồn, thời điểm và loại (số đo / mô hình / dự báo).
- Giá trị `null` hiển thị "Không có dữ liệu", không bao giờ hiển thị 0.
- Dữ liệu lưu UTC, hiển thị giờ Việt Nam.
- Bản đồ: chọn MapLibre + OpenStreetMap nếu không muốn đăng ký khóa Google Maps.
