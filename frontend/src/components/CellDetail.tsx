"use client";

import { useEffect, useState } from "react";
import type { LayerType, Season, SdmTimePeriod } from "@/lib/types";
import { fetchCellContext, type CellContext } from "@/lib/api";

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

/** Delta metric row: coloured ▲/▼ indicator with signed percentage. */
function DeltaMetric({
  label,
  delta,
}: {
  label: string;
  delta: number | null | undefined;
}) {
  if (delta == null) return null;
  const pct = (delta * 100).toFixed(1);
  const isPos = delta > 0.001;
  const isNeg = delta < -0.001;
  const arrow = isPos ? "▲" : isNeg ? "▼" : "–";
  const color = isPos
    ? "text-sky-400"
    : isNeg
      ? "text-red-400"
      : "text-slate-500";
  return (
    <p className="text-sm text-slate-300">
      <span className="text-slate-400">{label}: </span>
      <span className={color}>
        {arrow} {isPos ? "+" : ""}
        {pct}%
      </span>
    </p>
  );
}

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
  none: "",
  risk:
    "Composite collision risk from 7 expert-weighted sub-scores. " +
    "Each sub-score is a percentile rank (0–100%) relative to all cells in the study area.",
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
  sdm:
    "Species distribution model trained on OBIS opportunistic interaction data. " +
    "Out-of-fold spatial CV scores. Select future time periods to see CMIP6 " +
    "climate-projected habitat under SSP2-4.5 or SSP5-8.5 scenarios.",
  cetacean_density:
    "OBIS cetacean interaction records aggregated to H3 cells. " +
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
        "Three weighted components: total interaction count (50%), baleen whale interactions (30%), and recent observations since 2015 (20%).",
        "Baleen whales receive extra weight because they are the primary strike victims — large, slow-surfacing species that overlap with shipping lanes.",
        "Recent interactions are up-weighted to prioritise current population distributions over historical records.",
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
        "Whale proximity uses a 10 km half-life — risk halves every 10 km from the nearest interaction. Strike proximity uses 25 km, and protection gap uses 50 km.",
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
  if (pct >= 90) return `Extremely high ${label} — top 10% of all study-area cells.`;
  if (pct >= 75) return `High ${label} — top 25% of study-area cells.`;
  if (pct >= 50) return `Moderate ${label} — above the median for study-area cells.`;
  if (pct >= 25) return `Below average ${label} — lower quartile of study-area cells.`;
  return `Very low ${label} — bottom 25% of all study-area cells.`;
}

/* ── Expandable metric row (for traffic / ocean / bathymetry) ── */

interface MetricExpandedInfo {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  explanation: string[];
}

