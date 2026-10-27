"""
Phase 4: DistilBERT Fine-Tuning
=================================
- Fine-tunes distilbert-base-uncased for 8-class dark pattern classification
- Weighted cross-entropy loss to handle class imbalance
- Early stopping on validation F1
- Saves best checkpoint + training loss curves
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import (
    DistilBertTokenizer, DistilBertForSequenceClassification,
    get_linear_schedule_with_warmup
)
from sklearn.metrics import f1_score, classification_report
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
import os
import time

# ============================================================
# CONFIG
# ============================================================
ALL_LABELS = [
    "Benign", "Urgency or Scarcity", "Disguised Ads", "Misdirection",
    "Confirmshaming", "Roach Motel", "Trick Questions", "Hidden Costs"
]
LABEL2ID = {label: idx for idx, label in enumerate(ALL_LABELS)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}
NUM_LABELS = len(ALL_LABELS)

MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 128
BATCH_SIZE = 16
LEARNING_RATE = 2e-5
NUM_EPOCHS = 10
PATIENCE = 3  # early stopping patience
CHECKPOINT_DIR = "./model_checkpoint"

# ============================================================
# DATASET CLASS
# ============================================================
class DarkPatternDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            str(self.texts[idx]),
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'labels': torch.tensor(self.labels[idx], dtype=torch.long)
        }


def compute_class_weights(labels):
    """Compute inverse frequency weights for class imbalance."""
    counts = np.bincount(labels, minlength=NUM_LABELS).astype(float)
    # Avoid division by zero
    counts[counts == 0] = 1.0
    weights = len(labels) / (NUM_LABELS * counts)
    return torch.tensor(weights, dtype=torch.float32)


def evaluate(model, dataloader, device):
    """Run evaluation and return predictions + true labels."""
    model.eval()
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            preds = torch.argmax(outputs.logits, dim=-1)

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    return np.array(all_preds), np.array(all_labels)


def main():
    print("=" * 60)
    print("PHASE 4: DistilBERT Fine-Tuning")
    print("=" * 60)

    # --- Device Selection ---
    device = torch.device("cpu")
    print(f"🖥️  Using device: CPU (Forced for reliability)")

    # --- Load Data ---
    train_df = pd.read_csv("train.csv")
    val_df = pd.read_csv("val.csv")

    train_texts = train_df['text'].tolist()
    val_texts = val_df['text'].tolist()
    train_labels = train_df['label'].map(LABEL2ID).values
    val_labels = val_df['label'].map(LABEL2ID).values

    print(f"Train: {len(train_texts)}, Val: {len(val_texts)}")

    # --- Tokenizer ---
    print(f"\n📦 Loading tokenizer: {MODEL_NAME}")
    tokenizer = DistilBertTokenizer.from_pretrained(MODEL_NAME)

    # --- Datasets & DataLoaders ---
    train_dataset = DarkPatternDataset(train_texts, train_labels, tokenizer, MAX_LENGTH)
    val_dataset = DarkPatternDataset(val_texts, val_labels, tokenizer, MAX_LENGTH)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

    # --- Model ---
    print(f"📦 Loading model: {MODEL_NAME}")
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL2ID
    )
    model.to(device)

    # --- Weighted Loss ---
    class_weights = compute_class_weights(train_labels)
    class_weights = class_weights.to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    print(f"\n⚖️  Class weights: {class_weights.cpu().numpy().round(2)}")

    # --- Optimizer & Scheduler ---
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)
    total_steps = len(train_loader) * NUM_EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(0.1 * total_steps),
        num_training_steps=total_steps
    )

    # --- Training Loop ---
    print(f"\n🏋️ Training for up to {NUM_EPOCHS} epochs (patience={PATIENCE})...")
    best_val_f1 = 0.0
    patience_counter = 0
    training_log = []

    for epoch in range(NUM_EPOCHS):
        model.train()
        total_loss = 0
        start_time = time.time()

        for batch_idx, batch in enumerate(train_loader):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            optimizer.zero_grad()
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = criterion(outputs.logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()

        avg_train_loss = total_loss / len(train_loader)
        epoch_time = time.time() - start_time

        # --- Validation ---
        val_preds, val_true = evaluate(model, val_loader, device)
        val_macro_f1 = f1_score(val_true, val_preds, average='macro')
        val_weighted_f1 = f1_score(val_true, val_preds, average='weighted')

        # Compute val loss
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                labels = batch['labels'].to(device)
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                val_loss += criterion(outputs.logits, labels).item()
        avg_val_loss = val_loss / len(val_loader)

        log_entry = {
            "epoch": epoch + 1,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
            "val_macro_f1": round(val_macro_f1, 4),
            "val_weighted_f1": round(val_weighted_f1, 4),
            "time_seconds": round(epoch_time, 1)
        }
        training_log.append(log_entry)

        print(f"  Epoch {epoch+1}/{NUM_EPOCHS} | "
              f"Train Loss: {avg_train_loss:.4f} | "
              f"Val Loss: {avg_val_loss:.4f} | "
              f"Val Macro F1: {val_macro_f1:.4f} | "
              f"Val Weighted F1: {val_weighted_f1:.4f} | "
              f"Time: {epoch_time:.1f}s")

        # --- Early Stopping & Checkpointing ---
        if val_macro_f1 > best_val_f1:
            best_val_f1 = val_macro_f1
            patience_counter = 0
            os.makedirs(CHECKPOINT_DIR, exist_ok=True)
            model.save_pretrained(CHECKPOINT_DIR)
            tokenizer.save_pretrained(CHECKPOINT_DIR)
            print(f"  ✅ Best model saved (F1: {best_val_f1:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"\n⏹️  Early stopping at epoch {epoch+1} (no improvement for {PATIENCE} epochs)")
                break

    # --- Save Training Log ---
    log_df = pd.DataFrame(training_log)
    log_df.to_csv("training_log.csv", index=False)
    print(f"\n✅ Training log saved to training_log.csv")

    # --- Plot Loss Curves ---
    os.makedirs("charts", exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    epochs = log_df['epoch']

    # Loss curves
    ax1.plot(epochs, log_df['train_loss'], 'b-o', label='Train Loss', linewidth=2, markersize=6)
    ax1.plot(epochs, log_df['val_loss'], 'r-o', label='Val Loss', linewidth=2, markersize=6)
    ax1.set_title("Training & Validation Loss", fontsize=14, fontweight='bold')
    ax1.set_xlabel("Epoch", fontsize=12)
    ax1.set_ylabel("Loss", fontsize=12)
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # F1 curves
    ax2.plot(epochs, log_df['val_macro_f1'], 'g-o', label='Macro F1', linewidth=2, markersize=6)
    ax2.plot(epochs, log_df['val_weighted_f1'], 'm-o', label='Weighted F1', linewidth=2, markersize=6)
    ax2.set_title("Validation F1 Scores", fontsize=14, fontweight='bold')
    ax2.set_xlabel("Epoch", fontsize=12)
    ax2.set_ylabel("F1 Score", fontsize=12)
    ax2.legend(fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 1)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig("charts/training_curves.png", dpi=150)
    plt.close()
    print("✅ Saved charts/training_curves.png")

    print(f"\n🎉 Phase 4 Complete!")
    print(f"   Best Validation Macro F1: {best_val_f1:.4f}")
    print(f"   Model checkpoint saved to: {CHECKPOINT_DIR}/")


if __name__ == "__main__":
    main()
