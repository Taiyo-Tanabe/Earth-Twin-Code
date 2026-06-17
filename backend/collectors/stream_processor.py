"""
Stream Processor: Redis ストリームを読んで Neon (PostgreSQL) に書き込む。
500 行蓄積されるごとに予測を再実行する。
"""
import os
import json
import logging
import time
import threading
from datetime import datetime, timezone

import redis
import sqlalchemy as sa

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
MODEL_UPDATE_THRESHOLD = 500
_pending_rows = 0
_lock = threading.Lock()


def _get_engine():
    url = (
        os.environ.get("DATABASE_URL") or
        os.environ.get("TIMESCALE_URL") or
        "postgresql://earthtwin:earthtwin123@timescaledb:5432/earthtwin"
    )
    connect_args = {"sslmode": "require"} if "neon.tech" in url else {}
    return sa.create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def _write_to_db(source: str, rows_json: str) -> int:
    """受信した JSON 行を raw_signals テーブルに書き込む（JSONB 形式）"""
    try:
        import json as _json
        records = _json.loads(rows_json)
        if not records:
            return 0
        engine = _get_engine()
        now = datetime.now(timezone.utc).isoformat()
        with engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO raw_signals (source, ingested_at, payload)
                VALUES (:source, :ingested_at, CAST(:payload AS jsonb))
            """), [
                {"source": source, "ingested_at": now, "payload": _json.dumps(r, default=str)}
                for r in records
            ])
        return len(records)
    except Exception as e:
        logger.warning(f"DB write failed for {source}: {e}")
        return 0


def _trigger_predict():
    """閾値超過時に予測を再実行して Neon に書き込む"""
    def _run():
        try:
            logger.info("Prediction triggered by stream processor")
            from push_to_neon import run
            run()
            logger.info("Prediction complete")
        except Exception as e:
            logger.error(f"Prediction trigger failed: {e}")
    threading.Thread(target=_run, daemon=True).start()


def process_stream(source_name: str):
    global _pending_rows
    r = redis.from_url(REDIS_URL, decode_responses=True)
    stream_key = f"earth_twin:stream:{source_name}"
    last_id = "$"

    logger.info(f"[processor:{source_name}] listening on {stream_key}")

    while True:
        try:
            messages = r.xread({stream_key: last_id}, count=10, block=5000)
            for _stream, entries in (messages or []):
                for msg_id, fields in entries:
                    last_id = msg_id
                    try:
                        payload = json.loads(fields["payload"])
                        written = _write_to_db(payload["source"], payload["data"])
                        with _lock:
                            _pending_rows += written
                            if _pending_rows >= MODEL_UPDATE_THRESHOLD:
                                _pending_rows = 0
                                _trigger_predict()
                    except Exception as e:
                        logger.error(f"[processor:{source_name}] message error: {e}")
        except redis.RedisError as e:
            logger.warning(f"Redis error: {e}")
            time.sleep(5)


def run_all_processors(source_names: list[str]):
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
