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
  Marker,
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
import type { GuidedMapPresentation } from "../../features/guided-spatial/guidedTypes";
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
  guidedPresentation?: GuidedMapPresentation | null;
  onAreaHover?(meshCode: string | null): void;
  onGuidedObjectSelect?(kind: "building" | "road", objectId: string): void;
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
    { id: "gsi-pale", type: "raster", source: "gsi-pale", paint: { "raster-opacity": .72, "raster-saturation": -.88, "raster-contrast": -.12, "raster-brightness-min": .18, "raster-brightness-max": .98, "raster-fade-duration": 80 } }
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
  const data = sourceData(collection);
  map.addSource(id, {
    type: "geojson",
    data,
    attribution: id.startsWith("validation") ? OSM_ATTRIBUTION : undefined,
    cluster,
    clusterMaxZoom: 13,
    clusterRadius: 46
  });
  const source = map.getSource(id) as (GeoJSONSource & { __cityGapData?: never }) | undefined;
  if (source) source.__cityGapData = data;
}

function setSource(map: MapLibreMap, id: string, collection: GeoJsonFeatureCollection | null | undefined): boolean {
  const source = map.getSource(id) as (GeoJSONSource & { __cityGapData?: never }) | undefined;
  const data = sourceData(collection);
  if (!(source instanceof GeoJSONSource) || source.__cityGapData === data) return false;
  source.setData(data);
  source.__cityGapData = data;
  return true;
}

function layerVisibility(map: MapLibreMap, id: string, visible: boolean): void {
  if (!map.getLayer(id)) return;
  const next = visible ? "visible" : "none";
  const current = map.getLayoutProperty(id, "visibility") ?? "visible";
  if (current !== next) map.setLayoutProperty(id, "visibility", next);
}

function sameStyleValue(left: unknown, right: unknown) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function setFilter(map: MapLibreMap, id: string, filter: unknown): void {
  if (!map.getLayer(id) || sameStyleValue(map.getFilter(id), filter)) return;
  map.setFilter(id, filter as never);
}

