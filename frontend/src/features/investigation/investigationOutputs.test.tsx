import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CandidateBrief, CandidateShortlist } from "./CandidatePanels";
import { FieldChecklist, InvestigationSummary } from "./FieldPanels";
import { InvestigationLanding } from "./ValueLanding";
import {
  buildInvestigationWorkspace,
  createFieldSheet,
} from "./investigationModel";
import { investigationFixture } from "./investigationFixture";

describe("public field-investigation outputs", () => {
  const workspace = buildInvestigationWorkspace(investigationFixture());
  const candidate = workspace.candidates[0];

  it("leads with one primary landing action and an actual output preview", () => {
    const html = renderToStaticMarkup(
      <InvestigationLanding
        workspace={workspace}
        onStart={() => undefined}
        onRestart={() => undefined}
      />,
    );

    expect(html).toContain("地図だけでは分からないことを、");
    expect(html).toContain("地域公共交通計画・デマンド交通・交通空白地域等を検討する自治体職員向け");
    expect(html).toContain("地図から確認候補を選ぶ");
    expect(html).toContain("不明点 → PLATEAU対象 → 未確認タスク");
    expect(html).toContain("写真・GPS・回答・自治体reviewのdemo値はありません");
    expect(html).toContain("常団地前周辺");
    expect(html).toContain("296棟");
    expect(html).toContain("135面");
    expect((html.match(/class="investigation-primary"/g) ?? [])).toHaveLength(1);
    expect((html.match(/class="investigation-secondary"/g) ?? [])).toHaveLength(1);
  });

  it("renders three explicit candidate purposes without a recommendation label", () => {
    const html = renderToStaticMarkup(
      <CandidateShortlist
        workspace={workspace}
        selectedId={candidate.id}
        onSelect={() => undefined}
      />,
    );

    expect((html.match(/role="radio"/g) ?? [])).toHaveLength(3);
    expect(html).toContain("分析上の候補");
    expect(html).toContain("詳細調査例");
    expect(html).toContain("データ確認候補");
    expect(html).toContain("政策順位ではありません");
    expect(html).not.toContain("推奨候補");
  });

  it("renders all human triage states without auto-confirming the candidate", () => {
    const html = renderToStaticMarkup(
      <CandidateBrief
        candidate={candidate}
        triageStatus="unreviewed"
        onTriageChange={() => undefined}
      />,
    );

    for (const label of [
      "未確認",
      "追加調査",
      "既存施策を確認",
      "データ不足",
      "現地確認中",
      "確認済み",
      "対象外",
    ]) expect(html).toContain(label);
    expect(html).toContain("分析だけで確認済みにはなりません");
  });

  it("shows why each initial field check exists", () => {
    const html = renderToStaticMarkup(<FieldChecklist candidate={candidate} />);
    expect(html).toContain("不足情報 → 現地確認項目");
    expect(html).toContain("確認する理由");
    expect(html).toContain("初期項目は自動生成");
    expect(html).toContain("確認結果は自動入力しません");
  });

  it("keeps review, baseline and policy boundaries in the final summary", () => {
    const html = renderToStaticMarkup(
      <InvestigationSummary
        candidate={candidate}
        onSheetChange={() => undefined}
        sheet={createFieldSheet(candidate, undefined, new Date("2026-08-30T00:00:00Z"))}
      />,
    );
    expect(html).toContain("庁内共有用調査サマリー");
    expect(html).toContain("AWAITING_MUNICIPAL_REVIEW");
    expect(html).toContain("BASELINE_NOT_COLLECTED");
    expect(html).toContain("実自治体からの回答はまだありません");
    expect(html).toContain("政策推奨");
    expect(html).toContain("直線距離は徒歩距離・所要時間ではありません");
  });
});
