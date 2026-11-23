# brWeather

Ứng dụng Android giúp người dân Hà Nội xem chất lượng không khí (PM2.5) và thời tiết ở cùng một nơi, kèm nguồn và độ tin cậy của số liệu, dự báo PM2.5 24 giờ, phát hiện bất thường và gợi ý khung giờ nên ra ngoài.

## Cấu trúc repo

| Thư mục | Nội dung | Phụ trách |
|---|---|---|
| `data-pipeline/` | Python: thu thập OpenAQ + Open-Meteo, làm sạch, điểm tin cậy, dự báo, bất thường | B |
| `backend/` | Java Spring Boot: REST API cho app, xếp hạng khung giờ, cảnh báo, gọi LLM | A |
| `mobile/` | React Native + TypeScript: app Android | C |
| `db/` | Schema PostgreSQL dùng chung cho pipeline và backend | A + B |
| `docs/` | Proposal, nguồn dữ liệu, danh sách chức năng, hợp đồng API | Cả nhóm |
| `scripts/` | Tiện ích chạy tay: kiểm tra cổng dữ liệu tuần 1, migration (`db/`), vận hành máy chủ chung (`env/`) | B, hieund |

## Chạy lần đầu

1. Cài: Docker Desktop, Python 3.11+, JDK 21, Node.js 20+, Android Studio.
2. Tạo file biến môi trường từ mẫu và điền khóa của bạn:
   ```bash
   cp .env.example .env
   ```
   Mỗi thành viên dùng khóa OpenAQ **của riêng mình** (OpenAQ không cho chia sẻ khóa). Không commit file `.env`.
3. Chạy cơ sở dữ liệu và backend (schema được service `migrate` tự áp):
   ```bash
   docker compose up -d db backend
   ```
   Muốn dùng **môi trường chung của nhóm** (db + API chạy 24/7) thay vì db trên máy mình: xem `docs/shared-environment.md`.
4. Chạy thử pipeline một lần (trên máy mình):
   ```bash
   cd data-pipeline
   pip install -e ".[dev]"
   python -m brweather_data.jobs.ingest_hourly
   python -m brweather_data.jobs.compute_reliability      # mức tin cậy mỗi trạm (scheduler chạy sau ingest)
   python -m brweather_data.jobs.detect_anomalies         # bất thường PM2.5 + phân loại (scheduler chạy sau tin cậy)
   python -m brweather_data.jobs.backfill_pm25 --days 14  # lịch sử PM2.5
   python -m brweather_data.jobs.data_report runs         # xem lượt chạy (cũng có: weather, pm25)
   ```
   Chi tiết các job dữ liệu và cách kiểm tra: `docs/data-tasks-sprint1-2.md`, `docs/sprint2-tasks.md`.
5. Chạy app: xem `mobile/README.md`.

## Quy ước làm việc

- `main` luôn chạy được. Làm trên nhánh `feature/<việc>` rồi mở Pull Request.
- Mỗi PR cần một người khác review (A review Python của B, B review Java của A, A/B review luồng chính của C).
- Không commit khóa API, file `.env`, dữ liệu thô hay file mô hình lớn.
- Mọi thời gian lưu theo UTC, hiển thị theo giờ Việt Nam.

## Nguồn dữ liệu

OpenAQ (số đo trạm), Open-Meteo Weather và Air Quality (thời tiết, dữ liệu mô hình). Chi tiết và điều khoản: `docs/data-sources.md`. App phải ghi nguồn cho mọi số liệu hiển thị.
