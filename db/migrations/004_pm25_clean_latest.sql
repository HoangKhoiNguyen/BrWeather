-- T2.1-2: bảng số đo sạch và view bản ghi mới nhất mỗi trạm.
--
-- air_measurements đã chống trùng bằng khóa chính (source, station_id, parameter, measured_at)
-- và pipeline ghi bằng ON CONFLICT DO NOTHING, nên nạp lại cùng lô không sinh bản trùng.
-- Ở đây thêm: ràng buộc giá trị cờ chất lượng, và view bản ghi mới nhất.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'air_measurements_quality_flag_check'
    ) THEN
        ALTER TABLE air_measurements
            ADD CONSTRAINT air_measurements_quality_flag_check
            CHECK (quality_flag IN ('ok', 'out_of_range', 'flatline', 'suspect'));
    END IF;
END $$;

-- Bản ghi PM2.5 (OpenAQ, số đo) mới nhất của mỗi trạm đang hoạt động.
-- Trạm chưa có bản ghi nào vẫn có một dòng, các cột số đo là NULL (API trả status "missing").
-- usable = có giá trị và cờ 'ok' (cùng định nghĩa "giờ dùng được" của T3.1-2).
CREATE OR REPLACE VIEW v_pm25_latest AS
SELECT s.id         AS station_id,
       s.name,
       s.lat,
       s.lon,
       m.measured_at,
       m.value,
       m.unit,
       m.kind,
       m.quality_flag,
       m.fetched_at,
       (m.value IS NOT NULL AND m.quality_flag = 'ok') AS usable
FROM stations s
LEFT JOIN LATERAL (
    SELECT a.measured_at, a.value, a.unit, a.kind, a.quality_flag, a.fetched_at
    FROM air_measurements a
    WHERE a.source = 'openaq' AND a.parameter = 'pm25' AND a.station_id = s.id
    ORDER BY a.measured_at DESC
    LIMIT 1
) m ON TRUE
WHERE s.is_active;
