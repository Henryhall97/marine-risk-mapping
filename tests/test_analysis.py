"""Tests for pipeline.analysis — ML evaluation and feature extraction.

Covers the pure-compute functions (metrics, spatial CV, spatial blocks)
that don't require a database or trained model artefacts.
"""

import matplotlib
import numpy as np
import pandas as pd

# Use non-interactive backend for CI
matplotlib.use("Agg")


# ── compute_binary_metrics() ────────────────────────────────


class TestComputeBinaryMetrics:
    def test_returns_all_keys(self, sample_binary_predictions):
        from pipeline.analysis.evaluate import compute_binary_metrics

        y_true, y_prob = sample_binary_predictions
        metrics = compute_binary_metrics(y_true, y_prob)

        expected_keys = {
            "roc_auc",
            "avg_precision",
            "log_loss",
            "brier_score",
            "f1",
            "precision",
            "recall",
            "tp",
            "fp",
            "fn",
            "tn",
            "threshold",
        }
        assert set(metrics.keys()) == expected_keys

    def test_auc_above_random(self, sample_binary_predictions):
        """With correlated predictions, AUC should beat 0.5."""
        from pipeline.analysis.evaluate import compute_binary_metrics

        y_true, y_prob = sample_binary_predictions
        metrics = compute_binary_metrics(y_true, y_prob)
        assert metrics["roc_auc"] > 0.5

    def test_confusion_matrix_sums_to_n(self, sample_binary_predictions):
        from pipeline.analysis.evaluate import compute_binary_metrics

        y_true, y_prob = sample_binary_predictions
        metrics = compute_binary_metrics(y_true, y_prob)
        total = metrics["tp"] + metrics["fp"] + metrics["fn"] + metrics["tn"]
        assert total == len(y_true)

    def test_perfect_predictions(self):
        from pipeline.analysis.evaluate import compute_binary_metrics

        y_true = np.array([0, 0, 1, 1])
        y_prob = np.array([0.1, 0.2, 0.8, 0.9])
        metrics = compute_binary_metrics(y_true, y_prob)
        assert metrics["roc_auc"] == 1.0
        assert metrics["f1"] == 1.0

    def test_custom_threshold(self, sample_binary_predictions):
        from pipeline.analysis.evaluate import compute_binary_metrics

        y_true, y_prob = sample_binary_predictions
        metrics_low = compute_binary_metrics(y_true, y_prob, threshold=0.3)
        metrics_high = compute_binary_metrics(y_true, y_prob, threshold=0.7)
        # Lower threshold → more positives → higher recall
        assert metrics_low["recall"] >= metrics_high["recall"]


# ── spatial_cv_split() ──────────────────────────────────────


class TestSpatialCvSplit:
    def test_yields_n_folds(self):
        from pipeline.analysis.evaluate import spatial_cv_split

        df = pd.DataFrame({"cv_fold": [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]})
        folds = list(spatial_cv_split(df, n_folds=5))
        assert len(folds) == 5

    def test_no_overlap(self):
        from pipeline.analysis.evaluate import spatial_cv_split

        df = pd.DataFrame({"cv_fold": [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]})
        for train_idx, val_idx in spatial_cv_split(df, n_folds=5):
            overlap = set(train_idx) & set(val_idx)
            assert len(overlap) == 0

    def test_full_coverage(self):
        from pipeline.analysis.evaluate import spatial_cv_split

        df = pd.DataFrame({"cv_fold": [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]})
        all_val = set()
        for _, val_idx in spatial_cv_split(df, n_folds=5):
            all_val.update(val_idx)
        assert all_val == set(df.index)

    def test_each_fold_has_data(self):
        from pipeline.analysis.evaluate import spatial_cv_split

        df = pd.DataFrame({"cv_fold": [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]})
        for train_idx, val_idx in spatial_cv_split(df, n_folds=5):
            assert len(train_idx) > 0
            assert len(val_idx) > 0


# ── _assign_spatial_blocks() ────────────────────────────────


class TestAssignSpatialBlocks:
    def test_adds_required_columns(self, sample_h3_df):
        from pipeline.analysis.extract_features import (
            _assign_spatial_blocks,
        )

        result = _assign_spatial_blocks(sample_h3_df)
        assert "spatial_block" in result.columns
        assert "cv_fold" in result.columns

    def test_fold_range(self, sample_h3_df):
        from pipeline.analysis.extract_features import (
            _assign_spatial_blocks,
        )

        result = _assign_spatial_blocks(sample_h3_df)
        assert result["cv_fold"].min() >= 0
        assert result["cv_fold"].max() <= 4

    def test_does_not_drop_rows(self, sample_h3_df):
        from pipeline.analysis.extract_features import (
            _assign_spatial_blocks,
        )

        result = _assign_spatial_blocks(sample_h3_df)
        assert len(result) == len(sample_h3_df)

    def test_deterministic(self, sample_h3_df):
        from pipeline.analysis.extract_features import (
            _assign_spatial_blocks,
        )

        r1 = _assign_spatial_blocks(sample_h3_df)
        r2 = _assign_spatial_blocks(sample_h3_df)
        pd.testing.assert_frame_equal(r1, r2)


# ── plot functions return Figure ────────────────────────────


class TestPlotFunctions:
    def test_roc_pr_returns_figure(self, sample_binary_predictions):
        from pipeline.analysis.evaluate import plot_roc_pr_curves

        y_true, y_prob = sample_binary_predictions
        fig = plot_roc_pr_curves(y_true, y_prob)
        assert isinstance(fig, matplotlib.figure.Figure)
        matplotlib.pyplot.close(fig)

    def test_calibration_returns_figure(self, sample_binary_predictions):
        from pipeline.analysis.evaluate import plot_calibration

        y_true, y_prob = sample_binary_predictions
        fig = plot_calibration(y_true, y_prob)
        assert isinstance(fig, matplotlib.figure.Figure)
        matplotlib.pyplot.close(fig)

    def test_feature_importance_returns_figure(self):
        from pipeline.analysis.evaluate import plot_feature_importance

        importances = pd.Series({"feat_a": 0.5, "feat_b": 0.3, "feat_c": 0.2})
        fig = plot_feature_importance(importances)
        assert isinstance(fig, matplotlib.figure.Figure)
        matplotlib.pyplot.close(fig)
