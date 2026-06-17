"""
経済・金融系データ (高頻度)
- コモディティ価格: World Bank (日次)
- 海運指数: Baltic Dry Index代理 (週次)
- エネルギー価格 (週次)
"""
import requests
import pandas as pd
from datetime import datetime, timezone
import logging
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class CommodityPriceCollector(BaseCollector):
    """
    World Bank Commodity Price Data (Pink Sheet)
    石油・金・小麦・銅など主要コモディティ価格
    紛争・不安定化の経済トリガー
    """
    name = "commodity_prices"
    interval_seconds = 21600  # 6時間

    INDICATORS = {
        "CRUDE_WTI": "原油(WTI)",
        "WHEAT_US_HRW": "小麦",
        "MAIZE": "トウモロコシ",
        "GOLD": "金",
        "COPPER": "銅",
    }

    def fetch(self) -> pd.DataFrame:
        # World Bank commodities API (JSON)
        url = "https://api.worldbank.org/v2/en/indicator/PNRG_INDEX?format=json&per_page=100&mrv=1"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if len(data) < 2 or not data[1]:
                return pd.DataFrame()

            rows = []
            for item in data[1]:
                if item.get("value") is not None:
                    rows.append({
                        "year": int(item.get("date", 0)),
                        "energy_price_index": item.get("value"),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    })
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception as e:
            logger.warning(f"Commodity price fetch failed: {e}")
            return pd.DataFrame()


class EconomicSignalCollector(BaseCollector):
    """
    World Bank経済指標の高頻度チェック
    新しいデータリリースを検知したら即取得
    """
    name = "economic_signals"
    interval_seconds = 21600  # 6時間

    def fetch(self) -> pd.DataFrame:
        indicators = {
            "FP.CPI.TOTL.ZG": "inflation",
            "NY.GDP.MKTP.KD.ZG": "gdp_growth",
            "SL.UEM.TOTL.ZS": "unemployment",
        }

        all_rows = []
        for code, col_name in indicators.items():
            url = f"https://api.worldbank.org/v2/country/all/indicator/{code}?format=json&per_page=500&mrv=2"
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                if len(data) < 2:
                    continue
                for item in (data[1] or []):
                    if item.get("value") is not None:
                        all_rows.append({
                            "country_code": item.get("countryiso3code"),
                            "year": int(item.get("date", 0)),
                            col_name: item.get("value"),
                        })
            except Exception as e:
                logger.warning(f"Economic signal [{code}] failed: {e}")
                continue

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        df = df.dropna(subset=["country_code"])
        df = df[df["country_code"].str.len() == 3]
        return df
