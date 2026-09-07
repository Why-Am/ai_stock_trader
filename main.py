from ai import AI
from fake_stock_portfolio import FakeStockPortfolio
from finnhub_helper import create_finnhub_client


def main():
    finnhub_client = create_finnhub_client()
    portfolio = FakeStockPortfolio(500, finnhub_client)
    ai = AI(finnhub_client, portfolio)

    trades = ai.get_trades()


if __name__ == "__main__":
    main()
