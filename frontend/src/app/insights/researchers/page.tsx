"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { API_BASE, mapLink } from "@/lib/config";
import { IconMicroscope, IconMap, IconGlobe } from "@/components/icons/MarineIcons";

/* ── Types ──────────────────────────────────────────────── */

interface MacroCell {
  h3_cell: number;
  cell_lat: number;
  cell_lon: number;
  risk_score: number;
  ml_risk_score: number | null;
  traffic_score: number;
  cetacean_score: number | null;
  habitat_score: number | null;
  any_whale_prob: number | null;
  isdm_blue_whale: number | null;
  isdm_fin_whale: number | null;
  isdm_humpback_whale: number | null;
  isdm_sperm_whale: number | null;
  sdm_any_whale: number | null;
  sdm_blue_whale: number | null;
  sdm_fin_whale: number | null;
  sdm_humpback_whale: number | null;
  sdm_sperm_whale: number | null;
  sdm_right_whale: number | null;
  sdm_minke_whale: number | null;
  sst: number | null;
  pp_upper_200m: number | null;
  depth_m_mean: number | null;
  shelf_fraction: number | null;
  total_sightings: number | null;
  baleen_sightings: number | null;
  [key: string]: number | null;
}

type Season = "annual" | "winter" | "spring" | "summer" | "fall";
type Scenario = "ssp245" | "ssp585";
type Decade = "2030s" | "2040s" | "2060s" | "2080s";

const SEASONS: Season[] = ["annual", "winter", "spring", "summer", "fall"];
const SCENARIOS: { value: Scenario; label: string }[] = [
  { value: "ssp245", label: "SSP2-4.5" },
  { value: "ssp585", label: "SSP5-8.5" },
];
const DECADES: Decade[] = ["2030s", "2040s", "2060s", "2080s"];

const SPECIES = [
  { key: "any_whale_prob", isdm: "any_whale_prob", sdm: "sdm_any_whale", label: "Any Whale", color: "text-cyan-400" },
  { key: "humpback", isdm: "isdm_humpback_whale", sdm: "sdm_humpback_whale", label: "Humpback", color: "text-blue-400" },
  { key: "fin", isdm: "isdm_fin_whale", sdm: "sdm_fin_whale", label: "Fin Whale", color: "text-emerald-400" },
  { key: "blue", isdm: "isdm_blue_whale", sdm: "sdm_blue_whale", label: "Blue Whale", color: "text-indigo-400" },
  { key: "sperm", isdm: "isdm_sperm_whale", sdm: "sdm_sperm_whale", label: "Sperm Whale", color: "text-amber-400" },
  { key: "right", isdm: null, sdm: "sdm_right_whale", label: "Right Whale", color: "text-red-400" },
  { key: "minke", isdm: null, sdm: "sdm_minke_whale", label: "Minke Whale", color: "text-teal-400" },
] as const;

/* ── Helpers ────────────────────────────────────────────── */

