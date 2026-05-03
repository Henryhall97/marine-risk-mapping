"use client";

import type {
  LayerType,
  Season,
  IsdmSpecies,
  OverlayToggles,
  ViewMode,
  TrafficMetric,
  OceanMetric,
  SightingColorBy,
  SightingStatusFilter,
  ClimateScenario,
  SdmTimePeriod,
  ProjectionMode,
} from "@/lib/types";
import Image from "next/image";
import {
  IconWarning,
  IconShip,
  IconWaves,
  IconThermometer,
  IconWhale,
  IconEye,
  IconRobot,
  IconChart,
  IconSpeedZone,
  IconShield,
  IconCompass,
  IconUsers,
  IconTrending,
  IconRuler,
  IconPlankton,
  IconSkull,
  IconBolt,
  IconDraft,
  IconMoon,
  IconFactory,
  IconPin,
} from "@/components/icons/MarineIcons";
import { useState, type ComponentType } from "react";

/* ── Layer guide content ─────────────────────────────────── */

const LAYER_GUIDE: Record<LayerType, { title: string; body: string }> = {
  none: {
    title: "Remove Data Layers",
    body:
      "Data layers are hidden. Use the overlay toggles below to view " +
      "regulatory boundaries, community sightings, and other map features " +
      "without the distraction of underlying hex or heatmap data.",
  },
  risk: {
    title: "Survey-Based Risk",
    body:
      "A composite index (0–1) combining 7 expert-weighted sub-scores: " +
      "traffic intensity (25%), cetacean presence from sighting surveys (25%), " +
      "proximity blend (15%), strike history (10%), habitat suitability (10%), " +
      "protection gap (10%), and Nisi reference risk (5%). Based on " +
      "observed data — no machine learning.",
  },
  risk_ml: {
    title: "Modelled Risk",
    body:
      "Replaces survey-based whale scores with machine-learned habitat " +
      "predictions. The top sub-score is whale×traffic interaction (30%) — " +
      "where high predicted whale probability meets heavy shipping. " +
      "Select a future decade + climate scenario (SSP2-4.5 or SSP5-8.5) " +
      "to see how risk shifts from the 2030s through the 2080s. Use " +
      "'Change from Today' to highlight which areas gain or lose risk.",
  },
  traffic_density: {
    title: "Ship Traffic",
    body:
      "Vessel traffic aggregated from 3.1 billion AIS pings into monthly " +
      "H3 cell summaries. Use the Danger Metric selector to switch between " +
      "vessel count, V&T lethality index (speed-based strike fatality), " +
      "high-speed fraction (≥10 kn), draft risk (>8 m), night traffic ratio, " +
      "and commercial vessel density.",
  },
  bathymetry: {
    title: "Bathymetry",
    body:
      "Ocean depth sampled from GEBCO at H3 centroids. Darker blue = deeper. " +
      "Continental shelf (<200 m) and shelf edge are key whale habitats — " +
      "upwelling at the shelf break concentrates prey.",
  },
  ocean: {
    title: "Ocean Covariates",
    body:
      "Copernicus marine data (2019–2024 climatology). SST drives species " +
      "distribution; MLD indicates mixing/upwelling; SLA shows mesoscale " +
      "eddies; PP (primary productivity) correlates with prey abundance. " +
      "Select a future decade to view CMIP6-projected ocean conditions. " +
      "Use 'Predicted Values' to see absolute projected values, or " +
      "'Change from Today' to see how each variable shifts vs the " +
      "current baseline (red = increase, blue = decrease).",
  },
  whale_predictions: {
    title: "Whale Habitat (Expert)",
    body:
      "Trained on expert-curated risk data (Nisi et al. 2024) combined " +
      "with 7 environmental covariates. Shows predicted whale presence " +
      "probability per cell per season. Select a species or view the " +
      "combined any-whale probability. Choose a future decade + climate " +
      "scenario to project habitat shifts under CMIP6 ocean warming.",
  },
  sdm: {
    title: "Whale Habitat (Observed)",
    body:
      "Trained on 1 million real-world OBIS whale sightings with spatial " +
      "cross-validation. View current predicted habitat, or switch to a " +
      "future decade to see how habitat may shift under climate change " +
      "(SSP2-4.5 moderate / SSP5-8.5 high emissions) through the 2080s. " +
      "Use 'Change from Today' to see habitat gains (blue) and losses (red) " +
      "relative to the current baseline.",
  },
  cetacean_density: {
    title: "Sighting Records",
    body:
      "Raw cetacean sighting counts from the Ocean Biodiversity " +
      "Information System (OBIS). Higher values = more observed whales. " +
      "Note: survey effort varies spatially, so absence ≠ no whales. " +
      "Compare with the Habitat layers which predict presence everywhere.",
  },
  strike_density: {
    title: "Strike History",
    body:
      "Known whale–ship collision records from NOAA (261 total, 67 geocoded). " +
      "Very sparse — most cells show zero. A non-zero value is highly " +
      "informative but absence doesn't mean safe.",
  },
};

const SCORING_GUIDE =
  "Scores are relative percentile ranks (0–1), not probabilities. " +
  "A cell scoring 0.8 means it's in the top 20% for that metric, " +
  "not that there's an 80% chance of a collision. Weights are " +
  "expert-elicited from V&T 2007, Rockwood 2021, and Nisi 2024.";

