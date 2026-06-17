"""
Open-Meteo — 無料・認証不要の気象データ
各国首都の気象データを収集し、国レベルに集計する
更新: 1時間ごと
https://open-meteo.com/en/docs
"""
import requests
import pandas as pd
from datetime import datetime, timezone
from collectors.base import BaseCollector

# 主要国の首都座標 (ISO3 → lat, lon)
COUNTRY_CAPITALS = {
    "AFG": (34.52, 69.18), "AGO": (-8.84, 13.23), "ARG": (-34.60, -58.38),
    "AUS": (-35.28, 149.13), "AZE": (40.41, 49.87), "BDI": (-3.38, 29.36),
    "BFA": (12.37, -1.52), "BGD": (23.72, 90.41), "BLR": (53.90, 27.57),
    "BOL": (-16.50, -68.15), "BRA": (-15.78, -47.93), "CAF": (4.36, 18.56),
    "CHL": (-33.46, -70.65), "CHN": (39.93, 116.39), "CIV": (5.35, -4.00),
    "CMR": (3.87, 11.52), "COD": (-4.32, 15.32), "COG": (-4.27, 15.28),
    "COL": (4.71, -74.07), "CUB": (23.13, -82.38), "DZA": (36.74, 3.06),
    "ECU": (-0.22, -78.51), "EGY": (30.06, 31.25), "ERI": (15.33, 38.93),
    "ETH": (9.03, 38.74), "GEO": (41.69, 44.83), "GIN": (9.54, -13.68),
    "GTM": (14.64, -90.51), "HND": (14.10, -87.22), "HTI": (18.54, -72.34),
    "IDN": (-6.21, 106.85), "IND": (28.64, 77.22), "IRN": (35.70, 51.42),
    "IRQ": (33.34, 44.40), "ISR": (31.77, 35.22), "JPN": (35.68, 139.75),
    "KAZ": (51.18, 71.45), "KEN": (-1.29, 36.82), "KGZ": (42.87, 74.59),
    "KHM": (11.57, 104.92), "KOR": (37.55, 126.99), "LBN": (33.87, 35.50),
    "LBY": (32.90, 13.18), "LKA": (6.91, 79.86), "LSO": (-29.32, 27.48),
    "MAR": (34.02, -6.85), "MDG": (-18.91, 47.54), "MEX": (19.43, -99.13),
    "MLI": (12.65, -8.00), "MMR": (19.74, 96.08), "MOZ": (-25.97, 32.59),
    "MRT": (18.07, -15.96), "MWI": (-13.97, 33.79), "NER": (13.51, 2.12),
    "NGA": (9.07, 7.40), "NPL": (27.72, 85.32), "PAK": (33.73, 73.09),
    "PER": (-12.05, -77.04), "PHL": (14.59, 120.98), "PNG": (-9.43, 147.18),
    "PRK": (39.02, 125.75), "PSE": (31.78, 35.23), "RUS": (55.75, 37.62),
    "RWA": (-1.94, 30.06), "SAU": (24.69, 46.72), "SDN": (15.55, 32.53),
    "SOM": (2.05, 45.34), "SSD": (4.85, 31.62), "SYR": (33.51, 36.29),
    "TCD": (12.11, 15.04), "TGO": (6.14, 1.22), "TJK": (38.56, 68.77),
    "TKM": (37.95, 58.38), "TZA": (-6.17, 35.74), "UGA": (0.32, 32.57),
    "UKR": (50.43, 30.52), "UZB": (41.30, 69.27), "VEN": (10.49, -66.88),
    "VNM": (21.03, 105.85), "YEM": (15.35, 44.21), "ZAF": (-25.75, 28.19),
    "ZMB": (-15.42, 28.28), "ZWE": (-17.83, 31.05), "USA": (38.90, -77.04),
    "GBR": (51.51, -0.13), "DEU": (52.52, 13.40), "FRA": (48.85, 2.35),
}

VARIABLES = "temperature_2m_max,precipitation_sum,wind_speed_10m_max"


class WeatherCollector(BaseCollector):
    name = "weather"
    interval_seconds = 3600  # 1時間ごと

    def fetch(self) -> pd.DataFrame:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = []

        # バッチで最大10カ国ずつ（API制限回避）
        codes = list(COUNTRY_CAPITALS.keys())
        batch_size = 10
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            lats = ",".join(str(COUNTRY_CAPITALS[c][0]) for c in batch)
            lons = ",".join(str(COUNTRY_CAPITALS[c][1]) for c in batch)
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lats}&longitude={lons}"
                f"&daily={VARIABLES}&timezone=UTC"
                f"&start_date={today}&end_date={today}"
            )
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                # 単一の場合はリストに包む
                if isinstance(data, dict):
                    data = [data]
                for j, item in enumerate(data):
                    daily = item.get("daily", {})
                    dates = daily.get("time", [])
                    temp = daily.get("temperature_2m_max", [None])
                    precip = daily.get("precipitation_sum", [None])
                    wind = daily.get("wind_speed_10m_max", [None])
                    if dates:
                        rows.append({
                            "country_code": batch[j],
                            "date": dates[0],
                            "year": int(dates[0][:4]),
                            "temp_max_c": temp[0] if temp else None,
                            "precipitation_mm": precip[0] if precip else None,
                            "wind_speed_kmh": wind[0] if wind else None,
                        })
            except Exception:
                continue

        return pd.DataFrame(rows) if rows else pd.DataFrame()
