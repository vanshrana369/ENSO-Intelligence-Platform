import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import pandas as pd
import numpy as np
from PIL import Image
import os
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns

print(f"GPU available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using: {device}")

# Dataset
class SSTDataset(Dataset):
    def __init__(self, df, transform=None):
        self.df = df.reset_index(drop=True)
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = f"data/processed/images/{row['filename']}"
        img = Image.open(img_path).convert('RGB')
        if self.transform:
            img = self.transform(img)
        label = int(row['label'])
        return img, label

# CNN Model
class ENSOCNN(nn.Module):
    def __init__(self):
        super(ENSOCNN, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(128, 256, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(4)
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256 * 4 * 4, 512),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(512, 3)
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x

# Load data
df = pd.read_csv("data/processed/labels.csv")
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

# Split
n = len(df)
train_df = df[:int(0.7*n)]
val_df = df[int(0.7*n):int(0.85*n)]
test_df = df[int(0.85*n):]

print(f"\nTrain: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")

# Transforms
train_transform = transforms.Compose([
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),
    transforms.ToTensor(),
    transforms.Normalize([0.5], [0.5])
])
val_transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize([0.5], [0.5])
])

train_loader = DataLoader(SSTDataset(train_df, train_transform), batch_size=32, shuffle=True)
val_loader = DataLoader(SSTDataset(val_df, val_transform), batch_size=32)
test_loader = DataLoader(SSTDataset(test_df, val_transform), batch_size=32)

# Train
model = ENSOCNN().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

train_losses = []
val_accs = []
best_val_acc = 0

print("\nStarting training...")
for epoch in range(30):
    model.train()
    total_loss = 0
    for imgs, labels in train_loader:
        imgs, labels = imgs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    # Validation
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for imgs, labels in val_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            outputs = model(imgs)
            _, predicted = torch.max(outputs, 1)
            correct += (predicted == labels).sum().item()
            total += labels.size(0)

    val_acc = correct / total * 100
    avg_loss = total_loss / len(train_loader)
    train_losses.append(avg_loss)
    val_accs.append(val_acc)
    scheduler.step()

    if val_acc > best_val_acc:
        best_val_acc = val_acc
        torch.save(model.state_dict(), 'cv_model/best_cnn.pth')

    if (epoch + 1) % 5 == 0:
        print(f"Epoch {epoch+1}/30 | Loss: {avg_loss:.4f} | Val Acc: {val_acc:.1f}%")

print(f"\nBest Val Accuracy: {best_val_acc:.1f}%")

# Test evaluation
model.load_state_dict(torch.load('cv_model/best_cnn.pth'))
model.eval()
all_preds = []
all_labels = []
with torch.no_grad():
    for imgs, labels in test_loader:
        imgs = imgs.to(device)
        outputs = model(imgs)
        _, predicted = torch.max(outputs, 1)
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
plt.title('CNN Confusion Matrix')
plt.savefig('outputs/cv_results/confusion_matrix.png', dpi=100, bbox_inches='tight')
plt.close()

# Save loss curve
plt.figure(figsize=(10, 4))
plt.subplot(1, 2, 1)
plt.plot(train_losses)
plt.title('Training Loss')
plt.subplot(1, 2, 2)
plt.plot(val_accs)
plt.title('Validation Accuracy')
plt.savefig('outputs/cv_results/training_curves.png', dpi=100, bbox_inches='tight')
plt.close()

print("\nResults saved to outputs/cv_results/")
print("Model saved to cv_model/best_cnn.pth")