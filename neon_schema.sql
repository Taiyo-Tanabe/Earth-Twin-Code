-- Run this in the Neon SQL editor before first deployment

CREATE TABLE IF NOT EXISTS risk_predictions (
    time        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    country_code VARCHAR(3)  NOT NULL,
    conflict_probability       FLOAT NOT NULL,
    regime_change_probability  FLOAT,
    risk_score                 FLOAT NOT NULL,
    top_features               JSONB,
    model_version              VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_rp_country_time
    ON risk_predictions (country_code, time DESC);
