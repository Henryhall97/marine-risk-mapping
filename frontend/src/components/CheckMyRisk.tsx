"use client";

import { useState, useCallback, useRef } from "react";
import { fetchNearestRisk } from "@/lib/api";
import { IconPin, IconGlobe, IconWaves } from "@/components/icons/MarineIcons";

/* ── Types ───────────────────────────────────────────────── */

interface RiskResult {
  h3_cell: string;
  cell_lat: number;
  cell_lon: number;
  risk_score: number;
  risk_category: string;
  scores: {
    traffic_score: number;
    cetacean_score: number;
    proximity_score: number;
    strike_score: number;
    habitat_score: number;
    protection_gap: number;
    reference_risk_score: number;
  };
  depth_m: number | null;
  depth_zone: string | null;
  is_continental_shelf: boolean | null;
  sst: number | null;
  sst_sd: number | null;
  mld: number | null;
  sla: number | null;
  pp_upper_200m: number | null;
}

export interface CheckMyRiskProps {
  /** Called when user submits coordinates — parent zooms the map.
   *  When the matched cell differs from the query, cellLat/cellLon
   *  identify the risk cell's position. */
  onLocate: (
    queryLat: number,
    queryLon: number,
    cellLat?: number,
    cellLon?: number,
  ) => void;
  /** Close the panel. */
  onClose: () => void;
}

/* ── Expandable sub-score bar (mirrors CellDetail) ───────── */

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
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-xs hover:bg-abyss-800/50"
      >
        <span className="w-20 truncate text-left text-slate-400">
          {info.label}
        </span>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-abyss-700">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              backgroundColor: `hsl(${hue}, 80%, 50%)`,
            }}
          />
        </div>
        <span className="w-9 text-right tabular-nums text-slate-300">
          {pct}%
        </span>
        <span className="w-3 text-slate-500">{expanded ? "▾" : "▸"}</span>
      </button>

      {expanded && (
        <div className="border-t border-ocean-800/30 px-3 pb-2.5 pt-2">
          <div className="mb-1.5 flex items-center gap-2">
            <span className="rounded-full bg-abyss-700 px-2 py-0.5 text-[10px] font-bold text-slate-400">
              {info.weight} weight
            </span>
            <span className="text-[10px] text-slate-500">
              {info.shortDesc}
            </span>
          </div>
          <ul className="mb-1.5 space-y-0.5 pl-3">
            {info.details.map((d, i) => (
              <li
                key={i}
                className="text-[10px] leading-snug text-slate-500 before:mr-1 before:text-slate-600 before:content-['•']"
              >
                {d}
              </li>
            ))}
          </ul>
          <p className="rounded-md bg-abyss-800/60 px-2 py-1 text-[10px] italic leading-snug text-slate-400">
            {info.interpretation}
          </p>
        </div>
      )}
    </div>
  );
}

/* ── Interpretation helper ───────────────────────────────── */

function pctInterpretation(value: number, label: string): string {
  const pct = Math.round(value * 100);
  if (pct >= 90)
    return `Extremely high ${label} — top 10% of all study-area cells.`;
  if (pct >= 75)
    return `High ${label} — top 25% of study-area cells.`;
  if (pct >= 50)
    return `Moderate ${label} — above the median for study-area cells.`;
  if (pct >= 25)
    return `Below average ${label} — lower quartile of study-area cells.`;
  return `Very low ${label} — bottom 25% of all study-area cells.`;
}

/* ── Build sub-score infos (same content as CellDetail) ─── */

