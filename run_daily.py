"""Configure production adapters and run today's experiment workflow."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from ai_stock_trader.ai_manager import AIDecisionManager
from ai_stock_trader.config import load_local_environment
from ai_stock_trader.daily_run import DailyRunner
from ai_stock_trader.errors import (
    AIDecisionError,
    ConfigurationError,
    DailyRunError,
    MarketDataError,
    StorageError,
)
from ai_stock_trader.market_data import FinnhubMarketData
from ai_stock_trader.storage import ExperimentStorage


def build_runner(experiments_root: str = "experiments") -> DailyRunner:
    load_local_environment()
    market = FinnhubMarketData.from_environment()
    decisions = AIDecisionManager.from_environment(market)
    return DailyRunner(ExperimentStorage(experiments_root), market, decisions)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiments-root", default="experiments")
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="skip duplicate UTC cron invocation outside 3:30 PM ET",
    )
    args = parser.parse_args(argv)
    if args.scheduled and datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M") != "15:30":
        return 0
    try:
        build_runner(args.experiments_root).run()
        return 0
    except (
        AIDecisionError,
        ConfigurationError,
        DailyRunError,
        MarketDataError,
        StorageError,
        OSError,
    ) as exc:
        print(f"Daily run failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
