import requests
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    df.to_csv('data/raw/mei_index.csv', index=False)
    logger.info(f"Saved {len(df)} records to data/raw/mei_index.csv")
    
    # Quick sanity check
    print(df.tail(6))
    return df

if __name__ == "__main__":
    fetch_mei_data()