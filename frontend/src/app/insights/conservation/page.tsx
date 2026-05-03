"use client";

import Link from "next/link";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { API_BASE, mapLink } from "@/lib/config";
import {
  IconWhale,
  IconMap,
  IconDolphin,
  IconShield,
  IconSpeaker,
  IconChart,
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
  strike_score: number | null;
  habitat_score: number | null;
  protection_gap: number | null;
  proximity_score: number | null;
  total_sightings: number | null;
  baleen_sightings: number | null;
  total_strikes: number | null;
  any_whale_prob: number | null;
  isdm_blue_whale: number | null;
  isdm_fin_whale: number | null;
  isdm_humpback_whale: number | null;
  isdm_sperm_whale: number | null;
  sdm_right_whale: number | null;
  depth_m_mean: number | null;
  shelf_fraction: number | null;
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

function StatCard({
  label,
  value,
  sub,
  accent = "text-emerald-400",
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

/* ── Species card ───────────────────────────────────────── */

interface SpeciesData {
  name: string;
  icon: ReactNode;
  color: string;
  border: string;
  highProbCells: number;
  avgProb: number | null;
  strikeCells: number;
  threatLevel: string;
  threatColor: string;
  insight: string;
}

function SpeciesCard({ sp }: { sp: SpeciesData }) {
  return (
    <div className={`rounded-xl border ${sp.border} bg-abyss-900/60 p-4`}>
      <div className="mb-2 flex items-center justify-between">
        <h3 className={`text-sm font-bold ${sp.color} flex items-center gap-1.5`}>
          {sp.icon} {sp.name}
        </h3>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${sp.threatColor}`}
        >
          {sp.threatLevel}
        </span>
      </div>
      <div className="mb-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-lg font-bold text-white">
            {sp.highProbCells.toLocaleString()}
          </p>
          <p className="text-[10px] text-slate-500">High-P Cells</p>
        </div>
        <div>
          <p className="text-lg font-bold text-white">{pct(sp.avgProb)}</p>
          <p className="text-[10px] text-slate-500">Mean Prob</p>
        </div>
        <div>
          <p className="text-lg font-bold text-white">{sp.strikeCells}</p>
          <p className="text-[10px] text-slate-500">Strike Zones</p>
        </div>
      </div>
      <p className="text-[11px] leading-relaxed text-slate-400">
        {sp.insight}
      </p>
    </div>
  );
}

/* ── Page ───────────────────────────────────────────────── */

export default function ConservationPage() {
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
  const sightingCells = cells.filter((c) => (c.total_sightings ?? 0) > 0);
  const baleenCells = cells.filter((c) => (c.baleen_sightings ?? 0) > 0);
  const strikeCells = cells.filter((c) => (c.total_strikes ?? 0) > 0);
  const criticalHabitat = cells.filter(
    (c) =>
      (c.any_whale_prob ?? 0) > 0.5 &&
      (c.habitat_score ?? 0) > 0.3,
  );

  /* Threat overlap: high whale + high traffic */
  const threatOverlap = cells.filter(
    (c) =>
      (c.any_whale_prob ?? 0) > 0.3 && c.traffic_score > 0.3,
  );

  /* Unprotected critical habitat */
  const unprotectedCritical = cells.filter(
    (c) =>
      (c.any_whale_prob ?? 0) > 0.3 && (c.protection_gap ?? 0) >= 0.7,
  );

  /* Species-specific stats */
  function buildSpecies(
    name: string,
    icon: ReactNode,
    color: string,
    border: string,
    key: keyof MacroCell,
    threatLevel: string,
    threatColor: string,
    insight: string,
  ): SpeciesData {
    const vals = cells
      .map((c) => c[key] as number | null)
      .filter((v): v is number => v != null && v > 0);
    const highP = vals.filter((v) => v > 0.3).length;
    const avg = vals.length > 0 ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
    return {
      name,
      icon,
      color,
      border,
      highProbCells: highP,
      avgProb: avg,
      strikeCells: strikeCells.length,
      threatLevel,
      threatColor,
      insight,
    };
  }

  const speciesList: SpeciesData[] = [
    buildSpecies(
      "North Atlantic Right Whale",
      <IconWhale className="h-4 w-4" />,
      "text-red-400",
      "border-red-800/30",
      "sdm_right_whale",
      "CRITICALLY ENDANGERED",
      "bg-red-500/20 text-red-400",
      "Fewer than 350 individuals remain. Calving habitat (SE US, winter) and feeding grounds (Gulf of Maine, summer) are critical. Any additional mortality threatens population recovery.",
    ),
    buildSpecies(
      "Humpback Whale",
      <IconWhale className="h-4 w-4" />,
      "text-blue-400",
      "border-blue-800/30",
      "isdm_humpback_whale",
      "LEAST CONCERN",
      "bg-blue-500/20 text-blue-400",
      "Recovering population but still MMPA-protected. Stellwagen Bank, Hawaiian waters, and SE Alaska are key aggregation areas. Entanglement and ship strike remain primary threats.",
    ),
    buildSpecies(
      "Fin Whale",
      <IconWhale className="h-4 w-4" />,
      "text-emerald-400",
      "border-emerald-800/30",
      "isdm_fin_whale",
      "VULNERABLE",
      "bg-yellow-500/20 text-yellow-400",
      "Second-largest animal on Earth. Fast-swimming and difficult to spot. High-speed vessel corridors overlap with feeding habitat along continental shelf edges.",
    ),
    buildSpecies(
      "Blue Whale",
      <span className="inline-block w-3 h-3 rounded-full" style={{backgroundColor: '#3b82f6'}}></span>,
      "text-indigo-400",
      "border-indigo-800/30",
      "isdm_blue_whale",
      "ENDANGERED",
      "bg-orange-500/20 text-orange-400",
      "Largest animal ever. West Coast shipping lanes (Santa Barbara Channel) overlap critical habitat. Seasonal krill aggregations drive predictable distribution patterns.",
    ),
    buildSpecies(
      "Sperm Whale",
      <IconDolphin className="h-4 w-4" />,
      "text-amber-400",
      "border-amber-800/30",
      "isdm_sperm_whale",
      "VULNERABLE",
      "bg-yellow-500/20 text-yellow-400",
      "Deep divers, primarily at risk during surface resting and breathing. Gulf of Mexico, Atlantic canyons are key habitat. Ship strikes mainly during slow-speed transits.",
    ),
  ];

  return (
    <main className="min-h-screen bg-abyss-950 px-4 pb-20 pt-24">
      <div className="mx-auto max-w-6xl">
        {/* Breadcrumb */}
        <div className="mb-6 flex items-center gap-2 text-xs text-slate-500">
          <Link href="/insights" className="hover:text-ocean-400">
            Insights
          </Link>
          <span>/</span>
          <span className="text-emerald-400">Conservation Groups</span>
        </div>

        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-600 to-green-500 shadow-lg">
              <IconWhale className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="font-display text-3xl font-extrabold tracking-tight text-white">
                Conservation Insights
              </h1>
              <p className="mt-1 max-w-xl text-sm text-slate-400">
                Species vulnerability assessments, critical habitat identification,
                threat hotspot mapping, and community sighting intelligence.
              </p>
            </div>
          </div>
          <Link
            href={mapLink({ lat: 37.5, lon: -76, layer: "whale_predictions", season, overlays: ["criticalHabitat", "bias", "mpas"] })}
            className="flex items-center gap-1.5 rounded-lg border border-ocean-800 bg-abyss-900 px-4 py-2 text-xs font-medium text-slate-300 transition-all hover:border-ocean-600 hover:text-white"
          >
            <IconMap className="h-3.5 w-3.5" />
            Open Habitat Map
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
                  ? "bg-emerald-600/20 text-emerald-400 shadow-sm"
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
              Loading conservation data…
            </div>
          </div>
        ) : (
          <>
            {/* Summary stats */}
            <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Critical Habitat Cells"
                value={criticalHabitat.length.toLocaleString()}
                sub="> 50% whale probability + habitat"
                accent="text-emerald-400"
                href={mapLink({ ...centroid(criticalHabitat), zoom: 7, layer: "whale_predictions", season, overlays: ["criticalHabitat", "bias"] })}
              />
              <StatCard
                label="Whale–Ship Overlap"
                value={threatOverlap.length.toLocaleString()}
                sub="High whale + high traffic zones"
                accent="text-red-400"
                href={mapLink({ ...centroid(threatOverlap), zoom: 7, layer: "risk", season, overlays: ["shippingLanes", "slowZones"] })}
              />
              <StatCard
                label="Unprotected Critical Areas"
                value={unprotectedCritical.length.toLocaleString()}
                sub="Whales present, no protection"
                accent="text-amber-400"
                href={mapLink({ ...centroid(unprotectedCritical), zoom: 7, layer: "risk", season, overlays: ["mpas", "criticalHabitat"] })}
              />
              <StatCard
                label="Baleen Sighting Cells"
                value={baleenCells.length.toLocaleString()}
                sub={`of ${sightingCells.length.toLocaleString()} whale cells`}
                accent="text-cyan-400"
                href={mapLink({ ...centroid(baleenCells), zoom: 6, layer: "cetacean_density", season, overlays: ["communitySightings", "bias"] })}
              />
            </div>

            {/* Species vulnerability cards */}
            <div className="mb-8">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                Species Vulnerability Assessment — {season}
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {speciesList.map((sp) => (
                  <SpeciesCard key={sp.name} sp={sp} />
                ))}
              </div>
            </div>

            {/* Conservation priorities */}
            <div className="mb-8 rounded-2xl border border-emerald-800/30 bg-emerald-950/20 p-6">
              <h2 className="mb-4 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-widest text-emerald-400">
                <IconShield className="h-5 w-5" /> Conservation Action Priorities — {season}
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <span className="inline-block w-3 h-3 shrink-0 rounded-full" style={{backgroundColor: '#ef4444'}}></span> Critical: Whale–Ship Overlap
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • <strong className="text-red-400">{threatOverlap.length.toLocaleString()}</strong>{" "}
                      cells where whales and vessels co-occur at dangerous levels
                    </li>
                    <li>
                      • These are the highest-priority areas for speed restrictions,
                      routing measures, or dynamic management areas
                    </li>
                    <li>
                      • Even a 5-knot speed reduction cuts lethality probability by ~60%
                    </li>
                    <li>
                      • Advocate for mandatory (not voluntary) compliance in these zones
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <span className="inline-block w-3 h-3 shrink-0 rounded-full" style={{backgroundColor: '#eab308'}}></span> Urgent: Protection Gaps
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • <strong className="text-amber-400">{unprotectedCritical.length.toLocaleString()}</strong>{" "}
                      cells with significant whale presence lack any MPA or speed zone
                    </li>
                    <li>
                      • These represent the biggest gap between known ecological value
                      and regulatory protection
                    </li>
                    <li>
                      • Target these areas for MPA expansion proposals, especially
                      where ESA-listed species overlap
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <IconSpeaker className="h-4 w-4" /> Community Science
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Encourage sighting reports via our{" "}
                      <Link href="/report" className="text-emerald-400 hover:underline">
                        Report Interaction
                      </Link>{" "}
                      tool — data improves model accuracy
                    </li>
                    <li>
                      • The{" "}
                      <Link href="/community" className="text-emerald-400 hover:underline">
                        Community feed
                      </Link>{" "}
                      shows verified sightings from citizen scientists
                    </li>
                    <li>
                      • Photo and audio classification provides species ID even for
                      non-expert observers
                    </li>
                    <li>
                      • Verified community sightings feed back into seasonal density models
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 flex items-center gap-1 text-xs font-bold text-white">
                    <IconChart className="h-4 w-4" /> Monitoring Gaps
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Ship strike records are severely under-reported — only 261
                      documented events with 67 geocoded
                    </li>
                    <li>
                      • OBIS sighting coverage is biased toward survey transects;
                      large ocean areas have zero observations
                    </li>
                    <li>
                      • Passive acoustic monitoring could fill gaps where visual
                      surveys are impractical
                    </li>
                    <li>
                      • Model predictions identify potential habitat even where no
                      sightings exist — useful for survey planning
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            {/* ── Projected Habitat Changes ──────────────── */}
            <div className="mb-8 rounded-2xl border border-cyan-800/30 bg-cyan-950/15 p-6">
              <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-widest text-cyan-400">
                <IconGlobe className="h-5 w-5" /> Projected Habitat Changes
              </h2>
              <p className="mb-4 text-xs text-slate-500">
                CMIP6 climate models project how whale habitat suitability will shift
                as ocean temperatures rise. Warming waters may push species poleward,
                creating new threat overlaps in areas that are currently low-risk.
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
                    const projCritHabitat = projCells.filter(
                      (c) => (c.any_whale_prob ?? 0) > 0.5 && (c.habitat_score ?? 0) > 0.3,
                    );
                    const projOverlap = projCells.filter(
                      (c) => (c.any_whale_prob ?? 0) > 0.3 && c.traffic_score > 0.3,
                    );
                    const projUnprotected = projCells.filter(
                      (c) => (c.any_whale_prob ?? 0) > 0.3 && (c.protection_gap ?? 0) >= 0.7,
                    );

                    const deltaHabitat = projCritHabitat.length - criticalHabitat.length;
                    const deltaOverlap = projOverlap.length - threatOverlap.length;
                    const deltaUnprot = projUnprotected.length - unprotectedCritical.length;

                    /* Per-species vulnerability shift */
                    const speciesShift = [
                      { name: "Right Whale", key: "sdm_right_whale" as keyof MacroCell, color: "text-red-400", esa: "CR" },
                      { name: "Humpback", key: "isdm_humpback_whale" as keyof MacroCell, color: "text-blue-400", esa: "LC" },
                      { name: "Fin Whale", key: "isdm_fin_whale" as keyof MacroCell, color: "text-emerald-400", esa: "VU" },
                      { name: "Blue Whale", key: "isdm_blue_whale" as keyof MacroCell, color: "text-indigo-400", esa: "EN" },
                      { name: "Sperm Whale", key: "isdm_sperm_whale" as keyof MacroCell, color: "text-amber-400", esa: "VU" },
                    ];

                    return (
                      <div className="space-y-5">
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                              Proj. Critical Habitat
                            </p>
                            <p className="mt-1 text-xl font-bold text-emerald-400">
                              {projCritHabitat.length.toLocaleString()}
                            </p>
                            <p className={`mt-0.5 text-xs font-semibold ${deltaHabitat > 0 ? "text-orange-400" : deltaHabitat < 0 ? "text-red-400" : "text-slate-500"}`}>
                              {deltaHabitat > 0 ? "↑ " : deltaHabitat < 0 ? "↓ " : ""}{Math.abs(deltaHabitat).toLocaleString()} vs current
                            </p>
                          </div>
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                              Proj. Whale–Ship Overlap
                            </p>
                            <p className="mt-1 text-xl font-bold text-red-400">
                              {projOverlap.length.toLocaleString()}
                            </p>
                            <p className={`mt-0.5 text-xs font-semibold ${deltaOverlap > 0 ? "text-red-400" : deltaOverlap < 0 ? "text-green-400" : "text-slate-500"}`}>
                              {deltaOverlap > 0 ? "↑ " : deltaOverlap < 0 ? "↓ " : ""}{Math.abs(deltaOverlap).toLocaleString()} vs current
                            </p>
                          </div>
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                              Proj. Unprotected Habitat
                            </p>
                            <p className="mt-1 text-xl font-bold text-amber-400">
                              {projUnprotected.length.toLocaleString()}
                            </p>
                            <p className={`mt-0.5 text-xs font-semibold ${deltaUnprot > 0 ? "text-red-400" : deltaUnprot < 0 ? "text-green-400" : "text-slate-500"}`}>
                              {deltaUnprot > 0 ? "↑ " : deltaUnprot < 0 ? "↓ " : ""}{Math.abs(deltaUnprot).toLocaleString()} vs current
                            </p>
                          </div>
                        </div>

                        {/* Per-species vulnerability */}
                        <div className="grid gap-3 sm:grid-cols-5">
                          {speciesShift.map((sp) => {
                            const curVals = cells.map((c) => c[sp.key] as number | null).filter((v): v is number => v != null && v > 0);
                            const projVals = projCells.map((c) => c[sp.key] as number | null).filter((v): v is number => v != null && v > 0);
                            const curHigh = curVals.filter((v) => v > 0.3).length;
                            const projHigh = projVals.filter((v) => v > 0.3).length;
                            const delta = projHigh - curHigh;
                            return (
                              <div key={sp.name} className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-3 text-center">
                                <p className={`text-xs font-bold ${sp.color}`}>{sp.name}</p>
                                <p className="text-[9px] text-slate-600">{sp.esa}</p>
                                <p className="mt-1 text-sm font-bold text-white">{projHigh.toLocaleString()}</p>
                                <p className="text-[10px] text-slate-500">high-P cells</p>
                                <p className={`text-[10px] font-semibold ${delta > 0 ? "text-orange-400" : delta < 0 ? "text-blue-400" : "text-slate-500"}`}>
                                  {delta > 0 ? "+" : ""}{delta.toLocaleString()}
                                </p>
                              </div>
                            );
                          })}
                        </div>

                        <Link
                          href={mapLink({ lat: 37.5, lon: -76, layer: "sdm_projections", season: season === "annual" ? "winter" : season, scenario: projScenario, decade: projDecade, overlays: ["criticalHabitat", "bias", "mpas"] })}
                          className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:underline"
                        >
                          View projected habitat on map →
                        </Link>
                      </div>
                    );
                  })()}
                  <p className="mt-4 text-[10px] text-slate-600">
                    Species shifts based on ISDM+SDM ensemble habitat models scored
                    on CMIP6-projected ocean covariates. Traffic held constant.
                    {season === "annual" && " Annual view shows winter projections."}
                  </p>
                </>
              )}
            </div>

            {/* Top threat hotspots table */}
            {threatOverlap.length > 0 && (
              <div className="rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-6">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                  Top Whale–Vessel Threat Hotspots — {season}
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-ocean-800/30 text-left text-slate-500">
                        <th className="pb-2 pr-4">#</th>
                        <th className="pb-2 pr-4">Location</th>
                        <th className="pb-2 pr-4">Whale P</th>
                        <th className="pb-2 pr-4">Traffic</th>
                        <th className="pb-2 pr-4">Speed Lethality</th>
                        <th className="pb-2 pr-4">Protection Gap</th>
                        <th className="pb-2 pr-4">Risk</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ocean-800/20">
                      {[...threatOverlap]
                        .sort((a, b) => {
                          const sa = (a.any_whale_prob ?? 0) * a.traffic_score;
                          const sb = (b.any_whale_prob ?? 0) * b.traffic_score;
                          return sb - sa;
                        })
                        .slice(0, 15)
                        .map((c, i) => (
                          <tr key={c.h3_cell} className="text-slate-400">
                            <td className="py-2.5 pr-4 text-slate-600">
                              {i + 1}
                            </td>
                            <td className="py-2.5 pr-4 tabular-nums">
                              <Link
                                href={mapLink({ lat: c.cell_lat, lon: c.cell_lon, zoom: 8, layer: "whale_predictions", season, overlays: ["criticalHabitat", "slowZones", "shippingLanes"] })}
                                className="text-emerald-400 hover:text-emerald-300 hover:underline"
                                title="View habitat + threats on map"
                              >
                                <IconPin className="mr-0.5 inline h-3 w-3" /> {c.cell_lat.toFixed(2)}°, {c.cell_lon.toFixed(2)}°
                              </Link>
                            </td>
                            <td className="py-2.5 pr-4 tabular-nums text-cyan-400">
                              {pct(c.any_whale_prob)}
                            </td>
                            <td className="py-2.5 pr-4 tabular-nums">
                              {pct(c.traffic_score)}
                            </td>
                            <td className="py-2.5 pr-4 tabular-nums text-red-400">
                              {pct(c.avg_speed_lethality)}
                            </td>
                            <td className="py-2.5 pr-4 tabular-nums text-amber-400">
                              {pct(c.protection_gap)}
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
