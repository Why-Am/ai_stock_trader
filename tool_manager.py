from typing import Any

import finnhub
import os


class ToolManager:
    def __init__(self, finnhub_client: finnhub.Client):
        self.finnhub_client = finnhub_client

    def get_stock_quote(self, ticker: str) -> str:
        res = self.finnhub_client.quote(ticker)
        if res["c"] == 0:
            return f"Error: could not get stock quote for '{ticker}'"
        return (
            f"Stock quote for {ticker}\n"
            f"Current price: {res['c']}\n"
            f"Change: {res['d']}\n"
            f"Percent change: {res['dp']}\n"
            f"High price of the day: {res['h']}\n"
            f"Low price of the day: {res['l']}\n"
            f"Open price of the day: {res['o']}\n"
            f"Previous close price: {res['pc']}\n"
        )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_stock_quote",
                "description": "Get the quote for a US stock.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "The stock's ticker",
                        }
                    },
                    "required": ["ticker"],
                },
            },
        }
    ]

    _tool_mapping = {"get_stock_quote": get_stock_quote}

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
