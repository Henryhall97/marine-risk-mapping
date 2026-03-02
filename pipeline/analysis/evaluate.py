"""Shared evaluation utilities for ML models.

Provides metrics computation, plotting, and MLflow logging helpers
used by both the strike-risk and whale-SDM training scripts.
"""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

log = logging.getLogger(__name__)


def compute_binary_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Compute a comprehensive set of binary classification metrics.

    Returns a flat dict suitable for mlflow.log_metrics().
    """
    y_pred = (y_prob >= threshold).astype(int)

    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)

    return {
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "avg_precision": float(average_precision_score(y_true, y_prob)),
        "log_loss": float(log_loss(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "threshold": threshold,
    }


def plot_roc_pr_curves(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    title_prefix: str = "",
    save_path: Path | None = None,
) -> plt.Figure:
    """Plot ROC and Precision-Recall curves side by side."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # ROC curve
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    auc_roc = roc_auc_score(y_true, y_prob)
    ax1.plot(fpr, tpr, color="#0D3B66", linewidth=2, label=f"AUC = {auc_roc:.4f}")
    ax1.plot([0, 1], [0, 1], "k--", alpha=0.3)
    ax1.set_xlabel("False Positive Rate")
    ax1.set_ylabel("True Positive Rate")
    ax1.set_title(f"{title_prefix}ROC Curve")
    ax1.legend(loc="lower right")
    ax1.grid(alpha=0.3)

    # Precision-Recall curve
    prec, rec, _ = precision_recall_curve(y_true, y_prob)
    ap = average_precision_score(y_true, y_prob)
    baseline = y_true.mean()
    ax2.plot(rec, prec, color="#1A936F", linewidth=2, label=f"AP = {ap:.4f}")
    ax2.axhline(
        y=baseline,
        color="red",
        linestyle="--",
        alpha=0.5,
        label=f"Baseline = {baseline:.4f}",
    )
    ax2.set_xlabel("Recall")
    ax2.set_ylabel("Precision")
    ax2.set_title(f"{title_prefix}Precision-Recall Curve")
    ax2.legend(loc="upper right")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        log.info("Saved curve plot: %s", save_path)
    return fig


def plot_calibration(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
    title_prefix: str = "",
    save_path: Path | None = None,
) -> plt.Figure:
    """Plot a calibration (reliability) diagram."""
    fig, ax = plt.subplots(figsize=(7, 5))
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins)
    ax.plot(prob_pred, prob_true, "o-", color="#0D3B66", linewidth=2, label="Model")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.3, label="Perfectly calibrated")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title(f"{title_prefix}Calibration Curve")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


def plot_feature_importance(
    importances: pd.Series,
    top_n: int = 25,
    title: str = "Feature Importance",
    save_path: Path | None = None,
) -> plt.Figure:
    """Horizontal bar chart of top-N feature importances."""
    top = importances.nlargest(top_n).sort_values()
    fig, ax = plt.subplots(figsize=(8, max(6, top_n * 0.3)))
    colors = ["#1A936F" if v > 0 else "#D64045" for v in top.values]
    ax.barh(top.index, top.values, color=colors, edgecolor="white")
    ax.set_xlabel("Importance")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


def spatial_cv_split(
    df: pd.DataFrame,
    fold_col: str = "cv_fold",
    n_folds: int = 5,
):
    """Yield (train_idx, val_idx) tuples for spatial block CV.

    Each fold holds out all rows in one spatial block group.
    """
    for fold in range(n_folds):
        val_mask = df[fold_col] == fold
        train_idx = df.index[~val_mask].tolist()
        val_idx = df.index[val_mask].tolist()
        yield train_idx, val_idx
