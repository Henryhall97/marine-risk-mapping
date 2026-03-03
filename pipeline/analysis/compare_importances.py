"""Compare learned feature importances vs hand-tuned risk weights.

Reads the trained XGBoost feature importances from the strike model
and whale SDM, then compares them against the hand-tuned sub-score
weights used in fct_collision_risk.

This reveals whether the ML models agree with the expert-designed
weight scheme, and where they diverge.

Usage:
    uv run python pipeline/analysis/compare_importances.py
"""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pipeline.config import COLLISION_RISK_WEIGHTS, ML_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

ARTIFACTS_DIR = ML_DIR / "artifacts" / "comparison"

# Map individual features to their domain sub-score
FEATURE_DOMAIN_MAP = {
    # Traffic features
    "months_active": "traffic_score",
    "total_pings": "traffic_score",
    "avg_monthly_vessels": "traffic_score",
    "peak_monthly_vessels": "traffic_score",
    "avg_speed_knots": "traffic_score",
    "peak_speed_knots": "traffic_score",
    "avg_high_speed_vessels": "traffic_score",
    "avg_large_vessels": "traffic_score",
    "avg_vessel_length_m": "traffic_score",
    "avg_deep_draft_vessels": "traffic_score",
    "avg_night_vessels": "traffic_score",
    "avg_commercial_vessels": "traffic_score",
    "avg_fishing_vessels": "traffic_score",
    "avg_passenger_vessels": "traffic_score",
    # Cetacean features
    "total_sightings": "cetacean_score",
    "unique_species": "cetacean_score",
    "baleen_whale_sightings": "cetacean_score",
    "recent_sightings": "cetacean_score",
    # Proximity features
    "dist_to_nearest_whale_km": "proximity_score",
    "dist_to_nearest_ship_km": "proximity_score",
    "whale_proximity_score": "proximity_score",
    "ship_proximity_score": "proximity_score",
    "dist_to_nearest_strike_km": "proximity_score",
    "strike_proximity_score": "proximity_score",
    "dist_to_nearest_protection_km": "proximity_score",
    "protection_proximity_score": "proximity_score",
    # Bathymetry → habitat
    "depth_m": "habitat_score",
    "depth_range_m": "habitat_score",
    "is_continental_shelf": "habitat_score",
    "is_shelf_edge": "habitat_score",
    # Ocean covariates → habitat
    "sst": "habitat_score",
    "sst_sd": "habitat_score",
    "mld": "habitat_score",
    "sla": "habitat_score",
    "pp_upper_200m": "habitat_score",
    # Speed zones → protection gap
    "in_speed_zone": "protection_gap",
    "in_current_sma": "protection_gap",
    "in_proposed_zone": "protection_gap",
    "zone_count": "protection_gap",
    "max_season_days": "protection_gap",
    # MPA → protection gap
    "mpa_count": "protection_gap",
    "has_strict_protection": "protection_gap",
    "has_no_take_zone": "protection_gap",
    # Nisi reference
    "nisi_all_risk": "reference_risk_score",
    "nisi_shipping_index": "reference_risk_score",
    "nisi_whale_space_use": "reference_risk_score",
    "nisi_hotspot_overlap": "reference_risk_score",
}


def _load_importances(model_name: str) -> pd.Series | None:
    """Load feature importances CSV for a model."""
    csv_path = ML_DIR / "artifacts" / model_name / "feature_importance.csv"
    if not csv_path.exists():
        log.warning("Importance file not found: %s", csv_path)
        return None
    df = pd.read_csv(csv_path, index_col=0)
    return df.iloc[:, 0]


def aggregate_domain_importance(
    importances: pd.Series,
) -> pd.Series:
    """Sum feature importances by domain sub-score."""
    domain_sums = {}
    unmapped = 0.0
    for feature, imp in importances.items():
        domain = FEATURE_DOMAIN_MAP.get(feature)
        if domain:
            domain_sums[domain] = domain_sums.get(domain, 0) + imp
        else:
            unmapped += imp

    # Normalise to sum to 1
    total = sum(domain_sums.values()) + unmapped
    if total > 0:
        domain_sums = {k: v / total for k, v in domain_sums.items()}

    return pd.Series(domain_sums).sort_values(ascending=False)


