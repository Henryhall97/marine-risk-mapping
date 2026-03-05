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
