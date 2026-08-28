import type {
  AnalysisDefinition,
  AnalysisRunSummary,
  CityHomePayload,
  CitySummary,
  DataHubPayload,
  EvidenceLibrary,
  Finding,
  Investigation,
  OperationsPayload,
  OnboardingPayload,
  ScenarioSummary,
  ScenarioComparisonSummary,
  ServiceProfile,
  ServiceSnapshot,
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
      ]).then(([overview, jobs]) => ({ overview, jobs: jobs.items }))
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
