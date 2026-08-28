import { describe, expect, it } from "vitest";
import { SCENE_PRESETS, sceneLayerIds } from "./scenePresets";

describe("Spatial OS scene presets", () => {
  it("governs all eight required scenes", () => {
    expect(Object.keys(SCENE_PRESETS)).toEqual([
      "city_overview", "gap_discovery", "plateau_detail", "network_access",
      "scenario_compare", "hazard_stress", "temporal_change", "validation_disagreement",
    ]);
    for (const scene of Object.values(SCENE_PRESETS)) {
      expect(scene.requiredLayers).toContain(scene.primaryLayer);
      expect(scene.inspectorSections).toEqual(expect.arrayContaining(["summary", "why", "plateau", "evidence"]));
      expect(scene.camera).toBeTruthy();
      expect(scene.readiness.stableFrames).toBe(3);
    }
  });

  it("makes PLATEAU indispensable in detailed 3D scenes", () => {
    for (const id of ["plateau_detail", "network_access", "hazard_stress"] as const) {
      expect(sceneLayerIds(id)).toEqual(expect.arrayContaining(["plateau-buildings", "plateau-roads", "plateau-terrain"]));
      expect(SCENE_PRESETS[id].recommendedMapMode).toBe("plateau3d");
      expect(SCENE_PRESETS[id].readiness).toMatchObject({ requiresTerrain: true, requiresBuildings: true });
    }
  });

  it("requires the local DEM only where its verified Deep Dive coverage exists", () => {
    expect(SCENE_PRESETS.plateau_detail.readiness.requiresLocalDem).toBe(true);
    expect(SCENE_PRESETS.network_access.readiness.requiresLocalDem).toBe(false);
    expect(SCENE_PRESETS.hazard_stress.readiness.requiresLocalDem).toBe(false);
  });

  it("binds the sharp analysis lenses to operational scenes", () => {
    expect(SCENE_PRESETS.plateau_detail.analysisLens).toBe("urban-xray");
    expect(SCENE_PRESETS.network_access.analysisLens).toBe("service-pulse");
    expect(SCENE_PRESETS.scenario_compare.analysisLens).toBe("changed-only");
    expect(SCENE_PRESETS.temporal_change.analysisLens).toBe("temporal-ghost");
  });
});
