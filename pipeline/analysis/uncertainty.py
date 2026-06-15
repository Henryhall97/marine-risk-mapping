"""Uncertainty quantification for the whale SDM/ISDM models.

Two complementary error-analysis tools used by the SDM training scripts
(IWC migration, Phase 1 — "uncertainty on existing models"):

1. Bootstrap / bagging ensemble
   The SDMs are ``binary:logistic`` XGBoost classifiers outputting a
   Bernoulli P(presence).  Quantile regression does not apply to a
   probability target, so we quantify predictive uncertainty by refitting
   the model K times on bootstrap resamples (optionally row-subsampled =
   bagging) with varied seeds.  The per-cell MEAN of the K grid
   predictions is the point estimate; the per-cell STANDARD DEVIATION of
   the K predictions is the uncertainty band (a CV-analogue surface).
   Tight spread → confident cell; wide spread → data-poor / low-confidence.

2. MESS extrapolation flag
   The Multivariate Environmental Similarity Surface (Elith et al. 2010)
   flags grid cells whose environmental covariates fall OUTSIDE the range
   the model was trained on — i.e. predictions that are extrapolations
   rather than interpolations.  Per cell it returns the minimum
   similarity across covariates (negative ⇒ at least one covariate is out
   of range) and names the most-dissimilar (MoD) variable.

Both are pure-numpy / XGBoost helpers with no I/O — the training scripts
own reading features, scoring, and persistence.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import xgboost as xgb

log = logging.getLogger(__name__)

# Default ensemble size.  ~50 refits gives a stable spread estimate while
# staying affordable; the seasonal SDM (7.3M rows) can trade K / sample
# fraction for runtime via the training-script CLI.
DEFAULT_BOOTSTRAP_K = 50


def bootstrap_ensemble_predict(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_grid: pd.DataFrame,
    base_params: dict,
    k: int = DEFAULT_BOOTSTRAP_K,
    sample_frac: float = 1.0,
    n_estimators: int | None = None,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit K bootstrap-resampled XGBoost models and score a grid.

    Each of the K members is trained on a bootstrap resample (sampling
    rows WITH replacement) of ``X_train`` / ``y_train`` and then scores
    every row of ``X_grid``.  The K grid-prediction vectors are stacked
    to produce per-cell summary statistics.

    Parameters
    ----------
    X_train, y_train
        The full training design matrix and binary target.
    X_grid
        The grid to score (columns aligned to ``X_train``).
    base_params
        XGBoost params shared by every member.  ``random_state`` is
        overwritten per member; ``early_stopping_rounds`` is stripped
        (members fit a fixed n_estimators — no eval set).
    k
        Number of ensemble members (bootstrap refits).
    sample_frac
        Fraction of rows drawn per bootstrap (with replacement).  1.0 is
        a classic bootstrap (n draws); <1.0 is sub-bagging — cheaper and
        still a valid spread estimator for large datasets.
    n_estimators
        Optional override for the per-member tree count.  Lowering this
        (e.g. 200) trades a little member accuracy for a large runtime
        saving on big grids; the spread estimate is robust to it.
    seed
        Base RNG seed; member ``i`` uses ``seed + i``.

    Returns
    -------
    mean, std
        Two float arrays of length ``len(X_grid)``: the per-cell mean and
        standard deviation of P(presence) across the K members.
    """
    params = {
        key: value
        for key, value in base_params.items()
        if key not in ("early_stopping_rounds", "random_state")
    }
    if n_estimators is not None:
        params["n_estimators"] = n_estimators

    n_rows = len(X_train)
    n_draw = max(int(round(n_rows * sample_frac)), 1)
    rng = np.random.RandomState(seed)

    # Accumulate sum and sum-of-squares to avoid holding K grid-length
    # vectors in memory simultaneously (the seasonal grid is 7.3M rows).
    n_grid = len(X_grid)
    pred_sum = np.zeros(n_grid, dtype=np.float64)
    pred_sumsq = np.zeros(n_grid, dtype=np.float64)

    X_values = X_train
    for i in range(k):
        idx = rng.randint(0, n_rows, size=n_draw)
        member = xgb.XGBClassifier(**params, random_state=seed + i)
        member.fit(X_values.iloc[idx], y_train.iloc[idx], verbose=False)
        preds = member.predict_proba(X_grid)[:, 1].astype(np.float64)
        pred_sum += preds
        pred_sumsq += preds * preds
        if (i + 1) % 10 == 0 or i == k - 1:
            log.info("  bootstrap member %d/%d fitted", i + 1, k)

    mean = pred_sum / k
    # Population variance across members; clip tiny negatives from fp error.
    var = np.maximum(pred_sumsq / k - mean * mean, 0.0)
    std = np.sqrt(var)
    return mean.astype(np.float32), std.astype(np.float32)


