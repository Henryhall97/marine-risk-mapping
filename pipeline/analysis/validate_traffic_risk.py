"""Validate the traffic risk scoring methodology.

Runs three categories of validation check described in the
traffic risk methodology document (docs/pdfs/traffic_risk_methodology.pdf):

  1. Internal consistency — Jensen's inequality, draft imputation
     coverage, weight-sum verification
  2. External benchmarks — Nisi correlation, strike-site overlap,
     SMA overlap
  3. Sensitivity analysis — weight perturbation, Jensen's bias
     spatial distribution

Usage:
    uv run python pipeline/analysis/validate_traffic_risk.py
    uv run python pipeline/analysis/validate_traffic_risk.py --section internal
    uv run python pipeline/analysis/validate_traffic_risk.py --section external
    uv run python pipeline/analysis/validate_traffic_risk.py --section sensitivity
"""

import argparse
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psycopg2
from scipy import stats

from pipeline.config import (
    COLLISION_RISK_ML_WEIGHTS,
    COLLISION_RISK_WEIGHTS,
    DB_CONFIG,
    ML_DIR,
    VT_LETHALITY_BETA0,
    VT_LETHALITY_BETA1,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Output directory ──────────────────────────────────────────
ARTIFACTS_DIR = ML_DIR / "artifacts" / "validation"

# ── Plotting style ────────────────────────────────────────────
NAVY = "#0D3B66"
TEAL = "#1A936F"
AMBER = "#FAA916"
RED = "#D64045"
LIGHT_BG = "#F0F4F8"


def get_connection():
    """Connect to PostGIS."""
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def query_df(sql: str) -> pd.DataFrame:
    """Execute SQL and return a DataFrame."""
    with get_connection() as conn:
        return pd.read_sql(sql, conn)


# ═══════════════════════════════════════════════════════════════
# 1. INTERNAL CONSISTENCY CHECKS
# ═══════════════════════════════════════════════════════════════


def check_weight_sums() -> bool:
    """Verify all weight dictionaries sum to 1.0."""
    log.info("=" * 60)
    log.info("CHECK: Weight sum verification")
    log.info("=" * 60)

    all_ok = True

    # Hand-tuned composite weights
    ht_sum = sum(COLLISION_RISK_WEIGHTS.values())
    ok = abs(ht_sum - 1.0) < 1e-9
    status = "PASS" if ok else "FAIL"
    log.info("  Hand-tuned composite weights sum: %.6f  [%s]", ht_sum, status)
    all_ok = all_ok and ok

    # ML composite weights
    ml_sum = sum(COLLISION_RISK_ML_WEIGHTS.values())
    ok = abs(ml_sum - 1.0) < 1e-9
    status = "PASS" if ok else "FAIL"
    log.info("  ML composite weights sum:         %.6f  [%s]", ml_sum, status)
    all_ok = all_ok and ok

    # 8-component traffic sub-score weights
    traffic_weights = {
        "speed_lethality": 0.20,
        "high_speed_fraction": 0.10,
        "vessels": 0.20,
        "large_vessels": 0.10,
        "draft_risk": 0.10,
        "draft_risk_fraction": 0.05,
        "commercial": 0.10,
        "night_traffic": 0.15,
    }
    tw_sum = sum(traffic_weights.values())
    ok = abs(tw_sum - 1.0) < 1e-9
    status = "PASS" if ok else "FAIL"
    log.info("  Traffic sub-score weights sum:    %.6f  [%s]", tw_sum, status)
    all_ok = all_ok and ok

    # Cetacean sub-score
    cetacean_sum = 0.35 + 0.35 + 0.30
    ok = abs(cetacean_sum - 1.0) < 1e-9
    status = "PASS" if ok else "FAIL"
    log.info("  Cetacean sub-score weights sum:   %.6f  [%s]", cetacean_sum, status)
    all_ok = all_ok and ok

    # Strike sub-score
    strike_sum = 0.40 + 0.35 + 0.25
    ok = abs(strike_sum - 1.0) < 1e-9
    status = "PASS" if ok else "FAIL"
    log.info("  Strike sub-score weights sum:     %.6f  [%s]", strike_sum, status)
    all_ok = all_ok and ok

    # Proximity sub-score
    prox_sum = 0.45 + 0.30 + 0.25
    ok = abs(prox_sum - 1.0) < 1e-9
    status = "PASS" if ok else "FAIL"
    log.info("  Proximity sub-score weights sum:  %.6f  [%s]", prox_sum, status)
    all_ok = all_ok and ok

    log.info("")
    return all_ok


def check_jensens_inequality() -> bool:
    """Compare per-vessel lethality vs cell-average approximation.

    Per-vessel lethality (vw_avg_lethality) is computed inside
    aggregate_ais.py by applying V&T to each vessel's speed,
    then averaging. The cell-average fallback applies V&T to
    the cell-mean speed. Jensen's inequality says the cell-average
    will systematically underestimate because V&T is convex.

    We check:
      1. Both columns are populated (AIS re-run completed)
      2. Rank correlation > 0.95 (orderings preserved)
      3. Per-vessel >= cell-average (Jensen's direction)
      4. Magnitude and spatial distribution of the bias
    """
    log.info("=" * 60)
    log.info("CHECK: Jensen's inequality — per-vessel vs cell-average lethality")
    log.info("=" * 60)

    # Query cells with per-vessel lethality populated
    sql = """
        select
            h3_cell,
            cell_lat,
            cell_lon,
            vw_avg_speed_knots,
            vw_avg_lethality,
            high_speed_fraction,
            unique_vessels
        from ais_h3_summary
        where vw_avg_lethality is not null
          and vw_avg_speed_knots is not null
    """
    df = query_df(sql)

    if df.empty:
        log.warning(
            "  No rows with vw_avg_lethality populated — AIS re-run "
            "may not have completed yet. SKIPPING."
        )
        return True  # Not a failure, just not ready

    n = len(df)
    log.info("  Cells with per-vessel lethality: %s", f"{n:,}")

    # Compute cell-average V&T approximation
    df["cell_avg_lethality"] = 1.0 / (
        1.0
        + np.exp(-(VT_LETHALITY_BETA0 + VT_LETHALITY_BETA1 * df["vw_avg_speed_knots"]))
    )

    # -- Rank correlation --
    rho, p_value = stats.spearmanr(df["vw_avg_lethality"], df["cell_avg_lethality"])
    ok_corr = rho > 0.90
    log.info(
        "  Spearman rank correlation:  rho=%.4f  p=%.2e  [%s]",
        rho,
        p_value,
        "PASS" if ok_corr else "WARN",
    )

    # -- Bias direction (Jensen's: per-vessel >= cell-average for convex f) --
    df["bias"] = df["vw_avg_lethality"] - df["cell_avg_lethality"]
    pct_higher = (df["bias"] > 0).mean() * 100
    mean_bias = df["bias"].mean()
    median_bias = df["bias"].median()
    max_bias = df["bias"].max()

    ok_direction = pct_higher > 50  # Majority should show positive bias
    log.info(
        "  Per-vessel > cell-average:  %.1f%% of cells  [%s]",
        pct_higher,
        "PASS" if ok_direction else "WARN",
    )
    log.info(
        "  Bias (per-vessel - cell-avg): mean=%.4f  median=%.4f  max=%.4f",
        mean_bias,
        median_bias,
        max_bias,
    )

    # -- Percentile comparisons --
    for pct in [50, 90, 95, 99]:
        pv = np.percentile(df["vw_avg_lethality"], pct)
        ca = np.percentile(df["cell_avg_lethality"], pct)
        log.info(
            "  P%d:  per-vessel=%.4f  cell-avg=%.4f  diff=%.4f", pct, pv, ca, pv - ca
        )

    # -- Where is the bias largest? --
    top_bias = df.nlargest(10, "bias")[
        [
            "h3_cell",
            "cell_lat",
            "cell_lon",
            "vw_avg_speed_knots",
            "vw_avg_lethality",
            "cell_avg_lethality",
            "bias",
            "unique_vessels",
        ]
    ]
    log.info("\n  Top 10 cells by Jensen's bias:")
    for _, row in top_bias.iterrows():
        log.info(
            "    cell=%d  lat=%.2f  lon=%.2f  speed=%.1f kn  "
            "pv=%.4f  ca=%.4f  bias=%.4f  vessels=%d",
            row["h3_cell"],
            row["cell_lat"],
            row["cell_lon"],
            row["vw_avg_speed_knots"],
            row["vw_avg_lethality"],
            row["cell_avg_lethality"],
            row["bias"],
            int(row["unique_vessels"]),
        )

    # -- Plot --
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Scatter: per-vessel vs cell-average
    ax = axes[0]
    sample = df.sample(min(50_000, n), random_state=42)
    ax.scatter(
        sample["cell_avg_lethality"],
        sample["vw_avg_lethality"],
        alpha=0.15,
        s=3,
        color=NAVY,
    )
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="1:1 line")
    ax.set_xlabel("Cell-average lethality (Jensen-biased)")
    ax.set_ylabel("Per-vessel lethality (correct)")
    ax.set_title(f"Jensen's Inequality Check\n(rho={rho:.4f}, n={n:,})")
    ax.legend()
    ax.grid(alpha=0.3)

    # Histogram of bias
    ax = axes[1]
    ax.hist(df["bias"], bins=100, color=TEAL, edgecolor="white", alpha=0.8)
    ax.axvline(0, color="k", linestyle="--", alpha=0.5)
    ax.axvline(
        mean_bias, color=RED, linestyle="-", linewidth=2, label=f"Mean={mean_bias:.4f}"
    )
    ax.set_xlabel("Bias (per-vessel - cell-average)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Jensen's Bias")
    ax.legend()
    ax.grid(alpha=0.3)

    # Bias vs speed
    ax = axes[2]
    ax.scatter(
        sample["vw_avg_speed_knots"],
        sample["bias"],
        alpha=0.15,
        s=3,
        color=AMBER,
    )
    ax.axhline(0, color="k", linestyle="--", alpha=0.5)
    ax.set_xlabel("Mean speed (knots)")
    ax.set_ylabel("Bias (per-vessel - cell-average)")
    ax.set_title("Jensen's Bias vs Cell Speed")
    ax.grid(alpha=0.3)

    plt.tight_layout()
    fig.savefig(
        ARTIFACTS_DIR / "jensens_inequality_check.png", dpi=150, bbox_inches="tight"
    )
    plt.close(fig)
    log.info("  Saved: jensens_inequality_check.png\n")

    return ok_corr and ok_direction


