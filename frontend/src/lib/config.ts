/** API base URL — reads from env, falls back to local dev server. */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** H3 resolution used across the project. */
export const H3_RESOLUTION = 7;

/** CARTO Dark Matter — free vector basemap, no API key needed. */
export const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

/** Initial map view — US East Coast, where most risk data concentrates. */
export const INITIAL_VIEW_STATE = {
  latitude: 37.5,
  longitude: -76.0,
  zoom: 5.5,
  bearing: 0,
  pitch: 0,
} as const;

/** Maximum cells to request per API call. */
export const PAGE_LIMIT = 5_000;

/** API max bbox area — must match backend MAX_BBOX_AREA_DEG2. */
export const MAX_BBOX_AREA_DEG2 = 100;

/**
 * Build a `/map` URL with query params that position the map
 * on a specific location, layer, and season.
 */
export function mapLink(opts: {
  lat: number;
  lon: number;
  zoom?: number;
  layer?: string;
  season?: string | null;
  scenario?: string | null;
  decade?: string | null;
  /** Overlay names to enable on the map (e.g. "activeSMAs", "mpas"). */
  overlays?: string[];
  /** Traffic sub-metric to select (e.g. "speed_lethality", "night_traffic"). */
  metric?: string;
}): string {
  const p = new URLSearchParams();
  p.set("lat", opts.lat.toFixed(4));
  p.set("lon", opts.lon.toFixed(4));
  if (opts.zoom) p.set("zoom", String(opts.zoom));
  if (opts.layer) p.set("layer", opts.layer);
  if (opts.season && opts.season !== "annual") p.set("season", opts.season);
  if (opts.scenario) p.set("scenario", opts.scenario);
  if (opts.decade) p.set("decade", opts.decade);
  if (opts.overlays?.length) p.set("overlays", opts.overlays.join(","));
  if (opts.metric) p.set("metric", opts.metric);
  return `/map?${p.toString()}`;
}
