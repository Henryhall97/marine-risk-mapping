"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { latLngToCell } from "h3-js";
import {
  H3_RESOLUTION,
  MAX_BBOX_AREA_DEG2,
  PAGE_LIMIT,
} from "@/lib/config";
import { fetchHexLayer, bboxArea } from "@/lib/api";
import type { BBox, LayerType, Season, IsdmSpecies } from "@/lib/types";

/* ── Types & constants ───────────────────────────────────── */

type EnrichedCell = Record<string, unknown> & { h3: string };

/** Map layer → API endpoint. */
const LAYER_ENDPOINTS: Record<LayerType, string> = {
  risk: "/api/v1/risk/zones",
  risk_ml: "/api/v1/risk/ml",
  bathymetry: "/api/v1/layers/bathymetry",
  ocean: "/api/v1/layers/ocean",
  whale_predictions: "/api/v1/layers/whale-predictions",
  sdm_predictions: "/api/v1/layers/sdm-predictions",
  cetacean_density: "/api/v1/layers/cetacean-density",
  strike_density: "/api/v1/layers/strike-density",
  traffic_density: "/api/v1/layers/traffic-density",
};

/** Layers that accept a `season` query parameter. */
const SEASON_LAYERS = new Set<LayerType>([
  "risk",
  "risk_ml",
  "ocean",
  "whale_predictions",
  "sdm_predictions",
  "cetacean_density",
  "traffic_density",
]);

/** Max cells to keep in the persistent accumulation cache. */
const MAX_CACHE_SIZE = 200_000;

/** Max offset-pages to fetch per sub-tile. */
const MAX_PAGES_PER_TILE = 4;

/** Max sub-tiles when viewport exceeds the API area limit. */
const MAX_TILES = 16;

/** Debounce (ms) after viewport movement stops. */
const DEBOUNCE_MS = 150;

export interface MapDataResult {
  /** Cached cells — grows as user pans, resets on layer/season change. */
  data: EnrichedCell[];
  /** Number of cached cells. */
  total: number;
  /** Whether a fetch is in flight. */
  loading: boolean;
}

/* ── Helpers ─────────────────────────────────────────────── */

/** Enrich raw API rows with an h3 hex-string index for deck.gl. */
function enrichRows(
  rows: Record<string, unknown>[],
): EnrichedCell[] {
  return rows.map((d) => ({
    ...d,
    h3: latLngToCell(
      d.cell_lat as number,
      d.cell_lon as number,
      H3_RESOLUTION,
    ),
  }));
}

/**
 * Split a bbox into sub-tiles that each fit within `maxArea` deg².
 * Returns the original bbox if it already fits.
 * Returns [] if too many tiles would be needed (caller falls back).
 */
function tileBbox(bbox: BBox, maxArea: number): BBox[] {
  const area = bboxArea(bbox);
  if (area <= maxArea) return [bbox];

  const latSpan = bbox.lat_max - bbox.lat_min;
  const lonSpan = bbox.lon_max - bbox.lon_min;
  const side = Math.sqrt(maxArea * 0.85); // leave headroom
  const nLat = Math.max(1, Math.ceil(latSpan / side));
  const nLon = Math.max(1, Math.ceil(lonSpan / side));

  if (nLat * nLon > MAX_TILES) return [];

  const dLat = latSpan / nLat;
  const dLon = lonSpan / nLon;
  const tiles: BBox[] = [];
  for (let i = 0; i < nLat; i++) {
    for (let j = 0; j < nLon; j++) {
      tiles.push({
        lat_min: bbox.lat_min + i * dLat,
        lat_max: bbox.lat_min + (i + 1) * dLat,
        lon_min: bbox.lon_min + j * dLon,
        lon_max: bbox.lon_min + (j + 1) * dLon,
      });
    }
  }
  return tiles;
}

/** Paginate through one tile, collecting all returned cells. */
async function fetchTilePages(
  endpoint: string,
  tile: BBox,
  extra: Record<string, string | undefined>,
  signal: AbortSignal,
): Promise<EnrichedCell[]> {
  const cells: EnrichedCell[] = [];
  let offset = 0;

  for (let p = 0; p < MAX_PAGES_PER_TILE; p++) {
    const body = await fetchHexLayer(
      endpoint,
      tile,
      { ...extra, offset: String(offset) },
      signal,
    );
    cells.push(...enrichRows(body.data));
    if (body.data.length < PAGE_LIMIT || cells.length >= body.total) {
      break;
    }
    offset += PAGE_LIMIT;
  }
  return cells;
}

/**
 * Round bbox corners to ~0.01° to avoid re-triggering fetches
 * on sub-pixel pan movements.
 */