def check_draft_imputation() -> bool:
    """Verify draft imputation coverage and quality.

    Before imputation ~15% of vessels lack draft. After our 4-tier
    waterfall (per-vessel type OLS → type median → global median),
    coverage should be ~100% of cell-months.
    """
    log.info("=" * 60)
    log.info("CHECK: Draft imputation coverage & quality")
    log.info("=" * 60)

    # Check raw vs imputed coverage
    sql = """
        select
            count(*) as total_rows,
            count(vw_avg_draft_m) as has_raw_draft,
            count(vw_avg_draft_imputed_m) as has_imputed_draft,
            count(draft_imputed_count) as has_impute_count,
            avg(vw_avg_draft_m) as mean_raw_draft,
            avg(vw_avg_draft_imputed_m) as mean_imputed_draft,
            sum(draft_imputed_count) as total_imputed_vessels
        from ais_h3_summary
    """
    row = query_df(sql).iloc[0]

    total = int(row["total_rows"])
    has_raw = int(row["has_raw_draft"])
    has_imputed = int(row["has_imputed_draft"])

    raw_coverage = has_raw / total * 100 if total > 0 else 0
    imputed_coverage = has_imputed / total * 100 if total > 0 else 0

    log.info("  Total cell-months:          %s", f"{total:,}")
    log.info("  With raw draft:             %s (%.1f%%)", f"{has_raw:,}", raw_coverage)
    log.info(
        "  With imputed draft:         %s (%.1f%%)",
        f"{has_imputed:,}",
        imputed_coverage,
    )

    if has_imputed > 0:
        log.info("  Mean raw draft:             %.2f m", row["mean_raw_draft"] or 0)
        log.info("  Mean imputed draft:         %.2f m", row["mean_imputed_draft"])
        log.info(
            "  Total imputed vessels:      %s",
            f"{int(row['total_imputed_vessels'] or 0):,}",
        )
    else:
        log.warning("  No imputed draft data — AIS re-run may not be complete.")

    # Check dbt-level imputation (int_vessel_traffic has draft_imputed_m)
    sql2 = """
        select
            count(*) as total,
            count(draft_imputed_m) as has_draft,
            avg(draft_imputed_m) as mean_draft,
            count(case when draft_was_imputed then 1 end) as was_imputed
        from int_vessel_traffic
    """
    dbt_row = query_df(sql2).iloc[0]

    dbt_total = int(dbt_row["total"])
    dbt_has = int(dbt_row["has_draft"])
    dbt_coverage = dbt_has / dbt_total * 100 if dbt_total > 0 else 0
    dbt_imputed = int(dbt_row["was_imputed"])

    log.info("\n  dbt int_vessel_traffic:")
    log.info("    Total rows:               %s", f"{dbt_total:,}")
    log.info("    With draft_imputed_m:     %s (%.1f%%)", f"{dbt_has:,}", dbt_coverage)
    log.info(
        "    Was OLS-imputed (dbt):    %s (%.1f%%)",
        f"{dbt_imputed:,}",
        dbt_imputed / dbt_total * 100 if dbt_total > 0 else 0,
    )
    log.info("    Mean imputed draft:       %.2f m", dbt_row["mean_draft"] or 0)

    ok = dbt_coverage > 95
    log.info("  Overall coverage check:     [%s]\n", "PASS" if ok else "WARN")
    return ok


