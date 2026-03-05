"use client";

import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { Map } from "react-map-gl/maplibre";
import { ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import "maplibre-gl/dist/maplibre-gl.css";
import { MAP_STYLE } from "@/lib/config";

/* ── Offline reverse-geocoder for US coastal waters ─────── */

interface CoastalRegion {
  name: string;
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
}

const COASTAL_REGIONS: CoastalRegion[] = [
  // East Coast — north to south
  { name: "Gulf of Maine", latMin: 42.5, latMax: 45.5, lonMin: -71, lonMax: -65 },
  { name: "Cape Cod, MA", latMin: 41.0, latMax: 42.5, lonMin: -71, lonMax: -69 },
  { name: "Nantucket Shoals", latMin: 40.5, latMax: 41.5, lonMin: -70.5, lonMax: -69 },
  { name: "Georges Bank", latMin: 40.5, latMax: 42.5, lonMin: -69, lonMax: -65 },
  { name: "Long Island Sound, NY", latMin: 40.5, latMax: 41.5, lonMin: -74, lonMax: -71.5 },
  { name: "New York Bight", latMin: 39.5, latMax: 41, lonMin: -74.5, lonMax: -71.5 },
  { name: "New Jersey Coast", latMin: 38.5, latMax: 40.5, lonMin: -75, lonMax: -73 },
  { name: "Delaware Bay", latMin: 38.5, latMax: 39.8, lonMin: -76, lonMax: -74.5 },
  { name: "Chesapeake Bay, VA", latMin: 36.5, latMax: 39.5, lonMin: -77.5, lonMax: -75.5 },
  { name: "Outer Banks, NC", latMin: 34.5, latMax: 36.5, lonMin: -77, lonMax: -74 },
  { name: "Cape Hatteras, NC", latMin: 34.5, latMax: 36, lonMin: -76.5, lonMax: -74 },
  { name: "South Carolina Coast", latMin: 32, latMax: 34.5, lonMin: -81, lonMax: -78 },
  { name: "Georgia Coast", latMin: 30.5, latMax: 32.2, lonMin: -82, lonMax: -79.5 },
  { name: "Jacksonville, FL", latMin: 29.5, latMax: 31, lonMin: -82, lonMax: -80 },
  { name: "East Florida Coast", latMin: 26, latMax: 30, lonMin: -81.5, lonMax: -79 },
  { name: "Florida Straits", latMin: 24, latMax: 26, lonMin: -83, lonMax: -79 },
  // Gulf of Mexico
  { name: "Florida Keys", latMin: 24, latMax: 25.5, lonMin: -82.5, lonMax: -79.5 },
  { name: "West Florida Shelf", latMin: 25, latMax: 30, lonMin: -87, lonMax: -82 },
  { name: "Gulf of Mexico", latMin: 25, latMax: 31, lonMin: -98, lonMax: -87 },
  { name: "Mississippi Delta", latMin: 28, latMax: 30.5, lonMin: -91, lonMax: -88 },
  { name: "Texas Coast", latMin: 25.5, latMax: 30, lonMin: -98, lonMax: -93 },
  // West Coast — south to north
  { name: "Southern California Bight", latMin: 32, latMax: 34.5, lonMin: -121, lonMax: -117 },
  { name: "Channel Islands, CA", latMin: 33, latMax: 34.5, lonMin: -121, lonMax: -119 },
  { name: "Central California Coast", latMin: 34.5, latMax: 38, lonMin: -124, lonMax: -120 },
  { name: "Monterey Bay, CA", latMin: 36, latMax: 37.2, lonMin: -123, lonMax: -121.5 },
  { name: "San Francisco Bay Area", latMin: 37, latMax: 38.5, lonMin: -124, lonMax: -121.5 },
  { name: "Northern California Coast", latMin: 38, latMax: 42, lonMin: -126, lonMax: -123 },
  { name: "Oregon Coast", latMin: 42, latMax: 46.5, lonMin: -126, lonMax: -123.5 },
  { name: "Washington Coast", latMin: 46, latMax: 49, lonMin: -126, lonMax: -123 },
  { name: "Puget Sound, WA", latMin: 47, latMax: 49, lonMin: -124, lonMax: -122 },
  { name: "Salish Sea", latMin: 48, latMax: 49.5, lonMin: -124, lonMax: -122 },
  // Alaska
  { name: "Gulf of Alaska", latMin: 54, latMax: 62, lonMin: -155, lonMax: -130 },
  { name: "Southeast Alaska", latMin: 54, latMax: 60, lonMin: -140, lonMax: -130 },
  { name: "Kodiak Island, AK", latMin: 56, latMax: 59, lonMin: -156, lonMax: -150 },
  { name: "Aleutian Islands", latMin: 50, latMax: 56, lonMin: -180, lonMax: -163 },
  { name: "Bering Sea", latMin: 54, latMax: 66, lonMin: -180, lonMax: -160 },
  // Hawaii
  { name: "Hawaiian Islands", latMin: 18, latMax: 23, lonMin: -162, lonMax: -154 },
  { name: "Maui, HI", latMin: 20, latMax: 21.3, lonMin: -157, lonMax: -155.5 },
  // Open ocean fallbacks
  { name: "North Atlantic", latMin: 30, latMax: 50, lonMin: -70, lonMax: -40 },
  { name: "North Pacific", latMin: 30, latMax: 55, lonMin: -160, lonMax: -120 },
];

function getLocationLabel(lat: number, lon: number): string {
  // Find the best (smallest) matching region
  let bestRegion: CoastalRegion | null = null;
  let bestArea = Infinity;

  for (const r of COASTAL_REGIONS) {
    if (lat >= r.latMin && lat <= r.latMax && lon >= r.lonMin && lon <= r.lonMax) {
      const area = (r.latMax - r.latMin) * (r.lonMax - r.lonMin);
      if (area < bestArea) {
        bestArea = area;
        bestRegion = r;
      }
    }
  }

  if (bestRegion) return bestRegion.name;

  // Generic cardinal direction from US mainland centroid
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= -100 ? "W" : "W";
  return `${Math.abs(lat).toFixed(1)}°${ns}, ${Math.abs(lon).toFixed(1)}°${ew}`;
}

/* ── Component ──────────────────────────────────────────── */

interface Props {
  lat: number;
  lon: number;
  /** Optional label shown beside the pin (e.g. species). */
  label?: string;
  /** Map container height in pixels. */
  height?: number;
  /** Initial zoom level (default 5). */
  zoom?: number;
  /** Allow zoom / pan (default false — static preview). */
  interactive?: boolean;
}

/**
 * A map that shows a single location pin with a geographic region
 * label. Static by default; pass interactive=true for zoom/pan.
 */
export default function LocationPin({
  lat,
  lon,
  label,
  height = 200,
  zoom = 5,
  interactive = false,
}: Props) {
  const viewState = useMemo(
    () => ({
      latitude: lat,
      longitude: lon,
      zoom,
      bearing: 0,
      pitch: 0,
    }),
    [lat, lon, zoom],
  );

  const regionName = useMemo(() => getLocationLabel(lat, lon), [lat, lon]);

  const data = useMemo(() => [{ lat, lon, label: label ?? "" }], [lat, lon, label]);

  const layers = useMemo(
    () => [
      // Outer glow ring
      new ScatterplotLayer({
        id: "pin-glow",
        data,
        getPosition: (d: (typeof data)[0]) => [d.lon, d.lat],
        getFillColor: [34, 211, 238, 60],
        getRadius: 2400,
        radiusMinPixels: 14,
        radiusMaxPixels: 30,
        pickable: false,
      }),
      // Inner pin dot
      new ScatterplotLayer({
        id: "pin-dot",
        data,
        getPosition: (d: (typeof data)[0]) => [d.lon, d.lat],
        getFillColor: [34, 211, 238, 220],
        getLineColor: [255, 255, 255, 200],
        getRadius: 1000,
        radiusMinPixels: 6,
        radiusMaxPixels: 14,
        stroked: true,
        lineWidthMinPixels: 2,
        pickable: false,
      }),
      // Species label on map
      ...(label
        ? [
            new TextLayer({
              id: "pin-label",
              data,
              getPosition: (d: (typeof data)[0]) => [d.lon, d.lat],
              getText: (d: (typeof data)[0]) => d.label,
              getColor: [255, 255, 255, 200],
              getSize: 13,
              getPixelOffset: [0, -24],
              fontFamily: "Inter, system-ui, sans-serif",
              fontWeight: "bold",
              pickable: false,
            }),
          ]
        : []),
    ],
    [data, label],
  );

  return (
    <div
      className="relative overflow-hidden rounded-xl border border-ocean-800"
      style={{ height }}
    >
      <DeckGL
        initialViewState={viewState}
        controller={interactive ? { scrollZoom: true, dragPan: true, doubleClickZoom: true, touchZoom: true, touchRotate: false, dragRotate: false } : false}
        layers={layers}
        style={{ position: "relative", width: "100%", height: "100%" }}
      >
        <Map mapStyle={MAP_STYLE} />
      </DeckGL>

      {/* Location name + coordinates badge */}
      <div className="absolute bottom-2 left-2 flex items-center gap-2">
        <div className="rounded-md bg-black/70 px-2.5 py-1.5 backdrop-blur-sm">
          <p className="text-[11px] font-semibold text-white leading-tight">
            📍 {regionName}
          </p>
          <p className="text-[10px] text-slate-400 leading-tight">
            {lat.toFixed(4)}°, {lon.toFixed(4)}°
          </p>
        </div>
      </div>
    </div>
  );
}
