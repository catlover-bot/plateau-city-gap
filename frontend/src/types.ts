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

export interface RobustScenarioResult {
  rank: number | null;
  top10: boolean;
  top20: boolean;
  pareto: boolean;
}

export interface RobustCandidate extends JsonProperties {
  robust_rank: number;
  mesh_code: string;
  area_label?: string | null;
  scenario_count: number;
  ranked_scenario_count: number;
  top10_frequency: number;
  top20_frequency: number;
  pareto_frequency: number;
  median_rank: number;
  rank_min: number;
  rank_max: number;
  scenarios: Record<string, RobustScenarioResult>;
}

export interface RobustnessData extends JsonProperties {
  scenario_count: number;
  interpretation: string;
  ranking_rule: string;
  scenarios: Array<{ id: string; label: string; definition: string; eligible_count: number }>;
  candidates: RobustCandidate[];
  top_candidates: RobustCandidate[];
}

export type DecisionMode = "overall" | "fairness" | "robust";
export type DecisionMapPhase = "before" | "after";

export interface InterventionSite {
  site_order: number;
  candidate_id: string;
  longitude: number;
  latitude: number;
  road_name: string | null;
  nearest_existing_transport_name: string;
  existing_transport_distance_m: number;
}

export interface InterventionMeshResult {
  before_distance_m: number;
  after_distance_m: number;
  distance_reduction_m: number;
  before_score_c: number;
  after_score_c: number;
  score_c_reduction: number;
  assigned_site_id: string | null;
}

export interface InterventionImpact {
  total_score_c_reduction: number;
  improved_mesh_count: number;
  affected_elderly_population: number;
  mean_improvement_among_improved_m: number;
  total_transport_distance_reduction_m: number;
  worst_decile_mean_reduction_m: number;
  worst_decile_improved_count: number;
  robust_top20_improved_count: number;
  robust_top20_median_reduction_m: number;
}

export interface InterventionPlan extends JsonProperties {
  plan_id: string;
  mode: DecisionMode;
  site_count: number;
  sites: InterventionSite[];
  impact: InterventionImpact;
  top_improvements: Array<InterventionMeshResult & { mesh_code: string; area_label: string }>;
  mesh_results: Record<string, InterventionMeshResult>;
}

export interface InterventionData extends JsonProperties {
  metadata: {
    algorithm: string;
    exactness: string;
    candidate_count: number;
    runtime_seconds: number;
    constraints: JsonProperties;
    objectives: Record<DecisionMode, string>;
    source_data_hashes: Record<string, string>;
  };
  plans: Record<DecisionMode, Record<"1" | "2" | "3", InterventionPlan>>;
  one_site_objective_comparison: Record<"affected_elderly" | "mean_distance", InterventionPlan>;
  diminishing_returns: Array<{ site_count: number } & Partial<InterventionImpact>>;
  limitations: string[];
}

