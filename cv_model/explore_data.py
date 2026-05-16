import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import os

print("Loading ERSST v5 data...")

ds = xr.open_dataset("data/raw/sst_data/sst.mnmean.nc")

print("\n=== Dataset Info ===")
print(ds)

print("\n=== Dimensions ===")
print(dict(ds.dims))

print("\n=== Variables ===")
print(list(ds.variables))

print("\n=== Time range ===")
print(f"Start: {ds.time.values[0]}")
print(f"End: {ds.time.values[-1]}")
print(f"Total months: {len(ds.time)}")

# Crop to Nino 3.4 region
# Nino 3.4: 5N-5S, 170W-120W
# In ERSST coords: lat -5 to 5, lon 190 to 240
nino34 = ds.sst.sel(
    lat=slice(5, -5),
    lon=slice(190, 240)
)

print(f"\n=== Nino 3.4 Region Shape ===")
print(f"Shape: {nino34.shape}")
print(f"Lat range: {float(nino34.lat.min())} to {float(nino34.lat.max())}")
print(f"Lon range: {float(nino34.lon.min())} to {float(nino34.lon.max())}")

# Plot one sample month
os.makedirs("outputs/sst_samples", exist_ok=True)
sample = nino34.isel(time=0)
plt.figure(figsize=(10, 3))
plt.imshow(sample.values, cmap='RdBu_r', aspect='auto')
plt.colorbar(label='SST (°C)')
plt.title(f"Nino 3.4 SST - {str(ds.time.values[0])[:7]}")
plt.savefig("outputs/sst_samples/sample_sst.png", dpi=100, bbox_inches='tight')
plt.close()

print("\nSample image saved to outputs/sst_samples/sample_sst.png")
print("\nData exploration complete!")
