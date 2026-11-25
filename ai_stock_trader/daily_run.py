"""Idempotent, single-process daily experiment orchestration."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from .ai_manager import DecisionResult
from .errors import AIDecisionError, DailyRunError
from .market_data import MarketNews, MarketStatus, Quote
from .models import Experiment, PortfolioConfig, PortfolioState, PortfolioType, Ticker, today_et
from .storage import ExperimentStorage
from .trading import initialize_control_portfolio, value_portfolio


class DailyMarket(Protocol):
    def market_status(self) -> MarketStatus: ...

    def market_news(self) -> Sequence[MarketNews]: ...

    def quote(self, ticker: Ticker | str) -> Quote: ...


class DecisionManager(Protocol):
    def run(
        self, *, strategy: str, state: PortfolioState, as_of: date, news: Sequence[MarketNews]
    ) -> DecisionResult: ...


@contextmanager
def _run_lock(root: Path):
    """Exclusive-create lock prevents overlapping scheduled and manual workflows."""
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".daily_run.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise DailyRunError("another daily run holds the experiments lock") from exc
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)


class DailyRunner:
    def __init__(
        self,
        storage: ExperimentStorage,
        market: DailyMarket,
        decisions: DecisionManager,
        *,
        today: Callable[[], date] = today_et,
    ) -> None:
        self.storage = storage
        self.market = market
        self.decisions = decisions
        self.today = today

    def run(self) -> None:
        day = self.today()
        with _run_lock(self.storage.root):
            experiments = self.storage.discover()
            active = {
                item.name: self.storage.active / item.name
                for item in experiments
                if (self.storage.active / item.name).is_dir()
            }
            # End dates are inclusive; finish due experiments before checking the market.
            for experiment in experiments:
                if experiment.name in active and experiment.end_date <= day:
                    self._finalize(experiment, active[experiment.name], day)

            try:
                if not self.market.market_status().is_open:
                    return
                news = self.market.market_news()
            except Exception as exc:
                raise DailyRunError(f"daily market check failed: {exc}") from exc

            for experiment in experiments:
                directory = active.get(experiment.name)
                if directory is None or experiment.end_date <= day or experiment.start_date > day:
                    continue
                for portfolio in sorted(
                    experiment.portfolios, key=lambda item: item.name.casefold()
                ):
                    try:
                        self._process(experiment, directory, portfolio, day, news)
                    except Exception as exc:
                        raise DailyRunError(
                            f"daily run failed for {experiment.name}/{portfolio.name}: {exc}"
                        ) from exc

    def _base_state(self, experiment: Experiment, portfolio: PortfolioConfig) -> PortfolioState:
        state = self.storage.load_snapshot(experiment.name, portfolio.name)
        return state if state is not None else PortfolioState(cash=portfolio.starting_cash)

    def _value(self, state: PortfolioState) -> PortfolioState:
        quotes: dict[Ticker | str, Decimal] = {
            str(ticker): self.market.quote(ticker).current_price for ticker in state.holdings
        }
        return value_portfolio(state, quotes)

    def _process(
        self,
        experiment: Experiment,
        directory: Path,
        portfolio: PortfolioConfig,
        day: date,
        news: Sequence[MarketNews],
    ) -> None:
        if self.storage.was_processed(experiment.name, portfolio.name, day):
            return
        state = self._base_state(experiment, portfolio)
        if portfolio.portfolio_type is PortfolioType.CONTROL:
            if not state.holdings:
                assert portfolio.control_ticker is not None
                quote = self.market.quote(portfolio.control_ticker)
                state = initialize_control_portfolio(
                    state, portfolio.control_ticker, quote.current_price
                )
            state = self._value(state)
            if not self.storage.has_state_for_date(directory, portfolio.name, day):
                self.storage.append_state(directory, portfolio.name, day, state)
            self.storage.save_snapshot(experiment.name, portfolio.name, state, processed_date=day)
            return

        state = self._value(state)
        if not self.storage.has_state_for_date(directory, portfolio.name, day):
            self.storage.append_state(directory, portfolio.name, day, state)
        if portfolio.strategy is None:
            raise AIDecisionError("AI-managed portfolio has no strategy")
        result = self.decisions.run(strategy=portfolio.strategy, state=state, as_of=day, news=news)
        decision = result.decision
        # Persist fresh prices with the post-trade snapshot so a later closed-market
        # finalization can use the last successful valuation without a stale quote.
        next_state = self._value(result.state)
        self.storage.append_trades(
            directory, portfolio.name, day, decision.trades, decision.explanation.summary
        )
        self.storage.save_snapshot(experiment.name, portfolio.name, next_state, processed_date=day)

    def _finalize(self, experiment: Experiment, directory: Path, day: date) -> None:
        for portfolio in sorted(experiment.portfolios, key=lambda item: item.name.casefold()):
            try:
                state = self._base_state(experiment, portfolio)
                # Finalization happens before market status is checked, so use the last
                # successfully saved quote set instead of requesting potentially stale
                # prices after close. Never-started portfolios retain their cash value.
                state = PortfolioState(
                    cash=state.cash,
                    holdings=state.holdings,
                    prices=state.prices if state.prices is not None else {},
                )
                if not self.storage.has_state_for_date(directory, portfolio.name, day):
                    self.storage.append_state(directory, portfolio.name, day, state)
            except Exception as exc:
                raise DailyRunError(
                    f"finalization failed for {experiment.name}/{portfolio.name}: {exc}"
                ) from exc
        self.storage.move_to_finished(directory)
