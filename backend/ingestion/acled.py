"""
ACLED (Armed Conflict Location & Event Data)
- 登録: https://acleddata.com/  (無料)
- カバー: 1997年〜現在、200+国
- 認証: OAuth Bearer token (email + password)
- 週次更新 → UCDPより速報性が高い (2026年データも取得可能)

環境変数:
  ACLED_EMAIL     - 登録メールアドレス
  ACLED_PASSWORD  - パスワード

未設定時: Noneを返しUCDPにフォールバック
"""
import os
import requests
import pandas as pd
from pathlib import Path
import logging
from ingestion.utils import save_parquet

logger = logging.getLogger(__name__)
PROCESSED_PATH = Path("/app/data/processed")

TOKEN_URL = "https://acleddata.com/oauth/token"
API_URL   = "https://acleddata.com/api/acled/read"


def _get_access_token() -> str | None:
    email    = os.environ.get("ACLED_EMAIL", "")
    password = os.environ.get("ACLED_PASSWORD", "")
    if not email or not password:
        logger.info(
            "ACLED credentials not set → skipping ACLED (using UCDP instead).\n"
            "  To enable: set ACLED_EMAIL and ACLED_PASSWORD in docker-compose environment."
        )
        return None

    try:
        resp = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "username":   email,
                "password":   password,
                "grant_type": "password",
                "client_id":  "acled",
                "scope":      "authenticated",
            },
            timeout=30,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            logger.warning("ACLED token response had no access_token")
            return None
        logger.info("ACLED OAuth token obtained successfully")
        return token
    except Exception as e:
        logger.warning(f"ACLED token request failed: {e}")
        return None


def fetch_acled_country_year(
    start_year: int = 1997,
    end_year: int | None = None,
) -> pd.DataFrame | None:
    """
    ACLED API から country × year の集計データを取得。
    返り値カラム:
      country_code (ISO3), year,
      acled_events    (総イベント数),
      acled_battles   (戦闘イベント数),
      acled_fatalities (死者数推定),
      acled_conflict  (battles ≥ 1 or fatalities ≥ 25 → 1)
    """
    token = _get_access_token()
    if token is None:
        return None

    if end_year is None:
        from datetime import datetime
        end_year = datetime.utcnow().year

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    logger.info(f"Fetching ACLED data {start_year}–{end_year}...")
    all_records = []

    for year in range(start_year, end_year + 1):
        logger.info(f"  ACLED year {year}...")
        params = {
            "_format": "json",
            "year":    year,
            "fields":  "iso3|year|event_type|fatalities",
            "limit":   0,  # 0 = no limit (pagination not needed for per-year calls)
        }
        try:
            resp = requests.get(API_URL, params=params, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            if data.get("count", 0) == 0:
                continue
            rows = data.get("data", [])
            df = pd.DataFrame(rows)
            df["fatalities"] = pd.to_numeric(df["fatalities"], errors="coerce").fillna(0)
            all_records.append(df)
        except Exception as e:
            logger.warning(f"  Failed year {year}: {e}")

    if not all_records:
        logger.warning("No ACLED data fetched")
        return pd.DataFrame()

    raw = pd.concat(all_records, ignore_index=True)
    raw.rename(columns={"iso3": "country_code"}, inplace=True)
    raw["year"] = raw["year"].astype(int)

    battle_types = {"Battles", "Explosions/Remote violence", "Violence against civilians"}
    raw["is_battle"] = raw["event_type"].isin(battle_types).astype(int)

    agg = raw.groupby(["country_code", "year"]).agg(
        acled_events=("event_type", "count"),
        acled_battles=("is_battle", "sum"),
        acled_fatalities=("fatalities", "sum"),
    ).reset_index()

    agg["acled_conflict"] = (
        (agg["acled_battles"] >= 1) | (agg["acled_fatalities"] >= 25)
    ).astype(int)

    dest = PROCESSED_PATH / "acled_panel.parquet"
    save_parquet(agg, dest)

    n_conflict = agg[agg["acled_conflict"] == 1]["country_code"].nunique()
    logger.info(f"ACLED panel: {len(agg)} rows, {n_conflict} countries with conflict")
    return agg
