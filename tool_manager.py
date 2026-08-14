from typing import Any

import finnhub
import os


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

        return res

    tools = [
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

    _tool_mapping = {"get_stock_quote": get_stock_quotes}

    def run_tool(self, tool_name: str, tool_args):
        return self._tool_mapping[tool_name](self, **tool_args)


def main():
    api_key = os.getenv("FINNHUB_API_KEY")
    finnhub_client = finnhub.Client(api_key)
    tool_manager = ToolManager(finnhub_client)
    # print(tool_manager.get_stock_quote("AAPL"))

    print(tool_manager.run_tool("get_stock_quote", {"ticker": "NVDA"}))

    print(finnhub_client.quote("NVDA"))


if __name__ == "__main__":
    main()