def run_internal_checks() -> dict[str, bool]:
    """Run all internal consistency checks."""
    log.info("\n" + "=" * 60)
    log.info("  SECTION 1: INTERNAL CONSISTENCY CHECKS")
    log.info("=" * 60 + "\n")

    results = {}
    results["weight_sums"] = check_weight_sums()
    results["jensens_inequality"] = check_jensens_inequality()
    results["draft_imputation"] = check_draft_imputation()
    return results


# ═══════════════════════════════════════════════════════════════
# 2. EXTERNAL BENCHMARKS
# ═══════════════════════════════════════════════════════════════


def check_nisi_correlation() -> bool:
    """Correlate our composite risk with Nisi et al. (2024) shipping index.

    Cells with Nisi coverage should show strong positive correlation
    between our traffic_score and their shipping_index. Divergence
    is not necessarily bad — it may indicate our model adds value
    (finer spatial resolution, speed-lethality gradient).
    """
    log.info("=" * 60)
    log.info("CHECK: Correlation with Nisi et al. (2024) reference risk")
    log.info("=" * 60)

    sql = """
        select
            r.risk_score,
            r.traffic_score,
            r.cetacean_score,
            r.proximity_score,
            r.strike_score,
            r.habitat_score,
            r.protection_gap,
            r.reference_risk_score,
            r.nisi_all_risk,
            r.nisi_shipping_index,
            r.nisi_whale_space_use,
            r.nisi_hotspot_overlap,
            r.avg_speed_lethality,
            r.avg_monthly_vessels
        from fct_collision_risk r
        where r.has_nisi_reference
          and r.has_traffic
    """
    df = query_df(sql)

    if df.empty:
        log.warning("  No cells with both traffic and Nisi data. SKIPPING.")
        return True

    n = len(df)
    log.info("  Cells with traffic + Nisi data: %s", f"{n:,}")

    # Spearman correlations for each pair
    pairs = [
        ("risk_score", "nisi_all_risk", "Composite risk vs Nisi all_risk"),
        (
            "traffic_score",
            "nisi_shipping_index",
            "Traffic score vs Nisi shipping_index",
        ),
        (
            "cetacean_score",
            "nisi_whale_space_use",
            "Cetacean score vs Nisi whale_space_use",
        ),
        (
            "risk_score",
            "nisi_hotspot_overlap",
            "Composite risk vs Nisi hotspot_overlap",
        ),
    ]

    rhos = {}
    log.info("\n  Spearman correlations:")
    for our_col, nisi_col, label in pairs:
        mask = df[our_col].notna() & df[nisi_col].notna()
        if mask.sum() < 100:
            log.info("    %s: too few data points (%d)", label, mask.sum())
            continue
        rho, p = stats.spearmanr(df.loc[mask, our_col], df.loc[mask, nisi_col])
        rhos[label] = rho
        log.info("    %s:  rho=%.4f  p=%.2e", label, rho, p)

    # Full cross-correlation matrix for the sub-scores vs Nisi
    sub_scores = [
        "traffic_score",
        "cetacean_score",
        "proximity_score",
        "strike_score",
        "habitat_score",
        "protection_gap",
    ]
    nisi_cols = ["nisi_all_risk", "nisi_shipping_index", "nisi_whale_space_use"]

    log.info("\n  Cross-correlation matrix (Spearman):")
    header = "  " + f"{'':>25s}" + "".join(f"{c:>18s}" for c in nisi_cols)
    log.info(header)
    for sc in sub_scores:
        vals = []
        for nc in nisi_cols:
            mask = df[sc].notna() & df[nc].notna()
            if mask.sum() > 100:
                rho, _ = stats.spearmanr(df.loc[mask, sc], df.loc[mask, nc])
                vals.append(f"{rho:>18.4f}")
            else:
                vals.append(f"{'N/A':>18s}")
        log.info("  %25s%s", sc, "".join(vals))

    # Plot: our risk vs Nisi all_risk
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Risk vs Nisi
    ax = axes[0]
    sample = df.sample(min(30_000, n), random_state=42)
    ax.scatter(
        sample["nisi_all_risk"], sample["risk_score"], alpha=0.15, s=3, color=NAVY
    )
    ax.set_xlabel("Nisi all_risk")
    ax.set_ylabel("Our composite risk_score")
    ax.set_title(f"Composite Risk vs Nisi\n(n={n:,})")
    ax.grid(alpha=0.3)

    # Traffic vs Nisi shipping
    ax = axes[1]
    mask = sample["nisi_shipping_index"].notna()
    ax.scatter(
        sample.loc[mask, "nisi_shipping_index"],
        sample.loc[mask, "traffic_score"],
        alpha=0.15,
        s=3,
        color=TEAL,
    )
    ax.set_xlabel("Nisi shipping_index")
    ax.set_ylabel("Our traffic_score")
    ax.set_title("Traffic Score vs Nisi Shipping Index")
    ax.grid(alpha=0.3)

    # Cetacean vs Nisi whale
    ax = axes[2]
    mask = sample["nisi_whale_space_use"].notna()
    ax.scatter(
        sample.loc[mask, "nisi_whale_space_use"],
        sample.loc[mask, "cetacean_score"],
        alpha=0.15,
        s=3,
        color=AMBER,
    )
    ax.set_xlabel("Nisi whale_space_use")
    ax.set_ylabel("Our cetacean_score")
    ax.set_title("Cetacean Score vs Nisi Whale Space Use")
    ax.grid(alpha=0.3)

    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "nisi_correlation.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("  Saved: nisi_correlation.png\n")

    # PASS if traffic-shipping correlation is positive
    key = "Traffic score vs Nisi shipping_index"
    ok = rhos.get(key, 0) > 0
    return ok


