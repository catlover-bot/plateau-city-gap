export type ProductRole =
  | "viewer"
  | "analyst"
  | "planner"
  | "field_staff"
  | "data_manager"
  | "administrator";

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
  dataset_category?: string;
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

export interface OnboardingPayload {
  city: CityHomePayload["city"];
  steps: Array<{
    key: string;
    status: "missing" | "in_progress" | "complete";
    registered_versions?: number;
    promoted_versions?: number;
    count?: number;
  }>;
  capabilities: Array<{
    capability: string;
    status: "available" | "partial" | "unavailable";
    note: string;
  }>;
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
  input_contract: {
    required?: string[];
    context_roles?: string[];
    dataset_roles?: string[];
  };
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
    allowed_values?: unknown[] | null;
  }>;
}

export interface UrbanStateSummary {
  id: string;
  state_key: string;
  label: string;
  effective_date: string;
  state_type: string;
  lifecycle_status: string;
  source_verified: boolean;
}

export interface AnalysisRunSummary {
  id: string;
  analysis_type: string;
  status: string;
  algorithm_version: string;
  config_hash: string;
  parameters: Record<string, unknown>;
  result_hash: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_by: string;
  dataset_version_ids: string[];
  job_id: string | null;
  job_state: string | null;
  job_stage: string | null;
}

export interface EvidenceLibrary {
  city: CityHomePayload["city"];
  evidence_centers: Array<{
    id: string;
    investigation_id: string | null;
    scenario_run_id: string | null;
    manifest_sha256: string;
    data_classification: "public" | "internal" | "restricted";
    created_by: string;
    created_at: string;
    field_evidence_count: number;
    decision_count: number;
  }>;
  reports: Array<{
    id: string;
    report_type: string;
    title: string;
    artifact_sha256: string;
    data_classification: "public" | "internal" | "restricted";
    generator_version: string;
    created_by: string;
    created_at: string;
  }>;
  validation_runs: Array<{
    id: string;
    claim_key: string;
    method_key: string;
    validation_status: string;
    run_status: string;
    algorithm_version: string;
    generated_at: string;
  }>;
}

export interface ServiceJobSummary {
  id: string;
  city_key: string;
  city_name: string;
  job_type: string;
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  current_stage: string | null;
  algorithm_version: string;
  retry_count: number;
  max_retries: number;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  last_heartbeat_at: string | null;
  error_message: string | null;
}

export interface OperationsPayload {
  overview: {
    jobs: {
      queued: number;
      running: number;
      failed: number;
      cancelled: number;
      latest_worker_heartbeat: string | null;
    };
    datasets: {
      failed: number;
      validating: number;
      awaiting_promotion: number;
    };
    backups: Array<Record<string, unknown>>;
    releases: Array<Record<string, unknown>>;
    boundaries: Record<string, string>;
  };
  jobs: ServiceJobSummary[];
  auditEvents: Array<{
    id: number;
    actor: string;
    action: string;
    resource_type: string;
    resource_id: string;
    city_id: string | null;
    request_id: string;
    data_classification: "public" | "internal" | "restricted";
    occurred_at: string;
  }>;
  memberships: Array<{
    user_id: string;
    issuer: string;
    subject: string;
    display_name: string;
    email: string | null;
    user_active: boolean;
    role: ProductRole;
    active: boolean;
    granted_at: string;
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

export interface ScenarioComparisonSummary {
  id: string;
  investigation_id: string | null;
  title: string;
  scenario_run_ids: string[];
  comparison_dimensions: Array<Record<string, unknown>>;
  created_by: string;
  created_at: string;
}

export interface FieldOfflinePackage {
  offline_package_id: string;
  package_version: number;
  content_sha256: string;
  expires_at: string | null;
  content: {
    package_scope: "single_selected_site";
    urban_state_id: string;
    scenario_run_id: string;
    site_order: number;
    field_record?: { record_version?: number };
    [key: string]: unknown;
  };
}

export interface AttachmentMetadata {
  id: string;
  city_id: string;
  original_file_name: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  data_classification: "public" | "internal" | "restricted";
  created_at: string;
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
  urban_states: UrbanStateSummary[];
  annual_updates?: Array<{
    id: string;
    status: string;
    algorithm_version: string;
    from_label: string;
    from_effective_date: string;
    to_label: string;
    to_effective_date: string;
    job_id: string | null;
    job_state: string | null;
    job_stage: string | null;
    created_at: string;
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
  analysisRuns: AnalysisRunSummary[];
  scenarios: ScenarioSummary[];
  scenarioComparisons: ScenarioComparisonSummary[];
  dataHub: DataHubPayload | null;
  evidence: EvidenceLibrary | null;
  operations: OperationsPayload | null;
  onboarding: OnboardingPayload | null;
}
