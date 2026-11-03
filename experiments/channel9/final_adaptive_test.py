
"""
Final held-out test of adaptive satellite anomaly detection.

Locked policy:
- 7-feature model screens every observation.
- Escalate when abs(score_7 - threshold_7) <= 0.10.
- Use the 13-feature model only for escalated observations.
- Use each model's threshold selected on validation data.

No model retraining.
No threshold or margin tuning on test data.
"""

from pathlib import Path
from time import perf_counter
import json

import numpy as np
import pandas as pd
from joblib import load
from sklearn.metrics import confusion_matrix


ROOT = Path(__file__).resolve().parents[2]

DATA_FILE = (
    ROOT / "data" / "colab_channel9"
    / "mission2_channel9_13feature_dataset.parquet"
)

MODEL_DIR = ROOT / "data" / "colab_channel9" / "models"

OUTPUT_DIR = ROOT / "results" / "channel9"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BATCH_SIZE = 100_000

# Locked using validation data only.
THRESHOLD_7 = 0.9562204553037759
THRESHOLD_13 = 0.9478779691947137
ESCALATION_MARGIN = 0.10

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


def predict_all(model, data, features):

    outputs = []

    start_time = perf_counter()

    for start in range(0, len(data), BATCH_SIZE):

        batch = data.iloc[start:start + BATCH_SIZE][features]

        scores = model.predict_proba(batch)[:, 1]
        outputs.append(scores)

    elapsed = perf_counter() - start_time

    return np.concatenate(outputs), elapsed


def predict_adaptive(model_7, model_13, data):

    all_scores_7 = []
    final_predictions = []

    escalated_total = 0

    start_time = perf_counter()

    for start in range(0, len(data), BATCH_SIZE):

        batch = data.iloc[start:start + BATCH_SIZE]

        scores_7 = model_7.predict_proba(
            batch[FEATURES_7]
        )[:, 1]

        escalate = (
            np.abs(scores_7 - THRESHOLD_7)
            <= ESCALATION_MARGIN
        )

        predictions = (
            scores_7 >= THRESHOLD_7
        ).astype(np.uint8)

        if escalate.any():

            strong_scores = model_13.predict_proba(
                batch.loc[escalate, FEATURES_13]
            )[:, 1]

            predictions[escalate] = (
                strong_scores >= THRESHOLD_13
            ).astype(np.uint8)

        escalated_total += int(escalate.sum())

        all_scores_7.append(scores_7)
        final_predictions.append(predictions)

    elapsed = perf_counter() - start_time

    return (
        np.concatenate(all_scores_7),
        np.concatenate(final_predictions),
        escalated_total,
        elapsed,
    )


def metrics(labels, predictions):

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
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "fpr": float(fpr),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


def main():

    print("Loading dataset...")

    data = pd.read_parquet(DATA_FILE).sort_index()

    train_end = int(len(data) * 0.70)
    validation_end = int(len(data) * 0.85)

    test = data.iloc[validation_end:]

    labels = test["anomaly_label"].to_numpy(
        dtype=np.uint8
    )

    print("Test observations:", len(test))
    print("Test anomalies:", int(labels.sum()))

    print("\nLocked validation policy:")
    print("7-feature threshold:", THRESHOLD_7)
    print("13-feature threshold:", THRESHOLD_13)
    print("Escalation margin:", ESCALATION_MARGIN)

    print("\nLoading saved models...")

    model_7 = load(
        MODEL_DIR / "rf_original_matched_fast.joblib"
    )

    model_13 = load(
        MODEL_DIR / "rf_drift_13feature.joblib"
    )

    print("\nRunning 7-feature baseline on all test observations...")

    scores_7, time_7 = predict_all(
        model_7, test, FEATURES_7
    )

    predictions_7 = (
        scores_7 >= THRESHOLD_7
    ).astype(np.uint8)

    print("\nRunning 13-feature model on all test observations...")

    scores_13, time_13 = predict_all(
        model_13, test, FEATURES_13
    )

    predictions_13 = (
        scores_13 >= THRESHOLD_13
    ).astype(np.uint8)

    print("\nRunning actual adaptive routing...")

    _, hybrid_predictions, escalated, hybrid_time = (
        predict_adaptive(model_7, model_13, test)
    )

    escalation_percentage = escalated / len(test) * 100

    results = {
        "experiment": "final_adaptive_test",
        "test_observations": len(test),
        "test_anomalies": int(labels.sum()),
        "threshold_7_selected_on_validation": THRESHOLD_7,
        "threshold_13_selected_on_validation": THRESHOLD_13,
        "escalation_margin_selected_on_validation": ESCALATION_MARGIN,
        "baseline_7_feature": metrics(labels, predictions_7),
        "always_13_feature": metrics(labels, predictions_13),
        "adaptive_hybrid": metrics(labels, hybrid_predictions),
        "escalated_observations": escalated,
        "escalation_percentage": float(escalation_percentage),
        "runtime_seconds": {
            "baseline_7_feature": float(time_7),
            "always_13_feature": float(time_13),
            "adaptive_hybrid": float(hybrid_time),
        },
    }

    print("\n========== FINAL TEST RESULTS ==========")

    for name in [
        "baseline_7_feature",
        "always_13_feature",
        "adaptive_hybrid",
    ]:

        print("\n" + name)

        for key, value in results[name].items():
            print(f"{key}: {value}")

    print("\nEscalated observations:", escalated)
    print("Escalation percentage:", round(escalation_percentage, 4), "%")

    print("\nMeasured inference times:")
    print("7-feature baseline:", round(time_7, 3), "seconds")
    print("13-feature always:", round(time_13, 3), "seconds")
    print("Adaptive hybrid:", round(hybrid_time, 3), "seconds")

    output_file = OUTPUT_DIR / "final_adaptive_test_results.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)

    print("\nResults saved to:", output_file)
    print("\nFinal adaptive test completed.")


if __name__ == "__main__":
    main()
