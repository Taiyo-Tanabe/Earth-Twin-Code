"""
ローカルの学習済みモデル + パネルデータで予測を生成し、Neon に書き込む。

使い方:
  1. .env に DATABASE_URL=postgresql://... を追記
  2. backend/ ディレクトリで実行:
       python push_to_neon.py
"""
import os, json, math, sys, datetime
from pathlib import Path

# ── .env を読み込む ──────────────────────────────────────────
def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_env()

# ── パス設定（ローカル実行用） ───────────────────────────────
BASE          = Path(__file__).parent / "data"
MODEL_PATH    = BASE / "models"
PROCESSED_PATH = BASE / "processed"

import pandas as pd
import numpy as np
import joblib
import sqlalchemy as sa

FEATURE_RISK_DIRECTION = {
    "conflict_onset": +1, "conflict_onset_lag1": +1, "conflict_onset_lag2": +1,
    "conflict_onset_lag3": +1, "conflict_onset_rolling5y": +1, "conflict_duration": +1,
    "neighbor_conflict_avg": +1, "pv_est": -1, "va_est": -1, "rl_est": -1,
    "ge_est": -1, "cc_est": -1, "rq_est": -1, "v2x_polyarchy": -1, "v2x_libdem": -1,
    "gdp_per_capita_log": -1, "gdp_growth": -1, "inflation": +1, "unemployment": +1,
    "population_log": 0, "military_expenditure": +1, "trade_openness": -1,
    "refugees_per_capita": +1, "gdelt_conflict_events": +1,
    "gdelt_tone_avg": -1, "gdelt_goldstein_avg": -1,
}

FEATURE_LABELS = {
    "conflict_onset": "Active conflict", "conflict_onset_lag1": "Conflict last year",
    "conflict_onset_lag2": "Conflict 2 years ago", "conflict_onset_lag3": "Conflict 3 years ago",
    "conflict_onset_rolling5y": "5-year conflict rate", "conflict_duration": "Prolonged conflict",
    "neighbor_conflict_avg": "Conflict spillover", "pv_est": "Political instability",
    "va_est": "Restricted civil liberties", "rl_est": "Weak rule of law",
    "ge_est": "Poor governance", "cc_est": "High corruption",
    "rq_est": "Regulatory failure", "v2x_polyarchy": "Democratic backsliding",
    "v2x_libdem": "Liberal deficit", "gdp_per_capita_log": "Low income level",
    "gdp_growth": "Economic contraction", "inflation": "Inflation pressure",
    "unemployment": "Unemployment", "population_log": "Population factor",
    "military_expenditure": "Militarization", "trade_openness": "Trade exposure",
    "refugees_per_capita": "Refugee pressure", "gdelt_conflict_events": "Recent incidents",
    "gdelt_tone_avg": "Negative media", "gdelt_goldstein_avg": "Political tensions",
}


def _top_features(X, feature_cols, importances, top_n=3):
    medians = X[feature_cols].median()
    stds    = X[feature_cols].std().replace(0, 1)
    results = []
    for _, row in X[feature_cols].iterrows():
        scores = {}
        for col in feature_cols:
            direction = FEATURE_RISK_DIRECTION.get(col, 0)
            if direction == 0:
                continue
            deviation = direction * (row[col] - medians[col]) / stds[col]
            if deviation > 0:
                scores[col] = importances.get(col, 0) * deviation
        top    = sorted(scores, key=scores.get, reverse=True)[:top_n]
        labels = [FEATURE_LABELS.get(c, c) for c in top] or ["Limited data"]
        results.append(labels)
    return results


def _feature_importances(model, feature_cols):
    try:
        if hasattr(model, "calibrated_classifiers_"):
            imp = np.mean([
                cc.estimator.feature_importances_
                for cc in model.calibrated_classifiers_
                if hasattr(cc.estimator, "feature_importances_")
            ], axis=0)
        elif hasattr(model, "feature_importances_"):
            imp = model.feature_importances_
        else:
            imp = np.ones(len(feature_cols)) / len(feature_cols)
    except Exception:
        imp = np.ones(len(feature_cols)) / len(feature_cols)
    return pd.Series(imp, index=feature_cols)


