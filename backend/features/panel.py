"""
パネルデータ構築:
UCDP + World Bank + WGI (統治指標) + V-Dem + UNHCR + GDELT を結合し
country × year の特徴量行列を作る
"""
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from ingestion.utils import save_parquet, save_csv

logger = logging.getLogger(__name__)

import os as _os
PROCESSED_PATH = Path(_os.environ.get("DATA_PROCESSED_PATH", "/app/data/processed/"))


def build_lag_features(df: pd.DataFrame, target_col: str, lags: list[int] = [1, 2, 3]) -> pd.DataFrame:
    """時系列ラグ特徴量を追加"""
    df = df.sort_values(["country_code", "year"])
    for lag in lags:
        df[f"{target_col}_lag{lag}"] = df.groupby("country_code")[target_col].shift(lag)
    return df


def build_rolling_features(df: pd.DataFrame, target_col: str, windows: list[int] = [5]) -> pd.DataFrame:
    """ローリング平均を追加"""
    df = df.sort_values(["country_code", "year"])
    for w in windows:
        df[f"{target_col}_rolling{w}y"] = (
            df.groupby("country_code")[target_col]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
        )
    return df


def _join_scout_features(df: pd.DataFrame) -> pd.DataFrame:
    """Neon の scout_features テーブルから Data Scout 発見特徴量を結合する"""
    import os
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return df
    try:
        import sqlalchemy as sa
        connect_args = {"sslmode": "require"} if "neon.tech" in url else {}
        engine = sa.create_engine(url, connect_args=connect_args)
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT country_code, year, feature_col, value FROM scout_features"
            )).fetchall()
        if not rows:
            return df
        scout_df = pd.DataFrame(rows, columns=["country_code", "year", "feature_col", "value"])
        scout_wide = scout_df.pivot_table(
            index=["country_code", "year"],
            columns="feature_col",
            values="value",
            aggfunc="mean",
        ).reset_index()
        scout_wide.columns.name = None
        n_features = len(scout_wide.columns) - 2
        df = df.merge(scout_wide, on=["country_code", "year"], how="left")
        logger.info(f"Scout features merged: {n_features} columns from Neon")
    except Exception as e:
        logger.warning(f"Scout feature join failed (non-fatal): {e}")
    return df


def build_neighbor_features(df: pd.DataFrame, adjacency_path: Path = None) -> pd.DataFrame:
    """隣国の紛争状況を特徴量として追加"""
    if adjacency_path is None or not adjacency_path.exists():
        logger.warning("Adjacency list not found. Skipping neighbor features.")
        df["neighbor_conflict_avg"] = np.nan
        return df

    adj = pd.read_csv(adjacency_path)
    conflict_map = df.set_index(["country_code", "year"])["conflict_onset"].to_dict()

    def get_neighbor_avg(row):
        neighbors = adj[adj["country_code"] == row["country_code"]]["neighbor_code"].tolist()
        values = [conflict_map.get((n, row["year"] - 1), np.nan) for n in neighbors]
        values = [v for v in values if not np.isnan(v)]
        return np.mean(values) if values else np.nan

    df["neighbor_conflict_avg"] = df.apply(get_neighbor_avg, axis=1)
    return df


