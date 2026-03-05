"use client";

import { useState } from "react";
import type { LayerType } from "@/lib/types";

/* ── Helpers ─────────────────────────────────────────────── */

/** Small explanation blurb below a section heading. */
function Explainer({ text }: { text: string }) {
  return (
    <p className="mb-2 text-[11px] leading-snug text-slate-500">
      {text}
    </p>
  );
}

/** Formatted metric row: label — value. */
function Metric({
  label,
  value,
  unit,
}: {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
}) {
  return (
    <p className="text-sm text-slate-300">
      <span className="text-slate-400">{label}: </span>
      <strong>
        {value ?? "—"}
        {unit && value != null ? ` ${unit}` : ""}
      </strong>
    </p>
  );
}

/* ── Score bar with expandable explanation ────────────────── */

interface SubScoreInfo {
  label: string;
  value: number;
  weight: string;
  shortDesc: string;
  details: string[];
  interpretation: string;
}

function ScoreBarExpanded({ info }: { info: SubScoreInfo }) {
  const [expanded, setExpanded] = useState(false);
  const pct = Math.round(info.value * 100);
  const hue = Math.round(120 - info.value * 120);

  return (
    <div className="rounded-lg border border-ocean-800/30 bg-abyss-800/30">
      {/* Clickable header row */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-2.5 py-2 text-xs hover:bg-abyss-800/50"
      >
        <span className="w-[6.5rem] truncate text-left text-slate-400">
          {info.label}
        </span>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-700">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${pct}%`,
              backgroundColor: `hsl(${hue}, 80%, 50%)`,
            }}
          />
        </div>
        <span className="w-10 text-right text-slate-300">{pct}%</span>
        <span className="w-3 text-slate-500">{expanded ? "▾" : "▸"}</span>
      </button>

      {/* Expanded detail panel */}
      {expanded && (
        <div className="border-t border-ocean-800/30 px-3 pb-3 pt-2">
          <div className="mb-2 flex items-center gap-2">
            <span className="rounded-full bg-abyss-700 px-2 py-0.5 text-[10px] font-bold text-slate-400">
              {info.weight} weight
            </span>
            <span className="text-[10px] text-slate-500">
              {info.shortDesc}
            </span>
          </div>
          <ul className="mb-2 space-y-1 pl-3">
            {info.details.map((d, i) => (
              <li
                key={i}
                className="text-[11px] leading-snug text-slate-500 before:mr-1.5 before:text-slate-600 before:content-['•']"
              >
                {d}
              </li>
            ))}
          </ul>
          <p className="rounded-md bg-abyss-800/60 px-2 py-1.5 text-[11px] italic leading-snug text-slate-400">
            {info.interpretation}
          </p>
        </div>
      )}
    </div>
  );
}

/** Simple score bar (no expand) for the composite row. */
function ScoreBar({
  label,
  value,
  tooltip,
}: {
  label: string;
  value: number;
  tooltip?: string;
}) {
  const pct = Math.round(value * 100);
  const hue = Math.round(120 - value * 120);
  return (
    <div className="flex items-center gap-2 text-xs" title={tooltip}>
      <span className="w-28 truncate text-slate-400">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-700">
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: `${pct}%`,
            backgroundColor: `hsl(${hue}, 80%, 50%)`,
          }}
        />
      </div>
      <span className="w-10 text-right text-slate-300">{pct}%</span>
    </div>
  );
}

/* ── Layer explanation text ───────────────────────────────── */

const LAYER_EXPLANATIONS: Record<LayerType, string> = {
  risk:
    "Composite collision risk from 7 expert-weighted sub-scores. " +
    "Each sub-score is a percentile rank (0–100%) relative to all US coastal cells.",
  risk_ml:
    "ML-enhanced risk replaces cetacean + habitat scores with ISDM species " +
    "distribution model predictions. 7 sub-scores, seasonally varying.",
  bathymetry:
    "GEBCO ocean depth sampled at H3 cell centres. Shelf edge and continental " +
    "shelf zones are key cetacean habitat indicators.",
  ocean:
    "Copernicus satellite-derived ocean covariates averaged by season. " +
    "Primary productivity and SST are key whale habitat drivers.",
  whale_predictions:
    "ISDM (Integrated Species Distribution Model) predictions per species. " +
    "P(any whale) = 1 − ∏(1 − Pᵢ) across 4 modelled species.",
  sdm_predictions:
    "SDM (OBIS-trained) species distribution model predictions. " +
    "Out-of-fold spatial CV scores — comparable to ISDM but trained on " +
    "opportunistic sighting data instead of expert-curated presence/absence.",
  cetacean_density:
    "OBIS cetacean sighting records aggregated to H3 cells. " +
    "Includes 364K records across 71 species.",
  strike_density:
    "NOAA ship strike records (261 total, 67 geocoded). " +
    "Extremely sparse — most cells have zero strikes.",
  traffic_density:
    "Seasonal vessel traffic from AIS data. 8 danger components: " +
    "speed lethality, high-speed fraction, vessel volume, large vessels, " +
    "draft risk, commercial traffic, night operations, and COG diversity.",
};

