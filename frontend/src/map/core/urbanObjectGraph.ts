import type {
  AppData,
  GeoJsonFeature,
  GeoJsonFeatureCollection,
  WorkspaceMapData,
  WorkspacePhase,
} from "../../types";
import type { SpatialResolution, SpatialSelection } from "../../state/spatial/types";

export type UrbanObjectKind =
  | "city"
  | "district"
  | "mesh"
  | "building_group"
  | "building"
  | "road"
  | "terrain"
  | "landuse"
  | "planning"
  | "hazard"
  | "site"
  | "analysis"
  | "finding";

export interface UrbanObjectNode {
  id: string;
  kind: UrbanObjectKind;
  label: string;
  source: string;
  year: string;
  attributes: Record<string, string | number | boolean | null>;
}

export type UrbanObjectRelationKind =
  | "contains"
  | "belongs_to"
  | "nearest"
  | "linked"
  | "intersects"
  | "within"
  | "affects"
  | "derived_from"
  | "explains";

export interface UrbanObjectRelation {
  from: string;
  to: string;
  kind: UrbanObjectRelationKind;
  label: string;
  semantics: string;
}

export interface ResolutionAvailability {
  resolution: SpatialResolution;
  available: boolean;
  count: number | null;
  reason: string;
}

export interface UrbanObjectGraph {
  nodes: UrbanObjectNode[];
  relations: UrbanObjectRelation[];
  selectedObjectId: string;
  findingId: string | null;
  resolution: ResolutionAvailability[];
  plateauRequired: boolean;
  plateauOffLoss: string[];
}

const RESOLUTIONS: SpatialResolution[] = [
  "city", "district", "mesh", "building_group", "building", "road", "site",
];

function asFinite(value: unknown): number | null {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

function pointFromSelection(selection: SpatialSelection | null): [number, number] | null {
  const longitude = asFinite(selection?.longitude ?? selection?.properties?.longitude);
  const latitude = asFinite(selection?.latitude ?? selection?.properties?.latitude);
  return longitude === null || latitude === null ? null : [longitude, latitude];
}

function rings(feature: GeoJsonFeature): number[][][][] {
  const coordinates = feature.geometry?.coordinates;
  if (!Array.isArray(coordinates)) return [];
  if (feature.geometry?.type === "Polygon") return [coordinates as number[][][]];
  if (feature.geometry?.type === "MultiPolygon") return coordinates as number[][][][];
  return [];
}

function inRing(point: [number, number], ring: number[][]): boolean {
  let inside = false;
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const current = ring[index];
    const prior = ring[previous];
    if (!current || !prior) continue;
    const crosses = current[1] > point[1] !== prior[1] > point[1]
      && point[0] < ((prior[0] - current[0]) * (point[1] - current[1])) / (prior[1] - current[1]) + current[0];
    if (crosses) inside = !inside;
  }
  return inside;
}

function contains(feature: GeoJsonFeature, point: [number, number]): boolean {
  return rings(feature).some((polygon) => {
    const [exterior, ...holes] = polygon;
    return Boolean(exterior && inRing(point, exterior) && !holes.some((hole) => inRing(point, hole)));
  });
}

function allCoordinatePairs(value: unknown): Array<[number, number]> {
  if (!Array.isArray(value)) return [];
  if (value.length >= 2 && Number.isFinite(value[0]) && Number.isFinite(value[1])) {
    return [[Number(value[0]), Number(value[1])]];
  }
  return value.flatMap(allCoordinatePairs);
}

function approximateDistanceM(a: [number, number], b: [number, number]): number {
  const latitudeScale = 111_320;
  const longitudeScale = Math.cos((a[1] * Math.PI) / 180) * latitudeScale;
  return Math.hypot((a[0] - b[0]) * longitudeScale, (a[1] - b[1]) * latitudeScale);
}

function nearestRoad(roads: GeoJsonFeatureCollection | null, point: [number, number] | null): { feature: GeoJsonFeature; distanceM: number } | null {
  if (!roads || !point) return null;
  let result: { feature: GeoJsonFeature; distanceM: number } | null = null;
  for (const feature of roads.features) {
    const distanceM = Math.min(...allCoordinatePairs(feature.geometry?.coordinates).map((candidate) => approximateDistanceM(point, candidate)));
    if (Number.isFinite(distanceM) && (!result || distanceM < result.distanceM)) result = { feature, distanceM };
  }
  return result;
}

