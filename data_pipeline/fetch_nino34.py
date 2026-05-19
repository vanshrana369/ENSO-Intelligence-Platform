"""
Fetch monthly Niño3.4 SST anomaly from NOAA CPC sstoi.indices.

Updates every ~month — more current than MEI v2 (bimonthly, ~2-month lag).
Used as the live current-phase indicator when MEI is lagged.

Source: https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices
Format: YR MON  NINO1+2 ANOM  NINO3 ANOM  NINO4 ANOM  NINO3.4 ANOM
         0   1    2      3      4     5      6     7      8       9
"""
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

NINO34_URL = "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices"


def fetch_nino34_weekly() -> dict | None:
    """
    Returns the most recent monthly Niño3.4 SST anomaly as a dict:
      { 'date': '2026-04-01', 'nino34_anom': 0.47, 'phase': 'Neutral' }
    Returns None on failure.
    """
    try:
        resp = requests.get(NINO34_URL, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Niño3.4 fetch failed: {e}")
        return None

    latest_yr   = None
    latest_mon  = None
    latest_anom = None

    for line in resp.text.splitlines():
        tokens = line.split()
        if len(tokens) < 10:
            continue
        try:
            yr   = int(tokens[0])
            mon  = int(tokens[1])
            anom = float(tokens[9])   # NINO3.4 SST anomaly
        except (ValueError, IndexError):
            continue
        if latest_yr is None or (yr, mon) > (latest_yr, latest_mon):
            latest_yr   = yr
            latest_mon  = mon
            latest_anom = anom

    if latest_yr is None:
        logger.warning("Niño3.4 parse returned no rows")
        return None

    date_str = f"{latest_yr}-{latest_mon:02d}-01"
    phase = ('El Niño' if latest_anom >= 0.5
             else 'La Niña' if latest_anom <= -0.5
             else 'Neutral')

    logger.info(f"Niño3.4 (sstoi): {date_str}  anomaly={latest_anom:+.2f}  phase={phase}")
    return {'date': date_str, 'nino34_anom': round(float(latest_anom), 2), 'phase': phase}


if __name__ == '__main__':
    result = fetch_nino34_weekly()
    print(result)