function MetricExpanded({ info }: { info: MetricExpandedInfo }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-lg border border-ocean-800/30 bg-abyss-800/30">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-2.5 py-2 text-xs hover:bg-abyss-800/50"
      >
        <span className="text-left text-slate-400">{info.label}</span>
        <span className="flex items-center gap-1.5">
          <strong className="text-slate-200">
            {info.value ?? "—"}
            {info.unit && info.value != null ? ` ${info.unit}` : ""}
          </strong>
          <span className="w-3 text-slate-500">
            {expanded ? "▾" : "▸"}
          </span>
        </span>
      </button>
      {expanded && (
        <div className="border-t border-ocean-800/30 px-3 pb-3 pt-2">
          <ul className="space-y-1 pl-2">
            {info.explanation.map((d, i) => (
              <li
                key={i}
                className="text-[11px] leading-snug text-slate-500 before:mr-1.5 before:text-slate-600 before:content-['•']"
              >
                {d}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ── Props ───────────────────────────────────────────────── */

/** Layers that show the species / habitat context panel. */
const CONTEXT_LAYERS: Set<LayerType> = new Set([
  "traffic_density",
  "ocean",
  "bathymetry",
  "cetacean_density",
  "strike_density",
]);

interface CellDetailProps {
  cell: Record<string, unknown>;
  detail: Record<string, unknown> | null;
  activeLayer: LayerType;
  season: Season;
  sdmTimePeriod?: SdmTimePeriod;
  onClose: () => void;
}

/* ── Component ───────────────────────────────────────────── */

export default function CellDetail({
  cell,
  detail,
  activeLayer,
  season,
  sdmTimePeriod = "current",
  onClose,
}: CellDetailProps) {
  const src = detail ?? cell;

  // Sub-scores live under a nested `scores` object in the API response
  const scores =
    (src.scores as Record<string, number> | undefined) ?? {};

  /* ── Species / habitat context (lazy-fetched) ── */
  const [cellCtx, setCellCtx] = useState<CellContext | null>(null);
  const [ctxLoading, setCtxLoading] = useState(false);
  const [ctxOpen, setCtxOpen] = useState(false);

  const h3Hex = cell.h3 as string | undefined;
  useEffect(() => {
    if (!h3Hex || !CONTEXT_LAYERS.has(activeLayer)) {
      setCellCtx(null);
      return;
    }
    const abort = new AbortController();
    setCtxLoading(true);
    const h3BigInt = BigInt("0x" + h3Hex).toString();
    const seasonStr =
      season && season !== "all" ? season : undefined;
    fetchCellContext(h3BigInt, seasonStr, abort.signal)
      .then((ctx) => {
        setCellCtx(ctx);
        setCtxLoading(false);
      })
      .catch(() => {
        if (!abort.signal.aborted) {
          setCellCtx(null);
          setCtxLoading(false);
        }
      });
    return () => abort.abort();
  }, [h3Hex, activeLayer, season]);

  return (
    <div className="glass-panel-strong absolute right-4 top-20 z-10 w-80 max-h-[calc(100vh-12rem)] overflow-y-auto rounded-xl shadow-ocean-lg">
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
            {/* Projected risk badge */}
            {activeLayer === "risk_ml" && !!src.scenario && !!src.decade && (
              <div className="flex items-center gap-2 mb-2">
                <span className="inline-flex items-center rounded-full bg-amber-500/20 px-2.5 py-0.5 text-[10px] font-semibold text-amber-300 ring-1 ring-amber-500/30">
                  {String(src.scenario).toUpperCase()} · {String(src.decade)}
                </span>
                {src.delta_risk_score != null && (
                  <span className={`text-xs font-mono ${
                    (src.delta_risk_score as number) > 0
                      ? "text-rose-400"
                      : (src.delta_risk_score as number) < 0
                        ? "text-sky-400"
                        : "text-slate-400"
                  }`}>
                    {"Δ"}{(src.delta_risk_score as number) > 0 ? "+" : ""}
                    {((src.delta_risk_score as number) * 100).toFixed(1)}{"pp"}
                  </span>
                )}
              </div>
            )}
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
            <Explainer
              text={
                "GEBCO ocean depth sampled at H3 cell centres and vertices. " +
                "Tap any metric below to learn what it means for whale habitat."
              }
            />
            <MetricExpanded
              info={{
                label: "Depth",
                value: (src.depth_m as number)?.toFixed(0) ?? null,
                unit: "m",
                explanation: [
                  "Ocean depth in metres below sea level at the cell centre, " +
                  "sampled from the GEBCO 2023 global bathymetric grid (15 arc-second resolution).",
                  "Depth controls which prey species are accessible — baleen whales " +
                  "feed in shallow to mid-depth waters (0–500 m) where krill and " +
                  "schooling fish concentrate.",
                  "Sperm whales prefer deep water (>1000 m) near continental slopes " +
                  "where deep-sea squid are found.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Depth zone",
                value: (src.depth_zone as string) ?? null,
                explanation: [
                  "Classified into 5 zones: shallow (0–200 m), shelf (200–1000 m), " +
                  "bathyal (1000–3000 m), abyssal (3000–6000 m), and hadal (>6000 m).",
                  "Shallow and shelf zones overlap most with shipping lanes, " +
                  "creating the highest strike risk where whale feeding grounds " +
                  "intersect with vessel routes.",
                  "The shelf break (~200 m contour) is a critical ecological " +
                  "boundary where upwelling concentrates nutrients and prey.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Continental shelf",
                value: src.is_continental_shelf ? "✓ Yes" : "✗ No",
                explanation: [
                  "Whether the cell falls on the continental shelf (depth ≤ 200 m).",
                  "The continental shelf is the submerged edge of a continent, " +
                  "extending from the coastline to the shelf break. These " +
                  "shallow, nutrient-rich waters support high biological " +
                  "productivity and are key feeding grounds for baleen whales.",
                  "Most commercial shipping also transits shelf waters — making " +
                  "the shelf a primary zone for whale–vessel encounters.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Shelf edge",
                value: src.is_shelf_edge ? "✓ Yes" : "✗ No",
                explanation: [
                  "Whether the cell falls on the shelf edge (depth 200–1000 m).",
                  "The shelf edge is a productivity hotspot where upwelling of " +
                  "deep, nutrient-rich water concentrates prey. Baleen whales " +
                  "— especially right, fin, and humpback whales — aggregate " +
                  "here to feed on dense patches of copepods and krill.",
                  "This zone receives 80% of the habitat sub-score weight in " +
                  "the composite risk model because of its outsized importance " +
                  "for cetacean habitat suitability.",
                ],
              }}
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
            <Explainer
              text={
                "Copernicus satellite-derived ocean variables averaged by " +
                "season (2019–2024 climatology). Tap any metric for details."
              }
            />
            <MetricExpanded
              info={{
                label: "Sea Surface Temp (SST)",
                value: (src.sst as number)?.toFixed(1) ?? null,
                unit: "°C",
                explanation: [
                  "Mean sea surface temperature from Copernicus OSTIA satellite " +
                  "analysis. Seasonal climatology averaged across 2019–2024.",
                  "SST fronts — sharp temperature gradients — concentrate prey " +
                  "and are strong predictors of baleen whale presence. " +
                  "The ISDM models rank SST in the top 3 features for all species.",
                  "Typical study-area range: ~10 °C (winter, northern waters) " +
                  "to ~28 °C (summer, Gulf/Caribbean).",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "SST Std. Deviation",
                value: (src.sst_sd as number)?.toFixed(2) ?? null,
                unit: "°C",
                explanation: [
                  "Standard deviation of SST within the grid cell, capturing " +
                  "thermal variability. High values indicate SST fronts.",
                  "Frontal zones with high SST variability aggregate " +
                  "phytoplankton, which attracts zooplankton and the fish " +
                  "and krill that whales feed on.",
                  "Values above ~1.5 °C often mark productive " +
                  "shelf-break fronts and eddies.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Mixed Layer Depth (MLD)",
                value: (src.mld as number)?.toFixed(1) ?? null,
                unit: "m",
                explanation: [
                  "Depth of the ocean's surface mixed layer — the upper zone " +
                  "of uniform temperature and salinity stirred by wind and waves.",
                  "Shallow MLD (<30 m) traps nutrients and phytoplankton near " +
                  "the surface, boosting primary productivity and prey density " +
                  "for foraging whales.",
                  "Seasonal range: ~10 m (summer, stratified) to ~60 m (winter, " +
                  "deep mixing). Deep winter MLD can disperse prey, reducing " +
                  "whale foraging efficiency.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Sea Level Anomaly (SLA)",
                value: (src.sla as number)?.toFixed(3) ?? null,
                unit: "m",
                explanation: [
                  "Deviation of sea surface height from the long-term mean. " +
                  "Measured by satellite altimetry (Copernicus SEALEVEL).",
                  "Positive SLA indicates warm-core anticyclonic eddies; " +
                  "negative SLA indicates cold-core cyclonic eddies that upwell " +
                  "nutrients to the surface.",
                  "Cyclonic eddies (negative SLA) are associated with higher " +
                  "primary productivity and prey concentration — areas where " +
                  "whales are more likely to forage.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Primary Productivity (PP)",
                value:
                  (src.pp_upper_200m as number)?.toFixed(2) ?? null,
                unit: "mg C/m²/day",
                explanation: [
                  "Net primary productivity in the upper 200 m — the rate at " +
                  "which phytoplankton convert CO₂ into organic carbon via " +
                  "photosynthesis. From Copernicus biogeochemistry models.",
                  "PP is the base of the marine food web. High PP areas support " +
                  "dense zooplankton (copepods, krill) — the primary prey of " +
                  "baleen whales. Ranked 5th–6th in ISDM feature importance.",
                  "PP receives 20% weight in the habitat sub-score of the " +
                  "standard risk model. The remaining 80% comes from " +
                  "bathymetric features (shelf edge, continental shelf).",
                ],
              }}
            />
          </div>
        )}

        {/* ── Whale predictions (ISDM) — current or projected ── */}
        {activeLayer === "whale_predictions" && sdmTimePeriod === "current" && (
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
                "XGBoost models trained on expert-curated presence/absence data " +
                "(Nisi et al. 2024) with 7 environmental covariates. " +
                "P(any) = 1 − ∏(1 − Pᵢ) treats all species equally."
              }
            />
          </div>
        )}

        {activeLayer === "whale_predictions" && sdmTimePeriod !== "current" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Projected ISDM Habitat · {sdmTimePeriod}
            </h3>
            {!!src.season && (
              <p className="text-xs text-ocean-400">
                Season: <strong>{String(src.season)}</strong>
              </p>
            )}
            {!!src.scenario && (
              <p className="text-xs text-amber-400/80">
                {String(src.scenario).toUpperCase()} · {String(src.decade)}
              </p>
            )}
            <Metric
              label="P(any whale)"
              value={`${(((src.isdm_any_whale as number) ?? 0) * 100).toFixed(1)}%`}
            />
            {/* Delta values (change mode) */}
            {src.delta_any_whale != null && (
              <>
                <div className="mt-2 border-t border-ocean-800/20 pt-2">
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Change vs Baseline
                  </p>
                  <DeltaMetric label="Any whale" delta={src.delta_any_whale as number} />
                  <DeltaMetric label="Blue whale" delta={src.delta_blue_whale as number} />
                  <DeltaMetric label="Fin whale" delta={src.delta_fin_whale as number} />
                  <DeltaMetric label="Humpback" delta={src.delta_humpback_whale as number} />
                  <DeltaMetric label="Sperm whale" delta={src.delta_sperm_whale as number} />
                </div>
              </>
            )}
            {/* Absolute species breakdown */}
            {src.delta_any_whale == null && (
              <div className="mt-1 space-y-0.5 pl-2 text-xs text-slate-400">
                <p>Blue whale: <span className="text-slate-300">{(((src.isdm_blue_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
                <p>Fin whale: <span className="text-slate-300">{(((src.isdm_fin_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
                <p>Humpback: <span className="text-slate-300">{(((src.isdm_humpback_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
                <p>Sperm whale: <span className="text-slate-300">{(((src.isdm_sperm_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
              </div>
            )}
          </div>
        )}

        {/* ── Species Distribution (SDM) — current or projected ── */}
        {activeLayer === "sdm" && sdmTimePeriod === "current" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              SDM Whale Predictions
            </h3>
            {!!src.season && (
              <p className="text-xs text-ocean-400">
                Season: <strong>{String(src.season)}</strong>
              </p>
            )}
            <Metric
              label="P(any whale) — SDM"
              value={`${(((src.sdm_any_whale as number) ?? 0) * 100).toFixed(1)}%`}
            />
            <Metric
              label="P(any) — joint"
              value={
                src.any_whale_prob_joint != null
                  ? `${(((src.any_whale_prob_joint as number)) * 100).toFixed(1)}%`
                  : null
              }
            />
            <Metric
              label="Max species P"
              value={
                src.max_whale_prob != null
                  ? `${(((src.max_whale_prob as number)) * 100).toFixed(1)}%`
                  : null
              }
            />
            <Metric
              label="Mean species P"
              value={
                src.mean_whale_prob != null
                  ? `${(((src.mean_whale_prob as number)) * 100).toFixed(1)}%`
                  : null
              }
            />
            <div className="mt-1 space-y-0.5 pl-2 text-xs text-slate-400">
              <p>
                Blue whale:{" "}
                <span className="text-slate-300">
                  {(((src.sdm_blue_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
              <p>
                Fin whale:{" "}
                <span className="text-slate-300">
                  {(((src.sdm_fin_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
              <p>
                Humpback:{" "}
                <span className="text-slate-300">
                  {(((src.sdm_humpback_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
              <p>
                Sperm whale:{" "}
                <span className="text-slate-300">
                  {(((src.sdm_sperm_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
              <p>
                Right whale:{" "}
                <span className="text-slate-300">
                  {(((src.sdm_right_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
              <p>
                Minke whale:{" "}
                <span className="text-slate-300">
                  {(((src.sdm_minke_whale as number) ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
            </div>
            <Explainer
              text={
                "XGBoost models trained on OBIS opportunistic interaction data " +
                "with 7 environmental covariates. Out-of-fold spatial CV scores — " +
                "comparable to ISDM but uses different training data (observer " +
                "reports vs expert-curated presence/absence)."
              }
            />
          </div>
        )}

        {activeLayer === "sdm" && sdmTimePeriod !== "current" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Projected Habitat · {sdmTimePeriod}
            </h3>
            {!!src.season && (
              <p className="text-xs text-ocean-400">
                Season: <strong>{String(src.season)}</strong>
              </p>
            )}
            {!!src.scenario && (
              <p className="text-xs text-amber-400/80">
                {String(src.scenario).toUpperCase()} · {String(src.decade)}
              </p>
            )}
            <Metric
              label="P(any whale)"
              value={`${(((src.sdm_any_whale as number) ?? 0) * 100).toFixed(1)}%`}
            />
            {/* Delta values (change mode) */}
            {src.delta_any_whale != null && (
              <>
                <div className="mt-2 border-t border-ocean-800/20 pt-2">
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Change vs Baseline
                  </p>
                  <DeltaMetric label="Any whale" delta={src.delta_any_whale as number} />
                  <DeltaMetric label="Blue whale" delta={src.delta_blue_whale as number} />
                  <DeltaMetric label="Fin whale" delta={src.delta_fin_whale as number} />
                  <DeltaMetric label="Humpback" delta={src.delta_humpback_whale as number} />
                  <DeltaMetric label="Sperm whale" delta={src.delta_sperm_whale as number} />
                  <DeltaMetric label="Right whale" delta={src.delta_right_whale as number} />
                  <DeltaMetric label="Minke whale" delta={src.delta_minke_whale as number} />
                </div>
              </>
            )}
            {/* Absolute species breakdown */}
            {src.delta_any_whale == null && (
              <div className="mt-1 space-y-0.5 pl-2 text-xs text-slate-400">
                <p>Blue whale: <span className="text-slate-300">{(((src.sdm_blue_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
                <p>Fin whale: <span className="text-slate-300">{(((src.sdm_fin_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
                <p>Humpback: <span className="text-slate-300">{(((src.sdm_humpback_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
                <p>Sperm whale: <span className="text-slate-300">{(((src.sdm_sperm_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
                <p>Right whale: <span className="text-slate-300">{(((src.sdm_right_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
                <p>Minke whale: <span className="text-slate-300">{(((src.sdm_minke_whale as number) ?? 0) * 100).toFixed(1)}%</span></p>
              </div>
            )}
          </div>
        )}

        {/* ── Cetacean density ── */}
        {activeLayer === "cetacean_density" && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Cetacean Interactions
            </h3>
            {!!src.season && (
              <p className="text-xs text-ocean-400">
                Season: <strong>{String(src.season)}</strong>
              </p>
            )}
            <Metric
              label="Total interactions"
              value={(src.total_sightings as number) ?? 0}
            />
            <Metric
              label="Unique species"
              value={(src.unique_species as number) ?? undefined}
            />
            <Metric
              label="Baleen interactions"
              value={(src.baleen_sightings as number) ?? undefined}
            />
            <Metric
              label="Recent interactions"
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
                "may appear to have more interactions due to survey effort."
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
            <Explainer
              text={
                "Seasonal averages from AIS vessel tracking data. " +
                "Tap any metric to see how it relates to strike risk."
              }
            />
            <MetricExpanded
              info={{
                label: "Avg vessels / month",
                value:
                  (src.avg_monthly_vessels as number)?.toFixed(0) ??
                  null,
                explanation: [
                  "Mean number of unique vessels transiting through this H3 cell " +
                  "per month, averaged across all months in the selected season.",
                  "Higher vessel counts increase the probability of whale–vessel " +
                  "encounters. Volume contributes ~15% of the traffic sub-score " +
                  "in the composite risk model.",
                  "Does not distinguish vessel size — a kayak and a container " +
                  "ship both count as one. Size is captured separately by " +
                  "draft risk and vessel length metrics.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Speed lethality",
                value:
                  src.avg_speed_lethality != null
                    ? `${((src.avg_speed_lethality as number) * 100).toFixed(1)}%`
                    : null,
                explanation: [
                  "Probability of lethal injury given a collision, computed " +
                  "using the Vanderlaan & Taggart (2007) logistic model: " +
                  "P(lethal) = 1 / (1 + e^(−(β₀ + β₁·speed))).",
                  "This is the single most important predictor of strike " +
                  "mortality. At 10 knots the probability is ~40%; at 15 knots " +
                  "it jumps to ~80%; above 18 knots it's nearly certain.",
                  "The V&T lethality model was calibrated on 292 documented " +
                  "whale–vessel collisions and is the standard reference in " +
                  "speed-reduction rulemaking (NOAA, IMO).",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Avg speed",
                value:
                  (src.avg_speed_knots as number)?.toFixed(1) ?? null,
                unit: "kn",
                explanation: [
                  "Mean speed over ground (SOG) of all AIS-transmitting " +
                  "vessels in this cell during the selected season.",
                  "Average speed contextualises the lethality score. A cell " +
                  "with high lethality but low average speed may have a few " +
                  "very fast vessels pulling up the mean, while one with " +
                  "moderate lethality and high average speed indicates " +
                  "uniformly fast traffic.",
                  "NOAA 10-knot speed restrictions in SMAs and DMAs target " +
                  "average vessel speeds to reduce lethal collision risk.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Peak speed",
                value:
                  (src.peak_speed_knots as number)?.toFixed(1) ?? null,
                unit: "kn",
                explanation: [
                  "Maximum recorded speed over ground in this cell during " +
                  "the selected season.",
                  "Peak speed captures worst-case lethality — even if " +
                  "average speeds are moderate, occasional high-speed " +
                  "transits (e.g. ferries, military vessels) can be lethal.",
                  "Cells with peak speeds >20 knots have near-100% strike " +
                  "lethality for large whale encounters.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "High-speed fraction",
                value:
                  src.avg_high_speed_fraction != null
                    ? `${((src.avg_high_speed_fraction as number) * 100).toFixed(0)}%`
                    : null,
                explanation: [
                  "Fraction of vessel transits exceeding 10 knots — the " +
                  "speed threshold above which strike lethality rises steeply.",
                  "The 10-knot threshold comes from the V&T (2007) logistic " +
                  "curve inflection point. Below 10 kn, lethality is <40%; " +
                  "above 10 kn, it rises sharply toward certainty.",
                  "This metric is the most actionable for management — it " +
                  "directly measures compliance with voluntary and mandatory " +
                  "speed-restriction zones.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Draft risk fraction",
                value:
                  src.avg_draft_risk_fraction != null
                    ? `${((src.avg_draft_risk_fraction as number) * 100).toFixed(0)}%`
                    : null,
                explanation: [
                  "Fraction of vessels with a draft exceeding 8 metres, " +
                  "indicating deep-draught ships (tankers, bulk carriers, " +
                  "large container ships).",
                  "Deep-draught vessels pose elevated risk because their " +
                  "propellers and bulbous bows extend into the water column " +
                  "where whales swim, increasing the probability and severity " +
                  "of sub-surface strikes.",
                  "These vessels also have the longest stopping distances and " +
                  "poorest manoeuvrability, making evasive action impossible.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Deep-draft vessels",
                value:
                  (src.avg_deep_draft_vessels as number)?.toFixed(1) ??
                  null,
                explanation: [
                  "Average number of vessels per month with draft >8 m " +
                  "transiting this cell.",
                  "Separates out the absolute count of dangerous large " +
                  "vessels from the fraction. A cell might have a low draft " +
                  "risk fraction but still see many deep-draft transits " +
                  "if total traffic is very high.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Night traffic ratio",
                value:
                  src.night_traffic_ratio != null
                    ? `${((src.night_traffic_ratio as number) * 100).toFixed(0)}%`
                    : null,
                explanation: [
                  "Fraction of vessel transits occurring between sunset and " +
                  "sunrise (based on vessel timestamp and cell latitude).",
                  "Night-time operations reduce visual whale detection by " +
                  "bridge watchkeepers to near zero. Thermal cameras and " +
                  "radar have limited effectiveness for whale detection.",
                  "Cells with >50% night traffic rely entirely on " +
                  "passive acoustic monitoring or pre-voyage whale alerts " +
                  "for collision avoidance.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Night high-speed",
                value:
                  (src.avg_night_high_speed as number)?.toFixed(1) ??
                  null,
                explanation: [
                  "Average number of vessels per month exceeding 10 knots " +
                  "at night in this cell.",
                  "The most dangerous combination: high-speed transits in " +
                  "darkness when whale detection is impossible. These events " +
                  "represent the highest per-transit strike risk.",
                  "This metric identifies cells where targeted speed " +
                  "restrictions during night hours would have the greatest " +
                  "impact on reducing lethal strikes.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Commercial vessels",
                value:
                  (src.avg_commercial_vessels as number)?.toFixed(1) ??
                  null,
                explanation: [
                  "Average monthly count of commercial-class vessels " +
                  "(cargo, tanker, passenger, vehicle carriers).",
                  "Commercial vessels are the primary strike threat — they " +
                  "are large, fast, and operate on fixed schedules with " +
                  "limited ability to alter routes for whale avoidance.",
                  "Commercial traffic is distinguished from fishing, " +
                  "recreational, and military vessels using AIS vessel " +
                  "type codes (70–89 in ITU-R M.1371-5).",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Fishing vessels",
                value:
                  (src.avg_fishing_vessels as number)?.toFixed(1) ??
                  null,
                explanation: [
                  "Average monthly count of fishing vessels (AIS type code 30).",
                  "Fishing vessels pose lower direct strike risk than " +
                  "commercial ships (slower speeds, smaller size), but they " +
                  "contribute to entanglement risk which is not modelled here.",
                  "Fishing activity also serves as a proxy for productive " +
                  "waters — areas with high fishing effort often overlap " +
                  "with whale feeding grounds.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Vessel length",
                value:
                  (src.avg_vessel_length_m as number)?.toFixed(0) ??
                  null,
                unit: "m",
                explanation: [
                  "Mean overall length of vessels transiting this cell, " +
                  "in metres. Derived from AIS static messages.",
                  "Larger vessels have greater mass and kinetic energy — " +
                  "a 300 m container ship at 15 kn has ~100× the momentum " +
                  "of a 30 m fishing boat at the same speed.",
                  "Vessel length also correlates with draft depth, wake " +
                  "intensity, and underwater noise — all of which affect " +
                  "whales beyond direct collision risk.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "COG diversity",
                value:
                  (src.avg_cog_diversity as number)?.toFixed(2) ?? null,
                unit: "rad",
                explanation: [
                  "Circular standard deviation of vessel course over ground " +
                  "(COG), in radians. Measures directional diversity of " +
                  "traffic through this cell.",
                  "Low COG diversity (~0.5 rad) indicates a one-way shipping " +
                  "lane. High diversity (>1.5 rad) indicates multi-directional " +
                  "traffic (port approaches, fishing grounds, crossing zones).",
                  "Multi-directional traffic makes whale avoidance harder — " +
                  "animals cannot predict vessel approach direction and may " +
                  "dodge one ship into the path of another.",
                ],
              }}
            />
            <MetricExpanded
              info={{
                label: "Months active",
                value: (src.months_active as number) ?? null,
                explanation: [
                  "Number of distinct months with at least one vessel " +
                  "transit recorded in this cell.",
                  "Cells active 12/12 months are permanent shipping lanes. " +
                  "Cells active only 3–6 months may be seasonal routes " +
                  "(e.g. Alaska summer tourism, seasonal fisheries).",
                  "Seasonal variation in traffic is a key input to the " +
                  "seasonal risk model — cells with winter-only traffic " +
                  "may coincide with right whale calving migrations.",
                ],
              }}
            />
          </div>
        )}

        {/* ── Species & Habitat Context (traffic / ocean / bathymetry / etc.) ── */}
        {CONTEXT_LAYERS.has(activeLayer) && (
          <div className="border-t border-ocean-800/30 pt-3">
            <button
              onClick={() => setCtxOpen((v) => !v)}
              className="flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-200"
            >
              <span>Species &amp; Habitat at this Cell</span>
              <span className="text-slate-500">
                {ctxOpen ? "▾" : "▸"}
              </span>
            </button>

            {ctxOpen && (
              <div className="mt-2 space-y-3">
                {ctxLoading && (
                  <p className="text-[11px] text-slate-500 animate-pulse">
                    Loading context…
                  </p>
                )}

                {!ctxLoading && cellCtx && (
                  <>
                    {/* ── Whale presence probabilities ── */}
                    {cellCtx.any_whale_prob != null && (
                      <div className="space-y-1">
                        <p className="text-[11px] font-semibold text-slate-400">
                          ISDM Whale Predictions
                          {season && season !== "all"
                            ? ` (${season})`
                            : ""}
                        </p>
                        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 pl-1 text-[11px]">
                          <span className="text-slate-500">P(any whale)</span>
                          <span className="text-slate-200 font-medium">
                            {((cellCtx.any_whale_prob ?? 0) * 100).toFixed(1)}%
                          </span>
                          <span className="text-slate-500">Blue whale</span>
                          <span className="text-slate-200">
                            {((cellCtx.isdm_blue_whale ?? 0) * 100).toFixed(1)}%
                          </span>
                          <span className="text-slate-500">Fin whale</span>
                          <span className="text-slate-200">
                            {((cellCtx.isdm_fin_whale ?? 0) * 100).toFixed(1)}%
                          </span>
                          <span className="text-slate-500">Humpback</span>
                          <span className="text-slate-200">
                            {((cellCtx.isdm_humpback_whale ?? 0) * 100).toFixed(1)}%
                          </span>
                          <span className="text-slate-500">Sperm whale</span>
                          <span className="text-slate-200">
                            {((cellCtx.isdm_sperm_whale ?? 0) * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    )}

                    {/* ── Observed species ── */}
                    {cellCtx.species_observed && (
                      <div>
                        <p className="text-[11px] font-semibold text-slate-400">
                          Species Observed (OBIS)
                        </p>
                        <p className="mt-0.5 text-[11px] leading-snug text-slate-300">
                          {cellCtx.species_observed}
                        </p>
                      </div>
                    )}

                    {/* ── BIA zones ── */}
                    {cellCtx.bia_zones.length > 0 && (
                      <div>
                        <p className="text-[11px] font-semibold text-teal-400">
                          ⬢ Biologically Important Area
                        </p>
                        {cellCtx.bia_zones.map((z, i) => (
                          <p
                            key={i}
                            className="mt-0.5 pl-2 text-[11px] text-slate-300"
                          >
                            <span className="text-slate-400">
                              {z.type}:
                            </span>{" "}
                            {z.species}
                          </p>
                        ))}
                      </div>
                    )}

                    {/* ── Critical Habitat ── */}
                    {cellCtx.critical_habitat.length > 0 && (
                      <div>
                        <p className="text-[11px] font-semibold text-purple-400">
                          ◆ ESA Critical Habitat
                        </p>
                        {cellCtx.critical_habitat.map((z, i) => (
                          <p
                            key={i}
                            className="mt-0.5 pl-2 text-[11px] text-slate-300"
                          >
                            {z.species}{" "}
                            <span className="text-slate-500">
                              ({z.status})
                            </span>
                          </p>
                        ))}
                      </div>
                    )}

                    {/* ── Nothing found ── */}
                    {cellCtx.any_whale_prob == null &&
                      !cellCtx.species_observed &&
                      cellCtx.bia_zones.length === 0 &&
                      cellCtx.critical_habitat.length === 0 && (
                        <p className="text-[11px] text-slate-500">
                          No whale predictions, sightings, or habitat
                          designations found for this cell.
                        </p>
                      )}
                  </>
                )}

                {!ctxLoading && !cellCtx && (
                  <p className="text-[11px] text-slate-500">
                    Context unavailable for this cell.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
