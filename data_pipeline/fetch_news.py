import requests
import json
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"

def fetch_enso_news():
    logger.info("Fetching El Nino related news...")

    params = {
        "q": "El Nino OR La Nina OR ENSO climate",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 20,
        "apiKey": NEWS_API_KEY
    }

    response = requests.get(NEWS_API_URL, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()
    articles = data["articles"]

    # Save with today's date in filename
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("data/raw/news", exist_ok=True)
    filename = f"data/raw/news/headlines_{today}.json"

    with open(filename, "w") as f:
        json.dump(articles, f, indent=2)

    logger.info(f"Saved {len(articles)} articles to {filename}")

    # Print first 3 headlines
    for i, article in enumerate(articles[:3]):
        print(f"{i+1}. {article['title']}")

    return articles

if __name__ == "__main__":
    fetch_enso_news()