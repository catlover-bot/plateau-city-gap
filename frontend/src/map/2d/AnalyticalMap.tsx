import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState
} from "react";
import {
  AttributionControl,
  GeoJSONSource,
  Map as MapLibreMap,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type MapLayerMouseEvent,
  type StyleSpecification
} from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { AppData, FuturesStressMode, GeoJsonFeatureCollection, ValidationWorkspaceData } from "../../types";
import type { MapEngineAdapter } from "../core/MapEngineAdapter";
import { activeLayerIds } from "../layers/layerRegistry";
import type { PublicCartographyPresentation } from "../../features/area-investigation/publicCartography";
import type { LayerPresetId, SpatialSelection, SpatialViewport } from "../../state/spatial/types";

interface Props {
  data: AppData;
  validation: ValidationWorkspaceData | null;
  preset: LayerPresetId;
  primaryLayer: string;
  activeLayerIdsOverride?: string[];
  selection: SpatialSelection | null;
  viewport: SpatialViewport;
  scenarioSites?: GeoJsonFeatureCollection | null;
  scenarioMeshes?: GeoJsonFeatureCollection | null;
  resilienceMap?: GeoJsonFeatureCollection | null;
  stressMode?: FuturesStressMode;
  dimNonSelected?: boolean;
  interactive?: boolean;
  ariaLabel?: string;
  publicCartography?: PublicCartographyPresentation | null;
  onSelectionChange(selection: SpatialSelection | null): void;
  onViewportChange(viewport: SpatialViewport): void;
  onReady?(): void;
  onError?(message: string): void;
}

const EMPTY: GeoJsonFeatureCollection = { type: "FeatureCollection", features: [] };
setWorkerUrl(maplibreWorkerUrl);
const GSI_ATTRIBUTION = '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noreferrer">地理院タイル</a>';
const OSM_ATTRIBUTION = '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>';

const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    "gsi-pale": {
      type: "raster",
      tiles: ["https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png"],
      tileSize: 256,
      minzoom: 5,
      maxzoom: 18,
      attribution: GSI_ATTRIBUTION
    }
  },
  layers: [
    { id: "product-background", type: "background", paint: { "background-color": "#e9ebe7" } },
    { id: "gsi-pale", type: "raster", source: "gsi-pale", paint: { "raster-opacity": .78, "raster-saturation": -.72, "raster-contrast": -.08 } }
  ]
};

const metricProperty = (primaryLayer: string): string => primaryLayer === "analysis-population"
  ? "elderly_population_percentile"
  : primaryLayer === "analysis-transport"
    ? "transport_distance_percentile"
    : primaryLayer === "analysis-medical"
      ? "medical_distance_percentile"
      : primaryLayer === "scenario-footprint"
        ? "after_score_c"
        : "exploratory_score_c";

const metricColors = (primaryLayer: string): [string, string, string] => primaryLayer === "analysis-transport"
  ? ["#e5ece9", "#9cabb0", "#526f7e"]
  : primaryLayer === "analysis-medical"
    ? ["#eeeae5", "#c49a83", "#965643"]
    : primaryLayer === "analysis-population"
      ? ["#e8eee8", "#c4ae7c", "#9a672b"]
      : ["#dfeae3", "#6d9e91", "#c38b2c"];

function sourceData(collection: GeoJsonFeatureCollection | null | undefined): never {
  return (collection ?? EMPTY) as never;
}

function addGeoJson(map: MapLibreMap, id: string, collection: GeoJsonFeatureCollection | null | undefined, cluster = false): void {
  if (map.getSource(id)) return;
  map.addSource(id, {
    type: "geojson",
    data: sourceData(collection),
    attribution: id.startsWith("validation") ? OSM_ATTRIBUTION : undefined,
    cluster,
    clusterMaxZoom: 13,
    clusterRadius: 46
  });
}

function setSource(map: MapLibreMap, id: string, collection: GeoJsonFeatureCollection | null | undefined): void {
  const source = map.getSource(id);
  if (source instanceof GeoJSONSource) source.setData(sourceData(collection));
}

function layerVisibility(map: MapLibreMap, id: string, visible: boolean): void {
  if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
}

function lngLatFromProperties(properties: Record<string, unknown>, fallback: { lng: number; lat: number }): [number, number] {
  const longitude = Number(properties.centroid_lon ?? properties.longitude ?? fallback.lng);
  const latitude = Number(properties.centroid_lat ?? properties.latitude ?? fallback.lat);
  return [Number.isFinite(longitude) ? longitude : fallback.lng, Number.isFinite(latitude) ? latitude : fallback.lat];
}

function collectionBounds(collection: GeoJsonFeatureCollection | null | undefined) {
  let west = Number.POSITIVE_INFINITY;
  let south = Number.POSITIVE_INFINITY;
  let east = Number.NEGATIVE_INFINITY;
  let north = Number.NEGATIVE_INFINITY;
  const visit = (value: unknown): void => {
    if (!Array.isArray(value)) return;
    if (
      value.length >= 2
      && typeof value[0] === "number"
      && typeof value[1] === "number"
    ) {
      west = Math.min(west, value[0]);
      south = Math.min(south, value[1]);
      east = Math.max(east, value[0]);
      north = Math.max(north, value[1]);
      return;
    }
    value.forEach(visit);
  };
  collection?.features.forEach((feature) => visit(feature.geometry?.coordinates));
  return Number.isFinite(west) ? { west, south, east, north } : null;
}

