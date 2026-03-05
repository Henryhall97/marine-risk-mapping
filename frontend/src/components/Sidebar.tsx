"use client";

import type {
  LayerType,
  Season,
  IsdmSpecies,
  OverlayToggles,
  ViewMode,
  TrafficMetric,
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
} from "@/components/icons/MarineIcons";
import type { ComponentType } from "react";

/* ── Layer options ───────────────────────────────────────── */

const LAYERS: { id: LayerType; label: string; Icon: ComponentType<{ className?: string }> }[] = [
  { id: "risk", label: "Collision Risk", Icon: IconWarning },
  { id: "risk_ml", label: "ML Risk", Icon: IconRobot },
  { id: "traffic_density", label: "Ship Traffic", Icon: IconShip },
  { id: "bathymetry", label: "Bathymetry", Icon: IconWaves },
  { id: "ocean", label: "Ocean (SST)", Icon: IconThermometer },
  { id: "whale_predictions", label: "Whale Predictions", Icon: IconWhale },
  { id: "sdm_predictions", label: "SDM Predictions", Icon: IconWhale },
  { id: "cetacean_density", label: "Sighting Density", Icon: IconEye },
  { id: "strike_density", label: "Strike History", Icon: IconChart },
];

const SEASONS: { id: Season; label: string }[] = [
  { id: null, label: "Annual" },
  { id: "winter", label: "Winter" },
  { id: "spring", label: "Spring" },
  { id: "summer", label: "Summer" },
  { id: "fall", label: "Fall" },
  { id: "all", label: "All" },
];

const ISDM_SPECIES: { id: IsdmSpecies; label: string; icon: string }[] = [
  { id: "blue_whale", label: "Blue Whale", icon: "🔵" },
  { id: "fin_whale", label: "Fin Whale", icon: "🟤" },
  { id: "humpback_whale", label: "Humpback", icon: "🟢" },
  { id: "sperm_whale", label: "Sperm Whale", icon: "⚫" },
];

/** Layers that show the species selector. */
const SPECIES_LAYERS = new Set<LayerType>([
  "whale_predictions",
  "sdm_predictions",
]);

/** Layers that show the traffic metric selector. */
const TRAFFIC_LAYERS = new Set<LayerType>(["traffic_density"]);

const TRAFFIC_METRICS: {
  id: TrafficMetric;
  label: string;
  icon: string;
  desc: string;
}[] = [
  {
    id: "vessel_density",
    label: "Vessel Density",
    icon: "📊",
    desc: "Monthly vessel count",
  },
  {
    id: "speed_lethality",
    label: "Speed Lethality",
    icon: "💀",
    desc: "V&T 2007 strike fatality index",
  },
  {
    id: "high_speed",
    label: "High Speed",
    icon: "⚡",
    desc: "Fraction at ≥10 kn lethal speed",
  },
  {
    id: "draft_risk",
    label: "Draft Risk",
    icon: "📐",
    desc: "Deep-draft vessel fraction (>8m)",
  },
  {
    id: "night_traffic",
    label: "Night Traffic",
    icon: "🌙",
    desc: "Night vessel ratio",
  },
  {
    id: "commercial",
    label: "Commercial",
    icon: "🏭",
    desc: "Cargo + tanker vessels",
  },
];

/* ── Props ───────────────────────────────────────────────── */

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
}

/* ── Sub-components ──────────────────────────────────────── */

function Toggle({
  label,
  checked,
  onChange,
  colorDot,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  colorDot?: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 py-0.5 text-sm text-slate-300">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="rounded border-ocean-700 bg-abyss-800 text-ocean-500 focus:ring-ocean-500"
      />
      {colorDot && (
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: colorDot }}
        />
      )}
      {label}
    </label>
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

      {/* ── Data Layer ── */}
      <section className="border-b border-ocean-800/30 p-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Data Layer
        </h2>
        <div className="space-y-1">
          {LAYERS.map((l) => (
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
            {ISDM_SPECIES.map((sp) => (
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
                <span className="mr-1">{sp.icon}</span>
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
                <span className="mr-2">{tm.icon}</span>
                {tm.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Season ── */}
      <section className="border-b border-ocean-800/30 p-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Season
        </h2>
        <div className="flex flex-wrap gap-1">
          {SEASONS.map((s) => (
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

      {/* ── Overlays ── */}
      <section className="p-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Overlays
        </h2>

        <div className="space-y-1">
          {/* Active SMAs */}
          <Toggle
            label="Active SMAs"
            checked={overlays.activeSMAs}
            colorDot="rgb(255, 80, 80)"
            onChange={(v) =>
              onOverlaysChange({ ...overlays, activeSMAs: v })
            }
          />

          {/* Proposed speed zones */}
          <Toggle
            label="Proposed Speed Zones"
            checked={overlays.proposedZones}
            colorDot="rgb(255, 200, 60)"
            onChange={(v) =>
              onOverlaysChange({ ...overlays, proposedZones: v })
            }
          />

          {/* MPAs */}
          <Toggle
            label="Marine Protected Areas"
            checked={overlays.mpas}
            colorDot="rgb(80, 200, 120)"
            onChange={(v) =>
              onOverlaysChange({ ...overlays, mpas: v })
            }
          />

          {/* Bathymetry contours (overview mode only) */}
          {viewMode === "overview" && (
            <Toggle
              label="Depth Contours"
              checked={showContours}
              colorDot="rgb(100, 180, 240)"
              onChange={onContoursChange}
            />
          )}
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
      </section>
    </div>
  );
}
