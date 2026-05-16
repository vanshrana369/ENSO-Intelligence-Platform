import requests
import os
import numpy as np
import pandas as pd

print("Downloading ERSST v5 data from NOAA...")

# NOAA ERSST v5 - monthly SST data from 1854 to present
# This is the gold standard dataset for ENSO research
URL = "https://downloads.psl.noaa.gov/Datasets/noaa.ersst.v5/sst.mnmean.nc"

os.makedirs("data/raw/sst_data", exist_ok=True)
output_path = "data/raw/sst_data/sst.mnmean.nc"

if os.path.exists(output_path):
    print("File already exists!")
else:
    print("Downloading... this may take a few minutes (30-40MB)")
    response = requests.get(URL, stream=True)
    total = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                print(f"\rProgress: {pct:.1f}%", end='')

print(f"\nSaved to {output_path}")
print("Done!")