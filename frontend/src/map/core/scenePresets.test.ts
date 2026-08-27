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
    }
  });

  it("makes PLATEAU indispensable in detailed 3D scenes", () => {
    for (const id of ["plateau_detail", "network_access", "hazard_stress"] as const) {
      expect(sceneLayerIds(id)).toEqual(expect.arrayContaining(["plateau-buildings", "plateau-roads", "plateau-terrain"]));
      expect(SCENE_PRESETS[id].recommendedMapMode).toBe("plateau3d");
    }
  });
});
