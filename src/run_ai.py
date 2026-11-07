from pathlib import Path

import finnhub

from ai import AI
from constants import MAXIMUM_TRIES, STARTING_MONEY
from exceptions import AIRunError, StockPortfolioError
from fake_stock_portfolio import FakeStockPortfolio
from historian import Historian

# This model is powerful, popular, and works well with this program
MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
# An alternative that is supposed to point to the best free model
# MODEL = "openrouter/free"


def run_ai(initialize: bool, save_file_path: Path, finnhub_client: finnhub.Client):
    historian = Historian(save_file_path)
    if initialize:
        portfolio = FakeStockPortfolio(STARTING_MONEY, finnhub_client)
    else:
        portfolio = historian.load_portfolio(finnhub_client)

    portfolio_before = portfolio.get_data()

    ai = AI(MODEL, finnhub_client, portfolio)

    try_count = 1
    while True:
        try:
            run_data = ai.get_and_make_trades()
            break
        except StockPortfolioError as e:
            print(f"try {try_count}/{MAXIMUM_TRIES} failed: {e}")
            try_count += 1
            if try_count > MAXIMUM_TRIES:
                raise AIRunError(f"StockPortfolioError after {MAXIMUM_TRIES} tries")

    historian.save(
        portfolio_before=portfolio_before,
        trades=run_data.trades,
        portfolio_after=portfolio.get_data(),
        explanation=run_data.explanation,
        all_messages=run_data.all_messages,
    )


if __name__ == "__main__":
    pass
    # run_ai(TEST_AI_SAVE_FILE_PATH)
