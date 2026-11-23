-- T1.3-2: lưu dự báo theo ngày theo snapshot, truy vấn trả 7 ngày kèm thời điểm phát hành.
--
-- Open-Meteo không trả thời điểm chạy mô hình, nên "thời điểm phát hành" của brWeather là
-- fetched_at của snapshot (lúc pipeline lấy dự báo). Mỗi snapshot giữ nguyên, không ghi đè.

ALTER TABLE weather_daily
    ADD COLUMN IF NOT EXISTS precipitation_prob_max_pct DOUBLE PRECISION;

-- Dự báo 7 ngày của snapshot mới nhất (có dữ liệu ngày) ở mỗi điểm.
CREATE OR REPLACE VIEW v_weather_daily_latest AS
WITH latest AS (
    SELECT DISTINCT ON (s.lat, s.lon) s.snapshot_id, s.lat, s.lon, s.source, s.fetched_at, s.raw_payload_id
    FROM weather_snapshots s
    WHERE EXISTS (SELECT 1 FROM weather_daily d WHERE d.snapshot_id = s.snapshot_id)
    ORDER BY s.lat, s.lon, s.fetched_at DESC, s.snapshot_id DESC
)
SELECT l.snapshot_id,
       l.lat,
       l.lon,
       l.source,
       'forecast'::text  AS kind,
       l.fetched_at      AS issued_at,
       d.day,
       d.temperature_max_c,
       d.temperature_min_c,
       d.precipitation_sum_mm,
       d.precipitation_prob_max_pct,
       d.weather_code,
       d.sunrise,
       d.sunset,
       l.raw_payload_id
FROM latest l
JOIN weather_daily d ON d.snapshot_id = l.snapshot_id;