function snapBbox(bbox: BBox): string {
  return [
    bbox.lat_min.toFixed(2),
    bbox.lat_max.toFixed(2),
    bbox.lon_min.toFixed(2),
    bbox.lon_max.toFixed(2),
  ].join(",");
}

/* ── Hook ────────────────────────────────────────────────── */

/**
 * Fetch hex-cell data for the active layer + viewport.
 *
 * **Key behaviours:**
 * - Cells are cached by H3 index and persist across pan / zoom.
 * - Large viewports are split into sub-tiles fetched in parallel.
 * - Cache resets only when layer or season changes.
 * - Uses h3_cell bigint→hex instead of latLngToCell() (100× faster).
 * - Bbox snapped to 0.01° to avoid re-fetching on sub-pixel movement.
 * - Data array reference is stable when cache content hasn't changed.
 */
export function useMapData(
  bbox: BBox | null,
  layer: LayerType,
  season: Season,
  species?: IsdmSpecies | null,
): MapDataResult {
  const cacheRef = useRef(new Map<string, EnrichedCell>());
  const [data, setData] = useState<EnrichedCell[]>([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const keyRef = useRef("");
  const lastSnapRef = useRef("");

  /** Snapshot the current cache into React state. */
  const flush = useCallback(() => {
    setData(Array.from(cacheRef.current.values()));
  }, []);

  useEffect(() => {
    /* ── Reset cache on layer / season / species switch ── */
    const key = `${layer}:${season ?? "annual"}:${species ?? "all"}`;
    if (key !== keyRef.current) {
      keyRef.current = key;
      cacheRef.current = new Map();
      lastSnapRef.current = "";
      setData([]);
    }

    /* ── Snap bbox to avoid re-fetching on sub-pixel pan ── */
    if (!bbox) return;
    const snap = snapBbox(bbox);
    if (snap === lastSnapRef.current) return; // same tile region — skip

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(async () => {
      lastSnapRef.current = snap;

      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      setLoading(true);

      try {
        const endpoint = LAYER_ENDPOINTS[layer];
        const extra: Record<string, string | undefined> = {};
        if (season && SEASON_LAYERS.has(layer)) {
          extra.season = season;
        }
        if (layer === "bathymetry") {
          extra.exclude_land = "true";
        }
        if (species && layer === "whale_predictions") {
          extra.species = species;
        }
        if (species && layer === "sdm_predictions") {
          extra.species = species;
        }

        /* ── Tile the viewport ── */
        let tiles = tileBbox(bbox, MAX_BBOX_AREA_DEG2);

        if (tiles.length === 0) {
          // Viewport too wide for full tiling — fetch a single
          // center tile so the user still sees *something*.
          const cLat = (bbox.lat_min + bbox.lat_max) / 2;
          const cLon = (bbox.lon_min + bbox.lon_max) / 2;
          const half = Math.sqrt(MAX_BBOX_AREA_DEG2 * 0.85) / 2;
          tiles = [
            {
              lat_min: Math.max(-90, cLat - half),
              lat_max: Math.min(90, cLat + half),
              lon_min: Math.max(-180, cLon - half),
              lon_max: Math.min(180, cLon + half),
            },
          ];
        }

        /* ── Fetch all tiles in parallel ── */
        const settled = await Promise.allSettled(
          tiles.map((t) =>
            fetchTilePages(endpoint, t, extra, ctrl.signal),
          ),
        );

        /* ── Merge into persistent cache ── */
        const sizeBefore = cacheRef.current.size;
        for (const r of settled) {
          if (r.status !== "fulfilled") continue;
          for (const cell of r.value) {
            cacheRef.current.set(cell.h3, cell);
          }
        }

        /* ── Evict oldest entries if over budget ── */
        if (cacheRef.current.size > MAX_CACHE_SIZE) {
          const entries: [string, EnrichedCell][] = [
            ...cacheRef.current.entries(),
          ];
          cacheRef.current = new Map(
            entries.slice(entries.length - MAX_CACHE_SIZE),
          );
        }

        /* Only rebuild array if cache actually changed */
        if (
          cacheRef.current.size !== sizeBefore ||
          cacheRef.current.size === 0
        ) {
          flush();
        }
      } catch (err) {
        if (
          err instanceof DOMException &&
          err.name === "AbortError"
        ) {
          return;
        }
        console.error(`[useMapData] ${layer}:`, err);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      abortRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    bbox?.lat_min,
    bbox?.lat_max,
    bbox?.lon_min,
    bbox?.lon_max,
    layer,
    season,
    species,
    flush,
  ]);

  return { data, total: cacheRef.current.size, loading };
}
