import type {
  AnalysisDefinition,
  CityHomePayload,
  CitySummary,
  DataHubPayload,
  Finding,
  Investigation,
  ScenarioSummary,
  ServiceProfile,
  ServiceSnapshot,
  WorkQueue
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
    super(payload.error?.message ?? payload.detail ?? `CITY GAP API error (${status})`);
    this.name = "ServiceApiError";
    this.status = status;
    this.requestId = payload.error?.request_id ?? null;
    this.remediation = payload.error?.remediation ?? null;
  }
}

function apiBase(): string {
  const configured = import.meta.env.VITE_CITYGAP_API_BASE_URL as string | undefined;
  return (configured ?? "").replace(/\/$/, "");
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  fetcher: typeof fetch = fetch
): Promise<T> {
  const response = await fetcher(`${apiBase()}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers
    }
  });
  const payload = await response.json().catch(() => ({})) as T & ServiceErrorShape;
  if (!response.ok) throw new ServiceApiError(response.status, payload);
  return payload;
}

export async function loadServiceSnapshot(
  fetcher: typeof fetch = fetch
): Promise<ServiceSnapshot> {
  const [profile, citiesPayload, workQueue, analysesPayload] = await Promise.all([
    requestJson<ServiceProfile>("/api/v1/me", {}, fetcher),
    requestJson<{ items: CitySummary[] }>("/api/v1/cities", {}, fetcher),
    requestJson<WorkQueue>("/api/v1/work-queue", {}, fetcher),
    requestJson<{ items: AnalysisDefinition[] }>("/api/v1/analysis-definitions", {}, fetcher)
  ]);
  const cities = citiesPayload.items;
  const selectedCity = cities.find((city) => city.service_status === "active") ?? cities[0];
  if (!selectedCity) {
    return {
      profile,
      cities,
      cityHome: null,
      findings: [],
      investigations: [],
      workQueue,
      analyses: analysesPayload.items,
      scenarios: [],
      dataHub: null
    };
  }
  const city = encodeURIComponent(selectedCity.city_key);
  const [cityHome, findingsPayload, investigationsPayload, scenariosPayload, dataHub] =
    await Promise.all([
      requestJson<CityHomePayload>(`/api/v1/cities/${city}/home`, {}, fetcher),
      requestJson<{ items: Finding[] }>(`/api/v1/cities/${city}/findings?limit=100`, {}, fetcher),
      requestJson<{ items: Investigation[] }>(`/api/v1/cities/${city}/investigations?limit=100`, {}, fetcher),
      requestJson<{ items: ScenarioSummary[] }>(`/api/v1/cities/${city}/scenarios?limit=100`, {}, fetcher),
      requestJson<DataHubPayload>(`/api/v1/cities/${city}/data-hub`, {}, fetcher)
    ]);
  return {
    profile,
    cities,
    cityHome,
    findings: findingsPayload.items,
    investigations: investigationsPayload.items,
    workQueue,
    analyses: analysesPayload.items,
    scenarios: scenariosPayload.items,
    dataHub
  };
}

export const serviceApi = {
  request: requestJson,
  async loadCity(cityKey: string, fetcher: typeof fetch = fetch) {
    const city = encodeURIComponent(cityKey);
    const [cityHome, findings, investigations, scenarios, dataHub] = await Promise.all([
      requestJson<CityHomePayload>(`/api/v1/cities/${city}/home`, {}, fetcher),
      requestJson<{ items: Finding[] }>(`/api/v1/cities/${city}/findings?limit=100`, {}, fetcher),
      requestJson<{ items: Investigation[] }>(`/api/v1/cities/${city}/investigations?limit=100`, {}, fetcher),
      requestJson<{ items: ScenarioSummary[] }>(`/api/v1/cities/${city}/scenarios?limit=100`, {}, fetcher),
      requestJson<DataHubPayload>(`/api/v1/cities/${city}/data-hub`, {}, fetcher)
    ]);
    return {
      cityHome,
      findings: findings.items,
      investigations: investigations.items,
      scenarios: scenarios.items,
      dataHub
    };
  }
};
