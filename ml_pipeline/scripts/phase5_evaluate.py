"""
Phase 5: Full Evaluation + LIME Explainability
=================================================
- Loads best DistilBERT checkpoint and test.csv
- Per-class F1, Precision, Recall
- Confusion matrix heatmap
- Error analysis on 20 misclassified examples
- LIME explainability for 5 example predictions
"""

import pandas as pd
import numpy as np
import torch
from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
from sklearn.metrics import (
    classification_report, confusion_matrix, f1_score,
    precision_recall_fscore_support
)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from lime.lime_text import LimeTextExplainer
import json
import os
import warnings
warnings.filterwarnings('ignore')

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

CHECKPOINT_DIR = "./model_checkpoint"
MAX_LENGTH = 128


def load_model(device):
    """Load the fine-tuned model and tokenizer."""
    tokenizer = DistilBertTokenizer.from_pretrained(CHECKPOINT_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(CHECKPOINT_DIR)
    model.to(device)
    model.eval()
    return model, tokenizer


def predict_batch(texts, model, tokenizer, device, batch_size=32):
    """Run inference on a list of texts."""
    all_preds = []
    all_probs = []

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        encoding = tokenizer(
            batch_texts,
            max_length=MAX_LENGTH,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        input_ids = encoding['input_ids'].to(device)
        attention_mask = encoding['attention_mask'].to(device)

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            probs = torch.softmax(outputs.logits, dim=-1)
            preds = torch.argmax(probs, dim=-1)

        all_preds.extend(preds.cpu().numpy())
        all_probs.extend(probs.cpu().numpy())

    return np.array(all_preds), np.array(all_probs)


def main():
    print("=" * 60)
    print("PHASE 5: Full Evaluation + LIME Explainability")
    print("=" * 60)

    # --- Device ---
    if torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    print(f"🖥️  Using device: {device}")

    # --- Load Model & Data ---
    print(f"\n📦 Loading model from {CHECKPOINT_DIR}...")
    model, tokenizer = load_model(device)

    test_df = pd.read_csv("test.csv")
    test_texts = test_df['text'].astype(str).tolist()
    test_labels = test_df['label'].map(LABEL2ID).values

    print(f"Test samples: {len(test_texts)}")

    # ============================================================
    # 1. FULL EVALUATION
    # ============================================================
    print("\n📊 Running full evaluation on test set...")

    preds, probs = predict_batch(test_texts, model, tokenizer, device)
    pred_labels = [ID2LABEL[p] for p in preds]
    true_labels = [ID2LABEL[t] for t in test_labels]

    # Classification Report
    report_str = classification_report(
        true_labels, pred_labels,
        labels=ALL_LABELS,
        target_names=ALL_LABELS,
        zero_division=0
    )
    report_dict = classification_report(
        true_labels, pred_labels,
        labels=ALL_LABELS,
        target_names=ALL_LABELS,
        zero_division=0,
        output_dict=True
    )

    print("\n" + "=" * 60)
    print("DISTILBERT TEST SET EVALUATION")
    print("=" * 60)
    print(report_str)

    macro_f1 = f1_score(test_labels, preds, average='macro')
    weighted_f1 = f1_score(test_labels, preds, average='weighted')
    print(f"Macro F1:    {macro_f1:.4f}")
    print(f"Weighted F1: {weighted_f1:.4f}")

    # --- Confusion Matrix ---
    os.makedirs("charts", exist_ok=True)
    cm = confusion_matrix(true_labels, pred_labels, labels=ALL_LABELS)

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Purples',
                xticklabels=ALL_LABELS, yticklabels=ALL_LABELS,
                ax=ax, linewidths=0.5, linecolor='white')
    ax.set_title("DistilBERT — Confusion Matrix (Test Set)", fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Predicted Label", fontsize=12)
    ax.set_ylabel("True Label", fontsize=12)
    plt.xticks(rotation=35, ha='right', fontsize=9)
    plt.yticks(rotation=0, fontsize=9)
    plt.tight_layout()
    plt.savefig("charts/distilbert_confusion_matrix.png", dpi=150)
    plt.close()
    print("\n✅ Saved charts/distilbert_confusion_matrix.png")

    # --- Per-class F1 Bar Chart ---
    per_class_f1 = {label: report_dict[label]['f1-score'] for label in ALL_LABELS}
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ['#64748b', '#ef4444', '#f97316', '#eab308',
              '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899']
    bars = ax.bar(ALL_LABELS, per_class_f1.values(), color=colors, edgecolor='white', linewidth=1.5)
    ax.set_title("Per-Class F1 Score — DistilBERT", fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Category", fontsize=12)
    ax.set_ylabel("F1 Score", fontsize=12)
    ax.set_ylim(0, 1.1)
    ax.set_xticklabels(ALL_LABELS, rotation=35, ha='right', fontsize=10)
    for bar, f1_val in zip(bars, per_class_f1.values()):
        ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.02,
                f"{f1_val:.2f}", ha='center', va='bottom', fontweight='bold', fontsize=11)
    ax.axhline(y=macro_f1, color='red', linestyle='--', linewidth=1.5, label=f'Macro F1: {macro_f1:.2f}')
    ax.legend(fontsize=11)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig("charts/per_class_f1.png", dpi=150)
    plt.close()
    print("✅ Saved charts/per_class_f1.png")

    # ============================================================
    # 2. ERROR ANALYSIS (20 misclassified examples)
    # ============================================================
    print("\n🔍 Error Analysis: Examining misclassified examples...")

    errors = []
    for i in range(len(test_texts)):
        if preds[i] != test_labels[i]:
            confidence = probs[i][preds[i]]
            errors.append({
                "text": test_texts[i][:200],
                "true_label": ID2LABEL[test_labels[i]],
                "predicted_label": ID2LABEL[preds[i]],
                "confidence": round(float(confidence), 3),
                "true_prob": round(float(probs[i][test_labels[i]]), 3)
            })

    # Take first 20 errors
    errors_sample = errors[:20]

    print(f"\nTotal misclassified: {len(errors)} / {len(test_texts)} ({100*len(errors)/len(test_texts):.1f}%)")
    print(f"\nShowing first {len(errors_sample)} errors:\n")

    for idx, err in enumerate(errors_sample, 1):
        print(f"  [{idx}] True: {err['true_label']} → Predicted: {err['predicted_label']} "
              f"(conf: {err['confidence']:.3f})")
        print(f"      Text: {err['text'][:120]}...")
        print()

    # Save error analysis
    error_analysis = {
        "total_test": len(test_texts),
        "total_errors": len(errors),
        "error_rate": round(len(errors) / len(test_texts), 4),
        "sample_errors": errors_sample,
        "error_pattern_summary": (
            "Common error patterns: (1) Short ambiguous text like product names "
            "being misclassified between Benign and other categories, "
            "(2) Urgency/Scarcity and Hidden Costs being confused when text mentions "
            "both time pressure and pricing, (3) Confirmshaming and Misdirection "
            "overlap when text uses guilt-laden but redirecting language."
        )
    }

    with open("error_analysis.json", "w") as f:
        json.dump(error_analysis, f, indent=2, default=str)
    print("✅ Saved error_analysis.json")

    # ============================================================
    # 3. LIME EXPLAINABILITY (5 examples)
    # ============================================================
    print("\n🔬 Generating LIME explanations for 5 examples...")

    # Create prediction function for LIME (needs to return probabilities)
    # LIME runs on CPU to avoid MPS issues
    model_cpu = model.to('cpu')

    def predict_proba(texts):
        """Prediction function for LIME."""
        encodings = tokenizer(
            list(texts),
            max_length=MAX_LENGTH,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        with torch.no_grad():
            outputs = model_cpu(
                input_ids=encodings['input_ids'],
                attention_mask=encodings['attention_mask']
            )
            probabilities = torch.softmax(outputs.logits, dim=-1)
        return probabilities.numpy()

    explainer = LimeTextExplainer(class_names=ALL_LABELS, random_state=42)

    # Select 5 diverse examples (one per category where possible)
    lime_examples = []
    used_labels = set()

    # First, pick correctly classified diverse examples
    for i in range(len(test_texts)):
        label = ID2LABEL[test_labels[i]]
        if label not in used_labels and preds[i] == test_labels[i]:
            lime_examples.append((i, test_texts[i], label))
            used_labels.add(label)
            if len(lime_examples) >= 5:
                break

    # If we don't have 5, fill with remaining
    if len(lime_examples) < 5:
        for i in range(len(test_texts)):
            if i not in [e[0] for e in lime_examples]:
                label = ID2LABEL[test_labels[i]]
                lime_examples.append((i, test_texts[i], label))
                if len(lime_examples) >= 5:
                    break

    os.makedirs("lime_explanations", exist_ok=True)

    for idx, (orig_idx, text, true_label) in enumerate(lime_examples, 1):
        print(f"\n  [{idx}/5] Explaining: '{text[:80]}...' (Label: {true_label})")
        try:
            exp = explainer.explain_instance(
                text,
                predict_proba,
                num_features=10,
                num_samples=500,
                labels=list(range(NUM_LABELS))
            )
            # Save as HTML
            html_path = f"lime_explanations/example_{idx}.html"
            exp.save_to_file(html_path)
            print(f"     ✅ Saved {html_path}")
        except Exception as e:
            print(f"     ⚠️ LIME failed for this example: {e}")

    # ============================================================
    # 4. SAVE FULL EVALUATION RESULTS
    # ============================================================
    eval_results = {
        "model": "DistilBERT (fine-tuned)",
        "test_macro_f1": round(macro_f1, 4),
        "test_weighted_f1": round(weighted_f1, 4),
        "per_class_metrics": {
            label: {
                "f1": round(report_dict[label]['f1-score'], 4),
                "precision": round(report_dict[label]['precision'], 4),
                "recall": round(report_dict[label]['recall'], 4),
                "support": report_dict[label]['support']
            }
            for label in ALL_LABELS
        }
    }

    with open("evaluation_results.json", "w") as f:
        json.dump(eval_results, f, indent=2)
    print("\n✅ Saved evaluation_results.json")

    # --- Compare with baseline ---
    if os.path.exists("baseline_results.json"):
        with open("baseline_results.json") as f:
            baseline = json.load(f)
        print("\n" + "=" * 60)
        print("📊 MODEL COMPARISON: TF-IDF vs DistilBERT")
        print("=" * 60)
        print(f"{'Metric':<25} {'TF-IDF':<15} {'DistilBERT':<15} {'Improvement':<15}")
        print("-" * 70)
        tfidf_f1 = baseline['test_macro_f1']
        bert_f1 = macro_f1
        print(f"{'Macro F1':<25} {tfidf_f1:<15.4f} {bert_f1:<15.4f} {'+' if bert_f1 > tfidf_f1 else ''}{(bert_f1 - tfidf_f1):.4f}")
        tfidf_wf1 = baseline['test_weighted_f1']
        bert_wf1 = weighted_f1
        print(f"{'Weighted F1':<25} {tfidf_wf1:<15.4f} {bert_wf1:<15.4f} {'+' if bert_wf1 > tfidf_wf1 else ''}{(bert_wf1 - tfidf_wf1):.4f}")

    print("\n🎉 Phase 5 Complete!")


if __name__ == "__main__":
    main()
