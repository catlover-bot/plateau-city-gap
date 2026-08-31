export type AreaKnowledgeStatus = "known" | "partial" | "unknown" | "unavailable";
export type AreaActionType = "none" | "data_acquisition" | "field_verification" | "expert_review";
export type RadiusMethodology =
  | "mlit_elderly_walk_reference_500m"
  | "mlit_general_walk_reference_800m"
  | "broad_context_1000m"
  | "custom_radius";

export interface AreaMetricSource {
  dataset: string;
  source_date: string;
  artifact?: string;
  sha256?: string;
}

export interface AreaMetric {
  key: string;
  group: "population" | "age_distribution" | "building_use" | "establishments" | "urban_planning" | "transport" | "secondary";
  label: string;
  status: AreaKnowledgeStatus;
  value: unknown;
  unit: string;
  coverage_ratio: number | null;
  calculation: "exact" | "area_weighted_estimate" | "modelled" | "observation_count";
  records?: number;
  source: AreaMetricSource;
  limitation: string;
}

export interface AreaTarget {
  scope: "plateau_object" | "mesh" | "facility";
  object_type: "building" | "road" | "mesh" | "facility";
  source_object_id: string;
  label: string;
  longitude: number;
  latitude: number;
  dataset: string;
  role: "primary" | "context";
}

export interface AreaUnknown {
  id: string;
  title: string;
  importance: string;
  status: "unknown" | "partial";
  action_type: AreaActionType;
  reason_code: string;
  source_boundary: string;
  target: AreaTarget;
  checks: string[];
}

export interface InvestigationAreaSummary {
  id: string;
  area_series_id: string;
  version: number;
  label: string;
  geometry_kind: "point_radius";
  origin: {
    kind: "station" | "map_point";
    source_feature_id?: string;
    label: string;
    coordinates: [number, number];
  };
  radius_m: number;
  radius_methodology: RadiusMethodology;
  clipped_area_ratio: number | null;
  effective_geometry?: unknown;
  metrics: AreaMetric[];
  unknowns: AreaUnknown[];
  status: "unverified";
  content_sha256: string | null;
}

export interface InvestigationAreaFixture {
  schema_version: "citygap.area-summary@1";
  rule_version: string;
  generated_from: string;
  validation_status: {
    aoi_need: string;
    area_summary_content: string;
    known_unknown_value: string;
    unknown_to_field_task_workflow: "AWAITING_MUNICIPAL_WORKFLOW_REVIEW";
    human: "AWAITING_HUMAN_TEST";
  };
  area_summary_priority: string[];
  areas: InvestigationAreaSummary[];
}
