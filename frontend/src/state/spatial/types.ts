export type CityId = "maizuru" | "fujisawa";

export type ProductTask = "discover" | "detail" | "try" | "validate" | "operate";

export type MapMode = "map2d" | "plateau3d";

export type MapState = "overview" | "focus" | "detail3d" | "compare" | "placement" | "validation";

export type UrbanStateId = "2020" | "2023" | "2025" | "2040";

export type SelectionType =
  | "mesh"
  | "building"
  | "road"
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
  city: CityId;
  task: ProductTask;
  urbanState: UrbanStateId;
  selection: SpatialSelection | null;
  scenario: string | null;
  validationSample: string | null;
  mapMode: MapMode;
  mapState: MapState;
  preset: LayerPresetId;
  primaryLayer: string;
  viewport: SpatialViewport;
  inspectorOpen: boolean;
  demoMode: boolean;
}

export type SpatialAction =
  | { type: "hydrate"; state: SpatialState }
  | { type: "set-city"; city: CityId }
  | { type: "set-task"; task: ProductTask }
  | { type: "set-urban-state"; urbanState: UrbanStateId }
  | { type: "set-selection"; selection: SpatialSelection | null }
  | { type: "set-scenario"; scenario: string | null }
  | { type: "set-validation-sample"; validationSample: string | null }
  | { type: "set-map-mode"; mapMode: MapMode }
  | { type: "set-map-state"; mapState: MapState }
  | { type: "set-preset"; preset: LayerPresetId; primaryLayer: string }
  | { type: "set-primary-layer"; primaryLayer: string }
  | { type: "set-viewport"; viewport: SpatialViewport }
  | { type: "set-inspector-open"; open: boolean }
  | { type: "set-demo-mode"; enabled: boolean };

export const CITY_VIEWPORTS: Record<CityId, SpatialViewport> = {
  maizuru: { longitude: 135.33, latitude: 35.47, zoom: 10.45, bearing: 0, pitch: 0 },
  fujisawa: { longitude: 139.47, latitude: 35.36, zoom: 11.25, bearing: 0, pitch: 0 }
};

export const DEFAULT_SPATIAL_STATE: SpatialState = {
  city: "maizuru",
  task: "discover",
  urbanState: "2025",
  selection: null,
  scenario: null,
  validationSample: null,
  mapMode: "map2d",
  mapState: "overview",
  preset: "discovery",
  primaryLayer: "analysis-city-gap",
  viewport: CITY_VIEWPORTS.maizuru,
  inspectorOpen: true,
  demoMode: false
};
