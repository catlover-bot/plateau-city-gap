import {
  CITY_VIEWPORTS,
  DEFAULT_SPATIAL_STATE,
  type CityId,
  type LayerPresetId,
  type MapMode,
  type ProductTask,
  type ScenePresetId,
  type SelectionType,
  type SpatialIntent,
  type SpatialResolution,
  type SpatialSelection,
  type SpatialState,
  type UrbanStateId
} from "./types";
import { scenePresetById } from "../../map/core/scenePresets";

const TASKS = new Set<ProductTask>(["discover", "detail", "try", "validate", "operate"]);
const CITIES = new Set<CityId>(["maizuru", "fujisawa"]);
const STATES = new Set<UrbanStateId>(["2020", "2023", "2025", "2040"]);
const MAP_MODES = new Set<MapMode>(["map2d", "plateau3d"]);
const INTENTS = new Set<SpatialIntent>(["discover", "inspect", "scenario", "resilience", "validate"]);
const RESOLUTIONS = new Set<SpatialResolution>(["city", "mesh", "building", "route", "site"]);
const SCENES = new Set<ScenePresetId>(["city_overview", "gap_discovery", "plateau_detail", "network_access", "scenario_compare", "hazard_stress", "temporal_change", "validation_disagreement"]);
const PRESETS = new Set<LayerPresetId>([
  "discovery", "plateau-detail", "transport", "medical", "hazard", "scenario-compare", "validation-compare"
]);
const SELECTION_TYPES = new Set<SelectionType>([
  "mesh", "building", "road", "facility", "scenario_site", "validation_sample", "temporal_change"
]);

const LEGACY_TASKS: Record<string, ProductTask> = {
  demo: "discover",
  workspace: "operate",
  validation: "validate",
  futures: "try",
  admin: "operate"
};

function finite(value: string | null, fallback: number): number {
  const parsed = value === null ? Number.NaN : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function selectionFromParams(params: URLSearchParams, city: CityId, urbanState: UrbanStateId): SpatialSelection | null {
  const ordered: Array<[string, SelectionType]> = [
    ["mesh", "mesh"],
    ["building", "building"],
    ["road", "road"],
    ["facility", "facility"],
    ["scenarioSite", "scenario_site"],
    ["validationSample", "validation_sample"],
    ["temporalChange", "temporal_change"]
  ];
  const explicitType = params.get("selectionType") as SelectionType | null;
  const explicitId = params.get("selection");
  if (explicitType && explicitId && SELECTION_TYPES.has(explicitType)) {
    return { type: explicitType, id: explicitId, city, urbanState };
  }
  const match = ordered.find(([key]) => params.has(key));
  return match ? { type: match[1], id: params.get(match[0]) ?? "", city, urbanState } : null;
}

export function parseSpatialUrl(search: string): SpatialState {
  const params = new URLSearchParams(search);
  const cityParam = params.get("city") as CityId | null;
  const city = cityParam && CITIES.has(cityParam) ? cityParam : DEFAULT_SPATIAL_STATE.city;
  const stateParam = (params.get("urbanState") ?? params.get("state")) as UrbanStateId | null;
  const urbanState = stateParam && STATES.has(stateParam) ? stateParam : DEFAULT_SPATIAL_STATE.urbanState;
  const taskParam = params.get("task") as ProductTask | null;
  const legacy = params.get("workspace");
  const explicitTask = taskParam && TASKS.has(taskParam) ? taskParam : legacy && LEGACY_TASKS[legacy] ? LEGACY_TASKS[legacy] : null;
  const intentParam = params.get("intent") as SpatialIntent | null;
  const resolutionParam = params.get("resolution") as SpatialResolution | null;
  const sceneParam = params.get("scene") as ScenePresetId | null;
  const scenePreset = sceneParam && SCENES.has(sceneParam) ? sceneParam : DEFAULT_SPATIAL_STATE.scenePreset;
  const scene = scenePresetById(scenePreset);
  const task: ProductTask = explicitTask ?? (scene.intent === "discover" ? "discover" : scene.intent === "inspect" ? "detail" : scene.intent === "scenario" || scene.intent === "resilience" ? "try" : "validate");
  const mapModeParam = params.get("mapMode") as MapMode | null;
  const mapMode = mapModeParam && MAP_MODES.has(mapModeParam) ? mapModeParam : scene.recommendedMapMode;
  const presetParam = params.get("preset") as LayerPresetId | null;
  const preset = presetParam && PRESETS.has(presetParam) ? presetParam : scene.legacyLayerPreset;
  const viewport = CITY_VIEWPORTS[city];
  const selection = selectionFromParams(params, city, urbanState);
  return {
    ...DEFAULT_SPATIAL_STATE,
    city,
    task,
    urbanState,
    selection,
    scenario: params.get("scenario"),
    validationSample: params.get("validationSample"),
    mapMode,
    intent: intentParam && INTENTS.has(intentParam) ? intentParam : scene.intent,
    resolution: resolutionParam && RESOLUTIONS.has(resolutionParam) ? resolutionParam : selection ? selection.type === "building" ? "building" : selection.type === "road" || selection.type === "validation_sample" ? "route" : selection.type === "scenario_site" || selection.type === "facility" ? "site" : "mesh" : scene.resolution,
    scenePreset,
    mapState: mapMode === "plateau3d" ? "detail3d" : task === "validate" ? "validation" : selection ? "focus" : "overview",
    preset,
    primaryLayer: params.get("layer") ?? scene.primaryLayer,
    viewport: {
      longitude: finite(params.get("lng"), viewport.longitude),
      latitude: finite(params.get("lat"), viewport.latitude),
      zoom: finite(params.get("z"), viewport.zoom),
      bearing: mapMode === "map2d" ? 0 : finite(params.get("bearing"), 0),
      pitch: mapMode === "map2d" ? 0 : finite(params.get("pitch"), 0)
    },
    inspectorOpen: params.get("inspector") !== "closed",
    demoMode: params.get("demo") === "1"
  };
}

export function spatialStateToSearch(state: SpatialState): string {
  const params = new URLSearchParams();
  params.set("city", state.city);
  params.set("task", state.task);
  params.set("workspace", state.task === "discover" ? "demo" : state.task === "validate" ? "validation" : state.task === "try" ? "futures" : state.task === "operate" ? "workspace" : "demo");
  params.set("urbanState", state.urbanState);
  params.set("mapMode", state.mapMode);
  params.set("intent", state.intent);
  params.set("resolution", state.resolution);
  params.set("scene", state.scenePreset);
  params.set("preset", state.preset);
  params.set("layer", state.primaryLayer);
  params.set("lng", state.viewport.longitude.toFixed(5));
  params.set("lat", state.viewport.latitude.toFixed(5));
  params.set("z", state.viewport.zoom.toFixed(2));
  if (state.scenario) params.set("scenario", state.scenario);
  if (state.validationSample) params.set("validationSample", state.validationSample);
  if (state.selection) {
    params.set("selectionType", state.selection.type);
    params.set("selection", state.selection.id);
    const key = state.selection.type === "scenario_site" ? "scenarioSite"
      : state.selection.type === "validation_sample" ? "validationSample"
      : state.selection.type === "temporal_change" ? "temporalChange"
      : state.selection.type;
    params.set(key, state.selection.id);
  }
  if (!state.inspectorOpen) params.set("inspector", "closed");
  if (state.demoMode) params.set("demo", "1");
  return `?${params.toString()}`;
}
