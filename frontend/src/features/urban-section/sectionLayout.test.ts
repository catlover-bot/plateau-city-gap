import { describe, expect, it } from "vitest";
import {
  buildSectionFocusCallout,
  buildSectionPlot,
  nearestSectionObject,
  selectedSectionObject,
  sectionSampleIndexAtViewX,
} from "./sectionLayout";
import type { SectionData } from "./sectionTypes";

function sectionFixture(): SectionData {
  return {
    transect_id: "test-section",
    pack_id: "test-pack",
    geometry: { type: "LineString", coordinates: [[135, 35], [135.01, 35.01]] },
    buffer_m: 20,
    sample_interval_m: 10,
    vertical_datum: "test",
    terrain_source: "test",
    terrain_interpolation: "test",
    terrain_samples: [
      { sample_order: 0, distance_m: 0, longitude: 135, latitude: 35, elevation_m: 100, source_triangle_id: "a", quality: "direct_tin" },
      { sample_order: 1, distance_m: 10, longitude: 135.0025, latitude: 35.0025, elevation_m: 90, source_triangle_id: "b", quality: "direct_tin" },
      { sample_order: 2, distance_m: 20, longitude: 135.005, latitude: 35.005, elevation_m: null, source_triangle_id: null, quality: "no_coverage" },
      { sample_order: 3, distance_m: 30, longitude: 135.0075, latitude: 35.0075, elevation_m: 80, source_triangle_id: "c", quality: "direct_tin" },
      { sample_order: 4, distance_m: 40, longitude: 135.01, latitude: 35.01, elevation_m: 85, source_triangle_id: "d", quality: "boundary" },
    ],
    buildings: [{
      source_object_id: "building-nearby",
      relation: "nearby",
      start_distance_m: 8,
      end_distance_m: 12,
      offset_distance_m: 2,
      properties: { usage_label: "公共施設", measured_height_m: 20 },
    }],
    roads: [{
      source_object_id: "road-direct",
      relation: "direct",
      start_distance_m: 9,
      end_distance_m: 11,
      offset_distance_m: 0,
      properties: { road_name: "テスト道路" },
    }],
    service_locations: [],
    scenario_sites: [],
    counterfactual: {
      plan_id: "test-plan",
      building_group_count: 0,
      baseline: { distance_m: 1, score_c: 1 },
      scenario: { distance_m: 1, score_c: 1, distance_reduction_m: 0, score_c_reduction: 0 },
      distance_semantics: "test",
      geometry_policy: "fixed",
      limitations: [],
    },
    planning_bands: [],
    hazard_bands: [],
  };
}

describe("urban section plot layout", () => {
  it("uses stable desktop and compact scales while splitting uncovered terrain", () => {
    const data = sectionFixture();
    const desktop = buildSectionPlot(data, false);
    const compact = buildSectionPlot(data, true);

    expect(desktop.viewWidth).toBe(1000);
    expect(compact.viewWidth).toBe(390);
    expect(desktop.x(0)).toBe(38);
    expect(desktop.x(40)).toBe(980);
    expect(compact.x(40)).toBe(370);
    expect(desktop.minimumElevation).toBe(80);
    expect(desktop.maximumElevation).toBe(100);
    expect(desktop.terrainSegments).toHaveLength(2);
    expect(desktop.terrainSegments[0].line).toMatch(/^M38\.00,/);
  });

  it("prefers a direct relation and preserves the focus callout bounds", () => {
    const data = sectionFixture();
    const plot = buildSectionPlot(data, false);
    const focused = nearestSectionObject(data, 10, 90);

    expect(focused).toMatchObject({
      id: "road-direct",
      kind: "road",
      label: "テスト道路",
      relation: "direct",
    });
    const callout = buildSectionFocusCallout(focused!, plot, false, () => 90, () => 110);
    expect(callout.relation).toBe("直接交差");
    expect(callout.labelX).toBeGreaterThanOrEqual(38);
    expect(callout.labelX + callout.labelWidth).toBeLessThanOrEqual(980);
  });

  it("maps view coordinates to the nearest terrain sample", () => {
    const data = sectionFixture();
    const plot = buildSectionPlot(data, true);
    expect(sectionSampleIndexAtViewX(data, plot, plot.x(30))).toBe(3);
  });

  it.each([320, 390, 640, 720, 919, 1050.2, 1480])("uses %ipx container coordinates without shrinking text or changing data", (width) => {
    const data = sectionFixture();
    const before = JSON.stringify(data);
    const plot = buildSectionPlot(data, width < 600, width);
    expect(plot.viewWidth).toBe(width);
    expect(plot.x(0)).toBe(54);
    expect(plot.x(40)).toBe(width - 20);
    expect(sectionSampleIndexAtViewX(data, plot, plot.x(30))).toBe(3);
    expect(plot.minimumElevation).toBe(80);
    expect(plot.maximumElevation).toBe(100);
    const detail = selectedSectionObject(data, { type: "building", id: "building-nearby", city: "maizuru", urbanState: "2025", properties: {} })!;
    const callout = buildSectionFocusCallout(detail, plot, width < 600, () => 180, () => 200);
    expect(callout.labelX).toBeGreaterThanOrEqual(plot.plotLeft);
    expect(callout.labelX + callout.labelWidth).toBeLessThanOrEqual(width - 20);
    expect(JSON.stringify(data)).toBe(before);
  });

  it("requires exact typed section membership, preserves nearby/zero and never infers a missing selection", () => {
    const data = sectionFixture();
    const selection = { type: "building" as const, id: "building-nearby", city: "maizuru" as const, urbanState: "2025" as const, properties: {} };
    expect(selectedSectionObject(data, selection)).toMatchObject({ id: selection.id, kind: "building", relation: "nearby", offsetDistanceM: 2, elevationM: 90 });
    expect(selectedSectionObject(data, { ...selection, id: "not-recorded" })).toBeNull();
    expect(selectedSectionObject(data, { ...selection, type: "road" })).toBeNull();
    expect(selectedSectionObject(data, { ...selection, type: "mesh" })).toBeNull();
    expect(selectedSectionObject(data, null)).toBeNull();
    data.terrain_samples[1].elevation_m = 0;
    expect(selectedSectionObject(data, selection)?.elevationM).toBe(0);
    data.terrain_samples[1].elevation_m = null;
    expect(selectedSectionObject(data, selection)?.elevationM).toBeNull();
  });

  it("matches road ID aliases only against real road relations", () => {
    const data = sectionFixture();
    data.roads[0].source_object_id = "tran_recorded-0";
    const selection = { type: "road" as const, id: "tran_recorded:0", city: "maizuru" as const, urbanState: "2025" as const, properties: {} };
    expect(selectedSectionObject(data, selection)?.id).toBe("tran_recorded-0");
    expect(selectedSectionObject(data, { ...selection, id: "tran_missing:0" })).toBeNull();
    expect(selectedSectionObject(data, { ...selection, type: "building" })).toBeNull();
  });
});
