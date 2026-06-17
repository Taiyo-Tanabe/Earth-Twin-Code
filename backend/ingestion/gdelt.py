"""
GDELT v2 Events — 国別紛争シグナル
- 日次更新: http://data.gdeltproject.org/gdeltv2/
- ActionGeo_CountryCode: FIPS 10-4 → ISO3 変換
- 紛争シグナル: QuadClass=4 (Material Conflict) + EventRootCode 14-20 でフィルタ
- 出力: country × year の conflict_events, tone_avg, goldstein_avg
"""
import requests
import pandas as pd
import zipfile
import io
from pathlib import Path
from datetime import date, timedelta
import logging
from ingestion.utils import save_parquet

logger = logging.getLogger(__name__)

GDELT_BASE_URL = "http://data.gdeltproject.org/gdeltv2/"
RAW_PATH = Path("/app/data/raw/gdelt/")
PROCESSED_PATH = Path("/app/data/processed/")

# GDELT v2 Events 列インデックス (0-indexed, タブ区切り)
COL_COUNTRY = 53   # ActionGeo_CountryCode (FIPS 10-4)
COL_EVENTROOT = 28  # EventRootCode (CAMEO)
COL_QUADCLASS = 29  # QuadClass (1=VerbCoop, 2=MatCoop, 3=VerbConflict, 4=MatConflict)
COL_GOLDSTEIN = 30  # GoldsteinScale (-10~+10, 負=紛争)
COL_TONE = 34       # AvgTone (負=否定的)
COL_MENTIONS = 31   # NumMentions
COL_YEAR = 3        # Year

# 紛争関連 CAMEO root codes
CONFLICT_ROOT_CODES = {
    "13",  # THREATEN
    "14",  # PROTEST
    "15",  # EXHIBIT FORCE POSTURE
    "17",  # COERCE
    "18",  # ASSAULT
    "19",  # FIGHT
    "20",  # USE UNCONVENTIONAL MASS VIOLENCE
}

# FIPS 10-4 → ISO 3166-1 alpha-3
FIPS_TO_ISO3 = {
    "AF": "AFG", "AL": "ALB", "AG": "DZA", "AO": "AGO", "AC": "ATG",
    "AR": "ARG", "AM": "ARM", "AU": "AUS", "AT": "AUT", "AJ": "AZE",
    "BF": "BHS", "BA": "BHR", "BG": "BGD", "BB": "BRB", "BO": "BLR",
    "BE": "BEL", "BH": "BLZ", "BN": "BEN", "BT": "BTN", "BL": "BOL",
    "BK": "BIH", "BC": "BWA", "BR": "BRA", "BU": "BGR", "UV": "BFA",
    "BM": "MMR", "BY": "BDI", "CB": "KHM", "CM": "CMR", "CA": "CAN",
    "CV": "CPV", "CT": "CAF", "CD": "TCD", "CI": "CHL", "CH": "CHN",
    "CO": "COL", "CN": "COM", "CG": "COD", "CF": "COG", "CS": "CRI",
    "IV": "CIV", "HR": "HRV", "CU": "CUB", "CY": "CYP", "EZ": "CZE",
    "DA": "DNK", "DJ": "DJI", "DO": "DOM", "TT": "TLS", "EC": "ECU",
    "EG": "EGY", "ES": "SLV", "EK": "GNQ", "ER": "ERI", "EN": "EST",
    "ET": "ETH", "FJ": "FJI", "FI": "FIN", "FR": "FRA", "GB": "GAB",
    "GA": "GMB", "GG": "GEO", "GM": "DEU", "GH": "GHA", "GI": "GIB",
    "GR": "GRC", "GL": "GRL", "GJ": "GRD", "GT": "GTM", "GV": "GIN",
    "PU": "GNB", "GY": "GUY", "HA": "HTI", "HO": "HND", "HK": "HKG",
    "HU": "HUN", "IC": "ISL", "IN": "IND", "ID": "IDN", "IR": "IRN",
    "IZ": "IRQ", "EI": "IRL", "IS": "ISR", "IT": "ITA", "JM": "JAM",
    "JA": "JPN", "JO": "JOR", "KZ": "KAZ", "KE": "KEN", "KR": "KIR",
    "KN": "PRK", "KS": "KOR", "KV": "XKX", "KU": "KWT", "KG": "KGZ",
    "LA": "LAO", "LG": "LVA", "LE": "LBN", "LT": "LSO", "LI": "LBR",
    "LY": "LBY", "LH": "LTU", "LU": "LUX", "MK": "MKD", "MA": "MDG",
    "MI": "MWI", "MY": "MYS", "MV": "MDV", "ML": "MLI", "MT": "MLT",
    "RM": "MHL", "MR": "MRT", "MP": "MUS", "MX": "MEX", "FM": "FSM",
    "MD": "MDA", "MN": "MCO", "MG": "MNG", "MJ": "MNE", "MO": "MAR",
    "MZ": "MOZ", "WA": "NAM", "NR": "NRU", "NP": "NPL", "NL": "NLD",
    "NZ": "NZL", "NU": "NIC", "NG": "NER", "NI": "NGA", "NO": "NOR",
    "MU": "OMN", "PK": "PAK", "PS": "PLW", "PM": "PAN", "PP": "PNG",
    "PF": "PRY", "PE": "PER", "RP": "PHL", "PL": "POL", "PO": "PRT",
    "QA": "QAT", "RO": "ROU", "RS": "RUS", "RW": "RWA", "WS": "WSM",
    "SM": "SMR", "TP": "STP", "SA": "SAU", "SG": "SEN", "RI": "SRB",
    "SE": "SYC", "SL": "SLE", "SN": "SGP", "LO": "SVK", "SI": "SVN",
    "BP": "SLB", "SO": "SOM", "SF": "ZAF", "SP": "ESP", "CE": "LKA",
    "SU": "SDN", "NS": "SUR", "WZ": "SWZ", "SW": "SWE", "SZ": "CHE",
    "SY": "SYR", "TW": "TWN", "TI": "TJK", "TZ": "TZA", "TH": "THA",
    "TN": "TON", "TD": "TTO", "TS": "TUN", "TU": "TUR", "TX": "TKM",
    "TV": "TUV", "UG": "UGA", "UP": "UKR", "UK": "GBR", "US": "USA",
    "UY": "URY", "UZ": "UZB", "NH": "VUT", "VE": "VEN", "VM": "VNM",
    "YM": "YEM", "ZA": "ZMB", "ZI": "ZWE",
    # 特別コード
    "GZ": "PSE",   # Gaza Strip → Palestine
    "WE": "PSE",   # West Bank → Palestine
    "RS": "RUS",   # Russia (重複: RO=ROU と区別)
}


