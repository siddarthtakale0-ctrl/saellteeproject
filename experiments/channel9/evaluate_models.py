
"""
Channel 9: Three-Model Random Forest Evaluation

Models:
1. Original baseline: 7 features
2. Expanded temporal: 10 features
3. Temporal + drift: 13 features

Thresholds are selected using validation data only.
Final metrics are calculated on the separate chronological test split.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    precision_score,
    recall_score,
    f1_score,
)

# --------------------------------------------------
# 1. PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_FILE = (
    PROJECT_ROOT / "data" / "colab_channel9"
    / "mission2_channel9_13feature_dataset.parquet"
)

MODEL_DIR = (
    PROJECT_ROOT / "data" / "colab_channel9" / "models"
)

OUTPUT_DIR = PROJECT_ROOT / "results" / "channel9"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# 2. EXPERIMENT SETTINGS
# --------------------------------------------------

TRAIN_RATIO = 0.70
VALIDATION_RATIO = 0.15

MAXIMUM_FALSE_POSITIVE_RATE = 0.01
BATCH_SIZE = 100_000


# --------------------------------------------------
# 3. FEATURE DEFINITIONS
# --------------------------------------------------

BASELINE_FEATURES = [
    "current_value",
    "difference",
    "absolute_difference",
    "rolling_mean_30",
    "rolling_std_30",
    "rolling_mean_120",
    "rolling_std_120",
]

TEMPORAL_FEATURES = BASELINE_FEATURES + [
    "deviation_30",
    "deviation_120",
    "variability_ratio",
]

DRIFT_FEATURES = TEMPORAL_FEATURES + [
    "long_term_slope",
    "short_long_mean_gap",
    "cumulative_deviation",
]


# --------------------------------------------------
# 4. LOAD DATA AND MODELS
# --------------------------------------------------

def load_experiment_data():

    print("\nLoading Channel 9 dataset...")

    if not DATA_FILE.exists():
        raise FileNotFoundError(DATA_FILE)

    data = pd.read_parquet(DATA_FILE)
    data = data.sort_index()

    if "anomaly_label" not in data.columns:
        raise ValueError("Missing anomaly_label column.")

    labels = data["anomaly_label"].to_numpy(dtype=np.uint8)

    print("Dataset shape:", data.shape)
    print("Total observations:", len(data))
    print("Anomaly observations:", int(labels.sum()))

    return data


def load_models():

    print("\nLoading all three trained models...")

    model_files = {
        "baseline_7_features": "rf_original_matched_fast.joblib",
        "temporal_10_features": "rf_expanded_temporal_fast.joblib",
        "temporal_drift_13_features": "rf_drift_13feature.joblib",
    }

    models = {}

    for name, filename in model_files.items():

        path = MODEL_DIR / filename

        if not path.exists():
            raise FileNotFoundError(path)

        models[name] = load(path)
        print(name, "loaded successfully.")

    return models


# --------------------------------------------------
# 5. CHRONOLOGICAL SPLIT
# --------------------------------------------------

def chronological_split(data):

    total_rows = len(data)

    train_end = int(total_rows * TRAIN_RATIO)

    validation_end = int(
        total_rows * (TRAIN_RATIO + VALIDATION_RATIO)
    )

    validation_data = data.iloc[train_end:validation_end]
    test_data = data.iloc[validation_end:]

    print("\nChronological split:")
    print("Training partition:", train_end)
    print("Validation partition:", len(validation_data))
    print("Test partition:", len(test_data))

    return validation_data, test_data


# --------------------------------------------------
# 6. BATCH PREDICTION
# --------------------------------------------------

def get_anomaly_scores(model, data, feature_names):

    scores = []

    for start in range(0, len(data), BATCH_SIZE):

        end = min(start + BATCH_SIZE, len(data))

        batch = data.iloc[start:end][feature_names]

        probabilities = model.predict_proba(batch)[:, 1]

        scores.append(probabilities)

    return np.concatenate(scores)


# --------------------------------------------------
# 7. VALIDATION THRESHOLD SELECTION
# --------------------------------------------------

def select_threshold(labels, scores):

    precision, recall, thresholds = precision_recall_curve(
        labels, scores
    )

    if len(thresholds) == 0:
        raise ValueError("Unable to calculate thresholds.")

    precision = precision[:-1]
    recall = recall[:-1]

    true_positives = recall * labels.sum()

    predicted_positives = np.divide(
        true_positives,
        precision,
        out=np.zeros_like(true_positives),
        where=precision > 0
    )

    false_positives = predicted_positives - true_positives

    negatives = len(labels) - labels.sum()

    false_positive_rate = false_positives / negatives

    f1_values = (
        2 * precision * recall
        / (precision + recall + 1e-12)
    )

    eligible = np.where(
        false_positive_rate <= MAXIMUM_FALSE_POSITIVE_RATE
    )[0]

    if len(eligible) == 0:
        raise ValueError("No threshold satisfies the FPR limit.")

    best_index = eligible[np.argmax(f1_values[eligible])]

    return float(thresholds[best_index])


# --------------------------------------------------
# 8. MODEL EVALUATION
# --------------------------------------------------

def evaluate_model(name, model, features, validation_data, test_data):

    print("\nEvaluating:", name)

    # Threshold is selected using validation data only.
    validation_labels = validation_data["anomaly_label"].to_numpy()

    validation_scores = get_anomaly_scores(
        model, validation_data, features
    )

    threshold = select_threshold(
        validation_labels, validation_scores
    )

    print("Validation threshold:", threshold)

    # Final evaluation on untouched test partition.
    test_labels = test_data["anomaly_label"].to_numpy()

    test_scores = get_anomaly_scores(
        model, test_data, features
    )

    predictions = (test_scores >= threshold).astype(np.uint8)

    tn, fp, fn, tp = confusion_matrix(
        test_labels,
        predictions,
        labels=[0, 1]
    ).ravel()

    return {
        "model": name,
        "number_of_features": len(features),
        "feature_names": features,
        "threshold": threshold,
        "precision": float(precision_score(
            test_labels, predictions, zero_division=0
        )),
        "recall": float(recall_score(
            test_labels, predictions, zero_division=0
        )),
        "f1_score": float(f1_score(
            test_labels, predictions, zero_division=0
        )),
        "pr_auc": float(average_precision_score(
            test_labels, test_scores
        )),
        "false_positive_rate": float(fp / (fp + tn)),
        "confusion_matrix": [
            [int(tn), int(fp)],
            [int(fn), int(tp)]
        ],
        "test_observations": len(test_labels),
    }


# --------------------------------------------------
# 9. MAIN EXPERIMENT
# --------------------------------------------------

def main():

    print("=" * 65)
    print("SATELLITE ANOMALY DETECTION: THREE-MODEL COMPARISON")
    print("=" * 65)

    data = load_experiment_data()
    models = load_models()

    feature_sets = {
        "baseline_7_features": BASELINE_FEATURES,
        "temporal_10_features": TEMPORAL_FEATURES,
        "temporal_drift_13_features": DRIFT_FEATURES,
    }

    # Verify expected model input dimensions.
    for name, model in models.items():

        expected_features = len(feature_sets[name])

        if model.n_features_in_ != expected_features:
            raise ValueError(
                f"{name}: expected {expected_features} features, "
                f"but model expects {model.n_features_in_}."
            )

    validation_data, test_data = chronological_split(data)

    all_results = {}

    for name, model in models.items():

        all_results[name] = evaluate_model(
            name,
            model,
            feature_sets[name],
            validation_data,
            test_data
        )

    comparison = {
        "experiment": {
            "dataset": "ESA-ADB Mission 2, channel_9",
            "split": "70% training / 15% validation / 15% testing",
            "threshold_selection": "Validation data only",
            "maximum_false_positive_rate": MAXIMUM_FALSE_POSITIVE_RATE,
            "batch_size": BATCH_SIZE,
            "note": (
                "This script evaluates previously trained models. "
                "It does not retrain them."
            ),
        },
        "results": all_results,
    }

    output_file = OUTPUT_DIR / "three_model_comparison.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(comparison, file, indent=4)

    print("\n" + "=" * 65)
    print("FINAL THREE-MODEL TEST COMPARISON")
    print("=" * 65)

    for name, result in all_results.items():

        print("\n", name)
        print("Features:", result["number_of_features"])
        print("Precision:", round(result["precision"], 4))
        print("Recall:", round(result["recall"], 4))
        print("F1-score:", round(result["f1_score"], 4))
        print("PR-AUC:", round(result["pr_auc"], 4))
        print(
            "False positive rate:",
            round(result["false_positive_rate"], 6)
        )

    print("\nResults saved to:", output_file)


if __name__ == "__main__":
    main()
