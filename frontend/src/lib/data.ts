import type {
  AppData,
  CityProfile,
  FinalDemoData,
  EvidenceData,
  GeoJsonFeatureCollection,
  InterventionData,
  Manifest,
  MeshMetrics,
  MunicipalWorkspaceData,
  NetworkScenarioStory,
  PlateauMetadata,
  PlatformRegistry,
  RobustnessData,
  Summary,
  WorkspaceBuildingPoints,
  WorkspaceMapData
} from "../types";
import { finiteNumber } from "./format";

interface Top10Envelope {
  items?: unknown[];
  records?: unknown[];
  top10?: unknown[];
  features?: Array<{ properties?: unknown }>;
}
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function assertFeatureCollection(value: unknown, filename: string): GeoJsonFeatureCollection {
  if (!isRecord(value) || value.type !== "FeatureCollection" || !Array.isArray(value.features)) {
    throw new Error(`${filename} の形式が正しくありません（FeatureCollectionが必要です）`);
  }
  return value as unknown as GeoJsonFeatureCollection;
}

function normalizeMesh(value: unknown): MeshMetrics | null {
  if (!isRecord(value)) return null;
  const code = value.mesh_code;
  if (typeof code !== "string" && typeof code !== "number") return null;
  return { ...value, mesh_code: String(code) } as MeshMetrics;
}

export function normalizeTop10(value: unknown): MeshMetrics[] {
  let candidates: unknown[] = [];
  if (Array.isArray(value)) {
    candidates = value;
  } else if (isRecord(value)) {
    const envelope = value as Top10Envelope;
    if (Array.isArray(envelope.items)) candidates = envelope.items;
    else if (Array.isArray(envelope.records)) candidates = envelope.records;
    else if (Array.isArray(envelope.top10)) candidates = envelope.top10;
    else if (Array.isArray(envelope.features)) {
      candidates = envelope.features.map((feature) => feature.properties);
    }
  }
  return sortRanking(candidates.map(normalizeMesh).filter((item): item is MeshMetrics => item !== null));
}

export function sortRanking(items: MeshMetrics[]): MeshMetrics[] {
  return [...items].sort((a, b) => {
    const rankA = finiteNumber(a.rank);
    const rankB = finiteNumber(b.rank);
    if (rankA !== null || rankB !== null) {
      return (rankA ?? Number.POSITIVE_INFINITY) - (rankB ?? Number.POSITIVE_INFINITY);
    }
    return (finiteNumber(b.exploratory_score_c) ?? -1) - (finiteNumber(a.exploratory_score_c) ?? -1);
  });
}

function dataUrl(baseUrl: string, filename: string): string {
  const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  return `${base}data/${filename}`;
}

const MAIZURU: CityProfile = {
  id: "maizuru",
  code: "26202",
  name: "舞鶴市",
  prefecture: "京都府",
  mode: "primary_demo",
  map_view: { longitude: 135.33, latitude: 35.47, height: 30_000 }
};

async function fetchJson(fetcher: typeof fetch, url: string): Promise<unknown> {
  const response = await fetcher(url);
  if (!response.ok) throw new Error(`${url} を読み込めませんでした（HTTP ${response.status}）`);
  return response.json() as Promise<unknown>;
}

async function optionalGeoJson(
  fetcher: typeof fetch,
  url: string,
  label: string,
  warnings: string[]
): Promise<GeoJsonFeatureCollection | null> {
  try {
    return assertFeatureCollection(await fetchJson(fetcher, url), label);
  } catch (error) {
    warnings.push(`${label}: ${error instanceof Error ? error.message : "読み込みに失敗しました"}`);
    return null;
  }
}

async function optionalMetadata(
  fetcher: typeof fetch,
  url: string,
  warnings: string[]
): Promise<PlateauMetadata | null> {
  try {
    const value = await fetchJson(fetcher, url);
    if (!isRecord(value)) throw new Error("JSON objectが必要です");
    return value as PlateauMetadata;
  } catch (error) {
    warnings.push(`PLATEAU metadata: ${error instanceof Error ? error.message : "読み込みに失敗しました"}`);
    return null;
  }
}

