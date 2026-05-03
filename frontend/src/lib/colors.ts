/* ── Colour ramps for map layers ────────────────────────── */

import type { IsdmSpecies, LayerType, OceanMetric, ProjectionMode, TrafficMetric } from "./types";

/** RGBA tuple for deck.gl. */
type RGBA = [number, number, number, number];

/** RGB tuple for deck.gl HeatmapLayer colorRange. */
export type RGB = [number, number, number];

/* ── Interpolation engine ────────────────────────────────── */

const lerp = (a: RGBA, b: RGBA, t: number): RGBA => [
  Math.round(a[0] + (b[0] - a[0]) * t),
  Math.round(a[1] + (b[1] - a[1]) * t),
  Math.round(a[2] + (b[2] - a[2]) * t),
  Math.round(a[3] + (b[3] - a[3]) * t),
];

function fromStops(value: number, stops: [number, RGBA][]): RGBA {
  const v = Math.max(0, Math.min(1, value));
  for (let i = 1; i < stops.length; i++) {
    if (v <= stops[i][0]) {
      const t =
        (v - stops[i - 1][0]) / (stops[i][0] - stops[i - 1][0]);
      return lerp(stops[i - 1][1], stops[i][1], t);
    }
  }
  return stops[stops.length - 1][1];
}

/* ── Risk (blue → yellow → red) ──────────────────────────── */

const RISK_STOPS: [number, RGBA][] = [
  [0.0, [33, 102, 172, 200]],
  [0.2, [103, 169, 207, 200]],
  [0.4, [253, 219, 199, 200]],
  [0.6, [239, 138, 98, 200]],
  [0.8, [178, 24, 43, 200]],
  [1.0, [128, 0, 0, 220]],
];

export const riskColor = (s: number): RGBA => fromStops(s, RISK_STOPS);

/* ── Bathymetry (pale → dark blue) ───────────────────────── */

const BATHY_STOPS: [number, RGBA][] = [
  [0.0, [200, 220, 240, 200]],
  [0.2, [120, 170, 220, 200]],
  [0.5, [50, 100, 180, 200]],
  [0.8, [20, 50, 130, 200]],
  [1.0, [5, 20, 80, 200]],
];

export function bathymetryColor(depthM: number): RGBA {
  // 0 m (surface) → 6000 m (deep ocean)
  const t = Math.min(Math.abs(depthM), 6000) / 6000;
  return fromStops(t, BATHY_STOPS);
}

/* ── SST (cold blue → warm red) ──────────────────────────── */

const SST_STOPS: [number, RGBA][] = [
  [0.0, [33, 102, 172, 200]],
  [0.25, [103, 169, 207, 200]],
  [0.5, [255, 237, 160, 200]],
  [0.75, [239, 138, 98, 200]],
  [1.0, [178, 24, 43, 200]],
];

export function sstColor(sst: number): RGBA {
  const t = Math.max(0, Math.min(sst, 30)) / 30;
  return fromStops(t, SST_STOPS);
}

/* ── MLD (Mixed Layer Depth: light cyan → dark blue) ─────── */

const MLD_STOPS: [number, RGBA][] = [
  [0.0, [180, 230, 240, 200]],
  [0.25, [80, 180, 220, 200]],
  [0.5, [40, 120, 200, 200]],
  [0.75, [20, 60, 160, 200]],
  [1.0, [10, 20, 100, 220]],
];

export function mldColor(mld: number): RGBA {
  const t = Math.max(0, Math.min(mld, 200)) / 200;
  return fromStops(t, MLD_STOPS);
}

/* ── SLA (Sea Level Anomaly: blue → white → red) ────────── */

const SLA_STOPS: [number, RGBA][] = [
  [0.0, [33, 80, 172, 200]],
  [0.25, [100, 140, 210, 200]],
  [0.5, [230, 230, 230, 180]],
  [0.75, [230, 120, 80, 200]],
  [1.0, [178, 24, 43, 220]],
];

export function slaColor(sla: number): RGBA {
  // Map -0.5..+0.5 → 0..1
  const t = Math.max(0, Math.min((sla + 0.5) / 1.0, 1));
  return fromStops(t, SLA_STOPS);
}

/* ── SST SD (variability: low green → high orange/red) ──── */

