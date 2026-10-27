"""
Phase 3: TF-IDF Baseline Classifier
======================================
- TF-IDF vectorizer + Logistic Regression
- Per-class F1, macro F1, precision, recall
- Confusion matrix heatmap
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
import json
import os

ALL_LABELS = [
    "Benign", "Urgency or Scarcity", "Disguised Ads", "Misdirection",
    "Confirmshaming", "Roach Motel", "Trick Questions", "Hidden Costs"
]

def main():
    print("=" * 60)
    print("PHASE 3: TF-IDF Baseline Classifier")
    print("=" * 60)

    # --- Load Data ---
    train_df = pd.read_csv("train.csv")
    val_df = pd.read_csv("val.csv")
    test_df = pd.read_csv("test.csv")

    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    # --- TF-IDF Vectorization ---
    print("\n🔧 Building TF-IDF features...")
    tfidf = TfidfVectorizer(
        max_features=10000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True
    )

    X_train = tfidf.fit_transform(train_df['text'].astype(str))
    X_val = tfidf.transform(val_df['text'].astype(str))
    X_test = tfidf.transform(test_df['text'].astype(str))

    y_train = train_df['label']
    y_val = val_df['label']
    y_test = test_df['label']

    # --- Train Logistic Regression ---
    print("🏋️ Training Logistic Regression (class_weight=balanced)...")
    clf = LogisticRegression(
        max_iter=1000,
        class_weight='balanced',
        C=1.0,
        random_state=42,
        multi_class='multinomial',
        solver='lbfgs'
    )
    clf.fit(X_train, y_train)

    # --- Evaluate on Validation Set ---
    y_val_pred = clf.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='macro')
    print(f"\n📊 Validation Macro F1: {val_f1:.4f}")

    # --- Evaluate on Test Set ---
    y_test_pred = clf.predict(X_test)

    print("\n" + "=" * 60)
    print("TEST SET EVALUATION")
    print("=" * 60)

    report = classification_report(
        y_test, y_test_pred, 
        labels=ALL_LABELS, 
        target_names=ALL_LABELS,
        zero_division=0,
        output_dict=True
    )
    report_str = classification_report(
        y_test, y_test_pred,
        labels=ALL_LABELS,
        target_names=ALL_LABELS,
        zero_division=0
    )
    print(report_str)

    test_macro_f1 = f1_score(y_test, y_test_pred, average='macro')
    test_weighted_f1 = f1_score(y_test, y_test_pred, average='weighted')
    print(f"Macro F1:    {test_macro_f1:.4f}")
    print(f"Weighted F1: {test_weighted_f1:.4f}")

    # --- Confusion Matrix ---
    os.makedirs("charts", exist_ok=True)
    cm = confusion_matrix(y_test, y_test_pred, labels=ALL_LABELS)

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=ALL_LABELS, yticklabels=ALL_LABELS,
                ax=ax, linewidths=0.5, linecolor='white')
    ax.set_title("TF-IDF Baseline — Confusion Matrix (Test Set)", fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Predicted Label", fontsize=12)
    ax.set_ylabel("True Label", fontsize=12)
    plt.xticks(rotation=35, ha='right', fontsize=9)
    plt.yticks(rotation=0, fontsize=9)
    plt.tight_layout()
    plt.savefig("charts/tfidf_confusion_matrix.png", dpi=150)
    plt.close()
    print("\n✅ Saved charts/tfidf_confusion_matrix.png")

    # --- Save Results ---
    baseline_results = {
        "model": "TF-IDF + LogisticRegression",
        "tfidf_features": X_train.shape[1],
        "validation_macro_f1": round(val_f1, 4),
        "test_macro_f1": round(test_macro_f1, 4),
        "test_weighted_f1": round(test_weighted_f1, 4),
        "per_class_f1": {
            label: round(report[label]['f1-score'], 4) for label in ALL_LABELS
        },
        "per_class_precision": {
            label: round(report[label]['precision'], 4) for label in ALL_LABELS
        },
        "per_class_recall": {
            label: round(report[label]['recall'], 4) for label in ALL_LABELS
        }
    }

    with open("baseline_results.json", "w") as f:
        json.dump(baseline_results, f, indent=2)

    print("✅ Saved baseline_results.json")
    print("\n🎉 Phase 3 Complete!")


if __name__ == "__main__":
    main()
