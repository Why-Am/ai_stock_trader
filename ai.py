import json
import os

import finnhub
import requests

from exceptions import APIKeyNotFoundError
from fake_stock_portfolio import FakeStockPortfolio
from finnhub_helper import get_news
from log import log
from tool_manager import ToolManager, get_stock_quote_tool, make_trades_tool

# MODEL = "openrouter/free"
# This model is powerful, popular, and works well with this program
MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"


class AI:
    def __init__(
        self,
        finnhub_client: finnhub.Client,
        portfolio: FakeStockPortfolio,
    ):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if self.api_key is None:
            raise APIKeyNotFoundError(
                "Couldn't find OPENROUTER_API_KEY in environment variables. Make sure it is set."
            )
        self.tool_manager = ToolManager(finnhub_client)

        prompt = self.make_prompt(finnhub_client, portfolio)
        self.messages = [{"role": "system", "content": prompt}]

    def get_response_1(self) -> tuple[dict, list[dict]]:
        """Gets first response and tool calls"""
        response_1 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": MODEL,
                "tools": get_stock_quote_tool,
                "messages": self.messages,
            },
        ).json()

        response_1_message = response_1["choices"][0]["message"]
        self.messages.append(response_1_message)

        response_1_tool_calls = response_1_message["tool_calls"]

        return response_1, response_1_tool_calls

    def get_response_2(self) -> tuple[dict, list[dict]]:
        """Gets second response and tool calls"""
        response_2 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": MODEL,
                "tools": make_trades_tool,
                "messages": self.messages,
            },
        ).json()

        response_2_message = response_2["choices"][0]["message"]
        self.messages.append(response_2_message)

        response_2_tool_calls = response_2_message["tool_calls"]

        return response_2, response_2_tool_calls

    def run_tools(self, tool_calls: list[dict]):
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])
            tool_response = self.tool_manager.run_tool(tool_name, tool_args)

            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_response),
                }
            )

    def get_response_message_content(self, response: dict) -> str:
        return response["choices"][0]["message"]["content"]

    def make_prompt(
        self, finnhub_client: finnhub.Client, portfolio: FakeStockPortfolio
    ):
        return (
            "You are a stock trading AI that is run every day.\n"
            "Your job is to maximize returns in trading US stocks.\n"
            "The following is the latest market news:\n"
            f"{get_news(finnhub_client)}\n\n"
            "The following is the state of your portfolio:\n"
            f"{portfolio.describe()}\n\n"
            "You can only use the `get_stock_quote` tool in your first response, "
            "so put in the tickers of every stock you want to know about.\n"
            "You will execute the trades in your second response with the `make_trades` tool.\n"
        )

    def get_and_make_trades(self) -> None:
        print("Getting response 1...")
        response_1, response_1_tool_calls = self.get_response_1()
        log("response_1.txt", json.dumps(response_1, indent=2))

        print("Running tools...")
        self.run_tools(response_1_tool_calls)

        print("Getting response 2...")
        response_2, response_2_tool_calls = self.get_response_2()
        log("response_2.txt", json.dumps(response_2, indent=2))

        log("messages.txt", json.dumps(self.messages, indent=2))

        response_2_message_content = self.get_response_message_content(response_2)
        print(f"AI Response:\n{response_2_message_content}")

        input("Press enter to confirm trades.")

        print("Making trades...")
        self.run_tools(response_2_tool_calls)
