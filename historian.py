import csv
import json
from pathlib import Path

import finnhub

from exceptions import EmptySaveError
from fake_stock_portfolio import FakeStockPortfolio
from finnhub_helper import create_finnhub_client

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
        time: str,
        portfolio_before_holdings: dict[str, float],
        portfolio_before_total_value: float,
        portfolio_before_money_left_to_trade: float,
        trades: str,
        portfolio_after_holdings: dict[str, float],
        portfolio_after_total_value: float,
        portfolio_after_money_left_to_trade: float,
        explanation: str,
        all_messages: str,
    ):
        with open(self.path_to_save, "a", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, FIELDNAMES)
            row = {
                FIELDNAMES[0]: time,
                FIELDNAMES[1]: json.dumps(portfolio_before_holdings),
                FIELDNAMES[2]: portfolio_before_total_value,
                FIELDNAMES[3]: portfolio_before_money_left_to_trade,
                FIELDNAMES[4]: trades,
                FIELDNAMES[5]: json.dumps(portfolio_after_holdings),
                FIELDNAMES[6]: portfolio_after_total_value,
                FIELDNAMES[7]: portfolio_after_money_left_to_trade,
                FIELDNAMES[8]: explanation,
                FIELDNAMES[9]: all_messages,
            }

            if self.save_is_empty():
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
        time="asdf",
        portfolio_before_holdings={"TSLA": 1, "AAPL": 2},
        portfolio_before_total_value=123,
        portfolio_before_money_left_to_trade=908,
        trades="lkajdsflj",
        portfolio_after_holdings={"TSLA": 0.5, "NVDA": 100},
        portfolio_after_total_value=4807,
        portfolio_after_money_left_to_trade=879,
        explanation="fjlfljkfjk",
        all_messages="foiudsoiu",
    )
    finnhub_client = create_finnhub_client()
    portfolio = historian.load_portfolio(finnhub_client)
    print(portfolio.describe())


if __name__ == "__main__":
    main()
