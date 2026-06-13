/* ── Shared climate-projection data hook (insights pages) ──────
 *
 * Every stakeholder insights page (researchers, ports, policy,
 * conservation, captains) renders a CMIP6 projection panel that
 * compares a future decade against the current baseline.
 *
 * Two subtleties this hook centralises so all five pages stay correct:
 *
 *  1. Season consistency.  Projection rows have no "annual" season,
 *     so an annual view must fall back to a real season ("winter").
 *     The *baseline* used for deltas must be fetched at that SAME
 *     season — otherwise an annual-current value is compared against
 *     a winter-projected value (apples to oranges).  This hook always
 *     returns `baseCells` fetched at `projSeason`, never the displayed
 *     (possibly annual) season.
 *
 *  2. Baseline provenance.  The "current" baseline is the 2019–2024
 *     Copernicus climatology; CMIP6 delta-method corrections are
 *     applied on top.  Exposed via BASELINE_NOTE for consistent
 *     labelling across pages.
 */

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/config";
import type { MacroCell } from "@/hooks/useMacroData";

export type ProjScenario = "ssp245" | "ssp585";
export type ProjDecade = "2030s" | "2040s" | "2060s" | "2080s";

export const PROJ_SCENARIOS: { value: ProjScenario; label: string }[] = [
  { value: "ssp245", label: "SSP2-4.5" },
  { value: "ssp585", label: "SSP5-8.5" },
];

export const PROJ_SCENARIOS_LONG: { value: ProjScenario; label: string }[] = [
  { value: "ssp245", label: "SSP2-4.5 (moderate)" },
  { value: "ssp585", label: "SSP5-8.5 (high emissions)" },
];

export const PROJ_DECADES: ProjDecade[] = [
  "2030s",
  "2040s",
  "2060s",
  "2080s",
];

/** Shared baseline-provenance note for projection panels. */
export const BASELINE_NOTE =
  "Baseline = 2019–2024 Copernicus climatology; CMIP6 delta-method " +
  "corrections applied to projected ocean covariates (SST, MLD, SLA, PP). " +
  "Bathymetry and vessel traffic are held constant.";

async function fetchMacro(
  season: string,
  scenario?: ProjScenario,
  decade?: ProjDecade,
  signal?: AbortSignal,
): Promise<MacroCell[]> {
  let url = `${API_BASE}/api/v1/macro/overview?season=${season}`;
  if (scenario && decade) {
    url += `&scenario=${scenario}&decade=${decade}`;
  }
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`macro overview ${res.status}`);
  const d = await res.json();
  return (d.data ?? []) as MacroCell[];
}

export interface ProjectionData {
  /** Projected cells for (projSeason, scenario, decade). */
  projCells: MacroCell[];
  /** Current baseline cells at the SAME season as the projection. */
  baseCells: MacroCell[];
  /** The real season the projection resolves to (annual → winter). */
  projSeason: string;
  /** True while either fetch is in flight. */
  loading: boolean;
  /** Non-null if the last fetch failed. */
  error: string | null;
}

/**
 * Fetch a CMIP6 projection slice plus a season-consistent current
 * baseline for computing deltas.
 *
 * @param season   The displayed season ("annual" | "winter" | …).
 * @param scenario CMIP6 scenario.
 * @param decade   Projection decade.
 */
export function useProjectionData(
  season: string,
  scenario: ProjScenario,
  decade: ProjDecade,
): ProjectionData {
  const projSeason = season === "annual" ? "winter" : season;

  const [projCells, setProjCells] = useState<MacroCell[]>([]);
  const [baseCells, setBaseCells] = useState<MacroCell[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const [proj, base] = await Promise.all([
          fetchMacro(projSeason, scenario, decade, signal),
          fetchMacro(projSeason, undefined, undefined, signal),
        ]);
        if (signal.aborted) return;
        setProjCells(proj);
        setBaseCells(base);
      } catch (e) {
        if (signal.aborted) return;
        setError(e instanceof Error ? e.message : "Failed to load projections");
        setProjCells([]);
        setBaseCells([]);
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    },
    [projSeason, scenario, decade],
  );

  useEffect(() => {
    const ac = new AbortController();
    load(ac.signal);
    return () => ac.abort();
  }, [load]);

  return { projCells, baseCells, projSeason, loading, error };
}

/* ── Small numeric helpers shared by projection panels ─────── */

/** Mean of a nullable numeric field over a cell array (nulls ignored). */
export function meanField(
  cells: MacroCell[],
  field: keyof MacroCell,
): number | null {
  const vals = cells
    .map((c) => c[field] as number | null)
    .filter((v): v is number => v != null);
  if (vals.length === 0) return null;
  return vals.reduce((s, v) => s + v, 0) / vals.length;
}

/** Mean of a field over cells where the value is > 0 (presence cells). */
export function meanPositiveField(
  cells: MacroCell[],
  field: keyof MacroCell,
): number | null {
  const vals = cells
    .map((c) => c[field] as number | null)
    .filter((v): v is number => v != null && v > 0);
  if (vals.length === 0) return null;
  return vals.reduce((s, v) => s + v, 0) / vals.length;
}

/** Count cells where a field exceeds a threshold (default 0.5). */
export function countAbove(
  cells: MacroCell[],
  field: keyof MacroCell,
  threshold = 0.5,
): number {
  return cells.filter((c) => ((c[field] as number | null) ?? 0) > threshold)
    .length;
}
