# Survey-Data Sourcing — Acquisition Status

> **Workstream:** IWC migration — survey-data SOURCING (runs in PARALLEL with Tranche 1,
> gates Phase 3). See `/memories/repo/context.md` and `/memories/repo/iwc-migration-plan.md`
> ("Survey datasets to source", "PARALLEL WORKSTREAM", "Survey-data acquisition gate").
>
> **This is a research / data-hunt tracker, not modelling code.** No DSM code is written
> here. The deliverable is the per-program GO / GO-caveated / NO-GO table below, kept
> current as each program is vetted.
>
> **Primary goal:** clear **NARW US-Atlantic to GO before Tranche 1 ends** so Phase 3 can
> start with no stall. Other programs continue sourcing in the background.
>
> **Last updated:** 2026-06-15

---

## 1. Why this exists

Phase 3 (R `dsm`/`mrds`/`Distance` density engine) turns whale observations into
**absolute density (animals/km²) with error bars**. A density-surface model is only
valid where it has *designed-survey* data — on-effort tracklines with perpendicular
distances, group sizes, and (ideally) the metadata to correct for animals missed on or
near the trackline (g(0)). Opportunistic / presence-only data (OBIS, NARWC sightings)
**cannot** anchor absolute density; they re-import effort bias.

Per the locked plan, **R DSM is the primary density product** and the **Roberts et al. /
Duke habitat-based density models are an independent VALIDATION benchmark only** (US
Atlantic + Gulf), not the primary source. So for each survey program we must establish:
*does its raw distance-sampling data exist, in reusable form, and what does it satisfy?*

---

## 2. Acquisition-gate checklist (decision 5)

Each program is scored against six items. Items 1–3 are **HARD** (a DSM cannot be fitted
without them); items 4–5 are **SOFT** (enable g(0) correction; their absence only
caveats the result); item 6 is normally already satisfied in our PostGIS covariate grid.

| # | Item | Hardness | What it buys |
|---|---|---|---|
| 1 | **Perpendicular distances** (or bearing+range / angle+reticle to derive) | HARD | Detection function → effective strip width |
| 2 | **Effort / tracklines** (on-effort segment geometry + length) | HARD | Segmentable effort + area offset |
| 3 | **Group size per detection** | HARD (fallback: mean E[s]) | Group→individual density |
| 4 | **Double-platform / independent observer** (perception g(0), MRDS) | SOFT | Corrects whales missed *on* the line |
| 5 | **Dive-tag / TDR time-at-depth** (availability g(0) + `whale_dive_cdf`) | SOFT | Corrects deep divers missed *underwater* |
| 6 | **Env covariate coverage** over footprint (SST/MLD/SLA/PP/depth) | (in PostGIS) | GAM predictors |

**Decision rule per program/species:**

- **GO (full DSM):** items 1–3 **and** (4 **or** 5) → g(0)-corrected DSM.
- **GO (caveated):** items 1–3 only, no g(0) data → DSM with **g(0)=1 documented**,
  divers flagged biased-low.
- **NO-GO:** any of 1–3 missing → no Phase-3 surface; that region/species stays
  **Product-A screening only** and emits **no R/N/I**.

> Item 5 (dive data) is intentionally **single-sourced in Phase 3** as `whale_dive_cdf.csv`
> and reused by Phase 4 (Pstrikedepth) and Phase 5b (availability uncertainty). It is
> *per-species*, not per-program — a program clears item 5 if published dive-tag/TDR
> time-at-depth exists for its species, regardless of who flew the survey.

---

## 3. Per-program status table (the deliverable)

