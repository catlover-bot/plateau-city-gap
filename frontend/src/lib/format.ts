import type { MeshMetrics } from "../types";

export function finiteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function formatInteger(value: unknown, suffix = "人"): string {
  const number = finiteNumber(value);
  return number === null ? "—" : `${Math.round(number).toLocaleString("ja-JP")}${suffix}`;
}

export function formatDistance(value: unknown): string {
  const metres = finiteNumber(value);
  if (metres === null || metres < 0) return "—";
  if (metres < 1000) return `${Math.round(metres).toLocaleString("ja-JP")} m`;
  return `${(metres / 1000).toFixed(2)} km`;
}

export function formatRatio(value: unknown): string {
  const ratio = finiteNumber(value);
  if (ratio === null) return "—";
  const percent = Math.abs(ratio) <= 1 ? ratio * 100 : ratio;
  return `${percent.toFixed(1)}%`;
}

export function formatScore(value: unknown): string {
  const score = finiteNumber(value);
  return score === null ? "—" : score.toFixed(3);
}

export function formatPercentile(value: unknown): string {
  const percentile = finiteNumber(value);
  if (percentile === null) return "—";
  const normalized = Math.min(1, Math.max(0, percentile > 1 ? percentile / 100 : percentile));
  return `${Math.round(normalized * 100)} パーセンタイル`;
}

export function percentileValue(value: unknown): number | null {
  const percentile = finiteNumber(value);
  if (percentile === null) return null;
  return Math.min(1, Math.max(0, percentile > 1 ? percentile / 100 : percentile));
}

export function textValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function isTop10Rank(value: unknown): boolean {
  const rank = finiteNumber(value);
  return rank !== null && rank >= 1 && rank <= 10;
}

export function comparisonMeshScope(count: unknown): string {
  const numericCount = finiteNumber(count);
  return numericCount !== null && numericCount >= 0
    ? `秘匿・合算影響のない${Math.round(numericCount).toLocaleString("ja-JP")}メッシュ`
    : "秘匿・合算影響のない比較対象メッシュ";
}

export function makeWhyCityGap(mesh: MeshMetrics, comparisonMeshCount?: unknown): string[] {
  const lines: string[] = [];
  const elderly = finiteNumber(mesh.elderly_population);
  const transport = finiteNumber(mesh.nearest_public_transport_distance_m);
  const medical = finiteNumber(mesh.nearest_medical_distance_m);
  const transportPercentile = percentileValue(mesh.transport_distance_percentile);
  const medicalPercentile = percentileValue(mesh.medical_distance_percentile);

  if (elderly !== null) {
    lines.push(`2020年国勢調査では、65歳以上人口が${Math.round(elderly).toLocaleString("ja-JP")}人です。`);
  }
  if (transport !== null && medical !== null) {
    lines.push(`メッシュ中心から最寄りの公共交通まで${formatDistance(transport)}、医療機関まで${formatDistance(medical)}あります。`);
  } else if (transport !== null) {
    lines.push(`メッシュ中心から最寄りの公共交通まで${formatDistance(transport)}あります。`);
  } else if (medical !== null) {
    lines.push(`メッシュ中心から最寄りの医療機関まで${formatDistance(medical)}あります。`);
  }
  if (transportPercentile !== null) {
    lines.push(`公共交通距離は${comparisonMeshScope(comparisonMeshCount)}の${Math.round(transportPercentile * 100)}パーセンタイル（距離が長い側）です。`);
  }
  if (medicalPercentile !== null) {
    lines.push(`医療距離は${comparisonMeshScope(comparisonMeshCount)}の${Math.round(medicalPercentile * 100)}パーセンタイル（距離が長い側）です。`);
  }
  return lines;
}
