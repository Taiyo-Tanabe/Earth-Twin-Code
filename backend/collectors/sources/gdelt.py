"""
GDELT v2 — Global Database of Events, Language, and Tone
15分ごとに新しいファイルが公開される。常時最新ファイルを取得する。
"""
import requests
import pandas as pd
import io
import zipfile
import logging
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

CAMEO_CONFLICT_CODES = {
    "14", "15", "16", "17", "18", "19",  # 抗議・暴力・強制
    "20",  # 大規模暴力
}


class GDELTCollector(BaseCollector):
    name = "gdelt"
    interval_seconds = 900  # 15分

    def fetch(self) -> pd.DataFrame:
        # 最新ファイルのURLを取得
        resp = requests.get(LASTUPDATE_URL, timeout=30)
        resp.raise_for_status()
        lines = resp.text.strip().splitlines()

        csv_url = None
        for line in lines:
            parts = line.split()
            if len(parts) >= 3 and parts[2].endswith(".export.CSV.zip"):
                csv_url = parts[2]
                break

        if not csv_url:
            return pd.DataFrame()

        # ZIPをダウンロード
        zresp = requests.get(csv_url, timeout=60)
        zresp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(zresp.content)) as z:
            csv_name = [n for n in z.namelist() if n.endswith(".CSV")][0]
            with z.open(csv_name) as f:
                df = pd.read_csv(f, sep="\t", header=None, low_memory=False,
                                 usecols=[0, 5, 6, 29, 30, 31, 33],
                                 names=["event_id", "actor1_country", "actor2_country",
                                        "goldstein", "num_mentions", "num_sources",
                                        "avg_tone"],
                                 dtype=str)

        df["goldstein"] = pd.to_numeric(df["goldstein"], errors="coerce")
        df["avg_tone"] = pd.to_numeric(df["avg_tone"], errors="coerce")
        df["num_mentions"] = pd.to_numeric(df["num_mentions"], errors="coerce")

        # 国別に集計
        records = []
        for country_col in ["actor1_country", "actor2_country"]:
            sub = df[[country_col, "goldstein", "avg_tone", "num_mentions"]].copy()
            sub = sub.rename(columns={country_col: "country_code"})
            sub = sub.dropna(subset=["country_code"])
            sub = sub[sub["country_code"].str.len() == 3]
            records.append(sub)

        if not records:
            return pd.DataFrame()

        combined = pd.concat(records)
        agg = combined.groupby("country_code").agg(
            gdelt_goldstein_avg=("goldstein", "mean"),
            gdelt_tone_avg=("avg_tone", "mean"),
            gdelt_events=("num_mentions", "sum"),
        ).reset_index()

        agg["year"] = pd.Timestamp.utcnow().year
        agg["fetched_at"] = pd.Timestamp.utcnow().isoformat()
        return agg
