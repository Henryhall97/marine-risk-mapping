"use client";

import {
  useState,
  useCallback,
  useMemo,
  useEffect,
  useRef,
} from "react";
import DeckGL from "@deck.gl/react";
import { Map, type MapRef } from "react-map-gl/maplibre";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import "maplibre-gl/dist/maplibre-gl.css";

import { INITIAL_VIEW_STATE, MAP_STYLE, MAX_BBOX_AREA_DEG2 } from "@/lib/config";
import {
  getColorForLayer,
  getHeatmapColorRange,
  getMacroWeightField,
  contourLineColor,
  getTrafficMetricConfig,
  getOceanMetricConfig,
  projectionChangeColor,
} from "@/lib/colors";
import { fetchSpeedZones, fetchMPAs, fetchBIAs, fetchCriticalHabitat, fetchShippingLanes, fetchSlowZones, fetchMapSightings, fetchCellDetail, bboxArea } from "@/lib/api";
import { useMapData } from "@/hooks/useMapData";
import { useMacroData, useContourData } from "@/hooks/useMacroData";
import Sidebar from "./Sidebar";
import CellDetail from "./CellDetail";
import ZoneDetail from "./ZoneDetail";
import type { ZoneInfo } from "./ZoneDetail";
import Legend from "./Legend";
import SlowZoneWarning from "./SlowZoneWarning";
import CheckMyRisk from "./CheckMyRisk";
import type {
  BBox,
  LayerType,
  Season,
  SpeedZone,
  MPA,
  BIA,
  CriticalHabitatZone,
  ShippingLane,
  SlowZone,
  MapSighting,
  IsdmSpecies,
  OverlayToggles,
  ViewMode,
  TrafficMetric,
  OceanMetric,
  SightingColorBy,
  SightingStatusFilter,
  ClimateScenario,
  SdmTimePeriod,
  ProjectionMode,
} from "@/lib/types";

/* ── Types ───────────────────────────────────────────────── */

type ViewState = {
  latitude: number;
  longitude: number;
  zoom: number;
  bearing: number;
  pitch: number;
};

/* ── Helpers ─────────────────────────────────────────────── */

