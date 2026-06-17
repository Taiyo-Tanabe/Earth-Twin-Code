"""
Data Scout — 常時稼働ランナー
Airflow不要。6時間ごとにモデル弱点を分析し、新データソースを統合し続ける。
"""
import time
import logging
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scout] %(levelname)s %(message)s",
)
logger = logging.getLogger("scout_runner")

INTERVAL_SECONDS = 6 * 3600  # 6時間ごと


def main():
    logger.info("Earth Twin Data Scout — continuous mode started")
    logger.info(f"Discovery interval: every {INTERVAL_SECONDS // 3600} hours")

    def _shutdown(sig, frame):
        logger.info("Shutdown signal received")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while True:
        try:
            logger.info("=" * 50)
            logger.info("Starting discovery cycle")
            from agents.data_scout import run_data_scout
            result = run_data_scout()
            integrated = len(result.get("integrated", []))
            rejected = len(result.get("rejected", []))
            logger.info(f"Cycle complete: +{integrated} integrated, {rejected} rejected")
        except Exception as e:
            logger.error(f"Scout cycle failed: {e}", exc_info=True)

        logger.info(f"Next cycle in {INTERVAL_SECONDS // 3600} hours")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
