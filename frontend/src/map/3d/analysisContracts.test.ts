import { describe, expect, it } from "vitest";
import { buildUrbanXrayField, URBAN_XRAY_SEMANTICS } from "./xray/urbanXray";
import { extractServicePulseRoutes, formatNetworkDistance, SERVICE_PULSE_SEMANTICS } from "./pulse/servicePulse";
import { deriveCounterfactualChanges } from "./comparison/counterfactualTwin";
import { buildTemporalGhostRecords } from "./temporal/temporalGhost";
import { evaluateVisualReadiness, INITIAL_VISUAL_READINESS } from "./readiness/visualReadiness";
import { servicePulseMarkerPlan } from "./pulse/servicePulseRenderer";

const meshes = {
  type: "FeatureCollection" as const,
  features: [
    { type: "Feature" as const, geometry: null, properties: { mesh_code: "a", exploratory_score_c: 0.25 } },
    { type: "Feature" as const, geometry: null, properties: { mesh_code: "b", exploratory_score_c: 0.5 } },
    { type: "Feature" as const, geometry: null, properties: { mesh_code: "c", exploratory_score_c: null } },
  ],
};

describe("3D analysis contracts", () => {
  it("builds the Urban X-Ray only from existing calculated values", () => {
    const field = buildUrbanXrayField(meshes);
    expect([...field.keys()]).toEqual(["a", "b"]);
    expect(field.get("b")).toMatchObject({ rawValue: 0.5, normalizedIntensity: 1, source: "observed_analysis" });
    expect(URBAN_XRAY_SEMANTICS.boundary).toContain("実地形ではありません");
  });

  it("uses scenario values without inventing unchanged city geometry", () => {
    const changes = deriveCounterfactualChanges(meshes, { a: 0.2, b: 0.5 });
    expect(changes.get("a")).toMatchObject({ before: 0.25, after: 0.2, changed: true });
    expect(changes.get("b")?.changed).toBe(false);
  });

  it("keeps Service Pulse in network-distance semantics", () => {
    const workspace = {
      type: "FeatureCollection" as const,
      schema_version: "test",
      generated_at: "2026-01-01",
      source: "real-test-fixture",
      privacy: "none",
      layer_counts: {},
      story_counts: {},
      features: [{
        type: "Feature" as const,
        id: "route-1",
        geometry: { type: "LineString", coordinates: [[135.1, 35.1], [135.2, 35.2]] },
        properties: { layer_type: "representative_route", story_id: "scenario_b", route_kind: "before", network_distance_m: 1240, route_semantics: "road_surface_adjacency_not_validated_pedestrian" },
      }],
    };
    const routes = extractServicePulseRoutes(workspace, "scenario_b");
    expect(routes[0]).toMatchObject({ networkDistanceM: 1240, distanceBandsM: [500, 1000, 1240] });
    expect(formatNetworkDistance(1240)).toBe("1.2 km");
    expect(SERVICE_PULSE_SEMANTICS.boundary).not.toContain("分");
  });

  it("replaces animation with static network-distance bands for reduced motion", () => {
    const route = { id: "route", storyId: "scenario_a" as const, routeKind: "before" as const, networkDistanceM: 1240, distanceBandsM: [500, 1000, 1240], coordinates: [[135.1, 35.1], [135.2, 35.2]] as Array<[number, number]>, destinationName: "test", routeSemantics: "road_surface_adjacency_not_validated_pedestrian" };
    expect(servicePulseMarkerPlan(route, true)).toEqual({ staticDistanceBandCount: 3, animatedMarkerCount: 0, semantics: "network-distance-only" });
    expect(servicePulseMarkerPlan(route, false).animatedMarkerCount).toBe(1);
  });

  it("renders temporal samples only at their published point geometry", () => {
    const records = buildTemporalGhostRecords({ type: "FeatureCollection", features: [{
      type: "Feature",
      id: "change-1",
      geometry: { type: "Point", coordinates: [139.4, 35.7] },
      properties: { change_type: "removed", review_status: "not_reviewed" },
    }] });
    expect(records).toEqual([{ id: "change-1", kind: "removed", longitude: 139.4, latitude: 35.7, reviewStatus: "not_reviewed", officialGeometryAvailable: false }]);
  });

  it("fails a terrain scene until every explicit readiness requirement is met", () => {
    const requirements = { requiresTerrain: true, requiresLocalDem: true, requiresBuildings: true, requiresRoads: true, requiresAnalysis: true, minimumBuildingFeatures: 1, minimumTerrainTiles: 1, stableFrames: 3 };
    expect(evaluateVisualReadiness(INITIAL_VISUAL_READINESS, requirements).visualReady).toBe(false);
    const complete = { ...INITIAL_VISUAL_READINESS, appReady: true, basemapReady: true, analysisReady: true, cameraSettled: true, cesiumSceneReady: true, canvasSizeReady: true, buildingTilesReady: true, buildingFeatureCount: 1, terrainProviderReady: true, terrainTileCount: 1, localDemReady: true, roadsReady: true, overlayReady: true, fontReady: true, stableFrameCount: 3, terrainSource: "PLATEAU DEM", buildingSource: "PLATEAU 3D Tiles" };
    expect(evaluateVisualReadiness(complete, requirements)).toEqual({ visualReady: true, unmet: [] });
    expect(evaluateVisualReadiness({ ...complete, localDemReady: false }, requirements).unmet).toContain("local_dem");
    expect(evaluateVisualReadiness({ ...complete, canvasSizeReady: false }, requirements).unmet).toContain("canvas_size");
    expect(evaluateVisualReadiness({ ...complete, outstandingCriticalRequests: 1 }, requirements).unmet).toContain("critical_requests");
    expect(evaluateVisualReadiness({ ...complete, stableFrameCount: 2 }, requirements).unmet).toContain("stable_frames");
  });
});
