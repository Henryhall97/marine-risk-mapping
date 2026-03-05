import { API_BASE, MAX_BBOX_AREA_DEG2, PAGE_LIMIT } from "./config";
import type { BBox, PaginatedResponse, SpeedZone, MPA } from "./types";

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
