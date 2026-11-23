-- T1.1-2: lưu thời tiết hiện tại kèm nguồn, fetched_at, valid_time và liên kết tới dữ liệu thô.
--
-- weather_snapshots đã có source, fetched_at và các cột current_* (migration 001).
-- Thêm raw_payload_id để từ một snapshot truy ngược về đúng JSON Open-Meteo đã nhận.

ALTER TABLE weather_snapshots
    ADD COLUMN IF NOT EXISTS raw_payload_id BIGINT REFERENCES raw_payloads(id);

CREATE INDEX IF NOT EXISTS weather_snapshots_point_fetched_idx
    ON weather_snapshots (lat, lon, fetched_at DESC);

-- Thời tiết hiện tại mới nhất của mỗi điểm.
-- valid_time là thời điểm Open-Meteo nói giá trị "hiện tại" có hiệu lực (khác fetched_at = lúc pipeline lấy).
CREATE OR REPLACE VIEW v_weather_current_latest AS
SELECT DISTINCT ON (s.lat, s.lon)
       s.snapshot_id,
       s.lat,
       s.lon,
       s.source,
       'modelled'::text                 AS kind,
       s.fetched_at,
       s.current_valid_time             AS valid_time,
       s.current_temperature_c          AS temperature_c,
       s.current_apparent_temperature_c AS apparent_temperature_c,
       s.current_humidity_pct           AS humidity_pct,
       s.current_precipitation_mm       AS precipitation_mm,
       s.current_weather_code           AS weather_code,
       s.current_wind_speed_kmh         AS wind_speed_kmh,
       s.current_wind_direction_deg     AS wind_direction_deg,
       s.current_uv_index               AS uv_index,
       s.raw_payload_id
FROM weather_snapshots s
WHERE s.current_valid_time IS NOT NULL
ORDER BY s.lat, s.lon, s.fetched_at DESC, s.snapshot_id DESC;
