-- Kiểm thử phần lưu trữ (T1.1-2, T1.3-2, T2.1-2, T2.3-2, T3.1-1, T4.1-3) trên Postgres thật.
-- Chạy sau migrate: bash db/tests/run.sh. Mọi thứ nằm trong một transaction và ROLLBACK ở cuối,
-- nên chạy được cả trên db có dữ liệu thật mà không để lại gì. Lỗi thì psql dừng với mã khác 0.
\set ON_ERROR_STOP 1
BEGIN;

-- Dữ liệu thử: id trạm 980001–980005 (không trùng trạm thật hay dữ liệu mẫu 99000x)
INSERT INTO stations (id, name, provider, lat, lon, is_active) VALUES
  (980001, '[Test] A', 'test', 21.00, 105.80, TRUE),
  (980002, '[Test] B', 'test', 21.01, 105.81, TRUE),
  (980003, '[Test] C', 'test', 21.02, 105.82, TRUE),
  (980004, '[Test] D', 'test', 21.03, 105.83, TRUE),
  (980005, '[Test] E - chưa có số đo', 'test', 21.04, 105.84, TRUE);

-- ---------------------------------------------------------------- T2.1-2: chống trùng
CREATE TEMP TABLE batch AS
SELECT s.id AS station_id, timestamptz '2026-11-20 00:00+00' + make_interval(hours => h) AS measured_at,
       (20 + h)::double precision AS value
FROM generate_series(980001, 980004) AS s(id), generate_series(0, 5) AS h;

INSERT INTO air_measurements (source, station_id, parameter, measured_at, value, unit, kind)
SELECT 'openaq', station_id, 'pm25', measured_at, value, 'µg/m³', 'observed' FROM batch
ON CONFLICT DO NOTHING;
-- Nạp lại đúng lô đó (như pipeline chạy lại)
INSERT INTO air_measurements (source, station_id, parameter, measured_at, value, unit, kind)
SELECT 'openaq', station_id, 'pm25', measured_at, value, 'µg/m³', 'observed' FROM batch
ON CONFLICT DO NOTHING;

DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM air_measurements WHERE station_id BETWEEN 980001 AND 980005;
    IF n <> 24 THEN RAISE EXCEPTION 'T2.1-2: nạp lại cùng lô phải giữ 24 bản ghi, đang có %', n; END IF;
END $$;

-- Cờ chất lượng ngoài danh sách bị từ chối
DO $$
BEGIN
    BEGIN
        INSERT INTO air_measurements (source, station_id, parameter, measured_at, value, unit, kind, quality_flag)
        VALUES ('openaq', 980001, 'pm25', '2026-11-21 00:00+00', 10, 'µg/m³', 'observed', 'bogus');
        RAISE EXCEPTION 'T2.1-2: cờ chất lượng "bogus" phải bị từ chối';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END $$;

-- View bản ghi mới nhất trả đủ 5 trạm, trạm chưa có số đo có giá trị NULL
DO $$
DECLARE n int; v double precision; t timestamptz; missing_value double precision;
BEGIN
    SELECT count(*) INTO n FROM v_pm25_latest WHERE station_id BETWEEN 980001 AND 980005;
    IF n <> 5 THEN RAISE EXCEPTION 'T2.1-2: v_pm25_latest phải trả 5 trạm, đang trả %', n; END IF;
    SELECT value, measured_at INTO v, t FROM v_pm25_latest WHERE station_id = 980001;
    IF v <> 25 OR t <> timestamptz '2026-11-20 05:00+00' THEN
        RAISE EXCEPTION 'T2.1-2: bản ghi mới nhất của 980001 sai (% lúc %)', v, t;
    END IF;
    SELECT value INTO missing_value FROM v_pm25_latest WHERE station_id = 980005;
    IF missing_value IS NOT NULL THEN RAISE EXCEPTION 'T2.1-2: trạm chưa có số đo phải trả NULL'; END IF;
END $$;

-- ---------------------------------------------------------------- T2.3-2: chuỗi theo giờ
-- 980002: xóa giờ 02:00, gắn cờ giờ 03:00 -> 2 giờ đó phải ra value NULL
DELETE FROM air_measurements WHERE station_id = 980002 AND measured_at = '2026-11-20 02:00+00';
UPDATE air_measurements SET quality_flag = 'flatline'
WHERE station_id = 980002 AND measured_at = '2026-11-20 03:00+00';

