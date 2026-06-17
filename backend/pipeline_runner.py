"""
Earth Twin — 完全パイプライン一括実行スクリプト
コンテナ内で実行: python pipeline_runner.py

ステップ:
  1. UCDP GED → 紛争パネル (ACLED_KEY/ACLED_EMAIL 設定時は ACLED 優先)
  2. World Bank WDI → 経済特徴量
  3. WGI (World Governance Indicators) → 統治指標
  3b. Powell-Thyne Coup Dataset → クーデターラベル (政権崩壊の正式定義)
  4. V-Dem → 民主主義指標 (失敗時はスキップ)
  5. UNHCR → 難民・国内避難民データ
  6. 隣国リスト生成
  7. GDELT 年次集計 → 紛争ニュースシグナル
  8. パネル結合 + 特徴量エンジニアリング
  9. XGBoost 学習 (Walk-Forward)
 10. 全国予測 → TimescaleDB
"""
import logging
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("pipeline")

SEP = "=" * 60


def step1_conflict():
    logger.info(SEP)
    import datetime
    end_year = datetime.date.today().year
    from ingestion.acled import fetch_acled_country_year
    acled_df = fetch_acled_country_year(1997, end_year)
    if acled_df is not None and not acled_df.empty:
        logger.info(f"STEP 1: ACLED 武力紛争データ取得 (1997-{end_year})")
        logger.info(f"  → {len(acled_df)} rows, {acled_df['country_code'].nunique()} countries")
        return acled_df
    else:
        logger.info("STEP 1: UCDP GED 紛争データ取得 (v25.1→v24.1フォールバック)")
        from ingestion.ucdp import build_conflict_panel
        df = build_conflict_panel(1989, end_year)
        logger.info(f"  → {len(df)} rows, {df['country_code'].nunique()} countries")
        pse = df[df['country_code'] == 'PSE']
        pse_conf = pse[pse['conflict_onset'] == 1]['year'].tolist()
        logger.info(f"  → Palestine conflict years: {pse_conf[-5:]}")
        return df


def step2_worldbank():
    logger.info(SEP)
    logger.info("STEP 2: World Bank WDI 経済指標取得")
    from ingestion.worldbank import fetch_worldbank
    df = fetch_worldbank()
    logger.info(f"  → {len(df)} rows, {df['country_code'].nunique()} countries")
    return df


def step3_wgi():
    logger.info(SEP)
    logger.info("STEP 3: World Governance Indicators (WGI) 取得")
    from ingestion.polity import download_powell_thyne_coups
    df = download_powell_thyne_coups()
    logger.info(f"  → {len(df)} rows")
    return df


def step3b_coups():
    logger.info(SEP)
    logger.info("STEP 3b: Powell-Thyne クーデターデータ取得 (政権崩壊の正式ラベル)")
    import datetime
    end_year = datetime.date.today().year
    from ingestion.powell_thyne import build_coup_panel
    df = build_coup_panel(1950, end_year)
    n = int(df['coup_attempt'].sum())
    logger.info(f"  → {len(df)} country-years, {n} coup attempts")
    return df


def step4_vdem():
    logger.info(SEP)
    logger.info("STEP 4: V-Dem 民主主義指標取得 (失敗時スキップ)")
    import datetime
    end_year = datetime.date.today().year
    try:
        from ingestion.vdem import fetch_vdem
        df = fetch_vdem(1990, end_year)
        if df.empty:
            logger.warning("  → V-Dem: データ取得失敗 (スキップ)")
        else:
            logger.info(f"  → {len(df)} rows, {df['country_code'].nunique()} countries")
        return df
    except Exception as e:
        logger.warning(f"  → V-Dem スキップ: {e}")
        return None


def step5_unhcr():
    logger.info(SEP)
    logger.info("STEP 5: UNHCR 難民・避難民データ取得")
    import datetime
    end_year = datetime.date.today().year
    try:
        from ingestion.unhcr import fetch_unhcr
        df = fetch_unhcr(2000, end_year)
        logger.info(f"  → {len(df)} rows, {df['country_code'].nunique()} countries")
        return df
    except Exception as e:
        logger.warning(f"  → UNHCR スキップ: {e}")
        return None


def step6_adjacency():
    logger.info(SEP)
    logger.info("STEP 6: 隣国リスト生成")
    from ingestion.adjacency import build_adjacency
    df = build_adjacency()
    logger.info(f"  → {len(df)} 国境ペア, {df['country_code'].nunique()} countries")
    return df


