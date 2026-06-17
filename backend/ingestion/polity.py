"""
World Governance Indicators (WGI) — World Bank API v2
全6指標を取得し、政治不安定ラベルと統治スコアを生成する。

指標:
- PV.EST: Political Stability and Absence of Violence/Terrorism
- VA.EST: Voice and Accountability
- RL.EST: Rule of Law
- GE.EST: Government Effectiveness
- CC.EST: Control of Corruption
- RQ.EST: Regulatory Quality
"""
import requests
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from ingestion.utils import save_parquet

logger = logging.getLogger(__name__)
PROCESSED_PATH = Path("/app/data/processed")

WB_API = "https://api.worldbank.org/v2/country/all/indicator/{code}"

WGI_CODE_TO_COL = {
    "GOV_WGI_PV.EST": "pv_est",
    "GOV_WGI_VA.EST": "va_est",
    "GOV_WGI_RL.EST": "rl_est",
    "GOV_WGI_GE.EST": "ge_est",
    "GOV_WGI_CC.EST": "cc_est",
    "GOV_WGI_RQ.EST": "rq_est",
}


def _fetch_wb_indicator(code: str, start_year: int, end_year: int) -> list:
    """World Bank API v2 で指標を全ページ取得"""
    url = WB_API.format(code=code)
    all_records = []
    page = 1
    while True:
        params = {
            "format": "json",
            "per_page": 2000,
            "date": f"{start_year}:{end_year}",
            "page": page,
        }
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"WB API {code} page={page}: {e}")
            break

        if not isinstance(data, list) or len(data) < 2:
            logger.warning(f"WB API {code}: unexpected format: {str(data)[:100]}")
            break

        meta = data[0]
        records = data[1] or []
        all_records.extend(records)

        total_pages = int(meta.get("pages", 1))
        if page >= total_pages:
            break
        page += 1

    return all_records


def download_powell_thyne_coups(start_year: int = 1996, end_year: int = 2024) -> pd.DataFrame:
    """World Bank WGI API v2 から統治指標を取得し、政治不安定ラベルを生成する。"""
    logger.info("Fetching WGI indicators from World Bank API v2...")

    all_dfs = []
    for wgi_code, col_name in WGI_CODE_TO_COL.items():
        records = _fetch_wb_indicator(wgi_code, start_year, end_year)
        if not records:
            logger.warning(f"  {wgi_code}: no data")
            continue

        rows = []
        for r in records:
            if r.get("value") is None:
                continue
            iso3 = r.get("countryiso3code", "")
            if not iso3 or len(iso3) != 3:
                continue
            try:
                rows.append({
                    "country_code": iso3.upper(),
                    "year": int(r["date"]),
                    col_name: float(r["value"]),
                })
            except (ValueError, KeyError):
                continue

        if not rows:
            logger.warning(f"  {wgi_code}: no valid rows after parsing")
            continue

        df = pd.DataFrame(rows)
        logger.info(f"  {wgi_code}: {len(df)} rows, {df['country_code'].nunique()} countries")
        all_dfs.append(df)

    if not all_dfs:
        logger.warning("No WGI data fetched — returning empty DataFrame")
        return _empty()

    merged = all_dfs[0]
    for df in all_dfs[1:]:
        merged = merged.merge(df, on=["country_code", "year"], how="outer")

    merged = merged.sort_values(["country_code", "year"]).reset_index(drop=True)

    if "pv_est" in merged.columns:
        merged["pv_est_delta"] = merged.groupby("country_code")["pv_est"].diff()
        merged["regime_change"] = (
            (merged["pv_est"] < -1.0) & (merged["pv_est_delta"] < -0.3)
        ).astype(int)
        merged["regime_change"] = merged["regime_change"].fillna(0).astype(int)
        n_events = int(merged["regime_change"].sum())
        logger.info(f"Political instability events: {n_events}")
    else:
        merged["regime_change"] = 0

    dest = PROCESSED_PATH / "regime_labels.parquet"
    save_parquet(merged, dest)
    logger.info(f"WGI saved: {merged.shape} → {dest}")
    return merged


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["country_code", "year", "pv_est", "regime_change"])
