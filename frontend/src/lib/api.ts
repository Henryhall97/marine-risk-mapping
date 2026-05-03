import { API_BASE, MAX_BBOX_AREA_DEG2, PAGE_LIMIT } from "./config";
import type { BBox, PaginatedResponse, SpeedZone, MPA, BIA, CriticalHabitatZone, ShippingLane, SlowZone, MapSighting } from "./types";

/* ── Helpers ─────────────────────────────────────────────── */

/** Calculate bbox area in degrees². */
export function bboxArea(bbox: BBox): number {
  return (bbox.lat_max - bbox.lat_min) * (bbox.lon_max - bbox.lon_min);
}

/** Build query string, optionally including bbox params. */
function buildParams(
  bbox: BBox | null,
  extra?: Record<string, string | number | boolean | undefined>,
): URLSearchParams {
  const p = new URLSearchParams({ limit: String(PAGE_LIMIT) });
  if (bbox) {
    p.set("lat_min", String(bbox.lat_min));
    p.set("lat_max", String(bbox.lat_max));
    p.set("lon_min", String(bbox.lon_min));
    p.set("lon_max", String(bbox.lon_max));
  }
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (v !== undefined && v !== null) p.set(k, String(v));
    }
  }
  return p;
}

/** Generic typed GET. */
async function get<T>(
  path: string,
  params?: URLSearchParams,
  signal?: AbortSignal,
): Promise<T> {
  const url = params
    ? `${API_BASE}${path}?${params}`
    : `${API_BASE}${path}`;
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

/* ── Public API functions ────────────────────────────────── */

/** Layers where bbox is optional (backend defaults to full US). */
const OPTIONAL_BBOX_LAYERS = new Set([
  "/api/v1/layers/bathymetry",
  "/api/v1/layers/ocean",
]);

/**
 * Fetch any hex-cell layer.
 *
 * If the viewport bbox exceeds the API area limit:
 * - Optional-bbox layers: omit bbox → backend returns full US.
 * - Required-bbox layers: reject early (zoom in).
 */
export function fetchHexLayer(
  endpoint: string,
  bbox: BBox,
  extra?: Record<string, string | number | boolean | undefined>,
  signal?: AbortSignal,
): Promise<PaginatedResponse<Record<string, unknown>>> {
  const tooWide = bboxArea(bbox) > MAX_BBOX_AREA_DEG2;
  const optionalBbox = OPTIONAL_BBOX_LAYERS.has(endpoint);

  if (tooWide && !optionalBbox) {
    // Can't query — return empty so caller shows "zoom in"
    return Promise.resolve({ total: 0, offset: 0, limit: 0, data: [] });
  }

  const effectiveBbox = tooWide ? null : bbox;
  return get<PaginatedResponse<Record<string, unknown>>>(
    endpoint,
    buildParams(effectiveBbox, extra),
    signal,
  );
}

/** Fetch full detail for a single risk cell. */
export function fetchCellDetail(
  h3BigInt: string,
  signal?: AbortSignal,
) {
  return get<Record<string, unknown>>(
    `/api/v1/risk/zones/${h3BigInt}`,
    undefined,
    signal,
  );
}

/** Species + habitat context for any H3 cell. */
export interface CellContext {
  h3_cell: number;
  isdm_blue_whale: number | null;
  isdm_fin_whale: number | null;
  isdm_humpback_whale: number | null;
  isdm_sperm_whale: number | null;
  any_whale_prob: number | null;
  max_whale_prob: number | null;
  mean_whale_prob: number | null;
  species_observed: string | null;
  bia_zones: { species: string; type: string }[];
  critical_habitat: { species: string; status: string }[];
}

/** Fetch species + habitat context for a single cell. */
export function fetchCellContext(
  h3BigInt: string,
  season?: string | null,
  signal?: AbortSignal,
) {
  const p = season
    ? new URLSearchParams({ season })
    : undefined;
  return get<CellContext>(
    `/api/v1/layers/context/${h3BigInt}`,
    p,
    signal,
  );
}

/** Result from the nearest-risk-cell endpoint. */
export interface NearestRiskResult {
  is_exact_match: boolean;
  query_lat: number;
  query_lon: number;
  distance_km: number;
  cell: Record<string, unknown>;
}

/** Find the nearest risk cell to a lat/lon coordinate. */
export function fetchNearestRisk(
  lat: number,
  lon: number,
  signal?: AbortSignal,
): Promise<NearestRiskResult> {
  const p = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
  });
  return get<NearestRiskResult>(
    "/api/v1/risk/zones/nearest",
    p,
    signal,
  );
}

/** Fetch speed zones (current SMAs or proposed). */
export async function fetchSpeedZones(
  type: "current" | "proposed",
  activeOn?: string,
  signal?: AbortSignal,
): Promise<{ total: number; data: SpeedZone[] }> {
  const p = activeOn
    ? new URLSearchParams({ active_on: activeOn })
    : undefined;
  const res = await get<{ total: number; data: Omit<SpeedZone, "source">[] }>(
    `/api/v1/zones/speed-zones/${type}`,
    p,
    signal,
  );
  // Tag each zone with its source so the map can color them differently
  return {
    ...res,
    data: res.data.map((z) => ({ ...z, source: type })),
  };
}

/** Fetch Marine Protected Areas within a bbox. */
export function fetchMPAs(bbox: BBox, signal?: AbortSignal) {
  return get<PaginatedResponse<MPA>>(
    "/api/v1/zones/mpas",
    buildParams(bbox),
    signal,
  );
}

/** Fetch Biologically Important Areas within a bbox. */
export function fetchBIAs(
  bbox: BBox,
  signal?: AbortSignal,
) {
  return get<PaginatedResponse<BIA>>(
    "/api/v1/zones/bia",
    buildParams(bbox),
    signal,
  );
}

/** Fetch all Critical Habitat polygons. */
export function fetchCriticalHabitat(signal?: AbortSignal) {
  return get<{ total: number; data: CriticalHabitatZone[] }>(
    "/api/v1/zones/critical-habitat",
    undefined,
    signal,
  );
}

/** Fetch shipping lanes within a bbox. */
export function fetchShippingLanes(
  bbox: BBox,
  signal?: AbortSignal,
) {
  return get<PaginatedResponse<ShippingLane>>(
    "/api/v1/zones/shipping-lanes",
    buildParams(bbox),
    signal,
  );
}

/** Fetch active Right Whale Slow Zones. */
export function fetchSlowZones(signal?: AbortSignal) {
  return get<{ total: number; data: SlowZone[] }>(
    "/api/v1/zones/slow-zones",
    undefined,
    signal,
  );
}

/** Fetch community sightings within a bbox for map display. */
export function fetchMapSightings(
  bbox: BBox,
  options?: {
    species?: string;
    status?: string;
    limit?: number;
  },
  signal?: AbortSignal,
) {
  const extra: Record<string, string | number | undefined> = {};
  if (options?.species) extra.species = options.species;
  if (options?.status) extra.status = options.status;
  if (options?.limit) extra.limit = options.limit;
  return get<{ total: number; data: MapSighting[] }>(
    "/api/v1/submissions/map-sightings",
    buildParams(bbox, extra),
    signal,
  );
}
