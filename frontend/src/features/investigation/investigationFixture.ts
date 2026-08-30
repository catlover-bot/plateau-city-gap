import type { AppData, MeshMetrics } from "../../types";

const detailed: MeshMetrics = {
  mesh_code: "533513314",
  area_label: "常団地前バス停周辺",
  rank: 23,
  population: 471,
  elderly_population: 200,
  nearest_public_transport_distance_m: 562.597,
  nearest_medical_distance_m: 1450.547,
  centroid_lon: 135.396875,
  centroid_lat: 35.4479167,
};

const screening: MeshMetrics = {
  mesh_code: "533503999",
  area_label: "二尾周辺",
  rank: 1,
  population: 63,
  elderly_population: 41,
  nearest_public_transport_distance_m: 1810,
  nearest_medical_distance_m: 5320,
  centroid_lon: 135.303,
  centroid_lat: 35.501,
};

const dataGap: MeshMetrics = {
  mesh_code: "533503998",
  area_label: "大浦地区",
  rank: 2,
  population: 81,
  elderly_population: 52,
  nearest_public_transport_distance_m: 1430,
  nearest_medical_distance_m: 4210,
  centroid_lon: 135.318,
  centroid_lat: 35.489,
};

export function investigationFixture(): AppData {
  const mesh = (properties: MeshMetrics) => ({
    type: "Feature" as const,
    geometry: null,
    properties,
  });
  return {
    city: {
      id: "maizuru",
      code: "26202",
      name: "舞鶴市",
      prefecture: "京都府",
      mode: "primary_demo",
      map_view: { longitude: 135.33, latitude: 35.47, height: 50000 },
    },
    manifest: {},
    summary: {
      record_counts: {
        population_meshes_intersecting_city: 495,
        primary_rank_eligible_meshes: 218,
      },
      audit: { score_comparison_denominator: 286 },
    },
    meshes: {
      type: "FeatureCollection",
      features: [mesh(detailed), mesh(screening), mesh(dataGap)],
    },
    top10: [screening, dataGap],
    stations: null,
    busStops: null,
    medicalFacilities: null,
    boundary: null,
    plateauBuildings: null,
    plateauRoads: null,
    plateauMetadata: null,
    finalDemo: {
      comparison_mesh_count: 286,
      rank_one: {
        mesh_code: screening.mesh_code,
        area_label: String(screening.area_label),
        plateau_building_count: 0,
      },
      plateau_covered_candidates: [],
      deep_dive: {
        mesh_code: detailed.mesh_code,
        overall_rank: 23,
        area_label: "常団地前周辺",
        plateau_building_count: 296,
        plateau_road_surfaces_intersecting_mesh: 135,
        plateau_buildings: { records: 296, displayed_on_click: [] },
      },
      placement_optimization: {
        objective: "fixture",
        screening_rule: "fixture",
        candidates: [],
      },
      plateau_context: {},
      offline: {},
    },
    robustness: null,
    interventions: null,
    evidence: null,
    warnings: [],
  };
}
