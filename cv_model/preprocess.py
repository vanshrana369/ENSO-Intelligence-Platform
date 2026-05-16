import xarray as xr
import numpy as np
import pandas as pd
import os
from PIL import Image

print("Starting preprocessing...")

# Load SST data
ds = xr.open_dataset("data/raw/sst_data/sst.mnmean.nc")
nino34 = ds.sst.sel(lat=slice(5, -5), lon=slice(190, 240))

# Load MEI labels
mei = pd.read_csv("data/raw/mei_index.csv")
mei['date'] = pd.to_datetime(mei['date'])
mei['year'] = mei['date'].dt.year
mei['month'] = mei['date'].dt.month

def get_label(mei_value):
    if mei_value >= 0.5:
        return 0  # El Nino
    elif mei_value <= -0.5:
        return 1  # La Nina
    else:
        return 2  # Neutral

os.makedirs("data/processed/images", exist_ok=True)

records = []
saved = 0
skipped = 0

for i in range(len(nino34.time)):
    t = pd.Timestamp(nino34.time.values[i])
    year = t.year
    month = t.month

    # Find matching MEI label
    match = mei[(mei['year'] == year) & (mei['month'] == month)]
    if len(match) == 0:
        skipped += 1
        continue

    mei_value = float(match['mei_value'].values[0])
    label = get_label(mei_value)
    label_name = ['el_nino', 'la_nina', 'neutral'][label]

    # Get SST image
    sst_img = nino34.isel(time=i).values

    # Handle NaN values
    sst_img = np.where(np.isnan(sst_img), 0, sst_img)

    # Normalize to 0-255
    sst_min, sst_max = 20.0, 32.0
    sst_norm = np.clip((sst_img - sst_min) / (sst_max - sst_min), 0, 1)
    sst_uint8 = (sst_norm * 255).astype(np.uint8)

    # Resize to 64x64 for CNN
    img = Image.fromarray(sst_uint8)
    img = img.resize((64, 64), Image.BILINEAR)

    # Save
    filename = f"{year}_{month:02d}_{label_name}.png"
    img.save(f"data/processed/images/{filename}")

    records.append({
        'filename': filename,
        'year': year,
        'month': month,
        'mei_value': mei_value,
        'label': label,
        'label_name': label_name
    })
    saved += 1

# Save labels CSV
df = pd.DataFrame(records)
df.to_csv("data/processed/labels.csv", index=False)

print(f"\nPreprocessing complete!")
print(f"Images saved: {saved}")
print(f"Skipped (no MEI label): {skipped}")
print(f"\nLabel distribution:")
print(df['label_name'].value_counts())
print(f"\nSaved to data/processed/images/")
print(f"Labels saved to data/processed/labels.csv")