const MAP_TIPS = [
  "Switch to Overview mode for a coast-wide heatmap, Detail for individual hexagons.",
  "Click a hex cell in Detail mode to see its full score breakdown.",
  "Toggle overlay layers (SMAs, MPAs, BIAs, shipping lanes) to see regulatory boundaries.",
  "Seasons affect traffic, whale density, speed zones, and ocean data.",
  "Select a future decade on Modelled Risk, Whale Habitat, or Ocean layers to explore CMIP6 climate projections.",
];

const TRAFFIC_METRIC_GUIDE: Record<TrafficMetric, { label: string; detail: string }> = {
  vessel_density: {
    label: "Vessel Density",
    detail:
      "Average number of unique vessels per month in this cell. " +
      "High values indicate major shipping lanes or port approaches. " +
      "Normalised to 0–200 vessels for the colour ramp.",
  },
  speed_lethality: {
    label: "Speed Lethality",
    detail:
      "Vanderlaan & Taggart (2007) strike fatality index based on " +
      "vessel speed distribution. Probability that a strike at the " +
      "cell's median speed would be lethal. Values 0–1.",
  },
  high_speed: {
    label: "High-Speed Fraction",
    detail:
      "Fraction of vessel transits at ≥10 knots — the speed threshold " +
      "above which whale strike lethality rises sharply (V&T 2007). " +
      "This is the main target for speed restriction policies.",
  },
  draft_risk: {
    label: "Draft Risk",
    detail:
      "Fraction of vessel transits with draft >8 m (large cargo ships, " +
      "tankers). Deep-draft vessels pose higher strike risk because " +
      "they're less manoeuvrable and generate stronger underwater noise.",
  },
  night_traffic: {
    label: "Night Traffic",
    detail:
      "Ratio of nighttime to total vessel transits. Night traffic is " +
      "riskier because lookout visibility is reduced, and whales " +
      "resting at the surface are harder to spot.",
  },
  commercial: {
    label: "Commercial Vessels",
    detail:
      "Count of cargo and tanker vessels only. Commercial ships are " +
      "the primary strike risk — they're large, fast, and unable to " +
      "manoeuvre quickly to avoid whales.",
  },
};

const OCEAN_METRIC_GUIDE: Record<OceanMetric, { label: string; detail: string }> = {
  sst: {
    label: "Sea Surface Temperature",
    detail:
      "Climatological mean SST (°C) from Copernicus. Each whale species " +
      "has a preferred thermal range — right whales favour 10–17°C, " +
      "while sperm whales tolerate wider ranges. SST is the strongest " +
      "single predictor of species distribution in our SDMs.",
  },
  sst_sd: {
    label: "SST Standard Deviation",
    detail:
      "Seasonal variability of sea surface temperature. High values " +
      "indicate frontal zones and thermal boundaries where upwelling " +
      "concentrates prey — these are often whale foraging hotspots.",
  },
  mld: {
    label: "Mixed Layer Depth",
    detail:
      "Depth of the oceanic mixed layer (m). Shallow MLD indicates " +
      "stratification and potential upwelling, concentrating nutrients " +
      "and prey near the surface where whales forage. Deeper MLD " +
      "occurs in winter when storms mix the water column.",
  },
  sla: {
    label: "Sea Level Anomaly",
    detail:
      "Sea surface height anomaly (m) from satellite altimetry. " +
      "Positive values indicate warm-core eddies (downwelling); " +
      "negative values indicate cold-core eddies (upwelling, " +
      "productive). Mesoscale eddies concentrate prey.",
  },
  pp_upper_200m: {
    label: "Primary Productivity",
    detail:
      "Net primary production in the upper 200 m (mg C/m²/day). " +
      "PP drives the base of the marine food web — high PP attracts " +
      "zooplankton, then fish, then whales. Ranks 5th–6th in ISDM " +
      "feature importance across species.",
  },
};

/* ── Layer options (categorised) ──────────────────────────── */

type LayerEntry = {
  id: LayerType;
  label: string;
  Icon: ComponentType<{ className?: string }>;
};

/** Standalone "clear layer" option — rendered separately above categories. */
const CLEAR_LAYER: LayerEntry = { id: "none", label: "Remove Data Layers", Icon: IconEye };

const LAYER_CATEGORIES: {
  heading: string;
  HeadingIcon: ComponentType<{ className?: string }>;
  layers: LayerEntry[];
}[] = [
  {
    heading: "Risk Analysis",
    HeadingIcon: IconWarning,
    layers: [
      { id: "risk", label: "Survey-Based Risk", Icon: IconWarning },
      { id: "risk_ml", label: "Modelled Risk", Icon: IconRobot },
    ],
  },
  {
    heading: "Wildlife",
    HeadingIcon: IconWhale,
    layers: [
      { id: "whale_predictions", label: "Whale Habitat (Expert)", Icon: IconWhale },
      { id: "sdm", label: "Whale Habitat (Observed)", Icon: IconWhale },
      { id: "cetacean_density", label: "Sighting Records", Icon: IconEye },
      { id: "strike_density", label: "Strike History", Icon: IconChart },
    ],
  },
  {
    heading: "Vessel Traffic",
    HeadingIcon: IconShip,
    layers: [
      { id: "traffic_density", label: "Ship Traffic", Icon: IconShip },
    ],
  },
  {
    heading: "Environment",
    HeadingIcon: IconWaves,
    layers: [
      { id: "bathymetry", label: "Bathymetry", Icon: IconWaves },
      { id: "ocean", label: "Ocean Covariates", Icon: IconThermometer },
    ],
  },
];

