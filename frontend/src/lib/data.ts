import type {
  AppData,
  FinalDemoData,
  GeoJsonFeatureCollection,
  Manifest,
  MeshMetrics,
  PlateauMetadata,
  Summary
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
  const [manifestRaw, meshesRaw, top10Raw, summaryRaw, finalDemoRaw] = await Promise.all([
    fetchJson(fetcher, dataUrl(baseUrl, "manifest.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "mesh_metrics.geojson")),
    fetchJson(fetcher, dataUrl(baseUrl, "top10.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "summary.json")),
    fetchJson(fetcher, dataUrl(baseUrl, "final_demo.json"))
  ]);
  if (!isRecord(manifestRaw)) throw new Error("manifest.json の形式が正しくありません");
  if (!isRecord(summaryRaw)) throw new Error("summary.json の形式が正しくありません");
  if (!isRecord(finalDemoRaw)) throw new Error("final_demo.json の形式が正しくありません");

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
    warnings
  };
}
