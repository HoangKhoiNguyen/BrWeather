#!/usr/bin/env bash
# Xem nhanh môi trường chung có khỏe không: container, API, lần ingest gần nhất, bản sao lưu.
#   scripts/env/status.sh
source "$(dirname "$0")/_common.sh"

echo "== Container"
compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'

echo; echo "== Máy chủ"
if command -v free >/dev/null; then
  free -m | awk '/^Mem:/ {printf "RAM: dùng %d/%d MB (%.0f%%)", $3, $2, $3*100/$2; if ($3*100/$2 < 25) printf "  <- thấp: Oracle Always Free có thể coi là nhàn rỗi, xem docs/shared-environment.md"; print ""}'
fi
df -h / | awk 'NR==2 {print "Ổ đĩa /: dùng " $3 "/" $2 " (" $5 ")"}'

echo; echo "== API"
port="$(env_get API_HOST_PORT)"; port="${port:-8080}"
if curl -fsS --max-time 5 "http://localhost:${port}/api/v1/health"; then echo; else echo "API không phản hồi"; fi

echo; echo "== 5 lần ingest gần nhất (giờ UTC)"
psql_db <<'SQL'
SELECT run_id, job, started_at::timestamp(0) AS started_utc, status, records,
       left(coalesce(error, ''), 60) AS error
FROM ingest_runs ORDER BY run_id DESC LIMIT 5;
SQL

echo "== Số bản ghi"
psql_db -At -F ' : ' <<'SQL'
SELECT 'stations', count(*) FROM stations
UNION ALL SELECT 'air_measurements', count(*) FROM air_measurements
UNION ALL SELECT 'weather_snapshots', count(*) FROM weather_snapshots;
SQL

echo; echo "== Bản sao lưu mới nhất"
ls -1t backups/*.dump 2>/dev/null | head -3 || echo "Chưa có"
