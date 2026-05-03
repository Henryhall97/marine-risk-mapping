"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { API_BASE, mapLink } from "@/lib/config";
import {
  IconShip,
  IconMap,
  IconWarning,
  IconBolt,
  IconTrending,
  IconCheck,
  IconAnchor,
  IconWhale,
  IconMoon,
  IconClipboard,
  IconPin,
  IconGlobe,
} from "@/components/icons/MarineIcons";

/* ── Types ──────────────────────────────────────────────── */

interface MacroCell {
  h3_cell: number;
  cell_lat: number;
  cell_lon: number;
  risk_score: number;
  traffic_score: number;
  avg_monthly_vessels: number | null;
  avg_speed_lethality: number | null;
  avg_high_speed_fraction: number | null;
  avg_draft_risk_fraction: number | null;
  night_traffic_ratio: number | null;
  avg_commercial_vessels: number | null;
  cetacean_score: number | null;
  strike_score: number | null;
  protection_gap: number | null;
  total_sightings: number | null;
  any_whale_prob: number | null;
  depth_m_mean: number | null;
}

type Season = "annual" | "winter" | "spring" | "summer" | "fall";
type Scenario = "ssp245" | "ssp585";
type Decade = "2030s" | "2040s" | "2060s" | "2080s";

const SEASONS: Season[] = ["annual", "winter", "spring", "summer", "fall"];
const SCENARIOS: { value: Scenario; label: string }[] = [
  { value: "ssp245", label: "SSP2-4.5 (moderate)" },
  { value: "ssp585", label: "SSP5-8.5 (high emissions)" },
];
const DECADES: Decade[] = ["2030s", "2040s", "2060s", "2080s"];

/* ── Helpers ────────────────────────────────────────────── */

function riskLabel(score: number): string {
  if (score >= 0.75) return "Critical";
  if (score >= 0.5) return "High";
  if (score >= 0.25) return "Medium";
  return "Low";
}

function riskColor(score: number): string {
  if (score >= 0.75) return "text-red-400";
  if (score >= 0.5) return "text-orange-400";
  if (score >= 0.25) return "text-yellow-400";
  return "text-green-400";
}

function riskBg(score: number): string {
  if (score >= 0.75) return "bg-red-500";
  if (score >= 0.5) return "bg-orange-500";
  if (score >= 0.25) return "bg-yellow-500";
  return "bg-green-500";
}

/** Compute centroid of a cell array; fallback to East Coast default. */
function centroid(cells: MacroCell[], fallbackLat = 37.5, fallbackLon = -76) {
  if (cells.length === 0) return { lat: fallbackLat, lon: fallbackLon };
  const lat = cells.reduce((s, c) => s + c.cell_lat, 0) / cells.length;
  const lon = cells.reduce((s, c) => s + c.cell_lon, 0) / cells.length;
  return { lat, lon };
}

function pct(v: number | null): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function speedGuidance(cell: MacroCell) {
  if ((cell.any_whale_prob ?? 0) > 0.5 && (cell.avg_speed_lethality ?? 0) > 0.4)
    return <span className="inline-flex items-center gap-1"><IconWarning className="h-3.5 w-3.5 shrink-0 text-red-400" /> SLOW to 10 kn — High whale probability + high lethality zone</span>;
  if ((cell.any_whale_prob ?? 0) > 0.3)
    return <span className="inline-flex items-center gap-1"><IconBolt className="h-3.5 w-3.5 shrink-0 text-yellow-400" /> Reduce to 12 kn — Moderate whale encounter probability</span>;
  if ((cell.protection_gap ?? 0) > 0.7)
    return <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 shrink-0 rounded-full" style={{backgroundColor: '#eab308'}}></span> Voluntary 10 kn — Unprotected high-risk area</span>;
  if ((cell.avg_high_speed_fraction ?? 0) > 0.3)
    return <span className="inline-flex items-center gap-1"><IconTrending className="h-3.5 w-3.5 shrink-0 text-orange-400" /> Reduce speed — Area has high-speed traffic concentration</span>;
  return <span className="inline-flex items-center gap-1"><IconCheck className="h-3.5 w-3.5 shrink-0 text-green-400" /> Standard transit — Monitor for marine mammals</span>;
}

/* ── Stat card ──────────────────────────────────────────── */

