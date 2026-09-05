import json
import os
import requests

import finnhub
from fake_stock_portfolio import FakeStockPortfolio

from tool_manager import ToolManager
from json_schema import json_schema
from finnhub_helper import get_news

MODEL = "openrouter/free"

class AI:
    def __init__(self, tool_manager: ToolManager, finnhub_client: finnhub.Client, portfolio: FakeStockPortfolio):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.tool_manager = tool_manager

        prompt = self.make_prompt(finnhub_client, portfolio)
        self.messages = [{"role": "system", "content": prompt}]

    def get_response_1(self):
        response_1 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": MODEL,
                "tools": self.tool_manager.tools,
                "messages": self.messages,
            },
        )

        response_1_message = response_1.json()["choices"][0]["message"]
        self.messages.append(response_1_message)

        self.response_1_tool_calls = response_1_message["tool_calls"]

        return response_1

    def run_tools(self):
        for tool_call in self.response_1_tool_calls:
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

    def get_response_2(self):
        response_2 = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": MODEL,
                "messages": self.messages,
                "response_format": json_schema,
            },
        )

        response_2_message = response_2.json()["choices"][0]["message"]
        self.messages.append(response_2_message)
        return response_2

    def get_response_message_content(self, response: requests.Response) -> str:
        return response.json()["choices"][0]["message"]["content"]

    def make_prompt(self, finnhub_client: finnhub.Client, portfolio: FakeStockPortfolio):
        return (
            "You are a stock trading AI that is run every day.\n"
            "Your job is to maximize returns in trading US stocks.\n"
            "The following is the latest market news:\n"
            f"{get_news(finnhub_client)}\n\n"
            "The following is the state of your portfolio:\n"
            f"{portfolio.describe()}\n\n"
            "You can only use the `get_stock_quote` tool in your first response, "
            "so put in the tickers of every stock you want to know about.\n"
            "You will execute the trades in your second response in JSON format.\n"
        )
