from openrouter import OpenRouter
import requests
from fake_stock_portfolio import FakeStockPortfolio
from json_schema import json_schema
import os

MODEL = "openrouter/free"


def main():
    finnhub_api_key = os.getenv("FINNHUB_API_KEY")
    if finnhub_api_key is None:
        raise Exception(
            "Cannot get the FINNHUB_API_KEY environment variable. Make sure it is set."
        )
    portfolio = FakeStockPortfolio(500, finnhub_api_key)
    prompt = (
        "You are a stock trading AI that is run every day.\n"
        "Your job is to maximize returns in trading US stocks.\n"
        "Search the web to get information to inform your trades.\n"
        "The following is the state of your portfolio."
        f"{portfolio.describe()}"
    )

    # TODO: If I go with requests, remove the dependency on openrouter
    # with OpenRouter(api_key=os.getenv("OPENROUTER_API_KEY")) as client:
    #     response = client.chat.send(
    #         model=MODEL,
    #         messages=[{"role": "user", "content": prompt}],
    #         response_format=
    #     )

    #     print(response.choices[0].message.content)

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": json_schema,
            "tools": [
                {"type": "openrouter:web_search"}
            ]
        },
    )

    print(response)
    print("---")
    print(response.json()["choices"][0]["message"]["content"])


if __name__ == "__main__":
    main()
