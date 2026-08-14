import finnhub
import os


class FakeStockPortfolio:
    def __init__(self, money_available_to_trade: float, finnhub_client: finnhub.Client):
        self.money_available_to_trade = money_available_to_trade
        self.holdings: dict[str, float] = {}
        self.finnhub_client = finnhub_client

    def get_current_price(self, ticker: str) -> float:
        res = self.finnhub_client.quote(ticker)["c"]
        if res == 0:
            raise Exception("Could not get price.")
        return res

    def describe(self) -> str:
        return (
            f"Portfolio status:\n"
            f"Money available to trade: ${self.money_available_to_trade}\n"
            f"Current holdings: {self.holdings}"
        )

    def buy(self, ticker: str, amount: float):
        if amount <= 0:
            raise Exception("Cannot buy zero or negative stock")

        current_price = self.get_current_price(ticker)

        transaction_total = current_price * amount
        if transaction_total > self.money_available_to_trade:
            raise Exception("Insufficient funds.")

        if ticker in self.holdings:
            self.holdings[ticker] += amount
        else:
            self.holdings[ticker] = amount

        self.money_available_to_trade -= transaction_total

    def sell(self, ticker: str, amount: float):
        if amount <= 0:
            raise Exception("Cannot sell zero or negative stock")

        if ticker not in self.holdings:
            raise Exception(f"There is no holding for `{ticker}`.")

        if amount > self.holdings[ticker]:
            raise Exception(
                f"Unable to sell more stock than is held ({amount} > {self.holdings[ticker]})."
            )

        if amount == self.holdings[ticker]:
            self.sell_all(ticker)
            return

        current_price = self.get_current_price(ticker)
        transaction_total = current_price * amount
        self.holdings[ticker] -= amount
        self.money_available_to_trade += transaction_total

    def sell_all(self, ticker: str):
        if ticker not in self.holdings:
            raise Exception(f"There is no holding for `{ticker}`.")

        current_price = self.get_current_price(ticker)
        amount = self.holdings.pop(ticker)
        self.money_available_to_trade += current_price * amount


def main():
    """Command line interaction with FakeStockPortfolio"""
    finnhub_api_key = os.getenv("FINNHUB_API_KEY")
    if finnhub_api_key is None:
        raise Exception("Cannot find FINNHUB_API_KEY environment variable.")

    starting_money = float(input("How much money should the account have? "))

    portfolio = FakeStockPortfolio(starting_money, finnhub.Client(finnhub_api_key))

    running = True
    while running:
        print()
        print(portfolio.describe())
        print()

        action = input("Enter action (`h` for help, `q` to quit): ")

        match action:
            case "q":
                running = False
            case "h":
                print("`b`: buy, `s`: sell, `sa`: sell all")
            case "b":
                try:
                    ticker = input("Ticker: ")
                    amount = float(input("Amount: "))
                    portfolio.buy(ticker, amount)
                except Exception as e:
                    print(f"Error buying: {e}")
            case "s":
                try:
                    ticker = input("Ticker: ")
                    amount = float(input("Amount: "))
                    portfolio.sell(ticker, amount)
                except Exception as e:
                    print(f"Error selling: {e}")
            case "sa":
                try:
                    ticker = input("Ticker: ")
                    portfolio.sell_all(ticker)
                except Exception as e:
                    print(f"Error selling: {e}")
            case _:
                print("Invalid action.")


if __name__ == "__main__":
    main()
