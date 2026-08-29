import { describe, expect, it } from "vitest";
import type { AppData } from "../../types";
import { buildGuidedCase, GUIDED_MESH_CODE, guidedMeshSelection } from "./guidedCase";

function guidedFixture(): AppData {
  const target = {
    type: "Feature",
    geometry: null,
    properties: {
      mesh_code: GUIDED_MESH_CODE,
      area_label: "常団地前バス停周辺",
      rank: 23,
      population: 471,
      elderly_population: 200,
      nearest_public_transport_distance_m: 562.597,
      nearest_medical_distance_m: 1450.547,
      centroid_lon: 135.396875,
      centroid_lat: 35.4479167,
    },
  };
  const features = Array.from({ length: 495 }, (_, index) => index === 0
    ? target
    : {
        type: "Feature",
        geometry: null,
        properties: { mesh_code: `fixture-${index}` },
      });

  return {
    city: { id: "maizuru" },
    meshes: { type: "FeatureCollection", features },
    finalDemo: {
      deep_dive: {
        plateau_building_count: 296,
        plateau_road_surfaces_intersecting_mesh: 135,
      },
    },
    interventions: {
      plans: {
        overall: {
          "1": {
            plan_id: "overall-1",
            sites: [{ longitude: 135.39665, latitude: 35.44772 }],
            mesh_results: {
              [GUIDED_MESH_CODE]: {
                before_distance_m: 562.597,
                after_distance_m: 29.867,
                distance_reduction_m: 532.73,
                after_score_c: 0.003608842,
              },
            },
          },
        },
      },
    },
  } as unknown as AppData;
}

describe("Guided public case", () => {
  it("keeps the five-step story tied to the canonical Maizuru data contract", () => {
    const data = guidedFixture();
    const guided = buildGuidedCase(data);

    expect(guided).toMatchObject({
      meshCount: 495,
      areaName: "常団地前周辺",
      overallRank: 23,
      population: 471,
      elderlyPopulation: 200,
      plateauBuildingCount: 296,
      plateauRoadCount: 135,
      scenarioBeforeM: 562.597,
      scenarioAfterM: 29.867,
      scenarioReductionM: 532.73,
    });
    expect(Math.round(guided.transportDistanceM)).toBe(563);
    expect((guided.medicalDistanceM / 1000).toFixed(2)).toBe("1.45");
    expect(guided.sources.map((source) => source.label)).toEqual([
      "国勢調査",
      "駅・バス停",
      "医療施設データ",
      "PLATEAU 舞鶴市",
      "CITY GAP計算方法",
    ]);

    expect(guidedMeshSelection(data, guided)).toMatchObject({
      type: "mesh",
      id: GUIDED_MESH_CODE,
      city: "maizuru",
      label: "常団地前周辺",
      longitude: 135.396875,
      latitude: 35.4479167,
      properties: {
        official_buildings_in_mesh: 296,
        plateau_coverage: "verified_deep_dive",
      },
    });
  });
});
