import os
import sys
import json
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:9213546700@localhost:5432/enso_db")

def startup():
    print("Running startup script...")
    engine = create_engine(DB_URL)
    
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS enso_data (
                id SERIAL PRIMARY KEY,
                date DATE UNIQUE,
                mei_value FLOAT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS news_data (
                id SERIAL PRIMARY KEY,
                date DATE,
                title TEXT,
                source TEXT,
                url TEXT
            )
        """))
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
    print("Tables created!")

    # Load and store MEI data
    try:
        df = pd.read_csv("data/raw/mei_index.csv")
        df.to_sql("enso_data", engine, if_exists="replace", index=False)
        print(f"Stored {len(df)} ENSO records")
    except Exception as e:
        print(f"ENSO data error: {e}")

    # Store commodity data
    try:
        import glob
        files = glob.glob("data/raw/commodity_prices_*.csv")
        if files:
            df = pd.read_csv(max(files))
            df.to_sql("commodity_prices", engine, if_exists="replace", index=False)
            print(f"Stored {len(df)} commodity records")
    except Exception as e:
        print(f"Commodity data error: {e}")

    print("Startup complete!")

if __name__ == "__main__":
    startup()