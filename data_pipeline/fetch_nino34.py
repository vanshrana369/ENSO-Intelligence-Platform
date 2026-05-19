"""
Fetch weekly Niño3.4 SST anomaly from NOAA CPC.

This updates every week — much faster than MEI v2 (bimonthly, ~2mo lag).
Used as the live current-phase indicator when MEI is lagged.

Source: https://www.cpc.ncep.noaa.gov/data/indices/wksst8110.for
Format: date  nino12_sst  nino12_anom  nino3_sst  nino3_anom  nino34_sst  nino34_anom  nino4_sst  nino4_anom
"""
import requests
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

NINO34_URL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst8110.for"


def fetch_nino34_weekly() -> dict | None:
    """
    Returns the most recent weekly Niño3.4 SST anomaly as a dict:
      { 'date': '2026-05-13', 'nino34_anom': 0.9, 'phase': 'El Niño' }
    Returns None on failure.
    """
    try:
        resp = requests.get(NINO34_URL, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Niño3.4 fetch failed: {e}")
        return None

    rows = []
    for line in resp.text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        tokens = line.split()
        # Lines look like: "03JAN1990  28.1  0.5  28.3  0.7  28.4  0.9  29.1  0.3"
        # (NOAA uses DDMMMYYYY — no hyphens.  Skip header / annotation lines.)
        if len(tokens) < 8:
            continue
        date = None
        for fmt in ('%d%b%Y', '%d-%b-%Y'):
            try:
                date = pd.to_datetime(tokens[0].upper(), format=fmt.upper())
                break
            except ValueError:
                continue
        if date is None:
            continue
        try:
            nino34_anom = float(tokens[6])  # Niño3.4 SST anomaly column
        except (IndexError, ValueError):
            continue
        rows.append({'date': date, 'nino34_anom': nino34_anom})

    if not rows:
        logger.warning("Niño3.4 parse returned no rows")
        return None

    df = pd.DataFrame(rows).sort_values('date')
    latest = df.iloc[-1]
    anom = float(latest['nino34_anom'])
    date_str = latest['date'].strftime('%Y-%m-%d')

    phase = 'El Niño' if anom >= 0.5 else 'La Niña' if anom <= -0.5 else 'Neutral'

    logger.info(f"Niño3.4 weekly: {date_str}  anomaly={anom:+.2f}  phase={phase}")
    return {'date': date_str, 'nino34_anom': anom, 'phase': phase}


if __name__ == '__main__':
    result = fetch_nino34_weekly()
    print(result)
