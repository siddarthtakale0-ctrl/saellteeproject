
"""
Validation-only experiment for adaptive satellite anomaly detection.

Compares:
1. Original 7-feature model
2. Strong 13-feature model
3. Hybrid routing: use the 13-feature model near the
   7-feature model's decision threshold.

No model is retrained or modified.
The test set is not used to select the routing margin.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load
from sklearn.metrics import confusion_matrix, precision_recall_curve


ROOT = Path(__file__).resolve().parents[2]

DATA_FILE = (
    ROOT / "data" / "colab_channel9"
    / "mission2_channel9_13feature_dataset.parquet"
)

MODEL_DIR = ROOT / "data" / "colab_channel9" / "models"

OUTPUT_DIR = ROOT / "results" / "channel9"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BATCH_SIZE = 100_000
MAX_FPR = 0.01

FEATURES_7 = [
    "current_value",
    "difference",
    "absolute_difference",
    "rolling_mean_30",
    "rolling_std_30",
    "rolling_mean_120",
    "rolling_std_120",
]

FEATURES_13 = FEATURES_7 + [
    "deviation_30",
    "deviation_120",
    "variability_ratio",
    "long_term_slope",
    "short_long_mean_gap",
    "cumulative_deviation",
]

MARGINS = [0.005, 0.01, 0.02, 0.05, 0.10]


def predict_in_batches(model, data, features):

    outputs = []

    for start in range(0, len(data), BATCH_SIZE):

        batch = data.iloc[start:start + BATCH_SIZE][features]

        probabilities = model.predict_proba(batch)[:, 1]

        outputs.append(probabilities)

    return np.concatenate(outputs)


def select_threshold(labels, scores):

    precision, recall, thresholds = precision_recall_curve(
        labels, scores
    )

    precision = precision[:-1]
    recall = recall[:-1]

    true_positives = recall * labels.sum()

    predicted_positive = np.divide(
        true_positives,
        precision,
        out=np.zeros_like(true_positives),
        where=precision > 0
    )

    false_positives = predicted_positive - true_positives
    negatives = len(labels) - labels.sum()
    fpr = false_positives / negatives

    f1 = (
        2 * precision * recall
        / (precision + recall + 1e-12)
    )

    eligible = np.where(fpr <= MAX_FPR)[0]

    if len(eligible) == 0:
        raise ValueError("No threshold satisfies the FPR limit.")

    best = eligible[np.argmax(f1[eligible])]

    return float(thresholds[best])


def calculate_metrics(labels, predictions):

    tn, fp, fn, tp = confusion_matrix(
        labels, predictions, labels=[0, 1]
    ).ravel()

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    fpr = fp / (fp + tn) if fp + tn else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
    }


def main():

    print("Loading dataset...")

    data = pd.read_parquet(DATA_FILE).sort_index()

    train_end = int(len(data) * 0.70)
    validation_end = int(len(data) * 0.85)

    validation = data.iloc[train_end:validation_end]

    labels = validation["anomaly_label"].to_numpy(
        dtype=np.uint8
    )

    print("Validation observations:", len(validation))
    print("Validation anomalies:", int(labels.sum()))

    print("\nLoading saved models...")

    model_7 = load(
        MODEL_DIR / "rf_original_matched_fast.joblib"
    )

    model_13 = load(
        MODEL_DIR / "rf_drift_13feature.joblib"
    )

    print("Calculating 7-feature probabilities...")
    scores_7 = predict_in_batches(
        model_7, validation, FEATURES_7
    )

    print("Calculating 13-feature probabilities...")
    scores_13 = predict_in_batches(
        model_13, validation, FEATURES_13
    )

    threshold_7 = select_threshold(labels, scores_7)
    threshold_13 = select_threshold(labels, scores_13)

    print("\nValidation thresholds:")
    print("7-feature threshold:", threshold_7)
    print("13-feature threshold:", threshold_13)

    predictions_7 = (scores_7 >= threshold_7).astype(np.uint8)
    predictions_13 = (scores_13 >= threshold_13).astype(np.uint8)

    rows = []

    baseline = calculate_metrics(labels, predictions_7)
    baseline.update({
        "model": "7-feature baseline",
        "margin": None,
        "escalation_percentage": 0.0,
    })
    rows.append(baseline)

    strong = calculate_metrics(labels, predictions_13)
    strong.update({
        "model": "13-feature always",
        "margin": None,
        "escalation_percentage": 100.0,
    })
    rows.append(strong)

    print("\nBaseline 7-feature results:")
    print(baseline)

    print("\nAlways-use-13-feature results:")
    print(strong)

    print("\nTesting adaptive routing margins...")

    for margin in MARGINS:

        escalate = np.abs(scores_7 - threshold_7) <= margin

        hybrid_predictions = predictions_7.copy()
        hybrid_predictions[escalate] = predictions_13[escalate]

        metrics = calculate_metrics(labels, hybrid_predictions)

        escalation_percentage = (
            int(escalate.sum()) / len(escalate) * 100
        )

        metrics.update({
            "model": "adaptive hybrid",
            "margin": margin,
            "escalation_percentage": escalation_percentage,
            "escalated_observations": int(escalate.sum()),
        })

        rows.append(metrics)

        print(
            f"\nMargin ±{margin:.3f} | "
            f"Escalated: {escalation_percentage:.3f}%"
        )
        print(
            f"Precision: {metrics['precision']:.4f} | "
            f"Recall: {metrics['recall']:.4f} | "
            f"F1: {metrics['f1']:.4f} | "
            f"FPR: {metrics['fpr']:.4f}"
        )
        print(
            f"TP: {metrics['true_positives']} | "
            f"FP: {metrics['false_positives']} | "
            f"FN: {metrics['false_negatives']}"
        )

    results = pd.DataFrame(rows)

    output_file = OUTPUT_DIR / "adaptive_routing_validation.csv"
    results.to_csv(output_file, index=False)

    print("\nComplete comparison:")
    print(
        results[
            [
                "model",
                "margin",
                "precision",
                "recall",
                "f1",
                "fpr",
                "escalation_percentage",
            ]
        ].to_string(index=False)
    )

    print("\nResults saved to:", output_file)
    print("\nAdaptive routing validation experiment completed.")


if __name__ == "__main__":
    main()
