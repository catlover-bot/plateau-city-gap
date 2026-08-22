export type JsonProperties = Record<string, unknown>;

export interface GeoJsonFeature {
  type: "Feature";
  id?: string | number;
  geometry: {
    type: string;
    coordinates: unknown;
  } | null;
  properties: JsonProperties | null;
}

export interface GeoJsonFeatureCollection {
  type: "FeatureCollection";
  features: GeoJsonFeature[];
}

export interface MeshMetrics extends JsonProperties {
  mesh_code: string;
  rank?: number | null;
  centroid_lat?: number | null;
  centroid_lon?: number | null;
  population?: number | null;
  elderly_population?: number | null;
  elderly_ratio?: number | null;
  disclosure_status?: string | null;
  primary_eligible?: boolean | null;
  nearest_station_name?: string | null;
  nearest_station_distance_m?: number | null;
  nearest_bus_stop_name?: string | null;
  nearest_bus_stop_distance_m?: number | null;
  nearest_public_transport_name?: string | null;
  nearest_public_transport_distance_m?: number | null;
  nearest_medical_name?: string | null;
  nearest_medical_distance_m?: number | null;
  nearest_hospital_name?: string | null;
  nearest_hospital_distance_m?: number | null;
  elderly_population_percentile?: number | null;
  elderly_ratio_percentile?: number | null;
  transport_distance_percentile?: number | null;
  medical_distance_percentile?: number | null;
  exploratory_score_c?: number | null;
  pareto_frontier?: boolean | null;
}

export interface Manifest extends JsonProperties {
  generated_at?: string;
  analysis_version?: string;
  source_datasets?: unknown;
  limitations?: unknown;
  outputs?: unknown;
}

export interface Summary extends JsonProperties {
  record_counts?: Record<string, number>;
  limitations?: string[];
  distance_method?: string;
  analysis_crs?: { code?: string; name?: string };
}

export interface PlateauMetadata extends JsonProperties {
  status?: string;
  dataset?: string;
  year?: number;
  source?: string;
  source_year?: number;
  record_count?: number;
  available_attributes?: string[];
  limitations?: string[];
  building_layer?: {
    status?: string;
    records?: number;
    unique_buildings?: number;
    source_distribution_unique_buildings?: number;
    top10_buildings?: number;
    selected_tiles?: number;
    bytes?: number;
    tileset_url?: string;
    lod1_buildings?: number;
    lod2_buildings?: number;
    attributes?: string[];
    reason?: string;
    coverage_note?: string;
  };
  reference_layer?: {
    status?: string;
    records?: number;
    selected_tiles?: number;
    bytes?: number;
    tileset_url?: string;
    lod1_buildings?: number;
    lod2_buildings?: number;
    attributes?: string[];
    scope?: string;
    reason?: string;
    viewpoint?: {
      longitude?: number;
      latitude?: number;
      height?: number;
    };
  };
}

export interface BuildingInfo {
  id: string;
  usage: string | null;
  measuredHeight: number | null;
  storeysAboveGround: number | null;
  storeysBelowGround: number | null;
  lod: string | null;
}

export interface AppData {
  manifest: Manifest;
  summary: Summary;
  meshes: GeoJsonFeatureCollection;
  top10: MeshMetrics[];
  stations: GeoJsonFeatureCollection | null;
  busStops: GeoJsonFeatureCollection | null;
  medicalFacilities: GeoJsonFeatureCollection | null;
  boundary: GeoJsonFeatureCollection | null;
  plateauBuildings: GeoJsonFeatureCollection | null;
  plateauMetadata: PlateauMetadata | null;
  warnings: string[];
}

export type MetricMode = "gap" | "elderly" | "transport" | "medical";

export interface LayerVisibility {
  meshes: boolean;
  stations: boolean;
  busStops: boolean;
  medical: boolean;
  boundary: boolean;
  plateau: boolean;
}