const SEASONS: { id: Season; label: string }[] = [
  { id: null, label: "Annual" },
  { id: "winter", label: "Winter" },
  { id: "spring", label: "Spring" },
  { id: "summer", label: "Summer" },
  { id: "fall", label: "Fall" },
  { id: "all", label: "All" },
];

/** Species available only for the ISDM layer (Nisi-trained, 4 species). */
const ISDM_ONLY_SPECIES = new Set<IsdmSpecies>(["blue_whale", "fin_whale", "humpback_whale", "sperm_whale"]);

const ISDM_SPECIES: { id: IsdmSpecies; label: string; color: string }[] = [
  { id: "blue_whale", label: "Blue Whale", color: "#3b82f6" },
  { id: "fin_whale", label: "Fin Whale", color: "#a16207" },
  { id: "humpback_whale", label: "Humpback", color: "#22c55e" },
  { id: "sperm_whale", label: "Sperm Whale", color: "#374151" },
  { id: "right_whale", label: "Right Whale", color: "#dc2626" },
  { id: "minke_whale", label: "Minke Whale", color: "#14b8a6" },
];

/** Layers that show the species selector. */
const SPECIES_LAYERS = new Set<LayerType>([
  "whale_predictions",
  "sdm",
]);

/** Layers that show the traffic metric selector. */
const TRAFFIC_LAYERS = new Set<LayerType>(["traffic_density"]);

/** Layers that show the ocean metric selector. */
const OCEAN_LAYERS = new Set<LayerType>(["ocean"]);

const OCEAN_METRICS: {
  id: OceanMetric;
  label: string;
  Icon: ComponentType<{ className?: string }>;
  desc: string;
}[] = [
  {
    id: "sst",
    label: "Sea Surface Temp",
    Icon: IconThermometer,
    desc: "Mean SST (°C)",
  },
  {
    id: "sst_sd",
    label: "SST Variability",
    Icon: IconTrending,
    desc: "SST standard deviation (°C)",
  },
  {
    id: "mld",
    label: "Mixed Layer Depth",
    Icon: IconWaves,
    desc: "Ocean mixing depth (m)",
  },
  {
    id: "sla",
    label: "Sea Level Anomaly",
    Icon: IconRuler,
    desc: "SSH anomaly (m)",
  },
  {
    id: "pp_upper_200m",
    label: "Primary Productivity",
    Icon: IconPlankton,
    desc: "PP upper 200 m (mg C/m²/day)",
  },
];

const TRAFFIC_METRICS: {
  id: TrafficMetric;
  label: string;
  Icon: ComponentType<{ className?: string }>;
  desc: string;
}[] = [
  {
    id: "vessel_density",
    label: "Vessel Density",
    Icon: IconChart,
    desc: "Monthly vessel count",
  },
  {
    id: "speed_lethality",
    label: "Speed Lethality",
    Icon: IconSkull,
    desc: "V&T 2007 strike fatality index",
  },
  {
    id: "high_speed",
    label: "High Speed",
    Icon: IconBolt,
    desc: "Fraction at ≥10 kn lethal speed",
  },
  {
    id: "draft_risk",
    label: "Draft Risk",
    Icon: IconDraft,
    desc: "Deep-draft vessel fraction (>8m)",
  },
  {
    id: "night_traffic",
    label: "Night Traffic",
    Icon: IconMoon,
    desc: "Night vessel ratio",
  },
  {
    id: "commercial",
    label: "Commercial",
    Icon: IconFactory,
    desc: "Cargo + tanker vessels",
  },
];

/* ── Props ───────────────────────────────────────────────── */

/** Layers that support seasonal data. */
const SEASONAL_LAYERS = new Set<LayerType>([
  "risk",
  "risk_ml",
  "ocean",
  "whale_predictions",
  "sdm",
  "cetacean_density",
  "traffic_density",
]);

/** Layers that show the time period + projection controls. */
const SDM_LAYERS = new Set<LayerType>(["sdm", "whale_predictions", "risk_ml", "ocean"]);

const CLIMATE_SCENARIOS: { id: ClimateScenario; label: string; desc: string }[] = [
  { id: "ssp245", label: "SSP2-4.5", desc: "Moderate emissions" },
  { id: "ssp585", label: "SSP5-8.5", desc: "High emissions" },
];

const SDM_TIME_PERIODS: { id: SdmTimePeriod; label: string }[] = [
  { id: "current", label: "Current" },
  { id: "2030s", label: "2030s" },
  { id: "2040s", label: "2040s" },
  { id: "2060s", label: "2060s" },
  { id: "2080s", label: "2080s" },
];