function setPaint(map: MapLibreMap, id: string, property: string, value: unknown): void {
  if (!map.getLayer(id) || sameStyleValue(map.getPaintProperty(id, property as never), value)) return;
  map.setPaintProperty(id, property as never, value as never);
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
  guidedPresentation,
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
  onAreaHover,
  onGuidedObjectSelect,
  onViewportChange,
  onReady,
  onError
}, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const publicReferenceMarker = useRef<Marker | null>(null);
  const hoveredId = useRef<string | number | null>(null);
  const [styleReady, setStyleReady] = useState(false);
  const [publicRenderTick, setPublicRenderTick] = useState(0);
  const publicCameraKey = useRef("");
  const guidedCameraKey = useRef("");
  const onSelectionRef = useRef(onSelectionChange);
  const onViewportRef = useRef(onViewportChange);
  const onAreaHoverRef = useRef(onAreaHover);
  const onGuidedObjectSelectRef = useRef(onGuidedObjectSelect);
  const [zoom, setZoom] = useState(viewport.zoom);
  const activeIdsKey = (activeLayerIdsOverride ?? activeLayerIds(preset)).join("\u001f");
  const activeIds = useMemo(
    () => new Set(activeIdsKey ? activeIdsKey.split("\u001f") : []),
    [activeIdsKey]
  );
  const publicCartographyRenderKey = [
    publicCartography?.area ? `${publicCartography.area.center.join(",")}:${publicCartography.area.radiusM}` : "no-area",
    publicCartography?.activeStory ?? "no-story",
    publicCartography?.target
      ? `${publicCartography.target.kind}:${publicCartography.target.objectId}:${publicCartography.target.resolution}:${publicCartography.target.longitude}:${publicCartography.target.latitude}:${publicCartography.target.geometry.features.length}`
      : "no-target",
    publicCartography?.showTarget ? "focused" : "context",
    publicCartography?.derivativeAvailable ? "derivative" : "fallback",
  ].join("|");
  const publicOrigin = useMemo<GeoJsonFeatureCollection>(() => publicCartography?.area ? {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      properties: { role: "origin" },
      geometry: { type: "Point", coordinates: publicCartography.area.center },
    }],
  } : EMPTY, [publicCartography?.area]);
  onSelectionRef.current = onSelectionChange;
  onViewportRef.current = onViewportChange;
  onAreaHoverRef.current = onAreaHover;
  onGuidedObjectSelectRef.current = onGuidedObjectSelect;

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
    let basemapFailed = false;
    const resumeBasemap = () => {
      if (!basemapFailed || !navigator.onLine) return;
      basemapFailed = false;
      const shell = containerRef.current?.parentElement;
      shell?.removeAttribute("data-basemap-error");
      shell?.setAttribute("data-basemap-retry", "online-event");
      shell?.setAttribute("data-map-render-state", "ready");
      layerVisibility(map, "gsi-pale", true);
    };
    window.addEventListener("online", resumeBasemap);

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
      addGeoJson(map, "public-area", EMPTY);
      addGeoJson(map, "public-area-mask", EMPTY);
      addGeoJson(map, "public-buildings", EMPTY);
      addGeoJson(map, "public-roads", EMPTY);
      addGeoJson(map, "public-planning", EMPTY);
      addGeoJson(map, "public-target", EMPTY);
      addGeoJson(map, "public-origin", EMPTY);
      addGeoJson(map, "guided-area", EMPTY);
      addGeoJson(map, "guided-buildings", EMPTY);
      addGeoJson(map, "guided-roads", EMPTY);
      addGeoJson(map, "guided-planning", EMPTY);
      addGeoJson(map, "guided-target", EMPTY);
      addGeoJson(map, "guided-section", EMPTY);
      addGeoJson(map, "guided-section-focus", EMPTY);

      map.addLayer({ id: "boundary-fill", type: "fill", source: "boundary", paint: { "fill-color": "#d9e4df", "fill-opacity": .11 } });
      map.addLayer({ id: "boundary-line", type: "line", source: "boundary", paint: { "line-color": "#315e5a", "line-width": 1.4, "line-opacity": .62 } });
      map.addLayer({ id: "mesh-fill", type: "fill", source: "meshes", minzoom: 8, maxzoom: 16.5, paint: {
        "fill-color": ["interpolate", ["linear"], ["coalesce", ["to-number", ["get", metricProperty(primaryLayer)]], 0], 0, metricColors(primaryLayer)[0], primaryLayer === "analysis-city-gap" ? .18 : .55, metricColors(primaryLayer)[1], primaryLayer === "analysis-city-gap" ? .55 : 1, metricColors(primaryLayer)[2]],
        "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], .86, ["<=", ["coalesce", ["get", "rank"], 9999], 10], dimNonSelected ? .46 : .82, ["==", ["get", "primary_eligible"], true], dimNonSelected ? .11 : .37, .055]
      } });
      map.addLayer({ id: "mesh-outline", type: "line", source: "meshes", minzoom: 10, maxzoom: 16.5, paint: { "line-color": "#506a65", "line-width": ["interpolate", ["linear"], ["zoom"], 10, .12, 14, .55], "line-opacity": ["interpolate", ["linear"], ["zoom"], 10, .08, 14, .28] } });
      map.addLayer({ id: "mesh-top-fill", type: "fill", source: "meshes", minzoom: 8, maxzoom: 13.2, filter: ["<=", ["coalesce", ["get", "rank"], 9999], 10], paint: { "fill-color": "#c38b2c", "fill-opacity": .32 } });
      map.addLayer({ id: "mesh-top-outline", type: "line", source: "meshes", minzoom: 8, maxzoom: 13.2, filter: ["<=", ["coalesce", ["get", "rank"], 9999], 10], paint: { "line-color": "#76561f", "line-width": 1.25, "line-opacity": .78 } });
      map.addLayer({ id: "mesh-selected", type: "line", source: "meshes", minzoom: 8, paint: { "line-color": "#132f31", "line-width": 3, "line-opacity": 1 }, filter: ["==", ["get", "mesh_code"], "__none__"] });
      map.addLayer({ id: "mesh-hovered", type: "line", source: "meshes", minzoom: 8, layout: { visibility: "none" }, paint: { "line-color": "#8c641c", "line-width": 3.5, "line-opacity": .96 }, filter: ["==", ["get", "mesh_code"], "__none__"] });
      map.addLayer({ id: "mesh-top-label", type: "symbol", source: "meshes", minzoom: 9.4, filter: ["<=", ["coalesce", ["get", "rank"], 9999], 10], layout: { "text-field": ["coalesce", ["get", "area_label"], ["get", "mesh_code"]], "text-size": ["interpolate", ["linear"], ["zoom"], 9.4, 11.5, 13, 13], "text-font": ["Open Sans Semibold", "Arial Unicode MS Regular"], "text-allow-overlap": false, "text-padding": 12 }, paint: { "text-color": "#493a1d", "text-halo-color": "#fbfaf6", "text-halo-width": 2.2 } });
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
      map.addLayer({ id: "public-target-halo", type: "line", source: "public-target", layout: { visibility: "none" }, paint: { "line-color": "#ffffff", "line-width": 8, "line-opacity": .96 } });
      map.addLayer({ id: "public-target-line", type: "line", source: "public-target", layout: { visibility: "none" }, paint: { "line-color": "#b7791f", "line-width": 4, "line-dasharray": [2, 1.4], "line-opacity": 1 } });
      map.addLayer({ id: "public-target-point", type: "circle", source: "public-target", filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none" }, paint: { "circle-color": "#b7791f", "circle-radius": 9, "circle-stroke-color": "#ffffff", "circle-stroke-width": 3, "circle-opacity": .98 } });

      map.addLayer({ id: "guided-planning-fill", type: "fill", source: "guided-planning", layout: { visibility: "none" }, paint: { "fill-color": "#8f7d97", "fill-opacity": .07 } });
      map.addLayer({ id: "guided-planning-line", type: "line", source: "guided-planning", layout: { visibility: "none" }, paint: { "line-color": "#76647e", "line-width": 1.1, "line-dasharray": [3, 2], "line-opacity": .46 } });
      map.addLayer({ id: "guided-roads-fill", type: "fill", source: "guided-roads", minzoom: 12, layout: { visibility: "none" }, paint: { "fill-color": "#6f8e96", "fill-opacity": .2 } });
      map.addLayer({ id: "guided-roads-line", type: "line", source: "guided-roads", minzoom: 12, layout: { visibility: "none" }, paint: { "line-color": "#476b74", "line-width": ["interpolate", ["linear"], ["zoom"], 12, .55, 17, 2.2], "line-opacity": .68 } });
      map.addLayer({ id: "guided-buildings-fill", type: "fill", source: "guided-buildings", minzoom: 12, layout: { visibility: "none" }, paint: { "fill-color": "#7f918b", "fill-opacity": .4 } });
      map.addLayer({ id: "guided-buildings-line", type: "line", source: "guided-buildings", minzoom: 12, layout: { visibility: "none" }, paint: { "line-color": "#526761", "line-width": ["interpolate", ["linear"], ["zoom"], 12, .3, 17, 1.05], "line-opacity": .56 } });
      map.addLayer({ id: "guided-area-fill", type: "fill", source: "guided-area", layout: { visibility: "none" }, paint: { "fill-color": "#1e6f62", "fill-opacity": .08 } });
      map.addLayer({ id: "guided-area-halo", type: "line", source: "guided-area", layout: { visibility: "none" }, paint: { "line-color": "#ffffff", "line-width": 7, "line-opacity": .9 } });
      map.addLayer({ id: "guided-area-line", type: "line", source: "guided-area", layout: { visibility: "none" }, paint: { "line-color": "#12574e", "line-width": 3.6, "line-opacity": 1 } });
      map.addLayer({ id: "guided-area-label", type: "symbol", source: "guided-area", minzoom: 9.4, layout: { visibility: "none", "text-field": ["coalesce", ["get", "area_label"], ["get", "mesh_code"]], "text-size": 14, "text-font": ["Open Sans Bold", "Arial Unicode MS Regular"], "text-allow-overlap": true, "text-offset": [0, 1.25] }, paint: { "text-color": "#123f38", "text-halo-color": "#ffffff", "text-halo-width": 2.8 } });
      map.addLayer({ id: "guided-section-halo", type: "line", source: "guided-section", layout: { visibility: "none" }, paint: { "line-color": "#ffffff", "line-width": 7, "line-opacity": .92 } });
      map.addLayer({ id: "guided-section-line", type: "line", source: "guided-section", layout: { visibility: "none", "line-cap": "round" }, paint: { "line-color": "#7b4b91", "line-width": 3.8, "line-opacity": 1 } });
      map.addLayer({ id: "guided-section-endpoint-dots", type: "circle", source: "guided-section", filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none" }, paint: { "circle-color": "#7b4b91", "circle-radius": 6.5, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2.5 } });
      map.addLayer({ id: "guided-section-endpoints", type: "symbol", source: "guided-section", filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none", "text-field": ["get", "endpoint"], "text-size": 14, "text-font": ["Open Sans Bold", "Arial Unicode MS Regular"], "text-offset": [0, -1.2], "text-allow-overlap": true }, paint: { "text-color": "#5d306f", "text-halo-color": "#ffffff", "text-halo-width": 2.5 } });
      map.addLayer({ id: "guided-section-focus", type: "circle", source: "guided-section-focus", layout: { visibility: "none" }, paint: { "circle-color": "#8d5f9f", "circle-radius": 6, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 } });
      map.addLayer({ id: "guided-target-fill", type: "fill", source: "guided-target", layout: { visibility: "none" }, paint: { "fill-color": "#d28b24", "fill-opacity": .36 } });
      map.addLayer({ id: "guided-target-halo", type: "line", source: "guided-target", layout: { visibility: "none" }, paint: { "line-color": "#ffffff", "line-width": 10, "line-opacity": .98 } });
      map.addLayer({ id: "guided-target-line", type: "line", source: "guided-target", layout: { visibility: "none" }, paint: { "line-color": "#a9660d", "line-width": 4.5, "line-opacity": 1 } });
      map.addLayer({ id: "guided-target-point", type: "circle", source: "guided-target", filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none" }, paint: { "circle-color": "#a9660d", "circle-radius": 10, "circle-stroke-color": "#ffffff", "circle-stroke-width": 4, "circle-opacity": 1 } });
      map.addLayer({ id: "guided-target-label", type: "symbol", source: "guided-target", layout: { visibility: "none", "text-field": ["get", "map_label"], "text-size": 13, "text-font": ["Open Sans Semibold", "Arial Unicode MS Regular"], "text-offset": [0, 1.5], "text-padding": 12, "text-allow-overlap": true, "text-ignore-placement": true }, paint: { "text-color": "#704505", "text-halo-color": "#ffffff", "text-halo-width": 2.8 } });

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
        const properties = event.features?.[0]?.properties as Record<string, unknown> | undefined;
        onAreaHoverRef.current?.(properties?.mesh_code ? String(properties.mesh_code) : null);
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "mesh-fill", () => {
        if (hoveredId.current !== null) map.setFeatureState({ source: "meshes", id: hoveredId.current }, { hover: false });
        hoveredId.current = null;
        onAreaHoverRef.current?.(null);
        map.getCanvas().style.cursor = "";
      });
      const guidedObjectSelection = (kind: "building" | "road") => (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        const objectId = String(feature?.id ?? feature?.properties?.surface_id ?? feature?.properties?.object_id ?? "");
        if (objectId) onGuidedObjectSelectRef.current?.(kind, objectId);
      };
      map.on("click", "guided-buildings-fill", guidedObjectSelection("building"));
      map.on("click", "guided-roads-fill", guidedObjectSelection("road"));
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
      containerRef.current?.parentElement?.setAttribute("data-map-render-state", basemapFailed ? "degraded" : "ready");
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
        if (!basemapFailed) {
          basemapFailed = true;
          layerVisibility(map, "gsi-pale", false);
        }
        shell?.setAttribute("data-map-render-state", "degraded");
        shell?.setAttribute("data-visual-ready", "true");
        shell?.setAttribute("data-basemap-error", message);
        shell?.setAttribute("data-basemap-retry", "waiting-for-online");
        return;
      }
      criticalError = true;
      containerRef.current?.parentElement?.setAttribute("data-visual-ready", "false");
      containerRef.current?.parentElement?.setAttribute("data-map-render-state", "degraded");
      containerRef.current?.parentElement?.setAttribute("data-critical-error", message);
      onError?.(message);
    });
    return () => {
      window.removeEventListener("online", resumeBasemap);
      setStyleReady(false);
      publicReferenceMarker.current?.remove();
      publicReferenceMarker.current = null;
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
    if (!styleReady || !map) return;
    const publicStyleReady = ["public-area", "public-area-mask", "public-buildings", "public-roads", "public-planning", "public-target", "public-origin"]
      .every((id) => Boolean(map.getSource(id)))
      && ["public-area-fill", "public-area-line", "public-target-line", "public-origin-point"]
        .every((id) => Boolean(map.getLayer(id)));
    if (!publicStyleReady) {
      const retry = () => setPublicRenderTick((value) => value + 1);
      const fallback = window.setTimeout(retry, 100);
      map.once("styledata", retry);
      return () => { window.clearTimeout(fallback); map.off("styledata", retry); };
    }
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
    const renderKey = publicCartographyRenderKey;
    const renderChanged = shell?.getAttribute("data-public-render-key") !== renderKey;

    if (renderChanged) {
      shell?.setAttribute("data-visual-ready", "false");
      shell?.setAttribute("data-public-cartography-ready", "false");
      shell?.setAttribute("data-public-render-key", renderKey);
    }
    shell?.setAttribute("data-public-story", story ?? "none");
    shell?.setAttribute("data-public-area-visible", String(areaVisible));
    shell?.setAttribute("data-public-area-radius-m", area ? String(area.radiusM) : "none");
    shell?.setAttribute("data-target-resolution", target?.resolution ?? "none");

    setSource(map, "public-area", area?.polygon);
    setSource(map, "public-area-mask", area?.outsideMask);
    if (story === "building-use" && presentation?.data?.buildings) {
      setSource(map, "public-buildings", presentation.data.buildings);
    }
    if (story === "urban-planning" && presentation?.data?.planning) {
      setSource(map, "public-planning", presentation.data.planning);
    }
    setSource(map, "public-target", target?.geometry);
    setSource(map, "public-origin", area ? publicOrigin : EMPTY);

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

    const areaFilter = area?.polygon.features[0]?.geometry
      ? ["within", area.polygon.features[0].geometry]
      : true;
    const derivativeFilter = area && presentation
      && presentation.data && area.radiusM < presentation.data.manifest.scope.radius_m
      ? areaFilter
      : true;
    for (const id of ["public-buildings-fill", "public-buildings-line", "public-planning-fill", "public-planning-line"]) {
      setFilter(map, id, derivativeFilter);
    }
    for (const prefix of ["station", "bus"]) {
      setFilter(map, `${prefix}-clusters`, ["all", ["has", "point_count"], areaFilter]);
      setFilter(map, `${prefix}-cluster-count`, ["all", ["has", "point_count"], areaFilter]);
      setFilter(map, `${prefix}-point`, ["all", ["!", ["has", "point_count"]], areaFilter]);
    }

    if (story === "population-age") {
      setPaint(map, "mesh-fill", "fill-color", [
        "interpolate", ["linear"],
        ["coalesce", ["to-number", ["get", "elderly_population_percentile"]], 0],
        0, "#dcebe6",
        .5, "#82b5a8",
        1, "#2f7466",
      ]);
      setPaint(map, "mesh-fill", "fill-opacity", [
        "case",
        ["==", ["get", "elderly_population_percentile"], null], .06,
        .54,
      ]);
    }

    const exactTargetVisible = targetVisible && targetExact;
    layerVisibility(map, "public-target-fill", exactTargetVisible && (targetTypes.has("Polygon") || targetTypes.has("MultiPolygon")));
    layerVisibility(map, "public-target-halo", exactTargetVisible);
    layerVisibility(map, "public-target-line", exactTargetVisible);
    layerVisibility(map, "public-target-point", targetVisible && !targetExact && targetTypes.has("Point"));
    if (targetExact) {
      setPaint(map, "public-target-fill", "fill-color", targetColor);
      setPaint(map, "public-target-line", "line-color", targetColor);
      setPaint(map, "public-target-line", "line-dasharray", targetFocused ? [1, .01] : [2, 1.4]);
    } else {
      setPaint(map, "public-target-point", "circle-color", targetColor);
      setPaint(map, "public-target-point", "circle-radius", targetFocused ? 12 : 9);
    }
    setPaint(map, "public-area-line", "line-color", targetFocused && target?.resolution === "area_fallback" ? targetColor : "#1e6f62");
    setPaint(map, "public-area-line", "line-dasharray", targetFocused && target?.resolution === "area_fallback" ? [2, 1.4] : [1, .01]);

    const showReferenceMarker = Boolean(targetVisible && !targetExact && targetTypes.has("Point") && target);
    if (showReferenceMarker && target) {
      if (!publicReferenceMarker.current) {
        const element = document.createElement("span");
        element.className = "public-reference-target-marker";
        element.setAttribute("role", "img");
        element.setAttribute("aria-label", "確認する場所として登録された位置");
        publicReferenceMarker.current = new Marker({ element, anchor: "center" })
          .setLngLat([target.longitude, target.latitude])
          .addTo(map);
      }
      publicReferenceMarker.current.setLngLat([target.longitude, target.latitude]);
    } else {
      publicReferenceMarker.current?.remove();
      publicReferenceMarker.current = null;
    }

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
          { padding: Math.max(34, Math.round(Math.min(map.getCanvas().clientWidth, map.getCanvas().clientHeight) * .2)), duration },
        );
      }
    }

    let cancelled = false;
    let readinessTimer = 0;
    const localSourceIds = ["public-area", "public-area-mask", "public-origin"];
    if (target?.geometry.features.length) localSourceIds.push("public-target");
    if (story === "building-use" && presentation?.derivativeAvailable) localSourceIds.push("public-buildings");
    if (story === "urban-planning" && presentation?.derivativeAvailable) localSourceIds.push("public-planning");
    const markReady = () => {
      if (cancelled) return;
      shell?.setAttribute("data-public-pending-sources", "");
      shell?.setAttribute("data-public-cartography-ready", "true");
      shell?.setAttribute("data-visual-ready", "true");
    };
    const awaitLocalSources = () => {
      if (cancelled) return;
      const pendingSourceIds = localSourceIds.filter((id) => !map.isSourceLoaded(id));
      shell?.setAttribute("data-public-pending-sources", pendingSourceIds.join(","));
      if (!pendingSourceIds.length) {
        markReady();
        return;
      }
      readinessTimer = window.setTimeout(awaitLocalSources, 50);
    };
    awaitLocalSources();
    return () => {
      cancelled = true;
      window.clearTimeout(readinessTimer);
    };
  }, [primaryLayer, publicCartography, publicCartographyRenderKey, publicOrigin, publicRenderTick, styleReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!styleReady || !map || !guidedPresentation) return;
    const presentation = guidedPresentation;
    const shell = containerRef.current?.parentElement;
    const context = presentation.context;
    const isIntro = presentation.story === "intro";
    const isFind = presentation.story === "find";
    const isUnderstand = presentation.story === "understand";
    const isVerify = presentation.story === "verify";
    const contextVisible = (isUnderstand || isVerify) && presentation.contextStatus === "ready";
    const sectionVisible = isUnderstand && presentation.sectionLine.features.length > 0;
    const targetVisible = isVerify && presentation.target.features.length > 0;
    const exactTargetVisible = targetVisible && presentation.targetResolution === "exact";

    if (isIntro || isFind || isVerify) map.setPadding({ top: 0, right: 0, bottom: 0, left: 0 });

    // Invalidate the previous scene before replacing any source. Consumers
    // must never mistake a rendered prior scene for the newly selected Area.
    shell?.setAttribute("data-guided-visual-ready", "false");
    shell?.setAttribute("data-visual-ready", "false");
    shell?.setAttribute("data-guided-story", presentation.story);
    shell?.setAttribute("data-guided-area-id", presentation.areaId);
    shell?.setAttribute("data-guided-context-status", presentation.contextStatus);
    shell?.setAttribute("data-guided-section-visible", String(sectionVisible));
    shell?.setAttribute("data-guided-target-resolution", presentation.targetResolution);
    shell?.setAttribute("data-guided-target-kind", presentation.targetKind);

    setPaint(map, "gsi-pale", "raster-opacity", isIntro ? .7 : isFind ? .61 : isUnderstand ? .54 : .46);
    setPaint(map, "gsi-pale", "raster-saturation", isIntro ? -.86 : -.95);
    setPaint(map, "gsi-pale", "raster-contrast", isIntro ? -.1 : -.16);

    setSource(map, "guided-area", presentation.area);
    setSource(map, "guided-buildings", context?.layers.buildings);
    setSource(map, "guided-roads", context?.layers.roads);
    setSource(map, "guided-planning", context?.layers.planning);
    setSource(map, "guided-target", presentation.target);
    setSource(map, "guided-section", presentation.sectionLine);
    setSource(map, "guided-section-focus", presentation.sectionFocus);

    layerVisibility(map, "mesh-fill", isIntro || isFind);
    layerVisibility(map, "mesh-outline", isIntro || isFind);
    setPaint(map, "mesh-fill", "fill-opacity", isIntro ? .1 : ["case", ["boolean", ["feature-state", "hover"], false], .24, ["==", ["get", "primary_eligible"], true], .12, .035]);
    const unselectedShortlist = presentation.shortlistIds.filter((id) => id !== presentation.areaId);
    const shortlistFilter = ["in", ["get", "mesh_code"], ["literal", unselectedShortlist]];
    setFilter(map, "mesh-top-fill", shortlistFilter);
    setFilter(map, "mesh-top-outline", shortlistFilter);
    setFilter(map, "mesh-top-label", shortlistFilter);
    layerVisibility(map, "mesh-top-fill", isFind);
    layerVisibility(map, "mesh-top-outline", isFind);
    layerVisibility(map, "mesh-top-label", isFind);
    layerVisibility(map, "mesh-selected", false);
    layerVisibility(map, "mesh-hovered", isFind && Boolean(presentation.hoveredAreaId));
    setFilter(map, "mesh-hovered", ["==", ["get", "mesh_code"], presentation.hoveredAreaId ?? "__none__"]);
    layerVisibility(map, "guided-area-fill", !isIntro);
    layerVisibility(map, "guided-area-halo", !isIntro);
    layerVisibility(map, "guided-area-line", !isIntro);
    layerVisibility(map, "guided-area-label", isFind);
    layerVisibility(map, "guided-buildings-fill", contextVisible);
    layerVisibility(map, "guided-buildings-line", contextVisible);
    layerVisibility(map, "guided-roads-fill", contextVisible);
    layerVisibility(map, "guided-roads-line", contextVisible);
    layerVisibility(map, "guided-planning-fill", contextVisible);
    layerVisibility(map, "guided-planning-line", contextVisible);
    layerVisibility(map, "guided-section-halo", sectionVisible);
    layerVisibility(map, "guided-section-line", sectionVisible);
    layerVisibility(map, "guided-section-endpoint-dots", sectionVisible);
    layerVisibility(map, "guided-section-endpoints", sectionVisible);
    layerVisibility(map, "guided-section-focus", sectionVisible && presentation.sectionFocus.features.length > 0);
    layerVisibility(map, "guided-target-fill", exactTargetVisible);
    layerVisibility(map, "guided-target-halo", exactTargetVisible);
    // The fallback target remains the selected Area itself. Keep the target
    // line active for the existing target-state contract while the Area
    // styling communicates that this is a range, not a resolved object.
    layerVisibility(map, "guided-target-line", targetVisible);
    layerVisibility(map, "guided-target-point", exactTargetVisible);
    layerVisibility(map, "guided-target-label", exactTargetVisible);
    setPaint(map, "guided-buildings-fill", "fill-opacity", isVerify ? .1 : .4);
    setPaint(map, "guided-buildings-line", "line-opacity", isVerify ? .24 : .56);
    setPaint(map, "guided-roads-fill", "fill-opacity", isVerify ? .08 : .2);
    setPaint(map, "guided-roads-line", "line-opacity", isVerify ? .3 : .68);
    setPaint(map, "guided-planning-fill", "fill-opacity", isVerify ? .025 : .07);
    setPaint(map, "guided-planning-line", "line-opacity", isVerify ? .18 : .46);
    setPaint(map, "guided-target-line", "line-dasharray", presentation.targetResolution === "area_fallback" ? [2, 1.4] : [1, .01]);
    setPaint(map, "guided-area-fill", "fill-opacity", isFind ? .2 : isVerify ? presentation.targetResolution === "area_fallback" ? .15 : .025 : .055);
    setPaint(map, "guided-area-halo", "line-width", isVerify && presentation.targetResolution === "area_fallback" ? 9 : 7);
    setPaint(map, "guided-area-line", "line-color", isVerify && presentation.targetResolution === "area_fallback" ? "#a9660d" : "#12574e");
    setPaint(map, "guided-area-line", "line-width", isVerify && presentation.targetResolution === "area_fallback" ? 4.5 : 3.6);
    setPaint(map, "guided-area-line", "line-dasharray", isVerify && presentation.targetResolution === "area_fallback" ? [2, 1.4] : [1, .01]);

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const duration = reducedMotion ? 0 : 320;
    const cameraKey = `${presentation.story}:${presentation.areaId}:${presentation.targetResolution}:${presentation.contextStatus}:${sectionVisible}`;
    if (!isIntro && !isFind && cameraKey !== guidedCameraKey.current) {
      guidedCameraKey.current = cameraKey;
      const collection = isVerify && presentation.targetResolution === "exact"
        ? presentation.target
        : presentation.area;
      const bounds = collectionBounds(collection);
      if (bounds) {
        const currentBounds = map.getBounds();
        const exactTargetAlreadyLegible = isVerify
          && presentation.targetResolution === "exact"
          && map.getZoom() >= 14.5
          && currentBounds.contains([bounds.west, bounds.south])
          && currentBounds.contains([bounds.east, bounds.north]);
        if (!exactTargetAlreadyLegible) {
          map.fitBounds(
            [[bounds.west, bounds.south], [bounds.east, bounds.north]],
            {
              padding: map.getCanvas().clientWidth < 600
                ? 44
                : isUnderstand && sectionVisible
                  ? { top: 54, right: 82, bottom: map.getCanvas().clientHeight <= 700 ? 370 : 455, left: 82 }
                  : isVerify ? 112 : 82,
              maxZoom: isVerify ? 17 : 15.7,
              duration,
            },
          );
        }
      }
    }

    let cancelled = false;
    let readinessTimer = 0;
    let stableFrames = 0;
    const sourceIds = ["guided-area"];
    if (contextVisible) sourceIds.push("guided-buildings", "guided-roads", "guided-planning");
    if (sectionVisible) sourceIds.push("guided-section");
    if (targetVisible) sourceIds.push("guided-target");
    const awaitGuidedSources = () => {
      if (cancelled) return;
      const pending = sourceIds.filter((id) => !map.isSourceLoaded(id));
      shell?.setAttribute("data-guided-pending-sources", pending.join(","));
      if (pending.length) {
        stableFrames = 0;
        shell?.setAttribute("data-guided-visual-ready", "false");
        readinessTimer = window.setTimeout(awaitGuidedSources, 50);
        return;
      }

      // A source can report loaded before MapLibre has painted the camera and
      // freshly replaced GeoJSON together. Require a short series of stable
      // polls and explicitly request a repaint so background/headless tabs do
      // not depend on requestAnimationFrame scheduling.
      stableFrames += 1;
      if (stableFrames < 4) {
        map.triggerRepaint();
        readinessTimer = window.setTimeout(awaitGuidedSources, 50);
        return;
      }
      shell?.setAttribute("data-guided-visual-ready", "true");
      shell?.setAttribute("data-visual-ready", "true");
    };
    awaitGuidedSources();
    return () => {
      cancelled = true;
      window.clearTimeout(readinessTimer);
    };
  }, [guidedPresentation, styleReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("mesh-selected")) return;
    setFilter(map, "mesh-selected", ["==", ["get", "mesh_code"], selection?.type === "mesh" ? selection.id : "__none__"]);
    setFilter(map, "validation-selected", ["==", ["get", "sample_id"], selection?.type === "validation_sample" ? selection.id : "__none__"]);
    if (!publicCartography?.showTarget && !guidedPresentation && selection?.longitude !== undefined && selection.latitude !== undefined) {
      const center = map.getCenter();
      if (Math.abs(center.lng - selection.longitude) > .0001 || Math.abs(center.lat - selection.latitude) > .0001) {
        map.easeTo({ center: [selection.longitude, selection.latitude], zoom: Math.max(map.getZoom(), selection.type === "mesh" ? 13 : 14), duration: 350 });
      }
    }
  }, [guidedPresentation, publicCartography?.showTarget, selection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (guidedPresentation && guidedPresentation.story !== "find") return;
    const center = map.getCenter();
    if (Math.abs(center.lng - viewport.longitude) > .0008 || Math.abs(center.lat - viewport.latitude) > .0008 || Math.abs(map.getZoom() - viewport.zoom) > .2) {
      map.jumpTo({ center: [viewport.longitude, viewport.latitude], zoom: viewport.zoom, bearing: 0, pitch: 0 });
    }
  }, [guidedPresentation, viewport]);

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
