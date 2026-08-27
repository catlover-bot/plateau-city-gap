import { CITY_VIEWPORTS, type SpatialAction, type SpatialState } from "./types";

const TASK_PRESETS = {
  discover: ["discovery", "analysis-city-gap", "overview"],
  detail: ["plateau-detail", "plateau-buildings", "focus"],
  try: ["scenario-compare", "scenario-footprint", "compare"],
  validate: ["validation-compare", "validation-disagreement", "validation"],
  operate: ["discovery", "analysis-city-gap", "focus"]
} as const;

export function spatialReducer(state: SpatialState, action: SpatialAction): SpatialState {
  switch (action.type) {
    case "hydrate": return action.state;
    case "set-city": return {
      ...state,
      city: action.city,
      viewport: CITY_VIEWPORTS[action.city],
      selection: null,
      validationSample: null,
      mapState: "overview"
    };
    case "set-task": {
      const [preset, primaryLayer, mapState] = TASK_PRESETS[action.task];
      return { ...state, task: action.task, preset, primaryLayer, mapState, demoMode: false };
    }
    case "set-urban-state": return {
      ...state,
      urbanState: action.urbanState,
      selection: state.selection ? { ...state.selection, urbanState: action.urbanState } : null
    };
    case "set-selection": return {
      ...state,
      selection: action.selection,
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
    case "set-preset": return { ...state, preset: action.preset, primaryLayer: action.primaryLayer };
    case "set-primary-layer": return { ...state, primaryLayer: action.primaryLayer };
    case "set-viewport": return { ...state, viewport: action.viewport };
    case "set-inspector-open": return { ...state, inspectorOpen: action.open };
    case "set-demo-mode": return { ...state, demoMode: action.enabled };
  }
}
