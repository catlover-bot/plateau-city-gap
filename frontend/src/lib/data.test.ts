import { describe, expect, it, vi } from "vitest";
import type { GeoJsonFeatureCollection, MeshMetrics } from "../types";
import {
  loadAppData,
  loadGuidedAppData,
  loadMunicipalWorkspaceData,
  loadUrbanFuturesData,
  loadValidationWorkspaceData,
  loadValidationCityData,
  normalizeTop10,
  sortRanking
} from "./data";

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
  it("loads the separate Validation Workspace evidence contract", async () => {
    const collection = { type: "FeatureCollection", features: [] };
    const fetcher = mockFetch({
      "network_cross_validation.json": { cities: [{ city_id: "maizuru" }] },
      "sensitivity_validation.json": { cities: { maizuru: {}, fujisawa: {} } },
      "real_temporal_validation.json": { themes: [] },
      "network_disagreement_routes.geojson": collection,
      "temporal_change_samples.geojson": collection,
      "criticality_map_audit.geojson": collection
    });
    const result = await loadValidationWorkspaceData(fetcher, "/plateau-city-gap/");
    expect(result.network.cities[0].city_id).toBe("maizuru");
    expect(result.disagreementRoutes.type).toBe("FeatureCollection");
    expect(fetcher).toHaveBeenCalledWith(
      "/plateau-city-gap/data/validation/network_cross_validation.json"
    );
  });

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

  it("keeps scenario and legacy PLATEAU bundles out of the Guided first load", async () => {
    const fetcher = mockFetch({
      "manifest.json": { analysis_version: "test" },
      "mesh_metrics.geojson": EMPTY_COLLECTION,
      "top10.json": { items: [] },
      "summary.json": {},
      "stations.geojson": EMPTY_COLLECTION,
      "bus_stops.geojson": EMPTY_COLLECTION,
      "medical_facilities.geojson": EMPTY_COLLECTION,
      "maizuru_boundary.geojson": EMPTY_COLLECTION,
    });
    const data = await loadGuidedAppData(fetcher, "/plateau-city-gap/");
    const requests = vi.mocked(fetcher).mock.calls.map(([input]) => String(input));
    expect(data.meshes).toEqual(EMPTY_COLLECTION);
    expect(data.interventions).toBeNull();
    expect(data.plateauBuildings).toBeNull();
    expect(requests).not.toEqual(expect.arrayContaining([
      expect.stringContaining("intervention_scenarios.json"),
      expect.stringContaining("robustness.json"),
      expect.stringContaining("plateau_buildings.geojson"),
      expect.stringContaining("plateau_roads.geojson"),
    ]));
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

  it("loads the selected scenario story, Workspace map and city registry", async () => {
    const fetcher = mockFetch({
      "municipal_workspace_story.json": {
        schema_version: "test",
        scenario_story: [
          { story_id: "scenario_a" },
          { story_id: "scenario_b" },
          { story_id: "scenario_c" }
        ]
      },
      "network_scenario_map.geojson": {
        type: "FeatureCollection",
        features: [],
        layer_counts: {},
        story_counts: {},
        schema_version: "test",
        generated_at: "2026-01-01T00:00:00Z",
        source: "test",
        privacy: "test"
      },
      "network_scenario_building_points.json": {
        schema_version: "test",
        generated_at: "2026-01-01T00:00:00Z",
        privacy: "test",
        band_codes: { "0": "under_250" },
        stories: { scenario_a: [], scenario_b: [], scenario_c: [] }
      },
      "platform_registry.json": { capabilities: [], cities: [] }
    });

    const result = await loadMunicipalWorkspaceData(fetcher, "/");
    expect(result.story.scenario_story[0].story_id).toBe("scenario_a");
    expect(result.map.type).toBe("FeatureCollection");
    expect(result.buildingPoints.stories.scenario_a).toEqual([]);
    expect(result.registry.capabilities).toEqual([]);
  });

  it("loads only reviewed aggregated urban futures data", async () => {
    const fetcher = mockFetch({
      "urban_futures_resilience.json": {
        schema_version: "urban-futures-public-1.0.0",
        analysis_status: "reviewed_aggregated_real_data",
        building_level_demographics_included: false,
        story: { title: "test", steps: [], prediction_claimed: false },
        cities: {
          maizuru: { city_name: "舞鶴市", stress_tests: {}, resilience_map: EMPTY_COLLECTION },
          fujisawa: { city_name: "藤沢市", stress_tests: {}, resilience_map: EMPTY_COLLECTION }
        },
        limitations: []
      }
    });
    const result = await loadUrbanFuturesData(fetcher, "/plateau-city-gap/");
    expect(result.cities.maizuru.city_name).toBe("舞鶴市");
    expect(result.building_level_demographics_included).toBe(false);

    const unsafe = mockFetch({
      "urban_futures_resilience.json": {
        building_level_demographics_included: true,
        story: { prediction_claimed: false },
        cities: { maizuru: {}, fujisawa: {} }
      }
    });
    await expect(loadUrbanFuturesData(unsafe, "/")).rejects.toThrow("公開境界");

    const buildingLevelMap = mockFetch({
      "urban_futures_resilience.json": {
        building_level_demographics_included: false,
        story: { prediction_claimed: false },
        cities: {
          maizuru: {
            resilience_map: {
              type: "FeatureCollection",
              features: [{
                type: "Feature",
                geometry: null,
                properties: { layer_type: "affected_building", stress_mode: "flood", gml_id: "secret" }
              }]
            }
          },
          fujisawa: { resilience_map: EMPTY_COLLECTION }
        }
      }
    });
    await expect(loadUrbanFuturesData(buildingLevelMap, "/")).rejects.toThrow("公開境界");
  });
});
