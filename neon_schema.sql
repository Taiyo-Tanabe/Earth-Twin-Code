-- Run this in the Neon SQL editor before first deployment

-- Prediction results (written by predict pipeline)
CREATE TABLE IF NOT EXISTS risk_predictions (
    time                       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    country_code               VARCHAR(3)   NOT NULL,
    conflict_probability       FLOAT        NOT NULL,
    regime_change_probability  FLOAT,
    risk_score                 FLOAT        NOT NULL,
    top_features               JSONB,
    model_version              VARCHAR(50),
    horizon_months             INTEGER      DEFAULT 12
);

CREATE INDEX IF NOT EXISTS idx_rp_country_time
    ON risk_predictions (country_code, time DESC);

-- Raw signals from always-on collectors (written by stream_processor)
CREATE TABLE IF NOT EXISTS raw_signals (
    id          BIGSERIAL    PRIMARY KEY,
    ingested_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    source      VARCHAR(50)  NOT NULL,
    payload     JSONB        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rs_source_time
    ON raw_signals (source, ingested_at DESC);
