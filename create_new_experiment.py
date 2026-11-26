"""Interactive creator for a new experiment directory."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from ai_stock_trader.config import load_local_environment
from ai_stock_trader.errors import (
    ConfigurationError,
    DomainValidationError,
    MarketDataError,
    StorageError,
)
from ai_stock_trader.market_data import FinnhubMarketData
from ai_stock_trader.models import Experiment, PortfolioConfig, PortfolioType, Ticker
from ai_stock_trader.storage import ExperimentStorage


def _ask(prompt: str, input_fn: Callable[[str], str]) -> str:
    value = input_fn(prompt).strip()
    if not value:
        raise DomainValidationError(f"{prompt.rstrip(': ')} cannot be empty")
    return value


def collect_experiment(input_fn: Callable[[str], str], market: FinnhubMarketData) -> Experiment:
    name = _ask("Experiment name: ", input_fn)
    try:
        start = date.fromisoformat(_ask("Start date (YYYY-MM-DD): ", input_fn))
        end = date.fromisoformat(_ask("End date (YYYY-MM-DD): ", input_fn))
    except ValueError as exc:
        raise DomainValidationError("dates must use YYYY-MM-DD format") from exc
    if end < start:
        raise DomainValidationError("end date must be on or after start date")
    try:
        count = int(_ask("Number of portfolios: ", input_fn))
    except ValueError as exc:
        raise DomainValidationError("portfolio count must be a positive whole number") from exc
    if count < 1:
        raise DomainValidationError("portfolio count must be a positive whole number")

    portfolios: list[PortfolioConfig] = []
    seen: set[str] = set()
    for index in range(1, count + 1):
        print(f"Portfolio {index} of {count}")
        portfolio_name = _ask("Portfolio name: ", input_fn)
        if portfolio_name.casefold() in seen:
            raise DomainValidationError("portfolio names must be unique")
        seen.add(portfolio_name.casefold())
        try:
            portfolio_type = PortfolioType(_ask("Type (ai-managed/control): ", input_fn).lower())
        except ValueError as exc:
            raise DomainValidationError("type must be ai-managed or control") from exc
        starting_cash = _ask("Starting money: ", input_fn)
        if portfolio_type is PortfolioType.CONTROL:
            ticker = Ticker(_ask("Control ticker: ", input_fn))
            # Validate the symbol without requiring a live-session quote; Finnhub's
            # latest quote is normally the prior close when the market is shut.
            try:
                market.validate_ticker(ticker)
            except Exception as exc:
                # Vendor-specific quote failures are presented as a clear validation failure.
                raise MarketDataError(f"could not validate control ticker {ticker}: {exc}") from exc
            portfolios.append(
                PortfolioConfig(
                    portfolio_name, portfolio_type, starting_cash, control_ticker=ticker
                )
            )
        else:
            print("Enter strategy Markdown; enter a single '.' on a line to finish.")
            lines: list[str] = []
            while True:
                line = input_fn("")
                if line == ".":
                    break
                lines.append(line)
            portfolios.append(
                PortfolioConfig(
                    portfolio_name, portfolio_type, starting_cash, strategy="\n".join(lines)
                )
            )
    return Experiment(name, start, end, tuple(portfolios))


def main(
    argv: Sequence[str] | None = None,
    *,
    market: FinnhubMarketData | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiments-root", type=Path, default=Path("experiments"))
    args = parser.parse_args(argv)
    try:
        load_local_environment()
        provider = market or FinnhubMarketData.from_environment()
        experiment = collect_experiment(input_fn or input, provider)
        path = ExperimentStorage(args.experiments_root).create(experiment)
        print(f"Created experiment at {path}")
        return 0
    except (
        ConfigurationError,
        DomainValidationError,
        MarketDataError,
        StorageError,
        OSError,
    ) as exc:
        print(f"Could not create experiment: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