const SST_SD_STOPS: [number, RGBA][] = [
  [0.0, [60, 180, 100, 180]],
  [0.25, [140, 210, 100, 190]],
  [0.5, [240, 220, 80, 200]],
  [0.75, [240, 140, 40, 210]],
  [1.0, [200, 40, 20, 220]],
];

export function sstSdColor(sd: number): RGBA {
  const t = Math.max(0, Math.min(sd, 5)) / 5;
  return fromStops(t, SST_SD_STOPS);
}

/* ── PP (Primary Productivity: pale → green → dark green) ── */

const PP_STOPS: [number, RGBA][] = [
  [0.0, [230, 240, 220, 160]],
  [0.25, [140, 200, 80, 190]],
  [0.5, [60, 160, 40, 200]],
  [0.75, [20, 120, 20, 210]],
  [1.0, [5, 60, 5, 230]],
];

export function ppColor(pp: number): RGBA {
  const t = Math.max(0, Math.min(pp, 2000)) / 2000;
  return fromStops(t, PP_STOPS);
}

/* ── Ocean metric config ─────────────────────────────────── */

export function getOceanMetricConfig(metric: OceanMetric): {
  field: string;
  minVal: number;
  maxVal: number;
  defaultVal: number;
  colorFn: (v: number) => RGBA;
  label: string;
  unit: string;
  decimals: number;
} {
  switch (metric) {
    case "sst_sd":
      return {
        field: "sst_sd",
        minVal: 0,
        maxVal: 5,
        defaultVal: 0,
        colorFn: sstSdColor,
        label: "SST Variability",
        unit: "°C",
        decimals: 2,
      };
    case "mld":
      return {
        field: "mld",
        minVal: 0,
        maxVal: 200,
        defaultVal: 0,
        colorFn: mldColor,
        label: "Mixed Layer Depth",
        unit: "m",
        decimals: 1,
      };
    case "sla":
      return {
        field: "sla",
        minVal: -0.5,
        maxVal: 0.5,
        defaultVal: 0,
        colorFn: slaColor,
        label: "Sea Level Anomaly",
        unit: "m",
        decimals: 3,
      };
    case "pp_upper_200m":
      return {
        field: "pp_upper_200m",
        minVal: 0,
        maxVal: 2000,
        defaultVal: 0,
        colorFn: ppColor,
        label: "Primary Productivity",
        unit: "mg C/m²/day",
        decimals: 0,
      };
    case "sst":
    default:
      return {
        field: "sst",
        minVal: 0,
        maxVal: 30,
        defaultVal: 15,
        colorFn: sstColor,
        label: "Sea Surface Temp",
        unit: "°C",
        decimals: 1,
      };
  }
}

/* ── Whale probability (grey → green → red) ──────────────── */

const WHALE_STOPS: [number, RGBA][] = [
  [0.0, [200, 200, 200, 40]],
  [0.2, [100, 200, 100, 150]],
  [0.5, [255, 255, 100, 180]],
  [0.8, [255, 100, 50, 200]],
  [1.0, [200, 0, 0, 220]],
];

export const whaleProbColor = (p: number): RGBA =>
  fromStops(p, WHALE_STOPS);

/* ── Species-specific ramps ───────────────────────────────── */

const SPECIES_STOPS: Record<IsdmSpecies, [number, RGBA][]> = {
  blue_whale: [
    [0.0, [200, 200, 220, 30]],
    [0.2, [80, 130, 220, 140]],
    [0.5, [40, 80, 200, 180]],
    [0.8, [20, 40, 180, 210]],
    [1.0, [10, 10, 140, 230]],
  ],
  fin_whale: [
    [0.0, [200, 200, 200, 30]],
    [0.2, [170, 120, 80, 140]],
    [0.5, [140, 80, 40, 180]],
    [0.8, [110, 50, 20, 210]],
    [1.0, [80, 30, 10, 230]],
  ],
  humpback_whale: [
    [0.0, [200, 220, 200, 30]],
    [0.2, [80, 180, 80, 140]],
    [0.5, [40, 150, 40, 180]],
    [0.8, [20, 120, 20, 210]],
    [1.0, [10, 80, 10, 230]],
  ],
  sperm_whale: [
    [0.0, [200, 200, 200, 30]],
    [0.2, [140, 140, 140, 140]],
    [0.5, [100, 100, 100, 180]],
    [0.8, [60, 60, 60, 210]],
    [1.0, [30, 30, 30, 230]],
  ],
  right_whale: [
    [0.0, [220, 200, 200, 30]],
    [0.2, [220, 100, 80, 140]],
    [0.5, [200, 60, 50, 180]],
    [0.8, [180, 30, 30, 210]],
    [1.0, [140, 10, 10, 230]],
  ],
  minke_whale: [
    [0.0, [200, 220, 220, 30]],
    [0.2, [80, 200, 200, 140]],
    [0.5, [40, 180, 180, 180]],
    [0.8, [20, 150, 150, 210]],
    [1.0, [10, 110, 110, 230]],
  ],
};

