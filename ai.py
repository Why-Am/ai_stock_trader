import json
import os
from dataclasses import dataclass

import finnhub
import requests

from exceptions import APIKeyNotFoundError
from fake_stock_portfolio import FakeStockPortfolio
from finnhub_helper import get_news
from log import log
from tool_manager import ToolManager, get_stock_quote_tool, make_trades_tool


@dataclass
class RunData:
    explanation: str
    trades: list[dict]
    all_messages: list[dict]


class AI:
    def __init__(
        self,
        model: str,
        finnhub_client: finnhub.Client,
        portfolio: FakeStockPortfolio,
    ):
        self.model = model
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if self.api_key is None:
            raise APIKeyNotFoundError(
                "Couldn't find OPENROUTER_API_KEY in environment variables. Make sure it is set."
            )
        self.tool_manager = ToolManager(finnhub_client, portfolio)

        prompt = self._make_prompt(finnhub_client, portfolio)
        self.messages = [{"role": "system", "content": prompt}]

    def _get_response_1(self) -> tuple[dict, list[dict]]:
        """Gets first response and tool calls"""
        response_1 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "tools": get_stock_quote_tool,
                "messages": self.messages,
            },
        ).json()

        response_1_message = response_1["choices"][0]["message"]
        self.messages.append(response_1_message)

        response_1_tool_calls = response_1_message["tool_calls"]

        return response_1, response_1_tool_calls

    def _get_response_2(self) -> tuple[dict, list[dict]]:
        """Gets second response and tool calls"""
        response_2 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "tools": make_trades_tool,
                "messages": self.messages,
            },
        ).json()

        response_2_message = response_2["choices"][0]["message"]
        self.messages.append(response_2_message)

        response_2_tool_calls = response_2_message["tool_calls"]

        return response_2, response_2_tool_calls

    def _run_tools(self, tool_calls: list[dict]) -> list:
        tool_responses = []

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])
            tool_response = self.tool_manager.run_tool(tool_name, tool_args)
            tool_responses.append(tool_response)

            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_response),
                }
            )

        return tool_responses

    def _get_response_message_content(self, response: dict) -> str:
        return response["choices"][0]["message"]["content"]

    def _make_prompt(
        self, finnhub_client: finnhub.Client, portfolio: FakeStockPortfolio
    ):
        return (
            "You are a stock trading AI that is run daily.\n"
            "Your job is to maximize returns in trading US stocks.\n"
            "The following is the latest market news:\n"
            f"{get_news(finnhub_client)}\n\n"
            "The following is the state of your portfolio:\n"
            f"{portfolio.describe()}\n\n"
            "You can only use the `get_stock_quote` tool in your first response, "
            "so put in the tickers of every stock you want to know about.\n"
            "You will execute the trades in your second response with the `make_trades` tool.\n"
            "Explain your trades."
        )

    def get_and_make_trades(self) -> RunData:
        print("Getting response 1...")
        response_1, response_1_tool_calls = self._get_response_1()
        log("response_1.txt", json.dumps(response_1, indent=2))

        print("Running tools...")
        self._run_tools(response_1_tool_calls)

        print("Getting response 2...")
        response_2, response_2_tool_calls = self._get_response_2()
        log("response_2.txt", json.dumps(response_2, indent=2))

        log("messages.txt", json.dumps(self.messages, indent=2))

        response_2_message_content = self._get_response_message_content(response_2)
        print(f"AI Response:\n{response_2_message_content}")

        input("Press enter to confirm trades.")

        print("Making trades...")
        explanation = self._run_tools(response_2_tool_calls)[0]

        trades = json.loads(response_2_tool_calls[0]["function"]["arguments"]["trades"])

        print(f"Trades: {json.dumps(trades, indent=2)}")
        print(f"explanation: {explanation}")

        return RunData(explanation, trades, self.messages)
