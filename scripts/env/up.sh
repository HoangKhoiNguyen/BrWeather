#!/usr/bin/env bash
# Khởi động (hoặc cập nhật) môi trường chung trên máy chủ. Chạy lại sau mỗi lần `git pull`.
#   scripts/env/up.sh
source "$(dirname "$0")/_common.sh"

[[ -f .env ]] || { echo "Chưa có .env. Chạy: cp .env.example .env rồi điền giá trị." >&2; exit 1; }

pw="$(env_get POSTGRES_PASSWORD)"
if [[ -z "$pw" || "$pw" == "change-me" ]]; then
  echo "POSTGRES_PASSWORD trong .env đang trống hoặc là 'change-me'. Đặt mật khẩu mạnh trước khi chạy máy chủ chung." >&2
  echo "Gợi ý: openssl rand -base64 24" >&2
  exit 1
fi
[[ -n "$(env_get OPENAQ_API_KEY)" ]] || echo "Cảnh báo: OPENAQ_API_KEY trống, pipeline sẽ báo lỗi mỗi giờ cho tới khi có khóa." >&2
for var in DB_BIND_ADDR API_BIND_ADDR; do
  v="$(env_get "$var")"
  if [[ -z "$v" || "$v" == "0.0.0.0" ]]; then
    echo "Cảnh báo: $var đang là ${v:-mặc định}. Trên VPS hãy đặt IP Tailscale (100.x.y.z), vì Docker mở cổng vòng qua ufw." >&2
  fi
done

if ! docker volume inspect "$SHARED_VOLUME" >/dev/null 2>&1; then
  echo "Tạo volume dữ liệu $SHARED_VOLUME (một lần duy nhất)"
  docker volume create "$SHARED_VOLUME" >/dev/null
fi
mkdir -p backups

compose up -d --build --remove-orphans
echo
compose ps
echo
echo "Kiểm tra tình trạng: scripts/env/status.sh"
