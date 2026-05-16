import yfinance as yf
import pandas as pd
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COMMODITIES = {
    "wheat": "ZW=F",
    "crude_oil": "CL=F",
    "soybean": "ZS=F"
}

def fetch_commodity_prices():
    print("Script started...")
    logger.info("Fetching commodity prices...")

    all_data = []

    for name, ticker in COMMODITIES.items():
        print(f"Trying {name} ({ticker})...")
        try:
            data = yf.download(ticker, period="3mo", interval="1d", progress=False)
            print(f"Got {len(data)} rows for {name}")
            
            if data.empty:
                print(f"WARNING: No data for {name}")
                continue

            data = data[["Close"]].copy()
            data.columns = ["price"]
            data["commodity"] = name
            data["ticker"] = ticker
            data["date"] = data.index
            all_data.append(data)

        except Exception as e:
            print(f"ERROR for {name}: {e}")

    if not all_data:
        print("No data fetched for any commodity!")
        return None

    df = pd.concat(all_data)
    df = df.reset_index(drop=True)
    df = df[["date", "commodity", "ticker", "price"]]

    os.makedirs("data/raw", exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"data/raw/commodity_prices_{today}.csv"
    df.to_csv(filename, index=False)

    logger.info(f"Saved {len(df)} records to {filename}")

    print("\nLatest Prices:")
    for name in COMMODITIES:
        latest = df[df["commodity"] == name].iloc[-1]
        print(f"  {name}: ${latest['price']:.2f}")

    return df

if __name__ == "__main__":
    fetch_commodity_prices()