import torch
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from transformers import ViTForImageClassification, ViTImageProcessor
import os
import pandas as pd
import xarray as xr

print("Loading ViT model...")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

processor = ViTImageProcessor.from_pretrained('cv_model/best_vit')
model = ViTForImageClassification.from_pretrained('cv_model/best_vit').to(device)
model.eval()

label_names = ['El Nino', 'La Nina', 'Neutral']
label_colors = ['#FF4444', '#4444FF', '#888888']

ds = xr.open_dataset("data/raw/sst_data/sst.mnmean.nc")
nino34 = ds.sst.sel(lat=slice(5, -5), lon=slice(190, 240))

def predict_image(img_path):
    img = Image.open(img_path).convert('RGB')
    inputs = processor(images=img, return_tensors="pt")
    pixel_values = inputs['pixel_values'].to(device)
    with torch.no_grad():
        outputs = model(pixel_values=pixel_values)
    pred = torch.argmax(outputs.logits, dim=1).item()
    confidence = torch.softmax(outputs.logits, dim=1)[0][pred].item()
    all_probs = torch.softmax(outputs.logits, dim=1)[0].cpu().numpy()
    return pred, confidence, all_probs

def visualize_sample(row, save_path):
    year = int(row['year'])
    month = int(row['month'])
    label_name = row['label_name']
    mei_value = row['mei_value']

    img_path = f"data/processed/images/{row['filename']}"
    pred, confidence, all_probs = predict_image(img_path)

    # Get raw SST data
    time_match = [(i, t) for i, t in enumerate(nino34.time.values)
                  if str(t)[:7] == f"{year}-{month:02d}"]

    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    fig.patch.set_facecolor('#0d1520')

    if time_match:
        idx = time_match[0][0]
        sst_raw = nino34.isel(time=idx).values
        sst_raw = np.where(np.isnan(sst_raw), np.nanmean(sst_raw), sst_raw)

        # SST Image
        im0 = axes[0].imshow(sst_raw, cmap='RdBu_r', aspect='auto',
                             vmin=24, vmax=30)
        plt.colorbar(im0, ax=axes[0], label='°C')
        axes[0].set_title(f'SST - Nino 3.4 Region\n{year}-{month:02d}',
                         color='white', fontsize=11)

        # Anomaly heatmap
        mean_sst = float(np.nanmean(sst_raw))
        anomaly = sst_raw - mean_sst
        im1 = axes[1].imshow(anomaly, cmap='RdBu_r', aspect='auto',
                            vmin=-1, vmax=1)
        plt.colorbar(im1, ax=axes[1], label='Anomaly °C')
        axes[1].set_title('SST Anomaly\n(Deviation from mean)',
                         color='white', fontsize=11)

    else:
        axes[0].text(0.5, 0.5, 'No SST data', ha='center', va='center',
                    color='white', transform=axes[0].transAxes)
        axes[1].text(0.5, 0.5, 'No SST data', ha='center', va='center',
                    color='white', transform=axes[1].transAxes)

    # Prediction bar chart
    colors = ['#FF4444', '#4444FF', '#888888']
    bars = axes[2].barh(label_names, all_probs * 100, color=colors, alpha=0.8)
    axes[2].set_xlim(0, 100)
    axes[2].set_xlabel('Confidence %', color='white')
    axes[2].set_title(
        f'Model Prediction\n{label_names[pred]} ({confidence*100:.1f}%)',
        color=label_colors[pred], fontsize=11, fontweight='bold'
    )
    axes[2].tick_params(colors='white')
    axes[2].spines['bottom'].set_color('#334155')
    axes[2].spines['left'].set_color('#334155')
    axes[2].spines['top'].set_visible(False)
    axes[2].spines['right'].set_visible(False)
    axes[2].set_facecolor('#0d1520')

    for ax in axes[:2]:
        ax.set_facecolor('#0d1520')
        ax.tick_params(colors='white')

    true_label = label_name.replace('_', ' ').title()
    correct = label_names[pred].replace(' ', '_').lower() == label_name
    status = "✓ CORRECT" if correct else "✗ WRONG"
    status_color = '#4ade80' if correct else '#f87171'

    fig.suptitle(
        f"True: {true_label} | MEI: {mei_value:.2f} | {status}",
        color=status_color, fontsize=13, fontweight='bold'
    )
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#0d1520')
    plt.close()
    print(f"Saved: {save_path} | Predicted: {label_names[pred]} ({confidence*100:.1f}%)")

os.makedirs("outputs/gradcam", exist_ok=True)
df = pd.read_csv("data/processed/labels.csv")

for label_name in ['el_nino', 'la_nina', 'neutral']:
    samples = df[df['label_name'] == label_name]
    if len(samples) == 0:
        continue
    sample = samples.iloc[0]
    save_path = f"outputs/gradcam/{label_name}_visualization.png"
    visualize_sample(sample, save_path)

print("\nVisualizations saved to outputs/gradcam/")
print("These show real SST data + model predictions!")