/* ── Sub-score detail definitions ────────────────────────── */

function buildSubScoreInfos(
  scores: Record<string, number>,
): SubScoreInfo[] {
  return [
    {
      label: "Traffic",
      value: (scores.traffic_score as number) ?? 0,
      weight: "25%",
      shortDesc: "Vessel traffic intensity",
      details: [
        "Combines 8 components: V&T speed-dependent lethality (Vanderlaan & Taggart 2007), vessel draft risk, traffic volume, large vessel fraction, night-time ratio, and vessel type diversity.",
        "V&T lethality models the probability of lethal injury as a logistic function of vessel speed — the single most important predictor of strike mortality.",
        "Draft risk captures deep-draught vessels (tankers, bulk carriers) whose propellers extend into whale habitat depth.",
      ],
      interpretation:
        pctInterpretation(
          (scores.traffic_score as number) ?? 0,
          "traffic intensity",
        ),
    },
    {
      label: "Cetacean",
      value: (scores.cetacean_score as number) ?? 0,
      weight: "25%",
      shortDesc: "Cetacean presence density",
      details: [
        "Three weighted components: total sighting count (50%), baleen whale sightings (30%), and recent observations since 2015 (20%).",
        "Baleen whales receive extra weight because they are the primary strike victims — large, slow-surfacing species that overlap with shipping lanes.",
        "Recent sightings are up-weighted to prioritise current population distributions over historical records.",
      ],
      interpretation:
        pctInterpretation(
          (scores.cetacean_score as number) ?? 0,
          "cetacean presence",
        ),
    },
    {
      label: "Strike",
      value: (scores.strike_score as number) ?? 0,
      weight: "10%",
      shortDesc: "Historical ship strike records",
      details: [
        "Based on NOAA ship strike database — only 67 of 261 records are geocoded, making this score effectively binary for most cells.",
        "Three components: total strikes (40%), fatal strikes (30%), large whale strikes (30%).",
        "Proximity decay (half-life 25 km) spreads influence to nearby cells, acknowledging that strikes occur in broader areas than single GPS points.",
      ],
      interpretation:
        (scores.strike_score as number) > 0
          ? "This cell has recorded ship strikes or is near cells with strike history. Even one strike significantly elevates this score due to extreme data sparsity."
          : "No recorded strikes in or near this cell. 99.99% of cells score zero — absence of data does not mean absence of risk.",
    },
    {
      label: "Habitat",
      value: (scores.habitat_score as number) ?? 0,
      weight: "10%",
      shortDesc: "Habitat suitability for cetaceans",
      details: [
        "Bathymetry contributes 80%: continental shelf edge (200–1000 m) scores highest because upwelling concentrates prey.",
        "Primary productivity (PP) contributes 20%: satellite-derived chlorophyll proxy — high PP indicates productive waters that attract whales.",
        "Three bathymetric sub-zones: shelf (<200 m), edge (200–1000 m, highest weight), and deep (>1000 m, lowest weight).",
      ],
      interpretation:
        pctInterpretation(
          (scores.habitat_score as number) ?? 0,
          "habitat suitability",
        ),
    },
    {
      label: "Proximity",
      value: (scores.proximity_score as number) ?? 0,
      weight: "15%",
      shortDesc: "Distance-decay from risk features",
      details: [
        "Blends three exponential decay distances: whale × ship co-occurrence (45%), nearest ship strike (30%), and distance to unprotected waters (25%).",
        "Whale proximity uses a 10 km half-life — risk halves every 10 km from the nearest sighting. Strike proximity uses 25 km, and protection gap uses 50 km.",
        "This intentionally overlaps with density sub-scores: density measures magnitude at a point, proximity captures spatial gradients around features.",
      ],
      interpretation:
        pctInterpretation(
          (scores.proximity_score as number) ?? 0,
          "proximity risk",
        ),
    },
    {
      label: "Protection Gap",
      value: (scores.protection_gap as number) ?? 0,
      weight: "10%",
      shortDesc: "Absence of enforceable protection",
      details: [
        "Tiered scoring based on real, enforceable protections: no-take zones (best, 0.10) → strict MPAs (0.25–0.35) → any MPA (0.60) → SMA only (0.80) → unprotected (1.0).",
        "SMAs (Seasonal Management Areas) are voluntary speed advisories — compliance is low (~5% for vessels >65 ft, Silber & Bettridge 2012), so they provide only a small bonus over unprotected waters.",
        "Proposed speed zones are excluded entirely — they signal recognised risk, not actual protection. Including them would artificially lower risk in the most dangerous corridors.",
      ],
      interpretation:
        (scores.protection_gap as number) >= 0.8
          ? "Little or no enforceable protection. This cell is in open waters or covered only by voluntary speed advisories."
          : (scores.protection_gap as number) <= 0.2
            ? "Strong enforceable protection — likely within or near a no-take marine reserve."
            : "Moderate protection — covered by some form of MPA, but not the strongest no-take designation.",
    },
    {
      label: "Reference",
      value: (scores.reference_risk_score as number) ?? 0,
      weight: "5%",
      shortDesc: "Nisi et al. 2024 global baseline",
      details: [
        "1-degree resolution global ship-strike risk grid from Nisi et al. 2024, derived from AIS traffic × whale habitat overlap.",
        "Provides a coarse independent baseline — useful for validation and for areas where our fine-grained data is sparse.",
        "Low weight (5%) because our own sub-scores provide much higher spatial resolution and more recent data.",
      ],
      interpretation:
        pctInterpretation(
          (scores.reference_risk_score as number) ?? 0,
          "Nisi reference risk",
        ),
    },
  ];
}

