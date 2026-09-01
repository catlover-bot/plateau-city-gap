import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PublicHeader } from "../navigation/PublicHeader";
import { AreaSummaryPanel, TargetTasks } from "./AreaInvestigationJourney";
import {
  PUBLIC_LANDING_COPY,
  PUBLIC_RADIUS_OPTIONS,
  contextual3dEligibility,
  radiusExplanation,
} from "./publicAreaPresentation";
import type { AreaMetric, AreaTarget, AreaUnknown, InvestigationAreaSummary } from "./areaTypes";

const metric = (group: AreaMetric["group"], label: string): AreaMetric => ({
  key: group,
  group,
  label,
  status: "unavailable",
  value: null,
  unit: "",
  coverage_ratio: null,
  calculation: "exact",
  source: { dataset: "official-test", source_date: "2020" },
  limitation: "公開データの範囲外",
});

const target: AreaTarget = {
  scope: "plateau_object",
  object_type: "building",
  source_object_id: "bldg-real-id",
  label: "PLATEAU建物",
  longitude: 135.33,
  latitude: 35.44,
  dataset: "PLATEAU舞鶴市 2025",
  role: "primary",
};

const unknown = (index: number, targetOverride: Partial<AreaTarget> = {}): AreaUnknown => ({
  id: `unknown-${index}`,
  title: `未確認事項${index}`,
  importance: "判断に影響するため",
  status: "unknown",
  action_type: "field_verification",
  reason_code: "requires_field_observation",
  source_boundary: "公開データでは現況を確認できません",
  target: { ...target, ...targetOverride },
  checks: ["確認1", "確認2", "確認3"],
});

const summary: InvestigationAreaSummary = {
  id: "area-1",
  area_series_id: "series-1",
  version: 1,
  label: "西舞鶴駅周辺800m",
  geometry_kind: "point_radius",
  origin: {
    kind: "station",
    source_feature_id: "station-007",
    label: "西舞鶴駅",
    coordinates: [135.33, 35.44],
  },
  radius_m: 800,
  radius_methodology: "mlit_general_walk_reference_800m",
  clipped_area_ratio: 1,
  metrics: [
    metric("population", "人口"),
    metric("age_distribution", "年齢分布"),
    metric("building_use", "建物用途分布"),
    metric("establishments", "事業所"),
    metric("urban_planning", "都市計画"),
    metric("transport", "交通"),
  ],
  unknowns: [unknown(1), unknown(2), unknown(3), unknown(4)],
  status: "unverified",
  content_sha256: "verified-content",
};

describe("Public first-run presentation contract", () => {
  it("uses the approved landing and short radius labels", () => {
    expect(PUBLIC_LANDING_COPY).toEqual({
      heading: "気になる場所を、地図とデータで確かめる。",
      subcopy: "場所と範囲を選ぶと、人口・年齢、建物の使われ方、事業所、都市計画、交通をまとめて確認できます。データだけでは判断できない点も整理します。",
      primaryCta: "地図で場所を調べる",
    });
    expect(PUBLIC_LANDING_COPY.heading).not.toContain("今");
    expect(PUBLIC_RADIUS_OPTIONS.map((option) => option.label)).toEqual(["500m", "800m", "1km"]);
    expect(radiusExplanation(800)).toBe("800mは、国土交通省の都市構造評価で一般的な徒歩圏の目安として使われる距離です。実際の徒歩10分到達圏を示すものではありません。");
  });

  it("keeps prohibited walking claims out of public copy", () => {
    const publicCopy = [
      ...Object.values(PUBLIC_LANDING_COPY),
      ...PUBLIC_RADIUS_OPTIONS.map((option) => option.label),
      radiusExplanation(500),
      radiusExplanation(800),
      radiusExplanation(1000),
      radiusExplanation(650),
    ].join("\n");
    for (const prohibited of [
      "徒歩10分圏",
      "10分以内に歩ける",
      "walking isochrone",
      "実際に徒歩で到達できる",
      "道路ネットワーク上の徒歩圏",
    ]) {
      expect(publicCopy).not.toContain(prohibited);
    }
  });

  it("renders the five summary groups and only three public unknowns", () => {
    const html = renderToStaticMarkup(<AreaSummaryPanel summary={summary} publicMode />);
    for (const label of ["人口・年齢", "建物の使われ方", "事業所", "都市計画", "交通"]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("未確認事項1");
    expect(html).toContain("未確認事項3");
    expect(html).not.toContain("未確認事項4");
    expect(html).not.toContain("KNOWN / UNKNOWN");
  });

  it("keeps target provenance behind disclosure and excludes fake field evidence", () => {
    const html = renderToStaticMarkup(<TargetTasks summary={{ ...summary, unknowns: [summary.unknowns[0]] }} publicMode />);
    expect(html).toContain("<summary>対象データの出典</summary>");
    expect(html).toContain("bldg-real-id");
    expect(html).toContain("未確認");
    expect(html).toContain("写真・GPS・回答・担当者・自治体の確認結果は作成も表示もしていません");
    expect(html).not.toMatch(/<(input|textarea|select)\b/);
  });

  it("allows contextual 3D only for resolved, version-compatible PLATEAU objects", () => {
    expect(contextual3dEligibility(summary, target, 2025, true).eligible).toBe(true);
    expect(contextual3dEligibility(summary, { ...target, scope: "mesh", object_type: "mesh" }, 2025, true).eligible).toBe(false);
    expect(contextual3dEligibility(summary, { ...target, scope: "facility", object_type: "facility" }, 2025, true).eligible).toBe(false);
    expect(contextual3dEligibility(summary, { ...target, source_object_id: "unresolved-road" }, 2025, true).eligible).toBe(false);
    expect(contextual3dEligibility({ ...summary, content_sha256: null }, target, 2025, true).eligible).toBe(false);
    expect(contextual3dEligibility(summary, target, undefined, true).eligible).toBe(false);
    expect(contextual3dEligibility(summary, target, 2025, false).eligible).toBe(false);
  });

  it("keeps a single secondary header action", () => {
    const html = renderToStaticMarkup(<PublicHeader onRestart={() => undefined} onOpenAdvanced={() => undefined} />);
    expect(html).toContain("CITY GAP");
    expect(html).toContain("舞鶴市");
    expect(html).toContain("詳細分析");
    expect((html.match(/<button/g) ?? [])).toHaveLength(2);
  });
});