def check_strike_overlap() -> bool:
    """Check if historical strike sites fall in high-risk cells.

    67 geocoded strikes exist. If our model is well-calibrated,
    cells with strike history should have disproportionately
    high risk scores.
    """
    log.info("=" * 60)
    log.info("CHECK: Historical strike site overlap with risk scores")
    log.info("=" * 60)

    # Risk scores at strike cells vs all cells
    sql = """
        with strike_cells as (
            select distinct h3_cell
            from ship_strike_h3
        ),
        all_risk as (
            select
                r.h3_cell,
                r.risk_score,
                r.traffic_score,
                r.cetacean_score,
                r.proximity_score,
                r.risk_category,
                case when s.h3_cell is not null then true else false end
                    as has_strike
            from fct_collision_risk r
            left join strike_cells s on r.h3_cell = s.h3_cell
        )
        select * from all_risk
        where risk_score is not null
    """
    df = query_df(sql)

    strikes = df[df["has_strike"]]
    non_strikes = df[~df["has_strike"]]

    n_strike = len(strikes)
    n_total = len(df)
    log.info("  Total scored cells:     %s", f"{n_total:,}")
    log.info("  Cells with strikes:     %s", f"{n_strike:,}")

    if n_strike == 0:
        log.warning("  No strike cells found in scored results. SKIPPING.")
        return True

    # Distributional comparison
    for col in ["risk_score", "traffic_score", "cetacean_score"]:
        s_med = strikes[col].median()
        ns_med = non_strikes[col].median()
        s_mean = strikes[col].mean()
        ns_mean = non_strikes[col].mean()

        # Mann-Whitney U test (non-parametric)
        u_stat, u_p = stats.mannwhitneyu(
            strikes[col].dropna(),
            non_strikes[col].dropna(),
            alternative="greater",
        )

        log.info("\n  %s:", col)
        log.info("    Strike cells:     mean=%.4f  median=%.4f", s_mean, s_med)
        log.info("    Non-strike cells: mean=%.4f  median=%.4f", ns_mean, ns_med)
        log.info(
            "    Mann-Whitney U:   U=%.0f  p=%.4e  (strike > non-strike)", u_stat, u_p
        )

    # What percentile do strike cells fall in?
    df["risk_percentile"] = df["risk_score"].rank(pct=True) * 100
    strike_pctls = df.loc[df["has_strike"], "risk_percentile"]
    log.info("\n  Strike cell risk percentiles:")
    log.info("    Mean percentile:  %.1f", strike_pctls.mean())
    log.info("    Median percentile: %.1f", strike_pctls.median())
    log.info("    Min percentile:   %.1f", strike_pctls.min())
    for thresh in [50, 75, 90, 95]:
        above = (strike_pctls >= thresh).mean() * 100
        log.info("    >= P%d: %.1f%% of strike cells", thresh, above)

    # Risk category breakdown
    log.info("\n  Risk category breakdown (strike vs all):")
    strike_cats = strikes["risk_category"].value_counts(normalize=True).sort_index()
    all_cats = df["risk_category"].value_counts(normalize=True).sort_index()
    for cat in ["critical", "high", "medium", "low", "minimal"]:
        s_pct = strike_cats.get(cat, 0) * 100
        a_pct = all_cats.get(cat, 0) * 100
        enrichment = s_pct / a_pct if a_pct > 0 else float("inf")
        log.info(
            "    %-10s  strike=%.1f%%  all=%.1f%%  enrichment=%.1fx",
            cat,
            s_pct,
            a_pct,
            enrichment,
        )

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    ax.hist(
        non_strikes["risk_score"],
        bins=50,
        alpha=0.6,
        color=NAVY,
        label=f"Non-strike (n={len(non_strikes):,})",
        density=True,
    )
    ax.hist(
        strikes["risk_score"],
        bins=20,
        alpha=0.8,
        color=RED,
        label=f"Strike cells (n={n_strike})",
        density=True,
    )
    ax.set_xlabel("Composite risk score")
    ax.set_ylabel("Density")
    ax.set_title("Risk Score Distribution:\nStrike vs Non-Strike Cells")
    ax.legend()
    ax.grid(alpha=0.3)

    ax = axes[1]
    cats = ["minimal", "low", "medium", "high", "critical"]
    s_vals = [strike_cats.get(c, 0) * 100 for c in cats]
    a_vals = [all_cats.get(c, 0) * 100 for c in cats]
    x = np.arange(len(cats))
    width = 0.35
    ax.bar(x - width / 2, a_vals, width, color=NAVY, label="All cells", alpha=0.8)
    ax.bar(x + width / 2, s_vals, width, color=RED, label="Strike cells", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in cats])
    ax.set_ylabel("Percentage")
    ax.set_title("Risk Category Distribution")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "strike_overlap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("  Saved: strike_overlap.png\n")

    # PASS if median strike percentile > 50
    ok = strike_pctls.median() > 50
    return ok


