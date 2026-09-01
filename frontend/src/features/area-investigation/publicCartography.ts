import type { GeoJsonFeature, GeoJsonFeatureCollection } from "../../types";
import type { AreaTarget, InvestigationAreaSummary } from "./areaTypes";

export type PublicStoryId =
  | "population-age"
  | "building-use"
  | "establishments"
  | "urban-planning"
  | "transport";

export type TargetResolution = "exact" | "reference_position" | "area_fallback";
export type PublicTargetKind = "building" | "road" | "facility" | "mesh";
export type PublicMapRenderState = "loading" | "ready" | "degraded";

interface DerivativeArtifact {
  path: string;
  feature_count: number;
  geometry_types: string[];
  property_allowlist: string[];
  sha256: string;
}

export interface PublicCartographyManifest {
  schema_version: "citygap.public-cartography@1";
  artifact_kind: "display_derivative";
  rule_version: string;
  source: {
    path: string;
    version: string;
    sha256: string;
    city_code: "26202";
    crs: "EPSG:4326";
  };
  scope: {
    area_id: string;
    area_version: number;
    radius_m: number;
    area_content_sha256: string;
    origin?: {
      kind: "station";
      source_feature_id: string;
      coordinates: [number, number];
    };
  };
  target_ids: string[];
  resolved_target_ids: Record<string, string[]>;
  artifacts: Record<"buildings" | "roads" | "planning", DerivativeArtifact>;
}

export interface PublicCartographyData {
  manifest: PublicCartographyManifest;
  buildings: GeoJsonFeatureCollection;
  roads: GeoJsonFeatureCollection;
  planning: GeoJsonFeatureCollection;
}

export interface PublicAreaMapGeometry {
  center: [number, number];
  radiusM: number;
  polygon: GeoJsonFeatureCollection;
  outsideMask: GeoJsonFeatureCollection;
  bounds: { west: number; south: number; east: number; north: number };
}

export interface PublicTargetRender {
  kind: PublicTargetKind;
  resolution: TargetResolution;
  label: string;
  objectId: string;
  geometry: GeoJsonFeatureCollection;
  longitude: number;
  latitude: number;
}

export interface PublicCartographyPresentation {
  data: PublicCartographyData;
  area: PublicAreaMapGeometry | null;
  activeStory: PublicStoryId | null;
  target: PublicTargetRender | null;
  showTarget: boolean;
  derivativeAvailable: boolean;
}

export interface PublicLegendItem {
  label: string;
  color: string;
  shape?: "fill" | "line" | "circle";
}

export interface PublicLegend {
  title: string;
  note?: string;
  items: PublicLegendItem[];
}

const EMPTY: GeoJsonFeatureCollection = { type: "FeatureCollection", features: [] };
const EARTH_RADIUS_M = 6_378_137;

function parseCollection(value: unknown, label: string): GeoJsonFeatureCollection {
  if (
    typeof value !== "object" ||
    value === null ||
    (value as { type?: unknown }).type !== "FeatureCollection" ||
    !Array.isArray((value as { features?: unknown }).features)
  ) {
    throw new Error(`${label} display geometryの形式が正しくありません。`);
  }
  return value as GeoJsonFeatureCollection;
}

export function parsePublicCartographyManifest(value: unknown): PublicCartographyManifest {
  if (
    typeof value !== "object" ||
    value === null ||
    (value as { schema_version?: unknown }).schema_version !== "citygap.public-cartography@1" ||
    (value as { artifact_kind?: unknown }).artifact_kind !== "display_derivative"
  ) {
    throw new Error("Public cartography manifestの形式が正しくありません。");
  }
  return value as PublicCartographyManifest;
}

export async function loadPublicCartographyData(
  fetcher: typeof fetch = fetch,
  baseUrl = import.meta.env.BASE_URL,
): Promise<PublicCartographyData> {
  const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  const root = `${base}data/cartography/`;
  const manifestResponse = await fetcher(`${root}manifest.json`);
  if (!manifestResponse.ok) {
    throw new Error(`Public cartographyを読み込めません（HTTP ${manifestResponse.status}）`);
  }
  const manifest = parsePublicCartographyManifest(await manifestResponse.json());
  const [buildingsResponse, roadsResponse, planningResponse] = await Promise.all([
    fetcher(`${root}${manifest.artifacts.buildings.path}`),
    fetcher(`${root}${manifest.artifacts.roads.path}`),
    fetcher(`${root}${manifest.artifacts.planning.path}`),
  ]);
  for (const response of [buildingsResponse, roadsResponse, planningResponse]) {
    if (!response.ok) throw new Error(`Public display geometryを読み込めません（HTTP ${response.status}）`);
  }
  return {
    manifest,
    buildings: parseCollection(await buildingsResponse.json(), "建物"),
    roads: parseCollection(await roadsResponse.json(), "道路"),
    planning: parseCollection(await planningResponse.json(), "都市計画"),
  };
}

function destination(center: [number, number], radiusM: number, bearingRadians: number): [number, number] {
  const longitude = center[0] * Math.PI / 180;
  const latitude = center[1] * Math.PI / 180;
  const angularDistance = radiusM / EARTH_RADIUS_M;
  const nextLatitude = Math.asin(
    Math.sin(latitude) * Math.cos(angularDistance)
      + Math.cos(latitude) * Math.sin(angularDistance) * Math.cos(bearingRadians),
  );
  const nextLongitude = longitude + Math.atan2(
    Math.sin(bearingRadians) * Math.sin(angularDistance) * Math.cos(latitude),
    Math.cos(angularDistance) - Math.sin(latitude) * Math.sin(nextLatitude),
  );
  return [nextLongitude * 180 / Math.PI, nextLatitude * 180 / Math.PI];
}

