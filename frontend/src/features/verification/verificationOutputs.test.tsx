import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { investigationFixture } from "../investigation/investigationFixture";
import { buildInvestigationWorkspace } from "../investigation/investigationModel";
import { buildPublicVerificationLoop } from "./verificationModel";
import {
  UncertaintyPanel,
  VerificationTargetsPanel,
  VerificationTasksPanel,
} from "./VerificationPanels";

describe("M3 public verification outputs", () => {
  const candidate = buildInvestigationWorkspace(investigationFixture()).candidates[0];
  const loop = buildPublicVerificationLoop(candidate);

  it("shows four decision-relevant unknowns and their importance", () => {
    const html = renderToStaticMarkup(<UncertaintyPanel loop={loop} />);
    expect((html.match(/data-uncertainty-kind=/g) ?? [])).toHaveLength(4);
    expect(html).toContain("この場所について、まだ分からないこと");
    expect((html.match(/なぜ重要？/g) ?? [])).toHaveLength(4);
    expect(html).toContain("最大4件。分析だけで確認済みにはしません");
  });

  it("renders tracked road, building, facility, and mesh targets", () => {
    const html = renderToStaticMarkup(<VerificationTargetsPanel loop={loop} />);
    for (const id of [
      "bus-071",
      "tran_05dbefba-6a77-40ea-88ac-a568a63a2f05-0",
      "medical-105",
      "bldg_00962182-17d0-4fde-8970-784dd489dcf5",
      "533513314",
    ]) expect(html).toContain(id);
    expect(html).toContain("mesh-533513314-accessibility-gap");
    expect(html).toContain("citygap-field-verification@1.0.0");
  });

  it("ends with four unverified tasks and no evidence controls", () => {
    const html = renderToStaticMarkup(<VerificationTasksPanel loop={loop} />);
    expect((html.match(/data-verification-task-id=/g) ?? [])).toHaveLength(4);
    expect((html.match(/<b>未確認<\/b>/g) ?? [])).toHaveLength(4);
    expect(html).toContain("ここでは未確認のまま停止します");
    expect(html).toContain("AWAITING_HUMAN_TEST");
    expect(html).toContain("AWAITING_MUNICIPAL_REVIEW");
    expect(html).not.toMatch(/<(input|textarea|select)\b/);
  });
});