function StatCard({
  label,
  value,
  sub,
  accent = "text-blue-400",
  href,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
  href?: string;
}) {
  const inner = (
    <div className={`rounded-xl border border-ocean-800/30 bg-abyss-900/60 p-4 transition-all ${href ? "hover:border-ocean-600/50 hover:bg-abyss-800/60 cursor-pointer" : ""}`}>
      <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
        {label}
      </p>
      <p className={`mt-1 text-2xl font-bold ${accent}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
      {href && (
        <p className="mt-1.5 text-[10px] text-ocean-400">View on map →</p>
      )}
    </div>
  );
  if (href) return <Link href={href}>{inner}</Link>;
  return inner;
}

/* ── Bar ────────────────────────────────────────────────── */

function MetricBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-36 shrink-0 text-xs text-slate-400">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-abyss-800">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${Math.min(value * 100, 100)}%` }}
        />
      </div>
      <span className="w-12 text-right text-xs tabular-nums text-slate-400">
        {pct(value)}
      </span>
    </div>
  );
}

/* ── Page ───────────────────────────────────────────────── */

export default function CaptainsPage() {
  const [season, setSeason] = useState<Season>("annual");
  const [cells, setCells] = useState<MacroCell[]>([]);
  const [loading, setLoading] = useState(true);

  /* Projection state */
  const [projScenario, setProjScenario] = useState<Scenario>("ssp585");
  const [projDecade, setProjDecade] = useState<Decade>("2060s");
  const [projCells, setProjCells] = useState<MacroCell[]>([]);
  const [projLoading, setProjLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/macro/overview?season=${season}`,
      );
      if (res.ok) {
        const d = await res.json();
        setCells(d.data ?? []);
      }
    } finally {
      setLoading(false);
    }
  }, [season]);

  const fetchProjected = useCallback(async () => {
    const projSeason = season === "annual" ? "winter" : season;
    setProjLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/macro/overview?season=${projSeason}&scenario=${projScenario}&decade=${projDecade}`,
      );
      if (res.ok) {
        const d = await res.json();
        setProjCells(d.data ?? []);
      }
    } finally {
      setProjLoading(false);
    }
  }, [season, projScenario, projDecade]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    fetchProjected();
  }, [fetchProjected]);

  /* Derived analytics */
  const trafficCells = cells.filter((c) => c.traffic_score > 0);
  const highRisk = cells.filter((c) => c.risk_score >= 0.5);
  const whaleZones = cells.filter((c) => (c.any_whale_prob ?? 0) > 0.3);
  const highSpeedZones = cells.filter(
    (c) => (c.avg_high_speed_fraction ?? 0) > 0.3,
  );
  const nightHeavy = cells.filter(
    (c) => (c.night_traffic_ratio ?? 0) > 0.3,
  );

  /* Top 10 riskiest shipping cells */
  const riskiestShipping = [...trafficCells]
    .sort((a, b) => {
      const sa = a.risk_score * a.traffic_score;
      const sb = b.risk_score * b.traffic_score;
      return sb - sa;
    })
    .slice(0, 10);

  /* Average stats */
  const avgSpeed =
    trafficCells.length > 0
      ? trafficCells.reduce((s, c) => s + (c.avg_speed_lethality ?? 0), 0) /
        trafficCells.length
      : 0;
  const avgDraft =
    trafficCells.length > 0
      ? trafficCells.reduce((s, c) => s + (c.avg_draft_risk_fraction ?? 0), 0) /
        trafficCells.length
      : 0;
  const avgNight =
    trafficCells.length > 0
      ? trafficCells.reduce((s, c) => s + (c.night_traffic_ratio ?? 0), 0) /
        trafficCells.length
      : 0;

  return (
    <main className="min-h-screen bg-abyss-950 px-4 pb-20 pt-24">
      <div className="mx-auto max-w-6xl">
        {/* Breadcrumb */}
        <div className="mb-6 flex items-center gap-2 text-xs text-slate-500">
          <Link href="/insights" className="hover:text-ocean-400">
            Insights
          </Link>
          <span>/</span>
          <span className="text-blue-400">Vessel Captains</span>
        </div>

        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-500 shadow-lg">
              <IconShip className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="font-display text-3xl font-extrabold tracking-tight text-white">
                Vessel Captain Insights
              </h1>
              <p className="mt-1 max-w-xl text-sm text-slate-400">
                Route-level risk intelligence, speed guidance, and species
                awareness for safe navigation through whale habitat areas.
              </p>
            </div>
          </div>
          <Link
            href={mapLink({ lat: 37.5, lon: -76, layer: "risk", season, overlays: ["activeSMAs", "shippingLanes"] })}
            className="flex items-center gap-1.5 rounded-lg border border-ocean-800 bg-abyss-900 px-4 py-2 text-xs font-medium text-slate-300 transition-all hover:border-ocean-600 hover:text-white"
          >
            <IconMap className="h-3.5 w-3.5" />
            Open Risk Map
          </Link>
        </div>

        {/* Season selector */}
        <div className="mb-8 flex gap-1 rounded-xl border border-ocean-800/30 bg-abyss-900/60 p-1">
          {SEASONS.map((s) => (
            <button
              key={s}
              onClick={() => setSeason(s)}
              className={`rounded-lg px-4 py-2 text-xs font-medium capitalize transition-all ${
                season === s
                  ? "bg-blue-600/20 text-blue-400 shadow-sm"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="animate-pulse text-sm text-slate-500">
              Loading navigation intelligence…
            </div>
          </div>
        ) : (
          <>
            {/* Summary stats */}
            <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="High-Risk Shipping Cells"
                value={highRisk.length.toLocaleString()}
                sub={`of ${cells.length.toLocaleString()} total cells`}
                accent="text-red-400"
                href={mapLink({ ...centroid(highRisk), zoom: 7, layer: "risk", season, overlays: ["activeSMAs", "shippingLanes"] })}
              />
              <StatCard
                label="Whale Encounter Zones"
                value={whaleZones.length.toLocaleString()}
                sub="> 30% whale probability"
                accent="text-cyan-400"
                href={mapLink({ ...centroid(whaleZones), zoom: 7, layer: "whale_predictions", season, overlays: ["criticalHabitat", "slowZones"] })}
              />
              <StatCard
                label="High-Speed Traffic Zones"
                value={highSpeedZones.length.toLocaleString()}
                sub="> 30% high-speed fraction"
                accent="text-orange-400"
                href={mapLink({ ...centroid(highSpeedZones), zoom: 7, layer: "traffic_density", season, metric: "high_speed", overlays: ["activeSMAs"] })}
              />
              <StatCard
                label="Heavy Night-Transit Areas"
                value={nightHeavy.length.toLocaleString()}
                sub="> 30% night traffic ratio"
                accent="text-purple-400"
                href={mapLink({ ...centroid(nightHeavy), zoom: 7, layer: "traffic_density", season, metric: "night_traffic", overlays: ["shippingLanes"] })}
              />
            </div>

            {/* Fleet-wide risk factors */}
            <div className="mb-8 rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-6">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                Fleet-Wide Risk Factors ({season})
              </h2>
              <div className="space-y-3">
                <MetricBar
                  label="Avg Speed Lethality"
                  value={avgSpeed}
                  color="bg-red-500"
                />
                <MetricBar
                  label="Avg Draft Risk"
                  value={avgDraft}
                  color="bg-orange-500"
                />
                <MetricBar
                  label="Avg Night Traffic"
                  value={avgNight}
                  color="bg-purple-500"
                />
              </div>
              <p className="mt-4 text-xs text-slate-600">
                Speed lethality is derived from the Van der Hoop & Vanderlaan
                (2007) logistic model: P(lethal) = 1/(1 + e^(−(β₀ + β₁·speed))).
                Values above 40% indicate speeds where most strikes are fatal.
              </p>
            </div>

            {/* Key recommendations */}
            <div className="mb-8 rounded-2xl border border-blue-800/30 bg-blue-950/20 p-6">
              <h2 className="mb-4 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-widest text-blue-400">
                <IconAnchor className="h-5 w-5" /> Key Recommendations — {season}
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <IconWhale className="h-4 w-4" /> Whale Avoidance
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • <strong className="text-slate-300">{whaleZones.length.toLocaleString()}</strong>{" "}
                      cells have &gt;30% whale encounter probability this {season}
                    </li>
                    <li>
                      • Post dedicated lookouts in these areas, especially during dawn/dusk
                    </li>
                    <li>
                      • North Atlantic right whales are ESA-listed — maintain ≥500 yd distance
                    </li>
                    <li>
                      • Humpback and fin whales: maintain ≥100 yd under MMPA
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <IconShip className="h-4 w-4" /> Speed Management
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Average fleet speed lethality: <strong className="text-slate-300">{pct(avgSpeed)}</strong>
                    </li>
                    <li>
                      • Reducing from 15 kn → 10 kn cuts lethality by ~80% (V&T model)
                    </li>
                    <li>
                      • SMAs (Nov–Apr, East Coast) mandate ≤10 kn for vessels ≥65 ft
                    </li>
                    <li>
                      • Voluntary compliance in proposed speed zones strongly recommended
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <IconMoon className="h-4 w-4" /> Night Navigation
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • <strong className="text-slate-300">{nightHeavy.length.toLocaleString()}</strong>{" "}
                      cells have heavy night traffic (&gt;30%)
                    </li>
                    <li>
                      • Whale detection drops by ~90% at night — passive avoidance is critical
                    </li>
                    <li>
                      • Consider infrared or thermal detection systems in high-risk corridors
                    </li>
                    <li>
                      • Route through lower-risk cells when possible during dark hours
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <IconClipboard className="h-4 w-4" /> Reporting Obligations
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Report all whale strikes to NOAA within 24 hours (MMPA requirement)
                    </li>
                    <li>
                      • Use our <Link href="/report" className="text-blue-400 hover:underline">Report Interaction</Link>{" "}
                      tool for sightings with photo/audio classification
                    </li>
                    <li>
                      • Report entangled or injured whales to the regional stranding hotline
                    </li>
                    <li>
                      • Community-verified sightings improve model accuracy for all users
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            {/* ── Climate Projection Outlook ──────────────── */}
            <div className="mb-8 rounded-2xl border border-cyan-800/30 bg-cyan-950/15 p-6">
              <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-widest text-cyan-400">
                <IconGlobe className="h-5 w-5" /> Climate Projection Outlook
              </h2>
              <p className="mb-4 text-xs text-slate-500">
                CMIP6 climate models project how whale habitat and collision risk
                may shift under different emission scenarios. Plan ahead for
                changing risk corridors.
              </p>

              {/* Scenario / decade selector */}
              <div className="mb-5 flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Scenario</span>
                  <div className="flex gap-1 rounded-lg border border-ocean-800/30 bg-abyss-900/60 p-0.5">
                    {SCENARIOS.map((s) => (
                      <button
                        key={s.value}
                        onClick={() => setProjScenario(s.value)}
                        className={`rounded-md px-3 py-1.5 text-[11px] font-medium transition-all ${
                          projScenario === s.value
                            ? "bg-cyan-600/20 text-cyan-400"
                            : "text-slate-500 hover:text-slate-300"
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Decade</span>
                  <div className="flex gap-1 rounded-lg border border-ocean-800/30 bg-abyss-900/60 p-0.5">
                    {DECADES.map((d) => (
                      <button
                        key={d}
                        onClick={() => setProjDecade(d)}
                        className={`rounded-md px-3 py-1.5 text-[11px] font-medium transition-all ${
                          projDecade === d
                            ? "bg-cyan-600/20 text-cyan-400"
                            : "text-slate-500 hover:text-slate-300"
                        }`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {projLoading ? (
                <div className="flex h-24 items-center justify-center">
                  <span className="animate-pulse text-xs text-slate-500">Loading projections…</span>
                </div>
              ) : projCells.length === 0 ? (
                <p className="text-xs text-slate-600">No projection data available for this selection.</p>
              ) : (
                <>
                  {(() => {
                    const projHighRisk = projCells.filter((c) => c.risk_score >= 0.5);
                    const projWhaleZones = projCells.filter((c) => (c.any_whale_prob ?? 0) > 0.3);
                    const projHighSpeed = projCells.filter((c) => (c.avg_high_speed_fraction ?? 0) > 0.3);
                    const deltaRisk = projHighRisk.length - highRisk.length;
                    const deltaWhale = projWhaleZones.length - whaleZones.length;

                    return (
                      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                            Projected High-Risk Cells
                          </p>
                          <p className="mt-1 text-xl font-bold text-red-400">
                            {projHighRisk.length.toLocaleString()}
                          </p>
                          <p className={`mt-0.5 text-xs font-semibold ${deltaRisk > 0 ? "text-red-400" : deltaRisk < 0 ? "text-green-400" : "text-slate-500"}`}>
                            {deltaRisk > 0 ? "+" : ""}{deltaRisk.toLocaleString()} vs current
                          </p>
                        </div>
                        <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                            Projected Whale Zones
                          </p>
                          <p className="mt-1 text-xl font-bold text-cyan-400">
                            {projWhaleZones.length.toLocaleString()}
                          </p>
                          <p className={`mt-0.5 text-xs font-semibold ${deltaWhale > 0 ? "text-orange-400" : deltaWhale < 0 ? "text-green-400" : "text-slate-500"}`}>
                            {deltaWhale > 0 ? "+" : ""}{deltaWhale.toLocaleString()} vs current
                          </p>
                        </div>
                        <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                            High-Speed Overlap
                          </p>
                          <p className="mt-1 text-xl font-bold text-orange-400">
                            {projHighSpeed.length.toLocaleString()}
                          </p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            zones with &gt;30% fast traffic
                          </p>
                        </div>
                        <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                            Scenario / Decade
                          </p>
                          <p className="mt-1 text-xl font-bold text-white">
                            {projScenario === "ssp585" ? "High" : "Mod."} {projDecade}
                          </p>
                          <Link
                            href={mapLink({ lat: 37.5, lon: -76, layer: "sdm_projections", season: season === "annual" ? "winter" : season, scenario: projScenario, decade: projDecade, overlays: ["shippingLanes"] })}
                            className="mt-0.5 text-[10px] text-cyan-400 hover:underline"
                          >
                            View projected map →
                          </Link>
                        </div>
                      </div>
                    );
                  })()}
                  <p className="mt-4 text-[10px] text-slate-600">
                    Climate projections use CMIP6 ISDM+SDM ensemble species habitat
                    models scored on projected ocean covariates (SST, MLD, SLA, PP).
                    Traffic patterns are held constant — only whale distributions shift.
                    {season === "annual" && " Annual view shows winter season projections."}
                  </p>
                </>
              )}
            </div>

            {/* Top 10 riskiest shipping lanes */}
            <div className="rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-6">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                Top 10 Highest-Risk Shipping Zones — {season}
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-ocean-800/30 text-left text-slate-500">
                      <th className="pb-2 pr-4">#</th>
                      <th className="pb-2 pr-4">Location</th>
                      <th className="pb-2 pr-4">Risk</th>
                      <th className="pb-2 pr-4">Traffic</th>
                      <th className="pb-2 pr-4">Whale P</th>
                      <th className="pb-2 pr-4">Speed Rec.</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ocean-800/20">
                    {riskiestShipping.map((c, i) => (
                      <tr key={c.h3_cell} className="text-slate-400">
                        <td className="py-2.5 pr-4 text-slate-600">
                          {i + 1}
                        </td>
                        <td className="py-2.5 pr-4 tabular-nums">
                          <Link
                            href={mapLink({ lat: c.cell_lat, lon: c.cell_lon, zoom: 8, layer: "risk", season, overlays: ["activeSMAs", "shippingLanes"] })}
                            className="text-blue-400 hover:text-blue-300 hover:underline"
                            title="View on map"
                          >
                            <IconPin className="mr-0.5 inline h-3 w-3" /> {c.cell_lat.toFixed(2)}°, {c.cell_lon.toFixed(2)}°
                          </Link>
                        </td>
                        <td className="py-2.5 pr-4">
                          <span
                            className={`inline-flex items-center gap-1 ${riskColor(c.risk_score)}`}
                          >
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${riskBg(c.risk_score)}`}
                            />
                            {riskLabel(c.risk_score)}{" "}
                            <span className="text-slate-600">
                              ({(c.risk_score * 100).toFixed(0)}%)
                            </span>
                          </span>
                        </td>
                        <td className="py-2.5 pr-4 tabular-nums">
                          {pct(c.traffic_score)}
                        </td>
                        <td className="py-2.5 pr-4 tabular-nums">
                          {pct(c.any_whale_prob)}
                        </td>
                        <td className="py-2.5 pr-4 text-[11px]">
                          {speedGuidance(c)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
