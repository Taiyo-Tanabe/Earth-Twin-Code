"""
Earth Twin unified background worker.
Single process that runs all background tasks as threads:
  - Data collectors (13 sources, always-on)
  - Stream processor (Redis -> Neon)
  - Data Scout (every 6h, discovers new sources)
  - Daily predict (every 24h, re-runs predictions -> Neon)
"""
import os
import threading
import logging
import time
import signal
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("worker")

# Point data paths to the committed models/panel in the repo
DATA_DIR = Path(__file__).parent / "data"
os.environ.setdefault("APP_DATA_DIR", str(DATA_DIR))

STREAM_SOURCES = [
    "earthquakes", "weather", "gdelt", "solar_activity",
    "forest_fires", "sea_temperature", "who_disease",
    "food_prices", "commodity_prices", "economic_signals",
    "ucdp_annual", "vdem_annual", "worldbank_annual",
]


def _run_collectors():
    from collectors.runner import main
    main()


def _run_stream_processor():
    from collectors.stream_processor import run_all_processors
    run_all_processors(STREAM_SOURCES)


def _run_scout():
    from agents.scout_runner import main
    main()


def _run_daily_predict():
    INTERVAL = 24 * 3600
    logger.info("Daily predict loop started (every 24h)")
    time.sleep(60)  # wait for boot
    while True:
        try:
            logger.info("[daily-predict] running predictions -> Neon")
            from push_to_neon import run as push
            push()
            logger.info("[daily-predict] done")
        except Exception as e:
            logger.error(f"[daily-predict] failed: {e}", exc_info=True)
        time.sleep(INTERVAL)


def main():
    logger.info("=" * 60)
    logger.info("Earth Twin Worker — starting all background tasks")
    logger.info("=" * 60)

    tasks = [
        ("collectors",       _run_collectors),
        ("stream-processor", _run_stream_processor),
        ("data-scout",       _run_scout),
        ("daily-predict",    _run_daily_predict),
    ]

    threads = []
    for name, fn in tasks:
        t = threading.Thread(target=fn, name=name, daemon=True)
        t.start()
        threads.append(t)
        logger.info(f"  started: {name}")

    def _shutdown(sig, frame):
        logger.info("Shutdown signal received")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    task_map = {name: fn for name, fn in tasks}
    while True:
        time.sleep(300)
        for i, t in enumerate(threads):
            if not t.is_alive():
                name = t.name
                fn = task_map.get(name)
                if fn:
                    logger.warning(f"Thread '{name}' died — restarting")
                    new_t = threading.Thread(target=fn, name=name, daemon=True)
                    new_t.start()
                    threads[i] = new_t


if __name__ == "__main__":
    main()
