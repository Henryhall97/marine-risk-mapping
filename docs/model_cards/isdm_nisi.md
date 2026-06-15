# Model Card — ISDM Per-Species SDM (Nisi et al. data)

> **Output type:** relative occurrence probability / habitat suitability (0–1).
> **NOT density, NOT abundance.** See [README](README.md).

| Field | Value |
|---|---|
| Model id | `isdm_species_sdm` (MLflow experiment) |
| Algorithm | XGBoost gradient-boosted trees, `binary:logistic` |
| Training script | `pipeline/analysis/train_isdm_model.py` |
| Training data | Nisi et al. (2024) integrated SDM presence/absence CSVs |
| Species | blue, fin, humpback, sperm whale (4 — Nisi coverage) |
| Output | `ml_whale_predictions` (scored onto H3 grid × season) |

## 1. Data
Expert-curated, pre-balanced (~50/50) presence/absence points from the Nisi
et al. integrated SDM dataset, one model per species. This is a higher-quality
label source than OBIS opportunistic sightings but covers only 4 species.

## 2. Covariates
7 environmental covariates, mapped from Nisi's names to ours:

| Nisi | Ours |
|---|---|
| `sst` | `sst` |
| `sst_sd` | `sst_sd` |
| `mld` | `mld` |
| `sla` | `sla` |
| `PPupper200m` | `pp_upper_200m` |
| `bathy` | `depth_m` |
| `bathy_sd` | `depth_range_m` |

Purely environmental — no traffic, proximity, or policy features.

## 3. Cross-validation
5-fold CV with early stopping (`EARLY_STOPPING_ROUNDS = 50`). When scoring the
H3 grid, a small fraction (~0.8%) of deep-ocean/edge cells lack Copernicus
ocean covariates and are median-filled at scoring time (logged as a warning).

## 4. Assumptions
- The Nisi presence/absence design is representative of species' realised
  niche over its spatial footprint.
- Environmental covariates transfer from the Nisi training extent to the full
  H3 scoring grid (extrapolation beyond the training envelope is a risk —
  envelope flag is a Phase 1 deliverable).

## 5. Biases & limitations
- **Coverage gap:** only 4 species; right whale and minke are SDM-only
  (no ISDM). Rice's whale and gray whale are absent entirely (Phase 1b item G
  adds them to the species set).
- **Ensemble NULL-deflation bug (Phase 1b item A):** where ISDM coverage is
  narrower than SDM, the current ML-mart ensemble treats a missing ISDM value
  as zero and still divides by two, halving P(whale) for coverage (not
  biological) reasons. Fix is an early Phase 1b deliverable.
- **Flat 50/50 ISDM:SDM ensemble weight** lacks justification; skill-weighting
  or a sensitivity test is planned (Phase 1b item D).
- Relative suitability ranking, **not** density or calibrated probability.

## 6. Intended use
Primary expert-informed whale-suitability signal in the ML-enhanced risk mart;
ensembled with the OBIS SDM for shared species. Same use boundaries as the
other SDM cards — no density/abundance inference.
