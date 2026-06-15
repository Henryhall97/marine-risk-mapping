# Model Cards

Model cards for every species-distribution model (SDM/ISDM) in the Marine
Risk Mapping platform, written against the **IWC model-based estimation
checklist** (Miller & Kelly 2023, SC/69A/ASI/20). Each card answers the same
six questions so reviewers can assess fitness-for-purpose at a glance:

| # | Section | What it documents |
|---|---|---|
| 1 | **Data** | Training data source, sampling design, response variable |
| 2 | **Covariates** | Predictors used (and which were deliberately excluded, and why) |
| 3 | **Cross-validation** | How predictive skill was estimated (spatial blocking) |
| 4 | **Assumptions** | Statistical and ecological assumptions the model relies on |
| 5 | **Biases & limitations** | Known biases, extrapolation risk, what the output is NOT |
| 6 | **Intended use** | What the output may and may not be used for |

## Critical labelling note (IWC SDM guidance)

All SDM/ISDM outputs are **relative occurrence probability / habitat
suitability** on a 0–1 scale. They are a *relative ranking* of where a
species is more or less likely to occur. **They are NOT density (animals
per km²) and NOT abundance (population totals).** Absolute density with
error bars is a separate, effort-corrected product (distance-sampling DSM,
planned Phase 3) and must never be inferred from these suitability surfaces.

## Cards

| Card | Model | Backend |
|---|---|---|
| [whale_sdm_static.md](whale_sdm_static.md) | Static whale SDM (any-cetacean) | XGBoost |
| [whale_sdm_seasonal.md](whale_sdm_seasonal.md) | Seasonal per-species SDM | XGBoost |
| [isdm_nisi.md](isdm_nisi.md) | ISDM per-species (Nisi et al. data) | XGBoost |
| [traffic_lethality_layers.md](traffic_lethality_layers.md) | Speed-lethality + draft-risk modular layers | dbt / SQL |

## Terminology crosswalk

The machine-readable mapping of our internal terms to the IWC standard
vocabulary lives in `transform/seeds/iwc_crosswalk.csv` and is served at
`GET /api/v1/species/iwc-crosswalk`.
