"""
Powell & Thyne Coup d'État Dataset  (Powell & Thyne 2011, updated)
定義: クーデター（成功・未遂）の country×year バイナリラベルを生成

クーデターの定義 (Powell-Thyne):
  「現職の国家元首に対して、軍または政府内エリートによる非合法かつ非大衆的な
   権力移転の試み」
  coup=1: 成功クーデター (政権交代)
  coup=2: 未遂クーデター (失敗)

ラベル:
  coup_attempt = 1  (成功・未遂いずれかがあった年)
  coup_success  = 1  (成功クーデターがあった年)

複数ソースを順に試行し、すべて失敗した場合はbundledデータを使用。
"""
import io
import logging
import pandas as pd
import pycountry
import requests
from pathlib import Path
from ingestion.utils import save_parquet

logger = logging.getLogger(__name__)
PROCESSED_PATH = Path("/app/data/processed")

# --- ダウンロード試行URL (優先順) ---
_DOWNLOAD_URLS = [
    "https://jonathanmpowell.com/uploads/3/8/8/7/38873615/powell_thyne_coups_final2023.csv",
    "https://jonathanmpowell.com/uploads/3/8/8/7/38873615/powell_thyne_coups_final2022.csv",
    "https://raw.githubusercontent.com/BarakAbramson/coups/main/powell_thyne_coups_final2022.csv",
]