def _mess_one_variable(grid_vals: np.ndarray, train_vals: np.ndarray) -> np.ndarray:
    """MESS similarity (%) for one covariate, vectorised over the grid.

    Follows Elith et al. (2010) / ``dismo::mess``:
      * value below the training min ⇒ (p − min)/(max − min)·100  (< 0)
      * value above the training max ⇒ (max − p)/(max − min)·100  (< 0)
      * value inside the range       ⇒ 2·min(F, 100 − F), where F is the
        percentage of training values below ``p`` (0 at the edges of the
        observed range, 100 at the median).
    """
    train_sorted = np.sort(train_vals)
    n = train_sorted.size
    vmin = train_sorted[0]
    vmax = train_sorted[-1]
    spread = vmax - vmin
    if spread <= 0:
        # Degenerate covariate: similar where equal, extrapolated otherwise.
        return np.where(grid_vals == vmin, 100.0, -100.0).astype(np.float64)

    # Percentage of training points strictly below each grid value.
    below = np.searchsorted(train_sorted, grid_vals, side="left")
    f = (below / n) * 100.0
    inside = 2.0 * np.minimum(f, 100.0 - f)

    sim = np.where(
        grid_vals < vmin,
        (grid_vals - vmin) / spread * 100.0,
        np.where(grid_vals > vmax, (vmax - grid_vals) / spread * 100.0, inside),
    )
    return sim.astype(np.float64)


def mess_extrapolation(
    train_cov: pd.DataFrame,
    grid_cov: pd.DataFrame,
) -> pd.DataFrame:
    """Multivariate Environmental Similarity Surface for a prediction grid.

    Parameters
    ----------
    train_cov
        Covariate values observed during training (one column per
        environmental predictor).
    grid_cov
        Covariate values for every grid cell to be scored, same columns.

    Returns
    -------
    DataFrame with columns:
      * ``mess_value``    — minimum similarity across covariates (%);
        < 0 ⇒ extrapolation (≥ 1 covariate outside the training range).
      * ``extrapolated``  — boolean ``mess_value < 0``.
      * ``mod_variable``  — name of the most-dissimilar covariate (the one
        attaining the minimum similarity) per cell.
    """
    cols = list(grid_cov.columns)
    n_grid = len(grid_cov)
    sims = np.empty((len(cols), n_grid), dtype=np.float64)

    for j, col in enumerate(cols):
        train_vals = train_cov[col].to_numpy(dtype=np.float64)
        train_vals = train_vals[~np.isnan(train_vals)]
        grid_vals = grid_cov[col].to_numpy(dtype=np.float64)
        if train_vals.size == 0:
            sims[j, :] = np.nan
            continue
        # NaN grid covariate → treat as maximally dissimilar (extrapolated).
        col_sim = _mess_one_variable(np.nan_to_num(grid_vals, nan=np.inf), train_vals)
        col_sim = np.where(np.isnan(grid_vals), -100.0, col_sim)
        sims[j, :] = col_sim

    mess_value = np.nanmin(sims, axis=0)
    mod_idx = np.nanargmin(np.where(np.isnan(sims), np.inf, sims), axis=0)
    mod_variable = np.array(cols)[mod_idx]

    return pd.DataFrame(
        {
            "mess_value": mess_value.astype(np.float32),
            "extrapolated": mess_value < 0,
            "mod_variable": mod_variable,
        }
    )
