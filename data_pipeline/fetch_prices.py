import yfinance as yf
import pandas as pd
import os
import time
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

def _download_with_retry(ticker, period="5y", interval="1d", attempts=3):
    """Download one ticker, retrying with backoff.

    yfinance throttles rapid sequential requests — without retries a few of the
    8 commodities silently come back empty and get dropped from the dataset.
    """
    for i in range(attempts):
        try:
            data = yf.download(ticker, period=period, interval=interval, progress=False)
            if not data.empty:
                return data
            logger.warning(f"{ticker}: empty response (attempt {i + 1}/{attempts})")
        except Exception as e:
            logger.warning(f"{ticker}: download failed (attempt {i + 1}/{attempts}): {e}")
        time.sleep(2 * (i + 1))  # linear backoff: 2s, 4s, 6s
    return None


def fetch_commodity_prices():
    logger.info("Fetching commodity prices...")

    all_data = []

    for name, ticker in COMMODITIES.items():
        logger.info(f"Fetching {name} ({ticker})...")

        data = _download_with_retry(ticker)

        if data is None or data.empty:
            logger.warning(f"No data for {name} after retries — skipping")
            continue

        data = data[["Close"]].copy()
        data.columns = ["price"]
        data["commodity"] = name
        data["ticker"] = ticker
        data["date"] = data.index

        all_data.append(data)
        time.sleep(1)  # gentle pacing between tickers to avoid rate limiting

    if not all_data:
        logger.error("No commodity data fetched for any ticker — aborting save")
        return pd.DataFrame(columns=["date", "commodity", "ticker", "price"])

    fetched = sorted({d["commodity"].iloc[0] for d in all_data})
    logger.info(f"Fetched {len(fetched)}/{len(COMMODITIES)} commodities: {', '.join(fetched)}")

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
        sub = df[df["commodity"] == name]
        if sub.empty:
            continue
        latest = sub.iloc[-1]
        print(f"  {name}: ${latest['price']:.2f}")

    return df

if __name__ == "__main__":
    fetch_commodity_prices()