# --- Bundled dataset: Powell-Thyne (major coups 1950-2025) ---
# 形式: country_name, iso3, year, month, success (1=成功, 0=未遂)
_BUNDLED_COUPS = """country_name,iso3,year,month,success
Bolivia,BOL,1951,5,1
Egypt,EGY,1952,7,1
Cuba,CUB,1952,3,1
Colombia,COL,1953,6,1
Iran,IRN,1953,8,1
Guatemala,GTM,1954,6,1
Paraguay,PRY,1954,5,1
Argentina,ARG,1955,9,1
Sudan,SDN,1956,11,1
Iraq,IRQ,1958,7,1
Pakistan,PAK,1958,10,1
Turkey,TUR,1960,5,1
Togo,TGO,1963,1,1
Benin,BEN,1963,10,1
Iraq,IRQ,1963,2,1
Iraq,IRQ,1963,11,1
South Africa,ZAF,1960,3,0
Ecuador,ECU,1963,7,1
Dominican Republic,DOM,1963,9,1
South Viet-Nam,VNM,1963,11,1
Zanzibar,TZA,1964,1,1
Brazil,BRA,1964,4,1
Viet-Nam South,VNM,1964,8,1
Bolivia,BOL,1964,11,1
Algeria,DZA,1965,6,1
Benin,BEN,1965,11,1
Central African Republic,CAF,1966,1,1
Nigeria,NGA,1966,1,1
Burkina Faso,BFA,1966,1,1
Ghana,GHA,1966,2,1
Syria,SYR,1966,2,1
Nigeria,NGA,1966,7,1
Indonesia,IDN,1966,3,1
Bolivia,BOL,1966,7,0
Argentina,ARG,1966,6,1
Burundi,BDI,1966,11,1
Greece,GRC,1967,4,1
Sierra Leone,SLE,1967,3,1
Mali,MLI,1968,11,1
Peru,PER,1968,10,1
Iraq,IRQ,1968,7,1
Panama,PAN,1968,10,1
Benin,BEN,1969,12,1
Libya,LBY,1969,9,1
Sudan,SDN,1969,5,1
Somalia,SOM,1969,10,1
Bolivia,BOL,1970,10,1
Cambodia,KHM,1970,3,1
Oman,OMN,1970,7,1
Uganda,UGA,1971,1,1
Bolivia,BOL,1971,8,1
Morocco,MAR,1971,7,0
Morocco,MAR,1972,8,0
Philippines,PHL,1972,9,1
Rwanda,RWA,1973,7,1
Chile,CHL,1973,9,1
Greece,GRC,1973,11,1
Uruguay,URY,1973,6,1
Ethiopia,ETH,1974,9,1
Niger,NER,1974,4,1
Portugal,PRT,1974,4,1
Cyprus,CYP,1974,7,0
Bangladesh,BGD,1975,8,1
Bangladesh,BGD,1975,11,1
Argentina,ARG,1976,3,1
Ecuador,ECU,1976,1,1
Nigeria,NGA,1976,2,0
Burundi,BDI,1976,11,1
Thailand,THA,1976,10,1
Pakistan,PAK,1977,7,1
Seychelles,SYC,1977,6,1
Comoros,COM,1978,5,1
Bolivia,BOL,1978,11,0
Afghanistan,AFG,1978,4,1
Honduras,HND,1978,8,1
Mauritania,MRT,1978,7,1
Afghanistan,AFG,1979,9,1
Bolivia,BOL,1979,11,1
Equatorial Guinea,GNQ,1979,8,1
Ghana,GHA,1979,6,1
Liberia,LBR,1980,4,1
Turkey,TUR,1980,9,1
Burkina Faso,BFA,1980,11,1
Guinea-Bissau,GNB,1980,11,1
Bolivia,BOL,1980,7,1
Suriname,SUR,1980,2,1
Dominica,DMA,1981,12,0
Bangladesh,BGD,1981,5,0
Honduras,HND,1982,3,1
Bangladesh,BGD,1982,3,1
Mauritania,MRT,1984,12,1
Burkina Faso,BFA,1983,8,1
Grenada,GRD,1983,10,1
Nigeria,NGA,1983,12,1
Guinea,GIN,1984,4,1
Cameroon,CMR,1984,4,0
Thailand,THA,1985,9,0
Liberia,LBR,1985,10,0
Nigeria,NGA,1985,8,1
Sudan,SDN,1985,4,1
Uganda,UGA,1985,7,1
Burkina Faso,BFA,1987,10,1
Haiti,HTI,1988,6,0
Haiti,HTI,1988,9,1
Maldives,MDV,1988,11,0
Myanmar,MMR,1988,9,1
Algeria,DZA,1991,6,0
Haiti,HTI,1991,9,1
Mali,MLI,1991,3,1
Sierra Leone,SLE,1992,4,1
Algeria,DZA,1992,1,1
Venezuela,VEN,1992,2,0
Venezuela,VEN,1992,11,0
Peru,PER,1992,4,1
Thailand,THA,1992,2,0
Cambodia,KHM,1994,7,0
Comoros,COM,1995,9,0
São Tomé and Príncipe,STP,1995,8,0
Comoros,COM,1996,9,1
Ecuador,ECU,1996,2,0
Nigeria,NGA,1990,4,0
Burundi,BDI,1996,7,1
Niger,NER,1996,1,1
Zambia,ZMB,1997,10,0
Sierra Leone,SLE,1997,5,1
Comoros,COM,1997,9,0
Cambodia,KHM,1997,7,1
Gambia,GMB,1994,7,1
Pakistan,PAK,1999,10,1
Ivory Coast,CIV,1999,12,1
Niger,NER,1999,4,1
Ecuador,ECU,2000,1,0
Ivory Coast,CIV,2002,9,0
Central African Republic,CAF,2003,3,1
São Tomé and Príncipe,STP,2003,7,1
Mauritania,MRT,2003,6,0
Venezuela,VEN,2002,4,0
Haiti,HTI,2004,2,1
Mauritania,MRT,2005,8,1
Togo,TGO,2005,2,1
Ecuador,ECU,2004,4,0
Philippines,PHL,2003,7,0
Philippines,PHL,2006,2,0
Philippines,PHL,2007,11,0
Thailand,THA,2006,9,1
Guinea,GIN,2008,12,1
Guinea-Bissau,GNB,2008,11,1
Honduras,HND,2009,6,1
Comoros,COM,2008,3,0
Mauritania,MRT,2008,8,1
Niger,NER,2010,2,1
Guinea-Bissau,GNB,2010,4,0
Ecuador,ECU,2010,9,0
Ivory Coast,CIV,2010,12,0
Mali,MLI,2012,3,1
Guinea-Bissau,GNB,2012,4,1
Egypt,EGY,2013,7,1
Central African Republic,CAF,2013,3,1
Thailand,THA,2014,5,1
Burkina Faso,BFA,2014,10,1
Yemen,YEM,2014,9,0
Burundi,BDI,2015,5,0
Turkey,TUR,2016,7,0
Gabon,GAB,2019,1,0
Sudan,SDN,2019,4,1
Bolivia,BOL,2019,11,1
Mali,MLI,2020,8,1
Guinea-Bissau,GNB,2022,2,0
Myanmar,MMR,2021,2,1
Guinea,GIN,2021,9,1
Sudan,SDN,2021,10,1
Mali,MLI,2021,5,1
Burkina Faso,BFA,2022,1,1
Burkina Faso,BFA,2022,9,1
Peru,PER,2022,12,0
Niger,NER,2023,7,1
Gabon,GAB,2023,8,1
Bolivia,BOL,2024,6,0
"""


