import {
  CITY_VIEWPORTS,
  DEFAULT_SPATIAL_STATE,
  type AnalysisLens,
  type CityId,
  type GuidedStep,
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
const RESOLUTIONS = new Set<SpatialResolution>([
  "city", "district", "mesh", "building_group", "building", "road", "site"
]);
const SCENES = new Set<ScenePresetId>(["city_overview", "gap_discovery", "plateau_detail", "network_access", "scenario_compare", "hazard_stress", "temporal_change", "validation_disagreement"]);
const PRESETS = new Set<LayerPresetId>([
  "discovery", "plateau-detail", "transport", "medical", "hazard", "scenario-compare", "validation-compare"
]);
const SELECTION_TYPES = new Set<SelectionType>([
  "district", "mesh", "building_group", "building", "road", "terrain", "planning", "hazard",
  "facility", "scenario_site", "validation_sample", "temporal_change"
]);
const ANALYSIS_LENSES = new Set<AnalysisLens>(["none", "urban-xray", "service-pulse", "changed-only", "temporal-ghost"]);
const COUNTERFACTUAL_STATES = new Set(["baseline", "scenario", "stress"] as const);
const GUIDED_STEPS = new Set<GuidedStep>([1, 2, 3, 4, 5]);

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
  const rawSelectionLongitude = params.get("selectionLng") ?? params.get("lng");
  const rawSelectionLatitude = params.get("selectionLat") ?? params.get("lat");
  const selectionLongitude = rawSelectionLongitude === null ? Number.NaN : Number(rawSelectionLongitude);
  const selectionLatitude = rawSelectionLatitude === null ? Number.NaN : Number(rawSelectionLatitude);
  const position = Number.isFinite(selectionLongitude) && Number.isFinite(selectionLatitude)
    ? { longitude: selectionLongitude, latitude: selectionLatitude }
    : {};
  const ordered: Array<[string, SelectionType]> = [
    ["district", "district"],
    ["mesh", "mesh"],
    ["buildingGroup", "building_group"],
    ["building", "building"],
    ["road", "road"],
    ["terrain", "terrain"],
    ["planning", "planning"],
    ["hazard", "hazard"],
    ["facility", "facility"],
    ["scenarioSite", "scenario_site"],
    ["validationSample", "validation_sample"],
    ["temporalChange", "temporal_change"]
  ];
  const explicitType = params.get("selectionType") as SelectionType | null;
  const explicitId = params.get("selection");
  if (explicitType && explicitId && SELECTION_TYPES.has(explicitType)) {
    return { type: explicitType, id: explicitId, city, urbanState, ...position };
  }
  const match = ordered.find(([key]) => params.has(key));
  return match ? { type: match[1], id: params.get(match[0]) ?? "", city, urbanState, ...position } : null;
}

export function parseSpatialUrl(search: string): SpatialState {
  const params = new URLSearchParams(search);
  const parsedGuidedStep = Number(params.get("guide"));
  const guidedStep = GUIDED_STEPS.has(parsedGuidedStep as GuidedStep)
    ? parsedGuidedStep as GuidedStep
    : DEFAULT_SPATIAL_STATE.guidedStep;
  const requestedExperience = params.get("experience");
  const experience = requestedExperience === "advanced" || params.get("advanced") === "1"
    ? "advanced" as const
    : requestedExperience === "guided" || params.has("guide")
      ? "guided" as const
      : "landing" as const;
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
  const lensParam = params.get("lens") as AnalysisLens | null;
  const twinParam = params.get("twin") as "baseline" | "scenario" | "stress" | null;
  const task: ProductTask = explicitTask ?? (scene.intent === "discover" ? "discover" : scene.intent === "inspect" ? "detail" : scene.intent === "scenario" || scene.intent === "resilience" ? "try" : "validate");
  const mapModeParam = params.get("mapMode") as MapMode | null;
  const mapMode = mapModeParam && MAP_MODES.has(mapModeParam) ? mapModeParam : scene.recommendedMapMode;
  const presetParam = params.get("preset") as LayerPresetId | null;
  const preset = presetParam && PRESETS.has(presetParam) ? presetParam : scene.legacyLayerPreset;
  const viewport = CITY_VIEWPORTS[city];
  const selection = selectionFromParams(params, city, urbanState);
  return {
    ...DEFAULT_SPATIAL_STATE,
    experience,
    guidedStep,
    city,
    task,
    urbanState,
    selection,
    scenario: params.get("scenario"),
    validationSample: params.get("validationSample"),
    mapMode,
    intent: intentParam && INTENTS.has(intentParam) ? intentParam : scene.intent,
    resolution: resolutionParam && RESOLUTIONS.has(resolutionParam)
      ? resolutionParam
      : selection
        ? selection.type === "district"
          ? "district"
          : selection.type === "building_group"
            ? "building_group"
            : selection.type === "building"
              ? "building"
              : selection.type === "road" || selection.type === "validation_sample"
                ? "road"
                : selection.type === "scenario_site" || selection.type === "facility" || selection.type === "planning" || selection.type === "hazard"
                  ? "site"
                  : "mesh"
        : DEFAULT_SPATIAL_STATE.resolution,
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
    savedInvestigationOpen: params.get("saved") === "1",
    analysisLens: lensParam && ANALYSIS_LENSES.has(lensParam) ? lensParam : scene.analysisLens,
    counterfactualState: twinParam && COUNTERFACTUAL_STATES.has(twinParam)
      ? twinParam
      : scene.intent === "resilience"
        ? "stress"
        : scene.intent === "scenario"
          ? "scenario"
          : "baseline"
  };
}

export function spatialStateToSearch(state: SpatialState, passthrough?: URLSearchParams): string {
  const params = new URLSearchParams();
  params.set("experience", state.experience);
  if (state.experience === "guided") params.set("guide", String(state.guidedStep));
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
  params.set("lens", state.analysisLens);
  params.set("twin", state.counterfactualState);
  params.set("lng", state.viewport.longitude.toFixed(5));
  params.set("lat", state.viewport.latitude.toFixed(5));
  params.set("z", state.viewport.zoom.toFixed(2));
  if (state.scenario) params.set("scenario", state.scenario);
  if (state.validationSample) params.set("validationSample", state.validationSample);
  if (state.selection) {
    params.set("selectionType", state.selection.type);
    params.set("selection", state.selection.id);
    const key = state.selection.type === "building_group" ? "buildingGroup"
      : state.selection.type === "scenario_site" ? "scenarioSite"
      : state.selection.type === "validation_sample" ? "validationSample"
      : state.selection.type === "temporal_change" ? "temporalChange"
      : state.selection.type;
    params.set(key, state.selection.id);
    if (state.selection.longitude !== undefined && state.selection.latitude !== undefined) {
      params.set("selectionLng", state.selection.longitude.toFixed(7));
      params.set("selectionLat", state.selection.latitude.toFixed(7));
    }
  }
  if (!state.inspectorOpen) params.set("inspector", "closed");
  if (state.savedInvestigationOpen) params.set("saved", "1");
  const buildingSource = passthrough?.get("buildingSource");
  if (buildingSource === "verified-local" || buildingSource === "spatial-pack") {
    params.set("buildingSource", buildingSource);
  }
  const section = passthrough?.get("section");
  if (section === "open" || section === "closed") params.set("section", section);
  return `?${params.toString()}`;
}
