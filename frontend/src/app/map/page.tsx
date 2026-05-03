"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import type { LayerType, Season, TrafficMetric, OverlayToggles } from "@/lib/types";
import { SonarPing } from "@/components/animations";

// Deck.gl + MapLibre require browser APIs — disable SSR.
const MapView = dynamic(() => import("@/components/MapView"), {
  ssr: false,
  loading: () => (
    <div className="flex h-screen w-screen items-center justify-center bg-abyss-950">
      <div className="flex flex-col items-center gap-3">
        <SonarPing size={96} ringCount={3} active />
        <span className="text-xs text-ocean-400/70">Loading map…</span>
      </div>
    </div>
  ),
});

const VALID_LAYERS = new Set<string>([
  "none",
  "risk",
  "risk_ml",
  "bathymetry",
  "ocean",
  "whale_predictions",
  "sdm",
  "sdm_predictions",
  "sdm_projections",
  "cetacean_density",
  "strike_density",
  "traffic_density",
]);

/** Map legacy layer params to current identifiers. */
const LAYER_ALIASES: Record<string, string> = {
  sdm_predictions: "sdm",
  sdm_projections: "sdm",
};
const VALID_SEASONS = new Set<string>([
  "winter",
  "spring",
  "summer",
  "fall",
  "all",
]);

function MapWithParams() {
  const searchParams = useSearchParams();

  const lat = searchParams.get("lat");
  const lon = searchParams.get("lon");
  const zoom = searchParams.get("zoom");
  const layer = searchParams.get("layer");
  const season = searchParams.get("season");
  const checkRisk = searchParams.get("checkRisk");
  const overlaysParam = searchParams.get("overlays");
  const metricParam = searchParams.get("metric");

  /* Parse overlay toggles from comma-separated URL param */
  const VALID_OVERLAYS = new Set([
    "activeSMAs", "proposedZones", "mpas", "bias",
    "criticalHabitat", "shippingLanes", "slowZones",
    "communitySightings",
  ]);
  let initialOverlays: Partial<OverlayToggles> | undefined;
  if (overlaysParam) {
    initialOverlays = {};
    for (const name of overlaysParam.split(",")) {
      const trimmed = name.trim();
      if (VALID_OVERLAYS.has(trimmed)) {
        (initialOverlays as Record<string, boolean>)[trimmed] = true;
      }
    }
  }

  const VALID_METRICS = new Set([
    "vessel_density", "speed_lethality", "high_speed",
    "draft_risk", "night_traffic", "commercial",
  ]);

  return (
    <MapView
      initialLat={lat ? parseFloat(lat) : undefined}
      initialLon={lon ? parseFloat(lon) : undefined}
      initialZoom={zoom ? parseFloat(zoom) : undefined}
      initialLayer={
        layer && VALID_LAYERS.has(layer)
          ? ((LAYER_ALIASES[layer] ?? layer) as LayerType)
          : undefined
      }
      initialSeason={
        season && VALID_SEASONS.has(season) ? (season as Season) : undefined
      }
      initialCheckRisk={checkRisk === "true"}
      initialOverlays={initialOverlays}
      initialTrafficMetric={
        metricParam && VALID_METRICS.has(metricParam)
          ? (metricParam as TrafficMetric)
          : undefined
      }
    />
  );
}

export default function MapPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen w-screen items-center justify-center bg-abyss-950">
          <div className="flex flex-col items-center gap-3">
            <SonarPing size={96} ringCount={3} active />
            <span className="text-xs text-ocean-400/70">Loading map…</span>
          </div>
        </div>
      }
    >
      <MapWithParams />
    </Suspense>
  );
}
