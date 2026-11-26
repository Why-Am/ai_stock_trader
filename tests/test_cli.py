from datetime import datetime
from decimal import Decimal

import create_new_experiment
import run_daily
from ai_stock_trader.errors import DailyRunError
from ai_stock_trader.market_data import Quote
from ai_stock_trader.models import Ticker


class FakeMarket:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.lookups: list[str] = []

    def quote(self, ticker: Ticker | str) -> Quote:
        symbol = Ticker(str(ticker))
        self.lookups.append(str(symbol))
        if self.fail:
            raise RuntimeError("unavailable")
        return Quote(symbol, Decimal("10"), datetime.now().astimezone())


def test_creation_prompts_validates_ticker_then_creates(tmp_path, monkeypatch) -> None:
    answers = iter(["Study", "2026-01-01", "2026-01-03", "1", "Index", "control", "100", "AAPL"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    market = FakeMarket()
    code = create_new_experiment.main(["--experiments-root", str(tmp_path)], market=market)
    assert code == 0
    assert market.lookups == ["AAPL"]
    assert (tmp_path / "active" / "Study" / "Index_state.csv").exists()


def test_invalid_quote_leaves_no_partial_experiment(tmp_path, monkeypatch) -> None:
    answers = iter(["Study", "2026-01-01", "2026-01-03", "1", "Index", "control", "100", "AAPL"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert (
        create_new_experiment.main(
            ["--experiments-root", str(tmp_path)], market=FakeMarket(fail=True)
        )
        == 1
    )
    assert not (tmp_path / "active" / "Study").exists()


def test_creation_rejects_end_before_start_without_creating(tmp_path, monkeypatch) -> None:
    answers = iter(["Study", "2026-01-03", "2026-01-01"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert (
        create_new_experiment.main(["--experiments-root", str(tmp_path)], market=FakeMarket()) == 1
    )
    assert not (tmp_path / "active" / "Study").exists()


def test_daily_entrypoint_returns_nonzero_for_operational_error(monkeypatch) -> None:
    class BrokenRunner:
        def run(self) -> None:
            raise DailyRunError("market down")

    monkeypatch.setattr(run_daily, "build_runner", lambda *_: BrokenRunner())
    assert run_daily.main([]) == 1
