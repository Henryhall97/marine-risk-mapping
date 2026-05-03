/* ── Macro overview data hook ─────────────────────────────── */

import { useState, useEffect, useRef } from "react";
import { API_BASE } from "@/lib/config";
import type { Season, ClimateScenario, SdmTimePeriod } from "@/lib/types";

/** Row returned by GET /api/v1/macro/overview. */
export interface MacroCell {
  h3_cell: number;
  cell_lat: number;
  cell_lon: number;
  season: string;
  scenario: string | null;
  decade: string | null;
  risk_score: number | null;
  ml_risk_score: number | null;
  traffic_score: number | null;
  avg_monthly_vessels: number | null;
  avg_speed_lethality: number | null;
  avg_high_speed_fraction: number | null;
  avg_draft_risk_fraction: number | null;
  night_traffic_ratio: number | null;
  avg_commercial_vessels: number | null;
  cetacean_score: number | null;
  strike_score: number | null;
  habitat_score: number | null;
  proximity_score: number | null;
  protection_gap: number | null;
  reference_risk: number | null;
  total_sightings: number | null;
  baleen_sightings: number | null;
  total_strikes: number | null;
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
  sst_sd: number | null;
  mld: number | null;
  sla: number | null;
  pp_upper_200m: number | null;
  depth_m_mean: number | null;
  shelf_fraction: number | null;
  child_cell_count: number | null;
}

/** Cache keyed by season string. */
const cache = new Map<string, MacroCell[]>();

/**
 * Fetch the pre-aggregated macro overview grid (H3 res-4, ~5 500 cells).
 * Returns all coarse cells for the requested season in a single
 * response — no bbox or pagination needed.
 *
 * Pass `undefined` for season to disable fetching (e.g. when in detail mode).
 * For climate projections, pass scenario + timePeriod (non-"current").
 */
export function useMacroData(
  season: Season | undefined,
  scenario?: ClimateScenario,
  timePeriod?: SdmTimePeriod,
) {
  const [data, setData] = useState<MacroCell[]>([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Derive projection params — only active for future decades
  const isProjection = timePeriod !== undefined && timePeriod !== "current";
  const apiScenario = isProjection ? scenario : undefined;
  const apiDecade = isProjection ? timePeriod : undefined;

  useEffect(() => {
    // If season is undefined, we're not in overview mode — skip
    if (season === undefined) {
      setData([]);
      return;
    }

    // Map Season type to API param.
    // Projected data has no "annual" season — fall back to "winter".
    const rawSeason =
      season === null || season === "all" ? "annual" : season;
    const apiSeason =
      isProjection && rawSeason === "annual" ? "winter" : rawSeason;

    // Build cache key including projection dimensions
    const cacheKey = apiScenario && apiDecade
      ? `${apiSeason}:${apiScenario}:${apiDecade}`
      : apiSeason;

    // Serve from cache
    if (cache.has(cacheKey)) {
      setData(cache.get(cacheKey)!);
      return;
    }

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    // Build URL with optional projection params
    let url = `${API_BASE}/api/v1/macro/overview?season=${apiSeason}`;
    if (apiScenario && apiDecade) {
      url += `&scenario=${apiScenario}&decade=${apiDecade}`;
    }

    setLoading(true);
    fetch(url, { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((body: { data: MacroCell[] }) => {
        cache.set(cacheKey, body.data);
        setData(body.data);
      })
      .catch(() => {
        /* aborted or failed */
      })
      .finally(() => setLoading(false));

    return () => ac.abort();
  }, [season, apiScenario, apiDecade]);

  return { data, loading, total: data.length };
}

/** Contour GeoJSON (static, fetched once and cached). */
let contourCache: GeoJSON.FeatureCollection | null = null;

export function useContourData() {
  const [data, setData] = useState<GeoJSON.FeatureCollection | null>(
    null,
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (contourCache) {
      setData(contourCache);
      return;
    }

    setLoading(true);
    fetch(`${API_BASE}/api/v1/macro/contours/bathymetry`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((geojson: GeoJSON.FeatureCollection) => {
        contourCache = geojson;
        setData(geojson);
      })
      .catch(() => {
        /* not available */
      })
      .finally(() => setLoading(false));
  }, []);

  return { data, loading };
}
