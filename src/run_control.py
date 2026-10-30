import finnhub

from constants import S_AND_P_500_TICKER, STARTING_MONEY
from fake_stock_portfolio import FakeStockPortfolio
from historian import Historian


def run_control(initialize: bool, save_file_path: str, finnhub_client: finnhub.Client):
    historian = Historian(save_file_path)
    if initialize:
        portfolio = FakeStockPortfolio(STARTING_MONEY, finnhub_client)
        portfolio_before = portfolio.get_data()
        amount_to_buy = STARTING_MONEY / portfolio.get_current_price(S_AND_P_500_TICKER)
        portfolio.buy(S_AND_P_500_TICKER, amount_to_buy)
        trades = [
            {"ticker": S_AND_P_500_TICKER, "action": "buy", "amount": amount_to_buy}
        ]
    else:
        portfolio = historian.load_portfolio(finnhub_client)
        portfolio_before = portfolio.get_data()
        trades = []

    historian.save(
        portfolio_before=portfolio_before,
        trades=trades,
        portfolio_after=portfolio.get_data(),
        explanation="",
        all_messages=[],
    )
