-- TimescaleDB 拡張
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 生特徴量テーブル (country × year)
CREATE TABLE IF NOT EXISTS country_features (
    time        TIMESTAMPTZ NOT NULL,
    country_code CHAR(3)    NOT NULL,
    -- 紛争ラベル
    conflict_onset          SMALLINT,  -- 0/1 UCDP ACD
    regime_change           SMALLINT,  -- 0/1 coup or irregular transition
    -- 経済
    gdp_per_capita_log      FLOAT,
    gdp_growth              FLOAT,
    inflation               FLOAT,
    unemployment            FLOAT,
    -- 政治
    polity2                 FLOAT,     -- -10 to +10
    polity_change           FLOAT,     -- YoY change
    -- 紛争履歴
    conflict_lag1           SMALLINT,
    conflict_lag2           SMALLINT,
    conflict_lag3           SMALLINT,
    conflict_rolling5y      FLOAT,
    conflict_duration       INT,
    -- 近隣効果
    neighbor_conflict_avg   FLOAT,
    -- 構造的
    population_log          FLOAT,
    ethnic_fractionalization FLOAT,
    -- GDELT シグナル
    gdelt_event_count       FLOAT,
    gdelt_tone_avg          FLOAT,
    gdelt_instability_idx   FLOAT,
    PRIMARY KEY (time, country_code)
);

-- TimescaleDB ハイパーテーブル化
SELECT create_hypertable('country_features', 'time', if_not_exists => TRUE);

-- モデル予測結果テーブル
CREATE TABLE IF NOT EXISTS risk_predictions (
    time                    TIMESTAMPTZ NOT NULL,
    country_code            CHAR(3)     NOT NULL,
    model_version           TEXT        NOT NULL,
    horizon_months          INT         NOT NULL,
    conflict_probability    FLOAT       NOT NULL,
    regime_change_probability FLOAT     NOT NULL,
    risk_score              FLOAT       NOT NULL,
    top_features            JSONB,
    PRIMARY KEY (time, country_code, model_version, horizon_months)
);

SELECT create_hypertable('risk_predictions', 'time', if_not_exists => TRUE);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_features_country ON country_features (country_code, time DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_country ON risk_predictions (country_code, time DESC);
