export type CityId = "maizuru" | "fujisawa";

export type PublicExperience = "landing" | "guided" | "advanced";

export type GuidedStep = 1 | 2 | 3 | 4 | 5;

export type ProductTask = "discover" | "detail" | "try" | "validate" | "operate";

export type MapMode = "map2d" | "plateau3d";

export type AnalysisLens = "none" | "urban-xray" | "service-pulse" | "changed-only" | "temporal-ghost";

export type CounterfactualState = "baseline" | "scenario" | "stress";

export type MapState = "overview" | "focus" | "detail3d" | "compare" | "placement" | "validation";

export type SpatialIntent = "discover" | "inspect" | "scenario" | "resilience" | "validate";

export type SpatialResolution =
  | "city"
  | "district"
  | "mesh"
  | "building_group"
  | "building"
  | "road"
  | "site";

export type ScenePresetId =
  | "city_overview"
  | "gap_discovery"
  | "plateau_detail"
  | "network_access"
  | "scenario_compare"
  | "hazard_stress"
  | "temporal_change"
  | "validation_disagreement";

export type UrbanStateId = "2020" | "2023" | "2025" | "2040";

export type SelectionType =
  | "district"
  | "mesh"
  | "building_group"
  | "building"
  | "road"
  | "terrain"
  | "planning"
  | "hazard"
  | "facility"
  | "scenario_site"
  | "validation_sample"
  | "temporal_change";

export interface SpatialSelection {
  type: SelectionType;
  id: string;
  city: CityId;
  urbanState: UrbanStateId;
  label?: string;
  longitude?: number;
  latitude?: number;
  properties?: Record<string, unknown>;
}

export interface SpatialViewport {
  longitude: number;
  latitude: number;
  zoom: number;
  bearing: number;
  pitch: number;
}

export type LayerPresetId =
  | "discovery"
  | "plateau-detail"
  | "transport"
  | "medical"
  | "hazard"
  | "scenario-compare"
  | "validation-compare";

export interface SpatialState {
  experience: PublicExperience;
  guidedStep: GuidedStep;
  city: CityId;
  task: ProductTask;
  urbanState: UrbanStateId;
  selection: SpatialSelection | null;
  scenario: string | null;
  validationSample: string | null;
  mapMode: MapMode;
  mapState: MapState;
  intent: SpatialIntent;
  resolution: SpatialResolution;
  scenePreset: ScenePresetId;
  preset: LayerPresetId;
  primaryLayer: string;
  viewport: SpatialViewport;
  inspectorOpen: boolean;
  savedInvestigationOpen: boolean;
  analysisLens: AnalysisLens;
  counterfactualState: CounterfactualState;
}

export type SpatialAction =
  | { type: "hydrate"; state: SpatialState }
  | { type: "set-experience"; experience: PublicExperience }
  | { type: "set-guided-step"; step: GuidedStep }
  | { type: "set-city"; city: CityId }
  | { type: "set-task"; task: ProductTask }
  | { type: "set-urban-state"; urbanState: UrbanStateId }
  | { type: "set-selection"; selection: SpatialSelection | null }
  | { type: "set-scenario"; scenario: string | null }
  | { type: "set-validation-sample"; validationSample: string | null }
  | { type: "set-map-mode"; mapMode: MapMode }
  | { type: "set-map-state"; mapState: MapState }
  | { type: "set-intent"; intent: SpatialIntent }
  | { type: "set-resolution"; resolution: SpatialResolution }
  | { type: "set-scene-preset"; scenePreset: ScenePresetId }
  | { type: "set-preset"; preset: LayerPresetId; primaryLayer: string }
  | { type: "set-primary-layer"; primaryLayer: string }
  | { type: "set-viewport"; viewport: SpatialViewport }
  | { type: "set-inspector-open"; open: boolean }
  | { type: "set-saved-investigation-open"; open: boolean }
  | { type: "set-analysis-lens"; lens: AnalysisLens }
  | { type: "set-counterfactual-state"; state: CounterfactualState };

export const CITY_VIEWPORTS: Record<CityId, SpatialViewport> = {
  maizuru: { longitude: 135.33, latitude: 35.47, zoom: 10.45, bearing: 0, pitch: 0 },
  fujisawa: { longitude: 139.47, latitude: 35.36, zoom: 11.25, bearing: 0, pitch: 0 }
};

export const DEFAULT_SPATIAL_STATE: SpatialState = {
  experience: "landing",
  guidedStep: 1,
  city: "maizuru",
  task: "discover",
  urbanState: "2025",
  selection: null,
  scenario: null,
  validationSample: null,
  mapMode: "map2d",
  mapState: "overview",
  intent: "discover",
  resolution: "city",
  scenePreset: "gap_discovery",
  preset: "discovery",
  primaryLayer: "analysis-city-gap",
  viewport: CITY_VIEWPORTS.maizuru,
  inspectorOpen: true,
  savedInvestigationOpen: false,
  analysisLens: "none",
  counterfactualState: "baseline"
};
