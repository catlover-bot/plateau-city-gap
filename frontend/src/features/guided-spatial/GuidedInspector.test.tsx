import type { ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { AppData } from "../../types";
import { GuidedInspector } from "./GuidedInspector";
import { GUIDED_CHECKS } from "./guidedContent";

const empty = { type: "FeatureCollection" as const, features: [] };
function props(overrides: Partial<ComponentProps<typeof GuidedInspector>> = {}): ComponentProps<typeof GuidedInspector> {
  return {
    story: "understand", data: { meshes: empty } as unknown as AppData,
    selectedAreaId: "533513314", areaLabel: "常団地前周辺",
    properties: { population: 471, elderly_population: 200 },
    shortlisted: [], hoveredAreaId: null, catalogItem: null, catalogError: null,
    contextStatus: "ready", contextError: null, context: null,
    activeSectionData: null, sectionError: null, selectedObject: null,
    threeDActive: true, targetChoices: [], target: undefined,
    titleRef: { current: null }, onStoryChange: vi.fn(), onSelectArea: vi.fn(),
    onAreaHover: vi.fn(), onTargetChange: vi.fn(), onOpenAdvanced: vi.fn(), ...overrides,
  };
}

describe("Guided readable copy and source scope", () => {
  it("renders the concise Area heading and unchanged next action", () => {
    const html = renderToStaticMarkup(<GuidedInspector {...props({ story: "find" })} />);
    expect(html).toContain('id="guided-story-title" tabindex="-1">地域を選ぶ</h1>');
    expect(html).toContain("地図または一覧から、調べる地域を選べます。");
    expect(html).toContain("街の形を見る</button>");
  });

  it("keeps the exact building checklist unconfirmed under the new heading and Advanced action", () => {
    const target = { key: "building:test-building", kind: "building" as const, label: "テスト建物", reason: "形状だけでは入口を確認できません。", geometry: empty, resolution: "exact" as const, checks: GUIDED_CHECKS.building };
    const html = renderToStaticMarkup(<GuidedInspector {...props({ story: "verify", target, targetChoices: [target] })} />);
    expect(html).toContain('id="guided-story-title" tabindex="-1">現地で確認すること</h1>');
    expect(html).toContain("詳細分析を開く</button>");
    expect(html).toContain("3件・未確認");
    expect(html).toContain("回答や確認結果はまだありません。");
    for (const [, label, reason] of GUIDED_CHECKS.building) {
      expect(html).toContain(label);
      expect(html).toContain(reason);
    }
    expect(html).not.toContain(GUIDED_CHECKS.road[0][1]);
  });

  it("labels population as an Area aggregate separate from selected building attributes", () => {
    const selectedObject = { type: "building" as const, id: "test-building", city: "maizuru" as const, urbanState: "2025" as const, properties: { usage: "共同住宅", measured_height_m: 18, storeys_above_ground: 5, storeys_below_ground: 0 } };
    const html = renderToStaticMarkup(<GuidedInspector {...props({ selectedObject })} />);
    expect(html).toContain("この地域の人口 471人");
    expect(html).toContain("うち65歳以上 200人（国勢調査2020・500m集計）");
    expect(html).toContain("範囲と交差する2D地物の集計。3D画面内の描画数ではありません。");
    const attributes = html.split('class="guided-object-attributes"')[1].split("</section>")[0];
    expect(attributes).toContain("建物高さ</dt><dd>18m");
    expect(attributes).not.toContain("471人");
    expect(attributes).not.toContain("200人");
  });

  it.each([null, undefined, ""])("does not turn missing numeric attributes (%s) into zero", (missing) => {
    const selectedObject = { type: "building" as const, id: "test-building", city: "maizuru" as const, urbanState: "2025" as const, properties: { measured_height_m: missing, storeys_above_ground: missing, storeys_below_ground: missing } };
    const html = renderToStaticMarkup(<GuidedInspector {...props({ properties: { population: missing, elderly_population: missing }, selectedObject })} />);
    expect(html).toContain("この地域の人口 データなし");
    expect(html).toContain("うち65歳以上 データなし");
    expect(html).toContain("建物高さ</dt><dd>データなし");
    expect(html).toContain("地上階数</dt><dd>データなし");
    expect(html).toContain("地下階数</dt><dd>データなし");
    expect(html).not.toContain(">0m");
    expect(html).not.toContain(">0階");
  });
});
