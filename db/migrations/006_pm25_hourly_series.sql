-- T2.3-2: chuỗi PM2.5 theo giờ đầy đủ lịch giờ, giờ thiếu trả NULL.
--
-- Một view không nhận tham số khoảng thời gian, nên dùng hàm trả bảng:
--   SELECT * FROM pm25_hourly_series(2161306, '2026-11-20', '2026-11-23');
-- Trả đúng một dòng cho mỗi giờ trong [p_from, p_to) (làm tròn xuống đầu giờ, UTC).
--   value        : NULL khi giờ đó không có số đo, giá trị NULL, hoặc bị gắn cờ (không bao giờ là 0)
--   raw_value    : giá trị gốc trong kho (kể cả khi bị gắn cờ), để rà soát
--   quality_flag : NULL khi giờ đó không có bản ghi
--   status       : 'ok' | 'flagged' | 'missing'

CREATE OR REPLACE FUNCTION pm25_hourly_series(p_station_id BIGINT, p_from TIMESTAMPTZ, p_to TIMESTAMPTZ)
RETURNS TABLE (
    hour         TIMESTAMPTZ,
    value        DOUBLE PRECISION,
    raw_value    DOUBLE PRECISION,
    quality_flag TEXT,
    status       TEXT
)
LANGUAGE sql STABLE AS $$
    WITH hours AS (
        SELECT generate_series(
                   date_trunc('hour', p_from AT TIME ZONE 'UTC') AT TIME ZONE 'UTC',
                   p_to - interval '1 microsecond',
                   interval '1 hour') AS hour
    ),
    m AS (
        -- Có trạm gửi nhiều hơn 1 bản ghi/giờ: lấy trung bình các bản ghi dùng được trong giờ đó.
        SELECT date_trunc('hour', a.measured_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS hour,
               avg(a.value) FILTER (WHERE a.value IS NOT NULL AND a.quality_flag = 'ok') AS ok_value,
               avg(a.value) AS any_value,
               CASE WHEN bool_or(a.value IS NOT NULL AND a.quality_flag = 'ok') THEN 'ok'
                    ELSE min(a.quality_flag) END AS flag
        FROM air_measurements a
        WHERE a.source = 'openaq' AND a.parameter = 'pm25'
          AND a.station_id = p_station_id
          AND a.measured_at >= date_trunc('hour', p_from AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
          AND a.measured_at < p_to
        GROUP BY 1
    )
    SELECT h.hour,
           m.ok_value,
           m.any_value,
           m.flag,
           CASE WHEN m.ok_value IS NOT NULL THEN 'ok'
                WHEN m.hour IS NOT NULL AND m.any_value IS NOT NULL THEN 'flagged'
                ELSE 'missing' END
    FROM hours h
    LEFT JOIN m ON m.hour = h.hour
    ORDER BY h.hour;
$$;
