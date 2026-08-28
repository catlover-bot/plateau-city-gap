import { describe, expect, it } from "vitest";
import type { AppData, WorkspaceMapData } from "../../types";
import type { SpatialSelection } from "../../state/spatial/types";
import { buildUrbanObjectGraph } from "./urbanObjectGraph";

const mesh = {
  type: "Feature" as const,
  geometry: { type: "Polygon", coordinates: [[[135.39, 35.44], [135.4, 35.44], [135.4, 35.45], [135.39, 35.45], [135.39, 35.44]]] },
  properties: { mesh_code: "533513314", area_label: "常団地前", population: 410, elderly_population: 98, exploratory_score_c: 0.28 },
};

const data = {
  city: { id: "maizuru", code: "26202", name: "舞鶴市", prefecture: "京都府", mode: "primary_demo", map_view: { longitude: 135.39, latitude: 35.44, height: 600 } },
  meshes: { type: "FeatureCollection", features: [mesh] },
  plateauRoads: { type: "FeatureCollection", features: [{
    type: "Feature", geometry: { type: "Polygon", coordinates: [[[135.397, 35.446], [135.398, 35.446], [135.398, 35.447], [135.397, 35.446]]] },
    properties: { road_id: "tran-real-1", road_name: "実在道路", road_class: "1040", source: "Project PLATEAU 舞鶴市2025 道路LOD1" },
  }] },
  plateauMetadata: {
    year: 2025,
    streaming: { local_dem_kind: "舞鶴市2025 PLATEAU dem:TINRelief" },
    reference_layer: { deep_dive_mesh_code: "533513314", deep_dive_buildings: 296, reason: "公式3D Tiles監査", viewpoint: { longitude: 135.3975, latitude: 35.4465 } },
  },
} as unknown as AppData;

const building: SpatialSelection = {
  type: "building", id: "bldg-real-1", city: "maizuru", urbanState: "2025", label: "住宅",
  longitude: 135.3974, latitude: 35.4464,
  properties: { parent_mesh_code: "533513314", usage: "住宅", measured_height_m: 8.5 },
};

const workspace = { type: "FeatureCollection", features: [{
  type: "Feature", id: "planning-real-1",
  geometry: { type: "Polygon", coordinates: [[[135.39, 35.44], [135.41, 35.44], [135.41, 35.46], [135.39, 35.46], [135.39, 35.44]]] },
  properties: { layer_type: "planning_context", story_id: "scenario_a", plateau_gml_id: "urf-real-1", label: "第1種住居地域", source_member: "udx/urf/real.gml", interpretation: "review context" },
}], layer_counts: {} } as unknown as WorkspaceMapData;

describe("PLATEAU urban object graph", () => {
  it("lifts one Finding from mesh to real building group, building, road and terrain", () => {
    const graph = buildUrbanObjectGraph({ data, selection: building, primaryLayer: "analysis-city-gap" });
    expect(graph.nodes).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: "mesh:533513314" }),
      expect.objectContaining({ id: "building_group:533513314", attributes: expect.objectContaining({ building_count: 296 }) }),
      expect.objectContaining({ id: "building:bldg-real-1" }),
      expect.objectContaining({ id: "road:tran-real-1" }),
      expect.objectContaining({ id: "terrain:533513314", attributes: expect.objectContaining({ exact_local_dem: true, exaggeration: false }) }),
    ]));
    expect(graph.relations).toEqual(expect.arrayContaining([
      expect.objectContaining({ from: "finding:533513314", to: "building_group:533513314" }),
      expect.objectContaining({ from: "building:bldg-real-1", to: "finding:533513314" }),
    ]));
  });

  it("preserves privacy and experimental road graph semantics", () => {
    const graph = buildUrbanObjectGraph({ data, selection: building, primaryLayer: "analysis-population" });
    const buildingNode = graph.nodes.find((node) => node.kind === "building");
    const roadNode = graph.nodes.find((node) => node.kind === "road");
    expect(buildingNode?.attributes.population_semantics).toContain("actual resident countではない");
    expect(roadNode?.attributes.graph_semantics).toContain("pedestrian/walking networkではない");
  });

  it("links a selected object to actual planning geometry only when it contains the point", () => {
    const graph = buildUrbanObjectGraph({ data, selection: building, primaryLayer: "scenario-footprint", workspace, workspacePhase: "scenario_a" });
    expect(graph.nodes).toContainEqual(expect.objectContaining({ id: "planning:urf-real-1" }));
    expect(graph.relations).toContainEqual(expect.objectContaining({ from: "building:bldg-real-1", to: "planning:urf-real-1", kind: "within" }));
  });
});
