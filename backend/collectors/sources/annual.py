"""
年次データの常時監視コレクター
データが年次更新でも「常に監視し、リリースされたら即取得」する。
毎日チェックし、新しいバージョンが出たら自動取得。
"""
import requests
import pandas as pd
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

VERSION_CACHE = Path("/app/data/collector_versions.json")


def _load_versions() -> dict:
    if VERSION_CACHE.exists():
        return json.loads(VERSION_CACHE.read_text())
    return {}


def _save_version(source: str, version_hash: str):
    versions = _load_versions()
    versions[source] = version_hash
    VERSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_CACHE.write_text(json.dumps(versions, indent=2))


def _has_changed(source: str, content_hash: str) -> bool:
    return _load_versions().get(source) != content_hash


class UCDPAnnualCollector(BaseCollector):
    """UCDP GED — 年次リリースを即座に検知して取得"""
    name = "ucdp_annual"
    interval_seconds = 86400  # 日次チェック

    def fetch(self) -> pd.DataFrame:
        # UCDP APIから最新バージョンを確認
        url = "https://ucdpapi.pcr.uu.se/api/gedevents/24.1?pagesize=1"
        try:
            resp = requests.get(url, timeout=30)
            content_hash = hashlib.md5(resp.headers.get("ETag", resp.text[:200]).encode()).hexdigest()

            if not _has_changed(self.name, content_hash):
                logger.info(f"[{self.name}] No new data")
                return pd.DataFrame()

            _save_version(self.name, content_hash)

            # 本取得
            import datetime as _dt
            from ingestion.ucdp import build_conflict_panel
            df = build_conflict_panel(1989, _dt.date.today().year)
            logger.info(f"[{self.name}] New UCDP data: {len(df)} rows")
            return df
        except Exception as e:
            logger.warning(f"[{self.name}] Failed: {e}")
            return pd.DataFrame()


class VDemAnnualCollector(BaseCollector):
    """V-Dem — 年次リリース監視"""
    name = "vdem_annual"
    interval_seconds = 86400

    def fetch(self) -> pd.DataFrame:
        check_url = "https://v-dem.net/data/the-v-dem-dataset/"
        try:
            resp = requests.get(check_url, timeout=30)
            content_hash = hashlib.md5(resp.text[:1000].encode()).hexdigest()

            if not _has_changed(self.name, content_hash):
                return pd.DataFrame()

            _save_version(self.name, content_hash)
            from ingestion.vdem import fetch_vdem
            df = fetch_vdem()
            logger.info(f"[{self.name}] New V-Dem data: {len(df)} rows")
            return df
        except Exception as e:
            logger.warning(f"[{self.name}] Failed: {e}")
            return pd.DataFrame()


class WorldBankAnnualCollector(BaseCollector):
    """World Bank WDI — 新しいデータが追加されたら即取得"""
    name = "worldbank_annual"
    interval_seconds = 86400

    def fetch(self) -> pd.DataFrame:
        # WB APIの最終更新日を確認
        url = "https://api.worldbank.org/v2/sources/2?format=json"
        try:
            resp = requests.get(url, timeout=30)
            data = resp.json()
            last_updated = str(data[1][0].get("lastupdated", "")) if len(data) > 1 else ""
            content_hash = hashlib.md5(last_updated.encode()).hexdigest()

            if not _has_changed(self.name, content_hash):
                return pd.DataFrame()

            _save_version(self.name, content_hash)
            from ingestion.worldbank import fetch_worldbank
            df = fetch_worldbank()
            logger.info(f"[{self.name}] New WorldBank data: {len(df)} rows")
            return df
        except Exception as e:
            logger.warning(f"[{self.name}] Failed: {e}")
            return pd.DataFrame()
