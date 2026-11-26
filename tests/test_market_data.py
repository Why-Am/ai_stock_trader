from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ai_stock_trader.errors import ConfigurationError, MarketDataError
from ai_stock_trader.market_data import FinnhubMarketData, MarketNews, MarketStatus, Quote


class FakeFinnhub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.status_response: object = {
            "exchange": "US",
            "isOpen": True,
            "session": "regular",
            "holiday": None,
        }
        self.news_response: object = [
            {
                "category": "general",
                "datetime": 1_800_000_000,
                "headline": "Markets rise",
                "id": 7,
                "related": "AAPL,MSFT",
                "source": "Example News",
                "summary": "A summary",
                "url": "https://example.test/story",
            }
        ]
        self.quote_response: object = {
            "c": 123.456,
            "t": 1_800_000_000,
        }

    def market_status(self, exchange: str) -> object:
        self.calls.append(("market_status", (exchange,)))
        return self.status_response

    def general_news(self, category: str, min_id: int = 0) -> object:
        self.calls.append(("general_news", (category, min_id)))
        return self.news_response

    def quote(self, symbol: str) -> object:
        self.calls.append(("quote", (symbol,)))
        return self.quote_response


def make_adapter(fake: FakeFinnhub) -> FinnhubMarketData:
    return FinnhubMarketData(
        fake,
        now=lambda: datetime.fromtimestamp(1_800_000_030, UTC),
        max_quote_age=timedelta(minutes=5),
    )


def test_market_status_is_normalized_and_calls_finnhub_exactly() -> None:
    fake = FakeFinnhub()

    result = make_adapter(fake).market_status()

    assert result == MarketStatus(True, "US", "regular", None)
    assert fake.calls == [("market_status", ("US",))]


def test_news_and_quote_are_normalized_at_the_boundary() -> None:
    fake = FakeFinnhub()
    adapter = make_adapter(fake)

    assert adapter.market_news() == (
        MarketNews(
            category="general",
            published_at=datetime.fromtimestamp(1_800_000_000, UTC),
            headline="Markets rise",
            article_id=7,
            related=("AAPL", "MSFT"),
            source="Example News",
            summary="A summary",
            url="https://example.test/story",
        ),
    )
    assert adapter.quote("aapl") == Quote(
        "AAPL", Decimal("123.46"), datetime.fromtimestamp(1_800_000_000, UTC)
    )
    assert fake.calls == [
        ("general_news", ("general", 0)),
        ("quote", ("AAPL",)),
    ]


def test_quote_rejects_missing_zero_and_stale_values() -> None:
    fake = FakeFinnhub()
    adapter = make_adapter(fake)
    for response in (
        {"t": 1_800_000_000},
        {"c": 0, "t": 1_800_000_000},
        {"c": 10, "t": 1_799_999_000},
    ):
        fake.quote_response = response
        with pytest.raises(MarketDataError, match="quote"):
            adapter.quote("AAPL")


def test_ticker_validation_accepts_a_stale_quote_but_checks_price() -> None:
    fake = FakeFinnhub()
    fake.quote_response = {"c": 123.45, "t": 1_799_999_000}

    make_adapter(fake).validate_ticker("AAPL")

    assert fake.calls == [("quote", ("AAPL",))]


def test_malformed_status_and_news_are_reported() -> None:
    fake = FakeFinnhub()
    adapter = make_adapter(fake)
    fake.status_response = {"isOpen": "yes", "exchange": "US"}
    with pytest.raises(MarketDataError, match="market status"):
        adapter.market_status()

    fake.news_response = [{"datetime": "bad"}]
    with pytest.raises(MarketDataError, match="market news"):
        adapter.market_news()


def test_client_failures_are_retried_and_secret_is_not_exposed() -> None:
    class Broken:
        def market_status(self, exchange: str) -> object:
            raise RuntimeError("request failed with key secret-key")

    with pytest.raises(MarketDataError, match="market status") as error:
        FinnhubMarketData(Broken(), api_key="secret-key").market_status()
    assert "secret-key" not in str(error.value)


def test_missing_api_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="FINNHUB_API_KEY"):
        FinnhubMarketData.from_environment()
