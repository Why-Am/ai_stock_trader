from ai import AI
from exceptions import EmptySaveError
from finnhub_helper import create_finnhub_client
from historian import Historian

# This model is powerful, popular, and works well with this program
MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
# An alternative that is supposed to point to the best free model
# MODEL = "openrouter/free"

DEFAULT_STARTING_MONEY = 500


def main():
    finnhub_client = create_finnhub_client()
    historian = Historian("data/save.csv")
    try:
        portfolio = historian.load_portfolio(finnhub_client)
    except EmptySaveError:
        return  # TODO

    ai = AI(MODEL, finnhub_client, portfolio)

    ai.get_and_make_trades()


if __name__ == "__main__":
    main()
