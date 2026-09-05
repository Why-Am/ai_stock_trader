import os
import finnhub

def create_finnhub_client() -> finnhub.Client:
    finnhub_api_key = os.getenv("FINNHUB_API_KEY")
    if finnhub_api_key is None:
        raise Exception(
            "Cannot get the FINNHUB_API_KEY environment variable. Make sure it is set."
        )

    return finnhub.Client(finnhub_api_key)

def get_news(finnhub_client: finnhub.Client) -> dict:
    news = finnhub_client.general_news("general")
    for article in news:
        article.pop("id", None)
        article.pop("image", None)
        article.pop("url", None)
        article.pop("headline", None)
    return news