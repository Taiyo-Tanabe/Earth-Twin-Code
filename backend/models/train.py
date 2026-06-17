"""
XGBoost 学習スクリプト (Walk-Forward Validation)
- 紛争確率モデル: label_conflict
- 政権崩壊確率モデル: label_regime_change
- 評価: Brier Score + ROC-AUC + Calibration
- モデル管理: MLflow
"""
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss
from pathlib import Path
try:
    import mlflow
    import mlflow.xgboost
    _MLFLOW = True
except Exception:
    _MLFLOW = False
import logging
import os

logger = logging.getLogger(__name__)

PROCESSED_PATH = Path(os.environ.get("DATA_PROCESSED_PATH", "/app/data/processed/"))
MODEL_PATH = Path(os.environ.get("DATA_MODELS_PATH", "/app/data/models/"))

FEATURE_COLS = [
    # 経済・社会指標
    "gdp_per_capita_log",
    "gdp_growth",
    "inflation",
    "unemployment",
    "population_log",
    "military_expenditure",
    "trade_openness",
    # 統治・政治指標 (WGI)
    "pv_est",
    "va_est",
    "rl_est",
    "ge_est",
    "cc_est",
    # V-Dem 民主主義指標
    "v2x_polyarchy",
    "v2x_libdem",
    # 紛争履歴
    "conflict_onset",
    "conflict_onset_lag1",
    "conflict_onset_lag2",
    "conflict_onset_lag3",
    "conflict_onset_rolling5y",
    "conflict_duration",
    # 近隣効果
    "neighbor_conflict_avg",
    # 人道指標
    "refugees_per_capita",
    # GDELTニュースシグナル
    "gdelt_conflict_events",
    "gdelt_tone_avg",
    "gdelt_goldstein_avg",
]

REGIME_FEATURE_COLS = FEATURE_COLS + [
    # クーデター履歴 (クーデターモデル専用の最重要予測変数)
    "regime_change",
    "regime_change_lag1",
    "regime_change_lag2",
    "regime_change_lag3",
    "regime_change_rolling5y",
]

_LABEL_AND_ID_COLS = {
    "country_code", "year",
    "conflict_onset", "regime_change", "coup_attempt", "coup_success",
    "label_conflict", "label_regime_change",
    "refugees_total", "idp_total",
}


def _extend_with_scout_cols(df: pd.DataFrame, base_cols: list) -> list:
    """パネルに存在する Scout 発見列（base_cols 以外の数値列）を追加する"""
    exclude = set(base_cols) | _LABEL_AND_ID_COLS
    scout_cols = [
        c for c in df.select_dtypes(include="number").columns
        if c not in exclude and df[c].notna().sum() >= 50
    ]
    if scout_cols:
        logger.info(f"Scout features added to training: {scout_cols}")
    return base_cols + scout_cols


XGB_PARAMS = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "scale_pos_weight": 3,  # 紛争モデル用
    "use_label_encoder": False,
    "eval_metric": "logloss",
    "random_state": 42,
}


def walk_forward_validation(
    df: pd.DataFrame,
    label_col: str,
    feature_cols: list = None,
    train_start: int = 1990,
    val_start: int = 2010,
    end_year: int = 2022,
) -> dict:
    """
    Walk-Forward Validation で予測精度を評価。
    各年: train on [train_start, val_year-1], predict val_year
    """
    all_preds = []
    all_labels = []

    for val_year in range(val_start, end_year + 1):
        train_df = df[df["year"] < val_year].copy()
        val_df = df[df["year"] == val_year].copy()

        if len(train_df) < 100 or len(val_df) == 0:
            continue

        _cols = feature_cols if feature_cols else [c for c in FEATURE_COLS if c in train_df.columns]
        _cols = [c for c in _cols if c in train_df.columns]
        X_train = train_df[_cols].fillna(train_df[_cols].median())
        y_train = train_df[label_col].fillna(0).astype(int)
        X_val = val_df[_cols].fillna(train_df[_cols].median())
        y_val = val_df[label_col].fillna(0).astype(int)

        model = xgb.XGBClassifier(**XGB_PARAMS)
        model.fit(X_train, y_train, verbose=False)

        preds = model.predict_proba(X_val)[:, 1]
        all_preds.extend(preds)
        all_labels.extend(y_val.tolist())

    if not all_preds:
        return {}

    roc_auc = roc_auc_score(all_labels, all_preds)
    brier = brier_score_loss(all_labels, all_preds)
    logger.info(f"Walk-forward {label_col}: ROC-AUC={roc_auc:.3f}, Brier={brier:.3f}")
    return {"roc_auc": roc_auc, "brier_score": brier}