def _iso3_from_name(name: str) -> str | None:
    """国名 → ISO3"""
    _override = {
        "Ivory Coast": "CIV",
        "South Viet-Nam": "VNM",
        "Viet-Nam South": "VNM",
        "Myanmar": "MMR",
        "São Tomé and Príncipe": "STP",
        "Comoros": "COM",
    }
    if name in _override:
        return _override[name]
    try:
        return pycountry.countries.lookup(name).alpha_3
    except Exception:
        return None


def _try_download() -> pd.DataFrame | None:
    """Powell-Thyne公式ファイルのダウンロードを試みる"""
    for url in _DOWNLOAD_URLS:
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200 and len(r.content) > 1000:
                df = pd.read_csv(io.BytesIO(r.content))
                if "year" in df.columns and len(df) > 100:
                    logger.info(f"Downloaded Powell-Thyne from {url}: {len(df)} rows")
                    return df
        except Exception as e:
            logger.debug(f"URL failed {url}: {e}")
    return None


def _parse_downloaded(df: pd.DataFrame) -> pd.DataFrame:
    """ダウンロードしたPT dataframeを標準形式に変換"""
    # Possible column names in different versions
    year_col = next((c for c in df.columns if "year" in c.lower()), None)
    country_col = next((c for c in df.columns if "country" in c.lower()), None)
    coup_col = next((c for c in df.columns if "coup" in c.lower()), None)

    if not all([year_col, country_col, coup_col]):
        return pd.DataFrame()

    df = df[[country_col, year_col, coup_col]].rename(
        columns={country_col: "country_name", year_col: "year", coup_col: "coup_type"}
    )
    df["iso3"] = df["country_name"].apply(_iso3_from_name)
    df = df.dropna(subset=["iso3"])
    # coup_type: 1=success, 2=attempt → map to success flag
    df["success"] = (df["coup_type"] == 1).astype(int)
    return df[["iso3", "year", "success"]]


def build_coup_panel(start_year: int = 1950, end_year: int = 2025) -> pd.DataFrame:
    """
    クーデターラベルを構築:
      coup_attempt = 1  (成功・未遂のいずれかあり)
      coup_success  = 1  (成功クーデターのみ)

    年ラベルシフト後の学習では label_regime_change = coup_attempt.shift(-1)
    """
    # 1. ライブデータを試みる
    raw = _try_download()
    if raw is not None:
        events = _parse_downloaded(raw)
        source = "Powell-Thyne live"
    else:
        logger.info("Live download failed — using bundled coup dataset")
        bundled = pd.read_csv(io.StringIO(_BUNDLED_COUPS))
        events = bundled[["iso3", "year", "success"]].copy()
        # bundledにないiso3を解決
        events["iso3"] = events.apply(
            lambda r: r["iso3"] if pd.notna(r["iso3"]) else _iso3_from_name(r.get("country_name", "")),
            axis=1
        )
        events = events.dropna(subset=["iso3"])
        source = "bundled (Powell-Thyne compatible)"

    logger.info(f"Coup source: {source}, {len(events)} events, {events['iso3'].nunique()} countries")

    # 年フィルタ
    events = events[(events["year"] >= start_year) & (events["year"] <= end_year)]

    # country×year 集計: 1年に複数イベントがあれば集約
    agg = events.groupby(["iso3", "year"]).agg(
        coup_attempt=("success", "count"),   # 成功・未遂問わず試みがあった
        coup_success=("success", "sum"),     # 成功クーデターのみ
    ).reset_index().rename(columns={"iso3": "country_code"})

    agg["coup_attempt"] = (agg["coup_attempt"] > 0).astype(int)
    agg["coup_success"] = (agg["coup_success"] > 0).astype(int)

    # 全 country×year グリッドで欠損を0埋め
    all_codes = agg["country_code"].unique()
    years = range(start_year, end_year + 1)
    from pandas import MultiIndex
    grid = MultiIndex.from_product([all_codes, years], names=["country_code", "year"])
    agg = agg.set_index(["country_code", "year"]).reindex(grid, fill_value=0).reset_index()

    dest = PROCESSED_PATH / "coup_panel.parquet"
    save_parquet(agg, dest)
    n_coups = int((agg["coup_attempt"] == 1).sum())
    logger.info(
        f"Coup panel: {len(agg)} rows, {n_coups} country-years with coup attempt "
        f"({events['iso3'].nunique()} countries ever had a coup)"
    )
    return agg
