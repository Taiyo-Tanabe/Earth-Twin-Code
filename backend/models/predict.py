"""
全国リスクスコア算出 & TimescaleDB への書き込み
"""
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

MODEL_PATH = Path("/app/data/models/")
PROCESSED_PATH = Path("/app/data/processed/")

# 各特徴量が高い値のとき、リスクが増加(+1)か減少(-1)かの方向性
FEATURE_RISK_DIRECTION = {
    "conflict_onset": +1,
    "conflict_onset_lag1": +1,
    "conflict_onset_lag2": +1,
    "conflict_onset_lag3": +1,
    "conflict_onset_rolling5y": +1,
    "conflict_duration": +1,
    "neighbor_conflict_avg": +1,
    "pv_est": -1,
    "va_est": -1,
    "rl_est": -1,
    "ge_est": -1,
    "cc_est": -1,
    "rq_est": -1,
    "v2x_polyarchy": -1,
    "v2x_libdem": -1,
    "gdp_per_capita_log": -1,
    "gdp_growth": -1,
    "inflation": +1,
    "unemployment": +1,
    "population_log": 0,
    "military_expenditure": +1,
    "trade_openness": -1,
    "refugees_per_capita": +1,
    "gdelt_conflict_events": +1,
    "gdelt_tone_avg": -1,
    "gdelt_goldstein_avg": -1,
}

FEATURE_LABELS = {
    "conflict_onset": "Active conflict",
    "conflict_onset_lag1": "Conflict last year",
    "conflict_onset_lag2": "Conflict 2 years ago",
    "conflict_onset_lag3": "Conflict 3 years ago",
    "conflict_onset_rolling5y": "5-year conflict rate",
    "conflict_duration": "Prolonged conflict",
    "neighbor_conflict_avg": "Conflict spillover",
    "pv_est": "Political instability",
    "va_est": "Restricted civil liberties",
    "rl_est": "Weak rule of law",
    "ge_est": "Poor governance",
    "cc_est": "High corruption",
    "rq_est": "Regulatory failure",
    "v2x_polyarchy": "Democratic backsliding",
    "v2x_libdem": "Liberal deficit",
    "gdp_per_capita_log": "Low income level",
    "gdp_growth": "Economic contraction",
    "inflation": "Inflation pressure",
    "unemployment": "Unemployment",
    "population_log": "Population factor",
    "military_expenditure": "Militarization",
    "trade_openness": "Trade exposure",
    "refugees_per_capita": "Refugee pressure",
    "gdelt_conflict_events": "Recent incidents",
    "gdelt_tone_avg": "Negative media",
    "gdelt_goldstein_avg": "Political tensions",
}


def _get_feature_importances(model, feature_cols: list[str]) -> pd.Series:
    """CalibratedClassifierCV または XGBClassifier から特徴量重要度を取得"""
    try:
        # CalibratedClassifierCV の場合
        if hasattr(model, "calibrated_classifiers_"):
            importances = np.mean([
                cc.estimator.feature_importances_
                for cc in model.calibrated_classifiers_
                if hasattr(cc.estimator, "feature_importances_")
            ], axis=0)
        elif hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        else:
            return pd.Series(np.ones(len(feature_cols)) / len(feature_cols), index=feature_cols)
        return pd.Series(importances, index=feature_cols)
    except Exception as e:
        logger.warning(f"Could not get feature importances: {e}")
        return pd.Series(np.ones(len(feature_cols)) / len(feature_cols), index=feature_cols)


def _top_features_per_country(
    X: pd.DataFrame,
    feature_cols: list[str],
    importances: pd.Series,
    top_n: int = 3,
) -> list[list[str]]:
    """各国のリスク寄与度上位 top_n 特徴量をラベルで返す"""
    # グローバル中央値・標準偏差
    medians = X[feature_cols].median()
    stds = X[feature_cols].std().replace(0, 1)

    results = []
    for _, row in X[feature_cols].iterrows():
        scores = {}
        for col in feature_cols:
            direction = FEATURE_RISK_DIRECTION.get(col, 0)
            if direction == 0:
                continue
            imp = importances.get(col, 0)
            deviation = direction * (row[col] - medians[col]) / stds[col]
            if deviation > 0:  # この特徴量がリスクを押し上げている
                scores[col] = imp * deviation

        top = sorted(scores, key=scores.get, reverse=True)[:top_n]
        labels = [FEATURE_LABELS.get(c, c) for c in top]
        if not labels:
            labels = ["Limited data"]
        results.append(labels)
    return results


