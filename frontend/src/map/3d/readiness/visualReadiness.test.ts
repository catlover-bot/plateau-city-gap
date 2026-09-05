import { describe, expect, it } from "vitest";
import { SCENE_PRESETS } from "../../core/scenePresets";
import { evaluateVisualReadiness, INITIAL_VISUAL_READINESS, type VisualReadinessSnapshot } from "./visualReadiness";

const requirements = { ...SCENE_PRESETS.plateau_detail.readiness, requiresVerifiedPack: true };
const complete: VisualReadinessSnapshot = {
  ...INITIAL_VISUAL_READINESS,
  appReady: true,
  analysisReady: true,
  cameraSettled: true,
  cesiumSceneReady: true,
  canvasSizeReady: true,
  buildingTilesReady: true,
  buildingContentReady: true,
  buildingFeatureCount: 856,
  renderedBuildingFeatureCount: 856,
  targetBuildingCount: 296,
  loadedTargetBuildingCount: 296,
  visibleTargetBuildingCount: 205,
  targetCoverageRatio: 1,
  packArtifactsReady: true,
  terrainProviderReady: true,
  terrainTileCount: 1,
  localDemReady: true,
  roadsReady: true,
  overlayReady: true,
  fontReady: true,
  stableFrameCount: 3,
};

describe("Guided verified-local visual readiness", () => {
  it.each([
    ["unverified files", { packArtifactsReady: false }, "pack_artifacts"],
    ["incomplete content", { buildingContentReady: false }, "building_content_complete"],
    ["loaded but not rendered models", { renderedBuildingFeatureCount: 0 }, "rendered_buildings"],
  ] as const)("does not turn 296 catalog entries into visual completion with %s", (_label, missing, reason) => {
    const result = evaluateVisualReadiness({ ...complete, ...missing }, requirements);
    expect(result.interactionReady).toBe(true);
    expect(result.visualComplete).toBe(false);
    expect(result.captureStrictReady).toBe(false);
    expect(result.unmet).toContain(reason);
  });

  it("accepts verified content rendered in a stable local DEM scene without broad terrain or a basemap", () => {
    const result = evaluateVisualReadiness(complete, requirements);
    expect(complete.basemapReady).toBe(false);
    expect(result.visualComplete).toBe(true);
    expect(result.captureStrictReady).toBe(true);
    // Camera visibility is separate from complete coverage of the bounded pack.
    expect(complete.visibleTargetBuildingCount).toBeLessThan(complete.loadedTargetBuildingCount);
  });

  it("keeps the real local DEM and post-camera stable-frame requirements", () => {
    expect(evaluateVisualReadiness({ ...complete, localDemReady: false }, requirements).unmet).toContain("local_dem");
    const moving = evaluateVisualReadiness({ ...complete, stableFrameCount: 0 }, requirements);
    expect(moving.visualComplete).toBe(true);
    expect(moving.captureStrictReady).toBe(false);
    expect(moving.unmet).toContain("stable_frames");
  });
});
