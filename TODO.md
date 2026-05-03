# TODO — Marine Risk Mapping

> Centralised tracking for open improvements, technical debt, and
> future enhancements.  Reference inline `TODO:` comments back to
> entries in this file.

---

## Scoring & Risk Model

- [ ] **Species-vulnerability-weighted whale composite** — The ML mart's
  `any_whale_prob = 1 − ∏(1 − Pᵢ)` treats all 4 ISDM species equally.
  A right whale encounter (population ~350) is far more consequential
  than a sperm whale encounter (~800 000).  Replace with a vulnerability-
  weighted composite: `P_weighted = Σ wᵢ · Pᵢ`, where `wᵢ` reflects
  IUCN status, population size, or strike mortality rate.  Affects
  `int_ml_whale_predictions.sql` and `fct_collision_risk_ml.sql`.
  *(Added: 2026-03-03)*

- [ ] **Revisit habitat ocean weight (currently 80/20)** — ISDM feature
  importance shows PP ranks 5th–6th (9–13 %) across all 4 species.
  SST and MLD are stronger but species-directional (can't percentile-
  rank in a species-agnostic score).  The 20 % PP weight is defensible
  but should be re-evaluated when species-weighted habitat scoring or
  ML mart promotion is considered.
  *(Added: 2026-03-03, inline: dbt_project.yml, sub_scores.sql)*

- [ ] **Incremental AIS append mode** — Currently `--force` re-downloads
  and re-aggregates all AIS data from scratch (365 × 3.1 B pings).
  When adding a new year (e.g. 2025 on top of 2024), this is wasteful.
  Consider an `--append` mode that downloads only new daily files,
  aggregates only the new month-files in DuckDB, and INSERTs into
  `ais_h3_summary` instead of DROP + CREATE.  Would need a
  `loaded_through` watermark column or file-level tracking.
  *(Added: 2026-03-05)*

## Data Quality

- [ ] **49 % missing ocean covariates in grid scoring** — When ISDM
  models score the full H3 grid (7.3 M rows), ~49 % of cells lack
  Copernicus data (deep ocean / edge cells).  Filled with median
  values.  Investigate Copernicus higher-res products or spatial
  interpolation to improve coverage.

## Infrastructure & DevOps

- [x] **Add missing dbt tests** — 186 data tests across all staging,
  intermediate, and mart models.  Fixed `fct_species_risk` uniqueness
  grain (`species` not `species_group`), removed spurious
  `nisi_all_risk` not-null test (71 909 legitimate nulls).  All passing.
  *(Sprint item 5 — completed 2026-03-03)*

- [x] **Core unit tests** — 128 pytest tests across 6 modules (1 524
  lines): config, utils, audio, analysis, aggregation, validation.
  Source bug fixed in `quality_report.py` (pandas 2.3 compat).
  *(Sprint item 8 — completed 2026-03-03)*

- [x] **Clean up pyproject.toml deps** — Removed lightgbm, organised
  deps into 7 groups, added pytest + pytest-cov to dev group.
  *(Sprint item 7 — completed 2026-03-03)*

## Documentation

- [x] **Update copilot-instructions.md** — Reflected all changes from
  the pre-Phase-8 cleanup sprint: tests section, repo structure,
  testing checklist, known pitfalls.
  *(Sprint item 6 — completed 2026-03-03)*

## Future Phases

- [ ] **Forecast ocean covariates & predicted whale presence** — Extend the
  Copernicus ocean covariate pipeline to forecast SST, MLD, SLA, and PP
  into the future (e.g. seasonal forecasts from Copernicus Marine Service
  or NOAA CFS).  Feed forecasted covariates through the trained ISDM / SDM
  models to produce forward-looking whale probability maps.  Add a
  "Forecast" view in the frontend (time-slider or future season selector)
  so users can see predicted whale presence weeks/months ahead — enabling
  proactive route planning and dynamic speed zone recommendations.
  *(Added: 2026-03-07)*

- [ ] **Species audit — Pacific vs Atlantic right whale collapse** — Review
  all species handling across the pipeline.  Currently OBIS sightings for
  both *Eubalaena glacialis* (North Atlantic right whale) and *Eubalaena
  japonica* (North Pacific right whale) are collapsed into a single
  `right_whale` category, and Happywhale's `southern_right_whale`
  (*Eubalaena australis*) is also mapped to `right_whale` via label fixes.
  These are three distinct species with very different populations
  (~350 NARW vs ~500 NPRW vs ~15 000 SRW), ranges, and conservation
  statuses (NARW critically endangered, NPRW endangered, SRW least
  concern).  Audit the `species_crosswalk` seed for other silent
  collapses (e.g. Bryde's whale complex, spinner vs spotted dolphin in
  OBIS).  Document all species-level decisions and consider whether
  the vulnerability-weighted composite (TODO above) needs per-population
  weights rather than per-species.
  *(Added: 2026-03-07)*


- [ ] **Phase 10** — Testing (pytest, Vitest, E2E)
- [ ] **Phase 11** — Containerisation (Dockerfiles, CI/CD)
- [ ] **Phase 12** — Cloud Deployment (AWS ECS, RDS, S3)