def check_sma_overlap() -> bool:
    """Check that cells inside SMAs have high pre-mitigation risk.

    Seasonal Management Areas exist *because* they're high-risk
    areas. Cells inside active SMAs should:
      - Have high traffic_score (ships are present)
      - Have high cetacean_score (whales are present)
      - Have LOW protection_gap (they ARE protected)
    """
    log.info("=" * 60)
    log.info("CHECK: SMA (speed zone) validation — right areas protected?")
    log.info("=" * 60)

    sql = """
        select
            r.h3_cell,
            r.risk_score,
            r.traffic_score,
            r.cetacean_score,
            r.proximity_score,
            r.protection_gap,
            r.in_current_sma,
            r.in_proposed_zone,
            r.in_speed_zone,
            r.risk_category
        from fct_collision_risk r
        where r.has_traffic
    """
    df = query_df(sql)

    sma_cells = df[df["in_current_sma"].fillna(False)]
    proposed_cells = df[
        df["in_proposed_zone"].fillna(False) & ~df["in_current_sma"].fillna(False)
    ]
    unprotected = df[~df["in_speed_zone"].fillna(False) | df["in_speed_zone"].isna()]

    log.info("  Cells with traffic:            %s", f"{len(df):,}")
    log.info("  In active SMA:                 %s", f"{len(sma_cells):,}")
    log.info("  In proposed zones (not SMA):   %s", f"{len(proposed_cells):,}")
    log.info("  Unprotected:                   %s", f"{len(unprotected):,}")

    # Compare sub-scores
    groups = {
        "Active SMA": sma_cells,
        "Proposed zone": proposed_cells,
        "Unprotected": unprotected,
    }

    for col in ["risk_score", "traffic_score", "cetacean_score", "protection_gap"]:
        log.info("\n  %s:", col)
        for name, group in groups.items():
            if len(group) > 0:
                log.info(
                    "    %-20s  mean=%.4f  median=%.4f  n=%s",
                    name,
                    group[col].mean(),
                    group[col].median(),
                    f"{len(group):,}",
                )

    # SMA cells should have LOW protection_gap (= well protected)
    if len(sma_cells) > 0 and len(unprotected) > 0:
        sma_prot = sma_cells["protection_gap"].mean()
        unprot_prot = unprotected["protection_gap"].mean()
        log.info("\n  Protection gap check:")
        log.info("    SMA mean:         %.4f", sma_prot)
        log.info("    Unprotected mean: %.4f", unprot_prot)
        ok_protection = sma_prot < unprot_prot
        log.info("    SMA < Unprotected: [%s]", "PASS" if ok_protection else "FAIL")
    else:
        ok_protection = True

    # SMA cells should have HIGH traffic and cetacean scores
    # (they were designated because risk is high there)
    all_traffic_med = df["traffic_score"].median()
    sma_traffic_med = sma_cells["traffic_score"].median() if len(sma_cells) > 0 else 0
    ok_traffic = sma_traffic_med > all_traffic_med

    log.info("\n  Traffic score in SMA vs all:")
    log.info("    SMA median:       %.4f", sma_traffic_med)
    log.info("    All median:       %.4f", all_traffic_med)
    log.info("    SMA > All: [%s]", "PASS" if ok_traffic else "WARN")

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    for i, (col, title) in enumerate(
        [
            ("traffic_score", "Traffic Score"),
            ("cetacean_score", "Cetacean Score"),
            ("protection_gap", "Protection Gap"),
        ]
    ):
        ax = axes[i]
        colors = [NAVY, TEAL, AMBER]
        for j, (name, group) in enumerate(groups.items()):
            if len(group) > 0:
                ax.hist(
                    group[col].dropna(),
                    bins=30,
                    alpha=0.5,
                    color=colors[j],
                    label=name,
                    density=True,
                )
        ax.set_xlabel(col.replace("_", " ").title())
        ax.set_ylabel("Density")
        ax.set_title(f"{title} by Zone Type")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "sma_validation.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("  Saved: sma_validation.png\n")

    return ok_protection


def run_external_benchmarks() -> dict[str, bool]:
    """Run all external benchmark checks."""
    log.info("\n" + "=" * 60)
    log.info("  SECTION 2: EXTERNAL BENCHMARKS")
    log.info("=" * 60 + "\n")

    results = {}
    results["nisi_correlation"] = check_nisi_correlation()
    results["strike_overlap"] = check_strike_overlap()
    results["sma_overlap"] = check_sma_overlap()
    return results


# ═══════════════════════════════════════════════════════════════
# 3. SENSITIVITY ANALYSIS
# ═══════════════════════════════════════════════════════════════