export async function loadAppData(
  fetcher: typeof fetch = fetch,
  baseUrl = import.meta.env.BASE_URL
): Promise<AppData> {
  const [manifestRaw, meshesRaw, top10Raw, summaryRaw, finalDemoRaw, robustnessRaw, interventionsRaw, evidenceRaw] = await Promise.all([
    fetchJson(fetcher, dataUrl(baseUrl, "manifest.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "mesh_metrics.geojson")),
    fetchJson(fetcher, dataUrl(baseUrl, "top10.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "summary.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "final_demo.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "robustness.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "intervention_scenarios.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "evidence.json"))
  ]);
  if (!isRecord(manifestRaw)) throw new Error("manifest.json の形式が正しくありません");
  if (!isRecord(summaryRaw)) throw new Error("summary.json の形式が正しくありません");
  if (!isRecord(finalDemoRaw)) throw new Error("final_demo.json の形式が正しくありません");
  if (!isRecord(robustnessRaw)) throw new Error("robustness.json の形式が正しくありません");
  if (!isRecord(interventionsRaw)) throw new Error("intervention_scenarios.json の形式が正しくありません");
  if (!isRecord(evidenceRaw)) throw new Error("evidence.json の形式が正しくありません");

  const warnings: string[] = [];
  const [stations, busStops, medicalFacilities, boundary, plateauBuildings, plateauRoads, plateauMetadata] =
    await Promise.all([
      optionalGeoJson(fetcher, dataUrl(baseUrl, "stations.geojson"), "駅", warnings),
      optionalGeoJson(fetcher, dataUrl(baseUrl, "bus_stops.geojson"), "バス停", warnings),
      optionalGeoJson(fetcher, dataUrl(baseUrl, "medical_facilities.geojson"), "医療施設", warnings),
      optionalGeoJson(fetcher, dataUrl(baseUrl, "maizuru_boundary.geojson"), "舞鶴市境界", warnings),
      optionalGeoJson(fetcher, dataUrl(baseUrl, "plateau_buildings.geojson"), "PLATEAU建物", warnings),
      optionalGeoJson(fetcher, dataUrl(baseUrl, "plateau_roads.geojson"), "PLATEAU道路", warnings),
      optionalMetadata(fetcher, dataUrl(baseUrl, "plateau_metadata.json"), warnings)
    ]);

  return {
    city: MAIZURU,
    manifest: manifestRaw as Manifest,
    summary: summaryRaw as Summary,
    meshes: assertFeatureCollection(meshesRaw, "mesh_metrics.geojson"),
    top10: normalizeTop10(top10Raw),
    stations,
    busStops,
    medicalFacilities,
    boundary,
    plateauBuildings,
    plateauRoads,
    plateauMetadata,
    finalDemo: finalDemoRaw as FinalDemoData,
    robustness: robustnessRaw as unknown as RobustnessData,
    interventions: interventionsRaw as unknown as InterventionData,
    evidence: evidenceRaw as unknown as EvidenceData,
    warnings
  };
}

export async function loadValidationCityData(
  fetcher: typeof fetch = fetch,
  baseUrl = import.meta.env.BASE_URL
): Promise<AppData> {
  const prefix = "cities/fujisawa/";
  const url = (filename: string) => dataUrl(baseUrl, `${prefix}${filename}`);
  const [manifestRaw, meshesRaw, top10Raw, summaryRaw] = await Promise.all([
    fetchJson(fetcher, url("manifest.json")),
    fetchJson(fetcher, url("mesh_metrics.geojson")),
    fetchJson(fetcher, url("top10.json")),
    fetchJson(fetcher, url("summary.json"))
  ]);
  if (!isRecord(manifestRaw)) throw new Error("藤沢 manifest.json の形式が正しくありません");
  if (!isRecord(summaryRaw)) throw new Error("藤沢 summary.json の形式が正しくありません");
  const cityRaw = summaryRaw.city;
  if (!isRecord(cityRaw) || cityRaw.id !== "fujisawa" || !isRecord(cityRaw.map_view)) {
    throw new Error("藤沢の都市メタデータが正しくありません");
  }
  const city = cityRaw as unknown as CityProfile;
  const warnings: string[] = [];
  const [stations, busStops, medicalFacilities, boundary] = await Promise.all([
    optionalGeoJson(fetcher, url("stations.geojson"), "藤沢市の駅", warnings),
    optionalGeoJson(fetcher, url("bus_stops.geojson"), "藤沢市のバス停", warnings),
    optionalGeoJson(fetcher, url("medical_facilities.geojson"), "藤沢市の医療施設", warnings),
    optionalGeoJson(fetcher, url("boundary.geojson"), "藤沢市境界", warnings)
  ]);
  return {
    city,
    manifest: manifestRaw as Manifest,
    summary: summaryRaw as Summary,
    meshes: assertFeatureCollection(meshesRaw, "藤沢 mesh_metrics.geojson"),
    top10: normalizeTop10(top10Raw),
    stations,
    busStops,
    medicalFacilities,
    boundary,
    plateauBuildings: null,
    plateauRoads: null,
    plateauMetadata: null,
    finalDemo: null,
    robustness: null,
    interventions: null,
    evidence: null,
    warnings
  };
}

export async function loadMunicipalWorkspaceData(
  fetcher: typeof fetch = fetch,
  baseUrl = import.meta.env.BASE_URL
): Promise<MunicipalWorkspaceData> {
  const [storyRaw, mapRaw, buildingPointsRaw, registryRaw] = await Promise.all([
    fetchJson(fetcher, dataUrl(baseUrl, "municipal_workspace_story.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "network_scenario_map.geojson")),
    fetchJson(fetcher, dataUrl(baseUrl, "network_scenario_building_points.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "platform_registry.json"))
  ]);
  if (
    !isRecord(storyRaw) ||
    !Array.isArray(storyRaw.scenario_story) ||
    storyRaw.scenario_story.length !== 3
  ) {
    throw new Error("municipal_workspace_story.json の形式が正しくありません");
  }
  if (!isRecord(registryRaw) || !Array.isArray(registryRaw.capabilities)) {
    throw new Error("platform_registry.json の形式が正しくありません");
  }
  if (!isRecord(buildingPointsRaw) || !isRecord(buildingPointsRaw.stories)) {
    throw new Error("network_scenario_building_points.json の形式が正しくありません");
  }
  const map = assertFeatureCollection(mapRaw, "network_scenario_map.geojson") as WorkspaceMapData;
  if (!isRecord(mapRaw) || !isRecord(mapRaw.layer_counts)) {
    throw new Error("network_scenario_map.geojson のメタデータが正しくありません");
  }
  return {
    story: storyRaw as unknown as NetworkScenarioStory,
    map,
    buildingPoints: buildingPointsRaw as unknown as WorkspaceBuildingPoints,
    registry: registryRaw as unknown as PlatformRegistry
  };
}
