from ai import AI
from fake_stock_portfolio import FakeStockPortfolio
from finnhub_helper import create_finnhub_client

# This model is powerful, popular, and works well with this program
MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
# An alternative that is supposed to point to the best free model
# MODEL = "openrouter/free"


def main():
    finnhub_client = create_finnhub_client()
    portfolio = FakeStockPortfolio(500, finnhub_client)
    ai = AI(MODEL, finnhub_client, portfolio)

    ai.get_and_make_trades()


if __name__ == "__main__":
    main()
