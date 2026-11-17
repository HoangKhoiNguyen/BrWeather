# Dùng chung cho các script trong scripts/env/. Không chạy trực tiếp file này.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
SHARED_VOLUME="brweather_shared_pgdata"
compose() { docker compose -f docker-compose.yml -f compose.shared.yml "$@"; }
env_get() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- ; }
# Chạy SQL (đọc từ stdin) trong container db. Thêm cờ psql nếu cần, ví dụ: psql_db -At <<'SQL' ... SQL
psql_db() { compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -v ON_ERROR_STOP=1 "$@"' sh "$@"; }
