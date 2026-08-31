import type { AppData, GeoJsonFeature, GeoJsonFeatureCollection } from "../../types";
import type {
  AreaMetric,
  AreaTarget,
  InvestigationAreaFixture,
  InvestigationAreaSummary,
  RadiusMethodology,
} from "./areaTypes";

export const AREA_MIN_RADIUS_M = 100;
export const AREA_MAX_RADIUS_M = 3000;

export interface PublicAreaOrigin {
  kind: "station" | "map_point";
  label: string;
  coordinates: [number, number];
  sourceFeatureId?: string;
}

type XY = [number, number];

const METHODOLOGY_BY_RADIUS: Record<number, RadiusMethodology> = {
  500: "mlit_elderly_walk_reference_500m",
  800: "mlit_general_walk_reference_800m",
  1000: "broad_context_1000m",
};

export function radiusMethodology(radiusM: number): RadiusMethodology {
  return METHODOLOGY_BY_RADIUS[radiusM] ?? "custom_radius";
}

export function validatePublicRadius(radiusM: number): number {
  if (!Number.isInteger(radiusM)) throw new Error("半径は1m単位の整数で入力してください。");
  if (radiusM < AREA_MIN_RADIUS_M || radiusM > AREA_MAX_RADIUS_M) {
    throw new Error("半径は100m以上3000m以下で入力してください。");
  }
  return radiusM;
}

export function parseInvestigationAreaFixture(value: unknown): InvestigationAreaFixture {
  if (
    typeof value !== "object" ||
    value === null ||
    (value as { schema_version?: unknown }).schema_version !== "citygap.area-summary@1" ||
    !Array.isArray((value as { areas?: unknown }).areas)
  ) {
    throw new Error("Investigation Area fixtureの形式が正しくありません。");
  }
  return value as InvestigationAreaFixture;
}

export async function loadInvestigationAreaFixture(
  fetcher: typeof fetch = fetch,
  baseUrl = import.meta.env.BASE_URL,
): Promise<InvestigationAreaFixture> {
  const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  const response = await fetcher(`${base}data/investigation_area_summary.json`);
  if (!response.ok) throw new Error(`Investigation Areaを読み込めません（HTTP ${response.status}）`);
  return parseInvestigationAreaFixture(await response.json());
}

function numberValue(value: unknown): number | null {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function pointCoordinates(feature: GeoJsonFeature): XY | null {
  if (feature.geometry?.type !== "Point" || !Array.isArray(feature.geometry.coordinates)) return null;
  const [longitude, latitude] = feature.geometry.coordinates;
  const x = numberValue(longitude);
  const y = numberValue(latitude);
  return x === null || y === null ? null : [x, y];
}

function localPoint(coordinates: XY, center: XY): XY {
  const latitudeRadians = center[1] * Math.PI / 180;
  return [
    (coordinates[0] - center[0]) * 111_320 * Math.cos(latitudeRadians),
    (coordinates[1] - center[1]) * 110_540,
  ];
}

function polygonArea(points: XY[]): number {
  if (points.length < 3) return 0;
  let area = 0;
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    const next = points[(index + 1) % points.length];
    area += current[0] * next[1] - next[0] * current[1];
  }
  return Math.abs(area) / 2;
}

function cross(start: XY, end: XY, point: XY): number {
  return (end[0] - start[0]) * (point[1] - start[1])
    - (end[1] - start[1]) * (point[0] - start[0]);
}

function intersection(a: XY, b: XY, start: XY, end: XY): XY {
  const edgeX = end[0] - start[0];
  const edgeY = end[1] - start[1];
  const segmentX = b[0] - a[0];
  const segmentY = b[1] - a[1];
  const denominator = segmentX * edgeY - segmentY * edgeX;
  if (Math.abs(denominator) < 1e-9) return b;
  const t = ((start[0] - a[0]) * edgeY - (start[1] - a[1]) * edgeX) / denominator;
  return [a[0] + t * segmentX, a[1] + t * segmentY];
}

function clipPolygon(subject: XY[], clip: XY[]): XY[] {
  let output = subject;
  for (let edgeIndex = 0; edgeIndex < clip.length; edgeIndex += 1) {
    const start = clip[edgeIndex];
    const end = clip[(edgeIndex + 1) % clip.length];
    const input = output;
    output = [];
    if (!input.length) break;
    let previous = input[input.length - 1];
    for (const current of input) {
      const currentInside = cross(start, end, current) >= 0;
      const previousInside = cross(start, end, previous) >= 0;
      if (currentInside) {
        if (!previousInside) output.push(intersection(previous, current, start, end));
        output.push(current);
      } else if (previousInside) {
        output.push(intersection(previous, current, start, end));
      }
      previous = current;
    }
  }
  return output;
}

function geometryRings(feature: GeoJsonFeature): unknown[][] {
  const geometry = feature.geometry;
  if (!geometry || !Array.isArray(geometry.coordinates)) return [];
  if (geometry.type === "Polygon") return [geometry.coordinates[0] as unknown[]];
  if (geometry.type === "MultiPolygon") {
    return (geometry.coordinates as unknown[][][]).map((polygon) => polygon[0] as unknown[]);
  }
  return [];
}