export function speciesProbColor(
  species: IsdmSpecies,
  p: number,
): RGBA {
  return fromStops(p, SPECIES_STOPS[species]);
}

/* ── Climate projection probability (amber → deep orange) ── */

const PROJECTION_STOPS: [number, RGBA][] = [
  [0.0, [200, 200, 180, 40]],
  [0.2, [255, 200, 80, 150]],
  [0.5, [255, 150, 40, 180]],
  [0.8, [220, 80, 20, 210]],
  [1.0, [160, 20, 10, 230]],
];

export const projectionProbColor = (p: number): RGBA =>
  fromStops(p, PROJECTION_STOPS);

/* ── Climate projection change (diverging: red → white → blue) ── */

/**
 * Diverging ramp for habitat change vs baseline.
 * Input: normalised 0–1 where 0.5 = no change.
 *   0.0 = max habitat loss  (warm red)
 *   0.5 = no change          (neutral grey)
 *   1.0 = max habitat gain   (cool blue-teal)
 */
const CHANGE_STOPS: [number, RGBA][] = [
  [0.0, [200, 40, 40, 220]],
  [0.2, [230, 100, 70, 200]],
  [0.4, [240, 180, 150, 160]],
  [0.5, [180, 180, 180, 100]],
  [0.6, [140, 200, 220, 160]],
  [0.8, [60, 160, 220, 200]],
  [1.0, [20, 100, 200, 220]],
];

/** Map a raw delta (−1 to +1) to 0–1 for the diverging ramp. */
const normaliseDelta = (d: number): number =>
  Math.max(0, Math.min(1, 0.5 + d));

export const projectionChangeColor = (delta: number): RGBA =>
  fromStops(normaliseDelta(delta), CHANGE_STOPS);

/* ── Traffic density (blue → orange → red) ───────────────── */

const TRAFFIC_DENSITY_STOPS: [number, RGBA][] = [
  [0.0, [30, 60, 120, 100]],
  [0.15, [50, 120, 200, 160]],
  [0.35, [80, 180, 220, 180]],
  [0.55, [255, 200, 80, 200]],
  [0.75, [255, 120, 40, 210]],
  [1.0, [200, 20, 20, 230]],
];

/** Colour for vessel density (normalised 0–1). */
export const trafficDensityColor = (t: number): RGBA =>
  fromStops(t, TRAFFIC_DENSITY_STOPS);

/** Speed lethality ramp (green → yellow → red). */
const LETHALITY_STOPS: [number, RGBA][] = [
  [0.0, [40, 160, 80, 140]],
  [0.3, [180, 220, 60, 180]],
  [0.6, [255, 180, 40, 200]],
  [0.8, [240, 80, 30, 220]],
  [1.0, [180, 10, 10, 240]],
];

export const lethalityColor = (v: number): RGBA =>
  fromStops(v, LETHALITY_STOPS);

/** Night traffic ramp (dark blue → purple → magenta). */
const NIGHT_STOPS: [number, RGBA][] = [
  [0.0, [20, 20, 60, 100]],
  [0.3, [40, 40, 140, 160]],
  [0.6, [100, 40, 180, 200]],
  [0.8, [180, 40, 160, 220]],
  [1.0, [240, 60, 120, 240]],
];

export const nightTrafficColor = (v: number): RGBA =>
  fromStops(v, NIGHT_STOPS);

