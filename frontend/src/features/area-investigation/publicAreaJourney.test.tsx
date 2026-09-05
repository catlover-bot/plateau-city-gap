import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PublicHeader } from "../navigation/PublicHeader";
import { AreaSummaryPanel, TargetTasks } from "./AreaInvestigationJourney";
import {
  PUBLIC_LANDING_COPY,
  PUBLIC_LANDING_HEADING_PHRASES,
  PUBLIC_RADIUS_OPTIONS,
  PUBLIC_URBAN_SECTION_DECISION,
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
  it("keeps the full heading in two readable phrases without splitting 地図", () => {
    expect(PUBLIC_LANDING_HEADING_PHRASES).toEqual(["舞鶴を、", "地図で調べる。"]);
    expect(PUBLIC_LANDING_HEADING_PHRASES.join("")).toBe(PUBLIC_LANDING_COPY.heading);
  });

  it("uses the approved landing and short radius labels", () => {
    expect(PUBLIC_LANDING_COPY).toEqual({
      heading: "舞鶴を、地図で調べる。",
      subcopy: "場所と範囲を選び、人口・建物・交通などを確認します。",
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

  it("keeps public Unknown cards simple and moves rigor into one disclosure", () => {
    const html = renderToStaticMarkup(<AreaSummaryPanel summary={summary} publicMode />);
    for (const label of ["人口・年齢", "建物の使われ方", "事業所", "都市計画", "交通"]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("未確認事項1");
    expect(html).toContain("未確認事項3");
    expect(html).not.toContain("未確認事項4");
    expect(html).not.toContain("KNOWN / UNKNOWN");

    const unknownFirstView = html.split('<section class="area-unknown-section"')[1]?.split("</section>")[0] ?? "";
    expect(unknownFirstView).toContain("判断に影響するため");
    expect(unknownFirstView).not.toContain("公開データでは現況を確認できません");
    expect(unknownFirstView).not.toContain("official-test");
    expect(unknownFirstView).not.toContain("bldg-real-id");
    expect(unknownFirstView).not.toContain("未確認</span>");

    expect((html.match(/<summary>出典・データの注意点<\/summary>/g) ?? [])).toHaveLength(1);
    expect(html).not.toContain("<summary>出典と限界</summary>");
    expect(html).toContain("公開データでは現況を確認できません");
    expect(html).toContain("official-test");
    expect(html).toContain("bldg-real-id");
  });

  it("keeps Summary stories as small contextual actions rather than tabs", () => {
    const html = renderToStaticMarkup(
      <AreaSummaryPanel
        summary={summary}
        publicMode
        activeStoryId="population-age"
        onStorySelect={() => undefined}
      />,
    );
    expect((html.match(/class="area-story-action"/g) ?? [])).toHaveLength(5);
    expect((html.match(/aria-pressed="true"/g) ?? [])).toHaveLength(1);
    expect(html).toContain("地図に表示");
    expect(html).not.toContain('role="tab"');
    expect(html).not.toContain('role="tablist"');
  });

  it("keeps target provenance behind disclosure and excludes fake field evidence", () => {
    const html = renderToStaticMarkup(<TargetTasks summary={{ ...summary, unknowns: [summary.unknowns[0]] }} publicMode />);
    expect(html).toContain("<summary>場所データの出典</summary>");
    expect(html).toContain("bldg-real-id");
    expect(html).toContain("未確認");
    expect(html).toContain("この公開画面には、写真やGPSなどの現地記録はありません");
    expect(html).toContain("現地で見るポイント");
    expect(html).not.toMatch(/<(input|textarea|select)\b/);
  });

  it("keeps internal terms and unsupported claims out of the initial reading path", () => {
    const markup = [
      renderToStaticMarkup(<AreaSummaryPanel summary={summary} publicMode />),
      renderToStaticMarkup(<TargetTasks summary={{ ...summary, unknowns: [summary.unknowns[0]] }} publicMode />),
    ].join("\n");
    const initialText = markup
      .replace(/<details[\s\S]*?<\/details>/g, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ");

    for (const prohibited of [
      "KNOWN", "UNKNOWN", "EVIDENCE", "TARGET", "VERIFICATION", "Finding",
      " task ", "coverage", "version", "rule", "object", "analysis run",
      "最新", "リアルタイム", "おすすめ", "推奨", "最適", "AIが選定",
      "危険度", "安全性を判定",
    ]) {
      expect(initialText).not.toContain(prohibited);
    }
    expect(initialText).not.toContain("bldg-real-id");
    expect(initialText).not.toContain("official-test");
  });

  it("requires UX value in addition to technical 3D eligibility", () => {
    const roadDecision = contextual3dEligibility(
      summary,
      { ...target, object_type: "road", source_object_id: "tran-real-id" },
      2025,
      true,
    );
    expect(roadDecision).toMatchObject({
      eligible: false,
      technicalEligible: true,
      uxValuable: false,
      reasonCode: "single_road_point_2d_sufficient",
    });

    const buildingDecision = contextual3dEligibility(summary, target, 2025, true);
    expect(buildingDecision).toMatchObject({
      eligible: false,
      technicalEligible: true,
      uxValuable: false,
      reasonCode: "single_building_current_use_2d_sufficient",
    });

    expect(contextual3dEligibility(summary, { ...target, scope: "mesh", object_type: "mesh" }, 2025, true).technicalEligible).toBe(false);
    expect(contextual3dEligibility(summary, { ...target, scope: "facility", object_type: "facility" }, 2025, true).technicalEligible).toBe(false);
    expect(contextual3dEligibility(summary, { ...target, source_object_id: "unresolved-road" }, 2025, true).technicalEligible).toBe(false);
    expect(contextual3dEligibility({ ...summary, content_sha256: null }, target, 2025, true).technicalEligible).toBe(false);
    expect(contextual3dEligibility(summary, target, undefined, true).technicalEligible).toBe(false);
    expect(contextual3dEligibility(summary, target, 2025, false).technicalEligible).toBe(false);
  });

  it("keeps a single secondary header action", () => {
    const html = renderToStaticMarkup(<PublicHeader onRestart={() => undefined} onOpenAdvanced={() => undefined} />);
    expect(html).toContain("CITY GAP");
    expect(html).toContain("舞鶴市");
    expect(html).toContain("詳細分析");
    expect((html.match(/<button/g) ?? [])).toHaveLength(2);
  });

  it("keeps the Urban Section out of the Public first-run contract", () => {
    expect(PUBLIC_URBAN_SECTION_DECISION).toEqual({
      decision: "advanced_only",
      renderInFirstRun: false,
      reason: "The Public Area questions are answered by the 2D Area, story, and exact target geometry.",
    });
  });
});
