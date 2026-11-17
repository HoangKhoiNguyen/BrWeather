# Môi trường chung của nhóm (C-03)

Một máy luôn bật chạy `db` + `migrate` + `backend` + `pipeline` + `backup` bằng Docker Compose. Cả nhóm kết nối vào cùng một cơ sở dữ liệu và một API, nên dữ liệu PM2.5/thời tiết được thu liên tục, không phụ thuộc máy ai đang bật.

Điều kiện xong của C-03:

1. **Cả nhóm kết nối được**: mỗi thành viên gọi được API và mở được cơ sở dữ liệu từ máy mình.
2. **Dữ liệu không mất khi khởi động lại**: kiểm bằng `scripts/env/check-persistence.sh`.

## Kiến trúc

```
 Máy thành viên (laptop, emulator, điện thoại)
        │  mạng riêng Tailscale (100.x.y.z), mã hóa
        ▼
 Máy chủ chung ── docker compose ─────────────────────────────┐
   db (Postgres 16) ◄── migrate (chạy 1 lần mỗi khi khởi động) │
     ▲   ▲    ▲                                                │
     │   │    └── backup: pg_dump mỗi ngày → ./backups          │
     │   └─────── pipeline: ingest OpenAQ + Open-Meteo mỗi giờ  │
     └─────────── backend: API :8080                           │
   volume brweather_shared_pgdata (dữ liệu nằm ở đây)          │
└──────────────────────────────────────────────────────────────┘
```

| Thành phần | Vai trò | Khi sập |
|---|---|---|
| `db` | Postgres 16, dữ liệu trong volume ngoài `brweather_shared_pgdata` | Tự khởi động lại (`restart: unless-stopped`) |
| `migrate` | Áp `db/schema.sql` + `db/migrations/*.sql`, rồi thoát | Lỗi thì backend/pipeline không chạy, xem `docker compose logs migrate` |
| `backend` | API Spring Boot, healthcheck gọi `/api/v1/health` | Tự khởi động lại |
| `pipeline` | `scheduler`: ingest ngay khi bật, sau đó phút 10 mỗi giờ | Tự khởi động lại; lỗi từng lần ghi vào bảng `ingest_runs` |
| `backup` | Sao lưu mỗi ngày lúc 2 giờ sáng (giờ VN), giữ 7 ngày | Tự khởi động lại |

Log mỗi container giới hạn 3 × 10 MB, nên chạy lâu không làm đầy ổ đĩa.

---

## Phần nhóm cần tự làm

Hai việc dưới đây cần quyết định của nhóm hoặc tài khoản cá nhân, nên không làm sẵn trong repo được.

### Việc 1 – Chọn máy chủ

| Phương án | Chi phí | Ưu | Nhược | Hợp khi |
|---|---|---|---|---|
| **A. Máy một thành viên + Tailscale** (khuyên dùng cho Sprint 1–3) | 0 đ | Dựng trong 1 giờ, không lộ cổng ra Internet | Máy đó phải luôn bật, không ngủ; tốn điện | Có một máy bàn/laptop cắm điện cả ngày |
| **B. VPS miễn phí Oracle Cloud (Always Free) + Tailscale** | 0 đ (cần thẻ để đăng ký) | Chạy 24/7 thật, gần giống môi trường UAT ở C-07 | Đăng ký hay bị từ chối hoặc hết tài nguyên ở một số vùng; máy ARM | Muốn dùng luôn cho C-07 (HTTPS cho UAT) |
| **C. VPS trả phí nhỏ** (khoảng 2 vCPU / 2–4 GB RAM) | Vài USD/tháng, tùy nhà cung cấp | Ổn định, ít rắc rối | Tốn tiền | Phương án B không đăng ký được |

Lưu ý:

- **Tailscale**: gói Personal miễn phí cho mục đích phi thương mại, tối đa 6 người dùng, đủ cho nhóm 4 người. Mỗi thành viên cài Tailscale và đăng nhập vào cùng một mạng (tailnet). Máy chủ có một IP dạng `100.x.y.z` mà chỉ thành viên trong tailnet thấy.
- **Oracle Always Free** từ giữa năm 2026 chỉ còn 2 OCPU + 12 GB RAM cho máy Ampere A1 (trước đây là 4 + 24), vẫn đủ cho brWeather. Không tạo máy vượt mức này, vì khi hết thời gian dùng thử, máy vượt mức sẽ bị tắt. Các image `postgres:16`, `maven`, `eclipse-temurin`, `python:3.11-slim` đều có bản ARM.
- Máy chủ cần tối thiểu khoảng 2 GB RAM trống (lúc build backend Maven cần nhiều nhất) và 10 GB ổ đĩa.
- Phương án A trên Windows: dùng Docker Desktop (WSL2), bật *Start Docker Desktop when you sign in*, tắt chế độ ngủ trong *Power settings*. Chạy các script `scripts/env/*.sh` bằng Git Bash hoặc trong WSL.

### Việc 2 – Khóa OpenAQ cho pipeline chung

OpenAQ yêu cầu không chia sẻ khóa API, vì mỗi khóa có hạn mức riêng. Pipeline chung vẫn chỉ cần **một** khóa. Đề xuất:

1. Chọn **một người** (gợi ý: người phụ trách máy chủ, hieund) dùng khóa **của chính mình** cho pipeline chung. Khóa chỉ nằm trong `.env` trên máy chủ, không gửi qua chat, không commit.
2. Khi máy chủ chung đã chạy, các thành viên khác **tắt pipeline trên máy mình** (chạy `docker compose up -d db backend`, không chạy `pipeline`), đọc dữ liệu từ db chung, để không tốn hạn mức và không có hai nguồn dữ liệu lệch nhau.
3. Ghi quyết định này vào biên bản Sprint Planning hoặc `docs/data-sources.md`.