/**
 * Map a traffic metric enum to the raw field name, normalisation
 * divisor, and colour function.
 */
export function getTrafficMetricConfig(metric: TrafficMetric): {
  field: string;
  maxVal: number;
  colorFn: (v: number) => RGBA;
  label: string;
} {
  switch (metric) {
    case "speed_lethality":
      return {
        field: "avg_speed_lethality",
        maxVal: 1,
        colorFn: lethalityColor,
        label: "Speed Lethality",
      };
    case "high_speed":
      return {
        field: "avg_high_speed_fraction",
        maxVal: 1,
        colorFn: lethalityColor,
        label: "High-Speed Fraction",
      };
    case "draft_risk":
      return {
        field: "avg_draft_risk_fraction",
        maxVal: 1,
        colorFn: (v) => trafficDensityColor(v),
        label: "Draft Risk",
      };
    case "night_traffic":
      return {
        field: "night_traffic_ratio",
        maxVal: 1,
        colorFn: nightTrafficColor,
        label: "Night Traffic",
      };
    case "commercial":
      return {
        field: "avg_commercial_vessels",
        maxVal: 50,
        colorFn: (v) => trafficDensityColor(v),
        label: "Commercial Ships",
      };
    case "vessel_density":
    default:
      return {
        field: "avg_monthly_vessels",
        maxVal: 200,
        colorFn: (v) => trafficDensityColor(v),
        label: "Vessel Density",
      };
  }
}

/* ── Generic dispatcher — layer name → colour function ───── */

export type LayerColorFn = (d: Record<string, unknown>) => RGBA;

export function getColorForLayer(
  layer: string,
  species?: IsdmSpecies | null,
  projectionMode?: ProjectionMode | null,
  sdmTimePeriod?: string | null,
): LayerColorFn {
  switch (layer) {
    case "none":
      return () => [0, 0, 0, 0];
    case "risk":
      return (d) => riskColor((d.risk_score as number) ?? 0);
    case "risk_ml": {
      const isRiskProj = sdmTimePeriod && sdmTimePeriod !== "current";
      if (isRiskProj && projectionMode === "change") {
        return (d) =>
          projectionChangeColor((d.delta_risk_score as number) ?? 0);
      }
      return (d) => riskColor((d.risk_score as number) ?? 0);
    }
    case "bathymetry":
      return (d) => bathymetryColor((d.depth_m as number) ?? 0);
    case "ocean":
      return (d) => sstColor((d.sst as number) ?? 15);
    case "whale_predictions": {
      const isProjection = sdmTimePeriod && sdmTimePeriod !== "current";
      if (isProjection && projectionMode === "change") {
        if (species) {
          const deltaCol = `delta_${species}`;
          return (d) =>
            projectionChangeColor((d[deltaCol] as number) ?? 0);
        }
        return (d) =>
          projectionChangeColor(
            (d.delta_any_whale as number) ?? 0,
          );
      }
      if (isProjection) {
        if (species) {
          const projCol = `isdm_${species}`;
          return (d) =>
            projectionProbColor((d[projCol] as number) ?? 0);
        }
        return (d) =>
          projectionProbColor((d.isdm_any_whale as number) ?? 0);
      }
      // Current ISDM predictions
      if (species) {
        const col = `isdm_${species}`;
        return (d) =>
          speciesProbColor(species, (d[col] as number) ?? 0);
      }
      return (d) => whaleProbColor((d.any_whale_prob as number) ?? 0);
    }
    case "sdm": {
      const isProjection = sdmTimePeriod && sdmTimePeriod !== "current";
      if (isProjection && projectionMode === "change") {
        if (species) {
          const deltaCol = `delta_${species}`;
          return (d) =>
            projectionChangeColor((d[deltaCol] as number) ?? 0);
        }
        return (d) =>
          projectionChangeColor(
            (d.delta_any_whale as number) ?? 0,
          );
      }
      if (isProjection) {
        if (species) {
          const projCol = `sdm_${species}`;
          return (d) =>
            projectionProbColor((d[projCol] as number) ?? 0);
        }
        return (d) =>
          projectionProbColor((d.sdm_any_whale as number) ?? 0);
      }
      // Current SDM predictions
      if (species) {
        const sdmCol = `sdm_${species}`;
        return (d) =>
          speciesProbColor(species, (d[sdmCol] as number) ?? 0);
      }
      return (d) => whaleProbColor((d.sdm_any_whale as number) ?? 0);
    }
    case "cetacean_density":
      return (d) =>
        whaleProbColor(
          Math.min(((d.total_sightings as number) ?? 0) / 50, 1),
        );
    case "strike_density":
      return (d) =>
        riskColor(
          Math.min(((d.total_strikes as number) ?? 0) / 5, 1),
        );
    case "traffic_density":
      return (d) =>
        trafficDensityColor(
          Math.min(
            ((d.avg_monthly_vessels as number) ?? 0) / 200,
            1,
          ),
        );
    default:
      return () => [100, 100, 100, 150];
  }
}

