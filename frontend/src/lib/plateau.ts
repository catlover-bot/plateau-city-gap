import type { PlateauMetadata } from "../types";

export type PlateauTop10Status = "verified-empty" | "reported" | "unavailable";

export interface PlateauCoverageSummary {
  distributionCount: number | null;
  top10Count: number | null;
  referenceCount: number | null;
  top10Status: PlateauTop10Status;
  referenceIncluded: boolean;
}

function nonNegativeInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : null;
}

export function summarizePlateauCoverage(
  metadata: PlateauMetadata | null,
): PlateauCoverageSummary {
  const buildingLayer = metadata?.building_layer;
  const referenceLayer = metadata?.reference_layer;
  const distributionCount = nonNegativeInteger(
    buildingLayer?.source_distribution_unique_buildings,
  );
  const top10Count = nonNegativeInteger(
    buildingLayer?.records ?? buildingLayer?.top10_buildings,
  );
  const verifiedEmpty =
    buildingLayer?.status === "verified_empty_for_top10" && top10Count === 0;

  return {
    distributionCount,
    top10Count,
    referenceCount: nonNegativeInteger(referenceLayer?.records),
    top10Status: verifiedEmpty
      ? "verified-empty"
      : top10Count === null
        ? "unavailable"
        : "reported",
    referenceIncluded: referenceLayer?.status === "included",
  };
}

export function formatBuildingCount(count: number | null): string {
  return count === null ? "棟数を確認できません" : `${count.toLocaleString("ja-JP")}棟`;
}

export function top10CoverageLabel(coverage: PlateauCoverageSummary): string {
  if (coverage.top10Status === "unavailable") return "確認状況を取得できません";
  const count = formatBuildingCount(coverage.top10Count);
  return coverage.top10Status === "verified-empty"
    ? `${count}（公式データ検証済み）`
    : `${count}（メタデータ記載）`;
}

export function top10CoverageSentence(coverage: PlateauCoverageSummary): string {
  if (coverage.top10Status === "verified-empty") {
    return `CITY GAP Top 10内は公式データ検証で${formatBuildingCount(coverage.top10Count)}でした。`;
  }
  if (coverage.top10Status === "reported") {
    return `CITY GAP Top 10内は${formatBuildingCount(coverage.top10Count)}とメタデータに記載されています。`;
  }
  return "CITY GAP Top 10内のPLATEAU建物は、確認状況を取得できません。";
}

export function referenceCoverageSentence(coverage: PlateauCoverageSummary): string {
  if (!coverage.referenceIncluded) {
    return "3D Deep Dive subsetの収録状況はメタデータから確認できません。";
  }
  return `PLATEAU-covered候補から抽出した公式3D Tiles subset（${formatBuildingCount(coverage.referenceCount)}）を表示します。`;
}