function pctInterpretation(value: number, label: string): string {
  const pct = Math.round(value * 100);
  if (pct >= 90) return `Extremely high ${label} — top 10% of all US coastal cells.`;
  if (pct >= 75) return `High ${label} — top 25% of US coastal cells.`;
  if (pct >= 50) return `Moderate ${label} — above the median for US coastal cells.`;
  if (pct >= 25) return `Below average ${label} — lower quartile of US coastal cells.`;
  return `Very low ${label} — bottom 25% of all US coastal cells.`;
}

/* ── Props ───────────────────────────────────────────────── */

interface CellDetailProps {
  cell: Record<string, unknown>;
  detail: Record<string, unknown> | null;
  activeLayer: LayerType;
  onClose: () => void;
}

/* ── Component ───────────────────────────────────────────── */

export default function CellDetail({
  cell,
  detail,
  activeLayer,
  onClose,
}: CellDetailProps) {
  const src = detail ?? cell;

  // Sub-scores live under a nested `scores` object in the API response
  const scores =
    (src.scores as Record<string, number> | undefined) ?? {};

  return (
    <div className="glass-panel-strong absolute right-4 top-4 z-10 w-80 max-h-[calc(100vh-2rem)] overflow-y-auto rounded-xl shadow-ocean-lg">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-ocean-800/30 px-4 py-3">
        <h2 className="font-display text-sm font-bold text-white">
          Cell Detail
        </h2>
        <button
          onClick={onClose}
          className="text-lg leading-none text-slate-500 hover:text-slate-200"
        >
          ×
        </button>
      </div>

      <div className="space-y-4 p-4">
        {/* Location */}
        <div>
          <p className="mb-1 font-mono text-xs text-slate-500">
            {cell.h3 as string}
          </p>
          <p className="text-xs text-slate-400">
            {(cell.cell_lat as number)?.toFixed(3)}°N,{" "}
            {Math.abs(cell.cell_lon as number)?.toFixed(3)}°W
          </p>
        </div>

        {/* Layer explanation */}
        <Explainer text={LAYER_EXPLANATIONS[activeLayer]} />

        {/* ── Risk sub-scores ── */}
        {(activeLayer === "risk" || activeLayer === "risk_ml") && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Sub-scores
            </h3>
            <p className="mb-2 text-[10px] text-slate-500">
              Click any score to see what drives it and how to interpret the value.
            </p>
            {buildSubScoreInfos(scores).map((info) => (
              <ScoreBarExpanded key={info.label} info={info} />
            ))}
            <div className="border-t border-ocean-800/50 pt-2">
              <ScoreBar
                label="Composite"
                value={(src.risk_score as number) ?? 0}
                tooltip="Weighted sum of all 7 sub-scores"
              />
            </div>
            {!!src.risk_category && (
              <p className="mt-1 text-xs text-slate-400">
                Category:{" "}
                <strong className="text-slate-200">
                  {String(src.risk_category)}
                </strong>
              </p>
            )}
          </div>
        )}

        {/* ── Bathymetry ── */}
        {activeLayer === "bathymetry" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Depth Profile
            </h3>
            <Metric
              label="Depth"
              value={(src.depth_m as number)?.toFixed(0)}
              unit="m"
            />
            <Metric
              label="Depth zone"
              value={src.depth_zone as string}
            />
            <p className="text-sm text-slate-300">
              <span className="text-slate-400">Continental shelf: </span>
              <strong>{src.is_continental_shelf ? "✓ Yes" : "✗ No"}</strong>
              <span className="text-slate-400"> · Shelf edge: </span>
              <strong>{src.is_shelf_edge ? "✓ Yes" : "✗ No"}</strong>
            </p>
            <Explainer
              text={
                "Shelf edge (200–1000 m) is a productivity hotspot where " +
                "upwelling concentrates prey, attracting baleen whales."
              }
            />
          </div>
        )}

        {/* ── Ocean covariates ── */}
        {activeLayer === "ocean" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Ocean Covariates
            </h3>
            {!!src.season && (
              <p className="text-xs text-ocean-400">
                Season: <strong>{String(src.season)}</strong>
              </p>
            )}
            <Metric
              label="Sea Surface Temperature (SST)"
              value={(src.sst as number)?.toFixed(1)}
              unit="°C"
            />
            <Metric
              label="SST Std. Deviation"
              value={(src.sst_sd as number)?.toFixed(2)}
              unit="°C"
            />
            <Metric
              label="Mixed Layer Depth (MLD)"
              value={(src.mld as number)?.toFixed(1)}
              unit="m"
            />
            <Metric
              label="Sea Level Anomaly (SLA)"
              value={(src.sla as number)?.toFixed(3)}
              unit="m"
            />
            <Metric
              label="Primary Productivity (PP)"
              value={(src.pp_upper_200m as number)?.toFixed(2)}
              unit="mg C/m²/day"
            />
            <Explainer
              text={
                "SST and PP are key habitat predictors — warm SST fronts and " +
                "high primary productivity concentrate prey. MLD indicates mixing " +
                "depth; SLA reflects mesoscale eddies that aggregate plankton."
              }
            />
          </div>
        )}

        {/* ── Whale predictions ── */}
        {activeLayer === "whale_predictions" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              ISDM Whale Predictions
            </h3>
            {!!src.season && (
              <p className="text-xs text-ocean-400">
                Season: <strong>{String(src.season)}</strong>
              </p>
            )}
            <Metric
              label="P(any whale)"
              value={`${(((src.any_whale_prob as number) ?? 0) * 100).toFixed(1)}%`}
            />
            <div className="mt-1 space-y-0.5 pl-2 text-xs text-slate-400">
              <p>
                Blue whale:{" "}
                <span className="text-slate-300">
                  {(((src.isdm_blue_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
              <p>
                Fin whale:{" "}
                <span className="text-slate-300">
                  {(((src.isdm_fin_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
              <p>
                Humpback:{" "}
                <span className="text-slate-300">
                  {(((src.isdm_humpback_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
              <p>
                Sperm whale:{" "}
                <span className="text-slate-300">
                  {(((src.isdm_sperm_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
            </div>
            <Explainer
              text={
                "XGBoost models trained on OBIS sightings with 7 environmental " +
                "covariates (SST, MLD, SLA, PP, depth, depth range). " +
                "P(any) = 1 − ∏(1 − Pᵢ) treats all species equally."
              }
            />
          </div>
        )}

        {/* ── Cetacean density ── */}
        {activeLayer === "cetacean_density" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Cetacean Sightings
            </h3>
            {!!src.season && (
              <p className="text-xs text-ocean-400">
                Season: <strong>{String(src.season)}</strong>
              </p>
            )}
            <Metric
              label="Total sightings"
              value={(src.total_sightings as number) ?? 0}
            />
            <Metric
              label="Unique species"
              value={(src.unique_species as number) ?? undefined}
            />
            <Metric
              label="Baleen sightings"
              value={(src.baleen_sightings as number) ?? undefined}
            />
            <Metric
              label="Recent sightings"
              value={(src.recent_sightings as number) ?? undefined}
            />
            {!!src.species_list && (
              <p className="mt-1 text-[11px] leading-snug text-slate-400">
                <span className="text-slate-500">Species: </span>
                {String(src.species_list)}
              </p>
            )}
            <Explainer
              text={
                "OBIS cetacean observation records aggregated per H3 cell. " +
                "Biased toward surveyed areas — high-traffic shipping lanes " +
                "may appear to have more sightings due to survey effort."
              }
            />
          </div>
        )}

        {/* ── Strike density ── */}
        {activeLayer === "strike_density" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Ship Strike Records
            </h3>
            <Metric
              label="Total strikes"
              value={(src.total_strikes as number) ?? 0}
            />
            <Metric
              label="Fatal strikes"
              value={(src.fatal_strikes as number) ?? 0}
            />
            {!!src.species_list && (
              <p className="mt-1 text-[11px] leading-snug text-slate-400">
                <span className="text-slate-500">Species: </span>
                {String(src.species_list)}
              </p>
            )}
            <Explainer
              text={
                "NOAA ship strike database — only 67 of 261 records are geocoded. " +
                "Extremely sparse: the sub-score is effectively binary. " +
                "Proximity decay spreads influence to nearby cells."
              }
            />
          </div>
        )}

        {/* ── Traffic density ── */}
        {activeLayer === "traffic_density" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Vessel Traffic
            </h3>
            <Metric
              label="Avg vessels/month"
              value={
                (src.avg_monthly_vessels as number)?.toFixed(0) ?? null
              }
            />
            <Metric
              label="Speed lethality"
              value={
                src.avg_speed_lethality != null
                  ? `${((src.avg_speed_lethality as number) * 100).toFixed(1)}%`
                  : null
              }
            />
            <Metric
              label="Avg speed"
              value={
                (src.avg_speed_knots as number)?.toFixed(1) ?? null
              }
              unit="kn"
            />
            <Metric
              label="Peak speed"
              value={
                (src.peak_speed_knots as number)?.toFixed(1) ?? null
              }
              unit="kn"
            />
            <Metric
              label="High-speed fraction"
              value={
                src.avg_high_speed_fraction != null
                  ? `${((src.avg_high_speed_fraction as number) * 100).toFixed(0)}%`
                  : null
              }
            />
            <Metric
              label="Draft risk"
              value={
                src.avg_draft_risk_fraction != null
                  ? `${((src.avg_draft_risk_fraction as number) * 100).toFixed(0)}%`
                  : null
              }
            />
            <Metric
              label="Deep-draft vessels"
              value={
                (src.avg_deep_draft_vessels as number)?.toFixed(1) ??
                null
              }
            />
            <Metric
              label="Night ratio"
              value={
                src.night_traffic_ratio != null
                  ? `${((src.night_traffic_ratio as number) * 100).toFixed(0)}%`
                  : null
              }
            />
            <Metric
              label="Night high-speed"
              value={
                (src.avg_night_high_speed as number)?.toFixed(1) ??
                null
              }
            />
            <Metric
              label="Commercial vessels"
              value={
                (src.avg_commercial_vessels as number)?.toFixed(1) ??
                null
              }
            />
            <Metric
              label="Fishing vessels"
              value={
                (src.avg_fishing_vessels as number)?.toFixed(1) ?? null
              }
            />
            <Metric
              label="Vessel length"
              value={
                (src.avg_vessel_length_m as number)?.toFixed(0) ?? null
              }
              unit="m"
            />
            <Metric
              label="COG diversity"
              value={
                (src.avg_cog_diversity as number)?.toFixed(2) ?? null
              }
              unit="rad"
            />
            <Metric
              label="Months active"
              value={(src.months_active as number) ?? null}
            />
            <Explainer
              text={
                "Seasonal averages from AIS vessel tracking. Speed lethality " +
                "uses the Vanderlaan & Taggart (2007) logistic model. " +
                "High-speed = ≥10 kn (lethal threshold). Deep draft = >8m."
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}