/* ── Legend helpers ───────────────────────────────────────── */

export interface LegendStop {
  label: string;
  color: string;
}

export function getLegendStops(
  layer: string,
  species?: IsdmSpecies | null,
  oceanMetric?: OceanMetric | null,
  projectionMode?: ProjectionMode | null,
  sdmTimePeriod?: string | null,
): LegendStop[] {
  switch (layer) {
    case "none":
      return [];
    case "risk":
      return [
        { label: "Minimal", color: "rgb(33,102,172)" },
        { label: "Low", color: "rgb(103,169,207)" },
        { label: "Medium", color: "rgb(253,219,199)" },
        { label: "High", color: "rgb(239,138,98)" },
        { label: "Critical", color: "rgb(178,24,43)" },
      ];
    case "risk_ml": {
      const isRiskProj = sdmTimePeriod && sdmTimePeriod !== "current";
      if (isRiskProj && projectionMode === "change") {
        return [
          { label: "−Risk", color: "rgb(33,102,172)" },
          { label: "No change", color: "rgb(220,220,220)" },
          { label: "+Risk", color: "rgb(178,24,43)" },
        ];
      }
      return [
        { label: "Minimal", color: "rgb(33,102,172)" },
        { label: "Low", color: "rgb(103,169,207)" },
        { label: "Medium", color: "rgb(253,219,199)" },
        { label: "High", color: "rgb(239,138,98)" },
        { label: "Critical", color: "rgb(178,24,43)" },
      ];
    }
    case "bathymetry":
      return [
        { label: "Shallow", color: "rgb(200,220,240)" },
        { label: "Shelf", color: "rgb(120,170,220)" },
        { label: "Slope", color: "rgb(50,100,180)" },
        { label: "Deep", color: "rgb(5,20,80)" },
      ];
    case "ocean": {
      const isOcnProj = sdmTimePeriod && sdmTimePeriod !== "current";
      if (isOcnProj && projectionMode === "change") {
        return [
          { label: "Decrease", color: "rgb(200,40,40)" },
          { label: "−Small", color: "rgb(230,100,70)" },
          { label: "No change", color: "rgb(180,180,180)" },
          { label: "+Small", color: "rgb(60,160,220)" },
          { label: "Increase", color: "rgb(20,100,200)" },
        ];
      }
      switch (oceanMetric) {
        case "sst_sd":
          return [
            { label: "0 °C", color: "rgb(60,180,100)" },
            { label: "1.5 °C", color: "rgb(140,210,100)" },
            { label: "3 °C", color: "rgb(240,220,80)" },
            { label: "5 °C", color: "rgb(200,40,20)" },
          ];
        case "mld":
          return [
            { label: "0 m", color: "rgb(180,230,240)" },
            { label: "50 m", color: "rgb(80,180,220)" },
            { label: "100 m", color: "rgb(40,120,200)" },
            { label: "200 m", color: "rgb(10,20,100)" },
          ];
        case "sla":
          return [
            { label: "−0.5 m", color: "rgb(33,80,172)" },
            { label: "0 m", color: "rgb(230,230,230)" },
            { label: "+0.5 m", color: "rgb(178,24,43)" },
          ];
        case "pp_upper_200m":
          return [
            { label: "0", color: "rgb(230,240,220)" },
            { label: "500", color: "rgb(140,200,80)" },
            { label: "1000", color: "rgb(60,160,40)" },
            { label: "2000", color: "rgb(5,60,5)" },
          ];
        case "sst":
        default:
          return [
            { label: "0 °C", color: "rgb(33,102,172)" },
            { label: "10 °C", color: "rgb(103,169,207)" },
            { label: "20 °C", color: "rgb(255,237,160)" },
            { label: "30 °C", color: "rgb(178,24,43)" },
          ];
      }
    }
    case "whale_predictions": {
      const isProj = sdmTimePeriod && sdmTimePeriod !== "current";
      if (isProj && projectionMode === "change") {
        return [
          { label: "Loss", color: "rgb(200,40,40)" },
          { label: "−Small", color: "rgb(230,100,70)" },
          { label: "None", color: "rgb(180,180,180)" },
          { label: "+Small", color: "rgb(60,160,220)" },
          { label: "Gain", color: "rgb(20,100,200)" },
        ];
      }
      if (isProj) {
        return [
          { label: "Low", color: "rgb(255,200,80)" },
          { label: "Medium", color: "rgb(255,150,40)" },
          { label: "High", color: "rgb(220,80,20)" },
          { label: "Very High", color: "rgb(160,20,10)" },
        ];
      }
      if (species === "blue_whale") {
        return [
          { label: "Low", color: "rgb(80,130,220)" },
          { label: "Medium", color: "rgb(40,80,200)" },
          { label: "High", color: "rgb(10,10,140)" },
        ];
      }
      if (species === "fin_whale") {
        return [
          { label: "Low", color: "rgb(170,120,80)" },
          { label: "Medium", color: "rgb(140,80,40)" },
          { label: "High", color: "rgb(80,30,10)" },
        ];
      }
      if (species === "humpback_whale") {
        return [
          { label: "Low", color: "rgb(80,180,80)" },
          { label: "Medium", color: "rgb(40,150,40)" },
          { label: "High", color: "rgb(10,80,10)" },
        ];
      }
      if (species === "sperm_whale") {
        return [
          { label: "Low", color: "rgb(140,140,140)" },
          { label: "Medium", color: "rgb(100,100,100)" },
          { label: "High", color: "rgb(30,30,30)" },
        ];
      }
      return [
        { label: "Low", color: "rgb(100,200,100)" },
        { label: "Medium", color: "rgb(255,255,100)" },
        { label: "High", color: "rgb(200,0,0)" },
      ];
    }
    case "sdm": {
      const isProj = sdmTimePeriod && sdmTimePeriod !== "current";
      if (isProj && projectionMode === "change") {
        return [
          { label: "Loss", color: "rgb(200,40,40)" },
          { label: "−Small", color: "rgb(230,100,70)" },
          { label: "None", color: "rgb(180,180,180)" },
          { label: "+Small", color: "rgb(60,160,220)" },
          { label: "Gain", color: "rgb(20,100,200)" },
        ];
      }
      if (isProj) {
        return [
          { label: "Low", color: "rgb(255,200,80)" },
          { label: "Medium", color: "rgb(255,150,40)" },
          { label: "High", color: "rgb(220,80,20)" },
          { label: "Very High", color: "rgb(160,20,10)" },
        ];
      }
      if (species === "blue_whale") {
        return [
          { label: "Low", color: "rgb(80,130,220)" },
          { label: "Medium", color: "rgb(40,80,200)" },
          { label: "High", color: "rgb(10,10,140)" },
        ];
      }
      if (species === "fin_whale") {
        return [
          { label: "Low", color: "rgb(170,120,80)" },
          { label: "Medium", color: "rgb(140,80,40)" },
          { label: "High", color: "rgb(80,30,10)" },
        ];
      }
      if (species === "humpback_whale") {
        return [
          { label: "Low", color: "rgb(80,180,80)" },
          { label: "Medium", color: "rgb(40,150,40)" },
          { label: "High", color: "rgb(10,80,10)" },
        ];
      }
      if (species === "sperm_whale") {
        return [
          { label: "Low", color: "rgb(140,140,140)" },
          { label: "Medium", color: "rgb(100,100,100)" },
          { label: "High", color: "rgb(30,30,30)" },
        ];
      }
      return [
        { label: "Low", color: "rgb(100,200,100)" },
        { label: "Medium", color: "rgb(255,255,100)" },
        { label: "High", color: "rgb(200,0,0)" },
      ];
    }
    case "cetacean_density":
      return [
        { label: "Low", color: "rgb(100,200,100)" },
        { label: "Medium", color: "rgb(255,255,100)" },
        { label: "High", color: "rgb(200,0,0)" },
      ];
    case "strike_density":
      return [
        { label: "None", color: "rgb(33,102,172)" },
        { label: "Few", color: "rgb(253,219,199)" },
        { label: "Many", color: "rgb(178,24,43)" },
      ];
    case "traffic_density":
      return [
        { label: "Low", color: "rgb(50,120,200)" },
        { label: "Medium", color: "rgb(255,200,80)" },
        { label: "High", color: "rgb(255,120,40)" },
        { label: "Extreme", color: "rgb(200,20,20)" },
      ];
    default:
      return [
        { label: "Low", color: "rgb(33,102,172)" },
        { label: "High", color: "rgb(178,24,43)" },
      ];
  }
}

