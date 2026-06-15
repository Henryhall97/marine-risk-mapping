# Model Card — Static Whale SDM (any-cetacean)

> **Output type:** relative occurrence probability / habitat suitability (0–1).
> **NOT density, NOT abundance.** See [README](README.md).

| Field | Value |
|---|---|
| Model id | `whale_sdm` (MLflow experiment) |
| Algorithm | XGBoost gradient-boosted trees, `binary:logistic` |
| Training script | `pipeline/analysis/train_sdm_model.py` |
| Feature matrix | `fct_whale_sdm_training` → `whale_sdm_features.parquet` (~1.8M H3 cells) |
| Grain | One row per H3 res-7 cell (static, non-seasonal) |
| Response | `whale_present` (any cetacean sighting in the cell, binary) |

## 1. Data
Presence/background derived from OBIS opportunistic cetacean sightings
assigned to H3 res-7 cells across the study area (2°S–52°N, 180°W–59°W).
Presence = cell with ≥1 sighting; background = the remaining grid. This is
**presence-background**, not designed-survey distance-sampling data.

## 2. Covariates
47 environmental/contextual features (bathymetry depth + range, ocean
covariates SST/MLD/SLA/PP, derived terrain). **Deliberately excluded**
(see `NON_FEATURE_COLS` in the training script):
- **Traffic features** — survey effort correlates with shipping lanes
  (detection bias).
- **Whale proximity** — target leakage.
- **Nisi reference risk** — a model output, not independent data (reserved
  for validation).
- **Speed zones / MPA / protection** — policy placements, circular for an SDM.

## 3. Cross-validation
Spatial block CV: H3 res-2 parent cells (~158 km blocks) distributed across
5 folds (`evaluate.py:spatial_cv_split`). Spatial blocking prevents
optimistic skill estimates from spatial autocorrelation between adjacent
train/test cells.

> **Known limitation (Phase 1b item E):** the 158 km block size is fixed, not
> derived from the residual autocorrelation range. Phase 1 adds variogram
> diagnostics to set it empirically.

## 4. Assumptions
- Environmental covariates are informative proxies for habitat preference.
- Background cells approximate the available environment (presence-background
  assumption).
- Sightings reflect occurrence (modulated by effort — see biases).

## 5. Biases & limitations
- **OBIS effort bias:** sightings cluster near ports, coastlines and survey
  transects. Feature exclusion removes traffic predictors but cannot remove
  "where people looked". Target-group background + spatial thinning are
  planned (Phase 1b item C).
- **Probability scale:** `scale_pos_weight` is used for class imbalance, which
  inflates predicted probabilities (good for ranking/AUC, not calibrated).
  Calibration is planned (Phase 1b item B).
- **No uncertainty surface yet:** point predictions only; bootstrap-ensemble
  spread is a Phase 1 deliverable.
- **No extrapolation flag yet:** MESS/ExDet envelope flag is a Phase 1
  deliverable.
- The output is a **relative suitability ranking**, not a probability of a
  fixed event and not a density.

## 6. Intended use
Coast-wide **relative screening** of likely whale habitat to feed the
composite collision-risk index (Product A). Appropriate for ranking and
prioritisation. **Not** appropriate for: estimating animal counts, computing
absolute collision numbers, or any use requiring calibrated probabilities or
density (use the Phase 3 DSM density product instead).
