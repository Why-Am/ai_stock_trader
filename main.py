from datetime import datetime
import json
from news import get_news
from log import log

import requests
from fake_stock_portfolio import FakeStockPortfolio
from json_schema import json_schema
import os
import finnhub
from tool_manager import ToolManager

MODEL = "openrouter/free"


def main():
    finnhub_api_key = os.getenv("FINNHUB_API_KEY")
    if finnhub_api_key is None:
        raise Exception(
            "Cannot get the FINNHUB_API_KEY environment variable. Make sure it is set."
        )
    finnhub_client = finnhub.Client(finnhub_api_key)
    portfolio = FakeStockPortfolio(500, finnhub_client)
    tool_manager = ToolManager(finnhub_client)

    prompt = (
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

    messages = [{"role": "system", "content": prompt}]

    print("Getting response 1...")
    response_1 = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
        json={
            "model": MODEL,
            "tools": tool_manager.tools,
            "messages": messages,
        },
    )

    log("response_1.txt", json.dumps(response_1.json(), ensure_ascii=False, indent=2))

    response_1 = response_1.json()["choices"][0]["message"]

    messages.append(response_1)

    print("Running tools...")
    for tool_call in response_1["tool_calls"]:
        tool_name = tool_call["function"]["name"]
        tool_args = json.loads(tool_call["function"]["arguments"])
        tool_response = tool_manager.run_tool(tool_name, tool_args)

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(tool_response),
            }
        )

    print("Getting response 2...")
    response_2 = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
        json={
            "model": MODEL,
            "messages": messages,
            "response_format": json_schema,
        },
    )

    print(response_2.json()["choices"][0]["message"]["content"])

    log("response_2.txt", json.dumps(response_2.json(), ensure_ascii=False, indent=2))

    messages.append(response_2.json()["choices"][0]["message"])

    log("messages.txt", json.dumps(messages, indent=2))


if __name__ == "__main__":
    main()
