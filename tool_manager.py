import os
from time import sleep
from typing import ClassVar

import finnhub

from exceptions import ToolCallError
from fake_stock_portfolio import FakeStockPortfolio


class ToolManager:
    def __init__(self, finnhub_client: finnhub.Client):
        self.finnhub_client = finnhub_client

    def get_stock_quotes(self, tickers: list[str]) -> str:
        res = ""

        for ticker in tickers:
            quote = self.finnhub_client.quote(ticker)
            if quote["c"] == 0:
                res += f"Error: could not get stock quote for '{ticker}'\n\n"
                continue

            res += (
                f"Stock quote for {ticker}\n"
                f"Current price: {quote['c']}\n"
                f"Change: {quote['d']}\n"
                f"Percent change: {quote['dp']}\n"
                f"High price of the day: {quote['h']}\n"
                f"Low price of the day: {quote['l']}\n"
                f"Open price of the day: {quote['o']}\n"
                f"Previous close price: {quote['pc']}\n\n"
            )

            sleep(0.1)

        return res

    def make_trades(self, portfolio: FakeStockPortfolio, trades: list[dict]):
        for trade in trades:
            match trade["action"]:
                case "buy":
                    portfolio.buy(trade["ticker"], trade["amount"])
                case "sell":
                    portfolio.sell(trade["ticker"], trade["amount"])
                case _:
                    raise ToolCallError(
                        f'trade["action"] should be one of "buy" or "sell", instead got {trade["action"]}'
                    )

    _tool_mapping: ClassVar[dict] = {
        "get_stock_quote": get_stock_quotes,
        "make_trades": make_trades,
    }

    def run_tool(self, tool_name: str, tool_args):
        return self._tool_mapping[tool_name](self, **tool_args)


get_stock_quote_tool = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_quote",
            "description": "Get the quotes of US stocks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tickers for the stocks you want to get quotes for.",
                    }
                },
                "required": ["tickers"],
            },
        },
    }
]

make_trades_tool = [
    {
        "type": "function",
        "function": {
            "name": "make_trades",
            "description": "Make stock trades.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trades": {
                        "type": "array",
                        "description": "The trades you want to make.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ticker": {
                                    "type": "string",
                                    "description": "Ticker of the stock you want to trade.",
                                },
                                "action": {
                                    "type": "string",
                                    "enum": ["buy", "sell"],
                                    "description": "Type of trade you want to make.",
                                },
                                "amount": {
                                    "type": "number",
                                    "description": "Amount of shares. Can be fractional.",
                                },
                            },
                            "required": ["ticker", "action", "amount"],
                        },
                    }
                },
                "required": ["trades"],
            },
        },
    }
]


def main():
    api_key = os.getenv("FINNHUB_API_KEY")
    finnhub_client = finnhub.Client(api_key)
    tool_manager = ToolManager(finnhub_client)
    # print(tool_manager.get_stock_quote("AAPL"))

    print(tool_manager.run_tool("get_stock_quote", {"ticker": "NVDA"}))

    print(finnhub_client.quote("NVDA"))


if __name__ == "__main__":
    main()
