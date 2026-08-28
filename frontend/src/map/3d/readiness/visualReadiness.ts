export interface SceneReadinessRequirements {
  requiresTerrain: boolean;
  requiresLocalDem: boolean;
  requiresBuildings: boolean;
  requiresRoads: boolean;
  requiresAnalysis: boolean;
  minimumBuildingFeatures: number;
  minimumTerrainTiles: number;
  stableFrames: number;
}

export interface VisualReadinessSnapshot {
  appReady: boolean;
  basemapReady: boolean;
  analysisReady: boolean;
  cameraSettled: boolean;
  cesiumSceneReady: boolean;
  canvasSizeReady: boolean;
  buildingTilesReady: boolean;
  buildingFeatureCount: number;
  terrainProviderReady: boolean;
  terrainTileCount: number;
  localDemReady: boolean;
  roadsReady: boolean;
  overlayReady: boolean;
  fontReady: boolean;
  outstandingCriticalRequests: number;
  stableFrameCount: number;
  terrainSource: string;
  buildingSource: string;
}

export interface VisualReadinessResult {
  visualReady: boolean;
  unmet: string[];
}

export const INITIAL_VISUAL_READINESS: VisualReadinessSnapshot = {
  appReady: false,
  basemapReady: false,
  analysisReady: false,
  cameraSettled: false,
  cesiumSceneReady: false,
  canvasSizeReady: false,
  buildingTilesReady: false,
  buildingFeatureCount: 0,
  terrainProviderReady: false,
  terrainTileCount: 0,
  localDemReady: false,
  roadsReady: false,
  overlayReady: false,
  fontReady: false,
  outstandingCriticalRequests: 0,
  stableFrameCount: 0,
  terrainSource: "none",
  buildingSource: "none",
};

export function evaluateVisualReadiness(
  snapshot: VisualReadinessSnapshot,
  requirements: SceneReadinessRequirements,
): VisualReadinessResult {
  const unmet: string[] = [];
  if (!snapshot.appReady) unmet.push("app");
  if (!snapshot.basemapReady) unmet.push("basemap");
  if (!snapshot.analysisReady && requirements.requiresAnalysis) unmet.push("analysis");
  if (!snapshot.cameraSettled) unmet.push("camera");
  if (!snapshot.cesiumSceneReady) unmet.push("cesium_scene");
  if (!snapshot.canvasSizeReady) unmet.push("canvas_size");
  if (!snapshot.fontReady) unmet.push("font");
  if (!snapshot.overlayReady) unmet.push("overlay");
  if (snapshot.outstandingCriticalRequests > 0) unmet.push("critical_requests");
  if (requirements.requiresRoads && !snapshot.roadsReady) unmet.push("roads");
  if (requirements.requiresBuildings && (
    !snapshot.buildingTilesReady || snapshot.buildingFeatureCount < requirements.minimumBuildingFeatures
  )) unmet.push("buildings");
  if (requirements.requiresTerrain && (
    !snapshot.terrainProviderReady || snapshot.terrainTileCount < requirements.minimumTerrainTiles
  )) unmet.push("terrain");
  if (requirements.requiresLocalDem && !snapshot.localDemReady) unmet.push("local_dem");
  if (snapshot.stableFrameCount < requirements.stableFrames) unmet.push("stable_frames");
  return { visualReady: unmet.length === 0, unmet };
}
