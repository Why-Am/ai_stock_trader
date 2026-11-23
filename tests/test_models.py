from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from ai_stock_trader.errors import DomainValidationError
from ai_stock_trader.models import (
    Action,
    Experiment,
    PortfolioConfig,
    PortfolioState,
    PortfolioType,
    Price,
    Shares,
    Ticker,
    Trade,
    today_et,
)


def test_money_like_values_are_decimal_and_serializable() -> None:
    state = PortfolioState(
        cash=Decimal("100.005"),
        holdings={Ticker("aapl"): Decimal("1.23456789")},
        prices={Ticker("AAPL"): Decimal("10.12345")},
    )

    assert state.cash == Decimal("100.01")
    assert state.holdings == {Ticker("AAPL"): Shares("1.234568")}
    assert state.total_value == Price("112.50")
    assert state.to_dict() == {
        "cash": "100.01",
        "holdings": {"AAPL": "1.234568"},
        "total_value": "112.50",
    }


def test_state_rejects_total_value_that_does_not_match_prices() -> None:
    with pytest.raises(DomainValidationError, match="total value"):
        PortfolioState(
            cash="100",
            holdings={"AAPL": "2"},
            prices={"AAPL": "10"},
            total_value="101",
        )


@pytest.mark.parametrize(
    ("factory", "value"),
    [
        (Ticker, "AAPL!"),
        (Shares, "-1"),
        (Price, "0"),
        (PortfolioConfig, ""),
    ],
)
def test_domain_values_reject_invalid_input(factory, value) -> None:
    with pytest.raises(DomainValidationError):
        if factory is PortfolioConfig:
            factory(
                name=value,
                portfolio_type=PortfolioType.CONTROL,
                starting_cash="1",
                control_ticker="AAPL",
            )
        else:
            factory(value)


def test_trade_and_experiment_serialize_with_typed_rules() -> None:
    portfolio = PortfolioConfig(
        name="Control",
        portfolio_type=PortfolioType.CONTROL,
        starting_cash="1000",
        control_ticker="msft",
    )
    experiment = Experiment(
        name="April experiment",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        portfolios=(portfolio,),
    )
    trade = Trade(action=Action.BUY, ticker="MSFT", quantity="0.5")

    assert trade.to_dict() == {"action": "buy", "ticker": "MSFT", "quantity": "0.500000"}
    assert experiment.to_dict() == {
        "name": "April experiment",
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "portfolios": [portfolio.to_dict()],
    }


def test_string_enums_render_as_their_serialized_values() -> None:
    assert str(Action.BUY) == "buy"
    assert str(PortfolioType.CONTROL) == "control"


def test_experiment_dates_and_portfolio_names_are_validated() -> None:
    with pytest.raises(DomainValidationError, match="end date"):
        Experiment(name="x", start_date=date(2026, 5, 2), end_date=date(2026, 5, 1), portfolios=())

    with pytest.raises(DomainValidationError, match="unique"):
        Experiment(
            name="x",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 2),
            portfolios=(
                PortfolioConfig("same", PortfolioType.AI_MANAGED, "1", strategy="s"),
                PortfolioConfig("same", PortfolioType.AI_MANAGED, "1", strategy="s"),
            ),
        )


def test_today_et_uses_eastern_time_and_dst() -> None:
    assert today_et(datetime(2026, 3, 8, 4, 30, tzinfo=ZoneInfo("UTC"))) == date(2026, 3, 7)
    assert today_et(datetime(2026, 3, 8, 5, 30, tzinfo=ZoneInfo("UTC"))) == date(2026, 3, 8)