function buildSubScoreInfos(
  scores: RiskResult["scores"],
): SubScoreInfo[] {
  return [
    {
      label: "Traffic",
      value: scores.traffic_score,
      weight: "25%",
      shortDesc: "Vessel traffic intensity",
      details: [
        "Combines 8 components: V&T speed-dependent lethality, vessel draft risk, traffic volume, large vessel fraction, night-time ratio, and vessel type diversity.",
        "V&T lethality models the probability of lethal injury as a logistic function of vessel speed — the single most important predictor of strike mortality.",
        "Draft risk captures deep-draught vessels (tankers, bulk carriers) whose propellers extend into whale habitat depth.",
      ],
      interpretation: pctInterpretation(
        scores.traffic_score,
        "traffic intensity",
      ),
    },
    {
      label: "Cetacean",
      value: scores.cetacean_score,
      weight: "25%",
      shortDesc: "Cetacean presence density",
      details: [
        "Three components: total sighting count (50%), baleen whale sightings (30%), and recent observations since 2015 (20%).",
        "Baleen whales receive extra weight because they are the primary strike victims — large, slow-surfacing species.",
        "Recent sightings are up-weighted to prioritise current population distributions over historical records.",
      ],
      interpretation: pctInterpretation(
        scores.cetacean_score,
        "cetacean presence",
      ),
    },
    {
      label: "Proximity",
      value: scores.proximity_score,
      weight: "15%",
      shortDesc: "Distance-decay from risk features",
      details: [
        "Blends three exponential decay distances: whale × ship co-occurrence (45%), nearest ship strike (30%), and distance to unprotected waters (25%).",
        "Whale proximity uses a 10 km half-life. Strike proximity uses 25 km, and protection gap uses 50 km.",
        "Captures spatial gradients around features — complements density which measures magnitude at a point.",
      ],
      interpretation: pctInterpretation(
        scores.proximity_score,
        "proximity risk",
      ),
    },
    {
      label: "Strike",
      value: scores.strike_score,
      weight: "10%",
      shortDesc: "Historical ship strike records",
      details: [
        "Based on NOAA ship strike database — only 67 of 261 records are geocoded, making this score effectively binary for most cells.",
        "Three components: total strikes (40%), fatal strikes (30%), large whale strikes (30%).",
        "Proximity decay (half-life 25 km) spreads influence to nearby cells.",
      ],
      interpretation:
        scores.strike_score > 0
          ? "This cell has recorded ship strikes or is near cells with strike history."
          : "No recorded strikes in or near this cell. 99.99% of cells score zero.",
    },
    {
      label: "Habitat",
      value: scores.habitat_score,
      weight: "10%",
      shortDesc: "Habitat suitability for cetaceans",
      details: [
        "Bathymetry contributes 80%: continental shelf edge (200–1000 m) scores highest because upwelling concentrates prey.",
        "Primary productivity (PP) contributes 20%: high PP indicates productive waters that attract whales.",
        "Three bathymetric sub-zones: shelf (<200 m), edge (200–1000 m, highest), and deep (>1000 m, lowest).",
      ],
      interpretation: pctInterpretation(
        scores.habitat_score,
        "habitat suitability",
      ),
    },
    {
      label: "Protection",
      value: scores.protection_gap,
      weight: "10%",
      shortDesc: "Absence of enforceable protection",
      details: [
        "Tiered: no-take zones (best, 0.10) → strict MPAs (0.25–0.35) → any MPA (0.60) → SMA only (0.80) → unprotected (1.0).",
        "SMAs are voluntary — compliance is low (~5%), so they provide only a small bonus over unprotected waters.",
        "Proposed speed zones are excluded — they signal recognised risk, not actual protection.",
      ],
      interpretation:
        scores.protection_gap >= 0.8
          ? "Little or no enforceable protection. Open waters or voluntary speed advisories only."
          : scores.protection_gap <= 0.2
            ? "Strong enforceable protection — likely within or near a no-take marine reserve."
            : "Moderate protection — covered by some form of MPA, but not the strongest designation.",
    },
    {
      label: "Reference",
      value: scores.reference_risk_score,
      weight: "5%",
      shortDesc: "Nisi et al. 2024 global baseline",
      details: [
        "1-degree resolution global ship-strike risk grid from Nisi et al. 2024.",
        "Provides a coarse independent baseline for areas where fine-grained data is sparse.",
        "Low weight (5%) because our own sub-scores provide much higher spatial resolution.",
      ],
      interpretation: pctInterpretation(
        scores.reference_risk_score,
        "Nisi reference risk",
      ),
    },
  ];
}

