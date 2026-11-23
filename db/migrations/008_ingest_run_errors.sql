-- T2.1-1 (và chuẩn bị C-06): lỗi của từng trạm/bước trong một lượt chạy.
--
-- Một trạm lỗi không còn làm hỏng cả lượt: các trạm khác vẫn được lưu, lượt chạy có status 'partial'.
-- errors: [{"station_id": 2161306, "stage": "pm25" | "weather", "kind": "source" | "internal", "message": "..."}]
--   kind = 'source'   : lỗi phía nguồn (HTTP lỗi, hết hạn mức, mất mạng)
--   kind = 'internal' : lỗi của pipeline/cơ sở dữ liệu
-- C-06 dùng cột này để tách tỷ lệ lỗi nguồn và lỗi nội bộ.

ALTER TABLE ingest_runs
    ADD COLUMN IF NOT EXISTS errors JSONB NOT NULL DEFAULT '[]';

CREATE INDEX IF NOT EXISTS ingest_runs_job_started_idx
    ON ingest_runs (job, started_at DESC);
