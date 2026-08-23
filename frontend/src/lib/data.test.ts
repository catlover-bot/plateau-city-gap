import { describe, expect, it, vi } from "vitest";
import type { GeoJsonFeatureCollection, MeshMetrics } from "../types";
import { loadAppData, loadValidationCityData, normalizeTop10, sortRanking } from "./data";

const EMPTY_COLLECTION: GeoJsonFeatureCollection = { type: "FeatureCollection", features: [] };

function mockFetch(files: Record<string, unknown>): typeof fetch {
  return vi.fn(async (input: string | URL | Request) => {
    const url = String(input);
    const filename = url.split("/").at(-1) ?? "";
    if (!(filename in files)) {
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    }
    return { ok: true, status: 200, json: async () => files[filename] } as Response;
  }) as unknown as typeof fetch;
}

describe("ranking normalization", () => {
  it("reads the generated envelope and sorts by rank", () => {
    const result = normalizeTop10({
      schema_version: "1",
      items: [
        { mesh_code: "b", rank: 2, exploratory_score_c: 0.4 },
        { mesh_code: "a", rank: 1, exploratory_score_c: 0.5 }
      ]
    });
    expect(result.map((item) => item.mesh_code)).toEqual(["a", "b"]);
  });

  it("falls back to descending score when ranks are missing", () => {
    const items: MeshMetrics[] = [
      { mesh_code: "low", exploratory_score_c: 0.1 },
      { mesh_code: "high", exploratory_score_c: 0.8 },
      { mesh_code: "missing", exploratory_score_c: null }
    ];
    expect(sortRanking(items).map((item) => item.mesh_code)).toEqual(["high", "low", "missing"]);
  });
});
describe("data loading", () => {
  it("loads required and optional static web assets", async () => {
    const meshCollection: GeoJsonFeatureCollection = {
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [] },
        properties: { mesh_code: "533512753" }
      }]
    };
    const fetcher = mockFetch({
      "manifest.json": { analysis_version: "test" },
      "mesh_metrics.geojson": meshCollection,
      "top10.json": { items: [{ mesh_code: "533512753", rank: 1 }] },
      "summary.json": { record_counts: { primary_rank_eligible_meshes: 218 } },
      "final_demo.json": { comparison_mesh_count: 286 },
      "robustness.json": { scenario_count: 9, candidates: [], top_candidates: [] },
      "intervention_scenarios.json": { plans: {} },
      "evidence.json": { philosophy: "test" },
      "stations.geojson": EMPTY_COLLECTION,
      "bus_stops.geojson": EMPTY_COLLECTION,
      "medical_facilities.geojson": EMPTY_COLLECTION,
      "maizuru_boundary.geojson": EMPTY_COLLECTION,
      "plateau_buildings.geojson": EMPTY_COLLECTION,
      "plateau_roads.geojson": EMPTY_COLLECTION,
      "plateau_metadata.json": { status: "not_included" }
    });

    const data = await loadAppData(fetcher, "/plateau-city-gap/");
    expect(data.meshes.features).toHaveLength(1);
    expect(data.top10[0].mesh_code).toBe("533512753");
    expect(data.manifest.analysis_version).toBe("test");
    expect(data.warnings).toEqual([]);
    expect(fetcher).toHaveBeenCalledWith("/plateau-city-gap/data/manifest.json");
  });

  it("keeps the app usable when optional layers are absent", async () => {
    const fetcher = mockFetch({
      "manifest.json": {},
      "mesh_metrics.geojson": EMPTY_COLLECTION,
      "top10.json": { items: [] },
      "summary.json": {},
      "final_demo.json": {},
      "robustness.json": {},
      "intervention_scenarios.json": {},
      "evidence.json": {}
    });
    const data = await loadAppData(fetcher, "/");
    expect(data.stations).toBeNull();
    expect(data.plateauBuildings).toBeNull();
    expect(data.warnings.length).toBe(7);
  });

  it("fails clearly when a required asset has an invalid format", async () => {
    const fetcher = mockFetch({
      "manifest.json": {},
      "mesh_metrics.geojson": { type: "not-geojson" },
      "top10.json": { items: [] },
      "summary.json": {},
      "final_demo.json": {},
      "robustness.json": {},
      "intervention_scenarios.json": {},
      "evidence.json": {}
    });
    await expect(loadAppData(fetcher, "/")).rejects.toThrow("FeatureCollection");
  });

  it("loads Fujisawa in validation mode without Maizuru-only demo assets", async () => {
    const fetcher = mockFetch({
      "manifest.json": { mode: "cross_city_validation" },
      "mesh_metrics.geojson": EMPTY_COLLECTION,
      "top10.json": { items: [{ mesh_code: "533913073", rank: 1 }] },
      "summary.json": {
        city: {
          id: "fujisawa",
          code: "14205",
          name: "藤沢市",
          prefecture: "神奈川県",
          mode: "cross_city_validation",
          map_view: { longitude: 139.475, latitude: 35.365, height: 23000 }
        }
      },
      "stations.geojson": EMPTY_COLLECTION,
      "bus_stops.geojson": EMPTY_COLLECTION,
      "medical_facilities.geojson": EMPTY_COLLECTION,
      "boundary.geojson": EMPTY_COLLECTION
    });
    const data = await loadValidationCityData(fetcher, "/plateau-city-gap/");
    expect(data.city.name).toBe("藤沢市");
    expect(data.city.mode).toBe("cross_city_validation");
    expect(data.top10[0].mesh_code).toBe("533913073");
    expect(data.finalDemo).toBeNull();
    expect(fetcher).toHaveBeenCalledWith("/plateau-city-gap/data/cities/fujisawa/manifest.json");
  });
});
