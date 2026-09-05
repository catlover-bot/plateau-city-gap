import type {
  HumanTriageStatus,
  MunicipalReviewOutcome,
} from "./investigationTypes";

export const CANDIDATE_SELECTION_RULE_VERSION = "maizuru-field-candidate-1.0.0";
export const FIELD_CHECK_RULE_VERSION = "maizuru-field-check-1.0.0";
export const MUNICIPAL_REVIEW_STATUS = "AWAITING_MUNICIPAL_REVIEW" as const;
export const BASELINE_STATUS = "BASELINE_NOT_COLLECTED" as const;

export const HUMAN_TRIAGE_LABELS: Record<HumanTriageStatus, string> = {
  unreviewed: "未確認",
  additional_investigation: "追加調査",
  check_existing_measures: "既存施策を確認",
  data_insufficient: "データ不足",
  field_check_in_progress: "現地確認中",
  confirmed: "確認済み",
  out_of_scope: "対象外",
};

export function isHumanTriageStatus(
  value: unknown,
): value is HumanTriageStatus {
  return (
    typeof value === "string" &&
    Object.prototype.hasOwnProperty.call(HUMAN_TRIAGE_LABELS, value)
  );
}

export const MUNICIPAL_REVIEW_OUTCOME_LABELS: Record<
  MunicipalReviewOutcome,
  string
> = {
  unreviewed: "未確認",
  worth_checking: "確認する価値がある",
  partially_useful: "一部有用",
  existing_measures: "既存施策で対応済み",
  local_mismatch: "地域事情と異なる",
  data_insufficient: "データ不足",
  out_of_scope: "対象外",
};

export function isMunicipalReviewOutcome(
  value: unknown,
): value is MunicipalReviewOutcome {
  return (
    typeof value === "string" &&
    Object.prototype.hasOwnProperty.call(MUNICIPAL_REVIEW_OUTCOME_LABELS, value)
  );
}