export function buildPublicAreaGeometry(
  center: [number, number],
  radiusM: number,
): PublicAreaMapGeometry {
  const ring = Array.from({ length: 96 }, (_, index) =>
    destination(center, radiusM, index * 2 * Math.PI / 96));
  ring.push(ring[0]);
  const longitudes = ring.map((coordinate) => coordinate[0]);
  const latitudes = ring.map((coordinate) => coordinate[1]);
  const areaFeature: GeoJsonFeature = {
    type: "Feature",
    id: "public-investigation-area",
    properties: { radius_m: radiusM, geometry_semantics: "display_geodesic_circle" },
    geometry: { type: "Polygon", coordinates: [ring] },
  };
  const world = [
    [-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85],
  ];
  const maskFeature: GeoJsonFeature = {
    type: "Feature",
    id: "public-investigation-area-mask",
    properties: { role: "outside_context" },
    geometry: { type: "Polygon", coordinates: [world, [...ring].reverse()] },
  };
  return {
    center,
    radiusM,
    polygon: { type: "FeatureCollection", features: [areaFeature] },
    outsideMask: { type: "FeatureCollection", features: [maskFeature] },
    bounds: {
      west: Math.min(...longitudes),
      south: Math.min(...latitudes),
      east: Math.max(...longitudes),
      north: Math.max(...latitudes),
    },
  };
}

function matches(feature: GeoJsonFeature, objectId: string): boolean {
  return String(feature.properties?.object_id ?? feature.id ?? "") === objectId;
}

export function derivativeAvailableFor(
  data: PublicCartographyData,
  summary: InvestigationAreaSummary | null,
): boolean {
  if (!summary || summary.origin.kind !== "station") return false;
  const origin = data.manifest.scope.origin;
  if (!origin) {
    return summary.radius_m <= data.manifest.scope.radius_m
      && summary.origin.source_feature_id === "station-007";
  }
  return summary.radius_m <= data.manifest.scope.radius_m
    && summary.origin.source_feature_id === origin.source_feature_id
    && Math.abs(summary.origin.coordinates[0] - origin.coordinates[0]) < 1e-7
    && Math.abs(summary.origin.coordinates[1] - origin.coordinates[1]) < 1e-7;
}

export function resolvePublicTarget(
  target: AreaTarget | null,
  data: PublicCartographyData,
  derivativeAvailable: boolean,
): PublicTargetRender | null {
  if (!target) return null;
  const base = {
    kind: target.object_type as PublicTargetKind,
    label: target.label,
    objectId: target.source_object_id,
    longitude: target.longitude,
    latitude: target.latitude,
  };
  const targetKind = target.object_type === "building" ? "buildings" : "roads";
  const manifestResolvesTarget = data.manifest.target_ids.includes(target.source_object_id)
    && (data.manifest.resolved_target_ids[targetKind] ?? []).includes(target.source_object_id);
  if (
    derivativeAvailable && manifestResolvesTarget
    && (target.object_type === "building" || target.object_type === "road")
  ) {
    const source = target.object_type === "building" ? data.buildings : data.roads;
    const features = source.features.filter((feature) => matches(feature, target.source_object_id));
    if (features.length) {
      return { ...base, resolution: "exact", geometry: { type: "FeatureCollection", features } };
    }
  }
  if (target.object_type === "mesh") {
    return { ...base, resolution: "area_fallback", geometry: EMPTY };
  }
  return {
    ...base,
    resolution: "reference_position",
    geometry: {
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        id: target.source_object_id,
        properties: { object_type: target.object_type, resolution: "reference_position" },
        geometry: { type: "Point", coordinates: [target.longitude, target.latitude] },
      }],
    },
  };
}

export function publicStoryLegend(story: PublicStoryId | null, spatialAvailable = true): PublicLegend | null {
  if (story === "population-age") return {
    title: "65歳以上人口の相対分布",
    note: "500mメッシュ・2020年・舞鶴市内での相対比較",
    items: [
      { label: "比較的低い", color: "#dcebe6", shape: "fill" },
      { label: "中間", color: "#82b5a8", shape: "fill" },
      { label: "比較的高い", color: "#2f7466", shape: "fill" },
    ],
  };
  if (story === "building-use") return spatialAvailable ? {
    title: "PLATEAU建物用途",
    note: "公式用途属性・現在用途ではありません",
    items: [
      { label: "住宅", color: "#6f9f91", shape: "fill" },
      { label: "共同住宅", color: "#527b87", shape: "fill" },
      { label: "商業施設", color: "#9a7a50", shape: "fill" },
      { label: "その他・不明", color: "#aab3ae", shape: "fill" },
    ],
  } : { title: "建物の使われ方", note: "この範囲の個別位置情報は未登録です", items: [] };
  if (story === "establishments") return {
    title: "事業所",
    note: "範囲集計・個別事業所の位置は表示していません",
    items: [],
  };
  if (story === "urban-planning") return spatialAvailable ? {
    title: "PLATEAU都市計画",
    note: "利用可能な公式objectのみ",
    items: [
      { label: "用途地域等", color: "#78998e", shape: "fill" },
      { label: "区域・境界", color: "#526b65", shape: "line" },
    ],
  } : { title: "都市計画", note: "この範囲の境界geometryは未登録です", items: [] };
  if (story === "transport") return {
    title: "交通の登録地点",
    note: "運行・徒歩到達性は含みません",
    items: [
      { label: "駅", color: "#365f73", shape: "circle" },
      { label: "バス停", color: "#708d91", shape: "circle" },
    ],
  };
  return null;
}
