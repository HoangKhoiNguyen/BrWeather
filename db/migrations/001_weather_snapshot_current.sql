-- Open-Meteo "current" block stored with each weather snapshot.
-- data-pipeline/src/brweather_data/db.py (insert_weather_snapshot) writes these columns;
-- without them every weather insert fails with "column ... does not exist".
-- Same columns as db/schema.sql, so this is a no-op on a freshly created database.

ALTER TABLE weather_snapshots
    ADD COLUMN IF NOT EXISTS current_valid_time             TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS current_temperature_c          DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS current_apparent_temperature_c DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS current_humidity_pct           DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS current_precipitation_mm       DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS current_weather_code           INTEGER,
    ADD COLUMN IF NOT EXISTS current_wind_speed_kmh         DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS current_wind_direction_deg     DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS current_uv_index               DOUBLE PRECISION;
