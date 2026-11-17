#!/usr/bin/env bash
# Áp schema và migration cho cơ sở dữ liệu brWeather. Chạy lại nhiều lần vẫn an toàn.
#
#   1. db/schema.sql: chỉ dùng CREATE ... IF NOT EXISTS, nên tạo được bảng mới
#      nhưng KHÔNG sửa được bảng đã có.
#   2. db/migrations/NNN_ten.sql: thay đổi bảng đã có (thêm cột, index...). Mỗi file chạy
#      đúng một lần, theo thứ tự tên, và được ghi vào bảng schema_migrations.
#
# Trong Docker: chạy tự động bởi service `migrate`.
# Chạy tay:     PGHOST=localhost PGUSER=brweather PGPASSWORD=... PGDATABASE=brweather scripts/db/migrate.sh
set -euo pipefail

export PGHOST="${PGHOST:-${POSTGRES_HOST:-localhost}}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-${POSTGRES_USER:-brweather}}"
export PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-}}"
export PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-brweather}}"

# Trong container, thư mục db được gắn vào /db; khi chạy tay thì dùng db/ của repo.
DB_DIR="${DB_DIR:-}"
if [[ -z "$DB_DIR" ]]; then
  if [[ -d /db ]]; then DB_DIR=/db; else DB_DIR="$(cd "$(dirname "$0")/../../db" && pwd)"; fi
fi

# Ẩn các NOTICE "already exists, skipping" khi chạy lại
export PGOPTIONS="${PGOPTIONS:-} -c client_min_messages=warning"
PSQL=(psql -v ON_ERROR_STOP=1 -X -q)

echo "[migrate] Áp ${DB_DIR}/schema.sql vào ${PGDATABASE}@${PGHOST}:${PGPORT}"
"${PSQL[@]}" -f "${DB_DIR}/schema.sql"

"${PSQL[@]}" -c "CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);"

shopt -s nullglob
applied=0
for file in "${DB_DIR}"/migrations/*.sql; do
  version="$(basename "$file" .sql)"
  done_already="$("${PSQL[@]}" -tA -v v="$version" <<'SQL'
SELECT 1 FROM schema_migrations WHERE version = :'v';
SQL
)"
  if [[ "$done_already" == "1" ]]; then
    continue
  fi
  echo "[migrate] Chạy ${version}"
  # File migration và dòng ghi nhận nằm chung một transaction: lỗi giữa chừng thì không ghi gì cả.
  "${PSQL[@]}" -1 -v v="$version" -f "$file" -f - <<'SQL'
INSERT INTO schema_migrations (version) VALUES (:'v');
SQL
  applied=$((applied + 1))
done

echo "[migrate] Xong. Migration mới áp dụng: ${applied}"
