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

    # Ranking metrics (ROC AUC, average precision) are undefined when the
    # evaluation set contains a single class — which happens for rare,
    # spatially clustered species (e.g. right whale) in some spatial CV
    # folds. Return NaN for those and pass explicit labels to the loss
    # metrics so they don't raise on single-class targets.
    single_class = len(np.unique(y_true)) < 2
    if single_class:
        roc_auc = float("nan")
        avg_precision = float("nan")
    else:
        roc_auc = float(roc_auc_score(y_true, y_prob))
        avg_precision = float(average_precision_score(y_true, y_prob))

    return {
        "roc_auc": roc_auc,
        "avg_precision": avg_precision,
        "log_loss": float(log_loss(y_true, y_prob, labels=[0, 1])),
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


# ── Probability calibration (IWC Phase 1b item B) ───────────
# Raw XGBoost outputs under scale_pos_weight rebalancing are good
# *rankers* but poorly *calibrated* probabilities — they do not match
# observed positive frequencies.  Downstream the SDM probabilities are
# multiplied by a traffic score (P(whale) × traffic) and ensembled, so
# absolute-probability fidelity matters.  We fit a monotonic calibrator
# on out-of-fold predictions (which the per-fold models never trained
# on) and apply it to the saved OOF predictions before they feed the
# marts.  Isotonic is the default (non-parametric, large-sample safe);
# Platt/sigmoid is available for very small positive counts.


def fit_calibrator(
    oof_preds: np.ndarray,
    y_true: np.ndarray,
    method: str = "isotonic",
):
    """Fit a probability calibrator on out-of-fold predictions.

    Returns a fitted estimator with a ``predict``/``predict_proba``
    interface; pass it to :func:`apply_calibrator`.
    """
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression

    oof = np.asarray(oof_preds, dtype=np.float64)
    y = np.asarray(y_true, dtype=np.float64)
    if method == "isotonic":
        cal = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        cal.fit(oof, y)
    elif method in ("platt", "sigmoid"):
        cal = LogisticRegression(C=1e10, solver="lbfgs")
        cal.fit(oof.reshape(-1, 1), y)
    else:
        raise ValueError(f"Unknown calibration method: {method}")
    return cal


def apply_calibrator(cal, probs: np.ndarray) -> np.ndarray:
    """Apply a fitted calibrator to probabilities, clipped to [0, 1]."""
    from sklearn.isotonic import IsotonicRegression

    p = np.asarray(probs, dtype=np.float64)
    if isinstance(cal, IsotonicRegression):
        out = cal.predict(p)
    else:
        out = cal.predict_proba(p.reshape(-1, 1))[:, 1]
    return np.clip(out, 0.0, 1.0)


def plot_calibration_comparison(
    y_true: np.ndarray,
    raw_prob: np.ndarray,
    cal_prob: np.ndarray,
    n_bins: int = 10,
    title_prefix: str = "",
    save_path: Path | None = None,
) -> plt.Figure:
    """Plot raw vs calibrated reliability curves with Brier scores."""
    fig, ax = plt.subplots(figsize=(7, 5))
    raw_brier = brier_score_loss(y_true, raw_prob)
    cal_brier = brier_score_loss(y_true, cal_prob)

    rt, rp = calibration_curve(y_true, raw_prob, n_bins=n_bins)
    ct, cp = calibration_curve(y_true, cal_prob, n_bins=n_bins)
    ax.plot(
        rp,
        rt,
        "o-",
        color="#C1666B",
        linewidth=2,
        label=f"Raw (Brier={raw_brier:.4f})",
    )
    ax.plot(
        cp,
        ct,
        "s-",
        color="#1A936F",
        linewidth=2,
        label=f"Calibrated (Brier={cal_brier:.4f})",
    )
    ax.plot([0, 1], [0, 1], "k--", alpha=0.3, label="Perfectly calibrated")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title(f"{title_prefix}Calibration: Raw vs Isotonic")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        log.info("Saved calibration comparison: %s", save_path)
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


# ── Spatial residual diagnostics ────────────────────────────
# Out-of-fold residuals (y_true − P̂) should look like spatial noise once
# the model has captured the spatial structure.  Leftover autocorrelation
# means the SDM is missing a spatial signal (and that block-CV folds may
# still leak).  Two complementary checks (IWC Phase 1):
#   • Moran's I on a k-nearest-neighbour weight graph — a single global
#     autocorrelation statistic (≈ 0 ⇒ residuals are spatially random).
#   • Empirical semivariogram — γ(h) vs separation distance; a flat
#     variogram ⇒ no distance-dependent structure left in the residuals.
# Both subsample for tractability (the seasonal grid is millions of rows).


def _project_km(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Equirectangular lat/lon → local planar km (good enough for
    short-range neighbour and variogram diagnostics)."""
    lat0 = float(np.mean(lat))
    x = np.radians(lon) * 6371.0 * np.cos(np.radians(lat0))
    y = np.radians(lat) * 6371.0
    return np.column_stack([x, y])


def morans_i(
    values: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    k: int = 8,
    max_points: int = 20_000,
    seed: int = 42,
) -> float:
    """Global Moran's I of ``values`` on a row-standardised kNN graph.

    Returns a value in roughly [−1, 1]; ≈ 0 indicates spatial randomness,
    positive indicates clustering of like residuals.
    """
    from scipy.spatial import cKDTree

    values = np.asarray(values, dtype=np.float64)
    n_all = values.size
    rng = np.random.RandomState(seed)
    if n_all > max_points:
        sel = rng.choice(n_all, size=max_points, replace=False)
        values = values[sel]
        lat = np.asarray(lat)[sel]
        lon = np.asarray(lon)[sel]

    n = values.size
    if n < k + 1:
        return float("nan")

    coords = _project_km(np.asarray(lat), np.asarray(lon))
    tree = cKDTree(coords)
    # k+1 because the first neighbour is the point itself.
    _, nbr = tree.query(coords, k=k + 1)
    nbr = nbr[:, 1:]

    z = values - values.mean()
    denom = float(np.sum(z * z))
    if denom == 0:
        return float("nan")
    # Row-standardised weights ⇒ W = n, so I simplifies to this mean form.
    neighbour_mean = z[nbr].mean(axis=1)
    numer = float(np.sum(z * neighbour_mean))
    return numer / denom


def empirical_variogram(
    values: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    n_bins: int = 15,
    max_dist_km: float | None = None,
    sample: int = 4_000,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Empirical semivariogram γ(h) from a random subsample of points.

    Returns (bin_centres_km, gamma, pair_counts).
    """
    values = np.asarray(values, dtype=np.float64)
    n_all = values.size
    rng = np.random.RandomState(seed)
    if n_all > sample:
        sel = rng.choice(n_all, size=sample, replace=False)
        values = values[sel]
        lat = np.asarray(lat)[sel]
        lon = np.asarray(lon)[sel]

    coords = _project_km(np.asarray(lat), np.asarray(lon))
    # Pairwise distances + squared differences (O(sample²) — keep sample small).
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.sqrt((diff * diff).sum(axis=2))
    vdiff = values[:, None] - values[None, :]
    semivar = 0.5 * vdiff * vdiff

    iu = np.triu_indices(len(values), k=1)
    dist = dist[iu]
    semivar = semivar[iu]

    if max_dist_km is None:
        max_dist_km = float(np.percentile(dist, 90))
    edges = np.linspace(0, max_dist_km, n_bins + 1)
    centres = 0.5 * (edges[:-1] + edges[1:])
    gamma = np.full(n_bins, np.nan)
    counts = np.zeros(n_bins, dtype=int)
    for b in range(n_bins):
        mask = (dist >= edges[b]) & (dist < edges[b + 1])
        counts[b] = int(mask.sum())
        if counts[b] > 0:
            gamma[b] = float(semivar[mask].mean())
    return centres, gamma, counts


def variogram_range_km(
    centres: np.ndarray,
    gamma: np.ndarray,
    sill_fraction: float = 0.95,
) -> float:
    """Estimate the practical autocorrelation range from a variogram.

    The range is the separation distance at which the semivariance first
    reaches ``sill_fraction`` of the sill (max γ). Beyond this distance
    pairs of points are effectively spatially independent, so CV blocks
    sized at least this large keep train/test folds independent.

    Returns the range in km, or NaN if the variogram never plateaus.
    """
    valid = ~np.isnan(gamma)
    if valid.sum() < 2:
        return float("nan")
    c = np.asarray(centres)[valid]
    g = np.asarray(gamma)[valid]
    sill = float(np.max(g))
    if sill <= 0:
        return float("nan")
    threshold = sill_fraction * sill
    reached = np.where(g >= threshold)[0]
    if reached.size == 0:
        return float("nan")
    return float(c[reached[0]])


def h3_resolution_for_range_km(
    range_km: float,
    min_res: int = 1,
    max_res: int = 5,
) -> int | None:
    """Map an autocorrelation range (km) to an H3 block resolution.

    Picks the finest (highest) H3 resolution whose average edge length is
    still ≥ ``range_km``, so each CV block spans at least the spatial
    autocorrelation range while maximising the number of blocks (more,
    smaller folds give better CV coverage). Clamped to [min_res, max_res].

    Returns the resolution, or None if ``range_km`` is not usable.
    """
    import h3

    if not np.isfinite(range_km) or range_km <= 0:
        return None
    best = min_res
    for res in range(min_res, max_res + 1):
        edge = h3.average_hexagon_edge_length(res, unit="km")
        if edge >= range_km:
            best = res
        else:
            break
    return best


def plot_spatial_diagnostics(
    centres: np.ndarray,
    gamma: np.ndarray,
    morans: float,
    title_prefix: str = "",
    save_path: Path | None = None,
) -> plt.Figure:
    """Plot the residual semivariogram with the Moran's I annotation."""
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(centres, gamma, "o-", color="#0D3B66", linewidth=2)
    ax.set_xlabel("Separation distance (km)")
    ax.set_ylabel("Semivariance γ(h)")
    ax.set_title(f"{title_prefix}Residual Semivariogram")
    ax.grid(alpha=0.3)
    ax.text(
        0.97,
        0.05,
        f"Global Moran's I = {morans:.4f}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=11,
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "#1A936F"},
    )
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        log.info("Saved spatial diagnostics: %s", save_path)
    return fig


def spatial_residual_diagnostics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    title_prefix: str = "",
    save_path: Path | None = None,
    seed: int = 42,
) -> dict[str, float]:
    """Compute Moran's I + a semivariogram on out-of-fold residuals.

    Saves a diagnostic plot (if ``save_path`` given) and returns a flat
    metric dict suitable for ``mlflow.log_metrics()``.
    """
    residuals = np.asarray(y_true, dtype=np.float64) - np.asarray(
        y_pred, dtype=np.float64
    )
    morans = morans_i(residuals, lat, lon, seed=seed)
    centres, gamma, counts = empirical_variogram(residuals, lat, lon, seed=seed)
    plot_spatial_diagnostics(
        centres, gamma, morans, title_prefix=title_prefix, save_path=save_path
    )

    valid = ~np.isnan(gamma)
    nugget = float(gamma[valid][0]) if valid.any() else float("nan")
    sill = float(np.nanmax(gamma)) if valid.any() else float("nan")
    if sill and not np.isnan(sill) and sill != 0:
        ratio = float(nugget / sill)
    else:
        ratio = float("nan")
    return {
        "residual_morans_i": float(morans),
        "residual_variogram_nugget": nugget,
        "residual_variogram_sill": sill,
        "residual_variogram_ratio": ratio,
        "residual_variogram_range_km": variogram_range_km(centres, gamma),
    }
