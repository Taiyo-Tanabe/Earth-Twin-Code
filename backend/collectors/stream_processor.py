"""
Stream Processor: Redisストリームを読んでTimescaleDBに書き込む。
新データが一定量蓄積されたらモデル更新をトリガーする。
"""
import os
import json
import logging
import time
import threading
from datetime import datetime, timezone

import pandas as pd
import redis
import sqlalchemy as sa

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
TIMESCALE_URL = os.environ.get("TIMESCALE_URL", "postgresql://earthtwin:earthtwin123@timescaledb:5432/earthtwin")

# 何行蓄積されたらモデル更新をトリガーするか
MODEL_UPDATE_THRESHOLD = 500
_pending_rows = 0
_lock = threading.Lock()


def _get_engine():
    return sa.create_engine(TIMESCALE_URL, pool_pre_ping=True)


def _write_to_db(source: str, df: pd.DataFrame) -> int:
    """DataFrameをTimescaleDBのraw_signalsテーブルに書き込む"""
    if df.empty:
        return 0
    engine = _get_engine()
    df["source"] = source
    df["ingested_at"] = datetime.now(timezone.utc)
    try:
        with engine.begin() as conn:
            df.to_sql("raw_signals", conn, if_exists="append", index=False,
                      method="multi", chunksize=500)
        return len(df)
    except Exception as e:
        logger.warning(f"DB write failed for {source}: {e}")
        return 0


def _trigger_model_update():
    """モデル再学習を非同期でトリガー"""
    def _run():
        try:
            logger.info("Model update triggered by stream processor")
            import subprocess
            subprocess.run(
                ["python", "-c", "from models.train import train_conflict_model, train_regime_model; train_conflict_model(); train_regime_model()"],
                cwd="/app", timeout=3600, capture_output=True,
            )
            logger.info("Model update complete")
        except Exception as e:
            logger.error(f"Model update failed: {e}")
    threading.Thread(target=_run, daemon=True).start()


def process_stream(source_name: str):
    """単一ストリームを継続的に処理するワーカー"""
    global _pending_rows
    r = redis.from_url(REDIS_URL, decode_responses=True)
    stream_key = f"earth_twin:stream:{source_name}"
    last_id = "$"  # 起動後の新着のみ

    logger.info(f"[processor:{source_name}] listening on {stream_key}")

    while True:
        try:
            messages = r.xread({stream_key: last_id}, count=10, block=5000)
            for stream, entries in (messages or []):
                for msg_id, fields in entries:
                    last_id = msg_id
                    try:
                        payload = json.loads(fields["payload"])
                        df = pd.read_json(payload["data"], orient="records")
                        written = _write_to_db(payload["source"], df)
                        with _lock:
                            _pending_rows += written
                            if _pending_rows >= MODEL_UPDATE_THRESHOLD:
                                _pending_rows = 0
                                _trigger_model_update()
                    except Exception as e:
                        logger.error(f"[processor:{source_name}] message error: {e}")
        except redis.RedisError as e:
            logger.warning(f"Redis error: {e}")
            time.sleep(5)


def run_all_processors(source_names: list[str]):
    """すべてのストリームを並列処理"""
    threads = []
    for name in source_names:
        t = threading.Thread(target=process_stream, args=(name,), daemon=True, name=f"proc:{name}")
        t.start()
        threads.append(t)
    logger.info(f"Stream processors started: {source_names}")
    for t in threads:
        t.join()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sources = [
        "earthquakes", "weather", "gdelt", "solar_activity",
        "forest_fires", "sea_temperature", "who_disease",
        "food_prices", "commodity_prices", "economic_signals",
        "ucdp_annual", "vdem_annual", "worldbank_annual",
    ]
    run_all_processors(sources)