/* ── Environment covariate definitions ───────────────────── */

interface SpeciesRange {
  name: string;
  min: number;
  max: number;
  note: string;
}

interface CovariateDef {
  label: string;
  key: keyof RiskResult;
  unit: string;
  decimals: number;
  why: string;
  /** Whale-significant range: [min, max, description]. */
  whaleRange: [number, number, string];
  /** Per-species preferred ranges for this covariate. */
  speciesRanges: SpeciesRange[];
}

const COVARIATES: CovariateDef[] = [
  {
    label: "Depth",
    key: "depth_m",
    unit: "m",
    decimals: 0,
    why: "Ocean depth determines habitat type. The continental shelf edge (200–1000 m) concentrates prey through upwelling, making it a cetacean hotspot.",
    whaleRange: [
      -1000,
      -20,
      "20–1000 m: Most baleen whales feed on the continental " +
        "shelf (<200 m) or shelf edge (200–1000 m). " +
        "Sperm whales dive deeper (>1000 m) for squid.",
    ],
    speciesRanges: [
      { name: "Right whale", min: -80, max: -20, note: "Shallow shelf, copepod aggregations" },
      { name: "Humpback", min: -200, max: -40, note: "Shelf to upper slope, krill & fish" },
      { name: "Fin whale", min: -500, max: -50, note: "Shelf edge & slope, krill swarms" },
      { name: "Blue whale", min: -500, max: -100, note: "Shelf edge upwelling zones" },
      { name: "Sei whale", min: -300, max: -50, note: "Outer shelf, copepods & small fish" },
      { name: "Minke whale", min: -200, max: -20, note: "Shelf waters, fish & krill" },
      { name: "Sperm whale", min: -3000, max: -500, note: "Deep slope & canyon, squid" },
    ],
  },
  {
    label: "SST",
    key: "sst",
    unit: "°C",
    decimals: 1,
    why: "Sea surface temperature drives prey distribution. Thermal fronts — boundaries between warm and cold water — aggregate plankton and fish that whales follow.",
    whaleRange: [
      6,
      22,
      "6–22 °C: Thermal fronts (sharp SST gradients) " +
        "are especially important for concentrating prey.",
    ],
    speciesRanges: [
      { name: "Right whale", min: 6, max: 16, note: "Cool temperate, Cape Cod to SE US" },
      { name: "Humpback", min: 10, max: 22, note: "Wide range, seasonal migration" },
      { name: "Fin whale", min: 8, max: 18, note: "Sub-polar fronts & upwelling" },
      { name: "Blue whale", min: 10, max: 17, note: "Cool upwelling zones" },
      { name: "Sei whale", min: 8, max: 18, note: "Temperate frontal zones" },
      { name: "Minke whale", min: 6, max: 20, note: "Broad thermal tolerance" },
      { name: "Sperm whale", min: 15, max: 28, note: "Warm deep-water masses" },
    ],
  },
  {
    label: "SST Variability",
    key: "sst_sd",
    unit: "°C",
    decimals: 2,
    why: "High SST variability indicates dynamic frontal zones where warm and cold currents meet — these mixing zones create productive feeding areas.",
    whaleRange: [
      0.5,
      4.0,
      "0.5–4.0 °C: Higher variability signals thermal " +
        "fronts and seasonal upwelling that concentrate prey.",
    ],
    speciesRanges: [
      { name: "Right whale", min: 1.0, max: 3.5, note: "Strong fronts, Cape Cod gyre" },
      { name: "Humpback", min: 0.5, max: 3.0, note: "Moderate frontal activity" },
      { name: "Fin whale", min: 0.8, max: 3.0, note: "Shelf-edge thermal fronts" },
      { name: "Blue whale", min: 1.0, max: 4.0, note: "High variability upwelling" },
      { name: "Sei whale", min: 0.5, max: 2.5, note: "Temperate gradient zones" },
    ],
  },
  {
    label: "Mixed Layer Depth",
    key: "mld",
    unit: "m",
    decimals: 1,
    why: "MLD controls how deep surface nutrients mix. Shallow MLD keeps nutrients in the sunlit zone, fuelling phytoplankton blooms that support the food web.",
    whaleRange: [
      5,
      40,
      "5–40 m: Shallow mixed layers trap prey near the " +
        "surface where baleen whales forage most efficiently.",
    ],
    speciesRanges: [
      { name: "Right whale", min: 5, max: 25, note: "Very shallow, dense copepod layers" },
      { name: "Humpback", min: 10, max: 40, note: "Shallow to moderate, lunge feeding" },
      { name: "Fin whale", min: 10, max: 50, note: "Moderate depth, krill layers" },
      { name: "Blue whale", min: 5, max: 30, note: "Shallow MLD, concentrated krill" },
      { name: "Sei whale", min: 10, max: 35, note: "Shallow, skim-feeding copepods" },
      { name: "Minke whale", min: 10, max: 40, note: "Flexible, nearshore feeding" },
    ],
  },
  {
    label: "Sea Level Anomaly",
    key: "sla",
    unit: "m",
    decimals: 3,
    why: "SLA reveals mesoscale eddies — rotating water masses that trap and concentrate plankton. Positive SLA (anti-cyclonic eddies) often aggregate prey.",
    whaleRange: [
      -0.15,
      0.15,
      "±0.15 m: Moderate anomalies indicate mesoscale " +
        "eddies that concentrate or upwell prey.",
    ],
    speciesRanges: [
      { name: "Right whale", min: -0.15, max: -0.02, note: "Cyclonic upwelling, copepod patches" },
      { name: "Fin whale", min: -0.12, max: 0.05, note: "Cyclonic edges, krill concentration" },
      { name: "Blue whale", min: -0.15, max: 0.0, note: "Strong cyclonic upwelling" },
      { name: "Humpback", min: -0.10, max: 0.10, note: "Eddy edges, convergence zones" },
      { name: "Sperm whale", min: 0.02, max: 0.15, note: "Anti-cyclonic warm eddies, squid" },
    ],
  },
  {
    label: "Primary Productivity",
    key: "pp_upper_200m",
    unit: "mg C/m²/d",
    decimals: 1,
    why: "PP measures phytoplankton growth — the base of the marine food web. High PP areas sustain the krill and fish that baleen whales depend on. Ranks 5th–6th in ISDM feature importance.",
    whaleRange: [
      300,
      2000,
      "300–2000 mg C/m²/d: Productive waters that sustain " +
        "krill, copepods, and forage fish. Below 200 is " +
        "typically oligotrophic with little cetacean activity.",
    ],
    speciesRanges: [
      { name: "Right whale", min: 500, max: 2000, note: "Dense copepod patches required" },
      { name: "Humpback", min: 400, max: 1800, note: "Productive shelf & banks" },
      { name: "Fin whale", min: 400, max: 1500, note: "Moderately high krill areas" },
      { name: "Blue whale", min: 800, max: 2000, note: "Highly productive upwelling" },
      { name: "Sei whale", min: 300, max: 1200, note: "Moderate copepod density" },
      { name: "Minke whale", min: 300, max: 1500, note: "Flexible, shelf-productive" },
      { name: "Sperm whale", min: 200, max: 800, note: "Moderate — deep prey, not PP-dependent" },
    ],
  },
];
/* ── Coordinate / distance formatters ────────────────────── */

