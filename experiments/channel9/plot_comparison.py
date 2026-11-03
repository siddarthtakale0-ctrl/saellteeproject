
"""
Generate three-model comparison charts for Channel 9 anomaly detection.
Reads three_model_comparison.json and preserves previous charts.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESULTS_FILE = (
    PROJECT_ROOT / "results" / "channel9"
    / "three_model_comparison.json"
)

OUTPUT_DIR = PROJECT_ROOT / "results" / "channel9"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


MODEL_KEYS = [
    "baseline_7_features",
    "temporal_10_features",
    "temporal_drift_13_features",
]

MODEL_LABELS = [
    "Baseline\n7 features",
    "Temporal\n10 features",
    "Temporal + drift\n13 features",
]


def load_results():

    if not RESULTS_FILE.exists():
        raise FileNotFoundError(RESULTS_FILE)

    with open(RESULTS_FILE, "r", encoding="utf-8") as file:
        results = json.load(file)

    return results["results"]


def plot_metric_comparison(results):

    metrics = [
        ("precision", "Precision"),
        ("recall", "Recall"),
        ("f1_score", "F1-score"),
        ("pr_auc", "PR-AUC"),
        ("false_positive_rate", "False-positive rate"),
    ]

    fig, axes = plt.subplots(1, 5, figsize=(17, 5))

    for ax, (metric, title) in zip(axes, metrics):

        values = [
            results[key][metric]
            for key in MODEL_KEYS
        ]

        bars = ax.bar(MODEL_LABELS, values)

        ax.set_title(title)
        ax.set_ylabel("Value")
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.35)

        for bar, value in zip(bars, values):

            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{value:.4f}",
                ha="center",
                va="bottom",
                fontsize=8
            )

    fig.suptitle(
        "Satellite Anomaly Detection: Three-Model Comparison"
    )

    fig.tight_layout()

    output_file = OUTPUT_DIR / "three_model_metric_comparison.png"

    fig.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print("Metric comparison saved:", output_file)


def plot_confusion_matrices(results):

    matrices = [
        np.array(results[key]["confusion_matrix"])
        for key in MODEL_KEYS
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for ax, matrix, title in zip(
        axes, matrices, MODEL_LABELS
    ):

        image = ax.imshow(matrix)

        ax.set_title(title.replace("\n", " "))
        ax.set_xlabel("Predicted label")
        ax.set_ylabel("Actual label")

        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])

        ax.set_xticklabels(["Normal", "Anomaly"])
        ax.set_yticklabels(["Normal", "Anomaly"])

        for row in range(2):
            for column in range(2):

                ax.text(
                    column,
                    row,
                    f"{matrix[row, column]:,}",
                    ha="center",
                    va="center"
                )

    fig.colorbar(image, ax=axes, shrink=0.8)
    fig.suptitle("Three-Model Confusion Matrix Comparison")

    fig.tight_layout()

    output_file = OUTPUT_DIR / "three_model_confusion_matrices.png"

    fig.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print("Confusion matrices saved:", output_file)


def plot_improvement_summary(results):

    baseline = results["baseline_7_features"]
    temporal = results["temporal_10_features"]
    drift = results["temporal_drift_13_features"]

    metrics = ["precision", "recall", "f1_score", "pr_auc"]

    labels = ["Precision", "Recall", "F1-score", "PR-AUC"]

    temporal_changes = []
    drift_changes = []

    for metric in metrics:

        base_value = baseline[metric]

        temporal_changes.append(
            (temporal[metric] - base_value) / base_value * 100
        )

        drift_changes.append(
            (drift[metric] - base_value) / base_value * 100
        )

    x = np.arange(len(metrics))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))

    ax.bar(
        x - width / 2,
        temporal_changes,
        width,
        label="10 features vs baseline"
    )

    ax.bar(
        x + width / 2,
        drift_changes,
        width,
        label="13 features vs baseline"
    )

    ax.axhline(0, linewidth=0.8)

    ax.set_title("Relative Improvement Over Original Baseline")
    ax.set_ylabel("Change (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.35)

    fig.tight_layout()

    output_file = OUTPUT_DIR / "three_model_improvement_summary.png"

    fig.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print("Improvement summary saved:", output_file)


def main():

    print("Loading three-model evaluation results...")

    results = load_results()

    plot_metric_comparison(results)
    plot_confusion_matrices(results)
    plot_improvement_summary(results)

    print("\nAll three-model charts generated successfully.")


if __name__ == "__main__":
    main()
