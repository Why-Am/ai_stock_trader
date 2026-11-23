import csv
import json
from datetime import date
from pathlib import Path

import pytest
from ai_stock_trader.errors import StorageError
from ai_stock_trader.models import (
    Action,
    Experiment,
    PortfolioConfig,
    PortfolioState,
    PortfolioType,
    Ticker,
    Trade,
)
from ai_stock_trader.storage import (
    STATE_HEADERS,
    ExperimentStorage,
)


def make_experiment() -> Experiment:
    return Experiment(
        name="April run",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        portfolios=(
            PortfolioConfig("AI", PortfolioType.AI_MANAGED, "100.00", strategy="# Buy carefully"),
            PortfolioConfig("Control", PortfolioType.CONTROL, "50.00", control_ticker="MSFT"),
        ),
    )


def test_create_discover_and_load_experiment(tmp_path: Path) -> None:
    storage = ExperimentStorage(tmp_path / "experiments")
    path = storage.create(make_experiment())

    assert path == tmp_path / "experiments" / "active" / "April run"
    assert storage.discover() == (make_experiment(),)
    assert storage.load(path) == make_experiment()
    assert (path / "AI_strategy.md").read_text(encoding="utf-8") == "# Buy carefully"
    assert (path / "Control_state.csv").read_text(encoding="utf-8").splitlines() == [
        ",".join(STATE_HEADERS)
    ]


def test_state_and_trade_rows_have_stable_format(tmp_path: Path) -> None:
    storage = ExperimentStorage(tmp_path / "experiments")
    path = storage.create(make_experiment())
    state = PortfolioState(cash="12.34", holdings={Ticker("AAPL"): "1.5"}, prices={"AAPL": "2"})
    storage.append_state(path, "AI", date(2026, 4, 2), state)
    storage.append_trades(
        path, "AI", date(2026, 4, 2), [Trade(Action.BUY, "AAPL", "0.5")], "reason"
    )

    with (path / "AI_state.csv").open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == [
            {
                "date": "2026-04-02",
                "cash": "12.34",
                "total_value": "15.34",
                "holdings": '{"AAPL":"1.500000"}',
            },
        ]
    with (path / "AI_trades.csv").open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == [
            {
                "date": "2026-04-02",
                "action": "buy",
                "ticker": "AAPL",
                "quantity": "0.500000",
                "explanation": "reason",
            },
        ]


def test_create_rejects_collision_without_overwriting(tmp_path: Path) -> None:
    storage = ExperimentStorage(tmp_path / "experiments")
    storage.create(make_experiment())
    with pytest.raises(StorageError, match="already exists"):
        storage.create(make_experiment())


def test_load_rejects_unknown_files_and_malformed_metadata(tmp_path: Path) -> None:
    storage = ExperimentStorage(tmp_path / "experiments")
    path = storage.create(make_experiment())
    (path / "unexpected.txt").write_text("x", encoding="utf-8")
    with pytest.raises(StorageError, match="unexpected"):
        storage.load(path)

    (path / "unexpected.txt").unlink()
    metadata = json.loads((path / "April run.json").read_text(encoding="utf-8"))
    metadata["end_date"] = "not-a-date"
    (path / "April run.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(StorageError, match="metadata"):
        storage.load(path)


def test_strategy_is_not_rewritten_by_load(tmp_path: Path) -> None:
    storage = ExperimentStorage(tmp_path / "experiments")
    path = storage.create(make_experiment())
    strategy = path / "AI_strategy.md"
    strategy.write_text("edited by owner", encoding="utf-8")
    loaded = storage.load(path)
    assert loaded.portfolios[0].strategy == "edited by owner"
    assert strategy.read_text(encoding="utf-8") == "edited by owner"


def test_append_rejects_portfolio_path_escape(tmp_path: Path) -> None:
    storage = ExperimentStorage(tmp_path / "experiments")
    path = storage.create(make_experiment())
    with pytest.raises(StorageError, match="invalid portfolio name"):
        storage.append_state(path, "../outside", date(2026, 4, 2), PortfolioState(cash="1"))
