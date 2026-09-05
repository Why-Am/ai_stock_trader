import json
from log import log

from fake_stock_portfolio import FakeStockPortfolio
from tool_manager import ToolManager
from finnhub_helper import create_finnhub_client
from ai import AI


def main():
    finnhub_client = create_finnhub_client()
    portfolio = FakeStockPortfolio(500, finnhub_client)
    tool_manager = ToolManager(finnhub_client)
    ai = AI(tool_manager, finnhub_client, portfolio)

    print("Getting response 1...")
    response_1 = ai.get_response_1()
    log("response_1.txt", json.dumps(response_1.json(), ensure_ascii=False, indent=2))

    print("Running tools...")
    ai.run_tools()

    print("Getting response 2...")
    response_2 = ai.get_response_2()
    log("response_2.txt", json.dumps(response_2.json(), ensure_ascii=False, indent=2))
    print(ai.get_response_message_content(response_2))
    log("messages.txt", json.dumps(ai.messages, indent=2))


if __name__ == "__main__":
    main()
