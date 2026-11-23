-- T3.1-1: bảng dự báo lưu theo thời điểm phát hành, không ghi đè; thêm chỉ mục truy vấn.
--
-- Khóa chính (station_id, issued_at, target_time) đã giữ mỗi lần phát hành thành một bộ riêng.
-- Trigger dưới đây chặn UPDATE, kể cả INSERT ... ON CONFLICT DO UPDATE, để dự báo đã phát hành
-- không bị sửa lại (US4.2 cần so đúng con số đã phát hành với số đo).
-- DELETE vẫn được phép (dọn dữ liệu mẫu, phục hồi bản sao lưu).

CREATE OR REPLACE FUNCTION pm25_forecasts_no_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'pm25_forecasts is append-only: issue a new forecast (new issued_at) instead of updating station %, issued_at %',
        OLD.station_id, OLD.issued_at
        USING ERRCODE = 'restrict_violation';
END $$;

DROP TRIGGER IF EXISTS pm25_forecasts_no_update ON pm25_forecasts;
CREATE TRIGGER pm25_forecasts_no_update
    BEFORE UPDATE ON pm25_forecasts
    FOR EACH ROW EXECUTE FUNCTION pm25_forecasts_no_update();

-- Khóa chính đã phục vụ "bản phát hành mới nhất của trạm" (station_id, issued_at ...).
-- Thêm chỉ mục cho đánh giá dự báo (US4.2): tìm mọi dự báo nhắm tới một giờ của một trạm.
CREATE INDEX IF NOT EXISTS pm25_forecasts_station_target_idx
    ON pm25_forecasts (station_id, target_time);

-- Bản phát hành mới nhất của mỗi trạm.
CREATE OR REPLACE VIEW v_pm25_forecast_latest AS
SELECT f.station_id, f.issued_at, f.target_time, f.value, f.model_version
FROM pm25_forecasts f
JOIN (
    SELECT station_id, max(issued_at) AS issued_at FROM pm25_forecasts GROUP BY station_id
) last USING (station_id, issued_at);
