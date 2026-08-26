export const MAX_SCENARIO_COMPARISON = 3;

export type ScenarioLifecycleStatus =
  | "draft"
  | "under_review"
  | "field_check_required"
  | "reviewed"
  | "archived";

const NEXT_STATUS: Partial<Record<ScenarioLifecycleStatus, ScenarioLifecycleStatus[]>> = {
  draft: ["under_review", "archived"],
  under_review: ["draft", "field_check_required", "archived"],
  field_check_required: ["under_review", "reviewed", "archived"],
  reviewed: ["archived"],
  archived: []
};

export function toggleScenarioComparison(current: string[], id: string): string[] {
  if (current.includes(id)) return current.filter((value) => value !== id);
  if (current.length >= MAX_SCENARIO_COMPARISON) return current;
  return [...current, id];
}

export function canTransitionScenario(
  current: ScenarioLifecycleStatus,
  next: ScenarioLifecycleStatus
): boolean {
  return NEXT_STATUS[current]?.includes(next) ?? false;
}

export function transitionScenario(
  current: ScenarioLifecycleStatus,
  next: ScenarioLifecycleStatus
): ScenarioLifecycleStatus {
  if (!canTransitionScenario(current, next)) {
    throw new Error(`Invalid scenario lifecycle transition: ${current} -> ${next}`);
  }
  return next;
}
