"""
生物系データ収集
- WHO感染症サーベイランス (週次)
- FAO食料価格指数 (月次)
- 蝗害 (FAO Desert Locust, 日次)
"""
import requests
import pandas as pd
from datetime import datetime, timezone
import io
import logging
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class WHODiseaseCollector(BaseCollector):
    """WHO Global Health Observatory — 感染症・死亡率データ"""
    name = "who_disease"
    interval_seconds = 86400  # 日次チェック (WHOは週次〜月次更新)

    def fetch(self) -> pd.DataFrame:
        # WHO GHO API — 乳幼児死亡率 (代理変数: 保健システム脆弱性)
        url = "https://ghoapi.azureedge.net/api/MDG_0000000001?$filter=SpatialDimType eq 'COUNTRY'"
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json().get("value", [])

            rows = []
            for item in data:
                if item.get("Dim1") == "BTSX":  # 両性
                    rows.append({
                        "country_code": item.get("SpatialDim"),
                        "year": item.get("TimeDim"),
                        "infant_mortality_rate": item.get("NumericValue"),
                    })

            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows).dropna(subset=["country_code", "year"])
            df["year"] = pd.to_numeric(df["year"], errors="coerce")
            return df.dropna(subset=["year"])
        except Exception as e:
            logger.warning(f"WHO disease fetch failed: {e}")
            return pd.DataFrame()


class FoodPriceCollector(BaseCollector):
    """FAO食料価格指数 — 食料安全保障・紛争トリガー"""
    name = "food_prices"
    interval_seconds = 86400  # 日次チェック (FAOは月次更新)

    def fetch(self) -> pd.DataFrame:
        # FAO WFP Food Price Monitoring
        url = "https://api.worldbank.org/v2/country/all/indicator/AG.PRD.FOOD.XD?format=json&per_page=5000&mrv=5"
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if len(data) < 2:
                return pd.DataFrame()

            rows = []
            for item in data[1] or []:
                if item.get("value") is not None:
                    rows.append({
                        "country_code": item.get("countryiso3code"),
                        "year": int(item.get("date", 0)),
                        "food_production_index": item.get("value"),
                    })

            df = pd.DataFrame(rows).dropna(subset=["country_code"])
            return df[df["country_code"].str.len() == 3]
        except Exception as e:
            logger.warning(f"Food price fetch failed: {e}")
            return pd.DataFrame()


class LocustCollector(BaseCollector):
    """FAO Desert Locust — 蝗害 (農業・食料危機の前兆)"""
    name = "desert_locust"
    interval_seconds = 86400  # 日次

    # FAO locust hub RSS feed — fallback to summary row on parse error
    _LOCUST_URLS = [
        "https://locust-hub-hqfao.hub.arcgis.com/api/feed/rss/new",
        "https://www.fao.org/ag/locusts/en/info/info/rss/index.html",
    ]

    def fetch(self) -> pd.DataFrame:
        import xml.etree.ElementTree as ET

        content = None
        for url in self._LOCUST_URLS:
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                raw = resp.content.strip()
                # Skip if response is HTML (error page)
                if raw[:5].lower().startswith(b"<!doc") or raw[:6].lower().startswith(b"<html"):
                    continue
                content = raw
                break
            except Exception:
                continue

        if content is None:
            logger.warning("Locust: no valid RSS feed available")
            return pd.DataFrame()

        try:
            root = ET.fromstring(content)
            items = root.findall(".//item")
            rows = []
            for item in items:
                title = item.findtext("title", "")
                desc = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")
                rows.append({
                    "year": datetime.now(timezone.utc).year,
                    "title": title,
                    "description": desc[:200],
                    "pub_date": pub_date,
                })
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except ET.ParseError as e:
            logger.warning(f"Locust fetch failed: {e}")
            return pd.DataFrame()
