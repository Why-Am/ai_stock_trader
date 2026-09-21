import csv
import json
from pathlib import Path

import finnhub

from exceptions import EmptySaveError, SaveCancelError
from fake_stock_portfolio import FakeStockPortfolio
from finnhub_helper import create_finnhub_client
from portfolio_data import PortfolioData

TIME = "Time"
PORTFOLIO_BEFORE_HOLDINGS = "Portfolio before - holdings"
PORTFOLIO_BEFORE_MONEY_LEFT_TO_TRADE = "Portfolio before - money left to trade"
PORTFOLIO_BEFORE_TOTAL_VALUE = "Portfolio before - total value"
TRADES = "Trades"
PORTFOLIO_AFTER_HOLDINGS = "Portfolio after - holdings"
PORTFOLIO_AFTER_MONEY_LEFT_TO_TRADE = "Portfolio after - money left to trade"
PORTFOLIO_AFTER_TOTAL_VALUE = "Portfolio after - total value"
EXPLANATION = "Explanation"
ALL_MESSAGES = "All messages"

FIELDNAMES = (
    TIME,
    PORTFOLIO_BEFORE_HOLDINGS,
    PORTFOLIO_BEFORE_MONEY_LEFT_TO_TRADE,
    PORTFOLIO_BEFORE_TOTAL_VALUE,
    TRADES,
    PORTFOLIO_AFTER_HOLDINGS,
    PORTFOLIO_AFTER_MONEY_LEFT_TO_TRADE,
    PORTFOLIO_AFTER_TOTAL_VALUE,
    EXPLANATION,
    ALL_MESSAGES,
)


class Historian:
    def __init__(self, path_to_save: str):
        self.path_to_save = Path(path_to_save)
        if not self.path_to_save.exists():
            self.path_to_save.touch()

    def save(
        self,
        time: int,
        portfolio_before: PortfolioData,
        trades: list[dict],
        portfolio_after: PortfolioData,
        explanation: str,
        all_messages: list[dict],
        initialize: bool = False,
    ):
        with open(self.path_to_save, "a", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, FIELDNAMES)
            row: dict[str, str] = {
                FIELDNAMES[0]: str(time),
                FIELDNAMES[1]: json.dumps(portfolio_before.holdings),
                FIELDNAMES[2]: str(portfolio_before.total_value),
                FIELDNAMES[3]: str(portfolio_before.money_available_to_trade),
                FIELDNAMES[4]: json.dumps(trades),
                FIELDNAMES[5]: json.dumps(portfolio_after.holdings),
                FIELDNAMES[6]: str(portfolio_after.total_value),
                FIELDNAMES[7]: str(portfolio_after.money_available_to_trade),
                FIELDNAMES[8]: explanation,
                FIELDNAMES[9]: json.dumps(all_messages),
            }

            if initialize:
                if not self.save_is_empty():
                    answer = input(
                        f"Existing contents of {self.path_to_save} will be overwritten. Continue (y/n)?: "
                    )
                    if answer in ["Y", "y"]:
                        open(self.path_to_save, "w").close()
                    else:
                        raise SaveCancelError

                writer.writeheader()

            writer.writerow(row)  # type: ignore

    def load_portfolio(self, finnhub_client: finnhub.Client) -> FakeStockPortfolio:
        if self.save_is_empty():
            raise EmptySaveError

        with open(self.path_to_save, "r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file, FIELDNAMES)
            for row in reader:
                last_row = row

            holdings = json.loads(last_row[PORTFOLIO_AFTER_HOLDINGS])  # pyright: ignore[reportPossiblyUnboundVariable]
            money_available_to_trade = float(
                last_row[PORTFOLIO_AFTER_MONEY_LEFT_TO_TRADE]  # pyright: ignore[reportPossiblyUnboundVariable]
            )

        return FakeStockPortfolio(money_available_to_trade, finnhub_client, holdings)

    def save_is_empty(self) -> bool:
        return len(self.path_to_save.read_text()) == 0


def main():
    historian = Historian("data/save.csv")
    historian.save(
        time=0,
        portfolio_before=PortfolioData({"TSLA": 3, "AAPL": 2}, 333, 8.2),
        trades=[{"ticker": "SPX", "action": "buy", "amount": 1}],
        portfolio_after=PortfolioData({"RTX": 0.1, "AAPL": 3, "NVDA": 300}, 1000, 0),
        explanation="this is the explanation",
        all_messages=[{"message": "this is a message"}],
    )
    finnhub_client = create_finnhub_client()
    portfolio = historian.load_portfolio(finnhub_client)
    print(portfolio.describe())


if __name__ == "__main__":
    main()
