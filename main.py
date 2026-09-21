import sys
import time

from ai import AI
from constants import SAVE_FILE_PATH
from exceptions import EmptySaveError
from fake_stock_portfolio import FakeStockPortfolio
from finnhub_helper import create_finnhub_client
from historian import Historian

# This model is powerful, popular, and works well with this program
MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
# An alternative that is supposed to point to the best free model
# MODEL = "openrouter/free"


def main():
    finnhub_client = create_finnhub_client()
    historian = Historian(SAVE_FILE_PATH)
    try:
        portfolio = historian.load_portfolio(finnhub_client)
    except EmptySaveError:
        answer = input(
            "Save is empty or does not exist. Initialize new portfolio (y/n)? "
        )
        if answer not in ("Y", "y"):
            print("Exiting.")
            sys.exit(1)

        starting_money = float(input("How much starting money? "))
        portfolio = FakeStockPortfolio(starting_money, finnhub_client)

    portfolio_before = portfolio.get_data()

    ai = AI(MODEL, finnhub_client, portfolio)

    run_data = ai.get_and_make_trades()

    historian.save(
        time=int(time.time()),
        portfolio_before=portfolio_before,
        trades=run_data.trades,
        portfolio_after=portfolio.get_data(),
        explanation=run_data.explanation,
        all_messages=run_data.all_messages,
    )


if __name__ == "__main__":
    main()
