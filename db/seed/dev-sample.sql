-- Dữ liệu MẪU cho máy dev: test backend/app khi chưa có OpenAQ key hoặc pipeline chưa chạy.
-- KHÔNG chạy trên máy chủ thật. Số liệu là giả, mọi thời gian tính theo now() nên chạy lại là "mới".
-- Chạy:  docker compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB < db/seed/dev-sample.sql
-- Xoá:   chạy lại file này (nó tự xoá dữ liệu mẫu cũ trước, id trạm 990001–990004).

BEGIN;

DELETE FROM anomalies          WHERE station_id BETWEEN 990001 AND 990004;
DELETE FROM pm25_forecasts     WHERE station_id BETWEEN 990001 AND 990004;
DELETE FROM reliability_scores WHERE station_id BETWEEN 990001 AND 990004;
DELETE FROM air_measurements   WHERE station_id BETWEEN 990001 AND 990004;
DELETE FROM stations           WHERE id BETWEEN 990001 AND 990004;
DELETE FROM weather_snapshots  WHERE source = 'dev-sample';

INSERT INTO stations (id, name, provider, lat, lon, is_active, first_seen, last_seen) VALUES
  (990001, '[Mẫu] Hoàn Kiếm',  'dev-sample', 21.0285, 105.8542, TRUE, now() - interval '30 days', now()),
  (990002, '[Mẫu] Cầu Giấy',   'dev-sample', 21.0362, 105.7906, TRUE, now() - interval '30 days', now()),
  (990003, '[Mẫu] Long Biên',  'dev-sample', 21.0470, 105.8890, TRUE, now() - interval '30 days', now() - interval '5 hours'),
  (990004, '[Mẫu] Sóc Sơn',    'dev-sample', 21.2600, 105.8500, TRUE, now() - interval '30 days', NULL);

-- 990001, 990002: 24 giờ gần nhất, thiếu 2 giờ để thấy khoảng trống null trên biểu đồ.
INSERT INTO air_measurements (source, station_id, parameter, measured_at, value, unit, kind)
SELECT 'openaq', s.id, 'pm25', date_trunc('hour', now()) - make_interval(hours => h),
       round((45 + 25 * sin(h / 4.0) + (s.id - 990001) * 12)::numeric, 1), 'µg/m³', 'observed'
FROM (VALUES (990001), (990002)) AS s(id), generate_series(0, 23) AS h
WHERE h NOT IN (6, 7);

-- 990003: bản ghi cuối 5 giờ trước -> status "stale". 990004: không có bản ghi -> "missing".
INSERT INTO air_measurements (source, station_id, parameter, measured_at, value, unit, kind)
SELECT 'openaq', 990003, 'pm25', date_trunc('hour', now()) - make_interval(hours => h), 88.0, 'µg/m³', 'observed'
FROM generate_series(5, 23) AS h;

INSERT INTO reliability_scores (station_id, computed_at, level, reasons) VALUES
  (990001, now(), 'high',   '[]'),
  (990002, now(), 'medium', '["thiếu 2 giờ trong 24 giờ qua"]'),
  (990003, now(), 'low',    '["dữ liệu cũ hơn 3 giờ"]');

-- Dự báo 24 giờ cho 990001; 990002 cố ý không có để test available=false.
INSERT INTO pm25_forecasts (station_id, issued_at, target_time, value, model_version)
SELECT 990001, date_trunc('hour', now()), date_trunc('hour', now()) + make_interval(hours => h),
       round((50 + 20 * cos(h / 5.0))::numeric, 1), 'baseline-persistence-0.1'
FROM generate_series(1, 24) AS h;

INSERT INTO anomalies (station_id, start_time, end_time, category, description, detected_by) VALUES
  (990001, now() - interval '3 days', now() - interval '3 days' + interval '2 hours', 'data',
   'Giá trị nhảy đột ngột rồi về lại, có thể lỗi cảm biến', 'dev-sample'),
  (990001, now() - interval '1 day', now() - interval '1 day' + interval '6 hours', 'environment',
   'PM2.5 tăng ở nhiều trạm cùng lúc, gió yếu', 'dev-sample');

-- Thời tiết: 1 snapshot tại Hoàn Kiếm, 7 ngày theo giờ từ 00:00 UTC hôm nay (giống pipeline).
WITH snap AS (
  INSERT INTO weather_snapshots (lat, lon, fetched_at, source)
  VALUES (21.0285, 105.8542, now() - interval '20 minutes', 'dev-sample')
  RETURNING snapshot_id
)
INSERT INTO weather_hourly (snapshot_id, valid_time, temperature_c, apparent_temperature_c, humidity_pct,
                            precipitation_mm, precipitation_prob_pct, weather_code, wind_speed_kmh,
                            wind_direction_deg, uv_index, boundary_layer_height_m)
SELECT snap.snapshot_id,
       date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' + make_interval(hours => h),
       round((22 + 5 * sin((h - 2) * pi() / 12))::numeric, 1),
       round((23 + 5 * sin((h - 2) * pi() / 12))::numeric, 1),
       75 + (h % 10),
       CASE WHEN h % 24 BETWEEN 8 AND 10 AND h > 48 THEN 1.2 ELSE 0 END,
       CASE WHEN h > 48 THEN 60 ELSE 10 END,
       CASE WHEN h % 24 BETWEEN 8 AND 10 AND h > 48 THEN 61 WHEN h % 24 BETWEEN 0 AND 10 THEN 2 ELSE 3 END,
       8 + (h % 7), 120, GREATEST(0, round((6 * sin((h - 23) * pi() / 12))::numeric, 1)), 600
FROM snap, generate_series(0, 167) AS h;

COMMIT;
