"""AI trade decisions with strict parsing, quote tools, and bounded retries."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any, Protocol, cast

from openrouter_agent import OpenRouter, call_model, tool

from .errors import AIDecisionError, ConfigurationError, DomainValidationError
from .market_data import MarketNews, Quote
from .models import AIDecision, AITradeExplanation, PortfolioState, Ticker, Trade
from .trading import apply_trade

MODEL_NAME = "nvidia/nemotron-3.5-lightning"
MAX_ATTEMPTS = 3


class QuoteProvider(Protocol):
    def quote(self, ticker: Ticker | str) -> Quote: ...


class AIClient(Protocol):
    def complete(self, prompt: str, tools: list[object]) -> object: ...


class OpenRouterAIClient:
    """Small synchronous adapter around the SDK's async-capable model result."""

    def __init__(self, api_key: str, *, model: str = MODEL_NAME) -> None:
        self._client = OpenRouter(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, tools: list[object]) -> object:
        result = call_model(
            self._client,
            {"model": self._model, "input": prompt, "tools": tools},
        )
        return asyncio.run(result.get_text())


def build_decision_prompt(
    *, strategy: str, state: PortfolioState, as_of: date, news: Sequence[MarketNews]
) -> str:
    """Build a bounded prompt; quotes are intentionally available only as a tool."""
    news_lines = (
        "\n".join(f"- {item.headline}: {item.summary}" for item in news) or "- No news available."
    )
    state_payload = {
        "cash": f"{state.cash:.2f}",
        "holdings": {
            str(ticker): f"{quantity:.6f}" for ticker, quantity in sorted(state.holdings.items())
        },
        # A state before valuation is valid input to the decision prompt.
        "total_value": None if state.total_value is None else f"{state.total_value:.2f}",
    }
    return f"""You manage one stock portfolio on {as_of.isoformat()} ET.

IMMUTABLE STRATEGY:
{strategy}

CURRENT PORTFOLIO STATE:
{json.dumps(state_payload, sort_keys=True)}

MARKET NEWS:
{news_lines}

Rules:
- You may only propose buy or sell trades, with positive fractional quantities.
- Request every required current price with the quote tool; do not assume prices or use a market snapshot.
- Trades are checked against available cash and holdings in order.
- Return JSON with exactly these fields: trades (an array of action, ticker, quantity) and explanation.
- Keep explanation concise and summarized (under 2000 characters).
"""


def _object(value: object, label: str) -> Mapping[str, object]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AIDecisionError(f"AI response is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, Mapping):
        raise AIDecisionError(f"AI response must be an object, not {label}")
    return cast(Mapping[str, object], value)


def parse_ai_response(response: object) -> AIDecision:
    """Parse only the documented JSON shape and translate errors safely."""
    data = _object(response, type(response).__name__)
    unknown = set(data) - {"trades", "explanation"}
    if unknown:
        raise AIDecisionError(f"unknown field: {sorted(unknown)[0]}")
    if set(data) != {"trades", "explanation"}:
        raise AIDecisionError("response requires trades and explanation")
    raw_trades = data["trades"]
    if not isinstance(raw_trades, list):
        raise AIDecisionError("trades must be an array")
    trades: list[Trade] = []
    try:
        for raw_value in cast(list[object], raw_trades):
            if not isinstance(raw_value, Mapping):
                raise AIDecisionError("each trade must be an object")
            raw = cast(Mapping[str, object], raw_value)
            unknown_trade = set(raw) - {"action", "ticker", "quantity"}
            if unknown_trade:
                raise AIDecisionError(f"unknown trade field: {sorted(unknown_trade)[0]}")
            if set(raw) != {"action", "ticker", "quantity"}:
                raise AIDecisionError("each trade requires action, ticker, and quantity")
            trades.append(
                Trade(
                    cast(Any, raw["action"]), cast(Any, raw["ticker"]), cast(Any, raw["quantity"])
                )
            )
        explanation_value = data["explanation"]
        if not isinstance(explanation_value, str):
            raise AIDecisionError("explanation must be a string")
        explanation = AITradeExplanation(explanation_value)
    except (DomainValidationError, TypeError, ValueError) as exc:
        raise AIDecisionError(f"invalid AI decision: {exc}") from exc
    return AIDecision(tuple(trades), explanation)


class DecisionResult:
    def __init__(self, decision: AIDecision, state: PortfolioState) -> None:
        self.decision = decision
        self.state = state


class AIDecisionManager:
    def __init__(
        self, client: AIClient, market: QuoteProvider, *, attempts: int = MAX_ATTEMPTS
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be positive")
        self._client = client
        self._market = market
        self._attempts = attempts

    @classmethod
    def from_environment(
        cls, market: QuoteProvider, environ: Mapping[str, str] | None = None
    ) -> AIDecisionManager:
        values = os.environ if environ is None else environ
        key = values.get("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise ConfigurationError("OPENROUTER_API_KEY is required for AI decisions")
        return cls(OpenRouterAIClient(key), market)

    def run(
        self,
        *,
        strategy: str,
        state: PortfolioState,
        as_of: date,
        news: Sequence[MarketNews],
    ) -> DecisionResult:
        last_error: Exception | None = None
        for _ in range(self._attempts):
            try:
                quotes: dict[Ticker, Decimal] = {}

                def get_quote(
                    args: Mapping[str, object],
                    _context: object = None,
                    *,
                    _quotes: dict[Ticker, Decimal] = quotes,
                ) -> dict[str, str]:
                    ticker = Ticker(str(args["ticker"]))
                    quote = self._market.quote(ticker)
                    _quotes[ticker] = quote.current_price
                    return {"ticker": str(ticker), "current_price": f"{quote.current_price:.2f}"}

                quote_tool = tool(
                    name="quote",
                    description="Get the current Finnhub price for one ticker.",
                    input_schema={
                        "type": "object",
                        "properties": {"ticker": {"type": "string"}},
                        "required": ["ticker"],
                        "additionalProperties": False,
                    },
                    execute=get_quote,
                )
                decision = parse_ai_response(
                    self._client.complete(
                        build_decision_prompt(
                            strategy=strategy, state=state, as_of=as_of, news=news
                        ),
                        [quote_tool],
                    )
                )
                current = state
                for trade in decision.trades:
                    if trade.ticker not in quotes:
                        raise AIDecisionError(f"AI did not request a quote for {trade.ticker}")
                    current = apply_trade(current, trade, quotes[trade.ticker])
                return DecisionResult(decision, current)
            except Exception as exc:
                last_error = exc
        reason = str(last_error) if last_error else "unknown failure"
        raise AIDecisionError(
            f"AI decision failed after {self._attempts} attempts: {reason}"
        ) from last_error
