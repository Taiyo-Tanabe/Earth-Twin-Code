"""
World Bank WDI (World Development Indicators) 取得スクリプト
- wbgapi ライブラリを使用
- 取得指標: GDP, インフレ, 人口, 失業率など
"""
import pandas as pd
import wbgapi as wb
from pathlib import Path
import logging
from ingestion.utils import save_parquet

logger = logging.getLogger(__name__)

PROCESSED_PATH = Path("/app/data/processed/worldbank_features.parquet")

WB_INDICATORS = {
    "NY.GDP.PCAP.PP.KD": "gdp_per_capita_ppp",   # GDP per capita PPP (constant 2017 USD)
    "NY.GDP.MKTP.KD.ZG": "gdp_growth",             # GDP growth (annual %)
    "FP.CPI.TOTL.ZG":    "inflation",              # Inflation CPI (annual %)
    "SL.UEM.TOTL.ZS":    "unemployment",           # Unemployment (% of labor force)
    "SP.POP.TOTL":        "population",            # Total population
    "MS.MIL.XPND.GD.ZS": "military_expenditure",  # Military expenditure (% of GDP)
    "NE.TRD.GNFS.ZS":    "trade_openness",         # Trade (% of GDP)
}

START_YEAR = 1990
END_YEAR = 2024


def fetch_worldbank(
    indicators: dict = WB_INDICATORS,
    start: int = START_YEAR,
    end: int = END_YEAR,
    dest: Path = PROCESSED_PATH,
) -> pd.DataFrame:
    """World Bank API から指定指標を取得してparquetに保存"""
    dest.parent.mkdir(parents=True, exist_ok=True)

    dfs = []
    for code, name in indicators.items():
        logger.info(f"Fetching WB indicator: {code} ({name})")
        try:
            raw = wb.data.DataFrame(code, time=range(start, end + 1), labels=False)
            # raw: 国コード×年 のDataFrame
            df = raw.reset_index().melt(id_vars="economy", var_name="year", value_name=name)
            df.rename(columns={"economy": "country_code"}, inplace=True)
            df["year"] = df["year"].astype(str).str.replace("YR", "").astype(int)
            dfs.append(df)
        except Exception as e:
            logger.warning(f"Failed to fetch {code}: {e}")

    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.merge(df, on=["country_code", "year"], how="outer")

    merged["gdp_per_capita_log"] = merged["gdp_per_capita_ppp"].apply(
        lambda x: float("nan") if pd.isna(x) or x <= 0 else __import__("math").log(x)
    )
    merged["population_log"] = merged["population"].apply(
        lambda x: float("nan") if pd.isna(x) or x <= 0 else __import__("math").log(x)
    )

    save_parquet(merged, dest)
    logger.info(f"Saved World Bank features to {dest} ({len(merged)} rows)")
    return merged


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = fetch_worldbank()
    print(df.head())
    print(df.shape)
