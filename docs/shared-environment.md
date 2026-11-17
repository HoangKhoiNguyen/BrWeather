# Môi trường chung của nhóm (C-03)

Một VPS trên cloud chạy `db` + `migrate` + `backend` + `pipeline` + `backup` bằng Docker Compose. Cả nhóm kết nối vào cùng một cơ sở dữ liệu và một API, nên dữ liệu PM2.5/thời tiết được thu liên tục, không phụ thuộc máy ai đang bật.

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

### Việc 1 – Máy chủ: Oracle Cloud Always Free (đã chọn 17/11/2026)

Nhóm dùng **một máy ảo miễn phí của Oracle Cloud (Always Free)**, truy cập qua **Tailscale**. Nếu không đăng ký được Oracle thì dự phòng bằng VPS trả phí nhỏ (vài USD/tháng, 2 vCPU / 2–4 GB RAM, gần Việt Nam như Singapore).

**Cấu hình máy:**

| Mục | Chọn | Lý do |
|---|---|---|
| Shape | `VM.Standard.A1.Flex` (Ampere, ARM) | Loại duy nhất đủ RAM trong Always Free. Các image `postgres:16`, `maven`, `eclipse-temurin`, `python:3.11-slim` đều có bản ARM. |
| OCPU / RAM | **2 OCPU / 6 GB** | Hạn mức Always Free A1 từ giữa 2026 là tổng 2 OCPU + 12 GB; **không vượt**, vì khi hết dùng thử máy vượt mức bị tắt. Chọn 6 GB thay vì 12 GB để tránh bị thu hồi (xem dưới). |
| Hệ điều hành | Ubuntu 24.04 (bản aarch64) | Khớp với lệnh cài đặt bên dưới |
| Ổ đĩa | Boot volume 50 GB | Nằm trong 200 GB miễn phí |
| Home region | **Singapore** (gần Việt Nam nhất) | Máy Always Free chỉ tạo được ở home region, và **home region chọn lúc đăng ký thì không đổi được**. |

**Rủi ro bị thu hồi khi "nhàn rỗi":** Oracle có thể dừng máy Always Free nếu trong 7 ngày liên tục **cả ba** chỉ số đều dưới 20%: CPU (phân vị 95), mạng, và RAM (riêng máy A1). brWeather chỉ thu dữ liệu mỗi giờ nên CPU và mạng chắc chắn thấp. Vì vậy cách giữ máy là để **RAM luôn trên 20%**: Postgres + backend Java + pipeline dùng khoảng 1,5–2,5 GB, tức khoảng 25–40% của 6 GB, trong khi chỉ khoảng 12–20% của 12 GB. Đó là lý do chọn 6 GB.

- `scripts/env/status.sh` có in tỷ lệ RAM đang dùng. Nếu thấy dưới 25% thì giảm RAM máy (Edit shape) xuống 4 GB.
- Oracle gửi email báo trước khi dừng máy. Ai giữ tài khoản cần để ý email; máy bị dừng vẫn khởi động lại được, dữ liệu trên ổ đĩa không mất.
- Cách triệt để: nâng tài khoản lên **Pay As You Go**. Tài nguyên Always Free vẫn miễn phí và không bị thu hồi vì nhàn rỗi, nhưng tạo nhầm tài nguyên ngoài hạn mức sẽ bị tính tiền. Chỉ làm khi người giữ tài khoản chắc chắn kiểm soát được.
- **Không** dùng script "đốt CPU" giả tải để lách quy định.

**Các bước trên Oracle Console** (người giữ tài khoản làm):

1. Đăng ký tại `signup.cloud.oracle.com`: chọn home region **Singapore**, xác minh bằng thẻ (Oracle chỉ giữ tạm một khoản nhỏ để kiểm tra, không trừ tiền với tài nguyên Always Free).
2. *Compute → Instances → Create instance*: Image **Canonical Ubuntu 24.04**, Shape **Ampere → VM.Standard.A1.Flex**, 2 OCPU / 6 GB. Kiểm tra có nhãn **Always Free-eligible**.
3. *Networking*: để Oracle tạo VCN và subnet mới, **gán public IPv4** (cần cho lần SSH đầu và để máy tải image).
4. *Add SSH keys*: dán public key của bạn (`~/.ssh/id_ed25519.pub`, chưa có thì tạo bằng `ssh-keygen -t ed25519`).
5. *Boot volume*: 50 GB. Bấm **Create**.
6. Nếu báo **Out of capacity**: thử availability domain khác (nếu vùng có nhiều AD), hoặc thử lại sau vài giờ, thường vào sáng sớm hoặc khuya.
7. Khi máy chạy: `ssh ubuntu@<public IP>`, rồi làm tiếp phần **Dựng máy chủ** bên dưới.
8. Sau khi Tailscale chạy ổn: vào *VCN → Security List* xóa luật mở cổng 22 từ `0.0.0.0/0`, từ đó SSH qua IP Tailscale (`ssh ubuntu@100.x.y.z`).

