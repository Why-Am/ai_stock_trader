from ai import AI
from fake_stock_portfolio import FakeStockPortfolio
from finnhub_helper import create_finnhub_client
from tool_manager import ToolManager


def main():
    finnhub_client = create_finnhub_client()
    portfolio = FakeStockPortfolio(500, finnhub_client)
    tool_manager = ToolManager(finnhub_client)
    ai = AI(tool_manager, finnhub_client, portfolio)

    trades = ai.get_trades()


if __name__ == "__main__":
    main()