def _predict_for_year(df: pd.DataFrame, pred_year: int) -> pd.DataFrame:
    """指定された pred_year のモデルで予測を生成して返す"""
    suffix = f"_{pred_year}"
    conflict_model_path  = MODEL_PATH / f"conflict_model{suffix}_calibrated.pkl"
    conflict_cols_path   = MODEL_PATH / f"conflict_feature_cols{suffix}.pkl"
    regime_model_path    = MODEL_PATH / f"regime_model{suffix}_calibrated.pkl"
    regime_cols_path     = MODEL_PATH / f"regime_feature_cols{suffix}.pkl"

    # 年別ファイルがなければデフォルトにフォールバック
    if not conflict_model_path.exists():
        conflict_model_path = MODEL_PATH / "conflict_model_calibrated.pkl"
        conflict_cols_path  = MODEL_PATH / "conflict_feature_cols.pkl"
    if not regime_model_path.exists():
        regime_model_path = MODEL_PATH / "regime_model_calibrated.pkl"
        regime_cols_path  = MODEL_PATH / "regime_feature_cols.pkl"

    if not conflict_model_path.exists():
        print(f"[SKIP] No model files for pred_year={pred_year}")
        return pd.DataFrame()

    conflict_model    = joblib.load(conflict_model_path)
    conflict_features = joblib.load(conflict_cols_path)
    regime_model      = joblib.load(regime_model_path)
    regime_features   = joblib.load(regime_cols_path)

    result = df.copy()
    avail_c = [c for c in conflict_features if c in result.columns]
    X_c     = result[avail_c].fillna(result[avail_c].median())
    result["conflict_probability"] = conflict_model.predict_proba(X_c)[:, 1]

    avail_r = [c for c in regime_features if c in result.columns]
    X_r     = result[avail_r].fillna(result[avail_r].median())
    result["regime_change_probability"] = regime_model.predict_proba(X_r)[:, 1]

    result["risk_score"] = (
        result["conflict_probability"] * 0.6
        + result["regime_change_probability"] * 0.4
    )

    imp = _feature_importances(conflict_model, avail_c)
    result["top_features"] = _top_features(X_c, avail_c, imp)
    return result


def run():
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("TIMESCALE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL が設定されていません。.env に追記してください。")
        sys.exit(1)

    print(f"DB: {db_url[:40]}...")

    # パネルデータ読み込み
    latest_path = PROCESSED_PATH / "panel_latest.parquet"
    df = pd.read_parquet(latest_path)
    data_year = int(df["year"].max())

    # 利用可能なモデル年を検出（デフォルト horizon + その前年）
    default_horizon = max(1, datetime.date.today().year - data_year + 1)
    default_pred_year = data_year + default_horizon
    pred_years = sorted({default_pred_year - 1, default_pred_year})
    pred_years = [y for y in pred_years if y > data_year]

    print(f"[OK] panel_latest: {len(df)} countries, data_year={data_year}")
    print(f"[OK] prediction years: {pred_years}")

    connect_args = {"sslmode": "require"} if "neon.tech" in db_url else {}
    engine = sa.create_engine(db_url, connect_args=connect_args)

    insert_sql = sa.text("""
        INSERT INTO risk_predictions
            (time, country_code, model_version,
             conflict_probability, regime_change_probability, risk_score, top_features)
        VALUES
            (:time, :country_code, :model_version,
             :conflict_probability, :regime_change_probability, :risk_score,
             CAST(:top_features AS jsonb))
    """)

    total = 0
    for pred_year in pred_years:
        result = _predict_for_year(df, pred_year)
        if result.empty:
            continue

        model_version = f"xgb-v1-{pred_year}"
        now = datetime.datetime.utcnow()
        rows = []
        for _, row in result.iterrows():
            regime_p = row.get("regime_change_probability", 0)
            if regime_p is None or (isinstance(regime_p, float) and math.isnan(regime_p)):
                regime_p = 0.0
            rows.append({
                "time":                      now,
                "country_code":              row["country_code"],
                "model_version":             model_version,
                "conflict_probability":      float(row["conflict_probability"]),
                "regime_change_probability": float(regime_p),
                "risk_score":                float(row["risk_score"]),
                "top_features":              json.dumps(row.get("top_features", [])),
            })

        with engine.begin() as conn:
            for r in rows:
                conn.execute(insert_sql, r)

        print(f"[OK] {pred_year}: inserted {len(rows)} rows (model_version={model_version})")
        total += len(rows)

    print(f"[OK] total {total} rows inserted into Neon")
    print("  -> reload Vercel to see live data")


if __name__ == "__main__":
    run()
