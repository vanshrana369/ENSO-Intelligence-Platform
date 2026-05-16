import os
import pandas as pd
import logging
import json
import glob
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
DB_URL = "postgresql://postgres:9213546700@localhost:5432/enso_db"

def get_engine():
    engine = create_engine(DB_URL)
    return engine

def create_tables(engine):
    logger.info("Creating tables...")
    
    with engine.connect() as conn:
        # ENSO data table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS enso_data (
                id SERIAL PRIMARY KEY,
                date DATE UNIQUE,
                mei_value FLOAT
            )
        """))

        # News data table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS news_data (
                id SERIAL PRIMARY KEY,
                date DATE,
                title TEXT,
                source TEXT,
                url TEXT
            )
        """))

        # Commodity prices table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS commodity_prices (
                id SERIAL PRIMARY KEY,
                date DATE,
                commodity TEXT,
                ticker TEXT,
                price FLOAT
            )
        """))

        conn.commit()
    logger.info("Tables created successfully!")

def store_enso_data(engine):
    logger.info("Storing ENSO data...")
    df = pd.read_csv("data/raw/mei_index.csv")
    df.to_sql("enso_data", engine, if_exists="replace", index=False)
    logger.info(f"Stored {len(df)} ENSO records")

def store_news_data(engine):
    logger.info("Storing news data...")
    
    files = glob.glob("data/raw/news/*.json")
    if not files:
        logger.warning("No news files found")
        return
    
    rows = []
    for file in files:
        with open(file) as f:
            articles = json.load(f)
        for article in articles:
            rows.append({
                "date": article.get("publishedAt", "")[:10],
                "title": article.get("title", ""),
                "source": article.get("source", {}).get("name", ""),
                "url": article.get("url", "")
            })
    
    df = pd.DataFrame(rows)
    df.to_sql("news_data", engine, if_exists="replace", index=False)
    logger.info(f"Stored {len(df)} news records")

def store_commodity_data(engine):
    logger.info("Storing commodity prices...")
    
    files = glob.glob("data/raw/commodity_prices_*.csv")
    if not files:
        logger.warning("No commodity files found")
        return
    
    latest_file = max(files)
    df = pd.read_csv(latest_file)
    df.to_sql("commodity_prices", engine, if_exists="replace", index=False)
    logger.info(f"Stored {len(df)} commodity records")

if __name__ == "__main__":
    engine = get_engine()
    create_tables(engine)
    store_enso_data(engine)
    store_news_data(engine)
    store_commodity_data(engine)
    logger.info("All data stored successfully!")