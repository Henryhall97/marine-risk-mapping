"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { API_BASE, mapLink } from "@/lib/config";
import {
  IconShield,
  IconMap,
  IconBuilding,
  IconChart,
  IconCalendar,
  IconMicroscope,
  IconPin,
  IconGlobe,
  IconTrending,
} from "@/components/icons/MarineIcons";

/* ── Types ──────────────────────────────────────────────── */

interface MacroCell {
  h3_cell: number;
  cell_lat: number;
  cell_lon: number;
  risk_score: number;
  ml_risk_score: number | null;
  traffic_score: number;
  cetacean_score: number | null;
  strike_score: number | null;
  habitat_score: number | null;
  protection_gap: number | null;
  proximity_score: number | null;
  reference_risk: number | null;
  total_sightings: number | null;
  total_strikes: number | null;
  any_whale_prob: number | null;
  depth_m_mean: number | null;
  shelf_fraction: number | null;
  avg_monthly_vessels: number | null;
  avg_speed_lethality: number | null;
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

function pct(v: number | null): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

/** Compute centroid of a cell array; fallback to East Coast default. */
function centroid(cells: MacroCell[], fallbackLat = 37.5, fallbackLon = -76) {
  if (cells.length === 0) return { lat: fallbackLat, lon: fallbackLon };
  const lat = cells.reduce((s, c) => s + c.cell_lat, 0) / cells.length;
  const lon = cells.reduce((s, c) => s + c.cell_lon, 0) / cells.length;
  return { lat, lon };
}

/* ── Stat card ──────────────────────────────────────────── */

function StatCard({
  label,
  value,
  sub,
  accent = "text-amber-400",
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

/* ── Progress bar ───────────────────────────────────────── */

function GapBar({
  label,
  count,
  total,
  color,
}: {
  label: string;
  count: number;
  total: number;
  color: string;
}) {
  const frac = total > 0 ? count / total : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="tabular-nums text-slate-500">
          {count.toLocaleString()} ({(frac * 100).toFixed(1)}%)
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-abyss-800">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${frac * 100}%` }}
        />
      </div>
    </div>
  );
}

/* ── Page ───────────────────────────────────────────────── */

export default function PolicyPage() {
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
  const total = cells.length;
  const highRisk = cells.filter((c) => c.risk_score >= 0.5);
  const critical = cells.filter((c) => c.risk_score >= 0.75);

  /* Protection gap analysis */
  const unprotected = cells.filter((c) => (c.protection_gap ?? 0) >= 0.8);
  const partiallyProtected = cells.filter(
    (c) => (c.protection_gap ?? 0) >= 0.4 && (c.protection_gap ?? 0) < 0.8,
  );
  const wellProtected = cells.filter((c) => (c.protection_gap ?? 0) < 0.4);

  /* High-risk + unprotected = priority for new regulation */
  const regulatoryPriority = cells.filter(
    (c) => c.risk_score >= 0.5 && (c.protection_gap ?? 0) >= 0.7,
  );

  /* Cells with whale activity but no speed zone */
  const whaleNoSpeed = cells.filter(
    (c) =>
      (c.any_whale_prob ?? 0) > 0.3 && (c.protection_gap ?? 0) >= 0.6,
  );

  /* Strike history hotspots */
  const strikeHotspots = cells
    .filter((c) => (c.total_strikes ?? 0) > 0)
    .sort((a, b) => (b.total_strikes ?? 0) - (a.total_strikes ?? 0))
    .slice(0, 15);

  /* Regulatory priority table — top 15 by combined score */
  const priorityTable = [...regulatoryPriority]
    .sort((a, b) => {
      const sa = a.risk_score * (a.protection_gap ?? 0);
      const sb = b.risk_score * (b.protection_gap ?? 0);
      return sb - sa;
    })
    .slice(0, 15);

  /* Seasonal comparison stats (shown for annual) */
  const avgRisk =
    total > 0
      ? cells.reduce((s, c) => s + c.risk_score, 0) / total
      : 0;
  const avgProtGap =
    total > 0
      ? cells.reduce((s, c) => s + (c.protection_gap ?? 0), 0) / total
      : 0;
  const avgTraffic =
    total > 0
      ? cells.reduce((s, c) => s + c.traffic_score, 0) / total
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
          <span className="text-amber-400">Policy Makers</span>
        </div>

        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-600 to-yellow-500 shadow-lg">
              <IconShield className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="font-display text-3xl font-extrabold tracking-tight text-white">
                Policy Maker Insights
              </h1>
              <p className="mt-1 max-w-xl text-sm text-slate-400">
                Protection gap analysis, regulatory effectiveness assessment,
                and priority areas for new conservation measures.
              </p>
            </div>
          </div>
          <Link
            href={mapLink({ lat: 37.5, lon: -76, layer: "risk", season, overlays: ["activeSMAs", "proposedZones", "mpas"] })}
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
                  ? "bg-amber-600/20 text-amber-400 shadow-sm"
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
              Loading policy intelligence…
            </div>
          </div>
        ) : (
          <>
            {/* Summary stats */}
            <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Total Assessed Cells"
                value={total.toLocaleString()}
                sub={`Avg risk: ${pct(avgRisk)}`}
                accent="text-slate-300"
              />
              <StatCard
                label="Critical/High-Risk"
                value={highRisk.length.toLocaleString()}
                sub={`${critical.length.toLocaleString()} critical (≥75%)`}
                accent="text-red-400"
                href={mapLink({ ...centroid(critical.length > 0 ? critical : highRisk), zoom: 7, layer: "risk", season, overlays: ["activeSMAs", "mpas"] })}
              />
              <StatCard
                label="Regulatory Priority"
                value={regulatoryPriority.length.toLocaleString()}
                sub="High risk + unprotected"
                accent="text-amber-400"
                href={mapLink({ ...centroid(regulatoryPriority), zoom: 7, layer: "risk", season, overlays: ["mpas", "proposedZones", "activeSMAs"] })}
              />
              <StatCard
                label="Avg Protection Gap"
                value={pct(avgProtGap)}
                sub="Lower is better protected"
                accent="text-yellow-400"
              />
            </div>

            {/* Protection gap breakdown */}
            <div className="mb-8 rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-6">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                Protection Coverage Analysis — {season}
              </h2>
              <div className="space-y-4">
                <GapBar
                  label="Well Protected (gap < 40%)"
                  count={wellProtected.length}
                  total={total}
                  color="bg-emerald-500"
                />
                <GapBar
                  label="Partially Protected (40–80%)"
                  count={partiallyProtected.length}
                  total={total}
                  color="bg-yellow-500"
                />
                <GapBar
                  label="Unprotected (gap ≥ 80%)"
                  count={unprotected.length}
                  total={total}
                  color="bg-red-500"
                />
              </div>
              <p className="mt-4 text-xs text-slate-600">
                Protection gap is a composite score based on MPA coverage type
                (no-take, multi-use, unprotected) and speed zone presence. A
                gap of 100% means no MPA or speed zone covers the cell.
                Proposed speed zones are excluded — only active SMAs count.
              </p>
            </div>

            {/* Policy recommendations */}
            <div className="mb-8 rounded-2xl border border-amber-800/30 bg-amber-950/20 p-6">
              <h2 className="mb-4 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-widest text-amber-400">
                <IconBuilding className="h-5 w-5" /> Policy Recommendations — {season}
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <span className="inline-block w-3 h-3 shrink-0 rounded-full" style={{backgroundColor: '#ef4444'}}></span> Immediate Priority
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • <strong className="text-amber-300">{regulatoryPriority.length.toLocaleString()}</strong>{" "}
                      cells are high-risk AND unprotected — strongest candidates
                      for new SMA/speed zone designations
                    </li>
                    <li>
                      • <strong className="text-amber-300">{whaleNoSpeed.length.toLocaleString()}</strong>{" "}
                      cells have significant whale activity (&gt;30% probability) but no
                      speed restrictions
                    </li>
                    <li>
                      • Converting proposed speed zones to active SMAs would immediately
                      cover additional high-risk corridors
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <IconChart className="h-4 w-4" /> SMA Effectiveness
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Current SMAs are voluntary — compliance varies by vessel
                      type and route pressure
                    </li>
                    <li>
                      • Average traffic score in active shipping areas:{" "}
                      <strong className="text-slate-300">{pct(avgTraffic)}</strong>
                    </li>
                    <li>
                      • Mandatory speed restrictions (vs. voluntary) show 80–90%
                      compliance in peer-reviewed studies (Conn & Silber 2013)
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <IconCalendar className="h-4 w-4" /> Seasonal Considerations
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Switch between seasons above to see how risk shifts —
                      whale distributions are highly seasonal
                    </li>
                    <li>
                      • Winter/spring: highest North Atlantic right whale presence
                      (calving, northward migration)
                    </li>
                    <li>
                      • Summer: peak humpback feeding aggregations on Georges Bank
                      and Stellwagen
                    </li>
                    <li>
                      • Consider dynamic management areas that activate based on
                      real-time whale detections
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <IconMicroscope className="h-4 w-4" /> ML vs Expert Assessment
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Our modelled risk layer can identify areas
                      that survey-based scoring misses
                    </li>
                    <li>
                      • The <Link href={mapLink({ lat: 37.5, lon: -76, layer: "risk_ml", season, overlays: ["activeSMAs", "mpas"] })} className="text-amber-400 hover:underline">risk map</Link>{" "}
                      offers side-by-side survey-based vs. modelled risk comparison
                    </li>
                    <li>
                      • ML model trained on 7 environmental covariates with spatial
                      cross-validation (H3 res-2 blocks)
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
                CMIP6 projections show how rising ocean temperatures will shift whale
                habitat and collision risk. Use these projections to plan
                forward-looking regulatory frameworks.
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
                    const projTotal = projCells.length;
                    const projHighRisk = projCells.filter((c) => c.risk_score >= 0.5);
                    const projCritical = projCells.filter((c) => c.risk_score >= 0.75);
                    const projRegPriority = projCells.filter(
                      (c) => c.risk_score >= 0.5 && (c.protection_gap ?? 0) >= 0.7,
                    );
                    const projWhaleNoSpeed = projCells.filter(
                      (c) => (c.any_whale_prob ?? 0) > 0.3 && (c.protection_gap ?? 0) >= 0.6,
                    );

                    const deltaHigh = projHighRisk.length - highRisk.length;
                    const deltaCrit = projCritical.length - critical.length;
                    const deltaReg = projRegPriority.length - regulatoryPriority.length;
                    const deltaWhale = projWhaleNoSpeed.length - whaleNoSpeed.length;

                    return (
                      <div className="space-y-5">
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                              Proj. High-Risk Cells
                            </p>
                            <p className="mt-1 text-xl font-bold text-red-400">
                              {projHighRisk.length.toLocaleString()}
                            </p>
                            <p className={`mt-0.5 text-xs font-semibold ${deltaHigh > 0 ? "text-red-400" : deltaHigh < 0 ? "text-green-400" : "text-slate-500"}`}>
                              {deltaHigh > 0 ? "↑ " : deltaHigh < 0 ? "↓ " : ""}{Math.abs(deltaHigh).toLocaleString()} vs current ({deltaCrit > 0 ? "+" : ""}{deltaCrit} critical)
                            </p>
                          </div>
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                              Proj. Regulatory Priority
                            </p>
                            <p className="mt-1 text-xl font-bold text-amber-400">
                              {projRegPriority.length.toLocaleString()}
                            </p>
                            <p className={`mt-0.5 text-xs font-semibold ${deltaReg > 0 ? "text-red-400" : deltaReg < 0 ? "text-green-400" : "text-slate-500"}`}>
                              {deltaReg > 0 ? "↑ " : deltaReg < 0 ? "↓ " : ""}{Math.abs(deltaReg).toLocaleString()} vs current
                            </p>
                          </div>
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                              Whale Zones w/o Speed Limit
                            </p>
                            <p className="mt-1 text-xl font-bold text-cyan-400">
                              {projWhaleNoSpeed.length.toLocaleString()}
                            </p>
                            <p className={`mt-0.5 text-xs font-semibold ${deltaWhale > 0 ? "text-orange-400" : deltaWhale < 0 ? "text-green-400" : "text-slate-500"}`}>
                              {deltaWhale > 0 ? "↑ " : deltaWhale < 0 ? "↓ " : ""}{Math.abs(deltaWhale).toLocaleString()} vs current
                            </p>
                          </div>
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                              Projected Grid Cells
                            </p>
                            <p className="mt-1 text-xl font-bold text-white">
                              {projTotal.toLocaleString()}
                            </p>
                            <Link
                              href={mapLink({ lat: 37.5, lon: -76, layer: "sdm_projections", season: season === "annual" ? "winter" : season, scenario: projScenario, decade: projDecade, overlays: ["mpas", "proposedZones"] })}
                              className="mt-0.5 text-[10px] text-cyan-400 hover:underline"
                            >
                              View projected map →
                            </Link>
                          </div>
                        </div>

                        <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                          <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                            <IconTrending className="h-4 w-4 text-cyan-400" /> Regulatory Implications
                          </h3>
                          <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                            <li>
                              • Under {projScenario === "ssp585" ? "high-emission" : "moderate"} scenarios
                              by the {projDecade}, <strong className="text-amber-300">{projRegPriority.length.toLocaleString()}</strong> cells
                              will need regulatory attention (high risk + unprotected)
                            </li>
                            <li>
                              • Whale distributions are expected to shift poleward as SST rises,
                              potentially creating new overlap zones with shipping lanes
                            </li>
                            <li>
                              • Existing SMA boundaries may need expansion or seasonal date adjustments
                              to track shifting whale habitat
                            </li>
                            <li>
                              • Dynamic management areas (DMAs) that respond to real-time conditions
                              may be more resilient to climate shifts than static zones
                            </li>
                          </ul>
                        </div>
                      </div>
                    );
                  })()}
                  <p className="mt-4 text-[10px] text-slate-600">
                    Projections use CMIP6 ISDM+SDM ensemble whale habitat models on
                    projected ocean conditions. Traffic is held constant.
                    {season === "annual" && " Annual view shows winter season projections."}
                  </p>
                </>
              )}
            </div>

            {/* Top regulatory priority areas */}
            {priorityTable.length > 0 && (
              <div className="mb-8 rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-6">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                  Top Regulatory Priority Areas — {season}
                </h2>
                <p className="mb-4 text-xs text-slate-600">
                  Cells ranked by risk × protection gap. These are the highest-risk
                  locations with the least existing regulatory protection.
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-ocean-800/30 text-left text-slate-500">
                        <th className="pb-2 pr-4">#</th>
                        <th className="pb-2 pr-4">Location</th>
                        <th className="pb-2 pr-4">Risk Score</th>
                        <th className="pb-2 pr-4">Protection Gap</th>
                        <th className="pb-2 pr-4">Whale P</th>
                        <th className="pb-2 pr-4">Traffic</th>
                        <th className="pb-2 pr-4">Strikes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ocean-800/20">
                      {priorityTable.map((c, i) => (
                        <tr key={c.h3_cell} className="text-slate-400">
                          <td className="py-2.5 pr-4 text-slate-600">
                            {i + 1}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            <Link
                              href={mapLink({ lat: c.cell_lat, lon: c.cell_lon, zoom: 8, layer: "risk", season, overlays: ["mpas", "proposedZones", "activeSMAs"] })}
                              className="text-amber-400 hover:text-amber-300 hover:underline"
                              title="View on map"
                            >
                              <IconPin className="mr-0.5 inline h-3 w-3" /> {c.cell_lat.toFixed(2)}°, {c.cell_lon.toFixed(2)}°
                            </Link>
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums text-red-400">
                            {pct(c.risk_score)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums text-amber-400">
                            {pct(c.protection_gap)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {pct(c.any_whale_prob)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {pct(c.traffic_score)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {c.total_strikes ?? 0}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Strike history hotspots */}
            {strikeHotspots.length > 0 && (
              <div className="rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-6">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                  Historical Ship Strike Hotspots
                </h2>
                <p className="mb-4 text-xs text-slate-600">
                  Areas with documented ship strike incidents (NOAA records). Only
                  67 of 261 documented strikes have precise geolocation, so this
                  underestimates the true distribution.
                </p>
                <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
                  {strikeHotspots.map((c) => (
                    <Link
                      key={c.h3_cell}
                      href={mapLink({ lat: c.cell_lat, lon: c.cell_lon, zoom: 9, layer: "strike_density", overlays: ["activeSMAs", "shippingLanes"] })}
                      className="rounded-lg border border-red-900/30 bg-red-950/20 px-3 py-2 text-center transition-all hover:border-red-700/50 hover:bg-red-950/40"
                    >
                      <p className="text-xs font-semibold tabular-nums text-red-400">
                        {c.total_strikes} strike{(c.total_strikes ?? 0) > 1 ? "s" : ""}
                      </p>
                      <p className="text-[10px] tabular-nums text-slate-500">
                        <IconPin className="mr-0.5 inline h-3 w-3" /> {c.cell_lat.toFixed(1)}°, {c.cell_lon.toFixed(1)}°
                      </p>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
