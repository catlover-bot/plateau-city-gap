import { SCENE_PRESETS } from "../../map/core/scenePresets";
import { CITY_VIEWPORTS, type SelectionType, type SpatialAction, type SpatialResolution, type SpatialState } from "./types";

const TASK_PRESETS = {
  discover: ["discovery", "analysis-city-gap", "overview", "discover", "gap_discovery"],
  detail: ["plateau-detail", "plateau-buildings", "focus", "inspect", "plateau_detail"],
  try: ["scenario-compare", "scenario-footprint", "compare", "scenario", "scenario_compare"],
  validate: ["validation-compare", "validation-disagreement", "validation", "validate", "validation_disagreement"],
  operate: ["discovery", "analysis-city-gap", "focus", "inspect", "gap_discovery"]
} as const;

const RESOLUTION_BY_SELECTION: Record<SelectionType, SpatialResolution> = {
  district: "district",
  mesh: "mesh",
  building_group: "building_group",
  building: "building",
  road: "road",
  terrain: "building_group",
  planning: "site",
  hazard: "site",
  facility: "site",
  scenario_site: "site",
  validation_sample: "road",
  temporal_change: "building",
};

export function spatialReducer(state: SpatialState, action: SpatialAction): SpatialState {
  switch (action.type) {
    case "hydrate": return action.state;
    case "set-experience": return {
      ...state,
      experience: action.experience,
      guidedStep: action.experience === "landing" ? 1 : state.guidedStep,
    };
    case "set-guided-step": return {
      ...state,
      experience: action.step >= 5 ? "advanced" : "guided",
      guidedStep: action.step,
      guidedStory: action.step <= 2 ? "find" : action.step === 3 ? "understand" : "verify",
      task: action.step >= 5 ? "operate" : state.task,
    };
    case "set-guided-story": return {
      ...state,
      experience: "guided",
      guidedStory: action.story,
      guidedStep: action.story === "intro" || action.story === "find" ? 1 : action.story === "understand" ? 2 : 3,
    };
    case "set-city": return {
      ...state,
      city: action.city,
      viewport: CITY_VIEWPORTS[action.city],
      selection: null,
      validationSample: null,
      mapState: "overview"
    };
    case "set-task": {
      const [preset, primaryLayer, mapState, intent, scenePreset] = TASK_PRESETS[action.task];
      const scene = SCENE_PRESETS[scenePreset];
      return { ...state, task: action.task, preset, primaryLayer, mapState, intent, scenePreset, savedInvestigationOpen: false, analysisLens: scene.analysisLens, counterfactualState: action.task === "try" ? "scenario" : "baseline" };
    }
    case "set-urban-state": return {
      ...state,
      urbanState: action.urbanState,
      selection: state.selection ? { ...state.selection, urbanState: action.urbanState } : null
    };
    case "set-selection": return {
      ...state,
      selection: action.selection,
      resolution: action.selection ? RESOLUTION_BY_SELECTION[action.selection.type] : "city",
      inspectorOpen: action.selection ? true : state.inspectorOpen,
      mapState: action.selection ? state.mapMode === "plateau3d" ? "detail3d" : state.task === "validate" ? "validation" : "focus" : "overview",
      validationSample: action.selection?.type === "validation_sample" ? action.selection.id : state.validationSample
    };
    case "set-scenario": return { ...state, scenario: action.scenario };
    case "set-validation-sample": return { ...state, validationSample: action.validationSample };
    case "set-map-mode": return {
      ...state,
      mapMode: action.mapMode,
      mapState: action.mapMode === "plateau3d" ? "detail3d" : state.task === "validate" ? "validation" : state.selection ? "focus" : "overview",
      viewport: { ...state.viewport, bearing: 0, pitch: action.mapMode === "plateau3d" ? 48 : 0 }
    };
    case "set-map-state": return { ...state, mapState: action.mapState };
    case "set-intent": return { ...state, intent: action.intent };
    case "set-resolution": return { ...state, resolution: action.resolution };
    case "set-scene-preset": {
      const scene = SCENE_PRESETS[action.scenePreset];
      return {
        ...state,
        scenePreset: scene.id,
        intent: scene.intent,
        preset: scene.legacyLayerPreset,
        primaryLayer: scene.primaryLayer,
        mapMode: scene.recommendedMapMode,
        mapState: scene.recommendedMapMode === "plateau3d" ? "detail3d" : scene.intent === "validate" ? "validation" : scene.intent === "scenario" ? "compare" : state.selection ? "focus" : "overview",
        analysisLens: scene.analysisLens,
        counterfactualState: scene.intent === "resilience" ? "stress" : scene.intent === "scenario" ? "scenario" : "baseline",
      };
    }
    case "set-preset": return { ...state, preset: action.preset, primaryLayer: action.primaryLayer };
    case "set-primary-layer": return { ...state, primaryLayer: action.primaryLayer };
    case "set-viewport": return { ...state, viewport: action.viewport };
    case "set-inspector-open": return { ...state, inspectorOpen: action.open };
    case "set-saved-investigation-open": return { ...state, savedInvestigationOpen: action.open };
    case "set-analysis-lens": return { ...state, analysisLens: action.lens };
    case "set-counterfactual-state": return { ...state, counterfactualState: action.state };
  }
}