export interface EvidenceData extends JsonProperties {
  philosophy: string;
  rank_one: {
    mesh_code: string;
    transport: {
      origin: string;
      destination: string;
      dataset: string;
      crs: string;
      calculation: string;
      value_m: number;
    };
    medical: {
      origin: string;
      destination: string;
      dataset: string;
      crs: string;
      calculation: string;
      value_m: number;
    };
    score_c: {
      formula: string;
      components: Record<string, number>;
      value: number;
    };
  };
  intervention: {
    formula: string;
    percentile: string;
    source_data_hashes: Record<string, string>;
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
    building_demographics_detail?: PlateauBuildingDemographicsDetail;
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

export interface PlateauBuildingDemographicsDetail extends JsonProperties {
  method: string;
  privacy: string;
  residential_building_count: number;
  mixed_residential_building_count: number;
  estimated_population_allocated: number;
  estimated_elderly_allocated: number;
  centroid_transport_distance_m: number;
  weighted_mean_transport_distance_m: number;
  weighted_median_transport_distance_m: number;
  weighted_p90_transport_distance_m: number;
  centroid_medical_distance_m: number;
  weighted_mean_medical_distance_m: number;
  weighted_median_medical_distance_m: number;
  weighted_p90_medical_distance_m: number;
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
  robustness: RobustnessData | null;
  interventions: InterventionData | null;
  evidence: EvidenceData | null;
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

export type WorkspacePhase = "baseline" | "scenario_a" | "scenario_b" | "scenario_c";

export interface WorkspaceLayerVisibility {
  meshes: boolean;
  affectedBuildings: boolean;
  routes: boolean;
  plateauBuildings: boolean;
  roadNetwork: boolean;
  landuse: boolean;
  planning: boolean;
  hazard: boolean;
}

export interface NetworkScenarioSite extends JsonProperties {
  site_order: number;
  candidate_id: string;
  node_id: string;
  road_gml_id: string;
  road_surface_id: string;
  road_name: string | null;
  longitude: number;
  latitude: number;
  existing_transport_distance_m: number;
  landuse_context: string;
  planning_context: string;
  hazard_context: string;
  hazard_overlap: boolean;
  hazard_review_status: string;
  siting_feasibility: string;
  component_id: string;
  terrain: {
    elevation_m: number | null;
    maximum_incident_endpoint_grade_percent: number | null;
    routing_penalty_applied: boolean;
  };
}

export interface NetworkScenarioImpact extends JsonProperties {
  affected_graph_node_count: number;
  improved_building_count: number;
  newly_network_connected_building_count: number;
  total_building_distance_reduction_m: number;
  mean_reduction_all_reachable_buildings_m: number;
  mean_reduction_improved_buildings_m: number;
  affected_estimated_elderly_population: number;
  elderly_weighted_distance_reduction_person_m: number;
  elderly_weighted_mean_reduction_m: number;
  worst_decile_mean_reduction_m: number;
  improved_mesh_count: number;
  robust_top20_improved_mesh_count: number;
}

export interface NetworkScenarioEvidence extends JsonProperties {
  building_gml_id: string;
  origin_representative_point: {
    longitude: number;
    latitude: number;
    method: string;
  };
  snap_node_id: string;
  origin_to_node_connector_m: number;
  before: {
    network_distance_m: number;
    destination_name?: string;
    road_node_sequence: string[];
  };
  after: {
    network_distance_m: number;
    virtual_scenario_candidate_id: string;
    road_node_sequence: string[];
  };
  route_semantics: string;
}

export interface NetworkScenarioStoryPlan extends JsonProperties {
  story_id: "scenario_a" | "scenario_b" | "scenario_c";
  plan_id: string;
  mode: string;
  label: string;
  objective: string;
  site_count: number;
  exactness: string;
  sites: NetworkScenarioSite[];
  impact: NetworkScenarioImpact;
  representative_evidence: NetworkScenarioEvidence;
}

export interface NetworkScenarioStory extends JsonProperties {
  schema_version: string;
  generated_at: string;
  city: JsonProperties;
  source: string;
  scenario_story: NetworkScenarioStoryPlan[];
  limitations: string[];
}

export interface WorkspaceMapData extends GeoJsonFeatureCollection {
  schema_version: string;
  generated_at: string;
  source: string;
  privacy: string;
  layer_counts: Record<string, number>;
  story_counts: Record<string, number>;
}

export interface WorkspaceBuildingPoints {
  schema_version: string;
  generated_at: string;
  privacy: string;
  band_codes: Record<string, "under_250" | "250_499" | "500_plus">;
  stories: Record<"scenario_a" | "scenario_b" | "scenario_c", Array<[number, number, 0 | 1 | 2]>>;
}

export type CapabilityStatus = "available" | "partial" | "unavailable";

export interface PlatformCapability extends JsonProperties {
  city_code: string;
  capability: string;
  status: CapabilityStatus;
  note: string;
  evidence: Array<{ artifact: string; sha256: string; verified_present: boolean }>;
  dataset_version_ids: string[];
}

export interface PlatformRegistry extends JsonProperties {
  schema_version: string;
  generated_at: string;
  cities: Array<{
    city_id: string;
    city_code: string;
    name: string;
    prefecture_name: string;
    analysis_crs: string;
    mode: string;
  }>;
  capabilities: PlatformCapability[];
  datasets: JsonProperties[];
  dataset_versions: JsonProperties[];
  analysis_runs: JsonProperties[];
}

export interface MunicipalWorkspaceData {
  story: NetworkScenarioStory;
  map: WorkspaceMapData;
  buildingPoints: WorkspaceBuildingPoints;
  registry: PlatformRegistry;
}
