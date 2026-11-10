-- brWeather schema. Shared by data-pipeline (writes) and backend (reads, alerts).
-- All timestamps are UTC (timestamptz).

CREATE TABLE IF NOT EXISTS stations (
    id            BIGINT PRIMARY KEY,          -- OpenAQ location id
    name          TEXT NOT NULL,
    provider      TEXT,
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL,
    pm25_sensor_id BIGINT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen    TIMESTAMPTZ,
    last_seen     TIMESTAMPTZ
);

-- Raw payloads kept for traceability (F00)
CREATE TABLE IF NOT EXISTS raw_payloads (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,
    request     TEXT NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload     JSONB NOT NULL,
    run_id      BIGINT
);

-- Clean hourly air measurements (observed or modelled)
CREATE TABLE IF NOT EXISTS air_measurements (
    source        TEXT NOT NULL,               -- openaq | open-meteo-aq
    station_id    BIGINT REFERENCES stations(id),
    parameter     TEXT NOT NULL,               -- pm25, pm10, no2...
    measured_at   TIMESTAMPTZ NOT NULL,        -- start of the hour
    value         DOUBLE PRECISION,            -- NULL when missing, never 0
    unit          TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('observed', 'modelled')),
    quality_flag  TEXT NOT NULL DEFAULT 'ok',  -- ok | out_of_range | flatline | suspect
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source, station_id, parameter, measured_at)
);

-- Weather snapshots (F09); each fetch keeps its own forecast so evaluation never uses overwritten data
CREATE TABLE IF NOT EXISTS weather_snapshots (
    snapshot_id   BIGSERIAL PRIMARY KEY,
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    source        TEXT NOT NULL DEFAULT 'open-meteo'
);

CREATE TABLE IF NOT EXISTS weather_hourly (
    snapshot_id           BIGINT REFERENCES weather_snapshots(snapshot_id) ON DELETE CASCADE,
    valid_time            TIMESTAMPTZ NOT NULL,
    temperature_c         DOUBLE PRECISION,
    apparent_temperature_c DOUBLE PRECISION,
    humidity_pct          DOUBLE PRECISION,
    precipitation_mm      DOUBLE PRECISION,
    precipitation_prob_pct DOUBLE PRECISION,
    weather_code          INTEGER,
    wind_speed_kmh        DOUBLE PRECISION,
    wind_direction_deg    DOUBLE PRECISION,
    uv_index              DOUBLE PRECISION,
    boundary_layer_height_m DOUBLE PRECISION,
    PRIMARY KEY (snapshot_id, valid_time)
);

CREATE TABLE IF NOT EXISTS weather_daily (
    snapshot_id        BIGINT REFERENCES weather_snapshots(snapshot_id) ON DELETE CASCADE,
    day                DATE NOT NULL,
    temperature_max_c  DOUBLE PRECISION,
    temperature_min_c  DOUBLE PRECISION,
    precipitation_sum_mm DOUBLE PRECISION,
    weather_code       INTEGER,
    sunrise            TIMESTAMPTZ,
    sunset             TIMESTAMPTZ,
    PRIMARY KEY (snapshot_id, day)
);

-- Reliability score per station (F08)
CREATE TABLE IF NOT EXISTS reliability_scores (
    station_id   BIGINT REFERENCES stations(id),
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    level        TEXT NOT NULL CHECK (level IN ('high', 'medium', 'low')),
    reasons      JSONB NOT NULL DEFAULT '[]',
    PRIMARY KEY (station_id, computed_at)
);

-- Forecasts (F03); never overwritten so they can be compared to observations later
CREATE TABLE IF NOT EXISTS pm25_forecasts (
    station_id     BIGINT REFERENCES stations(id),
    issued_at      TIMESTAMPTZ NOT NULL,
    target_time    TIMESTAMPTZ NOT NULL,
    value          DOUBLE PRECISION NOT NULL,
    model_version  TEXT NOT NULL,
    PRIMARY KEY (station_id, issued_at, target_time)
);

-- Anomalies (F04)
CREATE TABLE IF NOT EXISTS anomalies (
    id           BIGSERIAL PRIMARY KEY,
    station_id   BIGINT REFERENCES stations(id),
    start_time   TIMESTAMPTZ NOT NULL,
    end_time     TIMESTAMPTZ NOT NULL,
    category     TEXT NOT NULL CHECK (category IN ('data', 'environment', 'needs_review')),
    description  TEXT NOT NULL,
    detected_by  TEXT NOT NULL,
    reviewed     BOOLEAN NOT NULL DEFAULT FALSE
);

-- Anonymous devices and alerts (F07a, F11)
CREATE TABLE IF NOT EXISTS devices (
    device_id   UUID PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    push_token  TEXT                              -- F07b, optional
);

CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id          BIGSERIAL PRIMARY KEY,
    device_id   UUID REFERENCES devices(device_id) ON DELETE CASCADE,
    label       TEXT,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    pm25_threshold DOUBLE PRECISION NOT NULL,
    use_forecast BOOLEAN NOT NULL DEFAULT TRUE,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS alert_events (
    id               BIGSERIAL PRIMARY KEY,
    subscription_id  BIGINT REFERENCES alert_subscriptions(id) ON DELETE CASCADE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    station_id       BIGINT REFERENCES stations(id),
    value            DOUBLE PRECISION,
    reason           TEXT NOT NULL,
    suppressed       BOOLEAN NOT NULL DEFAULT FALSE   -- duplicate within 60 minutes
);

-- Pipeline run log (F00): success rate and debugging
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id      BIGSERIAL PRIMARY KEY,
    job         TEXT NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status      TEXT NOT NULL DEFAULT 'running',  -- running | success | failed
    records     INTEGER NOT NULL DEFAULT 0,
    error       TEXT
);