def plot_comparison(
    hand_tuned: dict[str, float],
    strike_domains: pd.Series,
    sdm_domains: pd.Series | None,
    save_path: Path,
) -> plt.Figure:
    """Side-by-side bar chart: hand-tuned vs ML-learned domain weights."""
    domains = sorted(hand_tuned.keys())

    ht_vals = [hand_tuned[d] for d in domains]
    strike_vals = [strike_domains.get(d, 0) for d in domains]

    x = np.arange(len(domains))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.bar(
        x - width,
        ht_vals,
        width,
        label="Hand-tuned (fct_collision_risk)",
        color="#0D3B66",
        edgecolor="white",
    )
    ax.bar(
        x,
        strike_vals,
        width,
        label="XGBoost (strike model)",
        color="#1A936F",
        edgecolor="white",
    )

    if sdm_domains is not None:
        sdm_vals = [sdm_domains.get(d, 0) for d in domains]
        ax.bar(
            x + width,
            sdm_vals,
            width,
            label="XGBoost (whale SDM)",
            color="#FAA916",
            edgecolor="white",
        )

    ax.set_xlabel("Risk Domain")
    ax.set_ylabel("Weight / Importance")
    ax.set_title("Hand-Tuned Weights vs ML-Learned Feature Importance by Domain")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [d.replace("_", " ").title() for d in domains],
        rotation=30,
        ha="right",
    )
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    log.info("Saved comparison plot: %s", save_path)
    return fig


def main() -> None:
    """Compare hand-tuned vs learned importance."""
    import matplotlib

    matplotlib.use("Agg")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load ML importances
    strike_imp = _load_importances("strike")
    sdm_imp = _load_importances("sdm")

    if strike_imp is None and sdm_imp is None:
        log.error(
            "No trained models found. Run train_strike_model.py "
            "and/or train_sdm_model.py first."
        )
        return

    # Aggregate to domain level
    strike_domains = (
        aggregate_domain_importance(strike_imp)
        if strike_imp is not None
        else pd.Series(dtype=float)
    )
    sdm_domains = aggregate_domain_importance(sdm_imp) if sdm_imp is not None else None

    # Print comparison table
    print("\n" + "=" * 60)
    print("Domain Weight Comparison")
    print("=" * 60)
    print(f"{'Domain':<25} {'Hand-tuned':>10} {'Strike ML':>10} {'SDM ML':>10}")
    print("-" * 60)
    for domain in sorted(COLLISION_RISK_WEIGHTS.keys()):
        ht = COLLISION_RISK_WEIGHTS[domain]
        st = strike_domains.get(domain, 0) if strike_imp is not None else 0
        sd = sdm_domains.get(domain, 0) if sdm_domains is not None else 0
        print(f"{domain:<25} {ht:>10.2%} {st:>10.2%} {sd:>10.2%}")
    print("=" * 60)

    # Plot
    plot_comparison(
        COLLISION_RISK_WEIGHTS,
        strike_domains,
        sdm_domains,
        save_path=ARTIFACTS_DIR / "domain_weight_comparison.png",
    )

    # Save comparison data
    comparison_df = pd.DataFrame(
        {
            "hand_tuned": pd.Series(COLLISION_RISK_WEIGHTS),
            "strike_ml": strike_domains,
            "sdm_ml": (
                sdm_domains if sdm_domains is not None else pd.Series(dtype=float)
            ),
        }
    ).fillna(0)
    comparison_csv = ARTIFACTS_DIR / "domain_weight_comparison.csv"
    comparison_df.to_csv(comparison_csv)
    log.info("Saved comparison data: %s", comparison_csv)


if __name__ == "__main__":
    main()
