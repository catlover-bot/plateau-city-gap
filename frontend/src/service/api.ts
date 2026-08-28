import type {
  AnalysisDefinition,
  AnalysisRunSummary,
  CityHomePayload,
  CitySummary,
  DataHubPayload,
  EvidenceLibrary,
  FieldOfflinePackage,
  Finding,
  Investigation,
  OperationsPayload,
  OnboardingPayload,
  ScenarioSummary,
  ScenarioComparisonSummary,
  ServiceProfile,
  ServiceSnapshot,
  AttachmentMetadata,
  WorkQueue,
} from "./types";

export interface ServiceErrorShape {
  error?: {
    code?: string;
    message?: string;
    request_id?: string | null;
    remediation?: string;
  };
  detail?: string;
}

export class ServiceApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;
  readonly remediation: string | null;

  constructor(status: number, payload: ServiceErrorShape) {
    super(
      payload.error?.message ??
        payload.detail ??
        `CITY GAP API error (${status})`,
    );
    this.name = "ServiceApiError";
    this.status = status;
    this.requestId = payload.error?.request_id ?? null;
    this.remediation = payload.error?.remediation ?? null;
  }
}

function apiBase(): string {
  const configured = import.meta.env.VITE_CITYGAP_API_BASE_URL as
    string | undefined;
  return (configured ?? "").replace(/\/$/, "");
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  fetcher: typeof fetch = fetch,
): Promise<T> {
  const response = await fetcher(`${apiBase()}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  const payload = (await response.json().catch(() => ({}))) as T &
    ServiceErrorShape;
  if (!response.ok) throw new ServiceApiError(response.status, payload);
  return payload;
}

export async function loadServiceSnapshot(
  fetcher: typeof fetch = fetch,
): Promise<ServiceSnapshot> {
  const [profile, citiesPayload, workQueue, analysesPayload] =
    await Promise.all([
      requestJson<ServiceProfile>("/api/v1/me", {}, fetcher),
      requestJson<{ items: CitySummary[] }>("/api/v1/cities", {}, fetcher),
      requestJson<WorkQueue>("/api/v1/work-queue", {}, fetcher),
      requestJson<{ items: AnalysisDefinition[] }>(
        "/api/v1/analysis-definitions",
        {},
        fetcher,
      ),
    ]);
  const cities = citiesPayload.items;
  const operations: OperationsPayload | null = profile.roles.some((role) =>
    ["data_manager", "administrator"].includes(role),
  )
    ? await Promise.all([
        requestJson<OperationsPayload["overview"]>(
          "/api/v1/operations/overview",
          {},
          fetcher,
        ),
        requestJson<{ items: OperationsPayload["jobs"] }>(
          "/api/v1/jobs?limit=100",
          {},
          fetcher,
        ),
        profile.roles.includes("administrator")
          ? requestJson<{ items: OperationsPayload["auditEvents"] }>(
              "/api/v1/audit-events?limit=100",
              {},
              fetcher,
            )
          : Promise.resolve({ items: [] }),
      ]).then(([overview, jobs, audit]) => ({
        overview,
        jobs: jobs.items,
        auditEvents: audit.items,
      }))
    : null;
  const selectedCity =
    cities.find((city) => city.service_status === "active") ?? cities[0];
  if (!selectedCity) {
    return {
      profile,
      cities,
      cityHome: null,
      findings: [],
      investigations: [],
      workQueue,
      analyses: analysesPayload.items,
      analysisRuns: [],
      scenarios: [],
      scenarioComparisons: [],
      dataHub: null,
      evidence: null,
      operations,
      onboarding: null,
    };
  }
  const city = encodeURIComponent(selectedCity.city_key);
  const [
    cityHome,
    findingsPayload,
    investigationsPayload,
    scenariosPayload,
    scenarioComparisonsPayload,
    dataHub,
    analysisRuns,
    evidence,
    onboarding,
  ] = await Promise.all([
    requestJson<CityHomePayload>(`/api/v1/cities/${city}/home`, {}, fetcher),
    requestJson<{ items: Finding[] }>(
      `/api/v1/cities/${city}/findings?limit=100`,
      {},
      fetcher,
    ),
    requestJson<{ items: Investigation[] }>(
      `/api/v1/cities/${city}/investigations?limit=100`,
      {},
      fetcher,
    ),
    requestJson<{ items: ScenarioSummary[] }>(
      `/api/v1/cities/${city}/scenarios?limit=100`,
      {},
      fetcher,
    ),
    requestJson<{ items: ScenarioComparisonSummary[] }>(
      `/api/v1/cities/${city}/scenario-comparisons?limit=100`,
      {},
      fetcher,
    ),
    requestJson<DataHubPayload>(`/api/v1/cities/${city}/data-hub`, {}, fetcher),
    requestJson<{ items: AnalysisRunSummary[] }>(
      `/api/v1/cities/${city}/analysis-runs?limit=100`,
      {},
      fetcher,
    ),
    requestJson<EvidenceLibrary>(
      `/api/v1/cities/${city}/evidence?limit=100`,
      {},
      fetcher,
    ),
    requestJson<OnboardingPayload>(
      `/api/v1/cities/${city}/onboarding`,
      {},
      fetcher,
    ),
  ]);
  return {
    profile,
    cities,
    cityHome,
    findings: findingsPayload.items,
    investigations: investigationsPayload.items,
    workQueue,
    analyses: analysesPayload.items,
    analysisRuns: analysisRuns.items,
    scenarios: scenariosPayload.items,
    scenarioComparisons: scenarioComparisonsPayload.items,
    dataHub,
    evidence,
    operations,
    onboarding,
  };
}

export const serviceApi = {
  request: requestJson,
  url(path: string) {
    return `${apiBase()}${path}`;
  },
  createOfflinePackage(
    cityKey: string,
    payload: {
      urban_state_id: string;
      scenario_run_id: string;
      site_order: number;
      expires_at?: string;
    },
    fetcher: typeof fetch = fetch,
  ) {
    return requestJson<FieldOfflinePackage>(
      `/api/v1/cities/${encodeURIComponent(cityKey)}/field/offline-packages`,
      { method: "POST", body: JSON.stringify(payload) },
      fetcher,
    );
  },
  async syncFieldOperation(
    cityKey: string,
    payload: unknown,
    fetcher: typeof fetch = fetch,
  ): Promise<{ httpStatus: number; payload: Record<string, unknown> }> {
    const response = await fetcher(
      `${apiBase()}/api/v1/cities/${encodeURIComponent(cityKey)}/field/sync`,
      {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      },
    );
    const body = (await response.json().catch(() => ({}))) as Record<
      string,
      unknown
    > &
      ServiceErrorShape;
    if (!response.ok && response.status !== 409) {
      throw new ServiceApiError(response.status, body);
    }
    return { httpStatus: response.status, payload: body };
  },
  resolveFieldConflict(
    cityKey: string,
    conflictId: string,
    resolutionStatus: "use_server" | "use_client" | "merged",
    resolvedState?: Record<string, unknown>,
    fetcher: typeof fetch = fetch,
  ) {
    return requestJson<Record<string, unknown>>(
      `/api/v1/cities/${encodeURIComponent(cityKey)}/field-conflicts/${encodeURIComponent(conflictId)}/resolve`,
      {
        method: "POST",
        body: JSON.stringify({
          resolution_status: resolutionStatus,
          resolved_state: resolvedState,
        }),
      },
      fetcher,
    );
  },
  async uploadAttachment(
    cityKey: string,
    file: File,
    dataClassification: "public" | "internal" | "restricted" = "restricted",
    fetcher: typeof fetch = fetch,
  ): Promise<AttachmentMetadata> {
    const query = new URLSearchParams({
      filename: file.name,
      data_classification: dataClassification,
    });
    const response = await fetcher(
      `${apiBase()}/api/v1/cities/${encodeURIComponent(cityKey)}/attachments?${query}`,
      {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "application/json",
          "Content-Type": file.type || "application/octet-stream",
        },
        body: file,
      },
    );
    const body = (await response
      .json()
      .catch(() => ({}))) as AttachmentMetadata & ServiceErrorShape;
    if (!response.ok) throw new ServiceApiError(response.status, body);
    return body;
  },
  async loadCity(cityKey: string, fetcher: typeof fetch = fetch) {
    const city = encodeURIComponent(cityKey);
    const [
      cityHome,
      findings,
      investigations,
      scenarios,
      scenarioComparisons,
      dataHub,
      analysisRuns,
      evidence,
      onboarding,
    ] = await Promise.all([
      requestJson<CityHomePayload>(`/api/v1/cities/${city}/home`, {}, fetcher),
      requestJson<{ items: Finding[] }>(
        `/api/v1/cities/${city}/findings?limit=100`,
        {},
        fetcher,
      ),
      requestJson<{ items: Investigation[] }>(
        `/api/v1/cities/${city}/investigations?limit=100`,
        {},
        fetcher,
      ),
      requestJson<{ items: ScenarioSummary[] }>(
        `/api/v1/cities/${city}/scenarios?limit=100`,
        {},
        fetcher,
      ),
      requestJson<{ items: ScenarioComparisonSummary[] }>(
        `/api/v1/cities/${city}/scenario-comparisons?limit=100`,
        {},
        fetcher,
      ),
      requestJson<DataHubPayload>(
        `/api/v1/cities/${city}/data-hub`,
        {},
        fetcher,
      ),
      requestJson<{ items: AnalysisRunSummary[] }>(
        `/api/v1/cities/${city}/analysis-runs?limit=100`,
        {},
        fetcher,
      ),
      requestJson<EvidenceLibrary>(
        `/api/v1/cities/${city}/evidence?limit=100`,
        {},
        fetcher,
      ),
      requestJson<OnboardingPayload>(
        `/api/v1/cities/${city}/onboarding`,
        {},
        fetcher,
      ),
    ]);
    return {
      cityHome,
      findings: findings.items,
      investigations: investigations.items,
      scenarios: scenarios.items,
      scenarioComparisons: scenarioComparisons.items,
      dataHub,
      analysisRuns: analysisRuns.items,
      evidence,
      onboarding,
    };
  },
};
