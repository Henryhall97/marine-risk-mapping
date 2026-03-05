/* ── Shared TypeScript types for the frontend ──────────────── */

/** Map view mode: detail (hex tiles) vs overview (macro heatmap). */
export type ViewMode = "detail" | "overview";

/** Bounding box for spatial API queries. */
export interface BBox {
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
}

/** Selectable data layer identifiers. */
export type LayerType =
  | "risk"
  | "risk_ml"
  | "bathymetry"
  | "ocean"
  | "whale_predictions"
  | "sdm_predictions"
  | "cetacean_density"
  | "strike_density"
  | "traffic_density";

/** Season options — null = annual mean, "all" = all four. */
export type Season =
  | "winter"
  | "spring"
  | "summer"
  | "fall"
  | "all"
  | null;

/** ISDM species that the whale_predictions API accepts. */
export type IsdmSpecies =
  | "blue_whale"
  | "fin_whale"
  | "humpback_whale"
  | "sperm_whale";

/** Traffic danger metric for colouring hex cells. */
export type TrafficMetric =
  | "vessel_density"
  | "speed_lethality"
  | "high_speed"
  | "draft_risk"
  | "night_traffic"
  | "commercial";

/** Which polygon overlay types are visible. */
export interface OverlayToggles {
  activeSMAs: boolean;
  proposedZones: boolean;
  mpas: boolean;
}

/* ── Row types returned from API (after h3 enrichment) ───── */

export interface HexCell {
  h3: string; // H3 string index (computed client-side from lat/lon)
  cell_lat: number;
  cell_lon: number;
}

export interface RiskCell extends HexCell {
  risk_score: number;
  risk_category: string;
  traffic_score: number;
  cetacean_score: number;
  strike_score: number;
  habitat_score: number;
  proximity_score: number;
  protection_gap_score: number;
  reference_risk_score: number;
}

export interface BathymetryCell extends HexCell {
  depth_m: number;
  depth_zone: string;
  is_continental_shelf: boolean;
  is_shelf_edge: boolean;
  is_land: boolean;
}

export interface OceanCell extends HexCell {
  season: string | null;
  sst: number | null;
  sst_sd: number | null;
  mld: number | null;
  sla: number | null;
  pp_upper_200m: number | null;
}

export interface WhalePredictionCell extends HexCell {
  season: string;
  any_whale_prob: number;
  isdm_blue_whale: number;
  isdm_fin_whale: number;
  isdm_humpback_whale: number;
  isdm_sperm_whale: number;
}

export interface SdmPredictionCell extends HexCell {
  season: string;
  sdm_any_whale: number;
  sdm_blue_whale: number;
  sdm_fin_whale: number;
  sdm_humpback_whale: number;
  sdm_sperm_whale: number;
  any_whale_prob_joint: number;
}

export interface SpeedZone {
  zone_name: string;
  /** Tagged client-side: which API endpoint this came from. */
  source: "current" | "proposed";
  start_month: number;
  start_day: number;
  end_month: number;
  end_day: number;
  /** Whether the zone is seasonally active on the requested date. */
  is_active: boolean;
  season_label: string;
  geometry: GeoJSON.Geometry;
}

export interface MPA {
  mpa_name: string;
  protection_level: string | null;
  geometry: GeoJSON.Geometry;
}

/** Paginated API response wrapper. */
export interface PaginatedResponse<T> {
  total: number;
  offset: number;
  limit: number;
  data: T[];
}
