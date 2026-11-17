#!/usr/bin/env bash
# Sao lưu cơ sở dữ liệu ngay lập tức (ngoài lịch hằng ngày). Chạy trên máy chủ:
#   scripts/env/backup.sh
source "$(dirname "$0")/_common.sh"
mkdir -p backups
file="backups/brweather_$(date -u +%Y%m%d_%H%M%S)_manual.dump"
compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "${file}.part"
mv "${file}.part" "$file"
echo "Đã sao lưu: $file ($(du -h "$file" | cut -f1))"
