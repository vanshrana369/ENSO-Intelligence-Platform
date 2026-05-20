import yfinance as yf
import pandas as pd
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "")

# Commodity ticker symbols — all ENSO-sensitive markets
COMMODITIES = {
    "wheat":       "ZW=F",
    "crude_oil":   "CL=F",
    "soybean":     "ZS=F",
    "corn":        "ZC=F",
    "coffee":      "KC=F",
    "sugar":       "SB=F",
    "cotton":      "CT=F",
    "natural_gas": "NG=F",
}

def fetch_commodity_prices():
    logger.info("Fetching commodity prices...")

    all_data = []

    for name, ticker in COMMODITIES.items():
        logger.info(f"Fetching {name} ({ticker})...")
        
        data = yf.download(ticker, period="3mo", interval="1d", progress=False)
        
        if data.empty:
            logger.warning(f"No data for {name}")
            continue

        data = data[["Close"]].copy()
        data.columns = ["price"]
        data["commodity"] = name
        data["ticker"] = ticker
        data["date"] = data.index

        all_data.append(data)

    # Combine all commodities into one dataframe
    df = pd.concat(all_data)
    df = df.reset_index(drop=True)
    df = df[["date", "commodity", "ticker", "price"]]

    # Save to CSV
    os.makedirs("data/raw", exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"data/raw/commodity_prices_{today}.csv"
    df.to_csv(filename, index=False)

    logger.info(f"Saved {len(df)} records to {filename}")

    # Store to DB (skipped if no DATABASE_URL configured)
    if DB_URL:
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(DB_URL)
            with engine.connect() as conn:
                conn.execute(text("TRUNCATE TABLE commodity_prices"))
                for _, row in df.iterrows():
                    conn.execute(text("""
                        INSERT INTO commodity_prices (date, commodity, ticker, price)
                        VALUES (:date, :commodity, :ticker, :price)
                    """), {
                        "date": str(row["date"])[:10],
                        "commodity": row["commodity"],
                        "ticker": row["ticker"],
                        "price": float(row["price"])
                    })
                conn.commit()
            logger.info(f"Stored {len(df)} commodity price records to DB")
        except Exception as e:
            logger.error(f"Failed to store commodity prices to DB: {e}")

    print("\nLatest Prices:")
    for name in COMMODITIES:
        latest = df[df["commodity"] == name].iloc[-1]
        print(f"  {name}: ${latest['price']:.2f}")

    return df

if __name__ == "__main__":
    fetch_commodity_prices()