#!/usr/bin/env bash
# Kiểm tra tiêu chí C-03 "dữ liệu không mất khi khởi động lại":
# ghi một dòng đánh dấu, dừng hẳn toàn bộ container (down), bật lại (up), rồi tìm lại dòng đó.
#   scripts/env/check-persistence.sh
source "$(dirname "$0")/_common.sh"

marker="c03_persistence_check_$(date -u +%s)"
psql_db -At -v m="$marker" >/dev/null <<'SQL'
INSERT INTO ingest_runs (job, status, error) VALUES (:'m', 'success', 'dòng kiểm tra C-03, sẽ tự xóa');
SQL
echo "1/4 Đã ghi dòng đánh dấu ${marker}"

echo "2/4 Dừng và xóa toàn bộ container (docker compose down, giữ volume)"
compose down

echo "3/4 Khởi động lại"
compose up -d --wait db

found="$(psql_db -At -v m="$marker" <<'SQL'
SELECT count(*) FROM ingest_runs WHERE job = :'m';
SQL
)"
psql_db -At -v m="$marker" >/dev/null <<'SQL'
DELETE FROM ingest_runs WHERE job = :'m';
SQL
compose up -d

if [[ "$found" == "1" ]]; then
  echo "4/4 ĐẠT: dữ liệu còn nguyên sau khi khởi động lại."
else
  echo "4/4 KHÔNG ĐẠT: không tìm thấy dòng đánh dấu (kết quả: '${found}')." >&2
  exit 1
fi
