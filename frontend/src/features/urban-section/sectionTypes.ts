export interface TerrainSample {
  sample_order: number;
  distance_m: number;
  longitude: number;
  latitude: number;
  elevation_m: number | null;
  source_triangle_id: string | null;
  quality: "direct_tin" | "boundary" | "no_coverage";
}

export interface SectionRelation {
  source_object_id: string;
  relation: "direct" | "nearby";
  start_distance_m: number;
  end_distance_m: number;
  offset_distance_m: number;
  properties: Record<string, unknown>;
}

export interface SectionBand {
  source_object_id: string;
  start_distance_m: number;
  end_distance_m: number;
  planning?: Record<string, unknown>;
  hazards?: Array<Record<string, unknown>>;
}

export interface SectionData {
  transect_id: string;
  pack_id: string;
  geometry: { type: "LineString"; coordinates: Array<[number, number]> };
  buffer_m: number;
  sample_interval_m: number;
  vertical_datum: string;
  terrain_source: string;
  terrain_interpolation: string;
  terrain_samples: TerrainSample[];
  buildings: SectionRelation[];
  roads: SectionRelation[];
  service_locations: SectionRelation[];
  scenario_sites: SectionRelation[];
  counterfactual: {
    plan_id: string;
    building_group_count: number;
    baseline: { distance_m: number; score_c: number };
    scenario: { distance_m: number; score_c: number; distance_reduction_m: number; score_c_reduction: number };
    distance_semantics: string;
    geometry_policy: string;
    limitations: string[];
  };
  planning_bands: SectionBand[];
  hazard_bands: SectionBand[];
}
