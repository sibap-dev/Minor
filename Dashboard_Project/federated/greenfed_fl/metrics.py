"""Classification metrics with JSON-safe output."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


def _safe_float(value: float) -> float:
    return float(value) if np.isfinite(value) else 0.0


def evaluate_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    classes: list[str],
) -> dict:
    """Compute standard IDS metrics.

    Samples with unknown labels (encoded as -1) are excluded and counted.
    """

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    unknown = int((y_true < 0).sum())
    mask = y_true >= 0
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    if len(y_true) == 0:
        raise ValueError("No labelled samples available for evaluation")

    labels = list(range(len(classes)))
    report = classification_report(
        y_true,
        y_pred,
        labels=labels,
        target_names=classes,
        zero_division=0,
        output_dict=True,
    )

    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    per_class = {}
    for name in classes:
        entry = report.get(name, {})
        per_class[name] = {
            "precision": _safe_float(entry.get("precision", 0.0)),
            "recall": _safe_float(entry.get("recall", 0.0)),
            "f1_score": _safe_float(entry.get("f1-score", 0.0)),
            "support": int(entry.get("support", 0)),
        }

    return {
        "samples_evaluated": int(len(y_true)),
        "unknown_label_samples_excluded": unknown,
        "accuracy": _safe_float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": _safe_float(balanced_accuracy_score(y_true, y_pred)),
        "precision_macro": _safe_float(
            precision_score(y_true, y_pred, average="macro", zero_division=0)
        ),
        "recall_macro": _safe_float(
            recall_score(y_true, y_pred, average="macro", zero_division=0)
        ),
        "macro_f1": _safe_float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "weighted_f1": _safe_float(
            f1_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "per_class": per_class,
        "confusion_matrix": matrix.astype(int).tolist(),
        "confusion_matrix_order": classes,
    }
