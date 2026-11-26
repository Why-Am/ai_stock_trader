from decimal import Decimal

import pytest
from ai_stock_trader.errors import DomainValidationError
from ai_stock_trader.models import Action, PortfolioState, Ticker, Trade
from ai_stock_trader.trading import apply_trade, initialize_control_portfolio, value_portfolio


def test_buy_is_pure_and_updates_cash_and_holdings() -> None:
    original = PortfolioState(cash="100", holdings={"AAPL": "1"})

    updated = apply_trade(original, Trade(Action.BUY, "AAPL", "2.5"), "10")

    assert original == PortfolioState(cash="100", holdings={"AAPL": "1"})
    assert updated.cash == Decimal("75.00")
    assert updated.holdings == {Ticker("AAPL"): Decimal("3.500000")}
    assert updated.prices is None


def test_sell_is_pure_and_removes_zero_quantity_holding() -> None:
    original = PortfolioState(cash="5", holdings={"AAPL": "2"})

    updated = apply_trade(original, Trade(Action.SELL, "AAPL", "2"), "12.50")

    assert original.holdings == {Ticker("AAPL"): Decimal("2.000000")}
    assert updated.cash == Decimal("30.00")
    assert updated.holdings == {}


@pytest.mark.parametrize(
    ("state", "trade", "price", "message"),
    [
        (PortfolioState(cash="10"), Trade(Action.BUY, "AAPL", "1"), "11", "insufficient cash"),
        (
            PortfolioState(cash="10", holdings={"AAPL": "1"}),
            Trade(Action.SELL, "AAPL", "2"),
            "11",
            "insufficient holdings",
        ),
        (PortfolioState(cash="10"), Trade(Action.BUY, "AAPL", "1"), "0", "price"),
    ],
)
def test_invalid_trade_is_rejected_without_mutation(
    state: PortfolioState, trade: Trade, price: str, message: str
) -> None:
    original_cash = state.cash
    original_holdings = dict(state.holdings)
    with pytest.raises(DomainValidationError, match=message):
        apply_trade(state, trade, price)
    assert state.cash == original_cash
    assert state.holdings == original_holdings


def test_trade_requires_a_known_ticker_price() -> None:
    with pytest.raises(DomainValidationError, match="quote"):
        apply_trade(PortfolioState(cash="10"), Trade(Action.BUY, "AAPL", "1"), None)


def test_control_initialization_spends_all_possible_cash_deterministically() -> None:
    initialized = initialize_control_portfolio(PortfolioState(cash="100"), "AAPL", "33.33")

    assert initialized.cash == Decimal("0.00")
    assert initialized.holdings == {Ticker("AAPL"): Decimal("3.000300")}
    assert initialized.total_value == Decimal("100.00")


def test_valuation_requires_a_valid_quote_for_every_holding() -> None:
    state = PortfolioState(cash="10", holdings={"AAPL": "2", "MSFT": "1"})

    with pytest.raises(DomainValidationError, match="missing quote"):
        value_portfolio(state, {"AAPL": "5"})

    valued = value_portfolio(state, {"AAPL": "5", "MSFT": "20"})
    assert valued.total_value == Decimal("40.00")
    assert valued.prices == {Ticker("AAPL"): Decimal("5.00"), Ticker("MSFT"): Decimal("20.00")}