def fetch_gdelt_events_day(target_date: date) -> pd.DataFrame:
    """
    指定日の GDELT Events v2 ファイルをダウンロードし、
    国別の紛争シグナルを集計して返す。
    """
    date_str = target_date.strftime("%Y%m%d")
    url = f"{GDELT_BASE_URL}{date_str}000000.export.CSV.zip"

    logger.info(f"Fetching GDELT events for {target_date}")
    try:
        resp = requests.get(url, timeout=90)
        if resp.status_code == 404:
            logger.warning(f"GDELT file not found for {target_date}")
            return pd.DataFrame()
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"GDELT fetch failed for {target_date}: {e}")
        return pd.DataFrame()

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            fname = z.namelist()[0]
            with z.open(fname) as f:
                df = pd.read_csv(
                    f,
                    sep="\t",
                    header=None,
                    usecols=[COL_COUNTRY, COL_EVENTROOT, COL_QUADCLASS, COL_GOLDSTEIN, COL_TONE, COL_MENTIONS],
                    low_memory=False,
                )
    except Exception as e:
        logger.warning(f"GDELT parse failed for {target_date}: {e}")
        return pd.DataFrame()

    df.columns = ["country_fips", "event_root", "quad_class", "goldstein", "avg_tone", "mentions"]
    df = df.dropna(subset=["country_fips"])

    # FIPS → ISO3
    df["country_code"] = df["country_fips"].astype(str).str[:2].str.upper().map(FIPS_TO_ISO3)
    df = df.dropna(subset=["country_code"])

    # 紛争イベントフィルタ: Material Conflict (4) または 紛争CAMEO codes
    df["event_root"] = df["event_root"].astype(str).str[:2]
    is_conflict = (df["quad_class"] == 4) | (df["event_root"].isin(CONFLICT_ROOT_CODES))
    conflict_df = df[is_conflict]

    if conflict_df.empty:
        return pd.DataFrame()

    agg = conflict_df.groupby("country_code").agg(
        conflict_events=("mentions", "sum"),
        tone_avg=("avg_tone", "mean"),
        goldstein_avg=("goldstein", "mean"),
    ).reset_index()
    agg["date"] = target_date
    return agg


def build_monthly_gdelt(
    start_year: int = 2000,
    end_year: int = 2023,
    dest: Path = None,
) -> pd.DataFrame:
    """
    月次集計のGDELT紛争シグナルを構築。
    各月1日のデータを代表値として使用。
    """
    if dest is None:
        dest = PROCESSED_PATH / "gdelt_monthly.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    records = []

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            target_date = date(year, month, 1)
            if target_date > date.today():
                break
            try:
                df = fetch_gdelt_events_day(target_date)
                if not df.empty:
                    df["year"] = year
                    df["month"] = month
                    records.append(df)
            except Exception as e:
                logger.warning(f"Error for {target_date}: {e}")

    if not records:
        logger.warning("No GDELT data fetched")
        return pd.DataFrame()

    result = pd.concat(records, ignore_index=True)

    # 年次集計 (パネルデータとの結合用)
    annual = result.groupby(["country_code", "year"]).agg(
        gdelt_conflict_events=("conflict_events", "sum"),
        gdelt_tone_avg=("tone_avg", "mean"),
        gdelt_goldstein_avg=("goldstein_avg", "mean"),
    ).reset_index()

    save_parquet(annual, dest.with_name("gdelt_annual.parquet"))
    save_parquet(result, dest)
    logger.info(f"GDELT monthly: {len(result)} rows, GDELT annual: {len(annual)} rows")
    return annual


def get_latest_gdelt_day() -> pd.DataFrame:
    """最新日のGDELT紛争シグナルを取得（日次パイプライン用）"""
    try:
        resp = requests.get(f"{GDELT_BASE_URL}lastupdate.txt", timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Could not fetch lastupdate.txt: {e}")
        target_date = date.today() - timedelta(days=1)
        return fetch_gdelt_events_day(target_date)

    # lastupdate.txt の最初の行にURLが書いてある
    first_url = resp.text.strip().split("\n")[0].split(" ")[-1]
    date_str = first_url.split("/")[-1][:8]
    try:
        target_date = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except Exception:
        target_date = date.today() - timedelta(days=1)

    return fetch_gdelt_events_day(target_date)
