import requests
import json
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:9213546700@localhost:5432/enso_db")

CLIMATE_QUERIES = [
    "El Nino OR La Nina OR ENSO climate",
    "climate drought flood agriculture commodity prices",
    "NOAA WMO weather forecast ocean temperature"
]

def fetch_enso_news():
    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set — skipping live news fetch")
        return []

    logger.info("Fetching fresh climate news from NewsAPI...")
    articles = []

    for query in CLIMATE_QUERIES:
        try:
            params = {
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 10,
                "apiKey": NEWS_API_KEY
            }
            response = requests.get(NEWS_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            articles.extend(data.get("articles", []))
        except Exception as e:
            logger.warning(f"NewsAPI query failed for '{query}': {e}")

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        title = a.get("title", "")
        if title and title not in seen:
            seen.add(title)
            unique.append(a)

    logger.info(f"Fetched {len(unique)} unique articles")

    # Save to file as backup
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("data/raw/news", exist_ok=True)
    filename = f"data/raw/news/headlines_{today}.json"
    with open(filename, "w") as f:
        json.dump(unique, f, indent=2)

    # Store to DB — replace today's news rows
    _store_to_db(unique)

    return unique


def _store_to_db(articles: list):
    try:
        engine = create_engine(DB_URL)
        today = datetime.now().strftime("%Y-%m-%d")
        rows = []
        for a in articles:
            title = a.get("title") or ""
            source = (a.get("source") or {}).get("name") or ""
            url = a.get("url") or ""
            published = (a.get("publishedAt") or today)[:10]
            if title:
                rows.append({"date": published, "title": title, "source": source, "url": url})

        with engine.connect() as conn:
            # Remove today's existing news to avoid duplicates on re-run
            conn.execute(text("DELETE FROM news_data WHERE date = :today"), {"today": today})
            for row in rows:
                conn.execute(text("""
                    INSERT INTO news_data (date, title, source, url)
                    VALUES (:date, :title, :source, :url)
                """), row)
            conn.commit()
        logger.info(f"Stored {len(rows)} fresh news articles to DB")
    except Exception as e:
        logger.error(f"Failed to store news to DB: {e}")


if __name__ == "__main__":
    fetch_enso_news()
