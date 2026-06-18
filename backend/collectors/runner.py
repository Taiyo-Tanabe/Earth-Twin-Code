"""
Earth Twin Collector Runner
すべてのデータコレクターを永続的なスレッドとして起動する。
このプロセスは止まらない。
"""
import threading
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("runner")

from collectors.sources.earthquakes import EarthquakeCollector
from collectors.sources.weather import WeatherCollector
from collectors.sources.gdelt import GDELTCollector
from collectors.sources.physical import SolarActivityCollector, ForestFireCollector, SeaTemperatureCollector
from collectors.sources.biological import WHODiseaseCollector, FoodPriceCollector, LocustCollector
from collectors.sources.economic import CommodityPriceCollector, EconomicSignalCollector
from collectors.sources.annual import UCDPAnnualCollector, VDemAnnualCollector, WorldBankAnnualCollector


ALL_COLLECTORS = [
    # ── リアルタイム (秒〜分) ────────────────────────────────
    EarthquakeCollector(),          # 1分ごと — USGS

    # ── 高頻度 (15分〜1時間) ─────────────────────────────────
    GDELTCollector(),               # 15分ごと — ニュースシグナル
    WeatherCollector(),             # 1時間ごと — 気象

    # ── 中頻度 (6時間) ───────────────────────────────────────
    SolarActivityCollector(),       # 1時間ごと — 太陽活動・地磁気
    CommodityPriceCollector(),      # 6時間ごと — コモディティ価格
    EconomicSignalCollector(),      # 6時間ごと — 経済指標

    # ── 日次 ────────────────────────────────────────────────
    ForestFireCollector(),          # 日次 — 森林火災 (NASA FIRMS)
    SeaTemperatureCollector(),      # 日次 — 海面水温
    WHODiseaseCollector(),          # 日次チェック — 感染症
    FoodPriceCollector(),           # 日次チェック — 食料価格
    LocustCollector(),              # 日次 — 蝗害

    # ── 年次監視 (日次チェック → 新リリース時即取得) ──────────
    UCDPAnnualCollector(),          # 武力衝突データ
    VDemAnnualCollector(),          # 民主主義指数
    WorldBankAnnualCollector(),     # 世界開発指標
]


def start_collector(collector):
    try:
        collector.run_forever()
    except Exception as e:
        logger.critical(f"[{collector.name}] crashed: {e}", exc_info=True)


def main():
    logger.info("=" * 60)
    logger.info("Earth Twin Collector — Starting all collectors")
    logger.info(f"Total: {len(ALL_COLLECTORS)} collectors")
    logger.info("=" * 60)

    threads = []
    for c in ALL_COLLECTORS:
        t = threading.Thread(
            target=start_collector,
            args=(c,),
            daemon=True,
            name=c.name,
        )
        t.start()
        threads.append(t)
        logger.info(f"  ✓ {c.name} (every {c.interval_seconds}s)")

    # メインスレッドは生存監視
    while True:
        alive = sum(1 for t in threads if t.is_alive())
        logger.info(f"Collectors alive: {alive}/{len(threads)}")
        time.sleep(300)  # 5分ごとに死活確認


if __name__ == "__main__":
    main()
