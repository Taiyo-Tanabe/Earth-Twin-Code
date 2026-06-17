"""
UNHCR Refugee Data Finder API
- エンドポイント: https://api.unhcr.org/population/v1/population/
- 認証不要、無料
- coa_iso でフィルタして庇護国別データを取得（国別ループ）
"""
import requests
import pandas as pd
import pycountry
from pathlib import Path
from ingestion.utils import save_parquet
import logging
import time

logger = logging.getLogger(__name__)
PROCESSED_PATH = Path("/app/data/processed")

UNHCR_API = "https://api.unhcr.org/population/v1/population/"


def _get_all_iso3() -> list:
    """pycountry から ISO3 コード一覧を取得"""
    return [c.alpha_3 for c in pycountry.countries]


def fetch_unhcr(start_year: int = 2000, end_year: int = 2024) -> pd.DataFrame:
    logger.info(f"Fetching UNHCR population data {start_year}–{end_year} (per-country)...")

    all_items = []
    iso3_codes = _get_all_iso3()
    logger.info(f"  Fetching {len(iso3_codes)} countries...")

    for i, iso3 in enumerate(iso3_codes):
        params = {
            "coa_iso": iso3,
            "yearFrom": start_year,
            "yearTo": end_year,
            "limit": 5000,
            "page": 1,
        }
        try:
            resp = requests.get(UNHCR_API, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if items:
                for item in items:
                    item["_coa_iso"] = iso3
                all_items.extend(items)
        except Exception as e:
            logger.debug(f"  UNHCR {iso3}: {e}")
            continue

        if (i + 1) % 50 == 0:
            logger.info(f"  Progress: {i+1}/{len(iso3_codes)}, records so far: {len(all_items)}")
        time.sleep(0.05)  # rate limit courtesy

    if not all_items:
        logger.warning("No UNHCR records fetched")
        return _empty()

    df = pd.DataFrame(all_items)
    logger.info(f"Raw UNHCR records: {len(df)}, columns: {df.columns.tolist()[:8]}")

    df["country_code"] = df["_coa_iso"].astype(str).str.strip().str.upper()
    df = df[df["country_code"].str.match(r"^[A-Z]{3}$")].copy()

    year_col = "year" if "year" in df.columns else next(
        (c for c in ["Year", "annee"] if c in df.columns), None
    )
    if not year_col:
        logger.warning("No year column found")
        return _empty()

    df["year"] = pd.to_numeric(df[year_col], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)

    def get_numeric(col_candidates):
        for c in col_candidates:
            if c in df.columns:
                return pd.to_numeric(df[c], errors="coerce").fillna(0)
        return pd.Series(0, index=df.index)

    df["refugees"]  = get_numeric(["refugees", "REF", "ref"])
    df["idp"]       = get_numeric(["idps", "idp", "IDP", "oip", "ooc"])
    df["stateless"] = get_numeric(["stateless", "STA", "sta"])

    agg = df.groupby(["country_code", "year"]).agg(
        refugees_total=("refugees", "sum"),
        idp_total=("idp", "sum"),
        stateless_total=("stateless", "sum"),
    ).reset_index()

    agg = agg[(agg["year"] >= start_year) & (agg["year"] <= end_year)]
    logger.info(f"UNHCR aggregated: {agg.shape}, {agg['country_code'].nunique()} countries")

    dest = PROCESSED_PATH / "unhcr_features.parquet"
    save_parquet(agg, dest)
    logger.info(f"UNHCR saved → {dest}")
    return agg


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["country_code", "year", "refugees_total", "idp_total", "stateless_total"])
