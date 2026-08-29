export interface SceneReadinessRequirements {
  requiresTerrain: boolean;
  requiresLocalDem: boolean;
  requiresBuildings: boolean;
  requiresRoads: boolean;
  requiresAnalysis: boolean;
  requiresBasemap?: boolean;
  minimumBuildingFeatures: number;
  interactionMinimumBuildingFeatures?: number;
  expectedTargetBuildingCount?: number;
  strictTargetCoverageRatio?: number;
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
  targetBuildingCount: number;
  loadedTargetBuildingCount: number;
  visibleTargetBuildingCount: number;
  targetCoverageRatio: number;
  packArtifactsReady: boolean;
  packArtifactBytes: number;
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
  packId: string;
}

export interface VisualReadinessResult {
  interactionReady: boolean;
  visualComplete: boolean;
  captureStrictReady: boolean;
  /** Compatibility alias. Capture automation alone may use this flag. */
  visualReady: boolean;
  interactionUnmet: string[];
  visualCompleteUnmet: string[];
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
  targetBuildingCount: 0,
  loadedTargetBuildingCount: 0,
  visibleTargetBuildingCount: 0,
  targetCoverageRatio: 0,
  packArtifactsReady: false,
  packArtifactBytes: 0,
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
  packId: "none",
};

function commonUnmet(
  snapshot: VisualReadinessSnapshot,
  requirements: SceneReadinessRequirements,
): string[] {
  const unmet: string[] = [];
  if (!snapshot.appReady) unmet.push("app");
  if (requirements.requiresBasemap && !snapshot.basemapReady) unmet.push("basemap");
  if (!snapshot.analysisReady && requirements.requiresAnalysis) unmet.push("analysis");
  if (!snapshot.cesiumSceneReady) unmet.push("cesium_scene");
  if (!snapshot.canvasSizeReady) unmet.push("canvas_size");
  if (!snapshot.overlayReady) unmet.push("overlay");
  if (requirements.requiresRoads && !snapshot.roadsReady) unmet.push("roads");
  if (requirements.requiresTerrain && (
    !snapshot.terrainProviderReady || snapshot.terrainTileCount < requirements.minimumTerrainTiles
  )) unmet.push("terrain");
  if (requirements.requiresLocalDem && !snapshot.localDemReady) unmet.push("local_dem");
  return unmet;
}

export function evaluateVisualReadiness(
  snapshot: VisualReadinessSnapshot,
  requirements: SceneReadinessRequirements,
): VisualReadinessResult {
  const interactionUnmet = commonUnmet(snapshot, requirements);
  const interactionMinimum = requirements.interactionMinimumBuildingFeatures
    ?? Math.min(15, Math.max(1, requirements.minimumBuildingFeatures));
  if (requirements.requiresBuildings && (
    !snapshot.buildingTilesReady || snapshot.buildingFeatureCount < interactionMinimum
  )) interactionUnmet.push("buildings_interaction");

  const visualCompleteUnmet = [...interactionUnmet];
  if (!snapshot.cameraSettled) visualCompleteUnmet.push("camera");
  if (!snapshot.fontReady) visualCompleteUnmet.push("font");
  const expectedTarget = requirements.expectedTargetBuildingCount ?? requirements.minimumBuildingFeatures;
  if (requirements.requiresBuildings && expectedTarget > 0 && (
    snapshot.targetBuildingCount !== expectedTarget
    || snapshot.loadedTargetBuildingCount < expectedTarget
  )) visualCompleteUnmet.push("target_buildings_complete");

  const strictUnmet = [...visualCompleteUnmet];
  if (snapshot.outstandingCriticalRequests > 0) strictUnmet.push("critical_requests");
  if (snapshot.stableFrameCount < requirements.stableFrames) strictUnmet.push("stable_frames");
  const strictCoverage = requirements.strictTargetCoverageRatio ?? 0.95;
  if (requirements.requiresBuildings && expectedTarget > 0 && (
    snapshot.targetBuildingCount !== expectedTarget
    || snapshot.targetCoverageRatio < strictCoverage
  )) strictUnmet.push("target_coverage");

  const interactionReady = interactionUnmet.length === 0;
  const visualComplete = visualCompleteUnmet.length === 0;
  const captureStrictReady = strictUnmet.length === 0;
  return {
    interactionReady,
    visualComplete,
    captureStrictReady,
    visualReady: captureStrictReady,
    interactionUnmet,
    visualCompleteUnmet,
    unmet: strictUnmet,
  };
}