function projectedRing(ring: unknown[], center: XY): XY[] {
  return ring.flatMap((value) => {
    if (!Array.isArray(value) || value.length < 2) return [];
    const longitude = numberValue(value[0]);
    const latitude = numberValue(value[1]);
    return longitude === null || latitude === null
      ? []
      : [localPoint([longitude, latitude], center)];
  });
}

function circlePolygon(radiusM: number): XY[] {
  return Array.from({ length: 96 }, (_, index) => {
    const angle = 2 * Math.PI * index / 96;
    return [radiusM * Math.cos(angle), radiusM * Math.sin(angle)] as XY;
  });
}

function overlap(feature: GeoJsonFeature, center: XY, circle: XY[]): { ratio: number; area: number } {
  let sourceArea = 0;
  let intersectionArea = 0;
  for (const ring of geometryRings(feature)) {
    const projected = projectedRing(ring, center);
    sourceArea += polygonArea(projected);
    intersectionArea += polygonArea(clipPolygon(projected, circle));
  }
  return {
    ratio: sourceArea > 0 ? Math.min(1, intersectionArea / sourceArea) : 0,
    area: intersectionArea,
  };
}

function pointDistanceM(coordinates: XY, center: XY): number {
  const [x, y] = localPoint(coordinates, center);
  return Math.hypot(x, y);
}

function countPoints(
  collection: GeoJsonFeatureCollection | null,
  center: XY,
  radiusM: number,
): number {
  return collection?.features.reduce((count, feature) => {
    const coordinates = pointCoordinates(feature);
    return count + (coordinates && pointDistanceM(coordinates, center) <= radiusM ? 1 : 0);
  }, 0) ?? 0;
}

function nearestMesh(data: AppData, center: XY): GeoJsonFeature {
  return [...data.meshes.features].sort((left, right) => {
    const leftPoint: XY = [
      numberValue(left.properties?.centroid_lon) ?? center[0],
      numberValue(left.properties?.centroid_lat) ?? center[1],
    ];
    const rightPoint: XY = [
      numberValue(right.properties?.centroid_lon) ?? center[0],
      numberValue(right.properties?.centroid_lat) ?? center[1],
    ];
    return pointDistanceM(leftPoint, center) - pointDistanceM(rightPoint, center);
  })[0];
}

function nearestPoint(
  collection: GeoJsonFeatureCollection | null,
  center: XY,
  radiusM: number,
): GeoJsonFeature | null {
  return collection?.features
    .map((feature) => ({ feature, coordinates: pointCoordinates(feature) }))
    .filter((item): item is { feature: GeoJsonFeature; coordinates: XY } => Boolean(item.coordinates))
    .map((item) => ({ ...item, distance: pointDistanceM(item.coordinates, center) }))
    .filter((item) => item.distance <= radiusM)
    .sort((left, right) => left.distance - right.distance)[0]?.feature ?? null;
}

function meshTarget(data: AppData, center: XY): AreaTarget {
  const mesh = nearestMesh(data, center);
  return {
    scope: "mesh",
    object_type: "mesh",
    source_object_id: String(mesh.properties?.mesh_code ?? "unresolved-mesh"),
    label: `${String(mesh.properties?.area_label ?? "選択地点")}の500mメッシュ（正直なfallback）`,
    longitude: numberValue(mesh.properties?.centroid_lon) ?? center[0],
    latitude: numberValue(mesh.properties?.centroid_lat) ?? center[1],
    dataset: "2020国勢調査500mメッシュ",
    role: "primary",
  };
}