Priority order is NARW-first, then GoM (Rice's whale), then Pacific/Alaska/Hawaii.
Items: ✓ satisfied · ◐ partial/caveated · ✗ missing · — n/a.

| # | Program | Region | Primary target species | 1 Perp. dist | 2 Effort | 3 Group | 4 g(0) dbl-plat | 5 Dive g(0) | 6 Covar | **Verdict** | Access route |
|---|---------|--------|------------------------|:---:|:---:|:---:|:---:|:---:|:---:|---|---|
| 1 | **AMAPPS** (NEFSC+SEFSC ship+aerial) | US Atlantic shelf+slope | NARW, fin, humpback, sei, sperm, minke | ✓ | ✓ | ✓ | ✓ | ◐ (per-spp pub.) | ✓ | **GO (full DSM)** | OBIS-SEAMAP + NOAA InPort; detailed distance/effort via direct **NEFSC/SEFSC request**; Palka et al. reports |
| 2 | **NARWSS** (NEFSC aerial sighting survey) | US NE / Mid-Atlantic | North Atlantic right whale | ◐ | ✓ | ✓ | ◐ | ◐ | ✓ | **GO-caveated** (pool into NARW DSM; not standalone) | NEFSC (Cole/Khan); feeds Roberts NARW model + NARWC |
| 3 | **NARWC** sightings DB | US+CAN Atlantic | NARW (+ other large whales) | ✗ | ◐ | ✓ | — | — | ✓ | **NO-GO for DSM** (validation / presence only) | narwc.org → DUA / application; `hpettis@neaq.org` |
| 4 | **GoMMAPPS** (SEFSC ship+aerial) | Gulf of Mexico | **Rice's whale**, sperm, Bryde's-type | ✓ | ✓ | ✓ | ✓ | ◐ | ✓ | **GO-caveated — data in hand** (NCEI; Rice's: very low n → wide CV, pool yrs) | NCEI accessions (downloaded) + OBIS-SEAMAP |
| 5 | **SWFSC** (CCE / CalCurCEAS / ORCAWALE / CSCAPE) | US Pacific / California Current | blue, fin, humpback, sperm, **gray** (coastal), minke | ✓ | ✓ | ✓ | ✓ | ◐ | ✓ | **GO (full DSM)** | OBIS-SEAMAP + SWFSC ERDDAP / data request |
| 6 | **AFSC** (GoA / Bering / Aleutian line-transect) | Alaska | fin, humpback, **gray** (migration), minke, sperm | ✓ | ✓ | ✓ | ◐ | ◐ | ✓ | **GO-caveated** (sparser coverage; gray migration under-sampled offshore) | NOAA InPort + OBIS-SEAMAP; AFSC request |
| 7 | **PIFSC HICEAS** | Hawaii (+ wider central Pacific) | sperm, false killer, humpback (winter), beaked | ✓ | ✓ | ✓ | ✓ | ◐ | ✓ | **GO (full DSM)** — but few large-whale strike targets | OBIS-SEAMAP + PIFSC; NOAA InPort |
| 8 | **SEFSC US Caribbean** surveys | US Caribbean (PR/USVI) | sparse — few large whales | ◐ | ◐ | ◐ | ✗ | — | ◐ | **NO-GO (provisional)** — too sparse to fit | SEFSC request; OBIS-SEAMAP |

**Headline:** **NARW US-Atlantic = GO** via **AMAPPS** (item 1–3 ✓ + double-platform g(0)
✓), with **NARWSS** pooled in as caveated aerial effort and **NARWC** held back as
validation/presence only. **This clears the Tranche-1 exit condition** — Phase 3 can begin
NARW-first the moment Tranche 1 lands.

---

## 4. Per-program detail & assessment

### 4.1 AMAPPS — Atlantic Marine Assessment Program for Protected Species  → **GO (full DSM)**
- **What it is:** NOAA NEFSC + SEFSC integrated ship and aerial line-transect surveys of
  the US Atlantic shelf and slope, 2010–present (successor to historic NEFSC/SEFSC
  abundance surveys). Designed distance-sampling protocol.
- **Checklist:**
  1. Perpendicular distances — ✓ (declination angle on aerial; reticle/angle+range on
     ship → perpendicular distance).
  2. Effort / tracklines — ✓ (GPS on-effort tracklines, segmentable).
  3. Group size — ✓ (per-sighting group size recorded).
  4. Double-platform g(0) — ✓ (ship surveys run two independent observer teams; aerial
     uses two-team / racetrack designs — Palka et al. perception-bias corrections exist).
  5. Dive-tag availability — ◐ (not collected *by* AMAPPS, but published per-species
     availability/dive-cycle corrections exist for the Atlantic baleen + sperm whales;
     sourced separately into `whale_dive_cdf.csv` in Phase 3).
  6. Covariates — ✓ (footprint fully inside our PostGIS covariate grid).
- **Verdict:** **GO — full g(0)-corrected DSM.** This is the cornerstone NARW dataset and
  the same effort that underpins the Roberts/Duke NARW model.
- **Access route — CONFIRMED:** The AMAPPS **Northeast + Southeast aerial and shipboard
  cruises (2010–2023)** are hosted on **OBIS-SEAMAP** under **provider 671 — Beth
  Josephson, NOAA Fisheries NEFSC data manager** (Woods Hole):
  https://seamap.env.duke.edu/provider/671 · `elizabeth.josephson@noaa.gov` · 508.495.2362.
  ~30 listed cruises (e.g. *AMAPPS Northeast Aerial Cruise Summer 2021*, *AMAPPS Northeast
  Shipboard Cruise Summer 2016*, *AMAPPS Southeast Aerial Cruise* 2010–2013, plus legacy
  NEFSC abundance/circle-back surveys 1999–2008). The **sighting observations are
  directly downloadable** there (per-dataset terms of use apply). **What still needs a
  request:** the **on-effort tracklines + per-sighting perpendicular distances + double-
  platform/MRDS fields** behind those observation layers (OBIS-SEAMAP often exposes the
  point observations but not the full distance-sampling effort tables) and the **SEFSC
  Southeast** components. **Action:** email **Beth Josephson** (cc SEFSC) for the effort +
  perpendicular-distance tables and confirm redistribution terms; this replaces the earlier
  generic "find a NEFSC contact" step — we now have the named data manager.

### 4.2 NARWSS — North Atlantic Right Whale Sighting Survey  → **GO-caveated**
- **What it is:** NEFSC broad-scale aerial survey program dedicated to right-whale
  distribution/abundance monitoring in the US NE and Mid-Atlantic.
- **Checklist:** effort ✓, group size ✓, perpendicular distance ◐ — NARWSS prioritises
  *coverage and photo-ID* (circle-back on right whales) over strict line-transect
  geometry, so perpendicular distances are present for some passes but the break-off /
  closing protocol violates distance-sampling assumptions in others. Double-platform ◐.
- **Verdict:** **GO-caveated — pool into the NARW DSM as additional aerial effort, do NOT
  fit standalone.** Best used alongside AMAPPS rather than as an independent surface.
- **Access route:** NEFSC (right-whale program, Cole/Khan). Feeds the Roberts NARW model
  and the NARWC database.

### 4.3 NARWC — North Atlantic Right Whale Consortium sightings database  → **NO-GO (DSM)**
- **What it is:** A multi-contributor **compiled sightings database** (1970s–present, some
  historical to the 18th C.). Each record = one *group*. Confirmed from the source: it
  *"contains survey data associated with many of these sightings that allow quantification
  of associated survey effort (note that the database does **not** include **interpreted**
  effort data as such)"* and pools dedicated + opportunistic contributors.
- **Checklist:** group size ✓, effort ◐ (raw not interpreted/uniformly segmentable),
  **perpendicular distance ✗** for the bulk of records (opportunistic + photo-ID heavy).
- **Verdict:** **NO-GO as a DSM input** (fails HARD item 1). **High value as:** (a) NARW
  **presence/validation** layer, (b) distribution context, (c) linkage to the
  Identification (photo-ID) database. Use it to *validate* the AMAPPS-based NARW DSM, not
  to fit it.
- **Access route:** Application + **data-use agreement** via narwc.org (login required);
  contact `hpettis@neaq.org`. User guide and Kenney (2015) review linked on the site.

### 4.4 GoMMAPPS — Gulf of Mexico Marine Assessment Program for Protected Species  → **GO-caveated (data in hand)**
- **What it is:** SEFSC (+ partners) integrated ship and aerial line-transect surveys of
  the Gulf of Mexico (~2017–2018 core effort). Distance-sampling protocol.
- **Checklist:** perpendicular distance ✓, effort ✓, group size ✓, double-platform g(0) ✓
  (ship two-team; aerial two-team T1/T2). Covariates ✓.
- **DATA OBTAINED (2026-06-15):** downloaded + tidied direct from **NCEI accessions** by
  `pipeline/ingestion/download_survey_gommapps.py` — no email request needed. 6 raw
  per-cruise accessions processed (3 vessel: 0241032/0243654/0244002; 3 aerial:
  0242273/0243468/0243469). Output: **272,555 effort points**, **1,564 on-transect
  (typeVLTS=F) sightings**, **1,508 (96.4%) with perpendicular distance** (vessel B 100%,
  aerial A 93.4%). Vessel perp = radial × sin(bearing); aerial perp = stored declination
  distance directly. Double-platform flags set on both. 3 accessions honestly **excluded**:
  0247205/0247206 (consolidated coarse-bin strip-transect, multi-taxon/seabird-dominated),
  0256800 (published SEFSC density-model shapefiles — kept as a **validation benchmark**,
  not survey data).
- **Verdict for Rice's whale:** **GO-caveated.** The protocol is GO-grade, but **Rice's
  whale sightings are very few** (population ~50, narrow NE-Gulf core range) → a fittable
  but **low-n DSM with wide CV**; expect to **pool years and seasons** (annual / pooled
  surface, not 4 seasonal surfaces) and lean on the envelope gate. Still the single
  highest-value strike-platform addition for the Gulf footprint.
- **Verdict for sperm whale:** GO (full) — adequate n (159 sightings tidied).
- **Access route:** **NCEI archive accessions** (done) + OBIS-SEAMAP. SEFSC contact
  Gina Rappucci retained only if richer per-observer detection metadata is later needed.

### 4.5 SWFSC — California Current line-transect (CCE / CalCurCEAS / ORCAWALE / CSCAPE)  → **GO (full DSM)**
- **What it is:** Long-running SWFSC shipboard line-transect programs across the
  California Current (1991–present, multiple named cruises). Mature two-team
  distance-sampling protocol with strong methods documentation.
- **Checklist:** items 1–4 ✓ (perpendicular distance, effort, group size, double-platform
  g(0) all standard); dive availability ◐ (per-species published). Covariates ✓.
- **Verdict:** **GO — full DSM.** Strong for blue, fin, humpback, sperm; **gray whale**
  coastal migration is partially captured (nearshore strata) — treat gray as **GO-caveated**
  pending sighting count. Best-documented Pacific program; good second validated region
  after NARW.
- **Access route:** **OBIS-SEAMAP** + SWFSC **ERDDAP** / data request.

### 4.6 AFSC — Alaska line-transect (Gulf of Alaska / Bering / Aleutian)  → **GO-caveated**
- **What it is:** AFSC shipboard/aerial line-transect surveys across Alaskan waters
  (various years, less continuous than SWFSC).
- **Checklist:** perpendicular distance ✓, effort ✓, group size ✓; double-platform ◐
  (varies by cruise); coverage spatially/temporally **sparser**.
- **Verdict:** **GO-caveated.** Fittable for fin/humpback in covered strata; **gray whale
  migration is under-sampled** by these offshore designs (the coastal migratory corridor
  is the strike-relevant part) → gray stays caveated / possibly SDM-only here.
- **Access route:** **NOAA InPort** + **OBIS-SEAMAP**; AFSC data request.

### 4.7 PIFSC HICEAS — Hawaiian Islands Cetacean & Ecosystem Assessment Survey  → **GO (full DSM)**
- **What it is:** PIFSC shipboard line-transect surveys of the Hawaii EEZ / central
  Pacific (2002, 2010, 2017, 2023). Two-team distance-sampling protocol.
- **Checklist:** items 1–4 ✓; dive availability ◐ (sperm/beaked dive-cycle published).
  Covariates ✓.
- **Verdict:** **GO (full DSM)** methodologically, **but limited strike relevance** — the
  large-whale strike targets in Hawaii are mainly **sperm whale** and wintering
  **humpback** (humpback breeding-season density is better characterised by dedicated
  winter surveys than HICEAS summer effort). Fit where useful, low platform priority.
- **Access route:** **OBIS-SEAMAP** + PIFSC; **NOAA InPort**.

### 4.8 SEFSC US Caribbean surveys (PR / USVI)  → **NO-GO (provisional)**
- **What it is:** Sparse SEFSC effort in US Caribbean waters; few large-whale detections.
- **Checklist:** all three HARD items ◐/✗ in practice **because sightings are too few to
  fit a stable detection function or GAM**, not because the protocol is wrong.
- **Verdict:** **NO-GO (provisional)** — stays Product-A screening only; revisit if a
  dedicated survey or pooled-region fit becomes viable.
- **Access route:** SEFSC request; OBIS-SEAMAP.

---

## 5. Validation benchmark (NOT a primary source)

**Roberts et al. / Duke "Habitat-based Marine Mammal Density Models for the U.S.
Atlantic"** — absolute density (individuals/100 km²), 5 km raster, **2.8M linear km of
1992–2020 effort** (AMAPPS contributed by NEFSC+SEFSC), >30 taxa incl. a dedicated
**NARW model (v12.2, 2024; MEPS doi:10.3354/meps14547)**.

- **Role:** independent **validation benchmark** for our DSM in US Atlantic + Gulf only
  (rank-correlation + calibration where overlapping; abundance cross-check). Per locked
  decision it is **not** the primary density source.
- **Access:** GIS rasters downloadable from the Duke EC model repository, **CC-BY 4.0**.
  Phase-3 plan already references `download_roberts_density.py` → `roberts_density`.
- **Reuse note:** the *processed* survey data feeding these models is curated by Duke and
  is **not openly redistributable** — for our own DSM fit we still source the raw
  distance/effort from NEFSC/SEFSC/OBIS-SEAMAP directly.

---

## 6. Common access routes

| Route | URL / contact | Notes |
|---|---|---|
| **OBIS-SEAMAP** (Duke) | https://seamap.env.duke.edu | Many NOAA survey datasets with perpendicular distance + effort; per-dataset licence/DUA |
| **AMAPPS provider (OBIS-SEAMAP)** | https://seamap.env.duke.edu/provider/671 · `elizabeth.josephson@noaa.gov` | **Confirmed:** Beth Josephson (NEFSC) — ~30 AMAPPS NE+SE cruises 2010–2023; observations downloadable, request effort/perp-distance tables |
| **NOAA InPort** | https://www.fisheries.noaa.gov/inport | Metadata catalog → data links / request contacts for NEFSC/SEFSC/SWFSC/AFSC/PIFSC |
| **NEFSC / SEFSC** direct request | NEFSC: Beth Josephson (above); SEFSC data managers via InPort | Cleanest AMAPPS / GoMMAPPS distance + effort tables |
| **SWFSC ERDDAP** | SWFSC ERDDAP server | California Current line-transect data |
| **NARWC** | https://www.narwc.org → DUA; `hpettis@neaq.org` | Right-whale sightings + photo-ID; validation/presence only |
| **Duke EC density models** | https://seamap.env.duke.edu/models/Duke/EC/ | Validation-benchmark rasters, CC-BY 4.0 |

---

## 7. Manual action tracker (non-automated tasks)

The sourcing workstream is **human-led by design** — data requests, data-use agreements
(DUAs), and redistribution-terms confirmation cannot be scripted. Tick these off as they
resolve and update the verdicts in §3.

**Legend — Status:** ☐ not started · ◔ drafted · ◑ submitted/awaiting reply · ◕ partial
data received · ● complete. **Blocks T1** = blocks the Tranche-1 exit condition (NARW→GO).

| # | Action | Where to send | Status | Owner | Date sent | Blocks T1 |
|---|--------|---------------|:------:|-------|-----------|:---------:|
| 1 | Request raw **AMAPPS** perpendicular-distance + segmentable-effort tables (NARW + Atlantic large whales) | Beth Josephson, NEFSC — OBIS-SEAMAP provider 671 (`elizabeth.josephson@noaa.gov`) | ◑ | | 2026-06-15 | **YES** |
| 2 | Confirm **redistribution / storage licence** for the AMAPPS data we receive | same reply thread as #1 | ◑ | | 2026-06-15 | **YES** |
| 3 | Confirm **double-platform / MRDS** perception-bias metadata is in the deliverable (g0-full vs caveated) | same reply thread as #1 | ◑ | | 2026-06-15 | **YES** |
| 4 | **GoMMAPPS** ship+aerial distance/effort — **obtained direct from NCEI accessions** (`download_survey_gommapps.py`): 272.5k effort pts, 1,564 sightings, 1,508 with perp. distance; double-platform set; consolidated strip + SEFSC SDM shapefiles excluded | Gina Rappucci, SEFSC (`gina.rappucci@noaa.gov`) — only if richer detection metadata later needed | ✓ | | 2026-06-15 | no |
| 5 | Apply for **NARWC DUA** (NARW validation/presence layer) — contributor-outreach step sent to Pettis; form gated on her reply | narwc.org application → `hpettis@neaq.org` | ◑ | | 2026-06-15 | no |
| 6 | Inventory published **per-species dive-tag / TDR time-at-depth** for `whale_dive_cdf.csv` — source inventory done + citations verified (§9); CDF depth-bin values still to extract from PDFs in Phase 3 | literature (no request) | ◑ | | 2026-06-15 | no |
| 7 | Request **SWFSC** California Current line-transect distance + effort | Jeff Moore, SWFSC CMAP — provider 1615 (`jeff.e.moore@noaa.gov`) | ◑ | | 2026-06-15 | no |
| 8 | Request **PIFSC HICEAS** distance + effort | Erin Oleson, PIFSC (`erin.oleson@noaa.gov`) | ◑ | | 2026-06-15 | no |
| 9 | Request **AFSC** (GoA / Bering / Aleutian) distance + effort | Janice Waite, NMML/AFSC — provider 98 (`Janice.Waite@noaa.gov`); provider-52 (Goetz, `ktg4@duke.edu`) is a stale ~2004 Duke student address — skipped | ◑ | | 2026-06-15 | no |

> **Status update (2026-06-15):** Actions #1–#4, #7, #8 **submitted** as five bundled
> emails (AMAPPS+licence+g0 = one thread to Josephson; GoMMAPPS to Rappucci; SWFSC to
> Moore; PIFSC to Oleson). **Bounces:** the OBIS-SEAMAP-listed addresses for
> **Karin Forney** (SWFSC provider 592, CSCAPE — was only a CC, primary Moore delivered)
> and **Marie C. Hill** (PIFSC provider 141, original HICEAS data owner) both returned
> `550 5.7.1 unrecognized address`. PIFSC re-routed to **Erin Oleson** (HICEAS chief
> scientist) with a note that Hill's address bounced. **AFSC (#9) still to send.**
> Awaiting replies — science-center turnaround is the long pole.

### 7.1 Where to find the right contact

1. **NOAA InPort** (https://www.fisheries.noaa.gov/inport) — search the program name
   (e.g. "AMAPPS", "GoMMAPPS", "HICEAS"). Each catalog record lists a **Data Steward /
   Point of Contact** with email; that is the correct recipient.
2. **OBIS-SEAMAP dataset page** (https://seamap.env.duke.edu) — if the program already has
   a dataset there, the page names the **provider/contact** and the per-dataset licence /
   DUA terms. Start here if a public subset already exists — it may be downloadable
   directly and only the *fuller* distance tables need a request.
3. **AMAPPS technical reports** (Palka et al.) — the author/affiliation list points to the
   NEFSC/SEFSC data managers; cite the specific report year you want data from.
4. **CC the OBIS-SEAMAP team** if the dataset is hosted there but you need the underlying
   perpendicular distances rather than the summarised occurrence layer.

### 7.2 Draft request — AMAPPS (actions #1–#3, one email)

> **To:** Beth Josephson, NOAA Fisheries NEFSC data manager — OBIS-SEAMAP provider 671
> (`elizabeth.josephson@noaa.gov`, 508.495.2362)
> **Cc:** SEFSC data steward (for the Southeast cruises)
> **Subject:** Data request — AMAPPS line-transect perpendicular distances & effort for a non-commercial whale ship-strike risk model
>
> Dear Beth Josephson,
>
> I am developing a non-commercial, open-methodology **whale–vessel collision-risk model**
> for US waters that aligns with the IWC ship-strike reporting standard (Leaper et al. 2026)
> and IWC model-based abundance guidance (Miller & Kelly 2023). To estimate **absolute
> whale density** with a distance-sampling / density-surface model (R `Distance`/`mrds`/`dsm`),
> I would like to request the underlying **AMAPPS** survey data for the US Atlantic, ideally
> covering North Atlantic right whale and the other large whales (fin, humpback, sei,
> sperm, minke). I can see the **AMAPPS Northeast + Southeast aerial and shipboard cruises
> (2010–2023)** under your OBIS-SEAMAP provider page, so I am specifically asking for the
> **on-effort tracklines + per-sighting perpendicular distances** behind those observation
> layers.
>
> Specifically, I am looking for, in whatever tabular form you can share:
> 1. **On-effort tracklines / effort segments** (segment geometry + length, platform, date),
> 2. **Sightings with perpendicular distances** (or the raw angle/reticle or bearing+range
>    needed to derive them) and **group size** per sighting,
> 3. **Detection covariates** — Beaufort/sea state, observer, platform (ship/aerial), and
>    any **double-platform / independent-observer** flags that support a perception-bias
>    (MRDS) g(0) correction.
>
> Three quick questions so I represent the data honestly:
> - Are **double-platform / independent-observer** data available for these surveys (i.e.
>   can perception g(0) be estimated), or should I treat g(0)=1 and flag deep divers as
>   biased-low?
> - What are the **redistribution / citation / storage terms**? I want to comply fully —
>   I can keep raw data private and publish only derived density surfaces + code if needed,
>   and will cite the program and any required acknowledgements.
> - Is any of this already public via **OBIS-SEAMAP / InPort** at the resolution above, so
>   I avoid asking you for something already released?
>
> This is unfunded / non-commercial research; results and code will be openly available and
> the work is intended to be useful for ship-strike risk reduction. Happy to sign a
> data-use agreement and to share methods or outputs back with your team.
>
> Thank you very much for your time.
>
> [Your name, affiliation if any, contact]

### 7.3 Draft request — GoMMAPPS / Rice's whale (action #4)

> **Subject:** Data request — GoMMAPPS distance/effort data (Rice's whale & Gulf large whales)
>
> Reuse the AMAPPS template above, changed to the **Gulf of Mexico / GoMMAPPS** program and
> SEFSC. Add one Rice's-whale-specific line:
>
> > Because Rice's whale is so rare, could you also indicate the **approximate number of
> > on-effort Rice's whale sightings** in the GoMMAPPS dataset? I need this to decide whether
> > a seasonal density surface is feasible or whether I should pool years/seasons into a
> > single annual surface with appropriately wide confidence intervals.

### 7.4 Draft request — SWFSC / AFSC / PIFSC (actions #7–#8)

> Reuse the AMAPPS template, swapping the program name and science center
> (SWFSC = California Current CCE/CalCurCEAS/ORCAWALE/CSCAPE; AFSC = Gulf of Alaska/Bering/
> Aleutian; PIFSC = HICEAS). For **SWFSC, check the ERDDAP server first** — much of the
> California Current line-transect data is already published there, so the request may only
> be needed for the detection-covariate / double-platform tables.

### 7.5 NARWC data-use agreement (action #5)

> NARWC is **not** an email request — it is a formal **application + DUA**:
> 1. Go to https://www.narwc.org → **NARWC Databases** → Sightings Database, and read the
>    **User Guide** (linked on the site) and Kenney (2015) review first.
> 2. Submit the **data-request / DUA application** (account login required).
> 3. Contact **`hpettis@neaq.org`** (Heather Pettis) for access questions.
> 4. **State the intended use explicitly:** *validation / presence layer only* for an
>    independent NARW DSM — NARWC is **not** being used to fit absolute density (it lacks
>    uniform perpendicular distances). This framing matches their data-sharing norms and
>    is the truthful description of how we use it (see §4.3).

---

## 8. Phase-3 readiness statement

- ✅ **NARW US-Atlantic is GO** (AMAPPS full DSM + NARWSS pooled aerial; NARWC for
  validation). **Tranche-1 exit condition is satisfiable** — Phase 3 can start NARW-first
  with no wait, provided the NEFSC/SEFSC AMAPPS data request is in motion.
- ✅ **GoMMAPPS done** (downloaded + tidied from NCEI accessions — 1,564 sightings,
  1,508 with perpendicular distance; vessel + aerial both DSM-ready). **Rice's whale**
  remains low-n → annual/pooled grain, envelope-gated.
- ⏳ **Next in queue:** SWFSC (second validated region), then AFSC / PIFSC region-by-region.
- ⛔ **Held back:** NARWC (validation only), SEFSC US Caribbean (too sparse).

**Open actions (data hunt, no code):**
1. File the **NEFSC/SEFSC AMAPPS** data request; confirm redistribution terms for raw
   perpendicular-distance + effort tables.
2. Confirm **double-platform/MRDS** metadata is included in the AMAPPS deliverable (sets
   GO-full vs GO-caveated for NARW).
3. Pull **Rice's-whale** GoMMAPPS sighting count → decide seasonal-vs-annual DSM grain.
4. Inventory published **per-species dive-tag / TDR time-at-depth** sources to build
   `whale_dive_cdf.csv` in Phase 3 (single-source for availability g(0) + Phase-4
   Pstrikedepth).
5. Apply for the **NARWC DUA** for the validation layer.

---

## 9. Dive-tag / TDR time-at-depth inventory (action #6)

> **What this is:** the literature sourcing pass for the **per-species cumulative
> time-at-depth CDF** that becomes `whale_dive_cdf.csv`. It is **not** modelling code and
> has **zero dependency** on the pending survey-data emails — pure desk research, doable
> now. The CDF is **single-sourced** and read twice (see plan): Phase 3 availability g(0)
> = fraction of time in the surface detection band; Phase 4 `Pstrikedepth` = F(Sz) =
> fraction of time shallower than the vessel strike-zone depth. Built in Phase 3, reused
> in Phase 4/5b.
>
> **HONESTY GATE — do not invent numbers.** This table lists *which papers to pull* and
> *what each provides*. The actual depth-bin percentages / CDF values **must be extracted
> from the source PDFs (or their raw TDR archives)** before anything is written to the
> seed. Citations below are a starting inventory to **verify** — confirm author/year/DOI
> against the actual paper, and prefer the most recent multi-deployment tag study per
> species. Many papers report only **summary stats** (max depth, mean dive depth, % time
> at surface), not a continuous CDF → expect to **digitise dive-profile histograms** or
> request the raw time-at-depth tables to build a true F(z).

### 9.1 Diver class → why it matters for g(0)

Availability bias scales with how little time a species spends in the surface detection
band. Rough ordering for our target set (deepest/longest-submerged → biggest correction):

**sperm ≫ blue ≈ fin > sei ≈ minke > Rice's > gray ≈ humpback ≈ right.**

Surface-active species (right, humpback, gray) need a **small** availability correction;
deep divers (sperm especially) need a **large** one and are the species where a missing
or wrong CDF most distorts downstream collision numbers.

### 9.2 Per-species source inventory (citations verified 2026-06-15)

Bibliographic details below were **verified against Google Scholar / publisher pages**
on 2026-06-15. A few summary dive statistics are quoted where the abstract gave them —
but the **continuous depth-bin percentages for the CDF still must be digitised from each
paper's dive-profile figures or its raw TDR archive.** Do not treat the quoted means/maxima
as a CDF.

| Species | Diver class | Verified primary source(s) | What it provides | Gap status |
|---|---|---|---|---|
| **Right (NARW)** | shallow/mid (prey-layer) | **Baumgartner & Mate 2003**, *MEPS* 264:123–135 (TDR/Argos, summer foraging); **Baumgartner et al. 2017**, *MEPS* 581:165–181 (diving + human-caused mortality); **Van der Hoop et al. 2019**, *Funct Ecol* (DTAG foraging rates) | Feeding dives track the Calanus max-density layer; avg dive ~12 min; high surface time | OK — US Atlantic, well-studied |
| **Humpback** | shallow, surface-active | **Goldbogen et al. 2008**, *J Exp Biol* 211(23):3712 (DTAG foraging kinematics); Friedlaender et al. (bottom-feeding) | Foraging dive depth/time; high surface availability | OK |
| **Fin** | deep lunge-feeder | **Goldbogen et al. 2006**, *J Exp Biol* 209(7):1231 (DTAG dive kinematics); Goldbogen et al. 2007, *MEPS* 349:289 | Foraging vs transit dive depth distribution | OK |
| **Blue** | deep lunge-feeder | **Goldbogen et al. 2011**, *J Exp Biol* 214(1):131; **Goldbogen et al. 2015**, *Funct Ecol* (3-D foraging, diel deep-day/shallow-night); Calambokidis et al. 2007 (Crittercam) | Diel depth pattern; 200 foraging dives / 654 lunges (2011) | OK |
| **Sperm** | **deepest** | **Watwood et al. 2006**, *J Anim Ecol* 75:814 — DOI `10.1111/j.1365-2656.2006.01101.x`. 198 dives, 37 individuals (Atlantic / GoM / Ligurian) | Mean max depth by region: **985 m / 644 m / 827 m**; dive cycle ≈ **45 min dive + 9 min surface** → **biggest availability correction** | OK — top priority to get right |
| **Minke** | mid, sparse data | No N-Atlantic/Pacific time-at-depth tag study located; Antarctic-minke tag work only | Few/no usable deployments | ⚠️ **Gap** |
| **Sei** | mid, very sparse | No published time-at-depth CDF located | Thin | ⚠️ **Gap — likely congener proxy** |
| **Gray** | shallow benthic, coastal | Mate & Urbán-Ramirez / Mate et al. (satellite-tag migration); Sumich (dive/respiration) | Shallow coastal dives; migration vs feeding differ | OK-ish |
| **Rice's** | mid, **near-surface at night** | **Soldevilla et al. 2017**, *Endang Species Res* 32:533–550 (orig. tag study, as "Bryde's"); **Rice et al. 2023**, *Sci Rep* 13 (2 tagged whales; deep dives >100 m by day, **near surface most of the night**); Stevens et al. 2024, *BOEM* 2024-053 (vessel-strike review) | Diel depth pattern — strike-critical (surface at night) | ⚠️ **Severe gap — only ~2 tag deployments**, but the single most strike-relevant CDF |

### 9.3 Known data gaps & fallback rule

- **Rice's, sei, minke** have sparse or near-absent published time-at-depth CDFs. Per the
  plan's g(0) fallback ladder: where no usable availability data exists, document
  **g(0)=1** and flag the species **biased-low**, OR borrow a **congener proxy CDF**
  (e.g. a balaenopterid analogue) with the substitution explicitly recorded in the model
  card. Do **not** silently fabricate a CDF.
- **Rice's whale is the highest-value gap** — ship strike is *the* primary threat, the
  diel "surface at night" pattern (Rice et al. 2023; Soldevilla et al. 2017) is exactly
  what drives strike exposure, yet only ~2 tags have been deployed. The GoMMAPPS request
  to Gina Rappucci (#4) is the natural channel to ask whether any newer tag/TDR
  time-at-depth is shareable; Garrison et al. 2024 (*ESR* 54:41–58) is the companion DSM.

### 9.4 Output spec (for Phase 3, not built here)

`whale_dive_cdf.csv` grain ≈ `(species, depth_bin_m, cumulative_fraction_shallower)` — a
monotone CDF per species from 0 → 1 with increasing depth. Phase 3 reads it two ways
(surface-band availability; F(Sz) for Pstrikedepth). **This inventory step only sources
the inputs; the CSV itself is assembled in Phase 3 `density/` R alongside the DSM fit.**

### 9.5 Extracted anchor values (read from source text, 2026-06-15)

These are **summary anchors quoted verbatim from the papers' text/abstracts** — *not* a
full CDF. They are enough to sanity-check a digitised curve and to seed the two species
that matter most (Rice's = strike-critical; sperm = deepest diver / largest g(0)
correction). The **continuous depth-bin fractions still require digitising each paper's
dive-profile / cumulative-time figure** (flagged below) and remain a Phase-3 task.

**Rice's whale — Rice et al. 2023, *Sci Rep* 13:8996 (open access, 2 tags: "Milky Way" 2015, "Edna" 2018):**
- **Night (strike-critical window):** within **2 m** of surface **45%** (Milky Way) /
  **52%** (Edna) of the time; within **15 m** of surface **85%** of the time. Shallow
  dives (<10 m) with only occasional ~100 m dives; ~9% of night dives involved foraging.
- **Day:** diel deep dives >100 m; mean foraging-dive depth **206.8 m** (Milky Way) /
  **172.5 m** (Edna); Edna hugged the bottom at ~200 m. 90% of feeding lunges at >50 m.
- **CDF figure exists:** Fig. 5 plots *"cumulative time spent at a given depth or
  shallower"* for daylight vs night → **this is the exact curve to digitise** for
  `whale_dive_cdf.csv`. The night curve is the one to use for strike exposure.
- *Direct strike relevance (authors' own words):* night-time surface tendency "supports
  earlier voiced concerns that they have a high risk of collision with vessels."

**Sperm whale — Watwood et al. 2006, *J Anim Ecol* 75:814 (198 dives, 37 individuals):**
- Mean max foraging-dive depth by region: **985 m** (Atlantic), **644 m** (Gulf of
  Mexico), **827 m** (Ligurian Sea).
- Dive cycle ≈ **45 min dive + 9 min surface interval** → only ~**17%** of the cycle is
  the inter-dive surface phase → **largest availability correction** of our set.
- Full depth distribution: **digitise from the paper's dive-profile figures in Phase 3**
  (Wiley PDF is BRONZE-OA but JS-gated; not text-extractable here). The above anchors are
  text-confirmed; the per-bin fractions are not yet extracted.

> **Still do NOT fabricate the intermediate bins.** A two-point night anchor (2 m → 45–52%,
> 15 m → 85%) plus the figure shape is enough to fit a monotone Rice's-whale night CDF in
> Phase 3; everything between the anchors must come from the digitised figure, not a guess.

> Update this file as each request resolves; flip verdicts and tick checklist items in the
> table in §3. When NARW US-Atlantic data is in hand and validated against Roberts, note it
> in the progress log of `/memories/repo/context.md`.
