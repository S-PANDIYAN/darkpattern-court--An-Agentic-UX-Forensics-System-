"""
Phase 6: ONNX Export + INT8 Quantisation
==========================================
- Exports fine-tuned DistilBERT → ONNX format
- Applies INT8 dynamic quantisation
- Benchmarks: model size, inference speed, F1 score
"""

import pandas as pd
import numpy as np
import torch
from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType
from sklearn.metrics import f1_score
import time
import os
import json

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
ONNX_DIR = "./model_onnx"
MAX_LENGTH = 128


def main():
    print("=" * 60)
    print("PHASE 6: ONNX Export + INT8 Quantisation")
    print("=" * 60)

    os.makedirs(ONNX_DIR, exist_ok=True)

    # --- Load PyTorch Model ---
    print("\n📦 Loading fine-tuned model...")
    tokenizer = DistilBertTokenizer.from_pretrained(CHECKPOINT_DIR)
    model = DistilBertForSequenceClassification.from_pretrained(CHECKPOINT_DIR)
    model.eval()

    # ============================================================
    # 1. EXPORT TO ONNX
    # ============================================================
    print("\n🔄 Exporting to ONNX format...")

    onnx_path = os.path.join(ONNX_DIR, "model.onnx")
    quantized_path = os.path.join(ONNX_DIR, "model_quantized.onnx")

    import subprocess
    print("Running optimum-cli to export the model (this ensures Transformers.js web compatibility)...")
    try:
        subprocess.run([
            "optimum-cli", "export", "onnx",
            "--model", CHECKPOINT_DIR,
            "--task", "text-classification",
            ONNX_DIR
        ], check=True)
        print(f"✅ ONNX model saved to: {ONNX_DIR}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Optimum-cli export failed. Make sure 'optimum' is installed. Error: {e}")
        return

    # ============================================================
    # 2. INT8 DYNAMIC QUANTISATION
    # ============================================================
    from onnxruntime.quantization import quantize_dynamic, QuantType
    
    print("\nApplying INT8 Dynamic Quantization...")
    quantize_dynamic(
        model_input=onnx_path,
        model_output=quantized_path,
        weight_type=QuantType.QInt8
    )
    print(f"✅ Quantised model saved: {quantized_path}")

    # ============================================================
    # 3. BENCHMARK: Size, Speed, F1
    # ============================================================
    print("\n📊 Running benchmarks...")

    # --- Model Sizes ---
    pytorch_size = sum(
        os.path.getsize(os.path.join(CHECKPOINT_DIR, f))
        for f in os.listdir(CHECKPOINT_DIR)
        if f.endswith('.bin') or f.endswith('.safetensors')
    ) / (1024 * 1024)

    onnx_size = os.path.getsize(onnx_path) / (1024 * 1024)
    quantized_size = os.path.getsize(quantized_path) / (1024 * 1024)

    print(f"\n  PyTorch model size:   {pytorch_size:.1f} MB")
    print(f"  ONNX model size:     {onnx_size:.1f} MB")
    print(f"  Quantised model size: {quantized_size:.1f} MB")
    print(f"  Compression ratio:   {onnx_size / quantized_size:.2f}x")

    # --- Load Test Data ---
    test_df = pd.read_csv("test.csv")
    test_texts = test_df['text'].astype(str).tolist()
    test_labels = test_df['label'].map(LABEL2ID).values

    # --- PyTorch Inference Speed ---
    print("\n⏱️  Benchmarking inference speed...")

    # PyTorch speed (CPU for fair comparison)
    model.to('cpu')
    model.eval()

    start = time.time()
    for text in test_texts[:50]:
        enc = tokenizer(text, max_length=MAX_LENGTH, padding='max_length',
                        truncation=True, return_tensors='pt')
        with torch.no_grad():
            _ = model(input_ids=enc['input_ids'], attention_mask=enc['attention_mask'])
    pytorch_time = (time.time() - start) / 50 * 1000  # ms per sample

    # --- ONNX Inference Speed ---
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    onnx_session = ort.InferenceSession(onnx_path, sess_options)

    start = time.time()
    for text in test_texts[:50]:
        enc = tokenizer(text, max_length=MAX_LENGTH, padding='max_length',
                        truncation=True, return_tensors='np')
        _ = onnx_session.run(None, {
            'input_ids': enc['input_ids'].astype(np.int64),
            'attention_mask': enc['attention_mask'].astype(np.int64)
        })
    onnx_time = (time.time() - start) / 50 * 1000

    # --- Quantised ONNX Inference Speed ---
    quant_session = ort.InferenceSession(quantized_path, sess_options)

    start = time.time()
    for text in test_texts[:50]:
        enc = tokenizer(text, max_length=MAX_LENGTH, padding='max_length',
                        truncation=True, return_tensors='np')
        _ = quant_session.run(None, {
            'input_ids': enc['input_ids'].astype(np.int64),
            'attention_mask': enc['attention_mask'].astype(np.int64)
        })
    quant_time = (time.time() - start) / 50 * 1000

    # --- F1 Scores for all three ---
    # PyTorch F1 (already computed in Phase 5, but let's verify)
    pytorch_preds = []
    for text in test_texts:
        enc = tokenizer(text, max_length=MAX_LENGTH, padding='max_length',
                        truncation=True, return_tensors='pt')
        with torch.no_grad():
            logits = model(input_ids=enc['input_ids'],
                           attention_mask=enc['attention_mask']).logits
            pytorch_preds.append(torch.argmax(logits, dim=-1).item())
    pytorch_f1 = f1_score(test_labels, pytorch_preds, average='macro')

    # ONNX F1
    onnx_preds = []
    for text in test_texts:
        enc = tokenizer(text, max_length=MAX_LENGTH, padding='max_length',
                        truncation=True, return_tensors='np')
        logits = onnx_session.run(None, {
            'input_ids': enc['input_ids'].astype(np.int64),
            'attention_mask': enc['attention_mask'].astype(np.int64)
        })[0]
        onnx_preds.append(np.argmax(logits, axis=-1)[0])
    onnx_f1 = f1_score(test_labels, onnx_preds, average='macro')

    # Quantised F1
    quant_preds = []
    for text in test_texts:
        enc = tokenizer(text, max_length=MAX_LENGTH, padding='max_length',
                        truncation=True, return_tensors='np')
        logits = quant_session.run(None, {
            'input_ids': enc['input_ids'].astype(np.int64),
            'attention_mask': enc['attention_mask'].astype(np.int64)
        })[0]
        quant_preds.append(np.argmax(logits, axis=-1)[0])
    quant_f1 = f1_score(test_labels, quant_preds, average='macro')

    # --- Benchmark Table ---
    print("\n" + "=" * 75)
    print("BENCHMARK TABLE: Model Compression Results")
    print("=" * 75)
    print(f"{'Model':<25} {'Size (MB)':<12} {'Speed (ms)':<12} {'Macro F1':<12} {'F1 Drop':<12}")
    print("-" * 75)
    print(f"{'PyTorch (FP32)':<25} {pytorch_size:<12.1f} {pytorch_time:<12.1f} {pytorch_f1:<12.4f} {'—':<12}")
    print(f"{'ONNX (FP32)':<25} {onnx_size:<12.1f} {onnx_time:<12.1f} {onnx_f1:<12.4f} {onnx_f1 - pytorch_f1:<+12.4f}")
    print(f"{'ONNX Quantised (INT8)':<25} {quantized_size:<12.1f} {quant_time:<12.1f} {quant_f1:<12.4f} {quant_f1 - pytorch_f1:<+12.4f}")
    print("=" * 75)

    # Estimate page-level inference time (assume ~20 text chunks per page)
    page_time = quant_time * 20
    print(f"\n📄 Estimated page inference time (20 chunks): {page_time:.0f} ms")
    if page_time < 300:
        print("   ✅ Within 300ms target!")
    else:
        print("   ⚠️  Exceeds 300ms target. Consider batching chunks.")

    # --- Save Results ---
    benchmark = {
        "pytorch": {
            "size_mb": round(pytorch_size, 1),
            "speed_ms": round(pytorch_time, 1),
            "macro_f1": round(pytorch_f1, 4)
        },
        "onnx": {
            "size_mb": round(onnx_size, 1),
            "speed_ms": round(onnx_time, 1),
            "macro_f1": round(onnx_f1, 4)
        },
        "quantized": {
            "size_mb": round(quantized_size, 1),
            "speed_ms": round(quant_time, 1),
            "macro_f1": round(quant_f1, 4)
        },
        "estimated_page_time_ms": round(page_time, 0)
    }

    with open("compression_benchmark.json", "w") as f:
        json.dump(benchmark, f, indent=2)
    print("\n✅ Saved compression_benchmark.json")

    print("\n🎉 Phase 6 Complete!")
    print(f"   Quantised model ready at: {quantized_path}")


if __name__ == "__main__":
    main()
