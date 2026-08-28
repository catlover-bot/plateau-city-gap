import type {
  AnalysisLens,
  LayerPresetId,
  MapMode,
  ScenePresetId,
  SpatialIntent,
} from "../../state/spatial/types";
import type { SceneReadinessRequirements } from "../3d/readiness/visualReadiness";

export type SceneCameraIntent = "city" | "mesh" | "building" | "route" | "hazard" | "scenario";

export interface ScenePreset {
  id: ScenePresetId;
  label: string;
  description: string;
  intent: SpatialIntent;
  recommendedMapMode: MapMode;
  camera: SceneCameraIntent;
  primaryLayer: string;
  requiredLayers: string[];
  legendLayer: string;
  inspectorSections: Array<"summary" | "why" | "plateau" | "accessibility" | "planning-hazard" | "evidence">;
  legacyLayerPreset: LayerPresetId;
  analysisLens: AnalysisLens;
  readiness: SceneReadinessRequirements;
}

const inspector = ["summary", "why", "plateau", "accessibility", "planning-hazard", "evidence"] as const;
const readiness2d: SceneReadinessRequirements = { requiresTerrain: false, requiresLocalDem: false, requiresBuildings: false, requiresRoads: false, requiresAnalysis: true, minimumBuildingFeatures: 0, minimumTerrainTiles: 0, stableFrames: 3 };
const readinessLocal3d: SceneReadinessRequirements = { requiresTerrain: true, requiresLocalDem: true, requiresBuildings: true, requiresRoads: true, requiresAnalysis: true, minimumBuildingFeatures: 1, minimumTerrainTiles: 1, stableFrames: 3 };
const readinessContext3d: SceneReadinessRequirements = { ...readinessLocal3d, requiresLocalDem: false };

export const SCENE_PRESETS: Record<ScenePresetId, ScenePreset> = {
  city_overview: {
    id: "city_overview", label: "舞鶴全体", description: "海岸・駅・主要道路と市域を読む",
    intent: "discover", recommendedMapMode: "map2d", camera: "city",
    primaryLayer: "analysis-city-gap", requiredLayers: ["reference-gsi-pale", "analysis-city-gap", "infra-stations"],
    legendLayer: "analysis-city-gap", inspectorSections: [...inspector], legacyLayerPreset: "discovery", analysisLens: "none", readiness: readiness2d,
  },
  gap_discovery: {
    id: "gap_discovery", label: "CITY GAP候補", description: "500mメッシュの追加調査候補を絞る",
    intent: "discover", recommendedMapMode: "map2d", camera: "mesh",
    primaryLayer: "analysis-city-gap", requiredLayers: ["reference-gsi-pale", "analysis-city-gap", "infra-stations", "infra-medical"],
    legendLayer: "analysis-city-gap", inspectorSections: [...inspector], legacyLayerPreset: "discovery", analysisLens: "none", readiness: readiness2d,
  },
  plateau_detail: {
    id: "plateau_detail", label: "PLATEAU詳細", description: "実建物・道路・DEMを同一3D sceneで確認",
    intent: "inspect", recommendedMapMode: "plateau3d", camera: "building",
    primaryLayer: "plateau-buildings", requiredLayers: ["plateau-buildings", "plateau-roads", "plateau-terrain"],
    legendLayer: "plateau-buildings", inspectorSections: [...inspector], legacyLayerPreset: "plateau-detail", analysisLens: "urban-xray", readiness: readinessLocal3d,
  },
  network_access: {
    id: "network_access", label: "道路・到達性", description: "建物から施設までの道路文脈を読む",
    intent: "inspect", recommendedMapMode: "plateau3d", camera: "route",
    primaryLayer: "analysis-transport", requiredLayers: ["analysis-transport", "plateau-buildings", "plateau-roads", "plateau-terrain", "scenario-routes"],
    legendLayer: "analysis-transport", inspectorSections: [...inspector], legacyLayerPreset: "transport", analysisLens: "service-pulse", readiness: readinessContext3d,
  },
  scenario_compare: {
    id: "scenario_compare", label: "施策案比較", description: "候補地・影響建物・経路を比較",
    intent: "scenario", recommendedMapMode: "plateau3d", camera: "scenario",
    primaryLayer: "scenario-footprint", requiredLayers: ["reference-gsi-pale", "scenario-footprint", "scenario-sites", "scenario-routes"],
    legendLayer: "scenario-footprint", inspectorSections: [...inspector], legacyLayerPreset: "scenario-compare", analysisLens: "changed-only", readiness: readinessContext3d,
  },
  hazard_stress: {
    id: "hazard_stress", label: "災害Stress", description: "平常時と仮定Stressの到達性差分を比較",
    intent: "resilience", recommendedMapMode: "plateau3d", camera: "hazard",
    primaryLayer: "hazard-composite", requiredLayers: ["plateau-buildings", "plateau-roads", "plateau-terrain", "hazard-composite", "scenario-sites"],
    legendLayer: "hazard-composite", inspectorSections: [...inspector], legacyLayerPreset: "hazard", analysisLens: "changed-only", readiness: readinessContext3d,
  },
  temporal_change: {
    id: "temporal_change", label: "年次差分", description: "PLATEAU 2023 / 2025の追加・削除・変更を読む",
    intent: "validate", recommendedMapMode: "map2d", camera: "building",
    primaryLayer: "validation-temporal", requiredLayers: ["reference-gsi-pale", "validation-temporal"],
    legendLayer: "validation-temporal", inspectorSections: [...inspector], legacyLayerPreset: "validation-compare", analysisLens: "temporal-ghost", readiness: readiness2d,
  },
  validation_disagreement: {
    id: "validation_disagreement", label: "経路検証", description: "PLATEAU実験網と参照網を同じ地図で比較",
    intent: "validate", recommendedMapMode: "map2d", camera: "route",
    primaryLayer: "validation-disagreement", requiredLayers: ["reference-gsi-pale", "validation-disagreement", "validation-primary-route", "validation-reference-route"],
    legendLayer: "validation-disagreement", inspectorSections: [...inspector], legacyLayerPreset: "validation-compare", analysisLens: "none", readiness: readiness2d,
  },
};

export const scenePresetById = (id: ScenePresetId): ScenePreset => SCENE_PRESETS[id];

export const sceneLayerIds = (id: ScenePresetId): string[] => [...SCENE_PRESETS[id].requiredLayers];

export function sceneForLayerPreset(id: LayerPresetId): ScenePresetId {
  const match = Object.values(SCENE_PRESETS).find((scene) => scene.legacyLayerPreset === id);
  return match?.id ?? "gap_discovery";
}
