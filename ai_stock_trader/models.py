"""Validated, serialization-friendly domain models.

Decimal values are quantized at the boundary: money and prices use cents, while
fractional shares use six decimal places. This makes CSV/JSON output stable and
prevents binary floating-point rounding from changing a portfolio balance.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum
from zoneinfo import ZoneInfo

from .errors import DomainValidationError

ET = ZoneInfo("America/New_York")
MONEY_QUANTUM = Decimal("0.01")
SHARES_QUANTUM = Decimal("0.000001")
PRICE_QUANTUM = Decimal("0.01")
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")
_TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")


def _decimal(value: Decimal | int | str, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainValidationError(f"{label} must be a decimal number") from exc
    if not result.is_finite():
        raise DomainValidationError(f"{label} must be finite")
    return result


def Money(value: Decimal | int | str) -> Decimal:
    """Return nonnegative currency rounded to two decimal places."""
    result = _decimal(value, "money").quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    if result < 0:
        raise DomainValidationError("money must be nonnegative")
    return result


def Shares(value: Decimal | int | str) -> Decimal:
    """Return nonnegative fractional shares rounded to six decimal places."""
    result = _decimal(value, "shares").quantize(SHARES_QUANTUM, rounding=ROUND_HALF_UP)
    if result < 0:
        raise DomainValidationError("shares must be nonnegative")
    return result


def Price(value: Decimal | int | str) -> Decimal:
    """Return a positive quote rounded to two decimal places."""
    result = _decimal(value, "price").quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)
    if result <= 0:
        raise DomainValidationError("price must be positive")
    return result


@dataclass(frozen=True, order=True)
class Ticker:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        if not _TICKER_PATTERN.fullmatch(normalized):
            raise DomainValidationError(f"invalid ticker: {self.value!r}")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


class PortfolioType(StrEnum):
    AI_MANAGED = "ai-managed"
    CONTROL = "control"


class Action(StrEnum):
    BUY = "buy"
    SELL = "sell"


def _name(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized or not _NAME_PATTERN.fullmatch(normalized):
        raise DomainValidationError(f"invalid {label}: use letters, numbers, spaces, '-' or '_'")
    return normalized


def today_et(now: datetime | None = None) -> date:
    """Return the calendar date in Eastern Time, independent of machine TZ."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        raise DomainValidationError("now must be timezone-aware")
    return current.astimezone(ET).date()


@dataclass(frozen=True)
class PortfolioConfig:
    name: str
    portfolio_type: PortfolioType
    starting_cash: Decimal
    strategy: str | None = None
    control_ticker: Ticker | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _name(self.name, "portfolio name"))
        try:
            object.__setattr__(self, "portfolio_type", PortfolioType(self.portfolio_type))
        except ValueError as exc:
            raise DomainValidationError(f"invalid portfolio type: {self.portfolio_type!r}") from exc
        object.__setattr__(self, "starting_cash", Money(self.starting_cash))
        if self.portfolio_type is PortfolioType.CONTROL:
            if self.control_ticker is None:
                raise DomainValidationError("control portfolio requires a ticker")
            object.__setattr__(self, "control_ticker", Ticker(str(self.control_ticker)))
            if self.strategy is not None:
                raise DomainValidationError("control portfolio cannot have a strategy")
        elif self.portfolio_type is PortfolioType.AI_MANAGED:
            if not self.strategy or not self.strategy.strip():
                raise DomainValidationError("AI-managed portfolio requires a strategy")
            if self.control_ticker is not None:
                raise DomainValidationError("AI-managed portfolio cannot have a control ticker")

    def to_dict(self) -> dict[str, str]:
        result = {
            "name": self.name,
            "type": self.portfolio_type.value,
            "starting_cash": f"{self.starting_cash:.2f}",
        }
        if self.strategy is not None:
            result["strategy"] = self.strategy
        if self.control_ticker is not None:
            result["control_ticker"] = str(self.control_ticker)
        return result


@dataclass(frozen=True)
class Experiment:
    name: str
    start_date: date
    end_date: date
    portfolios: tuple[PortfolioConfig, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _name(self.name, "experiment name"))
        if not isinstance(self.start_date, date) or isinstance(self.start_date, datetime):
            raise DomainValidationError("start date must be a calendar date")
        if not isinstance(self.end_date, date) or isinstance(self.end_date, datetime):
            raise DomainValidationError("end date must be a calendar date")
        if self.end_date < self.start_date:
            raise DomainValidationError("end date must be on or after start date")
        names = [portfolio.name.casefold() for portfolio in self.portfolios]
        if len(names) != len(set(names)):
            raise DomainValidationError("portfolio names must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "portfolios": [p.to_dict() for p in self.portfolios],
        }


@dataclass(frozen=True)
class Trade:
    action: Action
    ticker: Ticker
    quantity: Decimal

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "action", Action(self.action))
        except ValueError as exc:
            raise DomainValidationError(f"invalid trade action: {self.action!r}") from exc
        object.__setattr__(self, "ticker", Ticker(str(self.ticker)))
        object.__setattr__(self, "quantity", Shares(self.quantity))
        if self.quantity == 0:
            raise DomainValidationError("trade quantity must be positive")

    def to_dict(self) -> dict[str, str]:
        return {
            "action": self.action.value,
            "ticker": str(self.ticker),
            "quantity": f"{self.quantity:.6f}",
        }


@dataclass(frozen=True)
class AITradeExplanation:
    """A concise, human-readable explanation attached to an AI decision."""

    summary: str

    def __post_init__(self) -> None:
        summary = self.summary.strip()
        if not summary:
            raise DomainValidationError("AI trade explanation cannot be empty")
        if len(summary) > 2000:
            raise DomainValidationError("AI trade explanation must be at most 2000 characters")
        object.__setattr__(self, "summary", summary)


@dataclass(frozen=True)
class AIDecision:
    trades: tuple[Trade, ...]
    explanation: AITradeExplanation

    def to_dict(self) -> dict[str, object]:
        return {
            "trades": [trade.to_dict() for trade in self.trades],
            "explanation": self.explanation.summary,
        }


@dataclass(frozen=True)
class PortfolioState:
    cash: Decimal
    holdings: Mapping[Ticker, Decimal] = field(default_factory=dict)
    total_value: Decimal | None = None
    prices: Mapping[Ticker, Decimal] | None = None

    def __post_init__(self) -> None:
        cash = Money(self.cash)
        holdings = {
            Ticker(str(ticker)): Shares(quantity) for ticker, quantity in self.holdings.items()
        }
        prices = (
            None
            if self.prices is None
            else {Ticker(str(ticker)): Price(price) for ticker, price in self.prices.items()}
        )
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "holdings", holdings)
        object.__setattr__(self, "prices", prices)
        if prices is not None:
            if set(holdings) - set(prices):
                raise DomainValidationError("a current price is required for every holding")
            calculated = Money(
                cash + sum((holdings[ticker] * prices[ticker] for ticker in holdings), Decimal("0"))
            )
            if self.total_value is not None and Money(self.total_value) != calculated:
                raise DomainValidationError(
                    f"total value must equal cash plus holdings value ({calculated})"
                )
            object.__setattr__(self, "total_value", calculated)
        elif self.total_value is not None:
            object.__setattr__(self, "total_value", Money(self.total_value))

    def to_dict(self) -> dict[str, object]:
        if self.total_value is None:
            raise DomainValidationError("total value is required for serialization")
        return {
            "cash": f"{self.cash:.2f}",
            "holdings": {str(t): f"{q:.6f}" for t, q in sorted(self.holdings.items())},
            "total_value": f"{self.total_value:.2f}",
        }
