-- T5.1-1 / T5.2-1: bất thường PM2.5 theo sự kiện, kèm số liệu và lý do phân loại.
--
-- Job detect_anomalies chạy mỗi giờ, gộp các giờ liên tiếp bị gắn cờ thành một sự kiện.
-- category (đã có): 'data' = có thể do lỗi đo | 'environment' = biến động thật | 'needs_review' = cần kiểm tra
-- Các cột thêm:
--   direction      'up' (tăng) | 'down' (giảm)
--   peak_time      giờ có độ lệch lớn nhất; peak_value, baseline_value (trung vị 72 giờ trước), score (robust z)
--   details        số liệu và mã lý do phân loại, để API/AI giải thích chỉ dùng số thật (US6.1)
--   updated_at     lần cuối job cập nhật (sự kiện đang diễn ra được kéo dài mỗi giờ)
-- Sự kiện đã có người rà soát (reviewed = TRUE) không bị job ghi đè phân loại.

ALTER TABLE anomalies
    ADD COLUMN IF NOT EXISTS direction      TEXT,
    ADD COLUMN IF NOT EXISTS peak_time      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS peak_value     DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS baseline_value DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS score          DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS details        JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS updated_at     TIMESTAMPTZ NOT NULL DEFAULT now();

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'anomalies_direction_check') THEN
        ALTER TABLE anomalies ADD CONSTRAINT anomalies_direction_check
            CHECK (direction IS NULL OR direction IN ('up', 'down'));
    END IF;
END $$;

-- Một sự kiện mỗi (trạm, bộ phát hiện, giờ bắt đầu): chạy lại job không sinh bản trùng.
CREATE UNIQUE INDEX IF NOT EXISTS anomalies_station_detector_start_key
    ON anomalies (station_id, detected_by, start_time);

-- API /stations/{id}/anomalies?days=14 lọc theo trạm và thời gian.
CREATE INDEX IF NOT EXISTS anomalies_station_start_idx
    ON anomalies (station_id, start_time DESC);