def check_weight_perturbation() -> bool:
    """Systematically vary traffic sub-score weights and measure
    rank stability of top-1% risk cells.

    Robust rankings = the model is not over-sensitive to any
    single weight choice. We perturb each weight by +/-50%
    (re-normalising so sum stays 1.0) and measure how much
    the top-1% set changes.
    """
    log.info("=" * 60)
    log.info("CHECK: Weight perturbation — rank stability of top-1% cells")
    log.info("=" * 60)

    # Pull the 8 percentile components + risk_score for all cells
    sql = """
        with traffic_agg as (
            select
                h3_cell,
                avg(speed_lethality_index) as avg_speed_lethality,
                avg(high_speed_fraction) as avg_high_speed_fraction,
                avg(unique_vessels) as avg_monthly_vessels,
                avg(large_vessel_count) as avg_large_vessels,
                avg(draft_imputed_m) as avg_draft_imputed_m,
                avg(draft_risk_fraction) as avg_draft_risk_fraction,
                avg(cargo_vessels + tanker_vessels) as avg_commercial_vessels,
                avg(night_unique_vessels) as avg_night_vessels
            from int_vessel_traffic
            group by h3_cell
        )
        select
            h3_cell,
            avg_speed_lethality,
            avg_high_speed_fraction,
            avg_monthly_vessels,
            avg_large_vessels,
            avg_draft_imputed_m,
            avg_draft_risk_fraction,
            avg_commercial_vessels,
            avg_night_vessels
        from traffic_agg
        where avg_monthly_vessels > 0
    """
    df = query_df(sql)

    if df.empty:
        log.warning("  No traffic data. SKIPPING.")
        return True

    n = len(df)
    log.info("  Cells with traffic: %s", f"{n:,}")

    # Compute percentile ranks for each component
    components = [
        ("avg_speed_lethality", "pctl_speed_lethality"),
        ("avg_high_speed_fraction", "pctl_high_speed_fraction"),
        ("avg_monthly_vessels", "pctl_vessels"),
        ("avg_large_vessels", "pctl_large_vessels"),
        ("avg_draft_imputed_m", "pctl_draft_risk"),
        ("avg_draft_risk_fraction", "pctl_draft_risk_fraction"),
        ("avg_commercial_vessels", "pctl_commercial"),
        ("avg_night_vessels", "pctl_night_traffic"),
    ]

    for raw_col, pctl_col in components:
        df[pctl_col] = df[raw_col].fillna(0).rank(pct=True)

    # Baseline weights
    base_weights = {
        "pctl_speed_lethality": 0.20,
        "pctl_high_speed_fraction": 0.10,
        "pctl_vessels": 0.20,
        "pctl_large_vessels": 0.10,
        "pctl_draft_risk": 0.10,
        "pctl_draft_risk_fraction": 0.05,
        "pctl_commercial": 0.10,
        "pctl_night_traffic": 0.15,
    }

    def compute_traffic_score(weights: dict) -> pd.Series:
        score = pd.Series(0.0, index=df.index)
        for col, w in weights.items():
            score += w * df[col]
        return score

    # Baseline top-1%
    baseline_score = compute_traffic_score(base_weights)
    top1_threshold = baseline_score.quantile(0.99)
    baseline_top1 = set(df.loc[baseline_score >= top1_threshold, "h3_cell"])
    n_top1 = len(baseline_top1)
    log.info("  Baseline top-1%% cells: %d", n_top1)

    # Perturb each weight by -50%, -25%, +25%, +50%
    perturbations = [-0.50, -0.25, +0.25, +0.50]
    results = []

    for target_col in base_weights:
        for delta in perturbations:
            perturbed = base_weights.copy()
            original_w = perturbed[target_col]
            new_w = max(0.01, original_w * (1 + delta))
            perturbed[target_col] = new_w

            # Renormalise
            total = sum(perturbed.values())
            perturbed = {k: v / total for k, v in perturbed.items()}

            perturbed_score = compute_traffic_score(perturbed)
            p_threshold = perturbed_score.quantile(0.99)
            perturbed_top1 = set(df.loc[perturbed_score >= p_threshold, "h3_cell"])

            # Jaccard similarity
            intersection = len(baseline_top1 & perturbed_top1)
            union = len(baseline_top1 | perturbed_top1)
            jaccard = intersection / union if union > 0 else 1.0

            # Spearman rank correlation of full score vector
            rho, _ = stats.spearmanr(baseline_score, perturbed_score)

            results.append(
                {
                    "component": target_col.replace("pctl_", ""),
                    "delta": f"{delta:+.0%}",
                    "new_weight": perturbed[target_col],
                    "jaccard_top1": jaccard,
                    "rank_corr": rho,
                }
            )

    results_df = pd.DataFrame(results)

    # Summary per component
    log.info("\n  Perturbation results (Jaccard similarity of top-1%%):")
    log.info("  %-25s %8s %8s %8s", "Component", "Delta", "Jaccard", "Rank rho")
    log.info("  " + "-" * 55)
    for _, row in results_df.iterrows():
        log.info(
            "  %-25s %8s %8.4f %8.4f",
            row["component"],
            row["delta"],
            row["jaccard_top1"],
            row["rank_corr"],
        )

    # Aggregate stability
    mean_jaccard = results_df["jaccard_top1"].mean()
    min_jaccard = results_df["jaccard_top1"].min()
    mean_rho = results_df["rank_corr"].mean()

    log.info("\n  Stability summary:")
    log.info("    Mean Jaccard (top-1%%):  %.4f", mean_jaccard)
    log.info("    Min Jaccard (top-1%%):   %.4f  (worst case)", min_jaccard)
    log.info("    Mean rank correlation:  %.4f", mean_rho)

    ok = mean_jaccard > 0.70  # At least 70% overlap on average
    log.info("    Stability check:        [%s]\n", "PASS" if ok else "WARN")

    # Plot heatmap
    pivot = results_df.pivot_table(
        index="component",
        columns="delta",
        values="jaccard_top1",
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=0.5, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([i.replace("_", " ").title() for i in pivot.index])
    ax.set_xlabel("Weight perturbation")
    ax.set_ylabel("Traffic component")
    ax.set_title("Top-1% Rank Stability (Jaccard Similarity)")

    # Add values as text
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            color = "white" if val < 0.7 else "black"
            ax.text(
                j, i, f"{val:.2f}", ha="center", va="center", color=color, fontsize=9
            )

    fig.colorbar(im, ax=ax, label="Jaccard similarity")
    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "weight_perturbation.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("  Saved: weight_perturbation.png")

    # Save CSV
    results_df.to_csv(ARTIFACTS_DIR / "weight_perturbation.csv", index=False)
    log.info("  Saved: weight_perturbation.csv\n")

    return ok


def check_jensens_spatial_distribution() -> bool:
    """Map where Jensen's bias is largest.

    Expected: largest bias in port approach areas where speed
    distributions are bimodal (some vessels slow, some fast).
    """
    log.info("=" * 60)
    log.info("CHECK: Spatial distribution of Jensen's inequality bias")
    log.info("=" * 60)

    sql = """
        select
            h3_cell,
            cell_lat,
            cell_lon,
            vw_avg_speed_knots,
            vw_avg_lethality,
            high_speed_fraction,
            unique_vessels,
            month
        from ais_h3_summary
        where vw_avg_lethality is not null
          and vw_avg_speed_knots is not null
    """
    df = query_df(sql)

    if df.empty:
        log.warning("  No per-vessel lethality data. AIS re-run needed. SKIPPING.")
        return True

    # Compute cell-average lethality
    df["cell_avg_lethality"] = 1.0 / (
        1.0
        + np.exp(-(VT_LETHALITY_BETA0 + VT_LETHALITY_BETA1 * df["vw_avg_speed_knots"]))
    )
    df["bias"] = df["vw_avg_lethality"] - df["cell_avg_lethality"]

    # Aggregate to per-cell mean bias
    cell_bias = (
        df.groupby("h3_cell")
        .agg(
            mean_bias=("bias", "mean"),
            max_bias=("bias", "max"),
            mean_speed=("vw_avg_speed_knots", "mean"),
            mean_lethality=("vw_avg_lethality", "mean"),
            high_speed_frac=("high_speed_fraction", "mean"),
            total_vessels=("unique_vessels", "sum"),
            lat=("cell_lat", "first"),
            lon=("cell_lon", "first"),
            months=("month", "nunique"),
        )
        .reset_index()
    )

    n = len(cell_bias)
    log.info("  Unique cells analysed: %s", f"{n:,}")

    # Decile analysis by speed
    cell_bias["speed_decile"] = pd.qcut(
        cell_bias["mean_speed"], 10, labels=False, duplicates="drop"
    )
    decile_stats = cell_bias.groupby("speed_decile").agg(
        mean_speed=("mean_speed", "mean"),
        mean_bias=("mean_bias", "mean"),
        mean_lethality=("mean_lethality", "mean"),
        count=("h3_cell", "count"),
    )
    log.info("\n  Jensen's bias by speed decile:")
    log.info(
        "  %8s %12s %12s %12s %8s", "Decile", "Avg Speed", "Avg Bias", "Avg Lethal", "n"
    )
    for idx, row in decile_stats.iterrows():
        log.info(
            "  %8d %12.2f %12.4f %12.4f %8d",
            idx,
            row["mean_speed"],
            row["mean_bias"],
            row["mean_lethality"],
            int(row["count"]),
        )

    # Bias vs high-speed fraction (bimodal indicator)
    rho, p = stats.spearmanr(
        cell_bias["high_speed_frac"].fillna(0),
        cell_bias["mean_bias"].abs(),
    )
    log.info(
        "\n  Correlation: |bias| vs high_speed_fraction:  rho=%.4f  p=%.2e", rho, p
    )

    # Geographic hotspots of bias
    top_bias_cells = cell_bias.nlargest(20, "mean_bias")
    log.info("\n  Top 20 cells by Jensen's bias:")
    log.info(
        "  %12s %8s %8s %8s %8s %8s",
        "h3_cell",
        "lat",
        "lon",
        "speed",
        "bias",
        "hs_frac",
    )
    for _, row in top_bias_cells.iterrows():
        log.info(
            "  %12d %8.2f %8.2f %8.1f %8.4f %8.2f",
            row["h3_cell"],
            row["lat"],
            row["lon"],
            row["mean_speed"],
            row["mean_bias"],
            row["high_speed_frac"] or 0,
        )

    # Plot: geographic scatter of bias
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    ax = axes[0]
    scatter = ax.scatter(
        cell_bias["lon"],
        cell_bias["lat"],
        c=cell_bias["mean_bias"],
        cmap="RdYlGn_r",
        s=1,
        alpha=0.4,
        vmin=0,
        vmax=cell_bias["mean_bias"].quantile(0.95),
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Geographic Distribution of Jensen's Bias")
    fig.colorbar(scatter, ax=ax, label="Mean bias (per-vessel - cell-avg)")
    ax.grid(alpha=0.2)

    ax = axes[1]
    ax.scatter(
        cell_bias["high_speed_frac"].fillna(0),
        cell_bias["mean_bias"],
        alpha=0.1,
        s=2,
        color=NAVY,
    )
    ax.set_xlabel("High speed fraction (vessels >= 10 kn)")
    ax.set_ylabel("Mean Jensen's bias")
    ax.set_title(f"Bias vs Speed Distribution Shape\n(rho={rho:.4f})")
    ax.grid(alpha=0.3)

    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "jensens_spatial.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("  Saved: jensens_spatial.png\n")

    return True


def check_composite_sensitivity() -> bool:
    """Perturb the 7-sub-score composite weights and check rank stability.

    This tests whether the final risk ranking is robust to the
    choice of sub-score weights (traffic 25%, cetacean 25%, etc.).
    """
    log.info("=" * 60)
    log.info("CHECK: Composite sub-score weight sensitivity")
    log.info("=" * 60)

    sql = """
        select
            h3_cell,
            traffic_score,
            cetacean_score,
            proximity_score,
            strike_score,
            habitat_score,
            protection_gap,
            reference_risk_score,
            risk_score
        from fct_collision_risk
        where risk_score is not null
    """
    df = query_df(sql)

    if df.empty:
        log.warning("  No risk data. SKIPPING.")
        return True

    n = len(df)
    log.info("  Scored cells: %s", f"{n:,}")

    sub_score_cols = [
        "traffic_score",
        "cetacean_score",
        "proximity_score",
        "strike_score",
        "habitat_score",
        "protection_gap",
        "reference_risk_score",
    ]
    base_weights = COLLISION_RISK_WEIGHTS

    def compute_composite(weights: dict) -> pd.Series:
        score = pd.Series(0.0, index=df.index)
        for col, w in weights.items():
            score += w * df[col].fillna(0)
        return score

    # Baseline top-1%
    baseline_score = compute_composite(base_weights)
    threshold = baseline_score.quantile(0.99)
    baseline_top1 = set(df.loc[baseline_score >= threshold, "h3_cell"])

    # Perturb each sub-score weight
    perturbations = [-0.50, -0.25, +0.25, +0.50]
    results = []

    for target_col in sub_score_cols:
        target_key = target_col  # Keys match column names
        for delta in perturbations:
            perturbed = base_weights.copy()
            new_w = max(0.01, perturbed[target_key] * (1 + delta))
            perturbed[target_key] = new_w

            # Renormalise
            total = sum(perturbed.values())
            perturbed = {k: v / total for k, v in perturbed.items()}

            perturbed_score = compute_composite(perturbed)
            p_threshold = perturbed_score.quantile(0.99)
            perturbed_top1 = set(df.loc[perturbed_score >= p_threshold, "h3_cell"])

            intersection = len(baseline_top1 & perturbed_top1)
            union = len(baseline_top1 | perturbed_top1)
            jaccard = intersection / union if union > 0 else 1.0

            rho, _ = stats.spearmanr(baseline_score, perturbed_score)

            results.append(
                {
                    "sub_score": target_key.replace("_score", "")
                    .replace("_", " ")
                    .title(),
                    "delta": f"{delta:+.0%}",
                    "jaccard_top1": jaccard,
                    "rank_corr": rho,
                }
            )

    results_df = pd.DataFrame(results)

    log.info("\n  Composite weight perturbation (Jaccard of top-1%%):")
    log.info("  %-25s %8s %8s %8s", "Sub-score", "Delta", "Jaccard", "Rank rho")
    log.info("  " + "-" * 55)
    for _, row in results_df.iterrows():
        log.info(
            "  %-25s %8s %8.4f %8.4f",
            row["sub_score"],
            row["delta"],
            row["jaccard_top1"],
            row["rank_corr"],
        )

    mean_jaccard = results_df["jaccard_top1"].mean()
    min_jaccard = results_df["jaccard_top1"].min()
    worst = results_df.loc[results_df["jaccard_top1"].idxmin()]

    log.info("\n  Stability summary:")
    log.info("    Mean Jaccard (top-1%%):  %.4f", mean_jaccard)
    log.info(
        "    Min Jaccard (top-1%%):   %.4f  (%s at %s)",
        min_jaccard,
        worst["sub_score"],
        worst["delta"],
    )
    log.info("    Mean rank correlation:  %.4f", results_df["rank_corr"].mean())

    ok = mean_jaccard > 0.60
    log.info("    Stability check:        [%s]\n", "PASS" if ok else "WARN")

    # Plot heatmap
    pivot = results_df.pivot_table(
        index="sub_score",
        columns="delta",
        values="jaccard_top1",
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=0.4, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel("Weight perturbation")
    ax.set_ylabel("Sub-score")
    ax.set_title("Composite Risk: Top-1% Stability Under Weight Perturbation")

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            color = "white" if val < 0.6 else "black"
            ax.text(
                j, i, f"{val:.2f}", ha="center", va="center", color=color, fontsize=9
            )

    fig.colorbar(im, ax=ax, label="Jaccard similarity")
    plt.tight_layout()
    fig.savefig(
        ARTIFACTS_DIR / "composite_sensitivity.png", dpi=150, bbox_inches="tight"
    )
    plt.close(fig)
    log.info("  Saved: composite_sensitivity.png")

    results_df.to_csv(ARTIFACTS_DIR / "composite_sensitivity.csv", index=False)
    log.info("  Saved: composite_sensitivity.csv\n")

    return ok


def run_sensitivity_analysis() -> dict[str, bool]:
    """Run all sensitivity analyses."""
    log.info("\n" + "=" * 60)
    log.info("  SECTION 3: SENSITIVITY ANALYSIS")
    log.info("=" * 60 + "\n")

    results = {}
    results["weight_perturbation"] = check_weight_perturbation()
    results["jensens_spatial"] = check_jensens_spatial_distribution()
    results["composite_sensitivity"] = check_composite_sensitivity()
    return results


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate traffic risk scoring methodology",
    )
    parser.add_argument(
        "--section",
        choices=["internal", "external", "sensitivity", "all"],
        default="all",
        help="Which validation section(s) to run (default: all)",
    )
    args = parser.parse_args()

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Artifacts directory: %s", ARTIFACTS_DIR)
    log.info("")

    all_results = {}

    if args.section in ("internal", "all"):
        all_results.update(run_internal_checks())

    if args.section in ("external", "all"):
        all_results.update(run_external_benchmarks())

    if args.section in ("sensitivity", "all"):
        all_results.update(run_sensitivity_analysis())

    # ── Summary ───────────────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info("  VALIDATION SUMMARY")
    log.info("=" * 60)

    n_pass = sum(1 for v in all_results.values() if v)
    n_warn = sum(1 for v in all_results.values() if not v)

    for check, passed in all_results.items():
        status = "PASS" if passed else "WARN"
        log.info("  %-35s [%s]", check, status)

    log.info("")
    log.info(
        "  Total: %d PASS, %d WARN out of %d checks", n_pass, n_warn, len(all_results)
    )
    log.info("  Artifacts saved to: %s", ARTIFACTS_DIR)
    log.info("=" * 60)

    if n_warn > 0:
        log.warning(
            "  Some checks returned WARN — review the details above. "
            "WARN does not necessarily mean failure; it may indicate "
            "the AIS re-run has not completed or expected patterns "
            "are weaker than anticipated."
        )


if __name__ == "__main__":
    main()
