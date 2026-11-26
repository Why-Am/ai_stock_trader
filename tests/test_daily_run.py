import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from ai_stock_trader.daily_run import DailyRunner
from ai_stock_trader.errors import DailyRunError
from ai_stock_trader.market_data import MarketStatus, Quote
from ai_stock_trader.models import Experiment, PortfolioConfig, PortfolioType, Ticker
from ai_stock_trader.storage import ExperimentStorage


class FakeMarket:
    def __init__(self, is_open: bool = True) -> None:
        self.is_open = is_open
        self.status_calls = 0
        self.quotes: list[str] = []

    def market_status(self) -> MarketStatus:
        self.status_calls += 1
        return MarketStatus(self.is_open, "US", None, None)

    def market_news(self) -> tuple[object, ...]:
        return ()

    def quote(self, ticker: Ticker | str) -> Quote:
        symbol = Ticker(str(ticker))
        self.quotes.append(str(symbol))
        return Quote(symbol, Decimal("10"), datetime.now().astimezone())


class FakeAI:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, **kwargs: object) -> object:
        self.calls += 1

        class Result:
            decision = type(
                "Decision",
                (),
                {"trades": (), "explanation": type("Explanation", (), {"summary": "hold"})()},
            )()
            state = kwargs["state"]

        return Result()


def experiment(tmp_path: Path, *, end: date = date(2026, 1, 10)) -> tuple[ExperimentStorage, Path]:
    storage = ExperimentStorage(tmp_path / "experiments")
    exp = Experiment(
        "run",
        date(2026, 1, 1),
        end,
        (
            PortfolioConfig("Control", PortfolioType.CONTROL, "100", control_ticker="AAPL"),
            PortfolioConfig("AI", PortfolioType.AI_MANAGED, "100", strategy="hold"),
        ),
    )
    return storage, storage.create(exp)


def test_closed_market_stops_after_due_finalization(tmp_path: Path) -> None:
    storage, active = experiment(tmp_path, end=date(2026, 1, 9))
    market = FakeMarket(is_open=False)
    DailyRunner(storage, market, FakeAI(), today=lambda: date(2026, 1, 10)).run()
    assert not active.exists()
    assert (storage.finished / "run").is_dir()
    assert market.status_calls == 1


def test_finalization_uses_saved_valuation_without_closed_market_quote(tmp_path: Path) -> None:
    storage, active = experiment(tmp_path, end=date(2026, 1, 2))
    market, ai = FakeMarket(), FakeAI()
    DailyRunner(storage, market, ai, today=lambda: date(2026, 1, 1)).run()
    quote_count = len(market.quotes)
    market.is_open = False
    DailyRunner(storage, market, ai, today=lambda: date(2026, 1, 2)).run()
    assert len(market.quotes) == quote_count
    assert not active.exists()
    with (storage.finished / "run" / "Control_state.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        assert [row["date"] for row in csv.DictReader(handle)] == ["2026-01-01", "2026-01-02"]


def test_starting_control_initializes_and_same_date_is_idempotent(tmp_path: Path) -> None:
    storage, active = experiment(tmp_path)
    market, ai = FakeMarket(), FakeAI()
    runner = DailyRunner(storage, market, ai, today=lambda: date(2026, 1, 1))
    runner.run()
    runner.run()
    with (active / "Control_state.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["holdings"] == '{"AAPL":"10.000000"}'
    assert ai.calls == 1


def test_portfolio_errors_include_experiment_and_portfolio(tmp_path: Path) -> None:
    class BrokenMarket(FakeMarket):
        def quote(self, ticker: Ticker | str) -> Quote:
            raise RuntimeError("quote down")

    storage, _ = experiment(tmp_path)
    runner = DailyRunner(storage, BrokenMarket(), FakeAI(), today=lambda: date(2026, 1, 1))
    with pytest.raises(DailyRunError, match="run/Control"):
        runner.run()
