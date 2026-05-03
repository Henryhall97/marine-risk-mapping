"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { API_BASE, mapLink } from "@/lib/config";
import {
  IconShip,
  IconMap,
  IconAnchor,
  IconClipboard,
  IconWaves,
  IconHandshake,
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
  cetacean_score: number | null;
  habitat_score: number | null;
  protection_gap: number | null;
  total_sightings: number | null;
  total_strikes: number | null;
  any_whale_prob: number | null;
  avg_monthly_vessels: number | null;
  avg_speed_lethality: number | null;
  avg_high_speed_fraction: number | null;
  avg_draft_risk_fraction: number | null;
  night_traffic_ratio: number | null;
  avg_commercial_vessels: number | null;
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

function num(v: number | null, d: number = 0): string {
  if (v == null) return "—";
  return v.toFixed(d);
}

function StatCard({
  label,
  value,
  sub,
  accent = "text-rose-400",
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

function Bar({
  value,
  color = "bg-rose-500",
}: {
  value: number;
  color?: string;
}) {
  return (
    <div className="h-2 w-full rounded-full bg-abyss-800">
      <div
        className={`h-2 rounded-full ${color}`}
        style={{ width: `${Math.min(value * 100, 100)}%` }}
      />
    </div>
  );
}

/* ── Page ───────────────────────────────────────────────── */

export default function PortsPage() {
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
  const trafficCells = cells.filter((c) => c.traffic_score > 0);

  const avgVessels =
    trafficCells.length > 0
      ? trafficCells.reduce((s, c) => s + (c.avg_monthly_vessels ?? 0), 0) /
        trafficCells.length
      : 0;

  const avgCommercial =
    trafficCells.length > 0
      ? trafficCells.reduce((s, c) => s + (c.avg_commercial_vessels ?? 0), 0) /
        trafficCells.length
      : 0;

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

  const avgHighSpeed =
    trafficCells.length > 0
      ? trafficCells.reduce((s, c) => s + (c.avg_high_speed_fraction ?? 0), 0) /
        trafficCells.length
      : 0;

  /* Port-adjacent: high traffic cells */
  const denseTraffic = [...cells]
    .filter((c) => (c.avg_monthly_vessels ?? 0) > 10)
    .sort(
      (a, b) =>
        (b.avg_monthly_vessels ?? 0) - (a.avg_monthly_vessels ?? 0),
    );

  /* High-risk port approach: high traffic + high risk */
  const riskyApproaches = cells.filter(
    (c) => c.traffic_score > 0.5 && c.risk_score > 0.5,
  );

  /* Whale encounters near port areas (high traffic + whale presence) */
  const whaleTrafficOverlap = cells.filter(
    (c) => c.traffic_score > 0.3 && (c.any_whale_prob ?? 0) > 0.2,
  );

  /* Shallow draft areas (depth < 50m) */
  const shallowCells = cells.filter(
    (c) => (c.depth_m_mean ?? 0) > -50 && (c.depth_m_mean ?? 0) < 0,
  );

  return (
    <main className="min-h-screen bg-abyss-950 px-4 pb-20 pt-24">
      <div className="mx-auto max-w-6xl">
        {/* Breadcrumb */}
        <div className="mb-6 flex items-center gap-2 text-xs text-slate-500">
          <Link href="/insights" className="hover:text-ocean-400">
            Insights
          </Link>
          <span>/</span>
          <span className="text-rose-400">Port Authorities</span>
        </div>

        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-rose-600 to-pink-500 shadow-lg">
              <IconShip className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="font-display text-3xl font-extrabold tracking-tight text-white">
                Port Authority Insights
              </h1>
              <p className="mt-1 max-w-xl text-sm text-slate-400">
                Vessel traffic analysis, approach lane risk profiles, commercial
                fleet density, and whale encounter zones for port operations.
              </p>
            </div>
          </div>
          <Link
            href={mapLink({ lat: 37.5, lon: -76, layer: "traffic_density", season, metric: "commercial", overlays: ["shippingLanes", "activeSMAs"] })}
            className="flex items-center gap-1.5 rounded-lg border border-ocean-800 bg-abyss-900 px-4 py-2 text-xs font-medium text-slate-300 transition-all hover:border-ocean-600 hover:text-white"
          >
            <IconMap className="h-3.5 w-3.5" />
            Open Traffic Map
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
                  ? "bg-rose-600/20 text-rose-400 shadow-sm"
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
              Loading port data…
            </div>
          </div>
        ) : (
          <>
            {/* Summary stats */}
            <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Active Traffic Cells"
                value={trafficCells.length.toLocaleString()}
                sub={`of ${total.toLocaleString()} total`}
                accent="text-rose-400"
                href={mapLink({ ...centroid(trafficCells), zoom: 6, layer: "traffic_density", season, metric: "vessel_density", overlays: ["shippingLanes"] })}
              />
              <StatCard
                label="Avg Monthly Vessels"
                value={num(avgVessels, 1)}
                sub="per cell with traffic"
                accent="text-pink-400"
              />
              <StatCard
                label="Avg Commercial Vessels"
                value={num(avgCommercial, 1)}
                sub="cargo, tanker, bulk per cell"
                accent="text-orange-400"
              />
              <StatCard
                label="Risky Approaches"
                value={riskyApproaches.length.toLocaleString()}
                sub="high traffic + high collision risk"
                accent="text-red-400"
                href={mapLink({ ...centroid(riskyApproaches), zoom: 7, layer: "risk", season, overlays: ["shippingLanes", "activeSMAs", "slowZones"] })}
              />
            </div>

            {/* Fleet risk profile */}
            <div className="mb-8 rounded-2xl border border-rose-800/30 bg-rose-950/20 p-6">
              <h2 className="mb-4 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-widest text-rose-400">
                <IconAnchor className="h-5 w-5" /> Fleet-Wide Risk Profile — {season}
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs text-slate-400">
                      Speed Lethality Index
                    </span>
                    <span className="text-xs font-bold text-red-400">
                      {pct(avgSpeed)}
                    </span>
                  </div>
                  <Bar value={avgSpeed} color="bg-red-500" />
                  <p className="mt-2 text-[10px] text-slate-500">
                    Probability of lethal strike at average fleet speeds
                  </p>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs text-slate-400">
                      High-Speed Fraction
                    </span>
                    <span className="text-xs font-bold text-orange-400">
                      {pct(avgHighSpeed)}
                    </span>
                  </div>
                  <Bar value={avgHighSpeed} color="bg-orange-500" />
                  <p className="mt-2 text-[10px] text-slate-500">
                    Fraction of transits exceeding 10 knots
                  </p>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs text-slate-400">
                      Draft Risk Fraction
                    </span>
                    <span className="text-xs font-bold text-amber-400">
                      {pct(avgDraft)}
                    </span>
                  </div>
                  <Bar value={avgDraft} color="bg-amber-500" />
                  <p className="mt-2 text-[10px] text-slate-500">
                    Deep-draft vessels (higher strike severity)
                  </p>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs text-slate-400">
                      Night Traffic Ratio
                    </span>
                    <span className="text-xs font-bold text-indigo-400">
                      {pct(avgNight)}
                    </span>
                  </div>
                  <Bar value={avgNight} color="bg-indigo-500" />
                  <p className="mt-2 text-[10px] text-slate-500">
                    Nighttime transit share (reduced visibility)
                  </p>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs text-slate-400">
                      Whale–Traffic Overlap
                    </span>
                    <span className="text-xs font-bold text-cyan-400">
                      {whaleTrafficOverlap.length.toLocaleString()} cells
                    </span>
                  </div>
                  <Bar
                    value={total > 0 ? whaleTrafficOverlap.length / total : 0}
                    color="bg-cyan-500"
                  />
                  <p className="mt-2 text-[10px] text-slate-500">
                    Areas where wildlife avoidance may be needed
                  </p>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs text-slate-400">
                      Shallow-Water Cells
                    </span>
                    <span className="text-xs font-bold text-emerald-400">
                      {shallowCells.length.toLocaleString()}
                    </span>
                  </div>
                  <Bar
                    value={total > 0 ? shallowCells.length / total : 0}
                    color="bg-emerald-500"
                  />
                  <p className="mt-2 text-[10px] text-slate-500">
                    Depth &lt; 50m — under-keel clearance considerations
                  </p>
                </div>
              </div>
            </div>

            {/* Operational recommendations */}
            <div className="mb-8">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                Operational Recommendations
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/60 p-5">
                  <h3 className="mb-2 flex items-center gap-1 text-sm font-bold text-white">
                    <IconShip className="h-4 w-4" /> Vessel Traffic Management
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Implement dynamic speed advisories for approach lanes
                      with high whale probability
                    </li>
                    <li>
                      • Coordinate vessel scheduling to reduce simultaneous
                      transits in high-risk corridors
                    </li>
                    <li>
                      • Monitor seasonal changes in whale distribution to adjust
                      traffic patterns
                    </li>
                    <li>
                      • Share real-time whale sighting data with harbour pilots
                      and approaching vessels
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/60 p-5">
                  <h3 className="mb-2 flex items-center gap-1 text-sm font-bold text-white">
                    <IconClipboard className="h-4 w-4" /> Compliance & Reporting
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Enforce 10-knot speed limits in active Seasonal
                      Management Areas (SMAs)
                    </li>
                    <li>
                      • Track vessel compliance rates in whale-sensitive
                      approach lanes
                    </li>
                    <li>
                      • Mandate whale strike reporting for all port-calling
                      vessels
                    </li>
                    <li>
                      • Include collision-risk briefings in port arrival
                      information packages
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/60 p-5">
                  <h3 className="mb-2 flex items-center gap-1 text-sm font-bold text-white">
                    <IconWaves className="h-4 w-4" /> Seasonal Awareness
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Spring/summer: peak whale activity in Northeast
                      approach lanes — heightened lookout measures
                    </li>
                    <li>
                      • Winter: right whale calving in Southeast — mandatory
                      speed zones active
                    </li>
                    <li>
                      • Fall: humpback migration along East Coast — review
                      approach route alternatives
                    </li>
                    <li>
                      • Use seasonal filters on this page to see how risk
                      patterns shift quarterly
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/30 bg-abyss-900/60 p-5">
                  <h3 className="mb-2 flex items-center gap-1 text-sm font-bold text-white">
                    <IconHandshake className="h-4 w-4" /> Stakeholder Coordination
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Coordinate with NOAA on dynamic management area
                      activations near port approaches
                    </li>
                    <li>
                      • Share port traffic density data with conservation
                      groups for collaborative risk reduction
                    </li>
                    <li>
                      • Engage shipping companies on voluntary slow-steaming
                      programs in high-risk corridors
                    </li>
                    <li>
                      • Support community sighting networks to enhance
                      near-real-time whale awareness
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            {/* ── Climate Projection Outlook ──────────────── */}
            <div className="mb-8 rounded-2xl border border-cyan-800/30 bg-cyan-950/15 p-6">
              <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-widest text-cyan-400">
                <IconGlobe className="h-5 w-5" /> Future Risk Projections
              </h2>
              <p className="mb-4 text-xs text-slate-500">
                Climate change will shift whale distributions and create new
                overlap zones near port approaches. Plan port operations and
                infrastructure investments with these projections in mind.
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
                    const projTraffic = projCells.filter((c) => c.traffic_score > 0);
                    const projRisky = projCells.filter(
                      (c) => c.traffic_score > 0.5 && c.risk_score > 0.5,
                    );
                    const projWhaleTraffic = projCells.filter(
                      (c) => c.traffic_score > 0.3 && (c.any_whale_prob ?? 0) > 0.2,
                    );

                    const deltaRisky = projRisky.length - riskyApproaches.length;
                    const deltaOverlap = projWhaleTraffic.length - whaleTrafficOverlap.length;

                    return (
                      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                            Proj. Risky Approaches
                          </p>
                          <p className="mt-1 text-xl font-bold text-red-400">
                            {projRisky.length.toLocaleString()}
                          </p>
                          <p className={`mt-0.5 text-xs font-semibold ${deltaRisky > 0 ? "text-red-400" : deltaRisky < 0 ? "text-green-400" : "text-slate-500"}`}>
                            {deltaRisky > 0 ? "↑ " : deltaRisky < 0 ? "↓ " : ""}{Math.abs(deltaRisky).toLocaleString()} vs current
                          </p>
                        </div>
                        <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                            Proj. Whale–Traffic Overlap
                          </p>
                          <p className="mt-1 text-xl font-bold text-cyan-400">
                            {projWhaleTraffic.length.toLocaleString()}
                          </p>
                          <p className={`mt-0.5 text-xs font-semibold ${deltaOverlap > 0 ? "text-orange-400" : deltaOverlap < 0 ? "text-green-400" : "text-slate-500"}`}>
                            {deltaOverlap > 0 ? "↑ " : deltaOverlap < 0 ? "↓ " : ""}{Math.abs(deltaOverlap).toLocaleString()} vs current
                          </p>
                        </div>
                        <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                            Traffic Cells (Projected)
                          </p>
                          <p className="mt-1 text-xl font-bold text-rose-400">
                            {projTraffic.length.toLocaleString()}
                          </p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            of {projCells.length.toLocaleString()} total
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
                            href={mapLink({ lat: 37.5, lon: -76, layer: "sdm_projections", season: season === "annual" ? "winter" : season, scenario: projScenario, decade: projDecade, overlays: ["shippingLanes", "activeSMAs"] })}
                            className="mt-0.5 text-[10px] text-cyan-400 hover:underline"
                          >
                            View projected risk map →
                          </Link>
                        </div>
                      </div>
                    );
                  })()}
                  <p className="mt-4 text-[10px] text-slate-600">
                    Whale distributions shift under CMIP6 projections; vessel
                    traffic patterns are held constant. New whale–ship overlap
                    zones near port approaches may require updated speed
                    management and lookout protocols.
                    {season === "annual" && " Annual view shows winter projections."}
                  </p>
                </>
              )}
            </div>

            {/* Top traffic density table */}
            {denseTraffic.length > 0 && (
              <div className="rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-6">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                  Highest-Density Traffic Zones — {season}
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-ocean-800/30 text-left text-slate-500">
                        <th className="pb-2 pr-4">#</th>
                        <th className="pb-2 pr-4">Location</th>
                        <th className="pb-2 pr-4">Monthly Vessels</th>
                        <th className="pb-2 pr-4">Commercial</th>
                        <th className="pb-2 pr-4">High Speed</th>
                        <th className="pb-2 pr-4">Night Traffic</th>
                        <th className="pb-2 pr-4">Whale Risk</th>
                        <th className="pb-2 pr-4">Risk Score</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ocean-800/20">
                      {denseTraffic.slice(0, 15).map((c, i) => (
                        <tr key={c.h3_cell} className="text-slate-400">
                          <td className="py-2.5 pr-4 text-slate-600">
                            {i + 1}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            <Link
                              href={mapLink({ lat: c.cell_lat, lon: c.cell_lon, zoom: 8, layer: "traffic_density", season, metric: "commercial", overlays: ["shippingLanes", "activeSMAs"] })}
                              className="text-rose-400 hover:text-rose-300 hover:underline"
                              title="View traffic density on map"
                            >
                              <IconPin className="mr-0.5 inline h-3 w-3" /> {c.cell_lat.toFixed(2)}°, {c.cell_lon.toFixed(2)}°
                            </Link>
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums text-rose-400">
                            {num(c.avg_monthly_vessels, 0)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {num(c.avg_commercial_vessels, 0)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums text-orange-400">
                            {pct(c.avg_high_speed_fraction)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums text-indigo-400">
                            {pct(c.night_traffic_ratio)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums text-cyan-400">
                            {pct(c.any_whale_prob)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {pct(c.risk_score)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
