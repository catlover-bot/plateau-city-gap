import type { AppData, GeoJsonFeature, GeoJsonFeatureCollection, PlateauMetadata } from "../../types";
import type { SpatialSelection } from "../../state/spatial/types";
import type { GuidedAreaContext } from "./guidedTypes";
import type { GuidedTargetChoice } from "./guidedTargets";
import { GUIDED_CHECKS } from "./guidedContent";
import { GUIDED_DEFAULT_AREA, guidedAssetUrl } from "./guidedData";

export const GUIDED_3D_EXAMPLE_QUERY = "?experience=guided&story=understand&mapMode=plateau3d&selectionType=mesh&selection=533513314";

export function supportsGuided3D(areaId: string, context: GuidedAreaContext | null): boolean {
  return areaId === GUIDED_DEFAULT_AREA && context?.mesh_code === areaId
    && context.section.status === "available"
    && context.section.pack_id === "maizuru-533513314-plateau-2025-v1";
}

export async function loadGuided3DData(data: AppData, signal: AbortSignal): Promise<AppData> {
  const responses = await Promise.all(["plateau_metadata.json", "plateau_roads.geojson"].map(async (file) => {
    const response = await fetch(guidedAssetUrl(`data/${file}`), { signal });
    if (!response.ok) throw new Error(`3Dデータを読み込めません (${response.status})`);
    return response.json();
  }));
  const metadata = responses[0] as PlateauMetadata;
  const roads = responses[1] as GeoJsonFeatureCollection;
  if (metadata.reference_layer?.deep_dive_mesh_code !== GUIDED_DEFAULT_AREA || roads.type !== "FeatureCollection") {
    throw new Error("3Dデータの対象地域が一致しません");
  }
  return { ...data, plateauMetadata: metadata, plateauRoads: roads };
}

export function guidedObjectFeature(context: GuidedAreaContext | null, kind: "building" | "road", id: string): GeoJsonFeature | null {
  return context?.layers[kind === "building" ? "buildings" : "roads"].features.find((feature) =>
    String(feature.id) === id || String(feature.properties?.object_id) === id,
  ) ?? null;
}

export function guidedObjectTarget(object: SpatialSelection | null, context: GuidedAreaContext | null): GuidedTargetChoice | null {
  if (!object || (object.type !== "building" && object.type !== "road") || object.properties?.parent_mesh_code !== context?.mesh_code) return null;
  const feature = guidedObjectFeature(context, object.type, object.id);
  if (!feature) return null;
  return {
    key: `${object.type}:${String(feature.id ?? object.id)}`,
    kind: object.type,
    label: object.type === "building" ? "選択したPLATEAU建物" : String(feature.properties?.road_name ?? object.label ?? "選択したPLATEAU道路面"),
    reason: object.type === "building"
      ? "建物の形が分かっても、入口と現在の利用状況はデータだけでは判断できません。"
      : "道路面の形が分かっても、実際の通行条件は現地で確認が必要です。",
    geometry: { type: "FeatureCollection", features: [feature] },
    resolution: "exact",
    checks: GUIDED_CHECKS[object.type],
  };
}

export function selectionFromGuidedTarget(target: GuidedTargetChoice, area: SpatialSelection): SpatialSelection | null {
  if (target.kind !== "building" && target.kind !== "road") return null;
  const feature = target.geometry.features[0];
  if (!feature) return null;
  return {
    ...area,
    type: target.kind,
    id: String(feature.id ?? feature.properties?.object_id),
    label: target.label,
    properties: { ...feature.properties, parent_mesh_code: area.id },
  };
}
