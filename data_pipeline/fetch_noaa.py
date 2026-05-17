import os
import requests
import pandas as pd
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:9213546700@localhost:5432/enso_db")

NOAA_MEI_URL = "https://psl.noaa.gov/enso/mei/data/meiv2.data"

def fetch_mei_data():
    logger.info("Fetching MEI data from NOAA...")
    
    response = requests.get(NOAA_MEI_URL, timeout=10)
    response.raise_for_status()
    
    lines = response.text.strip().split('\n')
    
    # Skip header lines (they don't start with a year number)
    data_lines = [l for l in lines if l.strip()[:4].isdigit()]
    
    months = ['Jan','Feb','Mar','Apr','May','Jun',
              'Jul','Aug','Sep','Oct','Nov','Dec']
    
    rows = []
    for line in data_lines:
        values = line.split()
        year = int(values[0])
        for i, month in enumerate(months):
            if i + 1 >= len(values):  # handles incomplete years like 2026
                break
            val = float(values[i+1])
            if val == -999.0:   # missing data
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

    # Store to DB
    try:
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