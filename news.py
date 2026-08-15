import finnhub
import os


def get_news(finnhub_client: finnhub.Client) -> dict:
    news = finnhub_client.general_news("general")
    for article in news:
        article.pop("id", None)
        article.pop("image", None)
        article.pop("url", None)
        article.pop("headline", None)
    return news


def main():
    api_key = os.getenv("FINNHUB_API_KEY")
    finnhub_client = finnhub.Client(api_key)
    print(get_news(finnhub_client))


if __name__ == "__main__":
    main()