/* ── Heatmap colour ranges (deck.gl HeatmapLayer) ────────── */

/** Risk heatmap: blue → yellow → red. */
export const HEATMAP_RISK: RGB[] = [
  [33, 102, 172],
  [103, 169, 207],
  [255, 237, 160],
  [239, 138, 98],
  [178, 24, 43],
];

/** SST heatmap: cold blue → warm red. */
export const HEATMAP_SST: RGB[] = [
  [33, 102, 172],
  [103, 169, 207],
  [255, 237, 160],
  [239, 138, 98],
  [178, 24, 43],
];

/** MLD heatmap: light cyan → dark blue. */
export const HEATMAP_MLD: RGB[] = [
  [180, 230, 240],
  [80, 180, 220],
  [40, 120, 200],
  [20, 60, 160],
  [10, 20, 100],
];

/** SLA heatmap: blue → white → red (diverging). */
export const HEATMAP_SLA: RGB[] = [
  [33, 80, 172],
  [100, 140, 210],
  [230, 230, 230],
  [230, 120, 80],
  [178, 24, 43],
];

/** SST SD heatmap: green → yellow → red. */
export const HEATMAP_SST_SD: RGB[] = [
  [60, 180, 100],
  [140, 210, 100],
  [240, 220, 80],
  [240, 140, 40],
  [200, 40, 20],
];

