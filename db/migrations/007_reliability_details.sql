-- T4.1-3: mức tin cậy mỗi giờ, lưu kèm danh sách lý do và số liệu dẫn tới.
--
-- reasons : mảng mã lý do, ví dụ ["flatline", "stale"] (T4.1-4 đổi mã thành câu dễ hiểu)
-- details : số liệu dùng để kết luận, ví dụ {"latest_value": 48.2, "hours_since_last": 1,
--           "neighbour_count": 2, "local_median": 45.0, "flatline_hours": 0}
--           để API/AI giải thích (US6.1) chỉ dùng con số có thật.

ALTER TABLE reliability_scores
    ADD COLUMN IF NOT EXISTS details JSONB NOT NULL DEFAULT '{}';

-- Mức tin cậy mới nhất của mỗi trạm.
CREATE OR REPLACE VIEW v_reliability_latest AS
SELECT DISTINCT ON (r.station_id) r.station_id, r.computed_at, r.level, r.reasons, r.details
FROM reliability_scores r
ORDER BY r.station_id, r.computed_at DESC;
