/**
 * Named marine regions for the study area (2°S–52°N, 180°W–59°W).
 *
 * Turns abstract H3-cell coordinates into human-readable place names so that
 * "111 high-risk cells" can become "111 high-risk cells, concentrated in the
 * Mid-Atlantic Bight & Gulf of Maine". Boxes are deliberately coarse — they
 * exist to give a user a sense of *where*, not survey-grade boundaries.
 */

export interface MarineRegion {
  name: string;
  /** [lat_min, lat_max, lon_min, lon_max] */
  bbox: [number, number, number, number];
}

/** Ordered most-specific first; the first containing box wins. */
export const REGIONS: MarineRegion[] = [
  // ── US East Coast ───────────────────────────────────────
  { name: "Gulf of Maine", bbox: [42.0, 45.0, -71.0, -66.0] },
  { name: "Georges Bank", bbox: [40.0, 42.0, -69.5, -65.5] },
  { name: "Mid-Atlantic Bight", bbox: [35.5, 41.5, -77.0, -69.5] },
  { name: "South Atlantic Bight", bbox: [27.5, 35.5, -82.0, -75.0] },
  { name: "Florida Straits", bbox: [23.5, 27.5, -83.5, -78.5] },
  // ── Gulf of Mexico & Caribbean ──────────────────────────
  { name: "Gulf of Mexico", bbox: [18.0, 31.0, -98.0, -81.0] },
  { name: "Caribbean Sea", bbox: [9.0, 23.5, -88.0, -59.0] },
  // ── US West Coast ───────────────────────────────────────
  { name: "Southern California Bight", bbox: [32.0, 34.6, -121.5, -116.5] },
  { name: "Central California", bbox: [34.6, 38.5, -124.5, -120.0] },
  { name: "Northern California", bbox: [38.5, 42.0, -125.5, -122.0] },
  { name: "Pacific Northwest", bbox: [42.0, 48.7, -126.5, -122.5] },
  // ── Alaska & North Pacific ──────────────────────────────
  { name: "Gulf of Alaska", bbox: [48.0, 52.0, -150.0, -130.0] },
  { name: "Aleutians & Bering", bbox: [48.0, 52.0, -180.0, -157.0] },
  // ── Hawaii ──────────────────────────────────────────────
  { name: "Hawaiian Islands", bbox: [17.5, 23.5, -161.5, -153.5] },
  // ── Eastern Tropical Pacific ────────────────────────────
  { name: "Eastern Tropical Pacific", bbox: [-2.0, 9.0, -120.0, -77.0] },
];

/** Coarse fallback basin when no specific region box contains the point. */
function fallbackBasin(lat: number, lon: number): string {
  if (lon < -100) return "Pacific waters";
  if (lat < 23.5 && lon > -88) return "Caribbean waters";
  if (lon > -82 && lat < 31) return "Gulf of Mexico";
  return "Atlantic waters";
}

/**
 * Coarse frames for the catch-all basins so a map focused on one of them
 * stays bounded instead of fitting scattered offshore points coast-to-coast.
 * [lat_min, lat_max, lon_min, lon_max].
 */
const BASIN_BBOX: Record<string, [number, number, number, number]> = {
  "Atlantic waters": [24.0, 46.0, -80.0, -62.0],
  "Pacific waters": [30.0, 52.0, -130.0, -116.0],
  "Caribbean waters": [9.0, 23.5, -85.0, -59.0],
  "Gulf of Mexico": [18.0, 31.0, -98.0, -81.0],
};

/** Return the named region containing a coordinate (or a coarse basin). */
export function regionForCell(lat: number, lon: number): string {
  for (const r of REGIONS) {
    const [latMin, latMax, lonMin, lonMax] = r.bbox;
    if (lat >= latMin && lat <= latMax && lon >= lonMin && lon <= lonMax) {
      return r.name;
    }
  }
  return fallbackBasin(lat, lon);
}

/** Look up a named region's bounding box (undefined for basin fallbacks). */
export function regionBBox(name: string): MarineRegion["bbox"] | undefined {
  return REGIONS.find((r) => r.name === name)?.bbox ?? BASIN_BBOX[name];
}

/** Subset of cells that fall inside a named region (by point-in-bbox). */
export function cellsInRegion<T extends { cell_lat: number; cell_lon: number }>(
  cells: T[],
  name: string,
): T[] {
  return cells.filter((c) => regionForCell(c.cell_lat, c.cell_lon) === name);
}

export interface RegionCount {
  name: string;
  count: number;
}

/**
 * Tally a set of cells by region, sorted by descending count.
 * Cells must expose `cell_lat` / `cell_lon`.
 */
export function summarizeRegions(
  cells: { cell_lat: number; cell_lon: number }[],
): RegionCount[] {
  const tally = new Map<string, number>();
  for (const c of cells) {
    const name = regionForCell(c.cell_lat, c.cell_lon);
    tally.set(name, (tally.get(name) ?? 0) + 1);
  }
  return [...tally.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);
}

/**
 * Produce a prose phrase naming the top regions, e.g.
 * "the Mid-Atlantic Bight, Gulf of Maine, and 2 other areas".
 */
export function describeRegions(
  cells: { cell_lat: number; cell_lon: number }[],
  topN = 2,
): string {
  const ranked = summarizeRegions(cells);
  if (ranked.length === 0) return "—";
  const top = ranked.slice(0, topN).map((r) => r.name);
  const remainder = ranked.length - top.length;
  if (remainder <= 0) {
    if (top.length === 1) return top[0];
    return `${top.slice(0, -1).join(", ")} and ${top[top.length - 1]}`;
  }
  return `${top.join(", ")} and ${remainder} other area${
    remainder === 1 ? "" : "s"
  }`;
}
