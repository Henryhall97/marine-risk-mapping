"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

/**
 * Lightweight MapLibre GL map showing the study-area bounding box
 * that the risk model covers. Non-interactive — just a visual aid.
 */

const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

/** US bounding box from pipeline/config.py */
const US_BBOX = {
  lat_min: -2.0,
  lat_max: 52.0,
  lon_min: -180.0,
  lon_max: -59.0,
};

export default function CoverageMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [-115, 28],
      zoom: 1.3,
      interactive: false,
      attributionControl: false,
    });

    map.on("load", () => {
      // Add the bounding box as a GeoJSON source
      map.addSource("coverage-bbox", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [US_BBOX.lon_min, US_BBOX.lat_min],
                [US_BBOX.lon_max, US_BBOX.lat_min],
                [US_BBOX.lon_max, US_BBOX.lat_max],
                [US_BBOX.lon_min, US_BBOX.lat_max],
                [US_BBOX.lon_min, US_BBOX.lat_min],
              ],
            ],
          },
        },
      });

      // Fill
      map.addLayer({
        id: "coverage-fill",
        type: "fill",
        source: "coverage-bbox",
        paint: {
          "fill-color": "#3b82f6",
          "fill-opacity": 0.08,
        },
      });

      // Border
      map.addLayer({
        id: "coverage-border",
        type: "line",
        source: "coverage-bbox",
        paint: {
          "line-color": "#3b82f6",
          "line-width": 2,
          "line-dasharray": [4, 3],
          "line-opacity": 0.6,
        },
      });

      // Corner labels
      const corners = [
        { coord: [US_BBOX.lon_min, US_BBOX.lat_max], label: "52°N, 180°W" },
        { coord: [US_BBOX.lon_max, US_BBOX.lat_max], label: "52°N, 59°W" },
        { coord: [US_BBOX.lon_min, US_BBOX.lat_min], label: "2°S, 180°W" },
        { coord: [US_BBOX.lon_max, US_BBOX.lat_min], label: "2°S, 59°W" },
      ];
      for (const c of corners) {
        const el = document.createElement("div");
        el.className = "text-[9px] text-ocean-400/60 font-mono whitespace-nowrap";
        el.textContent = c.label;
        new maplibregl.Marker({ element: el })
          .setLngLat(c.coord as [number, number])
          .addTo(map);
      }
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-ocean-800">
      <div ref={containerRef} className="h-[340px] w-full" />
      {/* Overlay label */}
      <div className="pointer-events-none absolute inset-0 flex items-end justify-center pb-4">
        <div className="rounded-full bg-abyss-900/80 px-4 py-1.5 text-xs font-medium text-slate-300 backdrop-blur-sm">
          Western Hemisphere coverage: 2°S–52°N × 180°W–59°W
        </div>
      </div>
    </div>
  );
}