DO $$
DECLARE n int; n_null int; s2 text; s3 text; v0 double precision; first_hour timestamptz;
BEGIN
    SELECT count(*), count(*) FILTER (WHERE value IS NULL) INTO n, n_null
    FROM pm25_hourly_series(980002, '2026-11-19 22:00+00', '2026-11-20 08:00+00');
    -- 10 giờ: 22h, 23h (không có bản ghi), 00h–05h (có, trừ 02h thiếu và 03h bị cờ), 06h, 07h (không có)
    IF n <> 10 THEN RAISE EXCEPTION 'T2.3-2: phải có 10 giờ liên tục, đang có %', n; END IF;
    IF n_null <> 6 THEN RAISE EXCEPTION 'T2.3-2: phải có 6 giờ NULL, đang có %', n_null; END IF;
    SELECT status INTO s2 FROM pm25_hourly_series(980002, '2026-11-20 00:00+00', '2026-11-20 06:00+00')
    WHERE hour = '2026-11-20 02:00+00';
    SELECT status INTO s3 FROM pm25_hourly_series(980002, '2026-11-20 00:00+00', '2026-11-20 06:00+00')
    WHERE hour = '2026-11-20 03:00+00';
    IF s2 <> 'missing' OR s3 <> 'flagged' THEN
        RAISE EXCEPTION 'T2.3-2: trạng thái giờ thiếu/bị cờ sai (% / %)', s2, s3;
    END IF;
    -- Không bao giờ thay giờ thiếu bằng 0
    IF EXISTS (SELECT 1 FROM pm25_hourly_series(980002, '2026-11-19 22:00+00', '2026-11-20 08:00+00') WHERE value = 0) THEN
        RAISE EXCEPTION 'T2.3-2: giờ thiếu không được thành 0';
    END IF;
    -- Mốc không tròn giờ được làm tròn xuống, kết quả không phụ thuộc múi giờ phiên làm việc
    SET LOCAL TIME ZONE 'Asia/Ho_Chi_Minh';
    SELECT min(hour), (array_agg(value ORDER BY hour))[1] INTO first_hour, v0
    FROM pm25_hourly_series(980002, '2026-11-20 00:40+00', '2026-11-20 02:00+00');
    IF first_hour <> timestamptz '2026-11-20 00:00+00' OR v0 <> 20 THEN
        RAISE EXCEPTION 'T2.3-2: làm tròn giờ sai (% / %)', first_hour, v0;
    END IF;
END $$;

-- ---------------------------------------------------------------- T3.1-1: dự báo không ghi đè
INSERT INTO pm25_forecasts (station_id, issued_at, target_time, value, model_version)
SELECT 980001, i, i + make_interval(hours => h), 30 + h, 'persistence-v1'
FROM (VALUES (timestamptz '2026-11-20 06:00+00'), (timestamptz '2026-11-20 07:00+00')) AS iss(i),
     generate_series(1, 24) AS h;

DO $$
DECLARE n_issue int; n_rows int; latest timestamptz;
BEGIN
    SELECT count(DISTINCT issued_at), count(*) INTO n_issue, n_rows FROM pm25_forecasts WHERE station_id = 980001;
    IF n_issue <> 2 OR n_rows <> 48 THEN
        RAISE EXCEPTION 'T3.1-1: phát hành 2 lần phải giữ 2 bản (48 dòng), đang có % bản / % dòng', n_issue, n_rows;
    END IF;
    SELECT max(issued_at) INTO latest FROM v_pm25_forecast_latest WHERE station_id = 980001;
    IF latest <> timestamptz '2026-11-20 07:00+00' THEN RAISE EXCEPTION 'T3.1-1: bản mới nhất sai: %', latest; END IF;

    BEGIN
        UPDATE pm25_forecasts SET value = 0 WHERE station_id = 980001;
        RAISE EXCEPTION 'T3.1-1: UPDATE dự báo đã phát hành phải bị chặn';
    EXCEPTION WHEN restrict_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO pm25_forecasts (station_id, issued_at, target_time, value, model_version)
        VALUES (980001, '2026-11-20 06:00+00', '2026-11-20 07:00+00', 999, 'x')
        ON CONFLICT (station_id, issued_at, target_time) DO UPDATE SET value = EXCLUDED.value;
        RAISE EXCEPTION 'T3.1-1: upsert ghi đè dự báo phải bị chặn';
    EXCEPTION WHEN restrict_violation THEN NULL;
    END;
END $$;