function pct(v: number | null): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmt(v: number | null, dp: number = 1): string {
  if (v == null) return "—";
  return v.toFixed(dp);
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
  accent = "text-purple-400",
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

/* ── Page ───────────────────────────────────────────────── */

export default function ResearchersPage() {
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

  /* Species presence summary */
  function speciesStats(isdmKey: string | null, sdmKey: string) {
    const isdmVals = isdmKey
      ? cells
        .map((c) => c[isdmKey] as number | null)
        .filter((v): v is number => v != null && v > 0)
      : [];
    const sdmVals = cells
      .map((c) => c[sdmKey] as number | null)
      .filter((v): v is number => v != null && v > 0);
    const isdmMean =
      isdmVals.length > 0
        ? isdmVals.reduce((s, v) => s + v, 0) / isdmVals.length
        : null;
    const sdmMean =
      sdmVals.length > 0
        ? sdmVals.reduce((s, v) => s + v, 0) / sdmVals.length
        : null;
    const isdmHigh = isdmVals.filter((v) => v > 0.5).length;
    const sdmHigh = sdmVals.filter((v) => v > 0.5).length;
    return { isdmMean, sdmMean, isdmHigh, sdmHigh, isdmCount: isdmVals.length, sdmCount: sdmVals.length };
  }

  /* Environmental covariate summaries */
  const sstVals = cells.map((c) => c.sst).filter((v): v is number => v != null);
  const ppVals = cells.map((c) => c.pp_upper_200m).filter((v): v is number => v != null);
  const depthVals = cells.map((c) => c.depth_m_mean).filter((v): v is number => v != null);

  const sstMean = sstVals.length > 0 ? sstVals.reduce((s, v) => s + v, 0) / sstVals.length : null;
  const sstMin = sstVals.length > 0 ? Math.min(...sstVals) : null;
  const sstMax = sstVals.length > 0 ? Math.max(...sstVals) : null;
  const ppMean = ppVals.length > 0 ? ppVals.reduce((s, v) => s + v, 0) / ppVals.length : null;
  const depthMean = depthVals.length > 0 ? depthVals.reduce((s, v) => s + v, 0) / depthVals.length : null;
  const shelfCells = cells.filter((c) => (c.shelf_fraction ?? 0) > 0.5).length;

  /* ISDM vs SDM comparison (model agreement) */
  const bothModels = cells.filter(
    (c) => c.any_whale_prob != null && c.sdm_any_whale != null,
  );
  const agreementCount = bothModels.filter((c) => {
    const isdm = c.any_whale_prob! > 0.5;
    const sdm = (c.sdm_any_whale ?? 0) > 0.5;
    return isdm === sdm;
  }).length;
  const agreement =
    bothModels.length > 0 ? agreementCount / bothModels.length : null;

  /* Sightings coverage */
  const sightingCells = cells.filter((c) => (c.total_sightings ?? 0) > 0);
  const totalSightings = cells.reduce((s, c) => s + (c.total_sightings ?? 0), 0);

  return (
    <main className="min-h-screen bg-abyss-950 px-4 pb-20 pt-24">
      <div className="mx-auto max-w-6xl">
        {/* Breadcrumb */}
        <div className="mb-6 flex items-center gap-2 text-xs text-slate-500">
          <Link href="/insights" className="hover:text-ocean-400">
            Insights
          </Link>
          <span>/</span>
          <span className="text-purple-400">Marine Researchers</span>
        </div>

        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-600 to-violet-500 shadow-lg">
              <IconMicroscope className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="font-display text-3xl font-extrabold tracking-tight text-white">
                Marine Researcher Insights
              </h1>
              <p className="mt-1 max-w-xl text-sm text-slate-400">
                Species distribution model outputs, habitat covariate analysis,
                model comparison diagnostics, and observational data coverage.
              </p>
            </div>
          </div>
          <Link
            href={mapLink({ lat: 37.5, lon: -76, layer: "whale_predictions", season, overlays: ["criticalHabitat", "bias"] })}
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
                  ? "bg-purple-600/20 text-purple-400 shadow-sm"
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
              Loading research data…
            </div>
          </div>
        ) : (
          <>
            {/* Summary stats */}
            <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Grid Cells Analysed"
                value={total.toLocaleString()}
                sub="H3 resolution 4 (macro)"
              />
              <StatCard
                label="Sighting Coverage"
                value={sightingCells.length.toLocaleString()}
                sub={`${totalSightings.toLocaleString()} total sightings`}
                accent="text-cyan-400"
                href={mapLink({ ...centroid(sightingCells), zoom: 6, layer: "cetacean_density", season, overlays: ["communitySightings", "bias"] })}
              />
              <StatCard
                label="Mean SST"
                value={sstMean ? `${sstMean.toFixed(1)}°C` : "—"}
                sub={sstMin != null ? `${fmt(sstMin, 1)}°C – ${fmt(sstMax, 1)}°C` : ""}
                accent="text-orange-400"
                href={mapLink({ lat: 37.5, lon: -76, layer: "ocean", season })}
              />
              <StatCard
                label="ISDM/SDM Agreement"
                value={agreement != null ? pct(agreement) : "—"}
                sub={`${bothModels.length.toLocaleString()} cells with both`}
                accent="text-emerald-400"
                href={mapLink({ lat: 37.5, lon: -76, layer: "whale_predictions", season, overlays: ["criticalHabitat"] })}
              />
            </div>

            {/* Species distribution model comparison */}
            <div className="mb-8 rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-6">
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-widest text-slate-500">
                Species Habitat Model Comparison — {season}
              </h2>
              <p className="mb-5 text-xs text-slate-600">
                ISDM: trained on Nisi et al. (2024) risk grid with 7 environmental
                covariates. SDM (OBIS): trained on OBIS cetacean sighting presence/absence
                with spatial block cross-validation (H3 res-2, ~158 km blocks).
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-ocean-800/30 text-left text-slate-500">
                      <th className="pb-2 pr-4">Species</th>
                      <th className="pb-2 pr-4">ISDM Mean P</th>
                      <th className="pb-2 pr-4">SDM Mean P</th>
                      <th className="pb-2 pr-4">ISDM &gt;50%</th>
                      <th className="pb-2 pr-4">SDM &gt;50%</th>
                      <th className="pb-2 pr-4">ISDM Coverage</th>
                      <th className="pb-2 pr-4">SDM Coverage</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ocean-800/20">
                    {SPECIES.map((sp) => {
                      const stats = speciesStats(sp.isdm, sp.sdm);
                      return (
                        <tr key={sp.key} className="text-slate-400">
                          <td className={`py-2.5 pr-4 font-medium ${sp.color}`}>
                            {sp.label}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {pct(stats.isdmMean)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {pct(stats.sdmMean)}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {stats.isdmHigh.toLocaleString()}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {stats.sdmHigh.toLocaleString()}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {stats.isdmCount.toLocaleString()}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {stats.sdmCount.toLocaleString()}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Habitat covariates */}
            <div className="mb-8 rounded-2xl border border-ocean-800/30 bg-abyss-900/50 p-6">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-slate-500">
                Environmental Covariates — {season}
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-orange-400">
                    Sea Surface Temperature
                  </p>
                  <p className="mt-1 text-xl font-bold text-white">
                    {fmt(sstMean, 1)}°C
                  </p>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    Range: {fmt(sstMin, 1)}°C – {fmt(sstMax, 1)}°C
                  </p>
                  <p className="mt-2 text-[10px] text-slate-600">
                    Key predictor for baleen whale distribution. Right whales
                    prefer 5–15°C. Source: Copernicus Marine.
                  </p>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-400">
                    Primary Productivity
                  </p>
                  <p className="mt-1 text-xl font-bold text-white">
                    {fmt(ppMean, 0)} mg C/m²/d
                  </p>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    Upper 200m integrated
                  </p>
                  <p className="mt-2 text-[10px] text-slate-600">
                    Ranks 5th–6th in ISDM feature importance across species.
                    Drives prey aggregation. Source: Copernicus.
                  </p>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-blue-400">
                    Mean Depth
                  </p>
                  <p className="mt-1 text-xl font-bold text-white">
                    {fmt(depthMean, 0)} m
                  </p>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    {shelfCells.toLocaleString()} cells on continental shelf
                  </p>
                  <p className="mt-2 text-[10px] text-slate-600">
                    Shelf-edge is critical habitat for right whales and
                    humpbacks. Source: GEBCO 2023.
                  </p>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-purple-400">
                    Shelf Fraction
                  </p>
                  <p className="mt-1 text-xl font-bold text-white">
                    {(
                      (shelfCells / (total || 1)) *
                      100
                    ).toFixed(1)}
                    %
                  </p>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    Cells with &gt;50% shelf coverage
                  </p>
                  <p className="mt-2 text-[10px] text-slate-600">
                    Continental shelf (&lt;200m) hosts the densest whale
                    aggregations and highest vessel traffic overlap.
                  </p>
                </div>
              </div>
            </div>

            {/* ── CMIP6 Climate Projections ──────────────── */}
            <div className="mb-8 rounded-2xl border border-cyan-800/30 bg-cyan-950/15 p-6">
              <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-widest text-cyan-400">
                <IconGlobe className="h-5 w-5" /> CMIP6 Climate Projections
              </h2>
              <p className="mb-4 text-xs text-slate-500">
                ISDM+SDM ensemble species habitat models scored on projected ocean
                covariates from CMIP6 climate models. Compare current vs projected
                environmental conditions and species distributions.
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
                <Link
                  href={mapLink({ lat: 37.5, lon: -76, layer: "sdm_projections", season: season === "annual" ? "winter" : season, scenario: projScenario, decade: projDecade, overlays: ["criticalHabitat", "bias"] })}
                  className="ml-auto flex items-center gap-1 rounded-lg border border-ocean-800 bg-abyss-900 px-3 py-1.5 text-[11px] font-medium text-slate-300 transition-all hover:border-ocean-600 hover:text-white"
                >
                  View projected habitat map →
                </Link>
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
                    /* Projected covariates */
                    const pSst = projCells.map((c) => c.sst).filter((v): v is number => v != null);
                    const pPp = projCells.map((c) => c.pp_upper_200m).filter((v): v is number => v != null);
                    const pSstMean = pSst.length > 0 ? pSst.reduce((s, v) => s + v, 0) / pSst.length : null;
                    const pPpMean = pPp.length > 0 ? pPp.reduce((s, v) => s + v, 0) / pPp.length : null;
                    const sstDelta = sstMean != null && pSstMean != null ? pSstMean - sstMean : null;
                    const ppDelta = ppMean != null && pPpMean != null ? pPpMean - ppMean : null;

                    /* Projected species stats */
                    function projSpeciesStats(isdmKey: string | null, sdmKey: string) {
                      const sdmVals = projCells
                        .map((c) => c[sdmKey] as number | null)
                        .filter((v): v is number => v != null && v > 0);
                      const sdmMean = sdmVals.length > 0 ? sdmVals.reduce((s, v) => s + v, 0) / sdmVals.length : null;
                      const sdmHigh = sdmVals.filter((v) => v > 0.5).length;
                      return { sdmMean, sdmHigh, sdmCount: sdmVals.length };
                    }

                    return (
                      <div className="space-y-5">
                        {/* Covariate deltas */}
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-orange-400">
                              Projected SST
                            </p>
                            <p className="mt-1 text-xl font-bold text-white">
                              {pSstMean != null ? `${pSstMean.toFixed(1)}°C` : "—"}
                            </p>
                            <p className={`mt-0.5 text-xs font-semibold ${(sstDelta ?? 0) > 0 ? "text-red-400" : "text-blue-400"}`}>
                              {sstDelta != null ? `${sstDelta > 0 ? "+" : ""}${sstDelta.toFixed(1)}°C vs current` : ""}
                            </p>
                          </div>
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-400">
                              Projected PP
                            </p>
                            <p className="mt-1 text-xl font-bold text-white">
                              {pPpMean != null ? `${pPpMean.toFixed(0)}` : "—"}
                              <span className="ml-1 text-xs font-normal text-slate-500">mg C/m²/d</span>
                            </p>
                            <p className={`mt-0.5 text-xs font-semibold ${(ppDelta ?? 0) < 0 ? "text-red-400" : "text-green-400"}`}>
                              {ppDelta != null ? `${ppDelta > 0 ? "+" : ""}${ppDelta.toFixed(0)} vs current` : ""}
                            </p>
                          </div>
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-cyan-400">
                              Proj. Any-Whale P &gt;50%
                            </p>
                            <p className="mt-1 text-xl font-bold text-white">
                              {projCells.filter((c) => (c.any_whale_prob ?? 0) > 0.5).length.toLocaleString()}
                            </p>
                            <p className="mt-0.5 text-xs text-slate-500">
                              cells with high habitat probability
                            </p>
                          </div>
                          <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-purple-400">
                              Projected Grid Cells
                            </p>
                            <p className="mt-1 text-xl font-bold text-white">
                              {projCells.length.toLocaleString()}
                            </p>
                            <p className="mt-0.5 text-xs text-slate-500">
                              {projScenario.toUpperCase()} · {projDecade}
                            </p>
                          </div>
                        </div>

                        {/* Projected species table */}
                        <div className="overflow-x-auto">
                          <h3 className="mb-3 text-xs font-semibold text-slate-400">
                            Projected Species Distribution Shift
                          </h3>
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b border-ocean-800/30 text-left text-slate-500">
                                <th className="pb-2 pr-4">Species</th>
                                <th className="pb-2 pr-4">Current Mean P</th>
                                <th className="pb-2 pr-4">Projected Mean P</th>
                                <th className="pb-2 pr-4">Δ</th>
                                <th className="pb-2 pr-4">Current &gt;50%</th>
                                <th className="pb-2 pr-4">Projected &gt;50%</th>
                                <th className="pb-2 pr-4">Δ Cells</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-ocean-800/20">
                              {SPECIES.map((sp) => {
                                const cur = speciesStats(sp.isdm, sp.sdm);
                                const proj = projSpeciesStats(sp.isdm, sp.sdm);
                                const meanDelta = cur.sdmMean != null && proj.sdmMean != null ? proj.sdmMean - cur.sdmMean : null;
                                const cellDelta = proj.sdmHigh - cur.sdmHigh;
                                return (
                                  <tr key={sp.key} className="text-slate-400">
                                    <td className={`py-2.5 pr-4 font-medium ${sp.color}`}>
                                      {sp.label}
                                    </td>
                                    <td className="py-2.5 pr-4 tabular-nums">
                                      {pct(cur.sdmMean)}
                                    </td>
                                    <td className="py-2.5 pr-4 tabular-nums">
                                      {pct(proj.sdmMean)}
                                    </td>
                                    <td className={`py-2.5 pr-4 tabular-nums font-semibold ${(meanDelta ?? 0) > 0 ? "text-orange-400" : (meanDelta ?? 0) < 0 ? "text-blue-400" : "text-slate-600"}`}>
                                      {meanDelta != null ? `${meanDelta > 0 ? "+" : ""}${(meanDelta * 100).toFixed(1)}pp` : "—"}
                                    </td>
                                    <td className="py-2.5 pr-4 tabular-nums">
                                      {cur.sdmHigh.toLocaleString()}
                                    </td>
                                    <td className="py-2.5 pr-4 tabular-nums">
                                      {proj.sdmHigh.toLocaleString()}
                                    </td>
                                    <td className={`py-2.5 pr-4 tabular-nums font-semibold ${cellDelta > 0 ? "text-orange-400" : cellDelta < 0 ? "text-blue-400" : "text-slate-600"}`}>
                                      {cellDelta > 0 ? "+" : ""}{cellDelta.toLocaleString()}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })()}
                  <p className="mt-4 text-[10px] text-slate-600">
                    CMIP6 projections: SSP2-4.5 (moderate mitigation) and SSP5-8.5
                    (high emissions). Ocean covariates (SST, MLD, SLA, PP) are
                    projected; bathymetry and traffic held constant.
                    {season === "annual" && " Annual view defaults to winter projections."}
                    {" "}Δ values show change from current baseline; pp = percentage points.
                  </p>
                </>
              )}
            </div>

            {/* Methodology notes */}
            <div className="mb-8 rounded-2xl border border-purple-800/30 bg-purple-950/20 p-6">
              <h2 className="mb-4 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-widest text-purple-400">
                <IconMicroscope className="h-4 w-4" /> Methodology & Data Access
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 text-xs font-bold text-white">
                    Model Architecture
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • <strong className="text-slate-300">12 XGBoost classifiers</strong>{" "}
                      trained with spatial block CV (H3 res-2, 5 folds)
                    </li>
                    <li>
                      • Static SDM: 47 features, 1.8M rows
                    </li>
                    <li>
                      • Seasonal SDM: 7.3M rows (×4 seasons), one-hot season encoding
                    </li>
                    <li>
                      • ISDM: 7 environmental covariates, trained on Nisi et al.
                      global risk grid
                    </li>
                    <li>
                      • All models logged to MLflow with hyperparameter tracking
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 text-xs font-bold text-white">
                    Detection Bias Mitigation
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • Whale SDMs <strong className="text-slate-300">exclude traffic features</strong>{" "}
                      — survey effort correlates with shipping lanes
                    </li>
                    <li>
                      • Whale SDMs exclude whale proximity (target leakage)
                    </li>
                    <li>
                      • Seasonal SDMs exclude Nisi per-species risk (reserved
                      for validation)
                    </li>
                    <li>
                      • SHAP analysis confirms environmental features dominate
                      prediction (no traffic signal)
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 text-xs font-bold text-white">
                    Available APIs
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      •{" "}
                      <Link href={mapLink({ lat: 37.5, lon: -76, zoom: 5.5, layer: "whale_predictions", season, overlays: ["criticalHabitat", "bias"] })} className="text-purple-300 hover:underline">
                        Whale Habitat (Expert) layer
                      </Link>{" "}
                      — ISDM species probabilities with BIA + critical habitat overlays
                    </li>
                    <li>
                      •{" "}
                      <Link href={mapLink({ lat: 37.5, lon: -76, zoom: 5.5, layer: "sdm", season, overlays: ["communitySightings"] })} className="text-purple-300 hover:underline">
                        Whale Habitat (Observed) layer
                      </Link>{" "}
                      — SDM (OBIS) predictions with community sightings overlay
                    </li>
                    <li>
                      •{" "}
                      <Link href={mapLink({ lat: 37.5, lon: -76, zoom: 5.5, layer: "ocean", season })} className="text-purple-300 hover:underline">
                        Ocean Covariates layer
                      </Link>{" "}
                      — SST, MLD, SLA, PP covariates
                    </li>
                    <li>
                      •{" "}
                      <Link href={mapLink({ lat: 37.5, lon: -76, zoom: 5.5, layer: "risk_ml", season, overlays: ["activeSMAs", "mpas"] })} className="text-purple-300 hover:underline">
                        Modelled Risk layer
                      </Link>{" "}
                      — Survey-Based vs Modelled risk with regulatory zone overlays
                    </li>
                  </ul>
                </div>
                <div className="rounded-xl border border-ocean-800/20 bg-abyss-900/60 p-4">
                  <h3 className="mb-2 text-xs font-bold text-white">
                    Known Caveats
                  </h3>
                  <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
                    <li>
                      • ~49% of H3 cells lack Copernicus ocean covariates
                      (deep ocean/edge) — filled with median values
                    </li>
                    <li>
                      • Strike history is sparse: 67 geocoded out of 261 total
                      documented events
                    </li>
                    <li>
                      • OBIS sightings have significant spatial bias toward
                      research survey transects
                    </li>
                    <li>
                      • Risk scores are relative (percentile-ranked), not
                      calibrated probabilities
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
