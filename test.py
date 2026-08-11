from openrouter import OpenRouter
import os

with OpenRouter(api_key=os.getenv("OPENROUTER_API_KEY")) as client:
    response = client.chat.send(
        model="openrouter/free",
        messages=[
            {"role": "user", "content": "You are a stock trading AI. "}
        ],
    )

    print(response.choices[0].message.content)