import { describe, expect, it } from "vitest";
import type { GeoJsonFeatureCollection } from "../../types";
import { exactOrAreaTarget, oneAreaCollection } from "./guidedData";
import type { GuidedAreaContext } from "./guidedTypes";

const area: GeoJsonFeatureCollection = {
  type: "FeatureCollection",
  features: [{
    type: "Feature",
    properties: { mesh_code: "533513314", population: 471 },
    geometry: { type: "Polygon", coordinates: [[[135.39, 35.44], [135.4, 35.44], [135.4, 35.45], [135.39, 35.45], [135.39, 35.44]]] },
  }],
};

function context(meshCode: string): GuidedAreaContext {
  return {
    schema_version: "citygap.guided-area-context@1",
    area_id: `maizuru-${meshCode}`,
    mesh_code: meshCode,
    area_geometry_sha256: "fixture",
    source: { dataset: "fixture", version: "fixture", sha256: "fixture", limitations: [] },
    capabilities: {
      plateau_buildings: { status: "available", reason: "fixture" },
      plateau_roads: { status: "available", reason: "fixture" },
      planning: { status: "available", reason: "fixture" },
      terrain: { status: "unavailable", reason: "fixture" },
      urban_section: { status: "unavailable", reason: "fixture" },
      verification_targets: { status: "partial", reason: "fixture" },
    },
    layers: {
      buildings: { type: "FeatureCollection", features: [] },
      planning: { type: "FeatureCollection", features: [] },
      roads: {
        type: "FeatureCollection",
        features: [{
          type: "Feature",
          id: "tran_05dbefba-6a77-40ea-88ac-a568a63a2f05:0",
          properties: { object_id: "tran_05dbefba-6a77-40ea-88ac-a568a63a2f05", surface_index: 0 },
          geometry: area.features[0].geometry,
        }],
      },
    },
    section: { status: "unavailable", reason: "fixture" },
  };
}

describe("Guided selected-Area data", () => {
  it("keeps a selected mesh as the one canonical Area", () => {
    expect(oneAreaCollection(area, "533513314").features).toHaveLength(1);
    expect(oneAreaCollection(area, "533512753").features).toHaveLength(0);
  });

  it("uses the verified road only for its owning Area", () => {
    expect(exactOrAreaTarget(context("533513314"), area).resolution).toBe("exact");
    expect(exactOrAreaTarget(context("533512753"), area)).toEqual({ geometry: area, resolution: "area_fallback" });
  });
});
