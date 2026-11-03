
"""
Analyze baseline model confidence for adaptive escalation.

This is a validation-only experiment.
It does not modify or retrain any saved model.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load
from sklearn.metrics import precision_recall_curve


ROOT = Path(__file__).resolve().parents[2]

DATA_FILE = (
    ROOT / "data" / "colab_channel9"
    / "mission2_channel9_13feature_dataset.parquet"
)

MODEL_FILE = (
    ROOT / "data" / "colab_channel9" / "models"
    / "rf_original_matched_fast.joblib"
)

OUTPUT_DIR = ROOT / "results" / "channel9"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BATCH_SIZE = 100_000
MAX_FPR = 0.01

FEATURES = [
    "current_value",
    "difference",
    "absolute_difference",
    "rolling_mean_30",
    "rolling_std_30",
    "rolling_mean_120",
    "rolling_std_120",
]


def select_threshold(labels, scores):

    precision, recall, thresholds = precision_recall_curve(
        labels, scores
    )

    precision = precision[:-1]
    recall = recall[:-1]

    tp = recall * labels.sum()

    predicted_positive = np.divide(
        tp,
        precision,
        out=np.zeros_like(tp),
        where=precision > 0
    )

    fp = predicted_positive - tp
    negatives = len(labels) - labels.sum()
    fpr = fp / negatives

    f1 = (
        2 * precision * recall
        / (precision + recall + 1e-12)
    )

    eligible = np.where(fpr <= MAX_FPR)[0]

    if len(eligible) == 0:
        raise ValueError("No threshold satisfies the FPR limit.")

    best = eligible[np.argmax(f1[eligible])]

    return float(thresholds[best])


def predict_in_batches(model, data):

    outputs = []

    for start in range(0, len(data), BATCH_SIZE):

        batch = data.iloc[start:start + BATCH_SIZE][FEATURES]

        probabilities = model.predict_proba(batch)[:, 1]

        outputs.append(probabilities)

    return np.concatenate(outputs)


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

    print("\nLoading baseline model...")
    model = load(MODEL_FILE)

    print("Calculating validation probabilities...")
    scores = predict_in_batches(model, validation)

    threshold = select_threshold(labels, scores)

    print("\nSelected validation threshold:", threshold)

    print("\nProbability distribution:")
    for percentile in [0, 10, 25, 50, 75, 90, 95, 99, 100]:

        print(
            f"{percentile:>3}th percentile:",
            round(float(np.percentile(scores, percentile)), 6)
        )

    print("\nPotential escalation rates:")
    print("Margin means distance from the decision threshold.")

    margins = [0.005, 0.01, 0.02, 0.05, 0.10]

    results = []

    for margin in margins:

        uncertain = np.abs(scores - threshold) <= margin

        count = int(uncertain.sum())
        percentage = count / len(scores) * 100

        results.append({
            "margin": margin,
            "escalated_observations": count,
            "escalation_percentage": percentage,
        })

        print(
            f"Margin ±{margin:.3f}: "
            f"{count:,} observations "
            f"({percentage:.3f}%)"
        )

    output_file = OUTPUT_DIR / "confidence_analysis.csv"

    pd.DataFrame(results).to_csv(output_file, index=False)

    print("\nResults saved to:", output_file)
    print("\nConfidence analysis completed.")


if __name__ == "__main__":
    main()