def step7_gdelt():
    logger.info(SEP)
    logger.info("STEP 7: GDELT 年次紛争シグナル集計 (2000-2024, 月次サンプリング)")
    try:
        from ingestion.gdelt import build_monthly_gdelt
        df = build_monthly_gdelt(2000, 2024)
        if df is not None and not df.empty:
            logger.info(f"  → {len(df)} country-year records, {df['country_code'].nunique()} countries")
        else:
            logger.warning("  → GDELT: データなし (スキップ)")
        return df
    except Exception as e:
        logger.warning(f"  → GDELT スキップ: {e}")
        return None


def step8_features():
    logger.info(SEP)
    logger.info("STEP 8: パネルデータ結合 + 特徴量エンジニアリング")
    from features.panel import build_panel
    df = build_panel()
    logger.info(f"  → Training panel: {df.shape}")
    logger.info(f"  → 紛争ラベル陽性率: {df['label_conflict'].mean():.3f}")
    # 主要国のconflict_onsetを確認
    for cc in ['UKR', 'PSE', 'SYR', 'AFG']:
        row = df[df['country_code'] == cc]
        if not row.empty:
            latest = row.iloc[-1]
            logger.info(f"  → {cc}: conflict_onset={latest.get('conflict_onset', '?')}, lag1={latest.get('conflict_onset_lag1', '?'):.0f}")
    return df


def step9_train():
    logger.info(SEP)
    logger.info("STEP 9: XGBoost 学習 (Walk-Forward Validation)")
    from models.train import train_conflict_model, train_regime_model

    logger.info("  [9a] 紛争モデル学習...")
    conflict_metrics = train_conflict_model()
    auc = conflict_metrics.get('roc_auc', None)
    brier = conflict_metrics.get('brier_score', None)
    logger.info(f"  → Conflict ROC-AUC: {auc:.3f}" if auc else "  → Conflict: N/A")
    logger.info(f"  → Conflict Brier:   {brier:.3f}" if brier else "")

    logger.info("  [9b] 政権崩壊モデル学習...")
    regime_metrics = train_regime_model()
    rauc = regime_metrics.get("roc_auc", None)
    logger.info(f"  → Regime ROC-AUC: {rauc:.3f}" if rauc else "  → Regime model skipped")

    return conflict_metrics, regime_metrics


def step10_predict():
    logger.info(SEP)
    logger.info("STEP 10: 全国リスクスコア算出 → TimescaleDB")
    from models.predict import predict_all_countries
    df = predict_all_countries()
    logger.info(f"  → {len(df)} countries predicted")

    logger.info("  Top 10 conflict risk:")
    top = df.nlargest(10, "conflict_probability")
    for _, row in top.iterrows():
        logger.info(f"    {row['country_code']}: {row['conflict_probability']:.3f}")

    # 重要国の確認
    logger.info("  Key country check:")
    for cc in ['UKR', 'RUS', 'PSE', 'SYR', 'AFG', 'USA', 'JPN']:
        row = df[df['country_code'] == cc]
        if not row.empty:
            p = row.iloc[0]['conflict_probability']
            logger.info(f"    {cc}: {p:.3f} ({p*100:.1f}%)")

    return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-step", type=int, default=1, help="開始ステップ (1-10)")
    parser.add_argument("--to-step", type=int, default=10, help="終了ステップ (1-10)")
    parser.add_argument("--skip-gdelt", action="store_true", help="GDELT集計をスキップ (時間短縮)")
    args = parser.parse_args()

    # ステップ番号 → 関数のマッピング (3bは3.5として扱う)
    numbered_steps = [
        (1,   step1_conflict),
        (2,   step2_worldbank),
        (3,   step3_wgi),
        (3.5, step3b_coups),
        (4,   step4_vdem),
        (5,   step5_unhcr),
        (6,   step6_adjacency),
        (7,   step7_gdelt),
        (8,   step8_features),
        (9,   step9_train),
        (10,  step10_predict),
    ]

    for step_num, step_fn in numbered_steps:
        int_num = int(step_num)
        if int_num < args.from_step or int_num > args.to_step:
            continue
        if int_num == 7 and args.skip_gdelt:
            logger.info("STEP 7: GDELT スキップ (--skip-gdelt)")
            continue
        try:
            step_fn()
        except Exception as e:
            logger.error(f"STEP {step_num} 失敗: {e}", exc_info=True)
            logger.error(f"修正後は --from-step {int_num} で再開できます")
            sys.exit(1)

    logger.info(SEP)
    logger.info("✅ パイプライン完了")
