# Model Card — Traffic Lethality Layers (modular, toggleable)

> Component layers of the traffic sub-score, exposed individually so reviewers
> can inspect each strike-risk driver in isolation. See [README](README.md).

The platform separates **exposure** (how much vessel traffic / co-occurrence
exists) from **conditional lethality** (given a strike, how likely it is to be
fatal). The two lethality drivers below are surfaced as independent,
toggleable map layers (`TrafficMetric` toggles in the frontend `Sidebar`) so
their contribution is transparent and not buried inside the composite score.

## Speed-lethality layer (`speed_lethality`)

| Field | Value |
|---|---|
| IWC term | `Pleth` (probability of lethal strike) |
| Our field | `avg_speed_lethality` (macro) / V&T logistic in `int_vessel_traffic` |
| Definition | Probability that a strike at the cell's speed distribution is lethal |
| Source model | Vanderlaan & Taggart (2007) logistic, `vt_lethality_beta0/beta1` |
| Frontend toggle | Sidebar → Traffic Density → "Speed Lethality" |
| Range | 0–1 |

**Note (IWC feedback, R. Leaper):** the V&T 2007 curve is the current
implementation. The newer Garrison et al. (2025) `Pleth` formulation, and the
finding that *speed-derived risk can exceed the lethality term itself*, are
tracked for the Phase 2 VTD rewrite. This layer is a **relative lethality
ranking**, not a calibrated per-encounter fatality probability.

## Draft-risk layer (`draft_risk`)

| Field | Value |
|---|---|
| IWC term | `Pstrikedepth` (depth-overlap component of strike probability) |
| Our field | `avg_draft_risk_fraction` (macro) / `draft_risk_fraction` |
| Definition | Fraction of transits with draft > 8 m (deep-draft vessels) |
| Frontend toggle | Sidebar → Traffic Density → "Draft Risk" |
| Range | 0–1 |

Deep-draft vessels (cargo, tankers) are less manoeuvrable and their hull/
propeller occupies more of the water column a whale uses, raising the chance
that an encounter results in a strike. This is a **proxy** for depth-overlap
strike probability, not a measured `Pstrikedepth`.

## Why modular

Keeping these as separate layers (rather than only inside the composite risk
score) means a reviewer can:
- verify each lethality driver against the literature independently;
- see *where* speed vs depth dominates the risk picture;
- swap in an updated lethality curve (e.g. Garrison et al. 2025) without
  disturbing the exposure layers.

This mirrors the IWC standard's separation of **exposure** and **conditional
mortality** terms, and is a prerequisite for the Phase 2 vessel-traffic-density
(VTD) rebuild.