def build_panel(horizon: int = None) -> pd.DataFrame:
    """
    全データソースを結合して学習用パネルデータを構築。
    返り値: country_code × year の特徴量+ラベル行列
    """
    # 1. 紛争ラベル (ACLED 優先 → UCDP フォールバック)
    acled_path = PROCESSED_PATH / "acled_panel.parquet"
    ucdp_path = PROCESSED_PATH / "ucdp_panel.parquet"
    wb_path = PROCESSED_PATH / "worldbank_features.parquet"

    if acled_path.exists():
        logger.info("Using ACLED conflict labels (primary source)")
        acled = pd.read_parquet(acled_path)
        conflict_df = acled.rename(columns={"acled_conflict": "conflict_onset"})
    elif ucdp_path.exists():
        logger.info("Using UCDP GED conflict labels")
        conflict_df = pd.read_parquet(ucdp_path)
    else:
        logger.warning("No conflict label data found. Run ingestion first.")
        return pd.DataFrame()

    # 2. 経済特徴量 (World Bank) — WB を軸に全国をカバー、UCDP は左結合
    if wb_path.exists():
        wb_df = pd.read_parquet(wb_path)
        df = wb_df.merge(
            conflict_df[["country_code", "year", "conflict_onset"]],
            on=["country_code", "year"],
            how="left",
        )
        df["conflict_onset"] = df["conflict_onset"].fillna(0).astype(int)
    else:
        df = conflict_df.copy()

    # 3. WGI 統治指標 (pv_est, va_est, rl_est, ge_est, cc_est)
    regime_path = PROCESSED_PATH / "regime_labels.parquet"
    if regime_path.exists():
        regime_df = pd.read_parquet(regime_path)
        wgi_cols = [c for c in ["pv_est", "va_est", "rl_est", "ge_est", "cc_est", "rq_est"]
                    if c in regime_df.columns]
        df = df.merge(
            regime_df[["country_code", "year"] + wgi_cols],
            on=["country_code", "year"],
            how="left",
        )

    # 3b. クーデターラベル (Powell-Thyne) — regime_change の正式ラベル
    coup_path = PROCESSED_PATH / "coup_panel.parquet"
    if coup_path.exists():
        coup_df = pd.read_parquet(coup_path)
        df = df.merge(
            coup_df[["country_code", "year", "coup_attempt", "coup_success"]],
            on=["country_code", "year"],
            how="left",
        )
        df["coup_attempt"] = df["coup_attempt"].fillna(0).astype(int)
        df["coup_success"] = df["coup_success"].fillna(0).astype(int)
        # regime_change = coup_attempt (成功・未遂問わず)
        df["regime_change"] = df["coup_attempt"]
        logger.info(f"Coup labels merged: {int(df['coup_attempt'].sum())} country-years with coup attempt")
    else:
        df["regime_change"] = 0
        logger.warning("coup_panel.parquet not found — regime_change set to 0. Run step 3b.")

    # 4. V-Dem 民主主義指標
    vdem_path = PROCESSED_PATH / "vdem_features.parquet"
    if vdem_path.exists():
        vdem_df = pd.read_parquet(vdem_path)
        vdem_cols = [c for c in ["v2x_polyarchy", "v2x_libdem", "v2x_regime", "v2x_corr"]
                     if c in vdem_df.columns]
        df = df.merge(
            vdem_df[["country_code", "year"] + vdem_cols],
            on=["country_code", "year"],
            how="left",
        )
        logger.info(f"V-Dem merged: {vdem_cols}")

    # 5. UNHCR 難民データ
    unhcr_path = PROCESSED_PATH / "unhcr_features.parquet"
    if unhcr_path.exists():
        unhcr_df = pd.read_parquet(unhcr_path)
        # 人口比の難民数を計算
        if "population" in df.columns:
            df = df.merge(
                unhcr_df[["country_code", "year", "refugees_total", "idp_total"]],
                on=["country_code", "year"],
                how="left",
            )
            df["refugees_per_capita"] = df["refugees_total"] / (df["population"] + 1)
        else:
            df = df.merge(
                unhcr_df[["country_code", "year", "refugees_total"]],
                on=["country_code", "year"],
                how="left",
            )
            df["refugees_per_capita"] = df["refugees_total"]
        logger.info("UNHCR data merged")

    # 6. GDELT 紛争シグナル
    gdelt_path = PROCESSED_PATH / "gdelt_annual.parquet"
    if gdelt_path.exists():
        gdelt_df = pd.read_parquet(gdelt_path)
        df = df.merge(
            gdelt_df[["country_code", "year", "gdelt_conflict_events", "gdelt_tone_avg", "gdelt_goldstein_avg"]],
            on=["country_code", "year"],
            how="left",
        )
        logger.info("GDELT data merged")

    # 7. ラグ特徴量
    df = build_lag_features(df, "conflict_onset", lags=[1, 2, 3])
    df = build_rolling_features(df, "conflict_onset", windows=[5])

    # 7b. クーデター履歴ラグ特徴量 (regime_change モデルの重要予測変数)
    if "regime_change" in df.columns:
        df = build_lag_features(df, "regime_change", lags=[1, 2, 3])
        df = build_rolling_features(df, "regime_change", windows=[5])

    # 8. 紛争継続期間
    df = df.sort_values(["country_code", "year"])
    df["conflict_duration"] = (
        df.groupby("country_code")["conflict_onset"]
        .transform(lambda x: x * (x.groupby((x != x.shift()).cumsum()).cumcount() + 1))
    )

    # 9. 近隣効果
    adj_path = PROCESSED_PATH / "adjacency.csv"
    df = build_neighbor_features(df, adj_path)

    # 9b. Data Scout 発見特徴量 (Neon scout_features から結合)
    df = _join_scout_features(df)

    # 10. 予測用パネル保存 (ラベルシフト前の真の最新状態)
    # panel_latest.parquet: predict.py が使用する最新年データ
    df = df.sort_values(["country_code", "year"])
    latest_df = df.groupby("country_code").last().reset_index()
    latest_path = PROCESSED_PATH / "panel_latest.parquet"
    save_parquet(latest_df, latest_path)
    latest_year = latest_df["year"].max()
    logger.info(f"Prediction panel saved: {latest_df.shape}, latest_year={latest_year} → {latest_path}")

    # 11. ラベルシフト: 現在年 − データ最新年 を動的に計算
    import datetime as _dt
    data_year = int(df["year"].max())
    if horizon is None:
        horizon = max(1, _dt.date.today().year - data_year + 1)
    pred_year = data_year + horizon
    logger.info(f"Label shift horizon: -{horizon} (data_year={data_year}, pred_year={pred_year})")

    df["label_conflict"] = df.groupby("country_code")["conflict_onset"].shift(-horizon)
    df["label_regime_change"] = (
        df.groupby("country_code")["regime_change"].shift(-horizon)
        if "regime_change" in df.columns
        else np.nan
    )

    # ラベルがNaN（直近horizon年分）→ 除外
    df = df.dropna(subset=["label_conflict"])

    # 予測年別ファイルと、デフォルトファイルに保存
    save_parquet(df, PROCESSED_PATH / f"panel_features_{pred_year}.parquet")
    if horizon is None or True:  # default file も常に更新
        save_parquet(df, PROCESSED_PATH / "panel_features.parquet")

    n_countries = df["country_code"].nunique()
    pos_rate = df["label_conflict"].mean()
    logger.info(f"Training panel: {df.shape}, {n_countries} countries, conflict_rate={pos_rate:.3f}")
    return df
