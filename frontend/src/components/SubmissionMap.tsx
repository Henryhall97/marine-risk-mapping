"use client";

import { useMemo, useRef, useState } from "react";
import DeckGL from "@deck.gl/react";
import { Map, type MapRef } from "react-map-gl/maplibre";
import { ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import "maplibre-gl/dist/maplibre-gl.css";
import { MAP_STYLE } from "@/lib/config";

/* ── Types ───────────────────────────────────────────────── */

export interface MapSubmission {
  id: string;
  lat: number;
  lon: number;
  species: string;
  interaction_type: string | null;
  verification_status: string;
  submitter_name: string | null;
  created_at: string;
}

type ColorBy = "species" | "interaction" | "verification";

/* ── Colour palettes ─────────────────────────────────────── */

const SPECIES_COLORS: Record<string, [number, number, number]> = {
  humpback_whale: [56, 189, 248],
  right_whale: [248, 113, 113],
  fin_whale: [251, 191, 36],
  blue_whale: [96, 165, 250],
  minke_whale: [167, 139, 250],
  sperm_whale: [244, 114, 182],
  sei_whale: [52, 211, 153],
  killer_whale: [251, 146, 60],
};

const VERIFICATION_COLORS: Record<string, [number, number, number]> = {
  verified: [74, 222, 128],
  unverified: [156, 163, 175],
  disputed: [250, 204, 21],
  rejected: [248, 113, 113],
};

const INTERACTION_COLORS: Record<string, [number, number, number]> = {
  visual_sighting: [56, 189, 248],
  acoustic_detection: [167, 139, 250],
  vessel_interaction: [248, 113, 113],
  stranding: [251, 146, 60],
  entanglement: [244, 114, 182],
};

const DEFAULT_COLOR: [number, number, number] = [156, 163, 175];

function getColor(d: MapSubmission, colorBy: ColorBy): [number, number, number] {
  if (colorBy === "species") {
    return SPECIES_COLORS[d.species] ?? DEFAULT_COLOR;
  }
  if (colorBy === "verification") {
    return VERIFICATION_COLORS[d.verification_status] ?? DEFAULT_COLOR;
  }
  return INTERACTION_COLORS[d.interaction_type ?? ""] ?? DEFAULT_COLOR;
}

function getLegendItems(colorBy: ColorBy, data: MapSubmission[]) {
  if (colorBy === "species") {
    const seen = new Set(data.map((d) => d.species));
    return Object.entries(SPECIES_COLORS)
      .filter(([k]) => seen.has(k))
      .map(([k, v]) => ({ label: k.replace(/_/g, " "), color: v }))
      .concat(
        seen.has("") || data.some((d) => !SPECIES_COLORS[d.species])
          ? [{ label: "other", color: DEFAULT_COLOR }]
          : [],
      );
  }
  if (colorBy === "verification") {
    return Object.entries(VERIFICATION_COLORS).map(([k, v]) => ({
      label: k,
      color: v,
    }));
  }
  const seen = new Set(data.map((d) => d.interaction_type ?? ""));
  return Object.entries(INTERACTION_COLORS)
    .filter(([k]) => seen.has(k))
    .map(([k, v]) => ({ label: k.replace(/_/g, " "), color: v }))
    .concat(
      data.some((d) => !INTERACTION_COLORS[d.interaction_type ?? ""])
        ? [{ label: "other", color: DEFAULT_COLOR }]
        : [],
    );
}

/* ── Component ───────────────────────────────────────────── */

export default function SubmissionMap({
  data,
  onClickSubmission,
}: {
  data: MapSubmission[];
  onClickSubmission?: (id: string) => void;
}) {
  const mapRef = useRef<MapRef>(null);
  const [colorBy, setColorBy] = useState<ColorBy>("species");
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    d: MapSubmission;
  } | null>(null);

  const geoData = useMemo(
    () => data.filter((d) => d.lat != null && d.lon != null),
    [data],
  );

  const layers = [
    new ScatterplotLayer<MapSubmission>({
      id: "sightings-scatter",
      data: geoData,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: (d) => [...getColor(d, colorBy), 200],
      getRadius: 6000,
      radiusMinPixels: 5,
      radiusMaxPixels: 14,
      pickable: true,
      onClick: ({ object }) => {
        if (object && onClickSubmission) onClickSubmission(object.id);
      },
      onHover: ({ object, x, y }) => {
        setTooltip(object ? { x, y, d: object } : null);
      },
      stroked: true,
      getLineColor: [255, 255, 255, 80],
      lineWidthMinPixels: 1,
    }),
    new TextLayer<MapSubmission>({
      id: "sightings-labels",
      data: geoData,
      getPosition: (d) => [d.lon, d.lat],
      getText: (d) =>
        d.verification_status === "verified"
          ? "✓"
          : d.verification_status === "disputed"
            ? "?"
            : "",
      getSize: 11,
      getColor: [255, 255, 255, 200],
      getTextAnchor: "middle" as const,
      getAlignmentBaseline: "center" as const,
      fontFamily: "system-ui",
    }),
  ];

  const legendItems = getLegendItems(colorBy, geoData);

  return (
    <div className="relative h-full w-full">
      <DeckGL
        initialViewState={{
          latitude: 37.5,
          longitude: -76.0,
          zoom: 4.2,
          bearing: 0,
          pitch: 0,
        }}
        controller
        layers={layers}
        style={{ position: "absolute", inset: "0" }}
        getCursor={({ isHovering }) =>
          isHovering ? "pointer" : "grab"
        }
      >
        <Map ref={mapRef} mapStyle={MAP_STYLE} />
      </DeckGL>

      {/* Toggle controls */}
      <div className="absolute top-3 left-3 z-10 flex gap-1 rounded-lg border border-ocean-800 bg-abyss-900/90 p-1 backdrop-blur">
        {(["species", "interaction", "verification"] as ColorBy[]).map((c) => (
          <button
            key={c}
            onClick={() => setColorBy(c)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              colorBy === c
                ? "bg-ocean-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            {c === "interaction" ? "Type" : c.charAt(0).toUpperCase() + c.slice(1)}
          </button>
        ))}
      </div>

      {/* Inline legend */}
      <div className="absolute right-3 bottom-3 z-10 rounded-lg border border-ocean-800 bg-abyss-900/90 p-2.5 backdrop-blur">
        <div className="space-y-1">
          {legendItems.map((item) => (
            <div key={item.label} className="flex items-center gap-2 text-xs">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{
                  backgroundColor: `rgb(${item.color[0]},${item.color[1]},${item.color[2]})`,
                }}
              />
              <span className="capitalize text-slate-300">{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none absolute z-20 rounded-lg border border-ocean-800 bg-abyss-900/95 px-3 py-2 text-xs backdrop-blur"
          style={{ left: tooltip.x + 12, top: tooltip.y - 12 }}
        >
          <div className="font-medium text-white">
            {tooltip.d.species.replace(/_/g, " ") || "Unknown"}
          </div>
          <div className="text-slate-400">
            by {tooltip.d.submitter_name ?? "Anonymous"}
          </div>
          <div className="text-slate-500">
            {new Date(tooltip.d.created_at).toLocaleDateString()}
            {tooltip.d.interaction_type &&
              ` · ${tooltip.d.interaction_type.replace(/_/g, " ")}`}
          </div>
          <div className="mt-0.5">
            <span
              className={`text-xs ${
                tooltip.d.verification_status === "verified"
                  ? "text-green-400"
                  : tooltip.d.verification_status === "disputed"
                    ? "text-yellow-400"
                    : tooltip.d.verification_status === "rejected"
                      ? "text-red-400"
                      : "text-slate-400"
              }`}
            >
              {tooltip.d.verification_status}
            </span>
          </div>
        </div>
      )}

      {/* Count badge */}
      <div className="absolute top-3 right-3 z-10 rounded-full border border-ocean-800 bg-abyss-900/90 px-3 py-1 text-xs text-slate-400 backdrop-blur">
        {geoData.length} on map
      </div>
    </div>
  );
}
