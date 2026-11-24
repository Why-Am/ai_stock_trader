"""Pure portfolio calculations and state transitions.

This module does not call a market-data service. Callers provide the quote used
for each operation, which keeps trade behavior deterministic and straightforward
to test with fake market data.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_DOWN, Decimal

from .errors import DomainValidationError
from .models import Action, Money, PortfolioState, Price, Shares, Ticker, Trade


def _quote(value: Decimal | int | str | None, ticker: Ticker) -> Decimal:
    if value is None:
        raise DomainValidationError(f"missing quote for {ticker}")
    try:
        return Price(value)
    except DomainValidationError as exc:
        raise DomainValidationError(f"invalid quote for {ticker}: {exc}") from exc


def apply_trade(
    state: PortfolioState,
    trade: Trade,
    price: Decimal | int | str | None,
) -> PortfolioState:
    """Return the state after ``trade`` or raise before changing ``state``."""
    quote = _quote(price, trade.ticker)
    quantity = trade.quantity
    holdings = dict(state.holdings)
    current_shares = holdings.get(trade.ticker, Decimal("0"))

    if trade.action is Action.BUY:
        cost = Money(quantity * quote)
        if cost > state.cash:
            raise DomainValidationError("insufficient cash for buy")
        holdings[trade.ticker] = Shares(current_shares + quantity)
        cash = Money(state.cash - cost)
    elif trade.action is Action.SELL:
        if current_shares < quantity:
            raise DomainValidationError("insufficient holdings for sell")
        remaining = Shares(current_shares - quantity)
        if remaining:
            holdings[trade.ticker] = remaining
        else:
            holdings.pop(trade.ticker, None)
        cash = Money(state.cash + Money(quantity * quote))
    else:  # The Trade model normally makes this unreachable.
        raise DomainValidationError(f"unsupported trade action: {trade.action}")

    return PortfolioState(cash=cash, holdings=holdings)


def initialize_control_portfolio(
    state: PortfolioState,
    ticker: Ticker | str,
    price: Decimal | int | str | None,
) -> PortfolioState:
    """Buy the maximum six-decimal share quantity affordable with all cash.

    Flooring the quantity is intentional: rounding a fractional quantity up
    could make the calculated purchase cost exceed the available balance.
    """
    if state.holdings:
        raise DomainValidationError("control portfolio must be uninitialized")
    normalized_ticker = Ticker(str(ticker))
    quote = _quote(price, normalized_ticker)
    quantity = (state.cash / quote).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    quantity = Shares(quantity)
    cost = Money(quantity * quote)
    remaining = Money(state.cash - cost)
    holdings = {normalized_ticker: quantity} if quantity else {}
    return PortfolioState(cash=remaining, holdings=holdings, prices={normalized_ticker: quote})


def value_portfolio(
    state: PortfolioState,
    quotes: Mapping[Ticker | str, Decimal | int | str],
) -> PortfolioState:
    """Return ``state`` valued at current quotes for every held ticker."""
    normalized_quotes = {Ticker(str(ticker)): value for ticker, value in quotes.items()}
    prices: dict[Ticker, Decimal] = {}
    for ticker in state.holdings:
        if ticker not in normalized_quotes:
            raise DomainValidationError(f"missing quote for {ticker}")
        prices[ticker] = _quote(normalized_quotes[ticker], ticker)
    return PortfolioState(cash=state.cash, holdings=state.holdings, prices=prices)
