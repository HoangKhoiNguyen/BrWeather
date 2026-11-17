#!/usr/bin/env bash
# Chạy trong service `backup` (compose.shared.yml): mỗi ngày sao lưu một lần lúc BACKUP_HOUR_UTC
# (mặc định 19 UTC = 2 giờ sáng giờ Việt Nam), xóa bản cũ hơn BACKUP_KEEP_DAYS ngày.
set -uo pipefail

export PGHOST="${PGHOST:-db}"
export PGUSER="${PGUSER:-${POSTGRES_USER:-brweather}}"
export PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-}}"
export PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-brweather}}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
HOUR="${BACKUP_HOUR_UTC:-19}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

backup_once() {
  local file="${BACKUP_DIR}/brweather_$(date -u +%Y%m%d_%H%M%S).dump"
  # Ghi ra file tạm rồi mới đổi tên: nếu pg_dump lỗi giữa chừng thì không để lại bản sao lưu hỏng.
  if pg_dump -Fc -f "${file}.part"; then
    mv "${file}.part" "$file"
    echo "[backup] OK $(basename "$file") ($(du -h "$file" | cut -f1))"
  else
    rm -f "${file}.part"
    echo "[backup] LỖI: pg_dump thất bại, thử lại vào lần sau" >&2
  fi
  find "$BACKUP_DIR" -name 'brweather_*.dump' -mtime +"$KEEP_DAYS" -print -delete | sed 's/^/[backup] xóa bản cũ: /'
}

# Khởi động lần đầu mà chưa có bản sao lưu nào hôm nay thì sao lưu ngay.
if ! ls "$BACKUP_DIR"/brweather_"$(date -u +%Y%m%d)"_*.dump >/dev/null 2>&1; then
  backup_once
fi

while true; do
  now=$(date -u +%s)
  next=$(date -u -d "today ${HOUR}:00" +%s)
  (( next <= now )) && next=$(date -u -d "tomorrow ${HOUR}:00" +%s)
  sleep $(( next - now ))
  backup_once
done
