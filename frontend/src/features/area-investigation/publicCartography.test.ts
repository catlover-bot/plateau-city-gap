import { describe, expect, it, vi } from "vitest";
import type { GeoJsonFeatureCollection } from "../../types";
import type { AreaTarget, InvestigationAreaSummary } from "./areaTypes";
import {
  buildPublicAreaGeometry,
  derivativeAvailableFor,
  loadPublicCartographyData,
  publicStoryLegend,
  resolvePublicTarget,
  type PublicCartographyData,
  type PublicCartographyManifest,
} from "./publicCartography";

const empty: GeoJsonFeatureCollection = { type: "FeatureCollection", features: [] };
const building = {
  type: "Feature" as const,
  id: "building-1",
  properties: { object_id: "building-1", object_type: "building" },
  geometry: {
    type: "Polygon",
    coordinates: [[[135.32, 35.43], [135.33, 35.43], [135.33, 35.44], [135.32, 35.44], [135.32, 35.43]]],
  },
};

const manifest: PublicCartographyManifest = {
  schema_version: "citygap.public-cartography@1",
  artifact_kind: "display_derivative",
  rule_version: "test@1",
  source: {
    path: "city.gml.zip",
    version: "plateau-maizuru-2025",
    sha256: "source-hash",
    city_code: "26202",
    crs: "EPSG:4326",
  },
  scope: {
    area_id: "nishi-maizuru-800m-v1",
    area_version: 1,
    radius_m: 800,
    area_content_sha256: "area-hash",
    origin: {
      kind: "station",
      source_feature_id: "station-007",
      coordinates: [135.33, 35.44],
    },
  },
  target_ids: ["building-1"],
  resolved_target_ids: { buildings: ["building-1"], roads: [], planning: [] },
  artifacts: {
    buildings: { path: "buildings.geojson", feature_count: 1, geometry_types: ["Polygon"], property_allowlist: ["object_id"], sha256: "building-hash" },
    roads: { path: "roads.geojson", feature_count: 0, geometry_types: [], property_allowlist: ["object_id"], sha256: "road-hash" },
    planning: { path: "planning.geojson", feature_count: 0, geometry_types: [], property_allowlist: ["object_id"], sha256: "planning-hash" },
  },
};

const data: PublicCartographyData = {
  manifest,
  buildings: { type: "FeatureCollection", features: [building] },
  roads: empty,
  planning: empty,
};

const summary = {
  radius_m: 800,
  origin: {
    kind: "station",
    source_feature_id: "station-007",
    coordinates: [135.33, 35.44],
  },
} as InvestigationAreaSummary;

const buildingTarget: AreaTarget = {
  scope: "plateau_object",
  object_type: "building",
  source_object_id: "building-1",
  label: "PLATEAU建物",
  longitude: 135.325,
  latitude: 35.435,
  dataset: "PLATEAU舞鶴市 2025",
  role: "primary",
};

describe("Public cartography contract", () => {
  it("builds a deterministic 96-segment display circle and outside mask", () => {
    const first = buildPublicAreaGeometry([135.33, 35.44], 800);
    const second = buildPublicAreaGeometry([135.33, 35.44], 800);

    expect(second).toEqual(first);
    expect((first.polygon.features[0].geometry?.coordinates as number[][][])[0]).toHaveLength(97);
    expect(first.outsideMask.features[0].properties?.role).toBe("outside_context");
    expect(first.bounds.west).toBeLessThan(135.33);
    expect(first.bounds.east).toBeGreaterThan(135.33);
  });

  it("limits a display derivative to its versioned station Area", () => {
    expect(derivativeAvailableFor(data, summary)).toBe(true);
    expect(derivativeAvailableFor(data, { ...summary, radius_m: 1000 })).toBe(false);
    expect(derivativeAvailableFor(data, {
      ...summary,
      origin: { ...summary.origin, kind: "map_point" },
    })).toBe(false);
  });

  it("distinguishes exact geometry, reference positions, and Area fallback", () => {
    expect(resolvePublicTarget(buildingTarget, data, true)).toMatchObject({
      resolution: "exact",
      objectId: "building-1",
    });
    expect(resolvePublicTarget({ ...buildingTarget, source_object_id: "missing" }, data, true)).toMatchObject({
      resolution: "reference_position",
    });
    expect(resolvePublicTarget({
      ...buildingTarget,
      scope: "mesh",
      object_type: "mesh",
      source_object_id: "mesh-1",
    }, data, true)).toMatchObject({
      resolution: "area_fallback",
      geometry: empty,
    });
  });

  it("provides one contextual legend without inventing establishment points", () => {
    expect(publicStoryLegend("building-use", true)?.items).toHaveLength(4);
    expect(publicStoryLegend("transport", true)?.items).toHaveLength(2);
    expect(publicStoryLegend("establishments", true)).toMatchObject({
      items: [],
      note: "範囲集計・個別事業所の位置は表示していません",
    });
  });

  it("loads only manifest-declared display artifacts", async () => {
    const responses = new Map<string, unknown>([
      ["/base/data/cartography/manifest.json", manifest],
      ["/base/data/cartography/buildings.geojson", data.buildings],
      ["/base/data/cartography/roads.geojson", data.roads],
      ["/base/data/cartography/planning.geojson", data.planning],
    ]);
    const fetchMock = vi.fn(async (url: string | URL | Request) => ({
      ok: responses.has(String(url)),
      status: responses.has(String(url)) ? 200 : 404,
      json: async () => responses.get(String(url)),
    }));
    const fetcher = fetchMock as unknown as typeof fetch;

    const loaded = await loadPublicCartographyData(fetcher, "/base/");
    expect(loaded).toEqual(data);
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "/base/data/cartography/manifest.json",
      "/base/data/cartography/buildings.geojson",
      "/base/data/cartography/roads.geojson",
      "/base/data/cartography/planning.geojson",
    ]);
  });
});
