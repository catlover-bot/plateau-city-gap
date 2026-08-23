import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import evidenceJson from "../../public/data/evidence.json";
import interventionsJson from "../../public/data/intervention_scenarios.json";
import robustnessJson from "../../public/data/robustness.json";
import type { EvidenceData, InterventionData, MeshMetrics, RobustnessData } from "../types";
import { DetailPanel } from "./DetailPanel";
import { EvidenceModal } from "./EvidenceModal";
import { ScenarioPanel } from "./ScenarioPanel";

const interventions = interventionsJson as unknown as InterventionData;
const robustness = robustnessJson as unknown as RobustnessData;
const evidence = evidenceJson as unknown as EvidenceData;
const noop = () => undefined;

function renderPlan(mode: "overall" | "fairness" | "robust", count: "1" | "2" | "3", phase: "before" | "after") {
  const plan = interventions.plans[mode][count];
  const top = plan.top_improvements[0];
  const mesh: MeshMetrics = { mesh_code: top.mesh_code, area_label: top.area_label };
  return renderToStaticMarkup(
    <ScenarioPanel
      interventions={interventions}
      plan={plan}
      mode={mode}
      siteCount={Number(count) as 1 | 2 | 3}
      mapPhase={phase}
      selectedMesh={mesh}
      freeResult={null}
      placementMode={false}
      onModeChange={noop}
      onSiteCountChange={noop}
      onMapPhaseChange={noop}
      onSelectMesh={noop}
      onStartPlacement={noop}
      onResetFree={noop}
      onEvidence={noop}
    />
  );
}

describe("Decision Studio UI", () => {
  it("shows robustness as scenario frequency, never probability", () => {
    const candidate = robustness.top_candidates[0];
    const html = renderToStaticMarkup(
      <DetailPanel
        mesh={{ mesh_code: candidate.mesh_code, area_label: candidate.area_label }}
        robustness={candidate}
      />
    );
    expect(html).toContain(`${candidate.top10_frequency}条件`);
    expect(html).toContain("確率や信頼度ではありません");
    expect(html).not.toContain("95%信頼");
  });

  it("renders 1/2/3-site plans with their actual number of sites", () => {
    for (const count of ["1", "2", "3"] as const) {
      const html = renderPlan("overall", count, "before");
      expect(html.match(/PLATEAU道路面代表点/g)).toHaveLength(Number(count));
      expect(html).toContain(`${count}地点`);
      if (count === "1") expect(html).toContain("1地点を4つの目的で比較");
    }
  });

  it("switches objective content and exposes fairness trade-off", () => {
    const overall = renderPlan("overall", "2", "after");
    const fairness = renderPlan("fairness", "2", "after");
    const robust = renderPlan("robust", "2", "after");
    expect(overall).toContain("全体改善");
    expect(fairness).toContain("取り残し重視");
    expect(fairness).toContain("trade-off");
    expect(robust).toContain("頑健候補");
    expect(new Set([overall, fairness, robust]).size).toBe(3);
  });

  it("shows before/after values and avoids policy recommendation wording", () => {
    const html = renderPlan("overall", "1", "after");
    expect(html).toContain("施策前");
    expect(html).toContain("施策後");
    expect(html).toContain("BEFORE");
    expect(html).toContain("AFTER");
    expect(html).toContain("配置候補");
    expect(html).not.toContain("設置すべき場所");
    expect(html).not.toContain("政策の正解です");
  });

  it("renders the deterministic Evidence Chain", () => {
    const plan = interventions.plans.overall["1"];
    const html = renderToStaticMarkup(
      <EvidenceModal open evidence={evidence} plan={plan} onClose={noop} />
    );
    expect(html).toContain("EVIDENCE CHAIN");
    expect(html).toContain("国土数値情報 P11 2022");
    expect(html).toContain(evidence.rank_one.transport.value_m.toFixed(9));
    expect(html).toContain(plan.impact.total_score_c_reduction.toFixed(9));
  });
});
