import type { AppData, InterventionPlan, MeshMetrics } from "../../types";
import type { SpatialSelection } from "../../state/spatial/types";

export const GUIDED_MESH_CODE = "533513314";
export const GUIDED_AREA_NAME = "常団地前周辺";

export interface GuidedSource {
  id: "population" | "transport" | "medical" | "plateau" | "method";
  label: string;
  detail: string;
}

export interface GuidedCase {
  mesh: MeshMetrics;
  meshCount: number;
  areaName: string;
  overallRank: number;
  population: number;
  elderlyPopulation: number;
  transportDistanceM: number;
  medicalDistanceM: number;
  plateauBuildingCount: number;
  plateauRoadCount: number;
  scenarioPlan: InterventionPlan;
  scenarioBeforeM: number;
  scenarioAfterM: number;
  scenarioReductionM: number;
  sources: GuidedSource[];
}

function requiredNumber(value: unknown, label: string): number {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error(`案内用実データ「${label}」を確認できません`);
  return number;
}

export function buildGuidedCase(data: AppData): GuidedCase {
  const feature = data.meshes.features.find(
    (candidate) => String(candidate.properties?.mesh_code ?? "") === GUIDED_MESH_CODE,
  );
  if (!feature?.properties) throw new Error("案内用500mメッシュを確認できません");

  const mesh = { ...feature.properties, mesh_code: GUIDED_MESH_CODE } as MeshMetrics;
  const scenarioPlan = data.interventions?.plans.overall["1"];
  const scenario = scenarioPlan?.mesh_results[GUIDED_MESH_CODE];
  if (!scenarioPlan || !scenario) throw new Error("案内用の条件比較を確認できません");

  return {
    mesh,
    meshCount: data.meshes.features.length,
    areaName: GUIDED_AREA_NAME,
    overallRank: requiredNumber(mesh.rank, "全市順位"),
    population: requiredNumber(mesh.population, "人口"),
    elderlyPopulation: requiredNumber(mesh.elderly_population, "65歳以上人口"),
    transportDistanceM: requiredNumber(mesh.nearest_public_transport_distance_m, "公共交通距離"),
    medicalDistanceM: requiredNumber(mesh.nearest_medical_distance_m, "医療距離"),
    plateauBuildingCount: requiredNumber(
      data.finalDemo?.deep_dive.plateau_building_count
        ?? data.plateauMetadata?.reference_layer?.deep_dive_buildings,
      "PLATEAU建物数",
    ),
    plateauRoadCount: requiredNumber(
      data.finalDemo?.deep_dive.plateau_road_surfaces_intersecting_mesh,
      "PLATEAU道路数",
    ),
    scenarioPlan,
    scenarioBeforeM: requiredNumber(scenario.before_distance_m, "現在の交通距離"),
    scenarioAfterM: requiredNumber(scenario.after_distance_m, "仮想地点条件の交通距離"),
    scenarioReductionM: requiredNumber(scenario.distance_reduction_m, "距離の変化"),
    sources: [
      { id: "population", label: "国勢調査", detail: "2020年・500mメッシュ人口" },
      { id: "transport", label: "駅・バス停", detail: "PLATEAU駅 2025／国土数値情報 P11 2022" },
      { id: "medical", label: "医療施設データ", detail: "国土数値情報 P04 2020" },
      { id: "plateau", label: "PLATEAU 舞鶴市", detail: "2025年度・建物／道路／地形" },
      { id: "method", label: "CITY GAP計算方法", detail: "人口・交通・医療を500m単位で比較" },
    ],
  };
}

export function guidedMeshSelection(data: AppData, guided: GuidedCase): SpatialSelection {
  return {
    type: "mesh",
    id: GUIDED_MESH_CODE,
    city: data.city.id,
    urbanState: "2025",
    label: guided.areaName,
    longitude: requiredNumber(guided.mesh.centroid_lon, "経度"),
    latitude: requiredNumber(guided.mesh.centroid_lat, "緯度"),
    properties: {
      ...guided.mesh,
      area_label: guided.areaName,
      source_area_label: guided.mesh.area_label,
      plateau_coverage: "verified_deep_dive",
      official_buildings_in_mesh: guided.plateauBuildingCount,
    },
  };
}
