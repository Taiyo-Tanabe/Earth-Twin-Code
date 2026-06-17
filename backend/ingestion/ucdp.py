"""
UCDP GED (Georeferenced Event Dataset) v24.1
- URL: https://ucdp.uu.se/downloads/ged/ged241-csv.zip
- 1989-2023年、124カ国の武力衝突イベント
- 紛争ラベル: 年間死者数 ≥ 25 → conflict_onset = 1 (UCDP標準閾値)
- パレスチナ特別処理: Gaza Strip / West Bank イベントを PSE として追加
"""
import requests
import zipfile
import io
import pandas as pd
import pycountry
from pathlib import Path
import logging
from ingestion.utils import save_parquet

logger = logging.getLogger(__name__)
PROCESSED_PATH = Path("/app/data/processed")

# v25.1 (2024データ) 優先、失敗時は v24.1 にフォールバック
GED_URLS = [
    "https://ucdp.uu.se/downloads/ged/ged251-csv.zip",  # 2024年データ
    "https://ucdp.uu.se/downloads/ged/ged241-csv.zip",  # 2023年データ (フォールバック)
]

# UCDP 国名 → ISO3 手動マッピング (pycountry が解決できない別名)
_NAME_TO_ISO3 = {
    "DR Congo (Zaire)":                  "COD",
    "Myanmar (Burma)":                   "MMR",
    "Bosnia-Herzegovina":                "BIH",
    "Cambodia (Kampuchea)":              "KHM",
    "Russia (Soviet Union)":             "RUS",
    "Yemen (North Yemen)":               "YEM",
    "Kingdom of eSwatini (Swaziland)":   "SWZ",
    "Serbia (Yugoslavia)":               "SRB",
    "Zimbabwe (Rhodesia)":               "ZWE",
    "Madagascar (Malagasy)":             "MDG",
    "Ivory Coast":                       "CIV",
    "Congo":                             "COG",
    "North Macedonia":                   "MKD",
    "Trinidad and Tobago":               "TTO",
    "Turkey":                            "TUR",
}

# パレスチナ自治区の adm_1 名
_PSE_REGIONS = {"Gaza Strip", "West Bank"}


def _country_to_iso3(name: str) -> str | None:
    """UCDP 国名 → ISO3 変換。未対応なら None。"""
    if name in _NAME_TO_ISO3:
        return _NAME_TO_ISO3[name]
    try:
        c = pycountry.countries.lookup(name)
        return c.alpha_3
    except LookupError:
        pass
    # 部分一致フォールバック
    clean = name.split("(")[0].strip()
    try:
        c = pycountry.countries.lookup(clean)
        return c.alpha_3
    except LookupError:
        return None


def build_conflict_panel(start_year: int = 1989, end_year: int = 2024) -> pd.DataFrame:
    """
    UCDP GED から country × year の紛争ラベルを構築。
    deaths_best ≥ 25 → conflict_onset = 1 (UCDP標準閾値)
    """
    resp = None
    for url in GED_URLS:
        logger.info(f"Downloading UCDP GED from {url}...")
        try:
            r = requests.get(url, timeout=180)
            if r.status_code == 200:
                resp = r
                logger.info(f"Downloaded {len(r.content)//1024}KB from {url}")
                break
            else:
                logger.warning(f"  HTTP {r.status_code} for {url}, trying next...")
        except Exception as e:
            logger.warning(f"  Failed {url}: {e}")
    if resp is None:
        raise RuntimeError("All UCDP GED download URLs failed")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        with z.open(z.namelist()[0]) as f:
            df = pd.read_csv(f, low_memory=False)

    logger.info(f"GED raw: {len(df)} events, {df['country'].nunique()} countries")

    # 年フィルタ
    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)].copy()
    df["best"] = pd.to_numeric(df["best"], errors="coerce").fillna(0)

    # --- パレスチナ (PSE) 特別処理 ---
    # Gaza Strip / West Bank のイベントを PSE として複製
    pse_mask = df["adm_1"].isin(_PSE_REGIONS)
    pse_df = df[pse_mask].copy()
    pse_df["_iso3"] = "PSE"
    logger.info(f"Palestine events (Gaza+WB): {len(pse_df)} events")

    # --- 通常の国マッピング ---
    df["_iso3"] = df["country"].apply(_country_to_iso3)
    unmapped = df[df["_iso3"].isna()]["country"].unique()
    if len(unmapped) > 0:
        logger.warning(f"Unmapped countries ({len(unmapped)}): {unmapped}")
    df = df.dropna(subset=["_iso3"])

    # 結合
    combined = pd.concat([df, pse_df], ignore_index=True)

    # country × year 集計
    agg = combined.groupby(["_iso3", "year"]).agg(
        battle_deaths=("best", "sum"),
        event_count=("best", "count"),
    ).reset_index()
    agg.rename(columns={"_iso3": "country_code"}, inplace=True)

    # 紛争ラベル: UCDP 標準 25死者/年
    agg["conflict_onset"] = (agg["battle_deaths"] >= 25).astype(int)

    # 全 country × year グリッドで欠損を0埋め
    all_codes = agg["country_code"].unique()
    years = range(start_year, end_year + 1)
    grid = pd.MultiIndex.from_product([all_codes, years], names=["country_code", "year"])
    agg = agg.set_index(["country_code", "year"]).reindex(grid, fill_value=0).reset_index()

    dest = PROCESSED_PATH / "ucdp_panel.parquet"
    save_parquet(agg, dest)

    n_conflict = agg[agg["conflict_onset"] == 1]["country_code"].nunique()
    pse_years = agg[(agg["country_code"] == "PSE") & (agg["conflict_onset"] == 1)]["year"].tolist()
    logger.info(f"Conflict panel: {len(agg)} rows, {n_conflict} countries with conflict")
    logger.info(f"Palestine conflict years: {pse_years}")
    return agg
