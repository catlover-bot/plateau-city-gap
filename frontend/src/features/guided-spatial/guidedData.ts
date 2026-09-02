import type { GeoJsonFeatureCollection } from "../../types";
import type {
  GuidedAreaCatalogItem,
  GuidedAreaContext,
  GuidedAreaContextCatalog,
} from "./guidedTypes";
import type { SectionData } from "../urban-section/UrbanSection";

export const GUIDED_DEFAULT_AREA = "533513314";
export const GUIDED_SHORTLIST = ["533513314", "533512753", "533522274"] as const;
export const GUIDED_EXACT_TARGET_ID = "tran_05dbefba-6a77-40ea-88ac-a568a63a2f05-0";

const CATALOG_PATH = "data/guided/area-context-catalog.json";

export function guidedAssetUrl(path: string, baseUrl = import.meta.env.BASE_URL): string {
  const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  return `${base}${path.replace(/^\//, "")}`;
}

async function jsonResponse<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, cache: "no-cache" });
  if (!response.ok) throw new Error(`${url} を読み込めませんでした (${response.status})`);
  return await response.json() as T;
}

async function sha256Hex(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function loadGuidedAreaCatalog(signal?: AbortSignal): Promise<GuidedAreaContextCatalog> {
  const catalog = await jsonResponse<GuidedAreaContextCatalog>(guidedAssetUrl(CATALOG_PATH), signal);
  if (catalog.schema_version !== "citygap.guided-area-context-catalog@1" || catalog.items.length !== 495) {
    throw new Error("調査範囲一覧の形式が一致しません");
  }
  return catalog;
}

export async function loadGuidedAreaContext(
  item: GuidedAreaCatalogItem,
  signal?: AbortSignal,
): Promise<GuidedAreaContext> {
  const url = guidedAssetUrl(item.context_path);
  const response = await fetch(url, { signal, cache: "no-cache" });
  if (!response.ok) throw new Error(`${url} を読み込めませんでした (${response.status})`);
  const body = await response.text();
  if (await sha256Hex(body) !== item.context_sha256) {
    throw new Error(`範囲データのhashが一致しません (${item.mesh_code})`);
  }
  const context = JSON.parse(body) as GuidedAreaContext;
  if (
    context.schema_version !== "citygap.guided-area-context@1"
    || context.mesh_code !== item.mesh_code
    || context.area_geometry_sha256 !== item.area_geometry_sha256
  ) {
    throw new Error(`範囲データのidentityが一致しません (${item.mesh_code})`);
  }
  return context;
}

export async function loadGuidedSectionData(
  reference: { path?: string; sha256?: string; bytes?: number; pack_id?: string },
  signal?: AbortSignal,
): Promise<SectionData> {
  if (!reference.path || !reference.sha256 || !reference.pack_id) throw new Error("断面referenceが不足しています");
  const response = await fetch(guidedAssetUrl(reference.path), { signal, cache: "no-cache" });
  if (!response.ok) throw new Error(`断面を読み込めませんでした (${response.status})`);
  const body = await response.text();
  if (reference.bytes !== undefined && new TextEncoder().encode(body).byteLength !== reference.bytes) {
    throw new Error("断面artifactのsizeが一致しません");
  }
  if (await sha256Hex(body) !== reference.sha256) throw new Error("断面artifactのhashが一致しません");
  const data = JSON.parse(body) as SectionData;
  if (data.pack_id !== reference.pack_id) throw new Error("断面データと選択範囲の参照が一致しません");
  return data;
}

export function oneAreaCollection(
  meshes: GeoJsonFeatureCollection,
  meshCode: string,
): GeoJsonFeatureCollection {
  const feature = meshes.features.find((candidate) => String(candidate.properties?.mesh_code) === meshCode);
  return { type: "FeatureCollection", features: feature ? [feature] : [] };
}

export function exactOrAreaTarget(
  context: GuidedAreaContext | null,
  area: GeoJsonFeatureCollection,
): { geometry: GeoJsonFeatureCollection; resolution: "exact" | "area_fallback" } {
  if (context?.mesh_code === GUIDED_DEFAULT_AREA) {
    const targetBase = GUIDED_EXACT_TARGET_ID.replace(/-0$/, "");
    const feature = context.layers.roads.features.find((candidate) =>
      String(candidate.id) === GUIDED_EXACT_TARGET_ID
      || String(candidate.id) === `${targetBase}:0`
      || (String(candidate.properties?.object_id) === targetBase && Number(candidate.properties?.surface_index) === 0),
    );
    if (feature) return { geometry: { type: "FeatureCollection", features: [feature] }, resolution: "exact" };
  }
  return { geometry: area, resolution: "area_fallback" };
}

export const EMPTY_GUIDED_COLLECTION: GeoJsonFeatureCollection = { type: "FeatureCollection", features: [] };
