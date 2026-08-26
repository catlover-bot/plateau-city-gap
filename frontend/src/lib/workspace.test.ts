import { describe, expect, it } from "vitest";
import {
  canTransitionScenario,
  MAX_SCENARIO_COMPARISON,
  toggleScenarioComparison,
  transitionScenario
} from "./workspace";

describe("municipal workspace controls", () => {
  it("limits comparison to three distinct scenarios", () => {
    let selected: string[] = [];
    for (const id of ["a", "b", "c", "d"]) selected = toggleScenarioComparison(selected, id);
    expect(selected).toEqual(["a", "b", "c"]);
    expect(selected).toHaveLength(MAX_SCENARIO_COMPARISON);
    expect(toggleScenarioComparison(selected, "b")).toEqual(["a", "c"]);
  });

  it("prevents draft from skipping review and field check", () => {
    expect(canTransitionScenario("draft", "reviewed")).toBe(false);
    expect(() => transitionScenario("draft", "reviewed")).toThrow();
    expect(transitionScenario("draft", "under_review")).toBe("under_review");
    expect(transitionScenario("under_review", "field_check_required")).toBe(
      "field_check_required"
    );
    expect(transitionScenario("field_check_required", "reviewed")).toBe("reviewed");
  });
});
