"""
V-Dem (Varieties of Democracy) — vdemdata PyPI パッケージ経由
取得失敗時は空DataFrameを返してパイプライン継続。

インストール: pip install vdemdata
"""
import pandas as pd
from pathlib import Path
import logging
from ingestion.utils import save_parquet

logger = logging.getLogger(__name__)
PROCESSED_PATH = Path("/app/data/processed")

VDEM_COLS = [
    "country_text_id",
    "year",
    "v2x_polyarchy",     # 選挙民主主義指数 (0-1)
    "v2x_libdem",        # 自由民主主義指数 (0-1)
    "v2x_regime",        # 政体タイプ (0〜3)
    "v2x_corr",          # 政治腐敗指数
    "v2xel_frefair",     # 自由公正選挙指数
]


def fetch_vdem(start_year: int = 1990, end_year: int = 2024) -> pd.DataFrame:
    """
    vdemdata パッケージ経由で V-Dem データを取得。
    パッケージ未インストール or 取得失敗時は空DataFrameを返す。
    """
    # Our World In Data / GitHub 経由で V-Dem データを取得
    try:
        import requests, io
        # V-Dem が GitHub/OSF に置いている軽量版
        urls = [
            "https://ourworldindata.org/grapher/electoral-democracy.csv",
            "https://ourworldindata.org/grapher/v-dem-electoral-democracy-index.csv",
        ]
        for url in urls:
            try:
                logger.info(f"Trying: {url}")
                resp = requests.get(url, timeout=120)
                if resp.status_code != 200:
                    continue
                df = pd.read_csv(io.StringIO(resp.text))
                logger.info(f"Downloaded: {df.shape}, cols: {df.columns.tolist()[:8]}")

                # Our World In Data 形式の場合
                col_map = {}
                if "Entity" in df.columns:
                    col_map["Entity"] = "country_name"
                if "Code" in df.columns:
                    col_map["Code"] = "country_code"
                if "Year" in df.columns:
                    col_map["Year"] = "year"
                # V-Dem 指標の列を探す
                for c in df.columns:
                    cl = c.lower()
                    if "polyarchy" in cl or "electdem" in cl or "electoral democracy" in cl:
                        col_map[c] = "v2x_polyarchy"
                    elif "libdem" in cl:
                        col_map[c] = "v2x_libdem"
                    elif "regime" in cl and "type" in cl:
                        col_map[c] = "v2x_regime"

                if "country_code" not in col_map.values():
                    continue

                df = df.rename(columns=col_map)
                df = df[(df["year"] >= start_year) & (df["year"] <= end_year)]
                df = df.dropna(subset=["country_code"])
                df["country_code"] = df["country_code"].astype(str).str.strip().str.upper()
                df = df[df["country_code"].str.len() == 3]

                if len(df) > 100:
                    logger.info(f"V-Dem (OWID): {df.shape}, {df['country_code'].nunique()} countries")
                    _save(df)
                    return df
            except Exception as e2:
                logger.warning(f"  {url}: {e2}")

    except Exception as e:
        logger.warning(f"V-Dem direct download failed: {e}")

    logger.warning("V-Dem: all methods failed. Skipping V-Dem features.")
    return pd.DataFrame()


def _save(df: pd.DataFrame):
    dest = PROCESSED_PATH / "vdem_features.parquet"
    save_parquet(df, dest)
    logger.info(f"V-Dem saved → {dest}")
