"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MAP_STYLE } from "@/lib/config";
import {
  describeRegions,
  summarizeRegions,
  cellsInRegion,
  regionBBox,
} from "@/lib/regions";

export interface MiniMapCell {
  cell_lat: number;
  cell_lon: number;
  /** Drives the circle colour via the colour ramp. 0–1 expected. */
  value: number;
}

/** Default green→yellow→orange→red ramp (matches the risk legend). */
const DEFAULT_STOPS: [number, string][] = [
  [0, "#22c55e"],
  [0.25, "#eab308"],
  [0.5, "#f97316"],
  [0.75, "#ef4444"],
  [1, "#b91c1c"],
];

/**
 * A small, non-interactive MapLibre map that plots a set of hotspot cells and
 * auto-focuses on the densest region so coast-to-coast spreads don't collapse
 * into a tiny continental view. Region chips let the user jump between key
 * areas; the caption names where the dots are; an optional click links through
 * to the full risk map.
 */
export default function InsightMiniMap({
  cells,
  colorStops = DEFAULT_STOPS,
  caption,
  href,
  height = 300,
  maxWidth = 520,
  emptyLabel = "No cells match this selection.",
  showRegionChips = true,
  maxChips = 5,
}: {
  cells: MiniMapCell[];
  colorStops?: [number, string][];
  caption?: string;
  href?: string;
  height?: number;
  /** Cap the rendered width (centred) so full-width panels don't stretch. */
  maxWidth?: number;
  emptyLabel?: string;
  /** Show clickable region chips to focus the map on a key area. */
  showRegionChips?: boolean;
  maxChips?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const router = useRouter();

  /** null = auto (densest region); otherwise a named region focus. */
  const [focus, setFocus] = useState<string | null>(null);

  /** Region tally, recomputed when cells change. */
  const ranked = useMemo(() => summarizeRegions(cells), [cells]);

  /** Reset focus if the selected region vanishes (e.g. season change). */
  useEffect(() => {
    if (focus && !ranked.some((r) => r.name === focus)) setFocus(null);
  }, [focus, ranked]);

  /** Densest region is the default focus when the user hasn't picked one. */
  const activeRegion = focus ?? ranked[0]?.name ?? null;

  /** Cells to actually render — narrowed to the active region when possible. */
  const focusedCells = useMemo(() => {
    if (!activeRegion) return cells;
    const subset = cellsInRegion(cells, activeRegion);
    return subset.length > 0 ? subset : cells;
  }, [cells, activeRegion]);

  const geojson: GeoJSON.FeatureCollection = useMemo(
    () => ({
      type: "FeatureCollection",
      features: focusedCells.map((c) => ({
        type: "Feature",
        properties: { value: c.value },
        geometry: { type: "Point", coordinates: [c.cell_lon, c.cell_lat] },
      })),
    }),
    [focusedCells],
  );

  const autoCaption =
    caption ??
    (focusedCells.length > 0
      ? activeRegion
        ? `${activeRegion} — ${focusedCells.length.toLocaleString()} cells`
        : `Concentrated in ${describeRegions(cells)}`
      : "");

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [-76, 37.5],
      zoom: 3,
      interactive: false,
      attributionControl: false,
    });

    map.on("load", () => {
      map.addSource("hotspots", { type: "geojson", data: geojson });
      map.addLayer({
        id: "hotspots-glow",
        type: "circle",
        source: "hotspots",
        paint: {
          "circle-radius": 7,
          "circle-color": [
            "interpolate",
            ["linear"],
            ["get", "value"],
            ...colorStops.flat(),
          ],
          "circle-blur": 1,
          "circle-opacity": 0.35,
        },
      });
      map.addLayer({
        id: "hotspots-core",
        type: "circle",
        source: "hotspots",
        paint: {
          "circle-radius": 3,
          "circle-color": [
            "interpolate",
            ["linear"],
            ["get", "value"],
            ...colorStops.flat(),
          ],
          "circle-opacity": 0.9,
          "circle-stroke-width": 0.5,
          "circle-stroke-color": "rgba(255,255,255,0.3)",
        },
      });
      fitView(map, focusedCells, activeRegion);
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update data + bounds when the focused cells change after the initial mount.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const src = map.getSource("hotspots") as
      | maplibregl.GeoJSONSource
      | undefined;
    if (src) {
      src.setData(geojson);
      fitView(map, focusedCells, activeRegion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geojson]);

  const clickable = Boolean(href);
  const chips = ranked.slice(0, maxChips);

  return (
    <div className="mx-auto space-y-2" style={{ maxWidth }}>
      {showRegionChips && chips.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {chips.map((r) => {
            const active = r.name === activeRegion;
            return (
              <button
                key={r.name}
                onClick={() => setFocus(active && focus ? null : r.name)}
                className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
                  active
                    ? "border-ocean-500/70 bg-ocean-500/20 text-ocean-200"
                    : "border-ocean-800/40 bg-abyss-900/40 text-slate-400 hover:border-ocean-700/60 hover:text-slate-200"
                }`}
              >
                {r.name}
                <span className="ml-1 text-slate-500">
                  {r.count.toLocaleString()}
                </span>
              </button>
            );
          })}
        </div>
      )}
      <div
        onClick={clickable ? () => router.push(href as string) : undefined}
        className={`relative overflow-hidden rounded-xl border border-ocean-800/40 ${
          clickable
            ? "cursor-pointer transition-all hover:border-ocean-600/60"
            : ""
        }`}
      >
        <div ref={containerRef} style={{ height }} className="w-full" />
        {cells.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center bg-abyss-950/60 text-xs text-slate-500">
            {emptyLabel}
          </div>
        )}
        {autoCaption && focusedCells.length > 0 && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-abyss-950/90 to-transparent px-3 py-2">
            <span className="text-[11px] font-medium text-slate-200">
              {autoCaption}
            </span>
            {clickable && (
              <span className="shrink-0 text-[10px] text-ocean-400">
                Open on map →
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Fit the map view. Prefers the named region's fixed bbox (stable framing
 * across seasons); otherwise falls back to the cells' own bounding box.
 */
function fitView(
  map: maplibregl.Map,
  cells: MiniMapCell[],
  region: string | null,
) {
  if (cells.length === 0) return;

  if (region) {
    const bbox = regionBBox(region);
    if (bbox) {
      const [latMin, latMax, lonMin, lonMax] = bbox;
      map.fitBounds(
        [
          [lonMin, latMin],
          [lonMax, latMax],
        ],
        { padding: 18, maxZoom: 9, duration: 0 },
      );
      return;
    }
  }

  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLon = Infinity;
  let maxLon = -Infinity;
  for (const c of cells) {
    if (c.cell_lat < minLat) minLat = c.cell_lat;
    if (c.cell_lat > maxLat) maxLat = c.cell_lat;
    if (c.cell_lon < minLon) minLon = c.cell_lon;
    if (c.cell_lon > maxLon) maxLon = c.cell_lon;
  }
  map.fitBounds(
    [
      [minLon, minLat],
      [maxLon, maxLat],
    ],
    { padding: 24, maxZoom: 8, duration: 0 },
  );
}
