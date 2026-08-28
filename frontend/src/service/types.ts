export type ProductRole = "viewer" | "analyst" | "planner" | "field_staff" | "data_manager" | "administrator";

export interface Organization {
  id: string;
  organization_key: string;
  name: string;
  organization_type?: string;
  default_data_classification?: "public" | "internal" | "restricted";
}

export interface ServiceProfile {
  actor: string;
  issuer: string;
  roles: ProductRole[];
  organization: Organization;
  user: { id: string; display_name: string; email?: string } | null;
  memberships: Array<{ role: ProductRole; granted_at: string }>;
}

export interface CitySummary {
  city_id: string;
  city_code: string;
  city_key: string;
  name: string;
  service_status: "onboarding" | "active" | "paused" | "archived";
  open_findings: number;
  active_investigations: number;
  pending_reviews: number;
  pending_field_checks: number;
  latest_activity_at: string | null;
  available_capabilities?: number;
  capability_count?: number;
}

export interface Capability {
  capability: string;
  status: "available" | "partial" | "unavailable";
  note: string;
  evidence: unknown[];
  updated_at: string;
}

export interface DatasetSummary {
  dataset_id?: string;
  dataset_key: string;
  title: string;
  provider?: string;
  data_classification: "public" | "internal" | "restricted";
  version_id: string;
  version_key: string;
  dataset_year: number;
  data_format?: string;
  service_status: string;
  quality_status: string;
  lifecycle_status?: string;
  analysis_ready: boolean;
  registered_at?: string;
}

export interface ActivityEvent {
  id?: number;
  event_type: string;
  resource_type: string;
  resource_id: string;
  title?: string;
  summary: string;
  actor_label: string;
  occurred_at: string;
}

export interface CityHomePayload {
  city: {
    id: string;
    city_code: string;
    city_key: string;
    name: string;
    prefecture_name: string;
    analysis_crs: string;
    service_status: CitySummary["service_status"];
  };
  summary: CitySummary;
  capabilities: Capability[];
  datasets: DatasetSummary[];
  recent_activity: ActivityEvent[];
}

export interface Finding {
  id: string;
  city_id: string;
  urban_state_id: string | null;
  finding_type: string;
  title: string;
  summary: string;
  status: string;
  validation_status: string;
  created_by: string;
  created_at: string;
  updated_at?: string;
}

export interface Investigation {
  id: string;
  title: string;
  objective: string;
  status: string;
  urban_state_id: string;
  assigned_to?: string | null;
  due_date?: string | null;
  finding_count?: number;
  updated_at: string;
}

export interface WorkQueue {
  user: { id: string; display_name: string } | null;
  assignments: Array<{
    id: string;
    assignment_type: string;
    resource_id: string;
    status: string;
    due_date: string | null;
    created_at: string;
  }>;
  notifications: Array<{
    id: string;
    notification_type: string;
    title: string;
    body: string;
    resource_type: string | null;
    resource_id: string | null;
    read_at: string | null;
    created_at: string;
  }>;
  unregistered_identity: boolean;
}

export interface AnalysisDefinition {
  id: string;
  version: string;
  name: string;
  purpose: string;
  required_capabilities: string[];
  input_contract: Record<string, unknown>;
  output_contract: Record<string, unknown>;
  algorithm_description: string;
  claim_boundary: string;
  parameters: Array<{
    parameter_key: string;
    value_type: string;
    description: string;
    default_value: unknown;
    minimum: number | null;
    maximum: number | null;
  }>;
}

export interface ScenarioSummary {
  id: string;
  title: string;
  objective_mode: string;
  objective_definition: string;
  site_count: number;
  algorithm_version: string;
  lifecycle_status: string;
  review_status: string;
  generated_at: string;
}

export interface DataHubPayload {
  city: CityHomePayload["city"];
  datasets: DatasetSummary[];
  quality_checks: Array<{
    dataset_version_id: string;
    check_key: string;
    status: string;
    explanation: string;
    checked_at: string;
  }>;
  plateau_model: Array<{
    plateau_dataset_version_id: string;
    dataset_year: number;
    product_specification_version: string;
    theme: string;
    feature_count: number;
    available_lods: number[];
    geometry_count: number;
  }>;
}

export interface ServiceSnapshot {
  profile: ServiceProfile;
  cities: CitySummary[];
  cityHome: CityHomePayload | null;
  findings: Finding[];
  investigations: Investigation[];
  workQueue: WorkQueue;
  analyses: AnalysisDefinition[];
  scenarios: ScenarioSummary[];
  dataHub: DataHubPayload | null;
}
