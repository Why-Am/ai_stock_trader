import csv
from pathlib import Path

FIELDNAMES = (
    "Time",
    "Portfolio before - holdings",
    "Portfolio before - total value",
    "Trades",
    "Portfolio after - holdings",
    "Portfolio after - total value",
    "Explanation",
    "All messages",
)


class Historian:
    def __init__(self, path_to_save: str):
        self.path_to_save = Path(path_to_save)
        if not self.path_to_save.exists():
            self.path_to_save.touch()

    def save(
        self,
        time: str,
        portfolio_before_holdings: str,
        portfolio_before_total_value: float,
        trades: str,
        portfolio_after_holdings: str,
        portfolio_after_total_value: float,
        explanation: str,
        all_messages: str,
    ):
        is_empty = len(self.path_to_save.read_text()) == 0

        with open(self.path_to_save, "a", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, FIELDNAMES)
            row = {
                FIELDNAMES[0]: time,
                FIELDNAMES[1]: portfolio_before_holdings,
                FIELDNAMES[2]: portfolio_before_total_value,
                FIELDNAMES[3]: trades,
                FIELDNAMES[4]: portfolio_after_holdings,
                FIELDNAMES[5]: portfolio_after_total_value,
                FIELDNAMES[6]: explanation,
                FIELDNAMES[7]: all_messages,
            }

            if is_empty:
                writer.writeheader()

            writer.writerow(row)  # type: ignore


def main():
    historian = Historian("data/save.csv")
    historian.save(
        time="asdf",
        portfolio_before_holdings="as fds",
        portfolio_before_total_value=123,
        trades="lkajdsflj",
        portfolio_after_holdings="fkj adjlk",
        portfolio_after_total_value=4807,
        explanation="fjlfljkfjk",
        all_messages="foiudsoiu",
    )


if __name__ == "__main__":
    main()
