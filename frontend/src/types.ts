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
  area_label?: string | null;
  area_label_basis?: string | null;
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
  nearest_medical_access_class?: "confirmed_public" | "likely_public" | "uncertain_access" | null;
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
  city?: CityProfile;
  record_counts?: Record<string, number>;
  limitations?: string[];
  distance_method?: string;
  analysis_crs?: { code?: string; name?: string };
  audit?: {
    audit_date?: string;
    baseline_facility_scope?: string;
    medical_uncertain_access_records?: number;
    buffer_top10_overlap?: number;
    score_comparison_denominator?: number;
    interpretation?: string;
    rank_one_two_km_buffer?: {
      public_transport_distance_m?: number;
      medical_distance_excluding_uncertain_m?: number;
      public_transport_name?: string;
      medical_name?: string;
    };
  };
}

export interface CityProfile extends JsonProperties {
  id: "maizuru" | "fujisawa";
  code: string;
  name: string;
  prefecture: string;
  mode: "primary_demo" | "cross_city_validation";
  map_view: { longitude: number; latitude: number; height: number };
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
    deep_dive_buildings?: number;
    deep_dive_mesh_code?: string;
    deep_dive_overall_rank?: number;
    area_label?: string;
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
    featured_building?: {
      id?: string;
      longitude?: number;
      latitude?: number;
      usage?: string;
      measured_height_m?: number;
      storeys_above_ground?: number;
      storeys_below_ground?: number;
      building_footprint_area_m2?: number;
      total_floor_area_m2?: number;
      lod?: number;
    };
  };
}

export interface BuildingInfo {
  id: string;
  usage: string | null;
  measuredHeight: number | null;
  storeysAboveGround: number | null;
  storeysBelowGround: number | null;
  footprintArea: number | null;
  totalFloorArea: number | null;
  lod: string | null;
}

export interface PlacementCandidate extends JsonProperties {
  candidate_rank: number;
  candidate_id: string;
  area_label: string;
  longitude: number;
  latitude: number;
  road_name?: string | null;
  nearest_existing_transport_name: string;
  existing_transport_distance_m: number;
  objective_total_score_c_reduction: number;
  improved_mesh_count: number;
  affected_elderly_population: number;
  average_transport_distance_improvement_m: number;
  top_improvement_mesh: string;
  top_improvement: {
    mesh_code: string;
    before_distance_m: number;
    after_distance_m: number;
    before_score_c: number;
    after_score_c: number;
    score_c_reduction: number;
  };
}

export interface FinalDemoData extends JsonProperties {
  comparison_mesh_count: number;
  rank_one: {
    mesh_code: string;
    area_label: string;
    plateau_building_count: number;
  };
  plateau_covered_candidates: Array<{
    mesh_code: string;
    overall_rank: number;
    area_label: string;
    plateau_building_count: number;
  }>;
  deep_dive: {
    mesh_code: string;
    overall_rank: number;
    area_label: string;
    plateau_building_count: number;
    plateau_road_surfaces_intersecting_mesh: number;
    plateau_buildings: { records: number; displayed_on_click: string[] };
    terrain?: JsonProperties;
  };
  placement_optimization: {
    objective: string;
    screening_rule: string;
    candidates: PlacementCandidate[];
  };
  plateau_context: JsonProperties;
  offline: JsonProperties;
}

export interface AppData {
  city: CityProfile;
  manifest: Manifest;
  summary: Summary;
  meshes: GeoJsonFeatureCollection;
  top10: MeshMetrics[];
  stations: GeoJsonFeatureCollection | null;
  busStops: GeoJsonFeatureCollection | null;
  medicalFacilities: GeoJsonFeatureCollection | null;
  boundary: GeoJsonFeatureCollection | null;
  plateauBuildings: GeoJsonFeatureCollection | null;
  plateauRoads: GeoJsonFeatureCollection | null;
  plateauMetadata: PlateauMetadata | null;
  finalDemo: FinalDemoData | null;
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