function formatCoord(lat: number, lon: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(1)}°${ns}, ${Math.abs(lon).toFixed(1)}°${ew}`;
}

function formatDistance(km: number): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  if (km < 10) return `${km.toFixed(1)} km`;
  return `${Math.round(km)} km`;
}
/* ── Category badge colour ───────────────────────────────── */

function categoryColor(cat: string): string {
  switch (cat.toLowerCase()) {
    case "critical":
      return "bg-red-500/20 text-red-400 border-red-500/30";
    case "high":
      return "bg-orange-500/20 text-orange-400 border-orange-500/30";
    case "medium":
      return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    case "low":
      return "bg-green-500/20 text-green-400 border-green-500/30";
    default:
      return "bg-slate-500/20 text-slate-400 border-slate-500/30";
  }
}

/* ── Risk gauge arc ──────────────────────────────────────── */

function RiskGauge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const hue = Math.round(120 - score * 120);
  const r = 42;
  const cx = 50;
  const cy = 50;
  const startRad = (-135 * Math.PI) / 180;
  const endRad = ((-135 + score * 270) * Math.PI) / 180;
  const x1 = cx + r * Math.cos(startRad);
  const y1 = cy + r * Math.sin(startRad);
  const x2 = cx + r * Math.cos(endRad);
  const y2 = cy + r * Math.sin(endRad);
  const largeArc = score > 0.5 ? 1 : 0;

  return (
    <div className="relative mx-auto h-24 w-24">
      <svg viewBox="0 0 100 100" className="h-full w-full">
        <path
          d={`M ${cx + r * Math.cos(startRad)} ${cy + r * Math.sin(startRad)} A ${r} ${r} 0 1 1 ${cx + r * Math.cos((135 * Math.PI) / 180)} ${cy + r * Math.sin((135 * Math.PI) / 180)}`}
          fill="none"
          stroke="rgba(100,116,139,0.15)"
          strokeWidth="6"
          strokeLinecap="round"
        />
        {score > 0.005 && (
          <path
            d={`M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`}
            fill="none"
            stroke={`hsl(${hue}, 80%, 50%)`}
            strokeWidth="6"
            strokeLinecap="round"
            style={{
              filter: `drop-shadow(0 0 6px hsl(${hue}, 80%, 50%, 0.4))`,
            }}
          />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pt-2">
        <span className="text-xl font-bold text-white">{pct}%</span>
        <span className="text-[10px] text-slate-500">risk score</span>
      </div>
    </div>
  );
}

/* ── Expandable environment row ──────────────────────────── */

function isInWhaleRange(
  value: number | null,
  range: [number, number, string],
): boolean | null {
  if (value == null) return null;
  return value >= range[0] && value <= range[1];
}

function speciesMatchesValue(
  value: number | null,
  ranges: SpeciesRange[],
): { matched: SpeciesRange[]; unmatched: SpeciesRange[] } {
  if (value == null) return { matched: [], unmatched: ranges };
  const matched: SpeciesRange[] = [];
  const unmatched: SpeciesRange[] = [];
  for (const sp of ranges) {
    if (value >= sp.min && value <= sp.max) matched.push(sp);
    else unmatched.push(sp);
  }
  return { matched, unmatched };
}

function EnvRow({
  def,
  value,
}: {
  def: CovariateDef;
  value: number | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const formatted =
    value != null ? `${value.toFixed(def.decimals)} ${def.unit}` : "—";
  const inRange = isInWhaleRange(value, def.whaleRange);
  const { matched, unmatched } = speciesMatchesValue(
    value, def.speciesRanges,
  );

  return (
    <div>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between py-0.5 text-xs hover:bg-abyss-800/30"
      >
        <span className="flex items-center gap-1.5 text-slate-500">
          {def.label}
          {inRange === true && (
            <span className="rounded-full bg-emerald-500/15 px-1.5 py-px text-[8px] font-bold uppercase tracking-wider text-emerald-400">
              whale zone
            </span>
          )}
          {value != null && matched.length > 0 && (
            <span className="text-[8px] text-emerald-500/70">
              {matched.length} spp.
            </span>
          )}
          <span className="text-[9px] text-slate-600">
            {expanded ? "▾" : "▸"}
          </span>
        </span>
        <span className="text-right text-slate-300">{formatted}</span>
      </button>
      {expanded && (
        <div className="mb-1 mt-0.5 space-y-1.5">
          <p className="rounded-md bg-abyss-800/50 px-2 py-1 text-[10px] leading-snug text-slate-500">
            {def.why}
          </p>
          <div className="rounded-md border border-ocean-800/20 bg-ocean-900/20 px-2 py-1.5">
            <p className="mb-0.5 text-[9px] font-semibold uppercase tracking-wider text-ocean-400">
              Whale-significant range
            </p>
            <p className="text-[10px] leading-snug text-slate-400">
              {def.whaleRange[2]}
            </p>
            {value != null && (
              <p
                className={`mt-1 text-[10px] font-medium ${
                  inRange
                    ? "text-emerald-400"
                    : "text-slate-500"
                }`}
              >
                {inRange
                  ? "This value falls within the whale-significant range."
                  : "This value is outside the typical whale-significant range."}
              </p>
            )}
          </div>

          {/* Per-species likelihood */}
          <div className="rounded-md border border-ocean-800/20 bg-abyss-800/40 px-2 py-1.5">
            <p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-ocean-400">
              Species at this {def.label.toLowerCase()}
            </p>
            {value == null ? (
              <p className="text-[10px] text-slate-600">
                No value — cannot assess species likelihood.
              </p>
            ) : (
              <>
                {matched.length > 0 && (
                  <div className="mb-1.5">
                    <p className="mb-0.5 text-[9px] font-medium text-emerald-400/80">
                      Likely present
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {matched.map((sp) => (
                        <span
                          key={sp.name}
                          className="group relative rounded-full bg-emerald-500/15 px-1.5 py-px text-[9px] font-medium text-emerald-400"
                          title={`${sp.min}–${sp.max} ${def.unit}: ${sp.note}`}
                        >
                          {sp.name}
                          <span className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-abyss-900 px-2 py-1 text-[9px] text-slate-400 shadow-lg group-hover:block">
                            {sp.note}
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {unmatched.length > 0 && (
                  <div>
                    <p className="mb-0.5 text-[9px] font-medium text-slate-600">
                      Outside preferred range
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {unmatched.map((sp) => (
                        <span
                          key={sp.name}
                          className="group relative rounded-full bg-slate-700/30 px-1.5 py-px text-[9px] text-slate-600"
                          title={`${sp.min}–${sp.max} ${def.unit}: ${sp.note}`}
                        >
                          {sp.name}
                          <span className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-abyss-900 px-2 py-1 text-[9px] text-slate-400 shadow-lg group-hover:block">
                            Prefers {sp.min}–{sp.max} {def.unit}
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {matched.length === 0 && (
                  <p className="mt-0.5 text-[10px] italic text-slate-600">
                    This value is outside preferred ranges for all tracked species.
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Main component ──────────────────────────────────────── */

export default function CheckMyRisk({ onLocate, onClose }: CheckMyRiskProps) {
  const [latInput, setLatInput] = useState("");
  const [lonInput, setLonInput] = useState("");
  const [locating, setLocating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RiskResult | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [matchInfo, setMatchInfo] = useState<{
    isExact: boolean;
    distanceKm: number;
    cellLat: number;
    cellLon: number;
  } | null>(null);

  /* ── Geolocation ── */
  const handleUseMyLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by your browser.");
      return;
    }
    setLocating(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatInput(pos.coords.latitude.toFixed(4));
        setLonInput(pos.coords.longitude.toFixed(4));
        setLocating(false);
      },
      (err) => {
        setError(
          err.code === err.PERMISSION_DENIED
            ? "Location access denied. Enter coordinates manually."
            : "Could not determine your location. Try entering coordinates.",
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }, []);

  /* ── Submit ── */
  const handleCheck = useCallback(async () => {
    const lat = parseFloat(latInput);
    const lon = parseFloat(lonInput);
    if (isNaN(lat) || isNaN(lon)) {
      setError("Enter valid latitude and longitude values.");
      return;
    }
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setError(
        "Coordinates out of range (lat: -90 to 90, lon: -180 to 180).",
      );
      return;
    }

    setError(null);
    setLoading(true);
    setResult(null);
    setMatchInfo(null);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await fetchNearestRisk(
        lat, lon, controller.signal,
      );
      const d = resp.cell;
      const sc = d.scores as
        | Record<string, number>
        | undefined;

      const cellLat = (d.cell_lat as number) ?? lat;
      const cellLon = (d.cell_lon as number) ?? lon;

      setResult({
        h3_cell: String(d.h3_cell ?? ""),
        cell_lat: cellLat,
        cell_lon: cellLon,
        risk_score: (d.risk_score as number) ?? 0,
        risk_category: (d.risk_category as string) ?? "unknown",
        scores: {
          traffic_score: sc?.traffic_score ?? 0,
          cetacean_score: sc?.cetacean_score ?? 0,
          proximity_score: sc?.proximity_score ?? 0,
          strike_score: sc?.strike_score ?? 0,
          habitat_score: sc?.habitat_score ?? 0,
          protection_gap: sc?.protection_gap ?? 0,
          reference_risk_score: sc?.reference_risk_score ?? 0,
        },
        depth_m: (d.depth_m as number) ?? null,
        depth_zone: (d.depth_zone as string) ?? null,
        is_continental_shelf:
          (d.is_continental_shelf as boolean) ?? null,
        sst: (d.sst as number) ?? null,
        sst_sd: (d.sst_sd as number) ?? null,
        mld: (d.mld as number) ?? null,
        sla: (d.sla as number) ?? null,
        pp_upper_200m: (d.pp_upper_200m as number) ?? null,
      });

      setMatchInfo({
        isExact: resp.is_exact_match,
        distanceKm: resp.distance_km,
        cellLat,
        cellLon,
      });

      if (resp.is_exact_match) {
        onLocate(lat, lon);
      } else {
        onLocate(lat, lon, cellLat, cellLon);
      }
    } catch (e) {
      if (controller.signal.aborted) return;
      setError(
        e instanceof Error
          ? e.message
          : "Failed to fetch risk data.",
      );
    } finally {
      setLoading(false);
    }
  }, [latInput, lonInput, onLocate]);

  /* ── Key press ── */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") handleCheck();
    },
    [handleCheck],
  );

  return (
    <div className="absolute right-4 top-28 z-20 w-80 max-h-[calc(100vh-8rem)] overflow-y-auto overflow-x-hidden rounded-2xl border border-ocean-800/30 bg-abyss-900/95 shadow-2xl backdrop-blur-md">
      {/* ── Header ── */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-ocean-800/30 bg-abyss-900/95 px-4 py-3 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <IconPin className="h-5 w-5 text-ocean-400" />
          <h3 className="text-sm font-semibold text-white">Check My Risk</h3>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1 text-slate-500 transition-colors hover:bg-abyss-800 hover:text-slate-300"
          title="Close"
        >
          ✕
        </button>
      </div>

      <div className="space-y-4 p-4">
        {/* ── Location input ── */}
        <div>
          <button
            onClick={handleUseMyLocation}
            disabled={locating}
            className="mb-3 flex w-full items-center justify-center gap-2 rounded-lg bg-ocean-600/20 px-3 py-2 text-xs font-medium text-ocean-300 transition-all hover:bg-ocean-600/30 disabled:opacity-50"
          >
            {locating ? (
              <>
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-ocean-400 border-t-transparent" />
                Locating…
              </>
            ) : (
              <><IconGlobe className="inline h-3.5 w-3.5" /> Use My Location</>
            )}
          </button>

          <div className="flex gap-2">
            <div className="flex-1">
              <label className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-slate-500">
                Latitude
              </label>
              <input
                type="text"
                value={latInput}
                onChange={(e) => setLatInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="e.g. 41.5"
                className="w-full rounded-lg border border-ocean-800/30 bg-abyss-800/60 px-3 py-2 text-sm text-white placeholder-slate-600 outline-none transition-colors focus:border-ocean-500/50"
              />
            </div>
            <div className="flex-1">
              <label className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-slate-500">
                Longitude
              </label>
              <input
                type="text"
                value={lonInput}
                onChange={(e) => setLonInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="e.g. -70.5"
                className="w-full rounded-lg border border-ocean-800/30 bg-abyss-800/60 px-3 py-2 text-sm text-white placeholder-slate-600 outline-none transition-colors focus:border-ocean-500/50"
              />
            </div>
          </div>
        </div>

        {/* ── Submit ── */}
        <button
          onClick={handleCheck}
          disabled={loading || !latInput || !lonInput}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-ocean-600 to-ocean-500 px-4 py-2.5 text-sm font-semibold text-white shadow-md transition-all hover:from-ocean-500 hover:to-bioluminescent-600 disabled:opacity-40"
        >
          {loading ? (
            <>
              <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Checking…
            </>
          ) : (
            "Check Risk"
          )}
        </button>

        {/* ── Error ── */}
        {error && (
          <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {error}
          </p>
        )}

        {/* ── Results ── */}
        {result && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
            {/* Nearest-match notice */}
            {matchInfo && !matchInfo.isExact && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5">
                <p className="mb-1 text-xs font-medium text-amber-400">
                  Showing nearest available cell
                </p>
                <p className="text-[11px] leading-relaxed text-amber-300/80">
                  No data at your exact location. Showing risk for the
                  nearest cell,{" "}
                  <span className="font-semibold">
                    {formatDistance(matchInfo.distanceKm)}
                  </span>{" "}
                  away near{" "}
                  {formatCoord(matchInfo.cellLat, matchInfo.cellLon)}.
                </p>
                <div className="mt-2 flex items-center gap-4 text-[10px]">
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <span className="inline-block h-2.5 w-2.5 rounded-full bg-sky-400" />
                    Your location
                  </span>
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" />
                    Risk cell
                  </span>
                </div>
              </div>
            )}

            {/* Risk gauge + category */}
            <div className="text-center">
              <RiskGauge score={result.risk_score} />
              <span
                className={`mt-1 inline-block rounded-full border px-3 py-0.5 text-xs font-semibold uppercase tracking-wider ${categoryColor(result.risk_category)}`}
              >
                {result.risk_category}
              </span>
            </div>

            {/* Sub-scores with expandable explanations */}
            <div>
              <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Risk Breakdown
              </h4>
              <p className="mb-2 text-[10px] text-slate-600">
                Tap any score to see what drives it.
              </p>
              <div className="space-y-1">
                {buildSubScoreInfos(result.scores).map((info) => (
                  <ScoreBarExpanded key={info.label} info={info} />
                ))}
              </div>
            </div>

            {/* Environmental context with expandable explanations */}
            <div className="rounded-lg bg-abyss-800/40 px-3 py-2.5">
              <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                                <IconWaves className="mr-1 inline h-3.5 w-3.5" /> Environment
              </h4>
              <p className="mb-2 text-[10px] text-slate-600">
                Tap any covariate to learn why it matters for whale risk.
              </p>

              {/* Depth zone badge */}
              {result.depth_zone && (
                <div className="mb-2 flex items-center gap-2 text-[10px]">
                  <span className="rounded-full bg-ocean-600/20 px-2 py-0.5 font-semibold text-ocean-300">
                    {result.depth_zone.replace(/_/g, " ")}
                  </span>
                  {result.is_continental_shelf && (
                    <span className="text-slate-500">· shelf</span>
                  )}
                </div>
              )}

              <div className="space-y-0.5">
                {COVARIATES.map((def) => (
                  <EnvRow
                    key={def.key}
                    def={def}
                    value={result[def.key] as number | null}
                  />
                ))}
              </div>
            </div>

            {/* Tip */}
            <p className="text-center text-[10px] text-slate-600">
              Click the map for full cell detail with all sub-metrics.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