-- ---------------------------------------------------------------- T1.1-2, T1.3-2: thời tiết
INSERT INTO raw_payloads (id, source, request, payload) VALUES
  (-1, 'open-meteo', 'forecast test', '{"current": {"time": "2026-11-20T06:00"}}'),
  (-2, 'open-meteo', 'forecast test', '{"current": {"time": "2026-11-20T07:00"}}');

INSERT INTO weather_snapshots (snapshot_id, lat, lon, fetched_at, source, current_valid_time,
                               current_temperature_c, current_uv_index, raw_payload_id)
VALUES (-1, 21.5, 105.5, '2026-11-20 06:05+00', 'open-meteo', '2026-11-20 06:00+00', 24.0, NULL, -1),
       (-2, 21.5, 105.5, '2026-11-20 07:05+00', 'open-meteo', '2026-11-20 07:00+00', 25.0, NULL, -2);

INSERT INTO weather_daily (snapshot_id, day, temperature_max_c, temperature_min_c, precipitation_sum_mm,
                           precipitation_prob_max_pct, weather_code, sunrise, sunset)
SELECT sid, date '2026-11-20' + d, 28, 19, 0.5, 40, 3,
       timestamptz '2026-11-19 23:15+00' + make_interval(days => d),
       timestamptz '2026-11-20 10:20+00' + make_interval(days => d)
FROM (VALUES (-1), (-2)) AS s(sid), generate_series(0, 6) AS d;

DO $$
DECLARE r record; n int; issued timestamptz;
BEGIN
    SELECT * INTO r FROM v_weather_current_latest WHERE lat = 21.5 AND lon = 105.5;
    IF r.snapshot_id <> -2 OR r.temperature_c <> 25 OR r.raw_payload_id <> -2
       OR r.source <> 'open-meteo' OR r.valid_time <> timestamptz '2026-11-20 07:00+00'
       OR r.fetched_at <> timestamptz '2026-11-20 07:05+00' OR r.uv_index IS NOT NULL THEN
        RAISE EXCEPTION 'T1.1-2: thời tiết hiện tại mới nhất sai: %', r;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM raw_payloads WHERE id = r.raw_payload_id AND payload ? 'current') THEN
        RAISE EXCEPTION 'T1.1-2: không truy được dữ liệu thô';
    END IF;

    SELECT count(*), min(issued_at) INTO n, issued FROM v_weather_daily_latest WHERE lat = 21.5 AND lon = 105.5;
    IF n <> 7 OR issued <> timestamptz '2026-11-20 07:05+00' THEN
        RAISE EXCEPTION 'T1.3-2: phải trả 7 ngày của snapshot mới nhất kèm thời điểm phát hành (% ngày, %)', n, issued;
    END IF;
    -- Snapshot cũ vẫn còn nguyên (không ghi đè)
    SELECT count(*) INTO n FROM weather_daily WHERE snapshot_id = -1;
    IF n <> 7 THEN RAISE EXCEPTION 'T1.3-2: snapshot cũ phải giữ nguyên 7 ngày'; END IF;
END $$;

-- ---------------------------------------------------------------- T4.1-3: mức tin cậy mới nhất
INSERT INTO reliability_scores (station_id, computed_at, level, reasons, details) VALUES
  (980001, '2026-11-20 06:00+00', 'low',  '["flatline", "stale"]', '{"flatline_hours": 6}'),
  (980001, '2026-11-20 07:00+00', 'high', '[]', '{"hours_since_last": 1}');

DO $$
DECLARE lvl text; d jsonb;
BEGIN
    SELECT level, details INTO lvl, d FROM v_reliability_latest WHERE station_id = 980001;
    IF lvl <> 'high' OR (d->>'hours_since_last')::int <> 1 THEN
        RAISE EXCEPTION 'T4.1-3: mức tin cậy mới nhất sai (%, %)', lvl, d;
    END IF;
END $$;

-- ---------------------------------------------------------------- T2.1-1: lỗi từng trạm
DO $$
DECLARE n int;
BEGIN
    INSERT INTO ingest_runs (job, status, errors)
    VALUES ('test', 'partial', '[{"station_id": 980001, "stage": "pm25", "kind": "source", "message": "HTTP 503"}]');
    SELECT count(*) INTO n FROM ingest_runs, jsonb_array_elements(errors) e
    WHERE job = 'test' AND e->>'kind' = 'source';
    IF n <> 1 THEN RAISE EXCEPTION 'T2.1-1: cột errors không đọc được'; END IF;
END $$;

\echo 'db/tests/test_storage.sql: tất cả kiểm thử lưu trữ đạt'
ROLLBACK;
