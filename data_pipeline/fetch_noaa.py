import os
import requests
import pandas as pd
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "")

NOAA_MEI_URL = "https://psl.noaa.gov/enso/mei/data/meiv2.data"

def fetch_mei_data():
    logger.info("Fetching MEI data from NOAA...")
    
    response = requests.get(NOAA_MEI_URL, timeout=10)
    response.raise_for_status()
    
    lines = response.text.strip().split('\n')

    months = ['Jan','Feb','Mar','Apr','May','Jun',
              'Jul','Aug','Sep','Oct','Nov','Dec']

    rows = []
    for line in lines:
        tokens = line.split()
        # Need at least year + 1 monthly value
        if len(tokens) < 2:
            continue
        try:
            year = int(tokens[0])
        except ValueError:
            continue
        # Skip out-of-range years
        if year < 1950 or year > 2100:
            continue
        # The NOAA header line looks like "1979 2026" — exactly 2 tokens,
        # both 4-digit years. Detect and skip it.
        if len(tokens) == 2:
            try:
                second = int(tokens[1])
                if 1950 <= second <= 2100:
                    continue  # It's the year-range header, not data
            except ValueError:
                pass

        for i, month in enumerate(months):
            if i + 1 >= len(tokens):   # handles incomplete current year
                break
            try:
                val = float(tokens[i + 1])
            except ValueError:
                continue
            if val == -999.0:           # NOAA missing-data sentinel
                val = None
            rows.append({
                'date': f"{year}-{str(i+1).zfill(2)}-01",
                'mei_value': val
            })
    
    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    df = df.dropna()
    
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv('data/raw/mei_index.csv', index=False)
    logger.info(f"Saved {len(df)} records to data/raw/mei_index.csv")

    # Store to DB (skipped if no DATABASE_URL configured)
    if DB_URL:
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(DB_URL)
            with engine.connect() as conn:
                conn.execute(text("TRUNCATE TABLE enso_data"))
                for _, row in df.iterrows():
                    conn.execute(text(
                        "INSERT INTO enso_data (date, mei_value) VALUES (:date, :mei_value)"
                    ), {"date": str(row["date"])[:10], "mei_value": float(row["mei_value"])})
                conn.commit()
            logger.info(f"Stored {len(df)} MEI records to DB")
        except Exception as e:
            logger.error(f"Failed to store MEI data to DB: {e}")

    print(df.tail(6))
    return df

if __name__ == "__main__":
    fetch_mei_data()