import { describe, expect, it } from "vitest";
import contextFixture from "../../../public/data/guided/area-context/533513314.json";
import otherContextFixture from "../../../public/data/guided/area-context/533512753.json";
import renderedRoadFixture from "../../../public/data/plateau_roads.geojson?raw";
import type { AppData, GeoJsonFeatureCollection } from "../../types";
import type { SpatialSelection } from "../../state/spatial/types";
import type { GuidedAreaContext } from "../guided-spatial/guidedTypes";
import { guidedObjectTarget } from "../guided-spatial/guided3d";
import { advancedAreaId, advancedAreaSelection, advancedExactObject, advancedNumber } from "./advanced3dModel";

const context = contextFixture as unknown as GuidedAreaContext;
const otherContext = otherContextFixture as unknown as GuidedAreaContext;
const roads = JSON.parse(renderedRoadFixture) as GeoJsonFeatureCollection;
const area: SpatialSelection = { type: "mesh", id: context.mesh_code, city: "maizuru", urbanState: "2025" };
const building: SpatialSelection = { ...area, type: "building", id: String(context.layers.buildings.features[0].id), properties: { parent_mesh_code: area.id } };
const data = {
  city: { id: "maizuru" },
  meshes: { type: "FeatureCollection", features: [{ type: "Feature", geometry: null, properties: { mesh_code: area.id, area_label: "検証済み地域", centroid_lon: 135.396875, centroid_lat: 35.44791666666667 } }] },
} as unknown as AppData;

describe("Advanced Area and exact-object identity", () => {
  it("uses an explicit Area or known parent rather than inventing membership", () => {
    expect(advancedAreaId(area)).toBe(area.id);
    expect(advancedAreaId({ ...area, type: "building_group" })).toBe(area.id);
    expect(advancedAreaId(building)).toBe(area.id);
    expect(advancedAreaId({ ...building, properties: {} })).toBeNull();
    expect(advancedAreaId({ ...building, properties: { parent_mesh_code: Number(area.id) } })).toBeNull();
    expect(advancedAreaId({ ...area, id: `${area.id}0` })).toBeNull();
  });

  it("rehydrates Area data only from the same city's actual mesh catalog", () => {
    expect(advancedAreaSelection(data, building)).toMatchObject({ type: "mesh", id: area.id, label: "検証済み地域", longitude: 135.396875 });
    expect(advancedAreaSelection(data, { ...building, city: "fujisawa" })).toBeNull();
    expect(advancedAreaSelection(data, { ...area, id: otherContext.mesh_code })).toBeNull();
    expect(advancedAreaSelection(data, null)).toBeNull();
  });

  it("requires actual typed geometry membership for an exact target", () => {
    expect(advancedExactObject(building, context)?.id).toBe(building.id);
    expect(advancedExactObject(building, otherContext)).toBeNull();
    expect(advancedExactObject(building, null)).toBeNull();
    expect(advancedExactObject({ ...building, id: "bldg_not-in-area" }, context)).toBeNull();
    expect(advancedExactObject({ ...building, type: "road" }, context)).toBeNull();
    expect(advancedExactObject({ ...building, city: "fujisawa" }, context)).toBeNull();
    expect(advancedExactObject(area, context)).toBeNull();
  });

  it("preserves missing official height and recorded zero storeys without estimating values", () => {
    const picked = { ...building, properties: { ...building.properties, measured_height_m: null, storeys_below_ground: 0 } };
    const exact = advancedExactObject(picked, context);
    expect(exact?.properties?.measured_height_m).toBeNull();
    expect(exact?.properties?.storeys_below_ground).toBe(0);
    expect(advancedExactObject(building, context)?.properties?.measured_height_m).toBeUndefined();
    expect(exact?.properties?.object_id).toBe(building.id);
  });

  it("matches every existing renderer road surface to its exact context geometry and retains the renderer identity", () => {
    expect(roads.features.length).toBe(135);
    for (const road of roads.features) {
      const rendererId = String(road.properties?.road_id);
      const canonicalId = rendererId.replace(/-(\d+)$/, ":$1");
      const expectedFeature = context.layers.roads.features.find((feature) => feature.id === canonicalId);
      expect(expectedFeature).toBeDefined();
      const selected: SpatialSelection = { ...area, type: "road", id: rendererId, properties: { ...road.properties, parent_mesh_code: area.id } };
      const exact = advancedExactObject(selected, context);
      expect(exact).toMatchObject({ id: canonicalId, properties: { renderer_road_id: rendererId, parent_mesh_code: area.id } });
      expect(guidedObjectTarget(exact, context)?.geometry.features).toEqual([expectedFeature]);
    }
    expect(advancedExactObject({ ...area, type: "road", id: "tran_not-real-0", properties: { parent_mesh_code: area.id } }, context)).toBeNull();
  });
});

describe("Advanced values retain unknowns and measured precision", () => {
  it.each([null, undefined, "", "  ", "\t", Number.NaN, Number.POSITIVE_INFINITY, "not-recorded", false, {}])("shows missing or invalid %j as dataなし", (value) => {
    expect(advancedNumber(value, "m")).toBe("データなし");
  });

  it("keeps real zero and decimal measurements, rounding only when explicitly requested", () => {
    expect(advancedNumber(0, "階")).toBe("0階");
    expect(advancedNumber("0", "人", true)).toBe("0人");
    expect(advancedNumber(8.5, "m")).toBe("8.5m");
    expect(advancedNumber(" 8.5 ", "m")).toBe("8.5m");
    expect(advancedNumber(1200.6, "m", true)).toBe("1,201m");
  });
});