/** PP heatmap: pale → green → dark green. */
export const HEATMAP_PP: RGB[] = [
  [230, 240, 220],
  [140, 200, 80],
  [60, 160, 40],
  [20, 120, 20],
  [5, 60, 5],
];

/** Whale probability heatmap: transparent → green → red. */
export const HEATMAP_WHALE: RGB[] = [
  [200, 200, 200],
  [100, 200, 100],
  [255, 255, 100],
  [255, 100, 50],
  [200, 0, 0],
];

/** Climate projection heatmap: warm amber → deep orange → crimson. */
export const HEATMAP_PROJECTION: RGB[] = [
  [200, 200, 180],
  [255, 200, 80],
  [255, 150, 40],
  [220, 80, 20],
  [160, 20, 10],
];

/** Interaction density heatmap: green → yellow → red. */
export const HEATMAP_DENSITY: RGB[] = [
  [40, 100, 40],
  [100, 200, 100],
  [255, 255, 100],
  [255, 100, 50],
  [200, 0, 0],
];

/** Traffic heatmap: blue → orange → red. */
export const HEATMAP_TRAFFIC: RGB[] = [
  [33, 80, 130],
  [60, 130, 200],
  [255, 200, 80],
  [255, 120, 40],
  [200, 20, 20],
];

/** Lethality / high-speed heatmap: green → yellow → red. */
export const HEATMAP_LETHALITY: RGB[] = [
  [40, 160, 80],
  [180, 220, 60],
  [255, 200, 80],
  [240, 80, 30],
  [180, 10, 10],
];

/** Night traffic heatmap: dark blue → purple → magenta. */
export const HEATMAP_NIGHT: RGB[] = [
  [20, 20, 60],
  [40, 40, 140],
  [100, 40, 180],
  [180, 40, 160],
  [240, 60, 120],
];

