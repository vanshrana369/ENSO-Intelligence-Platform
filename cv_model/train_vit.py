import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from transformers import ViTForImageClassification, ViTImageProcessor
import pandas as pd
import numpy as np
from PIL import Image
import os
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns

print(f"GPU available: {torch.cuda.is_available()}")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using: {device}")

class SSTDataset(Dataset):
    def __init__(self, df, processor):
        self.df = df.reset_index(drop=True)
        self.processor = processor

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = f"data/processed/images/{row['filename']}"
        img = Image.open(img_path).convert('RGB')
        inputs = self.processor(images=img, return_tensors="pt")
        pixel_values = inputs['pixel_values'].squeeze(0)
        label = int(row['label'])
        return pixel_values, label

# Load data
df = pd.read_csv("data/processed/labels.csv")
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

n = len(df)
train_df = df[:int(0.7*n)]
val_df = df[int(0.7*n):int(0.85*n)]
test_df = df[int(0.85*n):]

print(f"Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")

# Load ViT
print("\nLoading ViT-base from HuggingFace...")
processor = ViTImageProcessor.from_pretrained('google/vit-base-patch16-224')
model = ViTForImageClassification.from_pretrained(
    'google/vit-base-patch16-224',
    num_labels=3,
    ignore_mismatched_sizes=True
)
model = model.to(device)
print("ViT loaded successfully!")

train_loader = DataLoader(SSTDataset(train_df, processor), batch_size=16, shuffle=True)
val_loader = DataLoader(SSTDataset(val_df, processor), batch_size=16)
test_loader = DataLoader(SSTDataset(test_df, processor), batch_size=16)

optimizer = optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=15)
criterion = nn.CrossEntropyLoss()

best_val_acc = 0
val_accs = []

print("\nFine-tuning ViT...")
for epoch in range(15):
    model.train()
    total_loss = 0
    for imgs, labels in train_loader:
        imgs, labels = imgs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(pixel_values=imgs)
        loss = criterion(outputs.logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for imgs, labels in val_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            outputs = model(pixel_values=imgs)
            _, predicted = torch.max(outputs.logits, 1)
            correct += (predicted == labels).sum().item()
            total += labels.size(0)

    val_acc = correct / total * 100
    val_accs.append(val_acc)
    avg_loss = total_loss / len(train_loader)
    scheduler.step()

    if val_acc > best_val_acc:
        best_val_acc = val_acc
        model.save_pretrained('cv_model/best_vit')
        processor.save_pretrained('cv_model/best_vit')

    print(f"Epoch {epoch+1}/15 | Loss: {avg_loss:.4f} | Val Acc: {val_acc:.1f}%")

print(f"\nBest Val Accuracy: {best_val_acc:.1f}%")

# Test evaluation
model = ViTForImageClassification.from_pretrained('cv_model/best_vit').to(device)
model.eval()

all_preds = []
all_labels = []
with torch.no_grad():
    for imgs, labels in test_loader:
        imgs = imgs.to(device)
        outputs = model(pixel_values=imgs)
        _, predicted = torch.max(outputs.logits, 1)
        all_preds.extend(predicted.cpu().numpy())
        all_labels.extend(labels.numpy())

print("\nClassification Report:")
print(classification_report(all_labels, all_preds,
      target_names=['El Nino', 'La Nina', 'Neutral']))

# Save confusion matrix
os.makedirs("outputs/cv_results", exist_ok=True)
cm = confusion_matrix(all_labels, all_preds)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['El Nino', 'La Nina', 'Neutral'],
            yticklabels=['El Nino', 'La Nina', 'Neutral'])
plt.title('ViT Confusion Matrix')
plt.savefig('outputs/cv_results/vit_confusion_matrix.png', dpi=100, bbox_inches='tight')

print("\nViT model saved to cv_model/best_vit/")
print("Confusion matrix saved to outputs/cv_results/")