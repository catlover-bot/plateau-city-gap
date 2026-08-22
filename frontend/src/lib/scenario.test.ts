import { describe, expect, it } from "vitest";

import type { MeshMetrics } from "../types";
import { calculateScenario, percentileRanks, projectToAnalysisCrs } from "./scenario";

const mesh = (overrides: Partial<MeshMetrics>): MeshMetrics => ({
  mesh_code: "mesh",
  centroid_lon: 135.3,
  centroid_lat: 35.48,
  elderly_population: 20,
  elderly_population_percentile: 0.5,
  transport_distance_percentile: 0.5,
  medical_distance_percentile: 0.5,
  nearest_public_transport_distance_m: 2_000,
  exploratory_score_c: 0.125,
  ...overrides,
});

describe("scenario calculation", () => {
  it("matches pandas-style average percentile ranks", () => {
    expect(percentileRanks([10, 20, 20, 40])).toEqual([0.25, 0.625, 0.625, 1]);
  });

  it("projects a Maizuru coordinate into finite EPSG:6674 metres", () => {
    const projected = projectToAnalysisCrs({ longitude: 135.315625, latitude: 35.48125 });
    expect(projected.every(Number.isFinite)).toBe(true);
    expect(Math.abs(projected[0])).toBeGreaterThan(1_000);
  });

  it("uses the virtual point only when it shortens straight-line transport distance", () => {
    const meshes = [
      mesh({ mesh_code: "near", centroid_lon: 135.3, nearest_public_transport_distance_m: 2_000 }),
      mesh({ mesh_code: "far", centroid_lon: 135.4, nearest_public_transport_distance_m: 100 }),
    ];
    const result = calculateScenario(meshes, { longitude: 135.3, latitude: 35.48 });
    expect(result.meshes.find((item) => item.meshCode === "near")?.afterDistanceM).toBeLessThan(1);
    expect(result.meshes.find((item) => item.meshCode === "far")?.afterDistanceM).toBe(100);
    expect(result.improvedMeshCount).toBe(1);
    expect(result.affectedElderlyPopulation).toBe(20);
    expect(result.averageTransportDistanceImprovementM).toBeGreaterThan(1_900);
    expect(result.meshes[0].areaLabel).toBe("Mesh near");
  });

  it("recalculates average-rank transport percentiles and scores deterministically", () => {
    const result = calculateScenario(
      [
        mesh({ mesh_code: "placed", centroid_lon: 135.3, nearest_public_transport_distance_m: 2_000 }),
        mesh({ mesh_code: "tie-a", centroid_lon: 135.4, nearest_public_transport_distance_m: 100 }),
        mesh({ mesh_code: "tie-b", centroid_lon: 135.5, nearest_public_transport_distance_m: 100 }),
      ],
      { longitude: 135.3, latitude: 35.48 },
    );

    const placed = result.meshes.find((item) => item.meshCode === "placed");
    const tied = result.meshes.find((item) => item.meshCode === "tie-a");
    expect(placed?.afterTransportPercentile).toBeCloseTo(1 / 3, 12);
    expect(placed?.afterScore).toBeCloseTo(1 / 12, 12);
    expect(tied?.afterTransportPercentile).toBeCloseTo(5 / 6, 12);
    expect(tied?.afterScore).toBeCloseTo(5 / 24, 12);
  });

  it("ignores rows missing baseline analysis fields", () => {
    const result = calculateScenario(
      [mesh({ mesh_code: "valid" }), mesh({ mesh_code: "missing", exploratory_score_c: null })],
      { longitude: 135.3, latitude: 35.48 },
    );
    expect(result.meshes.map((item) => item.meshCode)).toEqual(["valid"]);
    expect(result.comparisonMeshCount).toBe(1);
  });
});
