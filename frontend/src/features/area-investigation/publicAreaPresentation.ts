import type { AreaTarget, InvestigationAreaSummary } from "./areaTypes";

export const PUBLIC_LANDING_COPY = {
  heading: "気になる場所を、地図とデータで確かめる。",
  subcopy: "場所と範囲を選ぶと、人口・年齢、建物の使われ方、事業所、都市計画、交通をまとめて確認できます。データだけでは判断できない点も整理します。",
  primaryCta: "地図で場所を調べる",
} as const;

export const PUBLIC_RADIUS_OPTIONS = [
  { value: 500, label: "500m" },
  { value: 800, label: "800m" },
  { value: 1000, label: "1km" },
] as const;

export function radiusExplanation(radius: number): string {
  if (radius === 500) return "500mは、国土交通省の都市構造評価で高齢者徒歩圏の目安として使われる距離です。実際の徒歩時間到達圏を示すものではありません。";
  if (radius === 800) return "800mは、国土交通省の都市構造評価で一般的な徒歩圏の目安として使われる距離です。実際の徒歩10分到達圏を示すものではありません。";
  if (radius === 1000) return "1kmは周辺を広く確認するための半径です。徒歩圏を示すものではありません。";
  return `${radius}mは指定した半径による分析範囲です。実際の移動可能範囲を示すものではありません。`;
}

export function contextual3dEligibility(
  summary: InvestigationAreaSummary,
  target: AreaTarget,
  plateauYear: number | undefined,
  webgl: boolean,
): { eligible: boolean; reason: string } {
  if (!webgl) return { eligible: false, reason: "この端末では3D表示を利用できません。" };
  if (target.scope !== "plateau_object") return { eligible: false, reason: "この確認場所は2D地図で表示します。" };
  if (target.object_type !== "building" && target.object_type !== "road") return { eligible: false, reason: "この対象種別は2D地図で表示します。" };
  if (!summary.content_sha256 || !target.source_object_id || target.source_object_id.startsWith("unresolved")) {
    return { eligible: false, reason: "確認済みの対象情報がないため3Dを表示しません。" };
  }
  if (!target.dataset.startsWith("PLATEAU舞鶴市") || plateauYear === undefined) {
    return { eligible: false, reason: "現在のPLATEAUデータと対応を確認できないため3Dを表示しません。" };
  }
  return { eligible: true, reason: "同じ調査範囲に結び付いたPLATEAU対象を3Dで確認できます。" };
}