function runtimeMetrics(data: AppData, center: XY, radiusM: number): AreaMetric[] {
  const circle = circlePolygon(radiusM);
  let population = 0;
  let elderly = 0;
  let coveredArea = 0;
  let populationRecords = 0;
  for (const feature of data.meshes.features) {
    const result = overlap(feature, center, circle);
    if (result.ratio <= 0) continue;
    const populationValue = numberValue(feature.properties?.population);
    const elderlyValue = numberValue(feature.properties?.elderly_population);
    if (populationValue !== null) {
      population += populationValue * result.ratio;
      coveredArea += result.area;
      populationRecords += 1;
    }
    if (elderlyValue !== null) elderly += elderlyValue * result.ratio;
  }
  const coverage = Math.min(1, coveredArea / (Math.PI * radiusM * radiusM));
  const censusSource = { dataset: "2020国勢調査500mメッシュ", source_date: "2020-10-01" };
  const unavailable = (
    key: AreaMetric["key"],
    group: AreaMetric["group"],
    label: string,
    limitation: string,
  ): AreaMetric => ({
    key,
    group,
    label,
    status: "unavailable",
    value: null,
    unit: "—",
    coverage_ratio: null,
    calculation: "exact",
    source: { dataset: "Public preview source not loaded", source_date: "unknown" },
    limitation,
  });
  return [
    {
      key: "population",
      group: "population",
      label: "人口",
      status: coverage >= 0.995 ? "known" : "partial",
      value: Math.round(population),
      unit: "人（面積按分推計）",
      coverage_ratio: Number(coverage.toFixed(4)),
      calculation: "area_weighted_estimate",
      records: populationRecords,
      source: censusSource,
      limitation: "500mメッシュ値を円との面積重複率で按分。欠損は0補完しません。",
    },
    {
      key: "age_distribution",
      group: "age_distribution",
      label: "年齢分布",
      status: "partial",
      value: { age_65_plus: Math.round(elderly), total: Math.round(population) },
      unit: "人（面積按分推計）",
      coverage_ratio: Number(coverage.toFixed(4)),
      calculation: "area_weighted_estimate",
      source: censusSource,
      limitation: "P0公開値は総人口と65歳以上のみ。全年齢階級の分布ではありません。",
    },
    unavailable("building_use", "building_use", "建物用途分布", "任意地点用のPLATEAU建物用途packが未生成です。別地域のobjectを流用しません。"),
    unavailable("establishments", "establishments", "事業所", "任意地点用の経済センサス集計packが未生成です。"),
    unavailable("urban_planning", "urban_planning", "都市計画", "利用可能な公式都市計画objectを確認できないため補完しません。"),
    {
      key: "transport",
      group: "transport",
      label: "交通",
      status: "known",
      value: {
        stations: countPoints(data.stations, center, radiusM),
        bus_stops: countPoints(data.busStops, center, radiusM),
      },
      unit: "登録地点",
      coverage_ratio: 1,
      calculation: "observation_count",
      source: { dataset: "公開交通地点", source_date: "source metadata参照" },
      limitation: "駅・バス停の登録地点数。運行、現在利用、実際の徒歩到達性は含みません。医療施設は第一表示へ混在させません。",
    },
  ];
}

function runtimeSummary(
  data: AppData,
  origin: PublicAreaOrigin,
  radiusM: number,
): InvestigationAreaSummary {
  const target = meshTarget(data, origin.coordinates);
  const facility = nearestPoint(data.medicalFacilities, origin.coordinates, radiusM);
  const facilityCoordinates = facility ? pointCoordinates(facility) : null;
  const facilityTarget: AreaTarget = facility && facilityCoordinates
    ? {
      scope: "facility",
      object_type: "facility",
      source_object_id: String(facility.properties?.id ?? facility.properties?.name ?? "facility-record"),
      label: String(facility.properties?.name ?? "範囲内の登録施設"),
      longitude: facilityCoordinates[0],
      latitude: facilityCoordinates[1],
      dataset: "国土数値情報 医療機関データ",
      role: "primary",
    }
    : target;
  return {
    id: `public-preview-${origin.coordinates.join("-")}-${radiusM}m`,
    area_series_id: "not-persisted-public-preview",
    version: 1,
    label: `${origin.label}周辺${radiusM}m`,
    geometry_kind: "point_radius",
    origin: {
      kind: origin.kind,
      source_feature_id: origin.sourceFeatureId,
      label: origin.label,
      coordinates: origin.coordinates,
    },
    radius_m: radiusM,
    radius_methodology: radiusMethodology(radiusM),
    clipped_area_ratio: null,
    metrics: runtimeMetrics(data, origin.coordinates, radiusM),
    unknowns: [
      {
        id: "walking-connectivity",
        title: "この半径内を実際に歩いて通れるか",
        importance: "半径は分析上の目安で、横断・階段・通行制限を含む実際の到達性は判断できません。",
        status: "unknown",
        action_type: "field_verification",
        reason_code: "model_limit",
        source_boundary: "半径集計。validated pedestrian networkではありません。",
        target,
        checks: [
          "歩行者が連続して通れるか",
          "横断箇所や通行制限があるか",
          "階段・段差・狭窄があるか",
          "迂回が必要な区間があるか",
        ],
      },
      {
        id: "facility-availability",
        title: facility ? "登録施設が現在も利用できるか" : "地域サービスの現況",
        importance: "公開データだけでは現在の開設状況や地域内の代替手段を判断できません。",
        status: "unknown",
        action_type: "field_verification",
        reason_code: "requires_field_observation",
        source_boundary: "公開地点と500mメッシュ。現在利用や地域運用は含みません。",
        target: facilityTarget,
        checks: facility
          ? ["施設が現地に存在するか", "現在利用できる状態か", "利用時間の掲示があるか", "閉鎖時は移転先の手掛かりがあるか"]
          : ["現地で利用される移動手段は何か", "定期的な地域サービスがあるか", "案内掲示があるか"],
      },
    ],
    status: "unverified",
    content_sha256: null,
  };
}

export function resolveAreaSummary(
  fixture: InvestigationAreaFixture,
  data: AppData,
  origin: PublicAreaOrigin,
  radiusM: number,
): InvestigationAreaSummary {
  validatePublicRadius(radiusM);
  const fixtureArea = fixture.areas.find((area) =>
    origin.kind === "station"
    && origin.sourceFeatureId === area.origin.source_feature_id
    && radiusM === area.radius_m
  );
  return fixtureArea ?? runtimeSummary(data, origin, radiusM);
}
