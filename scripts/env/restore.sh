#!/usr/bin/env bash
# Phục hồi cơ sở dữ liệu từ một file .dump (tạo bởi backup.sh hoặc service backup).
#   scripts/env/restore.sh backups/brweather_20261117_190000.dump
# CẢNH BÁO: ghi đè dữ liệu hiện tại của các bảng có trong file sao lưu.
source "$(dirname "$0")/_common.sh"
dump="${1:?Cần đường dẫn file .dump}"
[[ -f "$dump" ]] || { echo "Không thấy file $dump" >&2; exit 1; }

read -r -p "Phục hồi từ $dump sẽ ghi đè dữ liệu hiện tại. Gõ 'yes' để tiếp tục: " ok
[[ "$ok" == "yes" ]] || { echo "Đã hủy."; exit 1; }

# Dừng các service đang ghi vào db trong lúc phục hồi
compose stop pipeline backend
compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$dump"
compose start backend pipeline
echo "Đã phục hồi từ $dump"
