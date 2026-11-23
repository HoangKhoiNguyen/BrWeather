#!/usr/bin/env bash
# Chạy kiểm thử SQL của phần lưu trữ trên db đã migrate. Không để lại dữ liệu (mỗi file tự ROLLBACK).
#   PGHOST=localhost PGUSER=brweather PGPASSWORD=... PGDATABASE=brweather bash db/tests/run.sh
set -euo pipefail

export PGHOST="${PGHOST:-${POSTGRES_HOST:-localhost}}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-${POSTGRES_USER:-brweather}}"
export PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-}}"
export PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-brweather}}"
export PGOPTIONS="${PGOPTIONS:-} -c client_min_messages=warning"

dir="$(cd "$(dirname "$0")" && pwd)"
for file in "$dir"/test_*.sql; do
  echo "[db-test] $(basename "$file")"
  psql -X -q -v ON_ERROR_STOP=1 -f "$file"
done