def predict_all_countries(model_version: str = "xgb-v1") -> pd.DataFrame:
    """
    学習済みモデルで全国の最新リスクスコアを算出し、
    TimescaleDB の risk_predictions に書き込む。
    """
    conflict_model_path = MODEL_PATH / "conflict_model_calibrated.pkl"
    regime_model_path = MODEL_PATH / "regime_model_calibrated.pkl"

    if not conflict_model_path.exists():
        logger.error("Conflict model not found. Run train_conflict_model() first.")
        return pd.DataFrame()

    conflict_model = joblib.load(conflict_model_path)
    conflict_features = joblib.load(MODEL_PATH / "conflict_feature_cols.pkl")

    regime_model = None
    regime_features = []
    if regime_model_path.exists():
        regime_model = joblib.load(regime_model_path)
        regime_features = joblib.load(MODEL_PATH / "regime_feature_cols.pkl")

    # 最新年の特徴量
    panel_latest_path = PROCESSED_PATH / "panel_latest.parquet"
    panel_path = PROCESSED_PATH / "panel_features.parquet"

    if panel_latest_path.exists():
        latest = pd.read_parquet(panel_latest_path)
        latest_year = latest["year"].max()
        logger.info(f"Using prediction panel (panel_latest): latest year = {latest_year}")
    else:
        df = pd.read_parquet(panel_path)
        latest_year = df["year"].max()
        latest = df[df["year"] == latest_year].copy()
        logger.warning(f"panel_latest.parquet not found. Using training panel year={latest_year}")

    # 特徴量行列 (パネルに存在する列のみ使用)
    available_conflict_features = [c for c in conflict_features if c in latest.columns]
    if len(available_conflict_features) < len(conflict_features):
        missing = set(conflict_features) - set(available_conflict_features)
        logger.warning(f"Features missing from panel (median impute): {missing}")
    X_conflict = latest[available_conflict_features].fillna(latest[available_conflict_features].median())
    conflict_proba = conflict_model.predict_proba(X_conflict)[:, 1]
    latest["conflict_probability"] = conflict_proba

    if regime_model:
        available_regime_features = [c for c in regime_features if c in latest.columns]
        X_regime = latest[available_regime_features].fillna(latest[available_regime_features].median())
        latest["regime_change_probability"] = regime_model.predict_proba(X_regime)[:, 1]
    else:
        latest["regime_change_probability"] = np.nan

    # 総合リスクスコア (加重平均)
    w_conflict, w_regime = 0.6, 0.4
    latest["risk_score"] = (
        latest["conflict_probability"] * w_conflict
        + latest["regime_change_probability"].fillna(0) * w_regime
    )

    # 国ごとのリスク寄与特徴量 (実際の feature importance × 偏差)
    importances = _get_feature_importances(conflict_model, available_conflict_features)
    latest["top_features"] = _top_features_per_country(X_conflict, available_conflict_features, importances)

    # TimescaleDB に書き込み
    _write_to_db(latest, model_version)

    return latest[["country_code", "conflict_probability", "regime_change_probability", "risk_score"]]


def _write_to_db(df: pd.DataFrame, model_version: str):
    """TimescaleDB の risk_predictions テーブルに書き込み"""
    import sqlalchemy as sa
    import json, math

    db_url = os.environ.get("TIMESCALE_URL", "postgresql://earthtwin:earthtwin123@timescaledb:5432/earthtwin")
    engine = sa.create_engine(db_url)

    now = datetime.utcnow()
    rows = []
    for _, row in df.iterrows():
        regime_p = row.get("regime_change_probability", 0)
        if regime_p is None or (isinstance(regime_p, float) and math.isnan(regime_p)):
            regime_p = 0.0
        rows.append({
            "time": now,
            "country_code": row["country_code"],
            "model_version": model_version,
            "horizon_months": 12,
            "conflict_probability": float(row["conflict_probability"]),
            "regime_change_probability": float(regime_p),
            "risk_score": float(row["risk_score"]),
            "top_features": json.dumps(row.get("top_features", [])),
        })

    insert_df = pd.DataFrame(rows)
    with engine.begin() as conn:
        for _, r in insert_df.iterrows():
            conn.execute(sa.text("""
                INSERT INTO risk_predictions
                    (time, country_code, model_version, horizon_months,
                     conflict_probability, regime_change_probability, risk_score, top_features)
                VALUES
                    (:time, :country_code, :model_version, :horizon_months,
                     :conflict_probability, :regime_change_probability, :risk_score,
                     CAST(:top_features AS jsonb))
                ON CONFLICT DO NOTHING
            """), r.to_dict())
    logger.info(f"Written {len(rows)} predictions to TimescaleDB")
