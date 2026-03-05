"use client";

import { getLegendStops, getTrafficMetricConfig } from "@/lib/colors";
import type { IsdmSpecies, LayerType, TrafficMetric } from "@/lib/types";

const LAYER_LABELS: Record<LayerType, string> = {
  risk: "Collision Risk",
  risk_ml: "ML Risk",
  bathymetry: "Depth",
  ocean: "Sea Surface Temp",
  whale_predictions: "Whale Probability",
  sdm_predictions: "SDM Probability",
  cetacean_density: "Sighting Density",
  strike_density: "Strike Density",
  traffic_density: "Ship Traffic",
};

const SPECIES_DISPLAY: Record<IsdmSpecies, string> = {
  blue_whale: "Blue Whale",
  fin_whale: "Fin Whale",
  humpback_whale: "Humpback Whale",
  sperm_whale: "Sperm Whale",
};

export default function Legend({
  activeLayer,
  species,
  trafficMetric,
}: {
  activeLayer: LayerType;
  species?: IsdmSpecies | null;
  trafficMetric?: TrafficMetric;
}) {
  const stops = getLegendStops(activeLayer, species);
  let label: string;
  if ((activeLayer === "whale_predictions" || activeLayer === "sdm_predictions") && species) {
    const prefix = activeLayer === "sdm_predictions" ? "SDM " : "";
    label = `${prefix}${SPECIES_DISPLAY[species]} Probability`;
  } else if (activeLayer === "traffic_density" && trafficMetric) {
    label = getTrafficMetricConfig(trafficMetric).label;
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
