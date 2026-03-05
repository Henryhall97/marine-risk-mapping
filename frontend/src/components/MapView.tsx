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
import { GeoJsonLayer } from "@deck.gl/layers";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import "maplibre-gl/dist/maplibre-gl.css";

import { INITIAL_VIEW_STATE, MAP_STYLE, MAX_BBOX_AREA_DEG2 } from "@/lib/config";
import {
  getColorForLayer,
  getHeatmapColorRange,
  getMacroWeightField,
  contourLineColor,
  getTrafficMetricConfig,
} from "@/lib/colors";
import { fetchSpeedZones, fetchMPAs, fetchCellDetail, bboxArea } from "@/lib/api";
import { useMapData } from "@/hooks/useMapData";
import { useMacroData, useContourData } from "@/hooks/useMacroData";
import Sidebar from "./Sidebar";
import CellDetail from "./CellDetail";
import Legend from "./Legend";
import type {
  BBox,
  LayerType,
  Season,
  SpeedZone,
  MPA,
  IsdmSpecies,
  OverlayToggles,
  ViewMode,
  TrafficMetric,
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
};

/* ── Main component ──────────────────────────────────────── */

export default function MapView() {
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
  });
  const [viewMode, setViewMode] = useState<ViewMode>("overview");
  const [activeLayer, setActiveLayer] = useState<LayerType>("risk");
  const [season, setSeason] = useState<Season>(null);
  const [selectedSpecies, setSelectedSpecies] =
    useState<IsdmSpecies | null>(null);
  const [trafficMetric, setTrafficMetric] =
    useState<TrafficMetric>("vessel_density");
  const [selectedCell, setSelectedCell] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [cellDetail, setCellDetail] = useState<Record<
    string,
    unknown
  > | null>(null);

  // Overlay toggles
  const [overlays, setOverlays] =
    useState<OverlayToggles>(DEFAULT_OVERLAYS);
  const [activeDate, setActiveDate] = useState(todayISO());
  const [speedZones, setSpeedZones] = useState<SpeedZone[]>([]);
  const [mpas, setMpas] = useState<MPA[]>([]);
  const [showContours, setShowContours] = useState(true);

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
  } = useMapData(bbox, activeLayer, season, selectedSpecies);

  /* ── Macro data (overview mode) ── */
  const {
    data: macroData,
    loading: macroLoading,
    total: macroTotal,
  } = useMacroData(viewMode === "overview" ? season : null);

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

  /* ── Clear species when leaving whale predictions ── */
  const handleLayerChange = useCallback((l: LayerType) => {
    setActiveLayer(l);
    if (l !== "whale_predictions" && l !== "sdm_predictions") {
      setSelectedSpecies(null);
    }
    if (l !== "traffic_density") {
      setTrafficMetric("vessel_density");
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
    (info: { object?: Record<string, unknown> }) => {
      if (!info.object) {
        setSelectedCell(null);
        setCellDetail(null);
        return;
      }
      const obj = info.object;
      setSelectedCell(obj);

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
    return getColorForLayer(activeLayer, selectedSpecies);
  }, [activeLayer, selectedSpecies, trafficMetric]);

  const heatmapColorRange = useMemo(
    () => getHeatmapColorRange(activeLayer, trafficMetric),
    [activeLayer, trafficMetric],
  );

  const macroWeightField = useMemo(
    () =>
      getMacroWeightField(
        activeLayer,
        selectedSpecies,
        trafficMetric,
      ),
    [activeLayer, selectedSpecies, trafficMetric],
  );

  const layers = useMemo(() => {
    const result: unknown[] = [];

    if (isOverview) {
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
              // Normalise sighting/strike counts to 0-1 range
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
    } else {
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
              getFillColor: [activeLayer, selectedSpecies, trafficMetric],
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

    return result;
  }, [
    isOverview,
    macroData,
    macroWeightField,
    heatmapColorRange,
    activeLayer,
    selectedSpecies,
    trafficMetric,
    showContours,
    contourData,
    hexData,
    colorFn,
    speedZones,
    mpas,
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
      if (props?.zone_name) {
        const src = props.source === "proposed" ? "Proposed" : "Active SMA";
        const seasonal = props.is_active
          ? "🔴 In season now"
          : "⚪ Off season";
        return {
          html:
            `<b>${props.zone_name}</b><br/>` +
            `${src} · ${props.season_label ?? ""}<br/>` +
            seasonal,
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
        val = `Risk: ${(((object.risk_score as number) ?? 0) * 100).toFixed(1)}%`;
      } else if (activeLayer === "bathymetry") {
        val = `Depth: ${(object.depth_m as number)?.toFixed(0) ?? "?"} m`;
      } else if (activeLayer === "ocean") {
        val = `SST: ${(object.sst as number)?.toFixed(1) ?? "?"} °C`;
      } else if (activeLayer === "whale_predictions") {
        if (selectedSpecies) {
          const col = `isdm_${selectedSpecies}` as string;
          val = `P(${selectedSpecies.replace("_", " ")}): ${(((object[col] as number) ?? 0) * 100).toFixed(1)}%`;
        } else {
          val = `P(whale): ${(((object.any_whale_prob as number) ?? 0) * 100).toFixed(1)}%`;
        }
      } else if (activeLayer === "sdm_predictions") {
        if (selectedSpecies) {
          const col = `sdm_${selectedSpecies}` as string;
          val = `SDM P(${selectedSpecies.replace("_", " ")}): ${(((object[col] as number) ?? 0) * 100).toFixed(1)}%`;
        } else {
          val = `SDM P(whale): ${(((object.sdm_any_whale as number) ?? 0) * 100).toFixed(1)}%`;
        }
      } else if (activeLayer === "cetacean_density") {
        val = `Sightings: ${(object.total_sightings as number) ?? 0}`;
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
    [activeLayer, selectedSpecies, trafficMetric],
  );

  /* ── Render ── */
  return (
    <div className="relative h-screen w-screen overflow-hidden">
      {mounted && (
      <DeckGL
        viewState={viewState}
        // @ts-expect-error — deck.gl generic ViewState callback type
        onViewStateChange={(e: { viewState: ViewState }) =>
          setViewState(e.viewState)
        }
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
      />

      {/* ── Cell detail panel (right, detail mode only) ── */}
      {!isOverview && selectedCell && (
        <CellDetail
          cell={selectedCell}
          detail={cellDetail}
          activeLayer={activeLayer}
          onClose={() => {
            setSelectedCell(null);
            setCellDetail(null);
          }}
        />
      )}

      {/* ── Legend (bottom right) ── */}
      <Legend
        activeLayer={activeLayer}
        species={selectedSpecies}
        trafficMetric={trafficMetric}
      />
    </div>
  );
}