interface SidebarProps {
  viewMode: ViewMode;
  onViewModeChange: (m: ViewMode) => void;
  activeLayer: LayerType;
  onLayerChange: (l: LayerType) => void;
  season: Season;
  onSeasonChange: (s: Season) => void;
  overlays: OverlayToggles;
  onOverlaysChange: (o: OverlayToggles) => void;
  activeDate: string;
  onDateChange: (d: string) => void;
  selectedSpecies: IsdmSpecies | null;
  onSpeciesChange: (s: IsdmSpecies | null) => void;
  showContours: boolean;
  onContoursChange: (v: boolean) => void;
  trafficMetric: TrafficMetric;
  onTrafficMetricChange: (m: TrafficMetric) => void;
  oceanMetric: OceanMetric;
  onOceanMetricChange: (m: OceanMetric) => void;
  // Community sightings
  sightingColorBy: SightingColorBy;
  onSightingColorByChange: (c: SightingColorBy) => void;
  sightingSpeciesFilter: string | null;
  onSightingSpeciesFilterChange: (s: string | null) => void;
  sightingStatusFilter: SightingStatusFilter;
  onSightingStatusFilterChange: (s: SightingStatusFilter) => void;
  sightingCount: number;
  // Climate projections
  sdmTimePeriod: SdmTimePeriod;
  onSdmTimePeriodChange: (p: SdmTimePeriod) => void;
  climateScenario: ClimateScenario;
  onClimateScenarioChange: (s: ClimateScenario) => void;
  projectionMode: ProjectionMode;
  onProjectionModeChange: (m: ProjectionMode) => void;
}

/* ── Sub-components ──────────────────────────────────────── */

function Toggle({
  label,
  checked,
  onChange,
  colorDot,
  info,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  colorDot?: string;
  info?: string;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <div className="flex items-center gap-2 py-0.5 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="rounded border-ocean-700 bg-abyss-800 text-ocean-500 focus:ring-ocean-500"
        />
        {colorDot && (
          <span
            className="inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full"
            style={{ backgroundColor: colorDot }}
          />
        )}
        {info ? (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex flex-1 items-center gap-1 text-left hover:text-slate-100"
          >
            <span className="flex-1">{label}</span>
            <span className="text-[9px] text-slate-600">
              {expanded ? "▾" : "▸"}
            </span>
          </button>
        ) : (
          <span>{label}</span>
        )}
      </div>
      {info && expanded && (
        <p className="mb-1 ml-7 mt-0.5 rounded-md bg-abyss-800/50 px-2 py-1.5 text-[10px] leading-snug text-slate-500">
          {info}
        </p>
      )}
    </div>
  );
}

/* ── Component ───────────────────────────────────────────── */

