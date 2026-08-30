import { describe, expect, it } from "vitest";
import {
  buildInvestigationWorkspace,
  createEditableChecks,
  createFieldSheet,
  createHumanCheck,
  isAutomaticConfirmationAllowed,
  preserveMunicipalReviewOutcome,
  toPublicFieldSheet,
} from "./investigationModel";
import { investigationFixture } from "./investigationFixture";

describe("field investigation candidate contract", () => {
  const workspace = buildInvestigationWorkspace(investigationFixture());
  const detailed = workspace.candidates[0];
  const screening = workspace.candidates[1];
  const dataGap = workspace.candidates[2];

  it("keeps three different candidate purposes instead of one mixed ranking", () => {
    expect(workspace.candidates).toHaveLength(3);
    expect(workspace.candidates.map((candidate) => candidate.type)).toEqual([
      "detailed_investigation",
      "screening",
      "data_gap",
    ]);
    expect(new Set(workspace.candidates.map((candidate) => candidate.type)).size).toBe(3);
    expect(workspace.selectionRuleVersion).toBe("maizuru-field-candidate-1.0.0");
    expect(workspace.fieldCheckRuleVersion).toBe("maizuru-field-check-1.0.0");
  });

  it("preserves the distinct real Maizuru denominators", () => {
    expect(detailed).toMatchObject({
      meshCode: "533513314",
      name: "常団地前周辺",
      rank: 23,
      rankingDenominator: 218,
      percentileDenominator: 286,
      cityIntersectingMeshCount: 495,
    });
    expect(detailed.rankingDenominator).not.toBe(detailed.percentileDenominator);
    expect(detailed.cityIntersectingMeshCount).not.toBe(detailed.rankingDenominator);
  });

  it("uses the actual detailed-example values and labels it as not top-ranked", () => {
    expect(detailed.population).toBe(471);
    expect(detailed.facts.map((fact) => fact.value)).toEqual([
      200,
      562.597,
      1.450547,
    ]);
    expect(detailed.reason).toContain("65歳以上人口200人");
    expect(detailed.reason).toContain("収録交通まで563m");
    expect(detailed.reason).toContain("収録医療まで1.45km");
    expect(detailed.whyThisExample).toContain("最上位候補ではありません");
    expect(detailed.plateau).toEqual({
      status: "verified",
      buildings: 296,
      roads: 135,
      terrain: "official_dem",
      message: "PLATEAU舞鶴市2025の建物・道路・DEMを確認できます。",
    });
  });

  it("represents missing PLATEAU coverage instead of inventing detail", () => {
    for (const candidate of [screening, dataGap]) {
      expect(candidate.plateau.status).toBe("unavailable");
      expect(candidate.plateau.buildings).toBeNull();
      expect(candidate.plateau.roads).toBeNull();
      expect(candidate.dataGaps.map((gap) => gap.id)).toContain("plateau_coverage");
      expect(
        candidate.fieldChecks
          .filter((check) => check.sourceGapIds.includes("plateau_coverage"))
          .every((check) => check.origin === "data_gap"),
      ).toBe(true);
    }
  });

  it("generates reasoned checks with traceable data-gap lineage", () => {
    expect(detailed.fieldChecks).toHaveLength(28);
    expect(new Set(detailed.fieldChecks.map((check) => check.category))).toEqual(
      new Set(["transport", "walking", "medical", "site", "local"]),
    );
    const gapIds = new Set(detailed.dataGaps.map((gap) => gap.id));
    for (const check of detailed.fieldChecks) {
      expect(check.label.length).toBeGreaterThan(0);
      expect(check.reason.length).toBeGreaterThan(0);
      expect(check.defaultPriority).toMatch(/high|medium|low/);
      for (const sourceGapId of check.sourceGapIds) {
        expect(gapIds.has(sourceGapId)).toBe(true);
      }
    }
    expect(detailed.fieldChecks.some((check) => check.origin === "analysis_assumption")).toBe(true);
    expect(detailed.fieldChecks.some((check) => check.origin === "plateau_context")).toBe(true);
  });

  it("starts every generated result unconfirmed and never auto-confirms it", () => {
    expect(createEditableChecks(detailed).every((check) => check.status === "unconfirmed")).toBe(true);
    expect(isAutomaticConfirmationAllowed()).toBe(false);
    expect(detailed.triageStatus).toBe("unreviewed");
    expect(detailed.municipalReviewStatus).toBe("AWAITING_MUNICIPAL_REVIEW");
    expect(createFieldSheet(detailed).candidateTriageStatus).toBe("unreviewed");
    expect(createFieldSheet(detailed).municipalReview.outcome).toBe("unreviewed");
    expect(workspace.valueHypotheses.every((hypothesis) => hypothesis.status === "AWAITING_MUNICIPAL_REVIEW")).toBe(true);
  });

  it("keeps human-added checks distinct from deterministic initial checks", () => {
    expect(createHumanCheck("自治会の送迎を確認", 1)).toMatchObject({
      id: "human-1",
      category: "local",
      origin: "human",
      status: "unconfirmed",
      sourceGapIds: [],
    });
    expect(() => createHumanCheck("  ", 2)).toThrow("入力してください");
  });

  it("strips internal field content from the public sheet", () => {
    const sheet = createFieldSheet(detailed, createEditableChecks(detailed), new Date("2026-08-30T00:00:00Z"));
    sheet.checks[0].assignee = "交通政策課";
    sheet.checks[0].dueDate = "2026-09-20";
    sheet.checks[0].note = "内部確認メモ";
    sheet.generalNote = "個人情報を含み得る内部記録";
    sheet.gps = { latitude: 35.4, longitude: 135.3 };
    sheet.photoReferences = ["internal-photo.jpg"];
    sheet.candidateTriageStatus = "additional_investigation";
    sheet.municipalReview.outcome = "existing_measures";
    sheet.municipalReview.originalResponse = "既存施策で対応済みとの原文回答";

    const publicText = JSON.stringify(toPublicFieldSheet(sheet));
    expect(publicText).not.toContain("交通政策課");
    expect(publicText).not.toContain("2026-09-20");
    expect(publicText).not.toContain("内部確認メモ");
    expect(publicText).not.toContain("個人情報");
    expect(publicText).not.toContain("35.4");
    expect(publicText).not.toContain("internal-photo");
    expect(publicText).not.toContain('"classification":"internal"');
    expect(publicText).not.toContain("candidateTriageStatus");
    expect(publicText).not.toContain("additional_investigation");
    expect(publicText).not.toContain("municipalReview");
    expect(publicText).not.toContain("existing_measures");
    expect(publicText).not.toContain("原文回答");
    expect(publicText).toContain("停留所");
  });

  it("preserves negative municipal outcomes without upgrading them", () => {
    expect(preserveMunicipalReviewOutcome("既存施策で対応済み")).toEqual({
      status: "CONTRADICTED",
      outcome: "既存施策で対応済み",
    });
    expect(preserveMunicipalReviewOutcome("一部部署では使える")).toEqual({
      status: "PARTIALLY_SUPPORTED",
      outcome: "一部部署では使える",
    });
  });

  it("does not turn candidate reasons into a policy recommendation", () => {
    const candidateOutput = workspace.candidates
      .map((candidate) => [candidate.reason, candidate.typeExplanation, candidate.whyThisExample].join(" "))
      .join(" ");
    expect(candidateOutput).not.toContain("実施すべき");
    expect(candidateOutput).not.toContain("政策推奨");
    expect(candidateOutput).not.toContain("危険地域");
  });
});
