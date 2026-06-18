"""
地球物理系データ収集
- 火山活動: Smithsonian GVP (週次)
- 太陽活動: NOAA SWPC (1時間ごと)
- 森林火災: NASA FIRMS (日次)
- 海面温度異常: NOAA (日次)
"""
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import io
import logging
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class SolarActivityCollector(BaseCollector):
    """太陽活動 (フレア・地磁気嵐) — インフラ脆弱性に影響"""
    name = "solar_activity"
    interval_seconds = 3600  # 1時間

    def fetch(self) -> pd.DataFrame:
        # NOAA SWPC Geomagnetic K-index (グローバル指標)
        url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        rows = []
        for item in data[-24:]:  # 直近24時間
            try:
                if isinstance(item, dict):
                    ts = item.get("time_tag") or item.get("time") or ""
                    kp = item.get("kp") or item.get("Kp") or item.get("kp_index") or ""
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    ts = item[0]
                    kp = item[1]
                else:
                    continue
                if not ts or ts == "time_tag":  # ヘッダ行をスキップ
                    continue
                rows.append({
                    "timestamp": ts,
                    "kp_index": float(kp) if kp not in ("", None) else None,
                    "year": int(str(ts)[:4]) if ts else datetime.now(timezone.utc).year,
                })
            except Exception:
                continue

        return pd.DataFrame(rows) if rows else pd.DataFrame()


class ForestFireCollector(BaseCollector):
    """NASA FIRMS — 森林火災・野火 (日次, 全球)"""
    name = "forest_fires"
    interval_seconds = 86400  # 日次

    def fetch(self) -> pd.DataFrame:
        # NASA FIRMS VIIRS 直近1日 (世界)
        # MAP_KEY不要の公開エンドポイント
        url = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_24h.csv"
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
        except Exception as e:
            logger.warning(f"FIRMS download failed: {e}")
            return pd.DataFrame()

        if df.empty or "latitude" not in df.columns:
            return pd.DataFrame()

        now = datetime.now(timezone.utc)
        frp_col = "frp" if "frp" in df.columns else df.columns[0]
        return pd.DataFrame([{
            "year": now.year,
            "fire_count_global": len(df),
            "fire_power_avg_global": float(df[frp_col].mean()) if frp_col in df.columns else 0.0,
            "fetched_at": now.isoformat(),
        }])


class SeaTemperatureCollector(BaseCollector):
    """NOAA 海面水温異常 (エルニーニョ監視)"""
    name = "sea_temperature"
    interval_seconds = 86400  # 日次

    def fetch(self) -> pd.DataFrame:
        # NOAA ENSO Nino3.4 SST anomaly
        url = "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            lines = [l for l in resp.text.strip().splitlines() if l.strip() and not l.startswith("YR")]
            rows = []
            for line in lines[-12:]:  # 直近12ヶ月
                parts = line.split()
                if len(parts) >= 5:
                    rows.append({
                        "year": int(parts[0]),
                        "month": int(parts[1]),
                        "nino34_sst": float(parts[4]) if parts[4] != "-99.9" else None,
                    })
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception as e:
            logger.warning(f"SST fetch failed: {e}")
            return pd.DataFrame()
