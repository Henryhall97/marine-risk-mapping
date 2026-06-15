# Model Card — Seasonal Per-Species Whale SDM

> **Output type:** relative occurrence probability / habitat suitability (0–1).
> **NOT density, NOT abundance.** See [README](README.md).

| Field | Value |
|---|---|
| Model id | `whale_sdm_seasonal` (MLflow experiment) |
| Algorithm | XGBoost gradient-boosted trees, `binary:logistic` |
| Training script | `pipeline/analysis/train_sdm_seasonal.py` |
| Feature matrix | `fct_whale_sdm_seasonal` → `whale_sdm_seasonal_features.parquet` (~7.3M rows) |
| Grain | `(h3_cell, season)` — 4 seasons × 1.8M cells |
| Response (`--target`) | `any_cetacean` (default) or per-species: right / humpback / fin / blue / sperm / minke whale presence |

## 1. Data
Same OBIS presence-background source as the static SDM, but split by season
(winter/spring/summer/fall) using each sighting's event-date month. Per-species
targets use the `species_crosswalk` seed to label presence.

## 2. Covariates
Seasonal environmental covariates (season-varying SST/MLD/SLA/PP) plus static
bathymetry. **Deliberately excluded:**
- **Traffic features** — detection bias (survey effort ∝ shipping lanes).
- **Whale proximity** — target leakage.
- **Nisi per-species risk** — reserved for validation.

## 3. Cross-validation
Spatial block CV at H3 res-2 (5 folds). For seasonal data, **all 4 seasons of a
given cell always land in the same fold** (spatial grouping, not temporal), so
seasonal replicates of one location cannot leak across train/test.

## 4. Assumptions
- Seasonality in occurrence is captured by season-varying ocean covariates.
- Per-species presence labels are reliable where the crosswalk resolves them;
  genus/family-level OBIS records are mapped conservatively.

## 5. Biases & limitations
- **Sparse seasons for rare species:** some species×season combinations have
  few presences, widening uncertainty (uncertainty surface is a Phase 1
  deliverable).
- Inherits the OBIS effort bias and uncalibrated-probability caveats of the
  static SDM (Phase 1b items B, C).
- `any_whale_prob` composites (where used downstream) assume species
  independence and therefore **overestimate** P(any whale) — documented
  simplification (Phase 1b item F).
- Relative suitability ranking, **not** density or calibrated probability.

## 6. Intended use
Season-resolved relative habitat screening; feeds the seasonal and ML risk
marts. Same use boundaries as the static SDM card.
