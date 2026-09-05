import type { AreaTarget, InvestigationAreaSummary } from "./areaTypes";

export const PUBLIC_LANDING_COPY = {
  heading: "舞鶴を、地図で調べる。",
  subcopy: "場所と範囲を選び、人口・建物・交通などを確認します。",
  primaryCta: "地図で場所を調べる",
} as const;

export const PUBLIC_RADIUS_OPTIONS = [
  { value: 500, label: "500m" },
  { value: 800, label: "800m" },
  { value: 1000, label: "1km" },
] as const;

export const PUBLIC_URBAN_SECTION_DECISION = {
  decision: "advanced_only",
  renderInFirstRun: false,
  reason: "The Public Area questions are answered by the 2D Area, story, and exact target geometry.",
} as const;

export function radiusExplanation(radius: number): string {
  if (radius === 500) return "500mは、国土交通省の都市構造評価で高齢者徒歩圏の目安として使われる距離です。実際の徒歩時間到達圏を示すものではありません。";
  if (radius === 800) return "800mは、国土交通省の都市構造評価で一般的な徒歩圏の目安として使われる距離です。実際の徒歩10分到達圏を示すものではありません。";
  if (radius === 1000) return "1kmは周辺を広く確認するための半径です。徒歩圏を示すものではありません。";
  return `${radius}mは指定した半径による分析範囲です。実際の移動可能範囲を示すものではありません。`;
}

export interface Contextual3dDecision {
  eligible: boolean;
  technicalEligible: boolean;
  uxValuable: boolean;
  reasonCode: string;
  reason: string;
}

export function contextual3dEligibility(
  summary: InvestigationAreaSummary,
  target: AreaTarget,
  plateauYear: number | undefined,
  webgl: boolean,
): Contextual3dDecision {
  if (!webgl) return { eligible: false, technicalEligible: false, uxValuable: false, reasonCode: "webgl_unavailable", reason: "この端末では3D表示を利用できません。" };
  if (target.scope !== "plateau_object") return { eligible: false, technicalEligible: false, uxValuable: false, reasonCode: "not_plateau_object", reason: "この確認場所は2D地図で表示します。" };
  if (target.object_type !== "building" && target.object_type !== "road") return { eligible: false, technicalEligible: false, uxValuable: false, reasonCode: "unsupported_object_type", reason: "この対象種別は2D地図で表示します。" };
  if (!summary.content_sha256 || !target.source_object_id || target.source_object_id.startsWith("unresolved")) {
    return { eligible: false, technicalEligible: false, uxValuable: false, reasonCode: "unresolved_object", reason: "確認済みの対象情報がないため3Dを表示しません。" };
  }
  if (!target.dataset.startsWith("PLATEAU舞鶴市") || plateauYear === undefined) {
    return { eligible: false, technicalEligible: false, uxValuable: false, reasonCode: "dataset_mismatch", reason: "現在のPLATEAUデータと対応を確認できないため3Dを表示しません。" };
  }

  if (target.object_type === "road") {
    return {
      eligible: false,
      technicalEligible: true,
      uxValuable: false,
      reasonCode: "single_road_point_2d_sufficient",
      reason: "この確認は道路上の一点が対象で、2D地図の方が場所を明確に確認できます。3Dを開いても判断材料が増えないため表示しません。",
    };
  }

  return {
    eligible: false,
    technicalEligible: true,
    uxValuable: false,
    reasonCode: "single_building_current_use_2d_sufficient",
    reason: "この確認は単一建物の現在利用が中心で、3Dを開いても判断材料が増えないため表示しません。",
  };
}
