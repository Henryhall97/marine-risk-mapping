"use client";

import { getLegendStops, getTrafficMetricConfig, getOceanMetricConfig } from "@/lib/colors";
import type { IsdmSpecies, LayerType, OceanMetric, ProjectionMode, SdmTimePeriod, TrafficMetric } from "@/lib/types";

const LAYER_LABELS: Record<LayerType, string> = {
  none: "",
  risk: "Survey-Based Risk",
  risk_ml: "Modelled Risk",
  bathymetry: "Depth",
  ocean: "Ocean Covariates",
  whale_predictions: "Whale Habitat (Expert)",
  sdm: "Whale Habitat (Observed)",
  cetacean_density: "Sighting Records",
  strike_density: "Strike History",
  traffic_density: "Ship Traffic",
};

const SPECIES_DISPLAY: Record<IsdmSpecies, string> = {
  blue_whale: "Blue Whale",
  fin_whale: "Fin Whale",
  humpback_whale: "Humpback Whale",
  sperm_whale: "Sperm Whale",
  right_whale: "Right Whale",
  minke_whale: "Minke Whale",
};

export default function Legend({
  activeLayer,
  species,
  trafficMetric,
  oceanMetric,
  projectionMode,
  sdmTimePeriod = "current",
}: {
  activeLayer: LayerType;
  species?: IsdmSpecies | null;
  trafficMetric?: TrafficMetric;
  oceanMetric?: OceanMetric;
  projectionMode?: ProjectionMode;
  sdmTimePeriod?: SdmTimePeriod;
}) {
  const stops = getLegendStops(
    activeLayer,
    species,
    oceanMetric,
    projectionMode,
    sdmTimePeriod,
  );

  // No legend when data layers are removed
  if (activeLayer === "none" || stops.length === 0) return null;

  const isProjection =
    (activeLayer === "sdm" || activeLayer === "whale_predictions" || activeLayer === "risk_ml" || activeLayer === "ocean") &&
    sdmTimePeriod !== "current";

  let label: string;
  if (isProjection && activeLayer === "risk_ml" && projectionMode === "change") {
    label = "Risk Change from Today";
  } else if (isProjection && activeLayer === "risk_ml") {
    label = `Projected Modelled Risk · ${sdmTimePeriod}`;
  } else if (isProjection && activeLayer === "ocean" && projectionMode === "change") {
    const cfg = getOceanMetricConfig(oceanMetric ?? "sst");
    label = `Δ ${cfg.label} (Change from Today)`;
  } else if (isProjection && activeLayer === "ocean") {
    const cfg = getOceanMetricConfig(oceanMetric ?? "sst");
    label = `Projected ${cfg.label} · ${sdmTimePeriod}`;
  } else if (isProjection && projectionMode === "change") {
    label = species
      ? `${SPECIES_DISPLAY[species]} Change from Today`
      : "Habitat Change from Today";
  } else if ((activeLayer === "whale_predictions" || activeLayer === "sdm") && species) {
    const prefix = isProjection
      ? "Projected "
      : activeLayer === "sdm"
        ? "Observed "
        : "Expert ";
    label = `${prefix}${SPECIES_DISPLAY[species]} Probability`;
  } else if (activeLayer === "traffic_density" && trafficMetric) {
    label = getTrafficMetricConfig(trafficMetric).label;
  } else if (activeLayer === "ocean" && oceanMetric) {
    label = getOceanMetricConfig(oceanMetric).label;
  } else if (isProjection) {
    const src = activeLayer === "whale_predictions" ? "Expert" : "Observed";
    label = `Projected ${src} Habitat · ${sdmTimePeriod}`;
  } else {
    label = LAYER_LABELS[activeLayer];
  }

  return (
    <div className="glass-panel-strong absolute bottom-6 right-4 z-10 rounded-xl px-4 py-3 shadow-ocean-md">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ocean-400">
        {label}
      </p>
      <div className="flex items-end gap-0">
        {stops.map((s, i) => (
          <div key={i} className="flex flex-col items-center">
            <div
              className="h-3 w-12"
              style={{
                backgroundColor: s.color,
                borderRadius:
                  i === 0
                    ? "4px 0 0 4px"
                    : i === stops.length - 1
                      ? "0 4px 4px 0"
                      : undefined,
              }}
            />
            <span className="mt-1 text-[10px] text-slate-400">
              {s.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