/** Diverging heatmap for projection change: red → grey → blue. */
export const HEATMAP_CHANGE: RGB[] = [
  [200, 40, 40],
  [230, 100, 70],
  [180, 180, 180],
  [60, 160, 220],
  [20, 100, 200],
];

/**
 * Select the right heatmap colorRange for a given layer.
 */
export function getHeatmapColorRange(
  layer: LayerType,
  trafficMetric?: TrafficMetric | null,
  oceanMetric?: OceanMetric | null,
  projectionMode?: ProjectionMode | null,
  sdmTimePeriod?: string | null,
): RGB[] {
  switch (layer) {
    case "none":
      return HEATMAP_RISK; // not rendered; placeholder
    case "risk":
    case "strike_density":
      return HEATMAP_RISK;
    case "risk_ml": {
      const isP = sdmTimePeriod && sdmTimePeriod !== "current";
      return isP && projectionMode === "change"
        ? HEATMAP_CHANGE
        : HEATMAP_RISK;
    }
    case "ocean": {
      const isOceanP = sdmTimePeriod && sdmTimePeriod !== "current";
      if (isOceanP && projectionMode === "change") return HEATMAP_CHANGE;
      switch (oceanMetric) {
        case "mld":
          return HEATMAP_MLD;
        case "sla":
          return HEATMAP_SLA;
        case "sst_sd":
          return HEATMAP_SST_SD;
        case "pp_upper_200m":
          return HEATMAP_PP;
        case "sst":
        default:
          return HEATMAP_SST;
      }
    }
    case "whale_predictions":
      return HEATMAP_WHALE;
    case "sdm":
      return projectionMode === "change"
        ? HEATMAP_CHANGE
        : HEATMAP_WHALE;
    case "cetacean_density":
      return HEATMAP_DENSITY;
    case "bathymetry":
      return [
        [200, 220, 240],
        [120, 170, 220],
        [50, 100, 180],
        [20, 50, 130],
        [5, 20, 80],
      ];
    case "traffic_density":
      if (
        trafficMetric === "speed_lethality" ||
        trafficMetric === "high_speed"
      )
        return HEATMAP_LETHALITY;
      if (trafficMetric === "night_traffic")
        return HEATMAP_NIGHT;
      return HEATMAP_TRAFFIC;
    default:
      return HEATMAP_TRAFFIC;
  }
}

/**
 * Which MacroCell field drives the heatmap weight for each layer.
 */
export function getMacroWeightField(
  layer: LayerType,
  species?: IsdmSpecies | null,
  trafficMetric?: TrafficMetric | null,
  oceanMetric?: OceanMetric | null,
): string {
  switch (layer) {
    case "none":
      return "";
    case "risk":
      return "risk_score";
    case "risk_ml":
      return "ml_risk_score";
    case "ocean":
      return oceanMetric ?? "sst";
    case "whale_predictions":
      if (species) return `isdm_${species}`;
      return "any_whale_prob";
    case "sdm":
      if (species) return `sdm_${species}`;
      return "sdm_any_whale";
    case "bathymetry":
      return "depth_m_mean";
    case "cetacean_density":
      return "total_sightings";
    case "strike_density":
      return "total_strikes";
    case "traffic_density":
      switch (trafficMetric) {
        case "speed_lethality":
          return "avg_speed_lethality";
        case "high_speed":
          return "avg_high_speed_fraction";
        case "draft_risk":
          return "avg_draft_risk_fraction";
        case "night_traffic":
          return "night_traffic_ratio";
        case "commercial":
          return "avg_commercial_vessels";
        case "vessel_density":
        default:
          return "avg_monthly_vessels";
      }
    default:
      return "traffic_score";
  }
}

/* ── Contour line colours ────────────────────────────────── */

/** Colour for a bathymetry contour line by depth. */
export function contourLineColor(
  depthM: number,
  style: string,
): RGBA {
  const alpha = style === "major" ? 200 : 120;
  if (depthM <= 100) return [160, 210, 255, alpha];
  if (depthM <= 200) return [100, 180, 240, alpha];
  if (depthM <= 500) return [60, 140, 210, alpha];
  if (depthM <= 1000) return [30, 100, 180, alpha];
  if (depthM <= 2000) return [15, 60, 140, alpha];
  return [5, 30, 100, alpha];
}