def train_conflict_model() -> dict:
    """紛争確率モデルを学習し、MLflowに記録"""
    panel_path = PROCESSED_PATH / "panel_features.parquet"
    if not panel_path.exists():
        logger.error("Panel data not found. Run build_panel() first.")
        return {}

    df = pd.read_parquet(panel_path)
    feature_cols = _extend_with_scout_cols(df, [c for c in FEATURE_COLS if c in df.columns])
    last_year = int(df["year"].max())
    metrics = walk_forward_validation(df, "label_conflict", feature_cols=feature_cols, end_year=last_year)

    # 全データで最終モデルを学習
    X = df[feature_cols].fillna(df[feature_cols].median())
    y = df["label_conflict"].fillna(0).astype(int)

    final_model = xgb.XGBClassifier(**XGB_PARAMS)
    final_model.fit(X, y, verbose=False)

    # Platt Scaling でキャリブレーション (sklearn 1.4+ は cv="prefit" 非対応)
    calibrated = CalibratedClassifierCV(final_model, method="sigmoid", cv=5)
    calibrated.fit(X, y)

    from ingestion.utils import save_joblib
    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    save_joblib(calibrated, MODEL_PATH / "conflict_model_calibrated.pkl")
    save_joblib(feature_cols, MODEL_PATH / "conflict_feature_cols.pkl")
    logger.info("Conflict model saved locally.")

    mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    if mlflow_uri:
        try:
            mlflow.set_tracking_uri(mlflow_uri)
            with mlflow.start_run(run_name="conflict_model"):
                mlflow.log_params(XGB_PARAMS)
                mlflow.log_metrics(metrics)
                mlflow.xgboost.log_model(final_model, "conflict_xgb")
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")

    return metrics


def train_regime_model() -> dict:
    """政権崩壊確率モデルを学習"""
    panel_path = PROCESSED_PATH / "panel_features.parquet"
    if not panel_path.exists():
        return {}

    df = pd.read_parquet(panel_path)
    if "label_regime_change" not in df.columns or df["label_regime_change"].isna().all():
        logger.warning("No regime change labels. Skipping.")
        return {}

    df = df.dropna(subset=["label_regime_change"])
    if df["label_regime_change"].sum() < 10:
        logger.warning(f"Too few regime change events ({int(df['label_regime_change'].sum())}). Skipping.")
        return {}

    # クーデターは陽性率~0.75% → scale_pos_weight を動的計算
    pos = df["label_regime_change"].sum()
    neg = len(df) - pos
    spw = max(int(neg / pos), 10)
    logger.info(f"Regime model: pos={int(pos)}, neg={int(neg)}, scale_pos_weight={spw}")

    regime_params = {**XGB_PARAMS, "scale_pos_weight": spw, "min_child_weight": 1}

    feature_cols = _extend_with_scout_cols(df, [c for c in REGIME_FEATURE_COLS if c in df.columns])
    last_year = int(df["year"].max())
    metrics = walk_forward_validation(df, "label_regime_change", feature_cols=feature_cols, end_year=last_year)

    logger.info(f"Regime model features ({len(feature_cols)}): {[f for f in feature_cols if 'regime' in f]}")
    X = df[feature_cols].fillna(df[feature_cols].median())
    y = df["label_regime_change"].astype(int)

    final_model = xgb.XGBClassifier(**regime_params)
    final_model.fit(X, y, verbose=False)

    # クーデターは陽性率0.75%のため CalibratedClassifierCV は使わない
    # (sigmoid calibration が全予測を0近辺に圧縮してしまう)
    # XGBoost の scale_pos_weight で確率を直接出力する
    from ingestion.utils import save_joblib
    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    save_joblib(final_model, MODEL_PATH / "regime_model_calibrated.pkl")
    save_joblib(feature_cols, MODEL_PATH / "regime_feature_cols.pkl")
    logger.info(f"Regime model saved. Features used: {len(feature_cols)}")

    mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    if mlflow_uri:
        try:
            mlflow.set_tracking_uri(mlflow_uri)
            with mlflow.start_run(run_name="regime_change_model"):
                mlflow.log_params(XGB_PARAMS)
                mlflow.log_metrics(metrics)
        except Exception as e:
            logger.warning(f"MLflow logging skipped: {e}")

    return metrics