export default function Sidebar({
  viewMode,
  onViewModeChange,
  activeLayer,
  onLayerChange,
  season,
  onSeasonChange,
  overlays,
  onOverlaysChange,
  activeDate,
  onDateChange,
  selectedSpecies,
  onSpeciesChange,
  showContours,
  onContoursChange,
  trafficMetric,
  onTrafficMetricChange,
  oceanMetric,
  onOceanMetricChange,
  sightingColorBy,
  onSightingColorByChange,
  sightingSpeciesFilter,
  onSightingSpeciesFilterChange,
  sightingStatusFilter,
  onSightingStatusFilterChange,
  sightingCount,
  sdmTimePeriod,
  onSdmTimePeriodChange,
  climateScenario,
  onClimateScenarioChange,
  projectionMode,
  onProjectionModeChange,
}: SidebarProps) {
  return (
    <div className="glass-panel-strong absolute left-4 top-16 z-10 w-72 max-h-[calc(100vh-5rem)] overflow-y-auto rounded-xl shadow-ocean-lg">
      {/* ── Header ── */}
      <div className="border-b border-ocean-800/30 px-4 py-3">
        <h1 className="flex items-center gap-2 font-display text-lg font-bold tracking-tight text-white">
          <Image src="/whale_watch_logo.png" alt="Whale Watch" width={48} height={32} className="h-8 w-12 object-contain drop-shadow-[0_0_6px_rgba(34,211,238,0.25)]" />
          <span>Whale<span className="text-ocean-bright">Watch</span> Map</span>
        </h1>
        <p className="mt-0.5 text-xs text-slate-400">
          Whale–vessel collision risk
        </p>
      </div>

      {/* ── View mode toggle ── */}
      <section className="border-b border-ocean-800/30 p-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          View Mode
        </h2>
        <div className="flex gap-1 rounded-lg border border-ocean-800/30 bg-abyss-900/80 p-0.5">
          {(
            [
              { id: "overview", label: "Overview", desc: "Coast-wide heatmap" },
              { id: "detail", label: "Detail", desc: "Hex cell tiles" },
            ] as const
          ).map((m) => (
            <button
              key={m.id}
              onClick={() => onViewModeChange(m.id)}
              title={m.desc}
              className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-all ${
                viewMode === m.id
                  ? "bg-ocean-500/20 text-bioluminescent-400 shadow-ocean-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </section>

      {/* ── Data Layer (categorised) ── */}
      <section className="border-b border-ocean-800/30 p-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Data Layer
        </h2>
        <div className="space-y-3">
          {/* Standalone clear-layer toggle */}
          <button
            onClick={() => onLayerChange(CLEAR_LAYER.id)}
            className={`flex w-full items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-sm transition-all ${
              activeLayer === "none"
                ? "border-slate-500/30 bg-slate-500/15 text-slate-300 shadow-ocean-sm"
                : "border-transparent text-slate-400 hover:bg-ocean-900/30"
            }`}
          >
            <CLEAR_LAYER.Icon className="h-4 w-4 flex-shrink-0" />
            {CLEAR_LAYER.label}
          </button>

          <div className="my-1 border-t border-ocean-800/20" />

          {LAYER_CATEGORIES.map((cat) => (
            <div key={cat.heading}>
              <p className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <cat.HeadingIcon className="h-3.5 w-3.5" />
                {cat.heading}
              </p>
              <div className="space-y-0.5">
                {cat.layers.map((l) => (
                  <button
                    key={l.id}
                    onClick={() => onLayerChange(l.id)}
                    className={`flex w-full items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-sm transition-all ${
                      activeLayer === l.id
                        ? "border-ocean-500/30 bg-ocean-500/15 text-bioluminescent-400 shadow-ocean-sm"
                        : "border-transparent text-slate-300 hover:bg-ocean-900/30"
                    }`}
                  >
                    <l.Icon className="h-4 w-4 flex-shrink-0" />
                    {l.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Species filter (whale_predictions) ── */}
      {SPECIES_LAYERS.has(activeLayer) && (
        <section className="border-b border-ocean-800/30 p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Species
          </h2>
          <div className="space-y-1">
            <button
              onClick={() => onSpeciesChange(null)}
              className={`flex w-full items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-sm transition-all ${
                selectedSpecies === null
                  ? "border-ocean-500/30 bg-ocean-500/15 text-bioluminescent-400"
                  : "border-transparent text-slate-300 hover:bg-ocean-900/30"
              }`}
            >
              <IconWhale className="h-4 w-4 flex-shrink-0" />
              All species (combined)
            </button>
            {ISDM_SPECIES
              .filter((sp) => activeLayer !== "whale_predictions" || ISDM_ONLY_SPECIES.has(sp.id))
              .map((sp) => (
              <button
                key={sp.id}
                onClick={() =>
                  onSpeciesChange(
                    selectedSpecies === sp.id ? null : sp.id,
                  )
                }
                className={`flex w-full items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-sm transition-all ${
                  selectedSpecies === sp.id
                    ? "border-ocean-500/30 bg-ocean-500/15 text-bioluminescent-400"
                    : "border-transparent text-slate-300 hover:bg-ocean-900/30"
                }`}
              >
                <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: sp.color }} />
                {sp.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Traffic metric selector ── */}
      {TRAFFIC_LAYERS.has(activeLayer) && (
        <section className="border-b border-ocean-800/30 p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Danger Metric
          </h2>
          <div className="space-y-1">
            {TRAFFIC_METRICS.map((tm) => (
              <button
                key={tm.id}
                onClick={() => onTrafficMetricChange(tm.id)}
                title={tm.desc}
                className={`w-full rounded-lg border px-3 py-1.5 text-left text-sm transition-all ${
                  trafficMetric === tm.id
                    ? "border-coral-500/30 bg-coral-500/15 text-coral-400"
                    : "border-transparent text-slate-300 hover:bg-ocean-900/30"
                }`}
              >
                <tm.Icon className="mr-1.5 inline h-4 w-4" />
                {tm.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Ocean metric selector ── */}
      {OCEAN_LAYERS.has(activeLayer) && (
        <section className="border-b border-ocean-800/30 p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Ocean Variable
          </h2>
          <div className="space-y-1">
            {OCEAN_METRICS.map((om) => (
              <button
                key={om.id}
                onClick={() => onOceanMetricChange(om.id)}
                title={om.desc}
                className={`w-full rounded-lg border px-3 py-1.5 text-left text-sm transition-all ${
                  oceanMetric === om.id
                    ? "border-ocean-500/30 bg-ocean-500/15 text-bioluminescent-400"
                    : "border-transparent text-slate-300 hover:bg-ocean-900/30"
                }`}
              >
                <om.Icon className="mr-1.5 inline h-4 w-4" />
                {om.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Season (only for seasonal layers) ── */}
      {SEASONAL_LAYERS.has(activeLayer) && (
        <section className="border-b border-ocean-800/30 p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Season
          </h2>
          <div className="flex flex-wrap gap-1">
            {SEASONS.filter(
              (s) =>
                // Projected data has no "annual" — hide Annual & All when projecting
                sdmTimePeriod === "current" ||
                !SDM_LAYERS.has(activeLayer) ||
                (s.id !== null && s.id !== "all"),
            ).map((s) => (
              <button
                key={s.id ?? "annual"}
                onClick={() => onSeasonChange(s.id)}
                className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-all ${
                  season === s.id
                    ? "border-ocean-500/40 bg-ocean-500/20 text-bioluminescent-400 shadow-ocean-sm"
                    : "border-ocean-800/30 text-slate-400 hover:bg-ocean-900/30"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── SDM Time Period + Projection Controls ── */}
      {SDM_LAYERS.has(activeLayer) && (
        <section className="border-b border-ocean-800/30 p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Time Period
          </h2>
          <div className="flex flex-wrap gap-1 mb-1">
            {SDM_TIME_PERIODS.map((tp) => (
              <button
                key={tp.id}
                onClick={() => onSdmTimePeriodChange(tp.id)}
                className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-all ${
                  sdmTimePeriod === tp.id
                    ? tp.id === "current"
                      ? "border-ocean-500/40 bg-ocean-500/20 text-bioluminescent-400 shadow-ocean-sm"
                      : "border-amber-500/40 bg-amber-500/20 text-amber-300 shadow-ocean-sm"
                    : "border-ocean-800/30 text-slate-400 hover:bg-ocean-900/30"
                }`}
              >
                {tp.label}
              </button>
            ))}
          </div>

          {sdmTimePeriod === "current" && (
            <p className="mt-2 text-[10px] text-slate-500 leading-relaxed">
              {activeLayer === "sdm"
                ? "Out-of-fold spatial CV predictions — each cell scored by a model that never trained on its spatial neighbourhood."
                : activeLayer === "risk_ml"
                  ? "Modelled 7-sub-score composite risk combining predicted whale habitat with V&T lethality and co-occurrence interaction."
                  : activeLayer === "ocean"
                    ? "Copernicus climatological means (2019–2024). Select a future decade to view CMIP6 projected ocean conditions."
                    : "Expert-curated presence/absence models (Nisi et al. 2024) trained on 4 species with 7 environmental covariates."}
            </p>
          )}

          {sdmTimePeriod !== "current" && (
            <>
              <h2 className="mt-3 mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Climate Scenario
              </h2>
              <div className="space-y-1.5 mb-3">
                {CLIMATE_SCENARIOS.map((cs) => (
                  <button
                    key={cs.id}
                    onClick={() => onClimateScenarioChange(cs.id)}
                    className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-all ${
                      climateScenario === cs.id
                        ? "border-amber-500/40 bg-amber-500/15 text-amber-300 shadow-ocean-sm"
                        : "border-ocean-800/30 text-slate-400 hover:bg-ocean-900/30"
                    }`}
                  >
                    <span className="font-medium">{cs.label}</span>
                    <span className="ml-1.5 text-xs text-slate-500">{cs.desc}</span>
                  </button>
                ))}
              </div>

              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Show As
              </h2>
              <div className="flex gap-1">
                {(["absolute", "change"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => onProjectionModeChange(m)}
                    className={`flex-1 rounded-md border px-2 py-1.5 text-xs font-medium transition-all ${
                      projectionMode === m
                        ? m === "change"
                          ? "border-sky-500/40 bg-sky-500/20 text-sky-300 shadow-ocean-sm"
                          : "border-amber-500/40 bg-amber-500/20 text-amber-300 shadow-ocean-sm"
                        : "border-ocean-800/30 text-slate-400 hover:bg-ocean-900/30"
                    }`}
                  >
                    {m === "absolute" ? "Predicted Values" : "Change from Today"}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-[10px] text-slate-500/70 leading-relaxed">
                {projectionMode === "absolute"
                  ? "Showing projected values for the selected future decade."
                  : activeLayer === "ocean"
                    ? "Showing difference: projected minus current seasonal baseline. Red/warm = increase, blue/cool = decrease."
                    : "Showing difference: future decade minus current baseline. Red = increase, blue = decrease."}
              </p>

              <p className="mt-2 text-[10px] text-slate-500 leading-relaxed">
                {activeLayer === "risk_ml"
                  ? "Projected risk: whale-dependent sub-scores (45% of composite) shift with projected habitat; traffic and other sub-scores (55%) remain current."
                  : activeLayer === "ocean"
                    ? "CMIP6 ensemble-mean projected ocean conditions: warming SST, shoaling MLD, shifting SLA, and declining primary productivity under the selected emissions scenario."
                    : <>Projected whale habitat shift based on CMIP6 ensemble-mean
                      ocean warming, mixed layer shoaling, and primary productivity
                      decline applied to the trained{" "}
                      {activeLayer === "sdm" ? "observation-based model" : "expert-based model (Nisi et al. 2024)"}.</>}
              </p>
            </>
          )}
        </section>
      )}

      {/* ── Overlays (categorised) ── */}
      <section className="p-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Overlays
        </h2>

        <div className="space-y-3">
          {/* ── Regulatory Zones ── */}
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <IconSpeedZone className="h-3.5 w-3.5" /> Regulatory Zones
            </p>
            <div className="space-y-0.5">
              <Toggle
                label="Active SMAs"
                checked={overlays.activeSMAs}
                colorDot="rgb(255, 80, 80)"
                onChange={(v) =>
                  onOverlaysChange({ ...overlays, activeSMAs: v })
                }
                info={
                  "Seasonal Management Areas (50 CFR § 224.105) — mandatory " +
                  "speed restrictions for vessels ≥65 ft in designated North " +
                  "Atlantic right whale habitat. Active during calving (Nov–Apr " +
                  "in SE US) and feeding (Jan–Jul in NE US) seasons. " +
                  "Compliance is monitored by NOAA Enforcement."
                }
              />
              <Toggle
                label="Proposed Speed Zones"
                checked={overlays.proposedZones}
                colorDot="rgb(255, 200, 60)"
                onChange={(v) =>
                  onOverlaysChange({ ...overlays, proposedZones: v })
                }
                info={
                  "NOAA-proposed vessel speed rule amendments that would expand " +
                  "the geographic and seasonal scope of speed restrictions to " +
                  "protect right whales. Not yet enacted — shown here because " +
                  "they indicate areas of recognised risk. These zones are " +
                  "excluded from the protection gap score (no real enforcement)."
                }
              />
              <Toggle
                label="Slow Zones (DMAs)"
                checked={overlays.slowZones}
                colorDot="rgb(255, 140, 0)"
                onChange={(v) =>
                  onOverlaysChange({ ...overlays, slowZones: v })
                }
                info={
                  "Dynamic Management Areas — temporary 10-knot speed " +
                  "restriction zones triggered when right whale aggregations " +
                  "are detected (aerial surveys or acoustic monitoring). " +
                  "Voluntary compliance only (~5%). Typically last 15 days " +
                  "and shift with whale movements. Count varies over time " +
                  "as zones are created and expire."
                }
              />
            </div>
          </div>

          {/* ── Protected Areas ── */}
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <IconShield className="h-3.5 w-3.5" /> Protected Areas
            </p>
            <div className="space-y-0.5">
              <Toggle
                label="Marine Protected Areas"
                checked={overlays.mpas}
                colorDot="rgb(80, 200, 120)"
                onChange={(v) =>
                  onOverlaysChange({ ...overlays, mpas: v })
                }
                info={
                  "926 MPAs from the NOAA MPA Inventory covering CONUS, " +
                  "Alaska, and Hawaii. Protection levels range from no-take " +
                  "marine reserves (strongest) to multiple-use areas with " +
                  "minimal restrictions. The protection gap sub-score in the " +
                  "risk model uses a tiered system: no-take zones score 0.10 " +
                  "(lowest gap), while unprotected waters score 1.0."
                }
              />
              <Toggle
                label="Biologically Important Areas"
                checked={overlays.bias}
                colorDot="rgb(0, 200, 200)"
                onChange={(v) =>
                  onOverlaysChange({ ...overlays, bias: v })
                }
                info={
                  "85 NOAA CetMap BIAs identifying areas of particular " +
                  "biological importance for cetaceans — feeding grounds, " +
                  "migratory corridors, and reproductive areas. BIAs are " +
                  "science-based delineations, not regulatory zones — they " +
                  "carry no legal protections but inform management decisions " +
                  "and environmental impact assessments."
                }
              />
              <Toggle
                label="Critical Habitat"
                checked={overlays.criticalHabitat}
                colorDot="rgb(180, 80, 220)"
                onChange={(v) =>
                  onOverlaysChange({ ...overlays, criticalHabitat: v })
                }
                info={
                  "31 NMFS-designated or proposed critical habitat areas " +
                  "for ESA-listed whale species (primarily North Atlantic " +
                  "right whale, fin whale, and humpback DPS). Critical habitat " +
                  "designation requires federal agencies to avoid actions that " +
                  "destroy or adversely modify these areas — the strongest " +
                  "habitat protection under US law."
                }
              />
            </div>
          </div>

          {/* ── Navigation ── */}
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <IconCompass className="h-3.5 w-3.5" /> Navigation
            </p>
            <div className="space-y-0.5">
              <Toggle
                label="Shipping Lanes"
                checked={overlays.shippingLanes}
                colorDot="rgb(60, 120, 220)"
                onChange={(v) =>
                  onOverlaysChange({ ...overlays, shippingLanes: v })
                }
                info={
                  "~300 NOAA Coast Survey features including Traffic " +
                  "Separation Schemes (TSS), recommended routes, and " +
                  "precautionary areas. TSS lanes channel vessel traffic " +
                  "into predictable corridors — overlap with whale habitat " +
                  "is a key driver of collision risk. Some lanes have been " +
                  "shifted to reduce right whale overlap (e.g. Boston TSS " +
                  "in 2007)."
                }
              />
              {viewMode === "overview" && (
                <Toggle
                  label="Depth Contours"
                  checked={showContours}
                  colorDot="rgb(100, 180, 240)"
                  onChange={onContoursChange}
                  info={
                    "Bathymetry contour lines from GEBCO highlighting the " +
                    "continental shelf edge (~200 m), slope (~1000 m), and " +
                    "deep ocean. The shelf break is one of the most " +
                    "important features for whale habitat — upwelling along " +
                    "the edge concentrates prey. Only visible in Overview mode."
                  }
                />
              )}
            </div>
          </div>

          {/* ── Community ── */}
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <IconUsers className="h-3.5 w-3.5" /> Community
            </p>
            <div className="space-y-0.5">
              <Toggle
                label={`Community Sightings${overlays.communitySightings && sightingCount > 0 ? ` (${sightingCount})` : ""}`}
                checked={overlays.communitySightings}
                colorDot="rgb(56, 189, 248)"
                onChange={(v) =>
                  onOverlaysChange({ ...overlays, communitySightings: v })
                }
                info={
                  "Whale sightings reported by the WhaleWatch community. " +
                  "Each marker shows a verified user submission with species " +
                  "identification (from photo/audio classification or manual " +
                  "report), location, and associated risk context for that " +
                  "H3 cell. Filter by species, verification status, or colour " +
                  "by species/risk using the controls below."
                }
              />
            </div>
          </div>
        </div>

        {/* Date scrubber — only when any speed zone overlay is on */}
        {(overlays.activeSMAs || overlays.proposedZones) && (
          <div className="ml-6 mt-2">
            <label className="mb-1 block text-xs text-slate-400">
              Active on date:
            </label>
            <input
              type="date"
              value={activeDate}
              onChange={(e) => onDateChange(e.target.value)}
              className="w-full rounded-md border border-ocean-800/30 bg-abyss-900/80 px-2 py-1 text-sm text-slate-300 focus:border-ocean-500 focus:ring-1 focus:ring-ocean-500"
            />
          </div>
        )}

        {/* ── Sighting filters (visible when overlay is on) ── */}
        {overlays.communitySightings && (
          <div className="ml-6 mt-2 space-y-2">
            {sightingCount === 0 && (
              <p className="rounded-md bg-ocean-900/30 px-2 py-1.5 text-[11px] leading-snug text-slate-500">
                No sightings in the current view. Try zooming out or
                panning to see community reports.
              </p>
            )}
            {/* Colour by */}
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Colour by:
              </label>
              <div className="flex gap-1">
                {(["species", "verification", "interaction"] as const).map(
                  (c) => (
                    <button
                      key={c}
                      onClick={() => onSightingColorByChange(c)}
                      className={`rounded-md border px-2 py-0.5 text-xs capitalize transition-all ${
                        sightingColorBy === c
                          ? "border-ocean-500/40 bg-ocean-500/20 text-bioluminescent-400"
                          : "border-ocean-800/30 text-slate-400 hover:bg-ocean-900/30"
                      }`}
                    >
                      {c}
                    </button>
                  ),
                )}
              </div>
            </div>

            {/* Species filter */}
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Species:
              </label>
              <select
                value={sightingSpeciesFilter ?? ""}
                onChange={(e) =>
                  onSightingSpeciesFilterChange(
                    e.target.value || null,
                  )
                }
                className="w-full rounded-md border border-ocean-800/30 bg-abyss-900/80 px-2 py-1 text-xs text-slate-300 focus:border-ocean-500 focus:ring-1 focus:ring-ocean-500"
              >
                <option value="">All species</option>
                <option value="right_whale">Right whale</option>
                <option value="humpback_whale">Humpback whale</option>
                <option value="fin_whale">Fin whale</option>
                <option value="blue_whale">Blue whale</option>
                <option value="minke_whale">Minke whale</option>
                <option value="sperm_whale">Sperm whale</option>
                <option value="sei_whale">Sei whale</option>
                <option value="killer_whale">Killer whale</option>
              </select>
            </div>

            {/* Verification status filter */}
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Status:
              </label>
              <select
                value={sightingStatusFilter}
                onChange={(e) =>
                  onSightingStatusFilterChange(
                    e.target.value as "all" | "verified" | "community_verified" | "unverified" | "disputed",
                  )
                }
                className="w-full rounded-md border border-ocean-800/30 bg-abyss-900/80 px-2 py-1 text-xs text-slate-300 focus:border-ocean-500 focus:ring-1 focus:ring-ocean-500"
              >
                <option value="all">All statuses</option>
                <option value="verified">Verified</option>
                <option value="community_verified">Community verified</option>
                <option value="unverified">Unverified</option>
                <option value="disputed">Disputed</option>
              </select>
            </div>
          </div>
        )}
      </section>

      {/* ── Guide / Info ── */}
      <GuidePanel
        activeLayer={activeLayer}
        trafficMetric={trafficMetric}
        oceanMetric={oceanMetric}
      />
    </div>
  );
}

/* ── Guide panel (collapsible) ───────────────────────────── */

function GuidePanel({
  activeLayer,
  trafficMetric,
  oceanMetric,
}: {
  activeLayer: LayerType;
  trafficMetric?: TrafficMetric;
  oceanMetric?: OceanMetric;
}) {
  const [open, setOpen] = useState(false);
  const guide = LAYER_GUIDE[activeLayer];

  // Metric-specific detail (if applicable)
  const metricDetail =
    activeLayer === "traffic_density" && trafficMetric
      ? TRAFFIC_METRIC_GUIDE[trafficMetric]
      : activeLayer === "ocean" && oceanMetric
        ? OCEAN_METRIC_GUIDE[oceanMetric]
        : null;

  return (
    <section className="border-t border-ocean-800/30">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-ocean-900/20"
      >
        <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <svg
            className="h-3.5 w-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4m0-4h.01" />
          </svg>
          Guide
        </span>
        <svg
          className={`h-3.5 w-3.5 text-slate-500 transition-transform ${
            open ? "rotate-180" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="space-y-4 px-4 pb-4 text-xs leading-relaxed text-slate-400">
          {/* Layer-specific help */}
          <div>
            <h3 className="mb-1 font-semibold text-ocean-300">
              {guide.title}
            </h3>
            <p>{guide.body}</p>
          </div>

          {/* Active metric detail */}
          {metricDetail && (
            <div className="rounded-lg border border-ocean-800/20 bg-ocean-900/20 p-3">
              <h3 className="mb-1 flex items-center gap-1.5 font-semibold text-bioluminescent-400">
                <IconPin className="h-3.5 w-3.5" /> {metricDetail.label}
              </h3>
              <p>{metricDetail.detail}</p>
            </div>
          )}

          {/* Scoring methodology — only for scored / risk layers */}
          {(activeLayer === "risk" ||
            activeLayer === "risk_ml" ||
            activeLayer === "traffic_density" ||
            activeLayer === "cetacean_density" ||
            activeLayer === "strike_density" ||
            activeLayer === "whale_predictions" ||
            activeLayer === "sdm") && (
            <div>
              <h3 className="mb-1 font-semibold text-ocean-300">
                How Scores Work
              </h3>
              <p>{SCORING_GUIDE}</p>
            </div>
          )}

          {/* Map tips */}
          <div>
            <h3 className="mb-1 font-semibold text-ocean-300">
              Tips
            </h3>
            <ul className="list-inside list-disc space-y-0.5">
              {MAP_TIPS.map((tip, i) => (
                <li key={i}>{tip}</li>
              ))}
            </ul>
          </div>

          {/* Data provenance */}
          <p className="border-t border-ocean-800/20 pt-3 text-[10px] text-slate-500">
            Data: AIS MarineCadastre, OBIS, NOAA ship strikes,
            Copernicus, GEBCO, Nisi et al. 2024.
          </p>
        </div>
      )}
    </section>
  );
}
