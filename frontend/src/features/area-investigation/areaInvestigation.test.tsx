import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { AppData } from "../../types";
import { AreaSummaryPanel, TargetTasks } from "./AreaInvestigationJourney";
import {
  parseInvestigationAreaFixture,
  radiusMethodology,
  resolveAreaSummary,
  validatePublicRadius,
  type PublicAreaOrigin,
} from "./areaModel";
import type {
  InvestigationAreaFixture,
  InvestigationAreaSummary,
} from "./areaTypes";

const center: [number, number] = [135.33, 35.44];
const origin: PublicAreaOrigin = {
  kind: "map_point",
  label: "任意地点",
  coordinates: center,
};

const square = {
  type: "Feature" as const,
  geometry: {
    type: "Polygon",
    coordinates: [[
      [135.32, 35.43],
      [135.34, 35.43],
      [135.34, 35.45],
      [135.32, 35.45],
      [135.32, 35.43],
    ]],
  },
  properties: {
    mesh_code: "test-mesh",
    area_label: "試験メッシュ",
    centroid_lon: center[0],
    centroid_lat: center[1],
    population: 1000,
    elderly_population: 300,
  },
};

const point = (id: string, name: string, longitude = center[0], latitude = center[1]) => ({
  type: "Feature" as const,
  geometry: { type: "Point", coordinates: [longitude, latitude] },
  properties: { id, name },
});

const appData = {
  meshes: { type: "FeatureCollection", features: [square] },
  stations: { type: "FeatureCollection", features: [point("station-test", "試験駅")] },
  busStops: { type: "FeatureCollection", features: [point("bus-test", "試験停留所")] },
  medicalFacilities: { type: "FeatureCollection", features: [point("medical-test", "試験施設")] },
} as unknown as AppData;

const fixture: InvestigationAreaFixture = {
  schema_version: "citygap.area-summary@1",
  rule_version: "test@1",
  generated_from: "test",
  validation_status: {
    aoi_need: "DIRECT_MUNICIPAL_NEED_CONFIRMED",
    area_summary_content: "DIRECT_MUNICIPAL_NEED_PARTIALLY_CONFIRMED",
    known_unknown_value: "DIRECT_MUNICIPAL_VALUE_SIGNAL_CONFIRMED",
    unknown_to_field_task_workflow: "AWAITING_MUNICIPAL_WORKFLOW_REVIEW",
    human: "AWAITING_HUMAN_TEST",
  },
  area_summary_priority: [
    "population",
    "age_distribution",
    "building_use",
    "establishments",
    "urban_planning",
    "transport",
  ],
  areas: [],
};

describe("Investigation Area P0 contract", () => {
  it("keeps presets and bounded custom radius semantics explicit", () => {
    expect(validatePublicRadius(100)).toBe(100);
    expect(validatePublicRadius(3000)).toBe(3000);
    expect(() => validatePublicRadius(99)).toThrow();
    expect(() => validatePublicRadius(3001)).toThrow();
    expect(() => validatePublicRadius(500.5)).toThrow();
    expect(radiusMethodology(500)).toBe("mlit_elderly_walk_reference_500m");
    expect(radiusMethodology(800)).toBe("mlit_general_walk_reference_800m");
    expect(radiusMethodology(1000)).toBe("broad_context_1000m");
    expect(radiusMethodology(650)).toBe("custom_radius");
  });

  it("validates the shared AreaSummary schema boundary", () => {
    expect(parseInvestigationAreaFixture(fixture)).toBe(fixture);
    expect(() => parseInvestigationAreaFixture({ schema_version: "other" })).toThrow();
  });

  it("derives an honest arbitrary-point preview without borrowing PLATEAU objects", () => {
    const summary = resolveAreaSummary(fixture, appData, origin, 800);
    expect(summary.geometry_kind).toBe("point_radius");
    expect(summary.origin.kind).toBe("map_point");
    expect(summary.metrics.map((metric) => metric.key)).toEqual(fixture.area_summary_priority);
    expect(summary.metrics.find((metric) => metric.key === "population")?.calculation)
      .toBe("area_weighted_estimate");
    expect(summary.metrics.find((metric) => metric.key === "building_use")?.status)
      .toBe("unavailable");
    expect(summary.unknowns).toHaveLength(2);
    expect(summary.unknowns.every((unknown) =>
      unknown.checks.length >= 3 && unknown.checks.length <= 5
    )).toBe(true);
    expect(summary.unknowns[0].target.scope).toBe("mesh");
    expect(summary.content_sha256).toBeNull();
  });
});

describe("Investigation Area public outputs", () => {
  const summary = resolveAreaSummary(fixture, appData, origin, 800);

  it("keeps quantified evidence and unknowns in one continuous panel", () => {
    const html = renderToStaticMarkup(<AreaSummaryPanel summary={summary} />);
    expect(html).toContain("この範囲で、データから確認できたこと");
    expect(html).toContain("まだデータだけでは分からないことがあります");
    for (const label of ["人口", "年齢分布", "建物用途分布", "事業所", "都市計画", "交通"]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("この範囲では未取得");
    expect(html).toContain("駅 1 · バス停 1");
    expect(html).not.toContain("医療施設 1");
  });

  it("renders only unverified tasks with traceable targets and no fake evidence", () => {
    const html = renderToStaticMarkup(<TargetTasks summary={summary as InvestigationAreaSummary} />);
    expect((html.match(/未確認/g) ?? []).length).toBeGreaterThanOrEqual(2);
    expect(html).toContain("test-mesh");
    expect(html).toContain("写真・GPS・回答・担当者・自治体reviewは作成も表示もしていません");
    expect(html).not.toMatch(/<(input|textarea|select)\b/);
  });
});
