"""
BaseCollector: すべてのデータコレクターの基底クラス。
各コレクターは run_forever() を呼ぶだけで永続的にデータを収集し続ける。
"""
import time
import logging
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import pandas as pd
import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")


class BaseCollector(ABC):
    name: str = "base"
    interval_seconds: int = 3600

    def __init__(self):
        self._redis: redis.Redis | None = None

    @property
    def redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        """最新データを取得して DataFrame で返す。空なら pd.DataFrame()"""

    def publish(self, df: pd.DataFrame) -> None:
        if df.empty:
            return
        payload = json.dumps({
            "source": self.name,
            "ts": datetime.now(timezone.utc).isoformat(),
            "rows": len(df),
            "data": df.to_json(orient="records"),
        }, ensure_ascii=False)
        stream_key = f"earth_twin:stream:{self.name}"
        try:
            self.redis.xadd(stream_key, {"payload": payload}, maxlen=10000)
            logger.info(f"[{self.name}] +{len(df)} rows → {stream_key}")
        except Exception as e:
            logger.warning(f"[{self.name}] Redis unavailable, skipping stream publish: {e}")

    def run_forever(self) -> None:
        logger.info(f"[{self.name}] collector started (interval={self.interval_seconds}s)")
        while True:
            t0 = time.monotonic()
            try:
                df = self.fetch()
                self.publish(df)
            except Exception as e:
                logger.error(f"[{self.name}] fetch error: {e}", exc_info=True)
            elapsed = time.monotonic() - t0
            sleep = max(0, self.interval_seconds - elapsed)
            time.sleep(sleep)