/** Rough bbox from deck.gl viewState. */
function viewStateToBbox(vs: ViewState): BBox {
  const latSpan = 180 / Math.pow(2, vs.zoom);
  const lonSpan = 360 / Math.pow(2, vs.zoom);
  return {
    lat_min: Math.max(-90, vs.latitude - latSpan / 2),
    lat_max: Math.min(90, vs.latitude + latSpan / 2),
    lon_min: Math.max(-180, vs.longitude - lonSpan / 2),
    lon_max: Math.min(180, vs.longitude + lonSpan / 2),
  };
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

const DEFAULT_OVERLAYS: OverlayToggles = {
  activeSMAs: true,
  proposedZones: false,
  mpas: false,
  bias: false,
  criticalHabitat: false,
  shippingLanes: false,
  slowZones: false,
  communitySightings: false,
};

/* ── Sighting marker colours ─────────────────────────────── */

const SIGHTING_SPECIES_COLORS: Record<string, [number, number, number]> = {
  humpback_whale: [56, 189, 248],
  right_whale: [248, 113, 113],
  fin_whale: [251, 191, 36],
  blue_whale: [96, 165, 250],
  minke_whale: [167, 139, 250],
  sperm_whale: [244, 114, 182],
  sei_whale: [52, 211, 153],
  killer_whale: [251, 146, 60],
};

const SIGHTING_VERIFICATION_COLORS: Record<string, [number, number, number]> = {
  verified: [74, 222, 128],
  community_verified: [134, 239, 172],
  unverified: [156, 163, 175],
  under_review: [250, 204, 21],
  disputed: [251, 146, 60],
  rejected: [248, 113, 113],
};

const SIGHTING_DEFAULT_COLOR: [number, number, number] = [156, 163, 175];

function sightingColor(
  d: MapSighting,
  colorBy: SightingColorBy,
): [number, number, number, number] {
  if (colorBy === "species") {
    const c = SIGHTING_SPECIES_COLORS[d.species ?? ""] ?? SIGHTING_DEFAULT_COLOR;
    return [...c, 210];
  }
  if (colorBy === "verification") {
    const c = SIGHTING_VERIFICATION_COLORS[d.verification_status] ?? SIGHTING_DEFAULT_COLOR;
    return [...c, 210];
  }
  // interaction
  const interColors: Record<string, [number, number, number]> = {
    visual_sighting: [56, 189, 248],
    acoustic_detection: [167, 139, 250],
    vessel_interaction: [248, 113, 113],
    stranding: [251, 146, 60],
    entanglement: [244, 114, 182],
  };
  const c = interColors[d.interaction_type ?? ""] ?? SIGHTING_DEFAULT_COLOR;
  return [...c, 210];
}

/* ── Main component ──────────────────────────────────────── */

export interface MapViewProps {
  /** Override initial latitude. */
  initialLat?: number;
  /** Override initial longitude. */
  initialLon?: number;
  /** Override initial zoom level. */
  initialZoom?: number;
  /** Override initial layer. */
  initialLayer?: LayerType;
  /** Override initial season. */
  initialSeason?: Season;
  /** Open the "Check My Risk" panel on mount. */
  initialCheckRisk?: boolean;
  /** Override which overlays are enabled on mount. */
  initialOverlays?: Partial<OverlayToggles>;
  /** Override the traffic density metric on mount. */
  initialTrafficMetric?: TrafficMetric;
}

export default function MapView({
  initialLat,
  initialLon,
  initialZoom,
  initialLayer,
  initialSeason,
  initialCheckRisk,
  initialOverlays,
  initialTrafficMetric,
}: MapViewProps = {}) {
  /*
   * Defer DeckGL mount until after the first browser paint.
   * luma.gl 9 reads device.limits.maxTextureDimension2D synchronously
   * on mount — if the WebGL context isn't ready yet, it crashes.
   * A double-rAF ensures the canvas element exists and the GPU
   * device has been initialised before DeckGL tries to use it.
   */
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const raf1 = requestAnimationFrame(() => {
      const raf2 = requestAnimationFrame(() => setMounted(true));
      return () => cancelAnimationFrame(raf2);
    });
    return () => cancelAnimationFrame(raf1);
  }, []);

  /* ── State ── */
  const [viewState, setViewState] = useState<ViewState>({
    ...INITIAL_VIEW_STATE,
    ...(initialLat != null && { latitude: initialLat }),
    ...(initialLon != null && { longitude: initialLon }),
    ...(initialZoom != null && { zoom: initialZoom }),
  });
  const [viewMode, setViewMode] = useState<ViewMode>(
    initialZoom != null && initialZoom >= 7 ? "detail" : "overview",
  );
  const [activeLayer, setActiveLayer] = useState<LayerType>(
    initialLayer ?? "risk",
  );
  const [season, setSeason] = useState<Season>(initialSeason ?? null);
  const [selectedSpecies, setSelectedSpecies] =
    useState<IsdmSpecies | null>(null);
  const [climateScenario, setClimateScenario] =
    useState<ClimateScenario>("ssp245");
  const [sdmTimePeriod, setSdmTimePeriod] =
    useState<SdmTimePeriod>("current");
  const [projectionMode, setProjectionMode] =
    useState<ProjectionMode>("absolute");
  const [trafficMetric, setTrafficMetric] =
    useState<TrafficMetric>(initialTrafficMetric ?? "vessel_density");
  const [oceanMetric, setOceanMetric] =
    useState<OceanMetric>("sst");
  const [selectedCell, setSelectedCell] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [cellDetail, setCellDetail] = useState<Record<
    string,
    unknown
  > | null>(null);

  // Zone detail panel (clicked GeoJSON feature)
  const [selectedZone, setSelectedZone] = useState<ZoneInfo | null>(null);

  // Overlay toggles
  const [overlays, setOverlays] =
    useState<OverlayToggles>(
      initialOverlays
        ? { ...DEFAULT_OVERLAYS, ...initialOverlays }
        : DEFAULT_OVERLAYS,
    );
  const [activeDate, setActiveDate] = useState(todayISO());
  const [speedZones, setSpeedZones] = useState<SpeedZone[]>([]);
  const [mpas, setMpas] = useState<MPA[]>([]);
  const [bias, setBias] = useState<BIA[]>([]);
  const [criticalHabitat, setCriticalHabitat] = useState<CriticalHabitatZone[]>([]);
  const [shippingLanes, setShippingLanes] = useState<ShippingLane[]>([]);
  const [slowZones, setSlowZones] = useState<SlowZone[]>([]);
  const [showContours, setShowContours] = useState(true);

  // Community sightings overlay
  const [sightings, setSightings] = useState<MapSighting[]>([]);
  const [sightingColorBy, setSightingColorBy] =
    useState<SightingColorBy>("species");
  const [sightingSpeciesFilter, setSightingSpeciesFilter] =
    useState<string | null>(null);
  const [sightingStatusFilter, setSightingStatusFilter] =
    useState<SightingStatusFilter>("all");

  // First-visit hint — persists per session so it reappears on refresh
  const [showMapHint, setShowMapHint] = useState(false);
  useEffect(() => {
    if (typeof window !== "undefined" && !sessionStorage.getItem("mw_map_hint_dismissed")) {
      setShowMapHint(true);
    }
  }, []);
  function dismissMapHint() {
    sessionStorage.setItem("mw_map_hint_dismissed", "1");
    setShowMapHint(false);
  }

  // Check My Risk panel
  const [showCheckRisk, setShowCheckRisk] =
    useState(initialCheckRisk ?? false);
  const [checkRiskMarker, setCheckRiskMarker] =
    useState<{ lat: number; lon: number } | null>(null);
  const [checkRiskCellMarker, setCheckRiskCellMarker] =
    useState<{ lat: number; lon: number } | null>(null);

  const mapRef = useRef<MapRef>(null);

  /* ── Bbox from viewport ── */
  const bbox = useMemo(
    () => viewStateToBbox(viewState),
    [viewState],
  );

  /* ── Hex data from active layer (detail mode) ── */
  const {
    data: hexData,
    total: hexTotal,
    loading: hexLoading,
  } = useMapData(bbox, activeLayer, season, selectedSpecies, climateScenario, sdmTimePeriod, projectionMode);

  /* ── Macro data (overview mode) — includes projections ── */
  const {
    data: macroData,
    loading: macroLoading,
    total: macroTotal,
  } = useMacroData(
    viewMode === "overview" ? season : undefined,
    climateScenario,
    sdmTimePeriod,
  );

  const { data: contourData } = useContourData();

  // Pick the right loading / total for the status bar
  const isOverview = viewMode === "overview";
  const total = isOverview ? macroTotal : hexTotal;
  const loading = isOverview ? macroLoading : hexLoading;

  /* ── Speed zone overlay ── */
  useEffect(() => {
    const wantSMAs = overlays.activeSMAs;
    const wantProposed = overlays.proposedZones;
    if (!wantSMAs && !wantProposed) {
      setSpeedZones([]);
      return;
    }
    const controller = new AbortController();
    const fetches: Promise<{ data: SpeedZone[] }>[] = [];
    if (wantSMAs) {
      fetches.push(
        fetchSpeedZones("current", activeDate, controller.signal),
      );
    }
    if (wantProposed) {
      fetches.push(
        fetchSpeedZones("proposed", activeDate, controller.signal),
      );
    }
    Promise.all(fetches)
      .then((results) => {
        setSpeedZones(results.flatMap((r) => r.data));
      })
      .catch(() => {});
    return () => controller.abort();
  }, [overlays.activeSMAs, overlays.proposedZones, activeDate]);

  /* ── MPA overlay ── */
  useEffect(() => {
    if (!overlays.mpas) {
      setMpas([]);
      return;
    }
    // Only fetch MPAs when zoomed in enough (must fit API area limit)
    if (bboxArea(bbox) > MAX_BBOX_AREA_DEG2) {
      setMpas([]);
      return;
    }
    const controller = new AbortController();
    fetchMPAs(bbox, controller.signal)
      .then((res) => setMpas(res.data))
      .catch(() => {});
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    overlays.mpas,
    // Only re-fetch when bbox changes significantly (round to 1dp)
    Math.round(bbox.lat_min),
    Math.round(bbox.lat_max),
    Math.round(bbox.lon_min),
    Math.round(bbox.lon_max),
  ]);

  /* ── BIA overlay ── */
  useEffect(() => {
    if (!overlays.bias) {
      setBias([]);
      return;
    }
    if (bboxArea(bbox) > MAX_BBOX_AREA_DEG2) {
      setBias([]);
      return;
    }
    const controller = new AbortController();
    fetchBIAs(bbox, controller.signal)
      .then((res) => setBias(res.data))
      .catch(() => {});
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    overlays.bias,
    Math.round(bbox.lat_min),
    Math.round(bbox.lat_max),
    Math.round(bbox.lon_min),
    Math.round(bbox.lon_max),
  ]);

  /* ── Critical Habitat overlay ── */
  useEffect(() => {
    if (!overlays.criticalHabitat) {
      setCriticalHabitat([]);
      return;
    }
    const controller = new AbortController();
    fetchCriticalHabitat(controller.signal)
      .then((res) => setCriticalHabitat(res.data))
      .catch(() => {});
    return () => controller.abort();
  }, [overlays.criticalHabitat]);

  /* ── Shipping Lanes overlay ── */
  useEffect(() => {
    if (!overlays.shippingLanes) {
      setShippingLanes([]);
      return;
    }
    if (bboxArea(bbox) > MAX_BBOX_AREA_DEG2) {
      setShippingLanes([]);
      return;
    }
    const controller = new AbortController();
    fetchShippingLanes(bbox, controller.signal)
      .then((res) => setShippingLanes(res.data))
      .catch(() => {});
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    overlays.shippingLanes,
    Math.round(bbox.lat_min),
    Math.round(bbox.lat_max),
    Math.round(bbox.lon_min),
    Math.round(bbox.lon_max),
  ]);

  /* ── Slow Zones overlay ── */
  useEffect(() => {
    if (!overlays.slowZones) {
      setSlowZones([]);
      return;
    }
    const controller = new AbortController();
    fetchSlowZones(controller.signal)
      .then((res) => setSlowZones(res.data))
      .catch(() => {});
    return () => controller.abort();
  }, [overlays.slowZones]);

  /* ── Community Sightings overlay ── */
  useEffect(() => {
    if (!overlays.communitySightings) {
      setSightings([]);
      return;
    }
    const controller = new AbortController();
    const statusParam =
      sightingStatusFilter === "all" ? undefined : sightingStatusFilter;
    fetchMapSightings(
      bbox,
      {
        species: sightingSpeciesFilter ?? undefined,
        status: statusParam,
      },
      controller.signal,
    )
      .then((res) => setSightings(res.data))
      .catch(() => {});
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    overlays.communitySightings,
    sightingSpeciesFilter,
    sightingStatusFilter,
    Math.round(bbox.lat_min),
    Math.round(bbox.lat_max),
    Math.round(bbox.lon_min),
    Math.round(bbox.lon_max),
  ]);

  /* ── Re-sync selected cell when hex data refreshes (season change) ── */
  useEffect(() => {
    if (!selectedCell) return;
    const h3 = selectedCell.h3 as string;
    const match = hexData.find((c) => c.h3 === h3);
    if (match) {
      // Update cell data from fresh fetch (new season values)
      setSelectedCell(match);
      // Re-fetch full detail for risk layers
      if (activeLayer === "risk" || activeLayer === "risk_ml") {
        const h3BigInt = BigInt("0x" + h3).toString();
        fetchCellDetail(h3BigInt)
          .then(setCellDetail)
          .catch(() => setCellDetail(null));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hexData]);

  /* ── Auto-switch season when entering projection mode ── */
  const handleSdmTimePeriodChange = useCallback(
    (tp: SdmTimePeriod) => {
      setSdmTimePeriod(tp);
      // Projected data has no "annual" season — force a real season
      if (tp !== "current" && (season === null || season === "all")) {
        setSeason("winter");
      }
    },
    [season],
  );

  /* ── Clear species when leaving whale predictions ── */
  const handleLayerChange = useCallback((l: LayerType) => {
    setActiveLayer(l);
    setSelectedCell(null);
    setCellDetail(null);
    if (l !== "whale_predictions" && l !== "sdm") {
      setSelectedSpecies(null);
    }
    if (l !== "sdm" && l !== "whale_predictions" && l !== "risk_ml" && l !== "ocean") {
      setSdmTimePeriod("current");
      setProjectionMode("absolute");
    }
    if (l !== "traffic_density") {
      setTrafficMetric("vessel_density");
    }
    if (l !== "ocean") {
      setOceanMetric("sst");
    }
  }, []);

  /* ── View mode change ── */
  const handleViewModeChange = useCallback((m: ViewMode) => {
    setViewMode(m);
    setSelectedCell(null);
    setCellDetail(null);
  }, []);

  /* ── Cell click handler (detail mode only) ── */
  const handleClick = useCallback(
    (info: { object?: Record<string, unknown>; layer?: { id?: string } | null }) => {
      if (!info.object) {
        setSelectedCell(null);
        setCellDetail(null);
        setSelectedZone(null);
        return;
      }
      const obj = info.object;
      const layerId = info.layer?.id ?? "";
      const props = obj.properties as
        | Record<string, unknown>
        | undefined;

      // Zone click → open zone detail panel
      if (props && layerId) {
        // Speed zone (SMA or proposed)
        if (layerId === "speed-zones" && props.zone_name) {
          const src = props.source as string;
          setSelectedZone({
            kind: src === "proposed" ? "proposed" : "sma",
            zone_name: String(props.zone_name),
            is_active: Boolean(props.is_active),
            season_label: String(props.season_label ?? ""),
          });
          return;
        }
        // Slow zone (DMA)
        if (layerId === "slow-zones" && props.zone_name) {
          setSelectedZone({
            kind: "slow_zone",
            zone_name: String(props.zone_name),
            effective_start: (props.effective_start as string) ?? null,
            effective_end: (props.effective_end as string) ?? null,
            is_expired: (props.is_expired as boolean) ?? null,
          });
          return;
        }
        // MPA
        if (layerId === "mpas" && props.mpa_name) {
          setSelectedZone({
            kind: "mpa",
            mpa_name: String(props.mpa_name),
            protection_level: (props.protection_level as string) ?? null,
          });
          return;
        }
        // BIA
        if (layerId === "bias" && (props.bia_name || props.bia_type)) {
          setSelectedZone({
            kind: "bia",
            bia_name: (props.bia_name as string) ?? null,
            cmn_name: (props.cmn_name as string) ?? null,
            bia_type: (props.bia_type as string) ?? null,
            bia_months: (props.bia_months as string) ?? null,
          });
          return;
        }
        // Critical Habitat
        if (layerId === "critical-habitat" && props.species_label) {
          setSelectedZone({
            kind: "critical_habitat",
            species_label: String(props.species_label),
            cmn_name: (props.cmn_name as string) ?? null,
            ch_status: (props.ch_status as string) ?? null,
            is_proposed: Boolean(props.is_proposed),
          });
          return;
        }
        // Shipping lane
        if (layerId === "shipping-lanes" && (props.name || props.zone_type)) {
          setSelectedZone({
            kind: "shipping_lane",
            zone_type: String(props.zone_type ?? "Shipping Lane"),
            name: (props.name as string) ?? null,
          });
          return;
        }
        // Bathymetry contour
        if (layerId === "bathymetry-contours" && props.depth_m !== undefined) {
          setSelectedZone({
            kind: "contour",
            depth_m: Number(props.depth_m),
            style: String(props.style ?? "minor"),
          });
          return;
        }
      }

      // Default: hex cell click
      setSelectedZone(null);
      setSelectedCell(obj);
      setCellDetail(null);
      setShowCheckRisk(false);
      setCheckRiskMarker(null);
      setCheckRiskCellMarker(null);

      // Fetch full detail for risk layers
      if (activeLayer === "risk" || activeLayer === "risk_ml") {
        const h3Hex = obj.h3 as string;
        const h3BigInt = BigInt("0x" + h3Hex).toString();
        fetchCellDetail(h3BigInt)
          .then(setCellDetail)
          .catch(() => setCellDetail(null));
      }
    },
    [activeLayer],
  );

  /* ── Build deck.gl layers ── */
  const colorFn = useMemo(() => {
    if (activeLayer === "traffic_density") {
      const cfg = getTrafficMetricConfig(trafficMetric);
      return (d: Record<string, unknown>) => {
        const raw = (d[cfg.field] as number) ?? 0;
        const norm = Math.min(raw / cfg.maxVal, 1);
        return cfg.colorFn(norm);
      };
    }
    if (activeLayer === "ocean") {
      const isOceanProj = sdmTimePeriod && sdmTimePeriod !== "current";
      if (isOceanProj && projectionMode === "change") {
        // Diverging colour: delta fields (red = increase, blue = decrease)
        const deltaField = `delta_${oceanMetric === "pp_upper_200m" ? "pp" : oceanMetric}`;
        return (d: Record<string, unknown>) => {
          const delta = (d[deltaField] as number) ?? 0;
          return projectionChangeColor(delta);
        };
      }
      const cfg = getOceanMetricConfig(oceanMetric);
      return (d: Record<string, unknown>) => {
        const raw = (d[cfg.field] as number) ?? cfg.defaultVal;
        const norm = (raw - cfg.minVal) / (cfg.maxVal - cfg.minVal);
        return cfg.colorFn(Math.max(0, Math.min(norm, 1)));
      };
    }
    return getColorForLayer(
      activeLayer,
      selectedSpecies,
      projectionMode,
      sdmTimePeriod,
    );
  }, [activeLayer, selectedSpecies, trafficMetric, oceanMetric, projectionMode, sdmTimePeriod]);

  const heatmapColorRange = useMemo(
    () =>
      getHeatmapColorRange(
        activeLayer,
        trafficMetric,
        oceanMetric,
        projectionMode,
        sdmTimePeriod,
      ),
    [activeLayer, trafficMetric, oceanMetric, projectionMode, sdmTimePeriod],
  );

  const macroWeightField = useMemo(
    () =>
      getMacroWeightField(
        activeLayer,
        selectedSpecies,
        trafficMetric,
        oceanMetric,
      ),
    [activeLayer, selectedSpecies, trafficMetric, oceanMetric],
  );

  const layers = useMemo(() => {
    const result: unknown[] = [];

    if (activeLayer !== "none" && isOverview) {
      /* ── Overview: HeatmapLayer ── */
      if (macroData.length > 0) {
        result.push(
          new HeatmapLayer({
            id: "macro-heatmap",
            data: macroData,
            getPosition: (
              d: Record<string, unknown>,
            ): [number, number] => [
              d.cell_lon as number,
              d.cell_lat as number,
            ],
            getWeight: (d: Record<string, unknown>) => {
              const v = (d[macroWeightField] as number) ?? 0;
              // Normalise interaction/strike counts to 0-1 range
              if (macroWeightField === "total_sightings")
                return Math.min(v / 200, 1);
              if (macroWeightField === "total_strikes")
                return Math.min(v / 3, 1);
              // Traffic sub-metrics: vessel count needs normalising
              if (macroWeightField === "avg_monthly_vessels")
                return Math.min(v / 200, 1);
              if (macroWeightField === "avg_commercial_vessels")
                return Math.min(v / 50, 1);
              // SST: normalise to 0-30°C range
              if (macroWeightField === "sst")
                return Math.max(0, Math.min(v / 30, 1));
              // SST SD: normalise to 0-5°C range
              if (macroWeightField === "sst_sd")
                return Math.max(0, Math.min(v / 5, 1));
              // MLD: normalise to 0-200m range
              if (macroWeightField === "mld")
                return Math.max(0, Math.min(v / 200, 1));
              // SLA: normalise from -0.5..+0.5 → 0..1
              if (macroWeightField === "sla")
                return Math.max(0, Math.min((v + 0.5) / 1.0, 1));
              // PP: normalise to 0-2000 mg C/m²/day
              if (macroWeightField === "pp_upper_200m")
                return Math.max(0, Math.min(v / 2000, 1));
              // Bathymetry: normalise depth 0-6000m to 0-1
              if (macroWeightField === "depth_m_mean")
                return Math.min(Math.abs(v) / 6000, 1);
              return v;
            },
            radiusPixels: 45,
            intensity: 1.2,
            threshold: 0.04,
            colorRange: heatmapColorRange,
            updateTriggers: {
              getWeight: [macroWeightField],
            },
          }),
        );
      }

      /* ── Overview: Bathymetry contour lines ── */
      if (showContours && contourData) {
        type ContourProps = {
          properties: { depth_m: number; style: string };
        };
        result.push(
          new GeoJsonLayer({
            id: "bathymetry-contours",
            data: contourData,
            getLineColor: (f: ContourProps) =>
              contourLineColor(
                f.properties.depth_m,
                f.properties.style,
              ),
            getLineWidth: (f: ContourProps) =>
              f.properties.style === "major" ? 2 : 1,
            lineWidthMinPixels: 1,
            lineWidthMaxPixels: 3,
            pickable: true,
          }),
        );
      }
    } else if (activeLayer !== "none") {
      /* ── Detail: H3 hexagon layer ── */
      if (hexData.length > 0) {
        result.push(
          new H3HexagonLayer({
            id: "hexagons",
            data: hexData,
            getHexagon: (d: Record<string, unknown>) =>
              d.h3 as string,
            getFillColor: (d: Record<string, unknown>) =>
              colorFn(d),
            extruded: false,
            pickable: true,
            opacity: 0.75,
            updateTriggers: {
              getFillColor: [activeLayer, selectedSpecies, trafficMetric, oceanMetric, projectionMode, sdmTimePeriod],
            },
          }),
        );
      }
    }

    // Speed zone polygon overlay
    if (speedZones.length > 0) {
      const features = speedZones.map((z) => ({
        type: "Feature" as const,
        geometry: z.geometry,
        properties: {
          zone_name: z.zone_name,
          source: z.source,
          is_active: z.is_active,
          season_label: z.season_label,
        },
      }));
      type ZoneProps = {
        properties: { source: "current" | "proposed"; is_active: boolean };
      };
      result.push(
        new GeoJsonLayer({
          id: "speed-zones",
          data: { type: "FeatureCollection" as const, features },
          getFillColor: (f: ZoneProps) =>
            f.properties.source === "proposed"
              ? f.properties.is_active
                ? [255, 200, 60, 50]   // proposed + in season
                : [255, 200, 60, 20]   // proposed + off season
              : f.properties.is_active
                ? [255, 80, 80, 60]    // current SMA + in season
                : [255, 80, 80, 25],   // current SMA + off season
          getLineColor: (f: ZoneProps) =>
            f.properties.source === "proposed"
              ? f.properties.is_active
                ? [255, 200, 60, 200]  // proposed + in season
                : [255, 200, 60, 80]   // proposed + off season
              : f.properties.is_active
                ? [255, 60, 60, 220]   // current SMA + in season
                : [255, 60, 60, 70],   // current SMA + off season
          lineWidthMinPixels: 2,
          pickable: true,
        }),
      );
    }

    // MPA overlay
    if (mpas.length > 0) {
      const mpaFeatures = mpas.map((m) => ({
        type: "Feature" as const,
        geometry: m.geometry,
        properties: {
          mpa_name: m.mpa_name,
          protection_level: m.protection_level,
        },
      }));
      result.push(
        new GeoJsonLayer({
          id: "mpas",
          data: {
            type: "FeatureCollection" as const,
            features: mpaFeatures,
          },
          getFillColor: [80, 200, 120, 35],
          getLineColor: [80, 200, 120, 140],
          lineWidthMinPixels: 1,
          pickable: true,
        }),
      );
    }

    // BIA overlay
    if (bias.length > 0) {
      const biaFeatures = bias.map((b) => ({
        type: "Feature" as const,
        geometry: b.geometry,
        properties: {
          bia_name: b.bia_name,
          cmn_name: b.cmn_name,
          bia_type: b.bia_type,
          bia_months: b.bia_months,
        },
      }));
      result.push(
        new GeoJsonLayer({
          id: "bias",
          data: {
            type: "FeatureCollection" as const,
            features: biaFeatures,
          },
          getFillColor: [0, 200, 200, 40],
          getLineColor: [0, 200, 200, 160],
          lineWidthMinPixels: 2,
          pickable: true,
        }),
      );
    }

    // Critical Habitat overlay
    if (criticalHabitat.length > 0) {
      const chFeatures = criticalHabitat.map((ch) => ({
        type: "Feature" as const,
        geometry: ch.geometry,
        properties: {
          species_label: ch.species_label,
          cmn_name: ch.cmn_name,
          ch_status: ch.ch_status,
          is_proposed: ch.is_proposed,
        },
      }));
      result.push(
        new GeoJsonLayer({
          id: "critical-habitat",
          data: {
            type: "FeatureCollection" as const,
            features: chFeatures,
          },
          getFillColor: (f: { properties: { is_proposed?: boolean } }) =>
            f.properties.is_proposed
              ? [180, 80, 220, 25]
              : [180, 80, 220, 45],
          getLineColor: (f: { properties: { is_proposed?: boolean } }) =>
            f.properties.is_proposed
              ? [180, 80, 220, 100]
              : [180, 80, 220, 180],
          lineWidthMinPixels: 2,
          pickable: true,
        }),
      );
    }

    // Shipping Lanes overlay
    if (shippingLanes.length > 0) {
      const slFeatures = shippingLanes.map((sl) => ({
        type: "Feature" as const,
        geometry: sl.geometry,
        properties: {
          zone_type: sl.zone_type,
          name: sl.name,
        },
      }));
      result.push(
        new GeoJsonLayer({
          id: "shipping-lanes",
          data: {
            type: "FeatureCollection" as const,
            features: slFeatures,
          },
          getFillColor: [60, 120, 220, 35],
          getLineColor: [60, 120, 220, 160],
          lineWidthMinPixels: 2,
          pickable: true,
        }),
      );
    }

    // Slow Zones overlay
    if (slowZones.length > 0) {
      const szFeatures = slowZones.map((sz) => ({
        type: "Feature" as const,
        geometry: sz.geometry,
        properties: {
          zone_name: sz.zone_name,
          effective_start: sz.effective_start,
          effective_end: sz.effective_end,
          is_expired: sz.is_expired,
        },
      }));
      result.push(
        new GeoJsonLayer({
          id: "slow-zones",
          data: {
            type: "FeatureCollection" as const,
            features: szFeatures,
          },
          getFillColor: (f: { properties: { is_expired?: boolean } }) =>
            f.properties.is_expired
              ? [255, 140, 0, 20]
              : [255, 140, 0, 60],
          getLineColor: (f: { properties: { is_expired?: boolean } }) =>
            f.properties.is_expired
              ? [255, 140, 0, 60]
              : [255, 140, 0, 200],
          lineWidthMinPixels: 2,
          pickable: true,
        }),
      );
    }

    // Community sightings scatterplot overlay
    if (sightings.length > 0) {
      result.push(
        new ScatterplotLayer<MapSighting>({
          id: "community-sightings",
          data: sightings,
          getPosition: (d) => [d.lon, d.lat],
          getFillColor: (d) => sightingColor(d, sightingColorBy),
          getRadius: 5000,
          radiusMinPixels: 4,
          radiusMaxPixels: 14,
          radiusUnits: "meters",
          pickable: true,
          stroked: true,
          getLineColor: [255, 255, 255, 100],
          lineWidthMinPixels: 1,
          updateTriggers: {
            getFillColor: [sightingColorBy],
          },
        }),
      );
    }

    // Check My Risk location marker (pulsing pin)
    if (checkRiskMarker) {
      result.push(
        new ScatterplotLayer<{ lat: number; lon: number }>({
          id: "check-risk-marker",
          data: [checkRiskMarker],
          getPosition: (d) => [d.lon, d.lat],
          getFillColor: [56, 189, 248, 200],
          getLineColor: [255, 255, 255, 255],
          getRadius: 8,
          radiusMinPixels: 8,
          radiusMaxPixels: 16,
          radiusUnits: "pixels",
          stroked: true,
          lineWidthMinPixels: 3,
          pickable: false,
        }),
        // Outer ring for pulsing effect
        new ScatterplotLayer<{ lat: number; lon: number }>({
          id: "check-risk-marker-ring",
          data: [checkRiskMarker],
          getPosition: (d) => [d.lon, d.lat],
          getFillColor: [56, 189, 248, 0],
          getLineColor: [56, 189, 248, 120],
          getRadius: 20,
          radiusMinPixels: 18,
          radiusMaxPixels: 28,
          radiusUnits: "pixels",
          stroked: true,
          lineWidthMinPixels: 2,
          pickable: false,
        }),
      );
    }

    // Matched risk cell marker (amber) — shown when nearest ≠ query
    if (checkRiskCellMarker) {
      result.push(
        new ScatterplotLayer<{ lat: number; lon: number }>({
          id: "check-risk-cell-marker",
          data: [checkRiskCellMarker],
          getPosition: (d) => [d.lon, d.lat],
          getFillColor: [245, 158, 11, 200],
          getLineColor: [255, 255, 255, 255],
          getRadius: 8,
          radiusMinPixels: 8,
          radiusMaxPixels: 16,
          radiusUnits: "pixels",
          stroked: true,
          lineWidthMinPixels: 3,
          pickable: false,
        }),
        new ScatterplotLayer<{ lat: number; lon: number }>({
          id: "check-risk-cell-marker-ring",
          data: [checkRiskCellMarker],
          getPosition: (d) => [d.lon, d.lat],
          getFillColor: [245, 158, 11, 0],
          getLineColor: [245, 158, 11, 120],
          getRadius: 20,
          radiusMinPixels: 18,
          radiusMaxPixels: 28,
          radiusUnits: "pixels",
          stroked: true,
          lineWidthMinPixels: 2,
          pickable: false,
        }),
      );
    }

    return result;
  }, [
    isOverview,
    macroData,
    macroWeightField,
    heatmapColorRange,
    activeLayer,
    selectedSpecies,
    trafficMetric,
    oceanMetric,
    showContours,
    contourData,
    hexData,
    colorFn,
    speedZones,
    mpas,
    bias,
    criticalHabitat,
    shippingLanes,
    slowZones,
    sightings,
    sightingColorBy,
    checkRiskMarker,
    checkRiskCellMarker,
  ]);

  /* ── Tooltip ── */
  const getTooltip = useCallback(
    ({ object }: { object?: Record<string, unknown> }) => {
      if (!object) return null;

      const tooltipStyle = {
        background: "#1e293b",
        color: "#f1f5f9",
        fontSize: "13px",
        padding: "8px 12px",
        borderRadius: "6px",
      };

      // Speed zone feature
      const props = object.properties as
        | Record<string, unknown>
        | undefined;
      if (props?.zone_name && props?.source !== undefined) {
        const src = props.source === "proposed" ? "Proposed" : "Active SMA";
        const seasonal = props.is_active
          ? '<span style="color:#ef4444">●</span> In season now'
          : '<span style="color:#94a3b8">●</span> Off season';
        return {
          html:
            `<b>${props.zone_name}</b><br/>` +
            `${src} · ${props.season_label ?? ""}<br/>` +
            seasonal,
          style: tooltipStyle,
        };
      }
      // Slow Zone feature (DMA)
      if (props?.zone_name && props?.is_expired !== undefined) {
        const status = props.is_expired
          ? '<span style="color:#94a3b8">●</span> Expired'
          : '<span style="color:#f97316">●</span> Active';
        return {
          html:
            `<b>${props.zone_name}</b><br/>` +
            `${String(props.effective_start ?? "")} – ` +
            `${String(props.effective_end ?? "")}<br/>` +
            status,
          style: tooltipStyle,
        };
      }
      // MPA feature
      if (props?.mpa_name) {
        return {
          html:
            `<b>${props.mpa_name}</b><br/>` +
            `${(props.protection_level as string) ?? "Unknown protection"}`,
          style: tooltipStyle,
        };
      }
      // BIA feature
      if (props?.bia_name) {
        return {
          html:
            `<b>${props.bia_name}</b><br/>` +
            `${String(props.cmn_name ?? "")} · ${String(props.bia_type ?? "")}<br/>` +
            `Months: ${String(props.bia_months ?? "year-round")}`,
          style: tooltipStyle,
        };
      }
      // Critical Habitat feature
      if (props?.species_label) {
        const status = props.is_proposed ? "Proposed" : "Designated";
        return {
          html:
            `<b>${props.cmn_name ?? props.species_label}</b><br/>` +
            `Critical Habitat · ${status}<br/>` +
            `${String(props.ch_status ?? "")}`,
          style: tooltipStyle,
        };
      }
      // Shipping Lane feature
      if (props?.zone_type && props?.name) {
        return {
          html:
            `<b>${props.name}</b><br/>` +
            `${String(props.zone_type ?? "Shipping Lane")}`,
          style: tooltipStyle,
        };
      }
      // Community sighting marker
      if (object.id && object.lat && object.lon && object.verification_status) {
        const s = object as unknown as MapSighting;
        const sp = s.species ?? s.species_guess ?? "Unknown species";
        const status = s.verification_status.replace(/_/g, " ");
        const media = [
          s.has_photo ? '<span style="opacity:0.7">◻ photo</span>' : "",
          s.has_audio ? '<span style="opacity:0.7">♪ audio</span>' : "",
        ].filter(Boolean).join(" ");
        const votes =
          s.community_agree + s.community_disagree > 0
            ? ` · <span style="color:#4ade80">▲</span>${s.community_agree} <span style="color:#f87171">▼</span>${s.community_disagree}`
            : "";
        const date = new Date(s.created_at).toLocaleDateString();
        return {
          html:
            `<b>${sp.replace(/_/g, " ")}</b><br/>` +
            `${status}${votes}<br/>` +
            `${media ? media + " · " : ""}${date}`,
          style: tooltipStyle,
        };
      }

      // Contour line
      if (props?.depth_m !== undefined) {
        return {
          html: `<b>Depth contour: ${props.label}</b>`,
          style: tooltipStyle,
        };
      }

      // Hex cell (detail mode)
      let val = "";
      if (activeLayer === "risk" || activeLayer === "risk_ml") {
        const isProj = activeLayer === "risk_ml" && sdmTimePeriod && sdmTimePeriod !== "current";
        if (isProj && projectionMode === "change" && object.delta_risk_score != null) {
          const d = object.delta_risk_score as number;
          val = `Δ Risk: ${d > 0 ? "+" : ""}${(d * 100).toFixed(1)}pp`;
        } else {
          val = `Risk: ${(((object.risk_score as number) ?? 0) * 100).toFixed(1)}%`;
        }
        if (isProj) {
          val += `<br/><span style="color:#9ca3af">${(object.scenario as string)?.toUpperCase() ?? ""} · ${object.decade ?? ""}</span>`;
        }
      } else if (activeLayer === "bathymetry") {
        val = `Depth: ${(object.depth_m as number)?.toFixed(0) ?? "?"} m`;
      } else if (activeLayer === "ocean") {
        const cfg = getOceanMetricConfig(oceanMetric);
        const isOcnProj = sdmTimePeriod && sdmTimePeriod !== "current";
        if (isOcnProj && projectionMode === "change") {
          const deltaKey = `delta_${oceanMetric === "pp_upper_200m" ? "pp" : oceanMetric}`;
          const d = (object[deltaKey] as number) ?? 0;
          const sign = d > 0 ? "+" : "";
          val = `Δ ${cfg.label}: ${sign}${d.toFixed(cfg.decimals)} ${cfg.unit}`;
          const abs = (object[cfg.field] as number) ?? null;
          if (abs != null) val += `<br/><span style="color:#9ca3af">Projected: ${abs.toFixed(cfg.decimals)} ${cfg.unit}</span>`;
        } else {
          const raw = (object[cfg.field] as number) ?? null;
          val = raw != null
            ? `${cfg.label}: ${raw.toFixed(cfg.decimals)} ${cfg.unit}`
            : `${cfg.label}: N/A`;
          if (isOcnProj) {
            val += `<br/><span style="color:#9ca3af">${(object.scenario as string)?.toUpperCase() ?? ""} · ${object.decade ?? ""}</span>`;
          }
        }
      } else if (activeLayer === "whale_predictions") {
        const isProj = sdmTimePeriod && sdmTimePeriod !== "current";
        if (isProj && projectionMode === "change" && selectedSpecies) {
          const dc = `delta_${selectedSpecies}`;
          const d = (object[dc] as number) ?? 0;
          val = `Δ ${selectedSpecies.replace("_", " ")}: ${d > 0 ? "+" : ""}${(d * 100).toFixed(1)}%`;
        } else if (selectedSpecies) {
          const col = `isdm_${selectedSpecies}` as string;
          val = `P(${selectedSpecies.replace("_", " ")}): ${(((object[col] as number) ?? 0) * 100).toFixed(1)}%`;
        } else if (isProj) {
          // Max across 4 species as summary
          const mx = Math.max(
            (object.isdm_blue_whale as number) ?? 0,
            (object.isdm_fin_whale as number) ?? 0,
            (object.isdm_humpback_whale as number) ?? 0,
            (object.isdm_sperm_whale as number) ?? 0,
          );
          val = `P(max species): ${(mx * 100).toFixed(1)}%`;
        } else {
          val = `P(whale): ${(((object.any_whale_prob as number) ?? 0) * 100).toFixed(1)}%`;
        }
      } else if (activeLayer === "sdm") {
        if (selectedSpecies) {
          const col = `sdm_${selectedSpecies}` as string;
          val = `SDM P(${selectedSpecies.replace("_", " ")}): ${(((object[col] as number) ?? 0) * 100).toFixed(1)}%`;
        } else {
          val = `SDM P(whale): ${(((object.sdm_any_whale as number) ?? 0) * 100).toFixed(1)}%`;
        }
      } else if (activeLayer === "cetacean_density") {
        val = `Interactions: ${(object.total_sightings as number) ?? 0}`;
      } else if (activeLayer === "strike_density") {
        val = `Strikes: ${(object.total_strikes as number) ?? 0}`;
      } else if (activeLayer === "traffic_density") {
        const vessels = ((object.avg_monthly_vessels as number) ?? 0).toFixed(0);
        const lethality = (((object.avg_speed_lethality as number) ?? 0) * 100).toFixed(1);
        const hiSpeed = (((object.avg_high_speed_fraction as number) ?? 0) * 100).toFixed(0);
        const night = (((object.night_traffic_ratio as number) ?? 0) * 100).toFixed(0);
        val = `Vessels: ${vessels}/mo<br/>` +
          `Lethality: ${lethality}%<br/>` +
          `High-speed: ${hiSpeed}%<br/>` +
          `Night: ${night}%`;
      }

      return {
        html: `<b>${(object.h3 as string)?.slice(0, 10) ?? "Cell"}…</b><br/>${val}`,
        style: tooltipStyle,
      };
    },
    [activeLayer, selectedSpecies, trafficMetric, oceanMetric, sdmTimePeriod, projectionMode],
  );

  /* ── Render ── */

  /** Enable slow-zones overlay, disable others, switch to overlays-only, and zoom to fit. */
  const handleViewSlowZones = useCallback(
    (zones: SlowZone[]) => {
      // Turn off other overlays, keep only slow zones
      setOverlays({
        activeSMAs: false,
        proposedZones: false,
        mpas: false,
        bias: false,
        criticalHabitat: false,
        shippingLanes: false,
        slowZones: true,
        communitySightings: false,
      });
      // Switch to overlays-only so zones are clearly visible
      setActiveLayer("none");

      // Compute bounding box from zone geometries and zoom to fit
      if (zones.length > 0) {
        let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
        const visitCoords = (coords: unknown): void => {
          if (!Array.isArray(coords)) return;
          if (typeof coords[0] === "number") {
            // [lon, lat]
            const lon = coords[0] as number;
            const lat = coords[1] as number;
            if (lat < minLat) minLat = lat;
            if (lat > maxLat) maxLat = lat;
            if (lon < minLon) minLon = lon;
            if (lon > maxLon) maxLon = lon;
          } else {
            coords.forEach(visitCoords);
          }
        };
        for (const z of zones) {
          const geom = z.geometry;
          if (geom && "coordinates" in geom) {
            visitCoords(geom.coordinates);
          }
        }
        if (minLat < maxLat && minLon < maxLon) {
          const centerLat = (minLat + maxLat) / 2;
          const centerLon = (minLon + maxLon) / 2;
          const latSpan = maxLat - minLat;
          const lonSpan = maxLon - minLon;
          const span = Math.max(latSpan, lonSpan * 0.5);
          // Convert span to zoom: zoom ≈ log2(180 / span) with padding
          const zoom = Math.max(
            4,
            Math.min(12, Math.log2(180 / (span * 1.6))),
          );
          setViewState((prev) => ({
            ...prev,
            latitude: centerLat,
            longitude: centerLon,
            zoom,
          }));
        }
      }
    },
    [],
  );

  /** Zoom map to a lat/lon when user checks risk at a location. */
  const handleCheckRiskLocate = useCallback(
    (
      queryLat: number,
      queryLon: number,
      cellLat?: number,
      cellLon?: number,
    ) => {
      // Zoom to cell (where the risk data is)
      const targetLat = cellLat ?? queryLat;
      const targetLon = cellLon ?? queryLon;

      // Choose zoom to fit both points when they differ
      let zoom = 10;
      let centerLat = targetLat;
      let centerLon = targetLon;
      if (cellLat !== undefined && cellLon !== undefined) {
        centerLat = (queryLat + cellLat) / 2;
        centerLon = (queryLon + cellLon) / 2;
        const maxSpan = Math.max(
          Math.abs(cellLat - queryLat),
          Math.abs(cellLon - queryLon),
        );
        if (maxSpan > 20) zoom = 3;
        else if (maxSpan > 8) zoom = 4;
        else if (maxSpan > 3) zoom = 5;
        else if (maxSpan > 1) zoom = 7;
        else if (maxSpan > 0.3) zoom = 9;
      }

      setViewState((prev) => ({
        ...prev,
        latitude: centerLat,
        longitude: centerLon,
        zoom,
      }));

      // Place query location marker (blue)
      setCheckRiskMarker({ lat: queryLat, lon: queryLon });

      // Place risk cell marker (amber) only when distinct
      if (
        cellLat !== undefined &&
        cellLon !== undefined &&
        (Math.abs(cellLat - queryLat) > 0.01 ||
          Math.abs(cellLon - queryLon) > 0.01)
      ) {
        setCheckRiskCellMarker({ lat: cellLat, lon: cellLon });
      } else {
        setCheckRiskCellMarker(null);
      }

      setViewMode("detail");
      if (activeLayer === "none") setActiveLayer("risk");
    },
    [activeLayer],
  );

  return (
    <div className="relative h-screen w-screen overflow-hidden">
      {mounted && (
      <DeckGL
        viewState={viewState}
        // @ts-expect-error — deck.gl generic ViewState callback type
        onViewStateChange={(e: { viewState: ViewState }) => {
          setViewState(e.viewState);
          const z = e.viewState.zoom;
          setViewMode((prev) => {
            if (prev === "overview" && z >= 7) return "detail";
            if (prev === "detail" && z < 6.5) return "overview";
            return prev;
          });
        }}
        controller={true}
        // @ts-expect-error — heterogeneous layer array
        layers={layers}
        onClick={handleClick}
        getTooltip={getTooltip}
      >
        <Map ref={mapRef} mapStyle={MAP_STYLE} />
      </DeckGL>
      )}

      {/* ── Status bar (top centre) ── */}
      <div className="pointer-events-none absolute left-1/2 top-4 z-10 flex -translate-x-1/2 items-center gap-3 rounded-full bg-abyss-900/80 px-4 py-1.5 text-sm text-slate-300">
        {loading && (
          <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-ocean-400" />
        )}
        <span>
          {total > 0
            ? isOverview
              ? `${total.toLocaleString()} overview cells`
              : `${total.toLocaleString()} cells`
            : loading
              ? "Loading\u2026"
              : isOverview
                ? "Loading overview\u2026"
                : "Pan or zoom to load data"}
        </span>
      </div>

      {/* ── Slow Zone warning (auto-fetched, top right) ── */}
      <SlowZoneWarning onViewZones={handleViewSlowZones} />

      {/* ── Check My Risk toggle button ── */}
      {!showCheckRisk && !selectedCell && (
        <button
          onClick={() => setShowCheckRisk(true)}
          className="group absolute right-4 top-28 z-20 overflow-hidden rounded-2xl border border-coral-500/30 bg-gradient-to-br from-abyss-900/95 via-abyss-800/95 to-abyss-900/95 shadow-[0_0_20px_rgba(255,107,107,0.12)] backdrop-blur-md transition-all duration-300 hover:border-coral-400/50 hover:shadow-[0_0_30px_rgba(255,107,107,0.25)]"
          title="Check risk at a specific location"
        >
          {/* Animated gradient border glow */}
          <span className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-r from-coral-500/0 via-coral-400/10 to-coral-500/0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
          {/* Shimmer sweep on hover */}
          <span className="pointer-events-none absolute inset-0 -translate-x-full rounded-2xl bg-gradient-to-r from-transparent via-white/5 to-transparent transition-transform duration-700 group-hover:translate-x-full" />

          <span className="relative flex items-center gap-3 px-5 py-3">
            {/* Pulsing pin icon */}
            <span className="relative flex h-8 w-8 items-center justify-center">
              <span className="absolute inset-0 animate-ping rounded-full bg-coral-500/20" />
              <span className="absolute inset-0.5 rounded-full bg-gradient-to-br from-coral-500/30 to-coral-600/20" />
              <svg
                viewBox="0 0 24 24"
                className="relative h-4.5 w-4.5 fill-coral-400 drop-shadow-[0_0_4px_rgba(255,107,107,0.5)] transition-transform duration-300 group-hover:scale-110"
              >
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 010-5 2.5 2.5 0 010 5z" />
              </svg>
            </span>

            {/* Text stack */}
            <span className="flex flex-col items-start gap-0.5">
              <span className="text-sm font-bold tracking-wide text-white transition-colors group-hover:text-coral-300">
                Check My Risk
              </span>
              <span className="text-[10px] font-medium tracking-wider text-slate-500 transition-colors group-hover:text-slate-400">
                Enter coordinates or use GPS
              </span>
            </span>
          </span>
        </button>
      )}

      {/* ── Check My Risk panel ── */}
      {showCheckRisk && (
        <CheckMyRisk
          onLocate={handleCheckRiskLocate}
          onClose={() => {
            setShowCheckRisk(false);
            setCheckRiskMarker(null);
            setCheckRiskCellMarker(null);
          }}
        />
      )}

      {/* ── Sidebar (left) ── */}
      <Sidebar
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        activeLayer={activeLayer}
        onLayerChange={handleLayerChange}
        season={season}
        onSeasonChange={setSeason}
        overlays={overlays}
        onOverlaysChange={setOverlays}
        activeDate={activeDate}
        onDateChange={setActiveDate}
        selectedSpecies={selectedSpecies}
        onSpeciesChange={setSelectedSpecies}
        showContours={showContours}
        onContoursChange={setShowContours}
        trafficMetric={trafficMetric}
        onTrafficMetricChange={setTrafficMetric}
        oceanMetric={oceanMetric}
        onOceanMetricChange={setOceanMetric}
        sightingColorBy={sightingColorBy}
        onSightingColorByChange={setSightingColorBy}
        sightingSpeciesFilter={sightingSpeciesFilter}
        onSightingSpeciesFilterChange={setSightingSpeciesFilter}
        sightingStatusFilter={sightingStatusFilter}
        onSightingStatusFilterChange={setSightingStatusFilter}
        sightingCount={sightings.length}
        sdmTimePeriod={sdmTimePeriod}
        onSdmTimePeriodChange={handleSdmTimePeriodChange}
        climateScenario={climateScenario}
        onClimateScenarioChange={setClimateScenario}
        projectionMode={projectionMode}
        onProjectionModeChange={setProjectionMode}
      />

      {/* ── Cell detail panel (right, detail mode only) ── */}
      {!isOverview && selectedCell && !selectedZone && (
        <CellDetail
          cell={selectedCell}
          detail={cellDetail}
          activeLayer={activeLayer}
          season={season}
          sdmTimePeriod={sdmTimePeriod}
          onClose={() => {
            setSelectedCell(null);
            setCellDetail(null);
          }}
        />
      )}

      {/* ── Zone detail panel (right, any zone click) ── */}
      {selectedZone && (
        <ZoneDetail
          zone={selectedZone}
          onClose={() => setSelectedZone(null)}
        />
      )}

      {/* ── Legend (bottom right) ── */}
      <Legend
        activeLayer={activeLayer}
        species={selectedSpecies}
        trafficMetric={trafficMetric}
        oceanMetric={oceanMetric}
        projectionMode={projectionMode}
        sdmTimePeriod={sdmTimePeriod}
      />

      {/* ── First-visit hint (bottom centre, above quick-nav) ── */}
      {showMapHint && (
        <div className="absolute bottom-16 left-1/2 z-20 flex -translate-x-1/2 items-center gap-3 rounded-full border border-ocean-700/40 bg-abyss-900/95 px-5 py-2.5 shadow-xl backdrop-blur-md">
          <span className="whitespace-nowrap text-xs text-slate-300">
            <span className="font-semibold text-bioluminescent-400">Zoom in</span>
            {" "}to auto-switch to hex cells ·{" "}
            <span className="font-semibold text-ocean-300">click any hex</span>
            {" "}for detail · open{" "}
            <span className="font-semibold text-slate-200">ⓘ Guide</span>
            {" "}in the sidebar to learn each layer
          </span>
          <button
            type="button"
            onClick={dismissMapHint}
            aria-label="Dismiss hint"
            className="ml-1 rounded-full p-0.5 text-slate-500 transition-colors hover:text-slate-300"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-3.5 w-3.5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414
                   10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0
                   01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