function contextFeatures(
  workspace: WorkspaceMapData | null,
  phase: WorkspacePhase,
  point: [number, number] | null,
  layerType: "landuse_context" | "planning_context" | "hazard_context",
): GeoJsonFeature[] {
  if (!workspace || !point || phase === "baseline") return [];
  return workspace.features.filter((feature) => (
    feature.properties?.layer_type === layerType
    && feature.properties.story_id === phase
    && contains(feature, point)
  ));
}

function selectedMeshCode(data: AppData, selection: SpatialSelection | null): string | null {
  if (selection?.type === "mesh" || selection?.type === "building_group") return selection.id;
  const parent = selection?.properties?.parent_mesh_code;
  if (typeof parent === "string") return parent;
  if (selection?.type === "building") return data.plateauMetadata?.reference_layer?.deep_dive_mesh_code ?? null;
  return null;
}

function nodeId(kind: UrbanObjectKind, id: string): string {
  return `${kind}:${id}`;
}

export function buildUrbanObjectGraph(input: {
  data: AppData;
  selection: SpatialSelection | null;
  primaryLayer: string;
  workspace?: WorkspaceMapData | null;
  workspacePhase?: WorkspacePhase;
}): UrbanObjectGraph {
  const { data, selection, primaryLayer, workspace = null, workspacePhase = "baseline" } = input;
  const year = String(data.plateauMetadata?.year ?? data.plateauMetadata?.source_year ?? "2025");
  const selectionPoint = pointFromSelection(selection);
  const containingMesh = selectionPoint
    ? data.meshes.features.find((feature) => contains(feature, selectionPoint))
    : null;
  const meshCode = selectedMeshCode(data, selection) ?? (containingMesh ? String(containingMesh.properties?.mesh_code ?? "") || null : null);
  const deepDive = data.plateauMetadata?.reference_layer;
  const isDeepDive = Boolean(meshCode && meshCode === deepDive?.deep_dive_mesh_code);
  const point = selectionPoint ?? (isDeepDive && deepDive?.viewpoint?.longitude && deepDive?.viewpoint?.latitude
    ? [deepDive.viewpoint.longitude, deepDive.viewpoint.latitude] as [number, number]
    : null);
  const meshFeature = meshCode
    ? data.meshes.features.find((feature) => String(feature.properties?.mesh_code ?? "") === meshCode)
    : null;
  const meshProperties = meshFeature?.properties ?? (selection?.type === "mesh" ? selection.properties ?? {} : {});
  const buildingCount = isDeepDive ? Number(deepDive?.deep_dive_buildings ?? 0) : 0;
  const findingId = meshCode ? nodeId("finding", meshCode) : null;
  const selectionKind: UrbanObjectKind = selection?.type === "scenario_site" || selection?.type === "facility"
    ? "site"
    : selection?.type === "temporal_change" || selection?.type === "validation_sample"
      ? "analysis"
      : selection?.type ?? "city";
  const selectedObjectId = nodeId(selectionKind, selection?.id ?? data.city.id);
  const nodes: UrbanObjectNode[] = [{
    id: nodeId("city", data.city.id), kind: "city", label: data.city.name,
    source: "自治体境界・公開統計", year: "現行", attributes: { city_code: data.city.code },
  }];
  const relations: UrbanObjectRelation[] = [];

  if (meshCode) {
    nodes.push({
      id: nodeId("mesh", meshCode), kind: "mesh",
      label: String(meshProperties.area_label ?? `500mメッシュ ${meshCode}`),
      source: "国勢調査500mメッシュ / CITY GAP", year: "2020 / analysis",
      attributes: {
        mesh_code: meshCode,
        population: asFinite(meshProperties.population),
        elderly_population: asFinite(meshProperties.elderly_population),
        exploratory_score_c: asFinite(meshProperties.exploratory_score_c),
        disclosure_status: String(meshProperties.disclosure_status ?? "集約公開"),
      },
    });
    nodes.push({
      id: findingId!, kind: "finding", label: `追加調査候補 ${meshCode}`,
      source: "CITY GAP analysis", year: "current run",
      attributes: { primary_layer: primaryLayer, claim: "追加調査候補。危険度・政策優先順位ではない" },
    });
    relations.push({ from: findingId!, to: nodeId("mesh", meshCode), kind: "derived_from", label: "500m統計から発見", semantics: "集約統計と施設距離による探索指標" });
    relations.push({ from: nodeId("mesh", meshCode), to: findingId!, kind: "explains", label: "このメッシュに関係するFinding", semantics: "reverse traceability" });
  }

  if (meshCode) {
    const groupId = nodeId("building_group", meshCode);
    nodes.push({
      id: groupId, kind: "building_group",
      label: isDeepDive ? `PLATEAU住宅建物群 ${buildingCount}棟` : "PLATEAU建物群（対象範囲外）",
      source: "Project PLATEAU 舞鶴市 3D都市モデル", year,
      attributes: {
        building_count: buildingCount,
        relation_method: deepDive?.reason ?? data.plateauMetadata?.building_layer?.reason ?? "coverage not verified",
        privacy: "建物別人口は公開しない",
      },
    });
    relations.push({ from: nodeId("mesh", meshCode), to: groupId, kind: "contains", label: isDeepDive ? `${buildingCount}棟を詳細化` : "公式建物0棟を確認", semantics: "PLATEAU 3D Tiles代表点・bboxによるメッシュ包含監査" });
    if (findingId) relations.push({ from: findingId, to: groupId, kind: "explains", label: "Findingを建物群へ解像度上昇", semantics: "統計値は建物別実人数へ分解しない" });
  }

  if (selection?.type === "building") {
    nodes.push({
      id: selectedObjectId, kind: "building", label: selection.label ?? "PLATEAU建物",
      source: "Project PLATEAU CityGML / 3D Tiles", year,
      attributes: {
        gml_id: selection.id,
        usage: String(selection.properties?.usage ?? "属性なし"),
        measured_height_m: asFinite(selection.properties?.measured_height_m),
        storeys_above_ground: asFinite(selection.properties?.storeys_above_ground),
        footprint_area_m2: asFinite(selection.properties?.footprint_area_m2),
        source_version: year,
        population_semantics: "model-estimated allocation; actual resident countではない。公開画面では非表示",
      },
    });
    if (meshCode) {
      relations.push({ from: nodeId("building_group", meshCode), to: selectedObjectId, kind: "contains", label: "建物群の構成地物", semantics: "公式PLATEAU building object" });
      if (findingId) relations.push({ from: selectedObjectId, to: findingId, kind: "linked", label: "この建物に関係するFinding", semantics: "parent meshを介したreverse traceability" });
    }
  }

  const explicitlySelectedRoad = selection?.type === "road"
    ? data.plateauRoads?.features.find((feature) => String(feature.properties?.road_id ?? feature.id ?? "") === selection.id)
    : null;
  const road = explicitlySelectedRoad ? { feature: explicitlySelectedRoad, distanceM: 0 } : nearestRoad(data.plateauRoads, point);
  if (road) {
    const properties = road.feature.properties ?? {};
    const id = String(properties.road_id ?? road.feature.id ?? "nearest-road");
    const roadId = nodeId("road", id);
    nodes.push({
      id: roadId, kind: "road", label: String(properties.road_name ?? "名称なしPLATEAU道路"),
      source: String(properties.source ?? "Project PLATEAU 舞鶴市 道路LOD1"), year,
      attributes: {
        gml_id: id,
        road_class: String(properties.road_class ?? "属性なし"),
        approximate_geometry_distance_m: Number(road.distanceM.toFixed(1)),
        graph_semantics: "experimental PLATEAU LOD1 road-surface adjacency; pedestrian/walking networkではない",
      },
    });
    if (selectedObjectId === roadId) {
      if (meshCode) relations.push({ from: nodeId("mesh", meshCode), to: roadId, kind: "intersects", label: "選択メッシュ内の道路面", semantics: "PLATEAU LOD1道路geometryによる包含" });
      if (findingId) relations.push({ from: roadId, to: findingId, kind: "linked", label: "この道路に関係するFinding", semantics: "道路位置を含む500m meshを介したreverse traceability" });
    } else {
      relations.push({ from: selectedObjectId, to: roadId, kind: "nearest", label: `最寄り道路形状 約${Math.round(road.distanceM)}m`, semantics: "クリック位置からLOD1道路形状頂点への概算直線距離。歩行距離ではない" });
    }
  }

  if (meshCode) {
    const terrainId = nodeId("terrain", meshCode);
    nodes.push({
      id: terrainId, kind: "terrain",
      label: isDeepDive ? "PLATEAU DEM実TIN地形" : "PLATEAU-Terrain広域地形",
      source: isDeepDive ? String(data.plateauMetadata?.streaming?.local_dem_kind ?? "PLATEAU dem:TINRelief") : String(data.plateauMetadata?.streaming?.terrain_kind ?? "PLATEAU-Terrain"),
      year, attributes: { exact_local_dem: isDeepDive, exaggeration: false, derived_slope: false },
    });
    relations.push({ from: nodeId("mesh", meshCode), to: terrainId, kind: "intersects", label: "地形上で建物・道路関係を確認", semantics: "実DEM面。分析surfaceとは分離し、高低差から歩行負荷を推定しない" });
  }

  for (const [layerType, kind] of [["landuse_context", "landuse"], ["planning_context", "planning"], ["hazard_context", "hazard"]] as const) {
    for (const feature of contextFeatures(workspace, workspacePhase, point, layerType)) {
      const properties = feature.properties ?? {};
      const id = String(properties.plateau_gml_id ?? feature.id ?? `${kind}-context`);
      const contextId = nodeId(kind, id);
      nodes.push({
        id: contextId, kind, label: String(properties.label ?? properties.hazard_type ?? `${kind} context`),
        source: String(properties.source_member ?? `Project PLATEAU ${kind}`), year,
        attributes: {
          gml_id: id,
          interpretation: String(properties.interpretation ?? "確認文脈。自動判定ではない"),
        },
      });
      relations.push({ from: selectedObjectId, to: contextId, kind: kind === "planning" ? "within" : "intersects", label: `${kind} object context`, semantics: "PLATEAU geometryによる同一地点確認。施策可否の自動判定ではない" });
    }
  }

  const availableByResolution: Record<SpatialResolution, ResolutionAvailability> = {
    city: { resolution: "city", available: true, count: 1, reason: "市域と全市統計" },
    district: { resolution: "district", available: true, count: null, reason: "統計地区文脈（500mへ接続）" },
    mesh: { resolution: "mesh", available: Boolean(meshCode), count: meshCode ? 1 : 0, reason: meshCode ? "同じFindingの500mメッシュ" : "メッシュを選択してください" },
    building_group: { resolution: "building_group", available: buildingCount > 0, count: buildingCount, reason: buildingCount > 0 ? "公式PLATEAU建物を確認済み" : "選択メッシュに公式建物coverageなし" },
    building: { resolution: "building", available: selection?.type === "building", count: selection?.type === "building" ? 1 : 0, reason: selection?.type === "building" ? "選択中のPLATEAU building object" : "3Dで建物を選択してください" },
    road: { resolution: "road", available: Boolean(road), count: road ? 1 : 0, reason: road ? "実LOD1道路形状へ接続" : "位置を持つ地物を選択してください" },
    site: { resolution: "site", available: workspacePhase !== "baseline", count: workspacePhase === "baseline" ? 0 : 1, reason: workspacePhase === "baseline" ? "Scenarioを選択してください" : "施策候補とPLATEAU文脈" },
  };

  return {
    nodes: [...new Map(nodes.map((node) => [node.id, node])).values()],
    relations,
    selectedObjectId,
    findingId,
    resolution: RESOLUTIONS.map((resolution) => availableByResolution[resolution]),
    plateauRequired: selection?.type === "building" || selection?.type === "road" || selection?.type === "terrain" || selection?.type === "planning" || selection?.type === "hazard",
    plateauOffLoss: [
      "500m統計から実在する建物群への詳細化",
      "建物とLOD1道路形状の位置関係",
      "DEM上の建物・道路・災害文脈",
      "建物／道路からFindingへの逆引き",
    ],
  };
}
