"""
USGS Earthquake Hazards Program — Real-time feed
更新: 1分ごと (USGSが1分ごとに更新)
URL: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson
"""
import requests
import pandas as pd
import pycountry
from collectors.base import BaseCollector


def _latlon_to_iso3(lat: float, lon: float) -> str | None:
    """座標から国コードに変換 (簡易実装: reverse geocoding なしで重心マッチ)"""
    try:
        import reverse_geocoder as rg
        result = rg.search((lat, lon), verbose=False)
        if result:
            cc2 = result[0].get("cc", "")
            c = pycountry.countries.get(alpha_2=cc2)
            return c.alpha_3 if c else None
    except Exception:
        pass
    return None


class EarthquakeCollector(BaseCollector):
    name = "earthquakes"
    interval_seconds = 60  # USGSは1分ごとに更新

    def fetch(self) -> pd.DataFrame:
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        features = resp.json().get("features", [])

        rows = []
        for f in features:
            props = f.get("properties", {})
            geom = f.get("geometry", {})
            coords = geom.get("coordinates", [None, None])
            lon, lat = coords[0], coords[1]
            mag = props.get("mag")
            ts = props.get("time")
            if mag is None or ts is None or lat is None:
                continue
            rows.append({
                "timestamp": pd.Timestamp(ts, unit="ms", tz="UTC"),
                "latitude": lat,
                "longitude": lon,
                "magnitude": float(mag),
                "depth_km": coords[2] if len(coords) > 2 else None,
                "place": props.get("place", ""),
            })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["year"] = df["timestamp"].dt.year
        return df
