"""Finnhub market-data adapter.

The rest of the application depends on the small records in this module rather
than on Finnhub's response dictionaries.  This boundary is also where bad or
stale vendor data is rejected, so trading code never has to guess what a quote
means.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol, cast

import finnhub

from .errors import ConfigurationError, MarketDataError
from .models import Price, Ticker


class FinnhubClient(Protocol):
    def market_status(self, exchange: str) -> object: ...

    def general_news(self, category: str, min_id: int = 0) -> object: ...

    def quote(self, symbol: str) -> object: ...


@dataclass(frozen=True)
class MarketStatus:
    is_open: bool
    exchange: str
    session: str | None
    holiday: str | None


@dataclass(frozen=True)
class MarketNews:
    category: str
    published_at: datetime
    headline: str
    article_id: int
    related: tuple[str, ...]
    source: str
    summary: str
    url: str


@dataclass(frozen=True)
class Quote:
    ticker: Ticker
    current_price: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", Ticker(str(self.ticker)))
        object.__setattr__(self, "current_price", Price(str(self.current_price)))
        if self.timestamp.tzinfo is None:
            raise MarketDataError("quote timestamp must be timezone-aware")


class FinnhubMarketData:
    """Translate the required Finnhub endpoints into validated records."""

    def __init__(
        self,
        client: FinnhubClient,
        *,
        api_key: str | None = None,
        now: Callable[[], datetime] | None = None,
        max_quote_age: timedelta = timedelta(minutes=15),
        attempts: int = 3,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be positive")
        self._client = client
        self._api_key = api_key
        self._now = now or (lambda: datetime.now(UTC))
        self._max_quote_age = max_quote_age
        self._attempts = attempts

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        now: Callable[[], datetime] | None = None,
        max_quote_age: timedelta = timedelta(minutes=15),
        attempts: int = 3,
    ) -> FinnhubMarketData:
        values = os.environ if environ is None else environ
        api_key = values.get("FINNHUB_API_KEY", "").strip()
        if not api_key:
            raise ConfigurationError("FINNHUB_API_KEY is required to access Finnhub")
        return cls(
            finnhub.Client(api_key=api_key),
            api_key=api_key,
            now=now,
            max_quote_age=max_quote_age,
            attempts=attempts,
        )

    def market_status(self) -> MarketStatus:
        response = self._call("market status", lambda: self._client.market_status("US"))
        try:
            data = _mapping(response, "market status")
            is_open = data["isOpen"]
            exchange = data["exchange"]
            session = data.get("session")
            holiday = data.get("holiday")
            if not isinstance(is_open, bool) or not isinstance(exchange, str) or not exchange:
                raise ValueError("isOpen and exchange have invalid types")
            if session is not None and not isinstance(session, str):
                raise ValueError("session has an invalid type")
            if holiday is not None and not isinstance(holiday, str):
                raise ValueError("holiday has an invalid type")
            return MarketStatus(is_open, exchange, session, holiday)
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(f"invalid market status response: {exc}") from exc

    def market_news(self, *, category: str = "general", min_id: int = 0) -> tuple[MarketNews, ...]:
        response = self._call("market news", lambda: self._client.general_news(category, min_id))
        try:
            if not isinstance(response, list):
                raise ValueError("response must be a list")
            return tuple(_news_item(item) for item in cast(list[object], response))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise MarketDataError(f"invalid market news response: {exc}") from exc

    def quote(self, ticker: Ticker | str) -> Quote:
        return self._quote(ticker, require_fresh=True)

    def validate_ticker(self, ticker: Ticker | str) -> None:
        """Check Finnhub recognizes the symbol without requiring a live-session quote."""
        self._quote(ticker, require_fresh=False)

    def _quote(self, ticker: Ticker | str, *, require_fresh: bool) -> Quote:
        normalized = Ticker(str(ticker))
        response = self._call("quote", lambda: self._client.quote(str(normalized)))
        try:
            data = _mapping(response, "quote")
            current = data["c"]
            timestamp = _timestamp(data["t"])
            if not isinstance(current, (int, float, str)) or isinstance(current, bool):
                raise ValueError("current price has an invalid type")
            if isinstance(current, float) and not math.isfinite(current):
                raise ValueError("current price must be finite")
            age = self._now() - timestamp
            # Freshness matters for trading. Ticker validation only checks that
            # Finnhub returns a usable price; the last close is expected off-hours.
            if require_fresh and (age < timedelta(0) or age > self._max_quote_age):
                raise ValueError(f"quote is stale (age: {age})")
            return Quote(normalized, Decimal(str(current)), timestamp)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise MarketDataError(f"invalid quote response for {normalized}: {exc}") from exc

    def _call(self, operation: str, request: Callable[[], object]) -> object:
        last_error: Exception | None = None
        for _ in range(self._attempts):
            try:
                return request()
            except Exception as exc:  # Vendor clients expose several exception types.
                last_error = exc
        raise MarketDataError(
            f"{operation} request failed after {self._attempts} attempts"
        ) from last_error


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} response must be an object")
    return cast(Mapping[str, object], value)


def _timestamp(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("timestamp must be a Unix number")
    return datetime.fromtimestamp(value, UTC)


def _news_item(value: object) -> MarketNews:
    data = _mapping(value, "market news")
    published_at = _timestamp(data["datetime"])
    related_value = data.get("related", "")
    if not isinstance(related_value, str):
        raise ValueError("related has an invalid type")
    related = tuple(Ticker(symbol).value for symbol in related_value.split(",") if symbol.strip())
    category = data["category"]
    headline = data["headline"]
    article_id = data["id"]
    source = data["source"]
    summary = data["summary"]
    url = data["url"]
    text_fields = (category, headline, source, summary, url)
    if not all(isinstance(item, str) and item.strip() for item in text_fields):
        raise ValueError("news text fields must be nonempty strings")
    if isinstance(article_id, bool) or not isinstance(article_id, int):
        raise ValueError("id must be an integer")
    return MarketNews(
        cast(str, category),
        published_at,
        cast(str, headline),
        article_id,
        related,
        cast(str, source),
        cast(str, summary),
        cast(str, url),
    )