**Tailscale** (gói Personal miễn phí, phi thương mại, tối đa 6 người dùng): mỗi thành viên cài và đăng nhập cùng một tailnet. VPS có IP `100.x.y.z` chỉ thành viên thấy. Nhờ vậy **không cần mở cổng 5432 hay 8080 ra Internet**.

**Lưu ý bảo mật riêng cho VPS có IP công khai:**

- Cổng do Docker mở (`ports:`) **đi vòng qua tường lửa `ufw`**: chặn bằng `ufw` không có tác dụng. Vì vậy trong `.env` của VPS đặt **cả** `DB_BIND_ADDR` **và** `API_BIND_ADDR` bằng IP Tailscale, không dùng `0.0.0.0`.
- Tường lửa của nhà cung cấp (Oracle: *Security List* của subnet) chỉ mở cổng 22 (SSH). Khi Tailscale chạy ổn, có thể đóng cả cổng 22 và SSH qua Tailscale.
- Đăng nhập SSH bằng khóa, tắt đăng nhập bằng mật khẩu.
- Mở API ra Internet cho người thử UAT là việc của C-07 (HTTPS), không làm ở C-03.

### Việc 2 – Khóa OpenAQ (đã chọn 17/11/2026)

Pipeline chung dùng **một khóa OpenAQ nhóm đang có**. Cách giữ khóa:

1. Khóa **chỉ** nằm trong file `.env` trên VPS (`OPENAQ_API_KEY=...`). Repo là public, nên tuyệt đối **không commit** khóa vào bất kỳ file nào. `.env` đã có trong `.gitignore`.
2. Người giữ VPS dán khóa trực tiếp khi SSH vào máy, không gửi qua nhóm chat. Lỡ để lộ thì vào `explore.openaq.org/account` tạo khóa mới (rotate) và cập nhật `.env`, rồi chạy `scripts/env/up.sh`.
3. OpenAQ yêu cầu không chia sẻ khóa vì mỗi khóa có hạn mức riêng. Vì vậy khi VPS đã chạy, các thành viên **không chạy pipeline bằng khóa này trên máy mình**: chạy `docker compose up -d db backend` hoặc đọc thẳng db chung. Ai cần gọi OpenAQ để thử (ví dụ `scripts/check_data_gate.ps1`) thì dùng khóa riêng của mình.

---

## Dựng máy chủ (người phụ trách làm một lần)

```bash
# 0. Thêm 2 GB swap: phòng thiếu bộ nhớ lúc build backend (bắt buộc với VPS 2 GB RAM)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 1. Cài Docker và Tailscale
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
sudo systemctl enable docker          # Docker tự chạy khi VPS khởi động lại
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up                     # mở link hiện ra để đăng nhập tailnet của nhóm
tailscale ip -4                       # ghi lại IP 100.x.y.z

# 2. Lấy code
git clone https://github.com/HoangKhoiNguyen/BrWeather.git && cd BrWeather

# 3. Cấu hình
cp .env.example .env && nano .env
#   OPENAQ_API_KEY    = khóa OpenAQ của nhóm (Việc 2)
#   POSTGRES_PASSWORD = mật khẩu mạnh: openssl rand -base64 24
#   DB_BIND_ADDR      = 100.x.y.z (IP Tailscale ở bước 1)
#   API_BIND_ADDR     = 100.x.y.z

# 4. Khởi động (lần đầu build mất vài phút)
scripts/env/up.sh

# 5. Kiểm tra
scripts/env/status.sh
scripts/env/check-persistence.sh      # tiêu chí "không mất dữ liệu khi khởi động lại"
sudo reboot                           # thử thật: sau khi VPS lên lại, chạy status.sh, mọi thứ phải tự chạy
```

`up.sh` từ chối chạy khi mật khẩu còn là `change-me`, và tự tạo volume `brweather_shared_pgdata` ở lần đầu.

Docker tự khởi động khi VPS bật lại (`systemctl enable docker` ở bước 1), và các container có `restart: unless-stopped` sẽ tự chạy theo.

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