export const AnalyticalMap = forwardRef<MapEngineAdapter, Props>(function AnalyticalMap({
  data,
  validation,
  preset,
  primaryLayer,
  activeLayerIdsOverride,
  publicCartography,
  selection,
  viewport,
  scenarioSites,
  scenarioMeshes,
  resilienceMap,
  stressMode = "normal",
  dimNonSelected = false,
  interactive = true,
  ariaLabel = "CITY GAP 2D分析地図。矢印キーで移動、プラスとマイナスで拡大縮小できます",
  onSelectionChange,
  onViewportChange,
  onReady,
  onError
}, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const hoveredId = useRef<string | number | null>(null);
  const [styleReady, setStyleReady] = useState(false);
  const publicCameraKey = useRef("");
  const onSelectionRef = useRef(onSelectionChange);
  const onViewportRef = useRef(onViewportChange);
  const [zoom, setZoom] = useState(viewport.zoom);
  const activeIds = useMemo(
    () => new Set(activeLayerIdsOverride ?? activeLayerIds(preset)),
    [activeLayerIdsOverride, preset]
  );
  onSelectionRef.current = onSelectionChange;
  onViewportRef.current = onViewportChange;

  useImperativeHandle(ref, () => ({
    setViewport(next) {
      mapRef.current?.jumpTo({ center: [next.longitude, next.latitude], zoom: next.zoom, bearing: 0, pitch: 0 });
    },
    getViewport() {
      const map = mapRef.current;
      if (!map) return viewport;
      const center = map.getCenter();
      return { longitude: center.lng, latitude: center.lat, zoom: map.getZoom(), bearing: 0, pitch: 0 };
    },
    fitBounds(bounds) {
      mapRef.current?.fitBounds([[bounds.west, bounds.south], [bounds.east, bounds.north]], { padding: 52, duration: 0 });
    },
    setSelection(next) {
      if (!next?.longitude || !next.latitude) return;
      mapRef.current?.easeTo({ center: [next.longitude, next.latitude], zoom: Math.max(mapRef.current.getZoom(), 13), duration: 300 });
    },
    setLayers() {},
    highlight(next) {
      if (next.longitude && next.latitude) mapRef.current?.easeTo({ center: [next.longitude, next.latitude], zoom: Math.max(mapRef.current.getZoom(), 13), duration: 300 });
    },
    clearHighlight() { onSelectionRef.current(null); },
    async exportView() {
      const canvas = mapRef.current?.getCanvas();
      if (!canvas) return null;
      return await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    }
  }), [viewport]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: BASE_STYLE,
      center: [viewport.longitude, viewport.latitude],
      zoom: viewport.zoom,
      bearing: 0,
      pitch: 0,
      attributionControl: false,
      cooperativeGestures: true,
      dragRotate: false,
      pitchWithRotate: false,
      interactive,
      maxPitch: 0,
      canvasContextAttributes: { preserveDrawingBuffer: true }
    });
    mapRef.current = map;
    const debugWindow = window as Window & { __cityGapMapInitCount?: number };
    debugWindow.__cityGapMapInitCount = (debugWindow.__cityGapMapInitCount ?? 0) + 1;
    (containerRef.current as HTMLDivElement & { __cityGapMap?: MapLibreMap }).__cityGapMap = map;
    map.addControl(new NavigationControl({ showCompass: false, visualizePitch: false }), "top-right");
    map.addControl(new ScaleControl({ unit: "metric", maxWidth: 110 }), "bottom-left");
    map.addControl(new AttributionControl({ compact: false, customAttribution: "CITY GAP" }), "bottom-right");
    const canvas = map.getCanvas();
    canvas.tabIndex = 0;
    canvas.setAttribute("role", "application");
    canvas.setAttribute("aria-label", ariaLabel);
    let criticalError = false;

    map.on("load", () => {
      addGeoJson(map, "boundary", data.boundary);
      addGeoJson(map, "meshes", data.meshes);
      addGeoJson(map, "stations", data.stations, true);
      addGeoJson(map, "bus", data.busStops, true);
      addGeoJson(map, "medical", data.medicalFacilities, true);
      addGeoJson(map, "plateau-roads", data.plateauRoads);
      addGeoJson(map, "validation-routes", validation?.disagreementRoutes);
      addGeoJson(map, "temporal", validation?.temporalSamples);
      addGeoJson(map, "scenario-sites", scenarioSites);
      addGeoJson(map, "scenario-meshes", scenarioMeshes);
      addGeoJson(map, "resilience", resilienceMap);
      addGeoJson(map, "public-area", publicCartography?.area?.polygon);
      addGeoJson(map, "public-area-mask", publicCartography?.area?.outsideMask);
      addGeoJson(map, "public-buildings", publicCartography?.data.buildings);
      addGeoJson(map, "public-roads", publicCartography?.data.roads);
      addGeoJson(map, "public-planning", publicCartography?.data.planning);
      addGeoJson(map, "public-target", publicCartography?.target?.geometry);
      addGeoJson(map, "public-origin", publicCartography?.area ? { type: "FeatureCollection", features: [{ type: "Feature", properties: { role: "origin" }, geometry: { type: "Point", coordinates: publicCartography.area.center } }] } : EMPTY);

      map.addLayer({ id: "boundary-fill", type: "fill", source: "boundary", paint: { "fill-color": "#d9e4df", "fill-opacity": .11 } });
      map.addLayer({ id: "boundary-line", type: "line", source: "boundary", paint: { "line-color": "#315e5a", "line-width": 1.4, "line-opacity": .62 } });
      map.addLayer({ id: "mesh-fill", type: "fill", source: "meshes", minzoom: 8, maxzoom: 16.5, paint: {
        "fill-color": ["interpolate", ["linear"], ["coalesce", ["to-number", ["get", metricProperty(primaryLayer)]], 0], 0, metricColors(primaryLayer)[0], primaryLayer === "analysis-city-gap" ? .18 : .55, metricColors(primaryLayer)[1], primaryLayer === "analysis-city-gap" ? .55 : 1, metricColors(primaryLayer)[2]],
        "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], .86, ["<=", ["coalesce", ["get", "rank"], 9999], 10], dimNonSelected ? .46 : .82, ["==", ["get", "primary_eligible"], true], dimNonSelected ? .11 : .37, .055]
      } });
      map.addLayer({ id: "mesh-outline", type: "line", source: "meshes", minzoom: 10, maxzoom: 16.5, paint: { "line-color": "#506a65", "line-width": ["interpolate", ["linear"], ["zoom"], 10, .12, 14, .55], "line-opacity": ["interpolate", ["linear"], ["zoom"], 10, .08, 14, .28] } });
      map.addLayer({ id: "mesh-top-fill", type: "fill", source: "meshes", minzoom: 8, maxzoom: 13.2, filter: ["<=", ["coalesce", ["get", "rank"], 9999], 10], paint: { "fill-color": "#c38b2c", "fill-opacity": .72 } });
      map.addLayer({ id: "mesh-top-outline", type: "line", source: "meshes", minzoom: 8, maxzoom: 13.2, filter: ["<=", ["coalesce", ["get", "rank"], 9999], 10], paint: { "line-color": "#173b39", "line-width": 1.5, "line-opacity": .9 } });
      map.addLayer({ id: "mesh-selected", type: "line", source: "meshes", minzoom: 8, paint: { "line-color": "#132f31", "line-width": 3, "line-opacity": 1 }, filter: ["==", ["get", "mesh_code"], "__none__"] });
      map.addLayer({ id: "mesh-top-label", type: "symbol", source: "meshes", minzoom: 9.6, filter: ["<=", ["coalesce", ["get", "rank"], 9999], 10], layout: { "text-field": ["coalesce", ["get", "area_label"], ["get", "mesh_code"]], "text-size": ["interpolate", ["linear"], ["zoom"], 9.6, 9, 13, 11], "text-allow-overlap": false, "text-padding": 8 }, paint: { "text-color": "#173c39", "text-halo-color": "#fafaf5", "text-halo-width": 1.8 } });
      map.addLayer({ id: "plateau-road-line", type: "line", source: "plateau-roads", minzoom: 13, paint: { "line-color": "#5e6f6b", "line-width": ["interpolate", ["linear"], ["zoom"], 13, .8, 17, 2.8], "line-opacity": .7 }, layout: { visibility: "none" } });

      const pointLayers = [
        ["stations", "station", "#526f7e"], ["bus", "bus", "#728991"], ["medical", "medical", "#985746"]
      ] as const;
      for (const [sourceId, prefix, color] of pointLayers) {
        map.addLayer({ id: `${prefix}-clusters`, type: "circle", source: sourceId, filter: ["has", "point_count"], minzoom: prefix === "bus" ? 13 : 10.5, paint: { "circle-color": color, "circle-radius": ["step", ["get", "point_count"], 12, 20, 16, 60, 20], "circle-opacity": .82, "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
        map.addLayer({ id: `${prefix}-cluster-count`, type: "symbol", source: sourceId, filter: ["has", "point_count"], minzoom: prefix === "bus" ? 13 : 10.5, layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 10, "text-allow-overlap": true }, paint: { "text-color": "#fff" } });
        map.addLayer({ id: `${prefix}-point`, type: "circle", source: sourceId, filter: ["!", ["has", "point_count"]], minzoom: prefix === "bus" ? 13 : 10.5, paint: { "circle-color": color, "circle-radius": prefix === "medical" ? 6 : 5, "circle-stroke-color": "#fff", "circle-stroke-width": 1.5, "circle-opacity": .92 } });
      }
      map.addLayer({ id: "public-buildings-fill", type: "fill", source: "public-buildings", minzoom: 12, layout: { visibility: "none" }, paint: { "fill-color": ["match", ["get", "usage_label"], "住宅", "#6f9f91", "共同住宅", "#527b87", "商業施設", "#9a7a50", "#aab3ae"], "fill-opacity": .62 } });
      map.addLayer({ id: "public-buildings-line", type: "line", source: "public-buildings", minzoom: 12, layout: { visibility: "none" }, paint: { "line-color": "#365b52", "line-width": ["interpolate", ["linear"], ["zoom"], 12, .3, 17, 1.1], "line-opacity": .72 } });
      map.addLayer({ id: "public-roads-fill", type: "fill", source: "public-roads", minzoom: 12, layout: { visibility: "none" }, paint: { "fill-color": "#789897", "fill-opacity": .3 } });
      map.addLayer({ id: "public-roads-line", type: "line", source: "public-roads", minzoom: 12, layout: { visibility: "none" }, paint: { "line-color": "#496a69", "line-width": ["interpolate", ["linear"], ["zoom"], 12, .45, 17, 2], "line-opacity": .7 } });
      map.addLayer({ id: "public-planning-fill", type: "fill", source: "public-planning", layout: { visibility: "none" }, paint: { "fill-color": "#78998e", "fill-opacity": .2 } });
      map.addLayer({ id: "public-planning-line", type: "line", source: "public-planning", layout: { visibility: "none" }, paint: { "line-color": "#526b65", "line-width": 1.2, "line-dasharray": [3, 2], "line-opacity": .8 } });
      map.addLayer({ id: "public-area-fill", type: "fill", source: "public-area", layout: { visibility: "none" }, paint: { "fill-color": "#1e6f62", "fill-opacity": .075 } });
      map.addLayer({ id: "public-area-mask", type: "fill", source: "public-area-mask", layout: { visibility: "none" }, paint: { "fill-color": "#f2f0e8", "fill-opacity": .11 } });
      map.addLayer({ id: "public-area-line", type: "line", source: "public-area", layout: { visibility: "none" }, paint: { "line-color": "#1e6f62", "line-width": 3, "line-opacity": .96 } });
      map.addLayer({ id: "public-origin-halo", type: "circle", source: "public-origin", layout: { visibility: "none" }, paint: { "circle-color": "#ffffff", "circle-radius": 9, "circle-opacity": .94 } });
      map.addLayer({ id: "public-origin-point", type: "circle", source: "public-origin", layout: { visibility: "none" }, paint: { "circle-color": "#173f38", "circle-radius": 5, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 } });
      map.addLayer({ id: "public-target-fill", type: "fill", source: "public-target", layout: { visibility: "none" }, paint: { "fill-color": "#b7791f", "fill-opacity": .2 } });
      map.addLayer({ id: "public-target-line", type: "line", source: "public-target", layout: { visibility: "none" }, paint: { "line-color": "#b7791f", "line-width": 4, "line-dasharray": [2, 1.4], "line-opacity": 1 } });
      map.addLayer({ id: "public-target-point", type: "circle", source: "public-target", filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none" }, paint: { "circle-color": "#b7791f", "circle-radius": 9, "circle-stroke-color": "#ffffff", "circle-stroke-width": 3, "circle-opacity": .98 } });

      map.addLayer({ id: "validation-primary", type: "line", source: "validation-routes", filter: ["==", ["get", "route_model"], "primary_model"], minzoom: 9, layout: { visibility: "none", "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#397888", "line-width": 4, "line-opacity": dimNonSelected ? .35 : .9 } });
      map.addLayer({ id: "validation-reference", type: "line", source: "validation-routes", filter: ["==", ["get", "route_model"], "reference_model"], minzoom: 9, layout: { visibility: "none", "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#719b43", "line-width": 3, "line-dasharray": [2, 1.5], "line-opacity": dimNonSelected ? .35 : .9 } });
      map.addLayer({ id: "validation-selected", type: "line", source: "validation-routes", minzoom: 9, filter: ["==", ["get", "sample_id"], "__none__"], layout: { visibility: "none", "line-cap": "round" }, paint: { "line-color": "#d3982d", "line-width": 7, "line-opacity": .78 } });
      map.addLayer({ id: "temporal-fill", type: "fill", source: "temporal", minzoom: 10, layout: { visibility: "none" }, paint: { "fill-color": ["match", ["get", "change_type"], "added", "#2b7a6e", "removed", "#9a5547", "#b4862e"], "fill-opacity": .5 } });
      map.addLayer({ id: "temporal-line", type: "line", source: "temporal", minzoom: 10, layout: { visibility: "none" }, paint: { "line-color": ["match", ["get", "change_type"], "added", "#1f6a60", "removed", "#8b493e", "#9a6d1f"], "line-width": 2.4, "line-dasharray": ["case", ["==", ["get", "change_type"], "removed"], ["literal", [2, 1.5]], ["literal", [1, 0]]] } });
      map.addLayer({ id: "temporal-point", type: "circle", source: "temporal", minzoom: 10, layout: { visibility: "none" }, paint: { "circle-color": ["match", ["get", "change_type"], "added", "#2b7a6e", "removed", "#9a5547", "#b4862e"], "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 4, 15, 8], "circle-stroke-color": "#fff", "circle-stroke-width": 2, "circle-opacity": .9 } });
      map.addLayer({ id: "temporal-point-label", type: "symbol", source: "temporal", minzoom: 12.5, layout: { visibility: "none", "text-field": ["match", ["get", "change_type"], "added", "+", "removed", "−", "△"], "text-size": 11, "text-allow-overlap": false }, paint: { "text-color": "#fff" } });
      map.addLayer({ id: "scenario-mesh-fill", type: "fill", source: "scenario-meshes", minzoom: 8, layout: { visibility: "none" }, paint: { "fill-color": ["interpolate", ["linear"], ["coalesce", ["to-number", ["get", "after_score_c"]], 0], 0, "#e5ece7", 1, "#9a6f83"], "fill-opacity": .55 } });
      map.addLayer({ id: "scenario-site-point", type: "circle", source: "scenario-sites", minzoom: 9, layout: { visibility: "none" }, paint: { "circle-color": ["match", ["get", "scenario"], "A", "#25766f", "B", "#aa7a2f", "#855f78"], "circle-radius": 9, "circle-stroke-color": "#fff", "circle-stroke-width": 3 } });
      map.addLayer({ id: "resilience-network", type: "line", source: "resilience", minzoom: 8, filter: ["in", ["get", "layer_type"], ["literal", ["normal_route", "disrupted_route", "critical_edge"]]], layout: { visibility: "none", "line-cap": "round" }, paint: { "line-color": ["match", ["get", "layer_type"], "critical_edge", "#b47a21", "disrupted_route", "#945442", "#526f7e"], "line-width": ["match", ["get", "layer_type"], "critical_edge", 6, "disrupted_route", 4, 2], "line-opacity": .88 } });
      map.addLayer({ id: "resilience-area", type: "fill", source: "resilience", minzoom: 8, filter: ["==", ["get", "layer_type"], "disconnected_area"], layout: { visibility: "none" }, paint: { "fill-color": "#68617e", "fill-opacity": .22 } });
      map.addLayer({ id: "resilience-area-outline", type: "line", source: "resilience", minzoom: 8, filter: ["==", ["get", "layer_type"], "disconnected_area"], layout: { visibility: "none" }, paint: { "line-color": "#4f4965", "line-width": 2, "line-dasharray": [3, 2], "line-opacity": .9 } });

      const meshInteraction = (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature?.properties) return;
        const properties = feature.properties as Record<string, unknown>;
        const [longitude, latitude] = lngLatFromProperties(properties, event.lngLat);
        onSelectionRef.current({
          type: "mesh",
          id: String(properties.mesh_code),
          city: data.city.id,
          urbanState: "2025",
          label: String(properties.area_label ?? `500mメッシュ ${properties.mesh_code}`),
          longitude,
          latitude,
          properties
        });
      };
      map.on("click", "mesh-fill", meshInteraction);
      map.on("mousemove", "mesh-fill", (event) => {
        if (hoveredId.current !== null) map.setFeatureState({ source: "meshes", id: hoveredId.current }, { hover: false });
        hoveredId.current = event.features?.[0]?.id ?? null;
        if (hoveredId.current !== null) map.setFeatureState({ source: "meshes", id: hoveredId.current }, { hover: true });
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "mesh-fill", () => {
        if (hoveredId.current !== null) map.setFeatureState({ source: "meshes", id: hoveredId.current }, { hover: false });
        hoveredId.current = null;
        map.getCanvas().style.cursor = "";
      });
      const routeSelection = (event: MapLayerMouseEvent) => {
        const properties = event.features?.[0]?.properties as Record<string, unknown> | undefined;
        if (!properties?.sample_id) return;
        onSelectionRef.current({ type: "validation_sample", id: String(properties.sample_id), city: data.city.id, urbanState: "2025", label: `経路差異 ${String(properties.sample_id).slice(-8)}`, longitude: event.lngLat.lng, latitude: event.lngLat.lat, properties });
      };
      map.on("click", "validation-primary", routeSelection);
      map.on("click", "validation-reference", routeSelection);
      map.on("click", "temporal-point", (event) => {
        const feature = event.features?.[0];
        const properties = feature?.properties as Record<string, unknown> | undefined;
        if (!feature || !properties) return;
        const changeType = String(properties.change_type ?? "changed");
        onSelectionRef.current({
          type: "temporal_change",
          id: String(feature.id ?? properties.sample_id ?? `${changeType}:${event.lngLat.lng}:${event.lngLat.lat}`),
          city: data.city.id,
          urbanState: "2025",
          label: `PLATEAU ${changeType} sample`,
          longitude: event.lngLat.lng,
          latitude: event.lngLat.lat,
          properties: { ...properties, geometry_semantics: "published_point_only" },
        });
      });
      map.on("mouseenter", "temporal-point", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "temporal-point", () => { map.getCanvas().style.cursor = ""; });
      const initialShowMeshes = primaryLayer.startsWith("analysis-");
      layerVisibility(map, "mesh-fill", initialShowMeshes);
      layerVisibility(map, "mesh-outline", initialShowMeshes);
      layerVisibility(map, "mesh-top-label", initialShowMeshes);
      layerVisibility(map, "mesh-top-fill", primaryLayer === "analysis-city-gap");
      layerVisibility(map, "mesh-top-outline", primaryLayer === "analysis-city-gap");
      layerVisibility(map, "plateau-road-line", activeIds.has("plateau-roads"));
      layerVisibility(map, "validation-primary", activeIds.has("validation-primary-route"));
      layerVisibility(map, "validation-reference", activeIds.has("validation-reference-route"));
      layerVisibility(map, "validation-selected", activeIds.has("validation-disagreement"));
      layerVisibility(map, "temporal-fill", primaryLayer === "validation-temporal");
      layerVisibility(map, "temporal-line", primaryLayer === "validation-temporal");
      layerVisibility(map, "temporal-point", primaryLayer === "validation-temporal");
      layerVisibility(map, "temporal-point-label", primaryLayer === "validation-temporal");
      layerVisibility(map, "scenario-mesh-fill", primaryLayer === "scenario-footprint");
      layerVisibility(map, "scenario-site-point", activeIds.has("scenario-sites"));
      layerVisibility(map, "resilience-network", primaryLayer === "hazard-composite");
      layerVisibility(map, "resilience-area", primaryLayer === "hazard-composite");
      layerVisibility(map, "resilience-area-outline", primaryLayer === "hazard-composite");
      setStyleReady(true);
      containerRef.current?.parentElement?.setAttribute("data-map-render-state", "ready");
      let stableFrames = 0;
      const settle = () => {
        if (criticalError) return;
        stableFrames += 1;
        if (stableFrames < 3) {
          requestAnimationFrame(settle);
          return;
        }
        void document.fonts?.ready.then(() => {
          containerRef.current?.parentElement?.setAttribute("data-visual-ready", "true");
          containerRef.current?.parentElement?.setAttribute("data-stable-frames", String(stableFrames));
          onReady?.();
        });
      };
      map.once("idle", () => requestAnimationFrame(settle));
    });
    map.on("moveend", () => {
      const center = map.getCenter();
      const next = { longitude: center.lng, latitude: center.lat, zoom: map.getZoom(), bearing: 0, pitch: 0 };
      setZoom(next.zoom);
      onViewportRef.current(next);
    });
    map.on("error", (event) => {
      const message = event.error?.message ?? "2D地図データを読み込めませんでした";
      const sourceId = (event as { sourceId?: string }).sourceId;
      if (sourceId === "gsi-pale" || message.includes("cyberjapandata.gsi.go.jp")) {
        const shell = containerRef.current?.parentElement;
        shell?.setAttribute("data-map-render-state", "degraded");
        shell?.setAttribute("data-visual-ready", "true");
        shell?.setAttribute("data-basemap-error", message);
        return;
      }
      criticalError = true;
      containerRef.current?.parentElement?.setAttribute("data-visual-ready", "false");
      containerRef.current?.parentElement?.setAttribute("data-map-render-state", "degraded");
      containerRef.current?.parentElement?.setAttribute("data-critical-error", message);
      onError?.(message);
    });
    return () => {
      setStyleReady(false);
      map.remove();
      mapRef.current = null;
    };
    // Recreating the engine for every synchronized viewport tick would break map continuity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeIds, ariaLabel, data, interactive, onError, onReady, primaryLayer, resilienceMap, scenarioMeshes, scenarioSites, validation]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    setSource(map, "meshes", scenarioMeshes && primaryLayer === "scenario-footprint" ? scenarioMeshes : data.meshes);
    setSource(map, "validation-routes", validation?.disagreementRoutes);
    setSource(map, "temporal", validation?.temporalSamples);
    setSource(map, "scenario-sites", scenarioSites);
    setSource(map, "scenario-meshes", scenarioMeshes);
    setSource(map, "resilience", resilienceMap);
    const colors = metricColors(primaryLayer);
    map.setPaintProperty("mesh-fill", "fill-color", ["interpolate", ["linear"], ["coalesce", ["to-number", ["get", metricProperty(primaryLayer)]], 0], 0, colors[0], primaryLayer === "analysis-city-gap" ? .18 : .55, colors[1], primaryLayer === "analysis-city-gap" ? .55 : 1, colors[2]]);
    map.setPaintProperty("mesh-fill", "fill-opacity", ["case", ["boolean", ["feature-state", "hover"], false], .86, ["<=", ["coalesce", ["get", "rank"], 9999], 10], dimNonSelected ? .46 : .82, ["==", ["get", "primary_eligible"], true], dimNonSelected ? .11 : .37, .055]);
    const showMeshes = primaryLayer.startsWith("analysis-");
    layerVisibility(map, "mesh-fill", showMeshes);
    layerVisibility(map, "mesh-outline", showMeshes);
    layerVisibility(map, "mesh-top-label", showMeshes);
    layerVisibility(map, "mesh-top-fill", primaryLayer === "analysis-city-gap");
    layerVisibility(map, "mesh-top-outline", primaryLayer === "analysis-city-gap");
    layerVisibility(map, "plateau-road-line", activeIds.has("plateau-roads"));
    layerVisibility(map, "validation-primary", activeIds.has("validation-primary-route"));
    layerVisibility(map, "validation-reference", activeIds.has("validation-reference-route"));
    layerVisibility(map, "validation-selected", activeIds.has("validation-disagreement"));
    layerVisibility(map, "temporal-fill", primaryLayer === "validation-temporal");
    layerVisibility(map, "temporal-line", primaryLayer === "validation-temporal");
    layerVisibility(map, "temporal-point", primaryLayer === "validation-temporal");
    layerVisibility(map, "temporal-point-label", primaryLayer === "validation-temporal");
    layerVisibility(map, "scenario-mesh-fill", primaryLayer === "scenario-footprint");
    layerVisibility(map, "scenario-site-point", activeIds.has("scenario-sites"));
    layerVisibility(map, "resilience-network", primaryLayer === "hazard-composite");
    layerVisibility(map, "resilience-area", primaryLayer === "hazard-composite");
    layerVisibility(map, "resilience-area-outline", primaryLayer === "hazard-composite");
    if (map.getLayer("resilience-network")) map.setFilter("resilience-network", ["all", ["in", ["get", "layer_type"], ["literal", ["normal_route", "disrupted_route", "critical_edge"]]], stressMode === "normal" ? ["==", ["get", "stress_mode"], "all"] : ["in", ["get", "stress_mode"], ["literal", ["all", stressMode]]]]);
    if (map.getLayer("resilience-area")) map.setFilter("resilience-area", ["all", ["==", ["get", "layer_type"], "disconnected_area"], stressMode === "normal" ? ["==", ["get", "stress_mode"], "all"] : ["in", ["get", "stress_mode"], ["literal", ["all", stressMode]]]]);
    if (map.getLayer("resilience-area-outline")) map.setFilter("resilience-area-outline", ["all", ["==", ["get", "layer_type"], "disconnected_area"], stressMode === "normal" ? ["==", ["get", "stress_mode"], "all"] : ["in", ["get", "stress_mode"], ["literal", ["all", stressMode]]]]);
    for (const prefix of ["station", "bus", "medical"]) {
      const registryId = prefix === "station" ? "infra-stations" : prefix === "bus" ? "infra-bus" : "infra-medical";
      for (const suffix of ["clusters", "cluster-count", "point"]) layerVisibility(map, `${prefix}-${suffix}`, activeIds.has(registryId));
    }
  }, [activeIds, data.meshes, dimNonSelected, primaryLayer, resilienceMap, scenarioMeshes, scenarioSites, stressMode, validation]);

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map?.isStyleLoaded()) return;
    const shell = containerRef.current?.parentElement;
    const presentation = primaryLayer === "public-cartography" ? publicCartography : null;
    const area = presentation?.area ?? null;
    const story = presentation?.activeStory ?? null;
    const target = presentation?.target ?? null;
    const areaVisible = Boolean(area);
    const targetTypes = new Set(target?.geometry.features.map((feature) => feature.geometry?.type) ?? []);
    const targetExact = target?.resolution === "exact";
    const targetVisible = Boolean(target && target.resolution !== "area_fallback");
    const targetFocused = Boolean(target && presentation?.showTarget);
    const targetColor = targetFocused ? "#6b4c7d" : "#b7791f";

    shell?.setAttribute("data-visual-ready", "false");
    shell?.setAttribute("data-public-cartography-ready", "false");
    shell?.setAttribute("data-public-story", story ?? "none");
    shell?.setAttribute("data-public-area-visible", String(areaVisible));
    shell?.setAttribute("data-target-resolution", target?.resolution ?? "none");

    setSource(map, "public-area", area?.polygon);
    setSource(map, "public-area-mask", area?.outsideMask);
    setSource(map, "public-buildings", presentation?.data.buildings);
    setSource(map, "public-roads", presentation?.data.roads);
    setSource(map, "public-planning", presentation?.data.planning);
    setSource(map, "public-target", target?.geometry);
    setSource(map, "public-origin", area ? {
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        properties: { role: "origin" },
        geometry: { type: "Point", coordinates: area.center },
      }],
    } : EMPTY);

    for (const id of ["public-area-fill", "public-area-mask", "public-area-line", "public-origin-halo", "public-origin-point"]) {
      layerVisibility(map, id, areaVisible);
    }
    layerVisibility(map, "public-buildings-fill", story === "building-use" && Boolean(presentation?.derivativeAvailable));
    layerVisibility(map, "public-buildings-line", story === "building-use" && Boolean(presentation?.derivativeAvailable));
    layerVisibility(map, "public-roads-fill", false);
    layerVisibility(map, "public-roads-line", false);
    layerVisibility(map, "public-planning-fill", story === "urban-planning" && Boolean(presentation?.derivativeAvailable));
    layerVisibility(map, "public-planning-line", story === "urban-planning" && Boolean(presentation?.derivativeAvailable));
    layerVisibility(map, "mesh-fill", story === "population-age");
    layerVisibility(map, "mesh-outline", story === "population-age");
    layerVisibility(map, "mesh-top-fill", false);
    layerVisibility(map, "mesh-top-outline", false);
    layerVisibility(map, "mesh-top-label", false);
    for (const suffix of ["clusters", "cluster-count", "point"]) {
      layerVisibility(map, `station-${suffix}`, story === "transport");
      layerVisibility(map, `bus-${suffix}`, story === "transport");
      layerVisibility(map, `medical-${suffix}`, false);
    }

    if (story === "population-age") {
      map.setPaintProperty("mesh-fill", "fill-color", [
        "interpolate", ["linear"],
        ["coalesce", ["to-number", ["get", "elderly_population_percentile"]], 0],
        0, "#dcebe6",
        .5, "#82b5a8",
        1, "#2f7466",
      ]);
      map.setPaintProperty("mesh-fill", "fill-opacity", [
        "case",
        ["==", ["get", "elderly_population_percentile"], null], .06,
        .54,
      ]);
    }

    layerVisibility(map, "public-target-fill", targetVisible && targetExact && (targetTypes.has("Polygon") || targetTypes.has("MultiPolygon")));
    layerVisibility(map, "public-target-line", targetVisible && targetExact);
    layerVisibility(map, "public-target-point", targetVisible && !targetExact && targetTypes.has("Point"));
    map.setPaintProperty("public-target-fill", "fill-color", targetColor);
    map.setPaintProperty("public-target-line", "line-color", targetColor);
    map.setPaintProperty("public-target-line", "line-dasharray", targetFocused ? [1, .01] : [2, 1.4]);
    map.setPaintProperty("public-target-point", "circle-color", targetColor);
    map.setPaintProperty("public-area-line", "line-color", targetFocused && target?.resolution === "area_fallback" ? targetColor : "#1e6f62");
    map.setPaintProperty("public-area-line", "line-dasharray", targetFocused && target?.resolution === "area_fallback" ? [2, 1.4] : [1, .01]);

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const duration = reducedMotion ? 0 : 280;
    const cameraKey = targetFocused && target
      ? `target:${target.objectId}:${target.resolution}`
      : area
        ? `area:${area.center.join(",")}:${area.radiusM}`
        : "";
    if (cameraKey && cameraKey !== publicCameraKey.current) {
      publicCameraKey.current = cameraKey;
      if (targetFocused && target?.resolution === "exact") {
        const bounds = collectionBounds(target.geometry);
        if (bounds) {
          map.fitBounds(
            [[bounds.west, bounds.south], [bounds.east, bounds.north]],
            { padding: map.getCanvas().clientWidth < 600 ? 58 : 96, maxZoom: 17, duration },
          );
        }
      } else if (targetFocused && target?.resolution === "reference_position") {
        map.easeTo({ center: [target.longitude, target.latitude], zoom: Math.max(map.getZoom(), 15), duration });
      } else if (area) {
        map.fitBounds(
          [[area.bounds.west, area.bounds.south], [area.bounds.east, area.bounds.north]],
          { padding: map.getCanvas().clientWidth < 600 ? 34 : 58, duration },
        );
      }
    }

    let cancelled = false;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (cancelled) return;
      shell?.setAttribute("data-public-cartography-ready", "true");
      shell?.setAttribute("data-visual-ready", "true");
    }));
    return () => { cancelled = true; };
  }, [primaryLayer, publicCartography, styleReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("mesh-selected")) return;
    map.setFilter("mesh-selected", ["==", ["get", "mesh_code"], selection?.type === "mesh" ? selection.id : "__none__"]);
    map.setFilter("validation-selected", ["==", ["get", "sample_id"], selection?.type === "validation_sample" ? selection.id : "__none__"]);
    if (!publicCartography?.showTarget && selection?.longitude !== undefined && selection.latitude !== undefined) {
      const center = map.getCenter();
      if (Math.abs(center.lng - selection.longitude) > .0001 || Math.abs(center.lat - selection.latitude) > .0001) {
        map.easeTo({ center: [selection.longitude, selection.latitude], zoom: Math.max(map.getZoom(), selection.type === "mesh" ? 13 : 14), duration: 350 });
      }
    }
  }, [publicCartography?.showTarget, selection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const center = map.getCenter();
    if (Math.abs(center.lng - viewport.longitude) > .0008 || Math.abs(center.lat - viewport.latitude) > .0008 || Math.abs(map.getZoom() - viewport.zoom) > .2) {
      map.jumpTo({ center: [viewport.longitude, viewport.latitude], zoom: viewport.zoom, bearing: 0, pitch: 0 });
    }
  }, [viewport]);

  const lod = zoom < 10.5 ? "都市：候補メッシュ" : zoom < 13 ? "地区：メッシュ＋主要施設" : zoom < 15 ? "街区：施設＋道路" : "詳細：建物・経路";
  return (
    <div className="analytical-map-shell" data-map-engine="maplibre" data-semantic-zoom={lod}>
      <div ref={containerRef} className="analytical-map-canvas" />
      <div className="semantic-zoom-indicator" aria-live="polite"><span>表示密度</span>{lod}</div>
      <div className="north-up-indicator" aria-label="北が上です">N ↑</div>
      <noscript><p>地図を表示できません。候補一覧とInspectorから同じ情報を確認できます。</p></noscript>
    </div>
  );
});