---

## Dựng máy chủ (người phụ trách làm một lần)

```bash
# 1. Cài Docker (Linux: https://docs.docker.com/engine/install/) và Tailscale (https://tailscale.com/download)
sudo tailscale up            # đăng nhập vào tailnet của nhóm
tailscale ip -4              # ghi lại IP 100.x.y.z

# 2. Lấy code
git clone https://github.com/HoangKhoiNguyen/BrWeather.git && cd BrWeather

# 3. Cấu hình
cp .env.example .env
#   - OPENAQ_API_KEY      = khóa của người phụ trách (Việc 2)
#   - POSTGRES_PASSWORD   = mật khẩu mạnh: openssl rand -base64 24
#   - DB_BIND_ADDR        = IP Tailscale ở bước 1 (để thành viên mở được db)
#   - API_BIND_ADDR       = IP Tailscale (VPS) hoặc giữ 0.0.0.0 (máy trong mạng nhà)

# 4. Khởi động
scripts/env/up.sh

# 5. Kiểm tra
scripts/env/status.sh
scripts/env/check-persistence.sh     # tiêu chí "không mất dữ liệu khi khởi động lại"
```

`up.sh` từ chối chạy khi mật khẩu còn là `change-me`, và tự tạo volume `brweather_shared_pgdata` ở lần đầu.

Docker tự khởi động khi máy bật lại (Linux: `sudo systemctl enable docker`; Windows: tùy chọn của Docker Desktop ở trên), và các container có `restart: unless-stopped` sẽ tự chạy theo.

**Cập nhật khi `main` có code mới:**

```bash
git pull && scripts/env/up.sh        # build lại image, chạy migration mới, giữ nguyên dữ liệu
```

## Thành viên kết nối vào

Cài Tailscale, đăng nhập cùng tailnet, rồi dùng IP máy chủ `100.x.y.z`:

| Muốn | Cách |
|---|---|
| Gọi API | `curl http://100.x.y.z:8080/api/v1/health` → `{"status":"ok"}` |
| Mở cơ sở dữ liệu | DBeaver / pgAdmin / `psql`: host `100.x.y.z`, cổng `5432`, db `brweather`, user `brweather`, mật khẩu do người phụ trách gửi riêng |
| Chạy notebook / script phân tích | Trong `.env` của máy mình đặt `POSTGRES_HOST=100.x.y.z` và mật khẩu chung |
| App trên emulator | Máy chạy emulator đã vào tailnet, nên emulator gọi được `http://100.x.y.z:8080/api/v1`. Hiện `BASE_URL` trong `mobile/app/src/api/client.ts` đang cố định `10.0.2.2` (máy cá nhân); đổi tạm khi cần thử với server chung |
| App trên điện thoại thật | Cài app Tailscale trên điện thoại, dùng cùng URL như trên |

Mật khẩu cơ sở dữ liệu là của **cả nhóm**, chỉ nên dùng để đọc và thử nghiệm. Không chạy `DROP`/`TRUNCATE` trên db chung; cần thử thì chạy db riêng trên máy mình.

## Vận hành hằng ngày

| Việc | Lệnh |
|---|---|
| Xem tình trạng | `scripts/env/status.sh` |
| Xem log | `docker compose logs -f --tail=100 pipeline` (hoặc `backend`, `migrate`, `backup`) |
| Sao lưu ngay | `scripts/env/backup.sh` |
| Phục hồi | `scripts/env/restore.sh backups/<file>.dump` (hỏi xác nhận trước khi ghi đè) |
| Dừng tạm | `docker compose -f docker-compose.yml -f compose.shared.yml stop` |
| Đổi schema | Xem `db/migrations/README.md` |

**Đừng** chạy `docker volume rm brweather_shared_pgdata`: đó là toàn bộ dữ liệu. `docker compose down -v` không xóa được volume này vì nó được khai báo `external`.

Bản sao lưu nằm trên **cùng máy** với db, nên chỉ chống được lỗi thao tác, không chống được hỏng máy. Thỉnh thoảng nên chép file `.dump` mới nhất sang chỗ khác (Google Drive của nhóm). Việc thử phục hồi đầy đủ là task C-15.

## Máy cá nhân (không đổi nhiều)

Vẫn chạy như trước, chỉ có `docker-compose.yml`:

```bash
cp .env.example .env    # giữ DB_BIND_ADDR=127.0.0.1
docker compose up -d db backend      # thêm pipeline nếu muốn tự thu dữ liệu
```

Khác biệt so với trước C-03: schema được áp bởi service `migrate` (không còn qua `docker-entrypoint-initdb.d`), nên db cũ trên máy cá nhân cũng nhận được bảng mới khi khởi động lại.

## Việc nối tiếp đề xuất

- **C-07 (HTTPS cho UAT)**: dùng lại máy chủ này. Thêm reverse proxy (Caddy) phía trước `backend`, hoặc `tailscale funnel` nếu chỉ cần mở tạm cho người thử.
- **Mobile**: đọc `BASE_URL` từ cấu hình build thay vì cố định trong code, để chuyển giữa máy cá nhân và server chung không phải sửa code.
- **C-15**: dùng `scripts/env/restore.sh` để thử phục hồi trên môi trường thử, ghi thời gian phục hồi.
