import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from ai_stock_trader.ai_manager import (
    MODEL_NAME,
    AIDecisionManager,
    build_decision_prompt,
    parse_ai_response,
)
from ai_stock_trader.errors import AIDecisionError, ConfigurationError
from ai_stock_trader.market_data import MarketNews, Quote
from ai_stock_trader.models import PortfolioState, Ticker


class FakeMarket:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def quote(self, ticker: Ticker | str) -> Quote:
        normalized = Ticker(str(ticker))
        self.calls.append(str(normalized))
        return Quote(
            normalized,
            Decimal("10.00"),
            __import__("datetime").datetime.now(__import__("datetime").UTC),
        )


class FakeAI:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.prompts: list[str] = []
        self.tools: list[object] = []

    def complete(self, prompt: str, tools: list[object]) -> object:
        self.prompts.append(prompt)
        self.tools = tools
        # This fake models the SDK's tool round: the model requests a quote
        # before returning its final JSON response.
        for item in tools:
            function = item["function"]  # type: ignore[index]
            function["execute"]({"ticker": "AAPL"}, None)
        return self.responses.pop(0)


def valid_response() -> dict[str, object]:
    return {
        "trades": [{"action": "buy", "ticker": "AAPL", "quantity": "2"}],
        "explanation": "Buy on strength.",
    }


def test_prompt_contains_strategy_state_date_and_news() -> None:
    prompt = build_decision_prompt(
        strategy="Prefer steady growth.",
        state=PortfolioState(cash="100"),
        as_of=date(2026, 1, 2),
        news=(
            MarketNews(
                "general",
                datetime(2026, 1, 2, tzinfo=UTC),
                "Headline",
                1,
                (),
                "Source",
                "Summary",
                "https://example.test",
            ),
        ),
    )
    assert "Prefer steady growth." in prompt
    assert "2026-01-02" in prompt
    assert "Headline" in prompt
    assert "buy" in prompt and "sell" in prompt and "quote" in prompt


def test_parse_rejects_unknown_fields_and_malformed_actions() -> None:
    with pytest.raises(AIDecisionError, match="unknown field"):
        parse_ai_response(json.dumps({**valid_response(), "extra": True}))
    with pytest.raises(AIDecisionError, match="action"):
        parse_ai_response(
            {"trades": [{"action": "hold", "ticker": "AAPL", "quantity": "1"}], "explanation": "x"}
        )


def test_manager_uses_quote_tool_then_returns_executed_state() -> None:
    market = FakeMarket()
    ai = FakeAI([valid_response()])
    result = AIDecisionManager(ai, market).run(
        strategy="Prefer growth.", state=PortfolioState(cash="100"), as_of=date(2026, 1, 2), news=()
    )
    assert result.decision.trades[0].ticker == Ticker("AAPL")
    assert result.state.cash == Decimal("80.00")
    assert market.calls == ["AAPL"]
    assert ai.tools
    assert "Prefer growth." in ai.prompts[0]


def test_manager_retries_complete_attempt_and_stops_at_three() -> None:
    market = FakeMarket()
    ai = FakeAI([{"trades": [], "explanation": "bad", "unknown": 1}] * 3)
    with pytest.raises(AIDecisionError, match="3 attempts"):
        AIDecisionManager(ai, market).run(
            strategy="x", state=PortfolioState(cash="100"), as_of=date(2026, 1, 2), news=()
        )
    assert len(ai.prompts) == 3


def test_missing_openrouter_key_fails_fast() -> None:
    assert MODEL_NAME == "nvidia/nemotron-3.5-lightning"
    with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY"):
        AIDecisionManager.from_environment(FakeMarket(), environ={})
