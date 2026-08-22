import { describe, expect, it } from "vitest";
import {
  comparisonMeshScope,
  formatDistance,
  formatInteger,
  formatPercentile,
  formatRatio,
  formatScore,
  isTop10Rank,
  makeWhyCityGap
} from "./format";

describe("metric formatting", () => {
  it("formats real analysis metrics for Japanese display", () => {
    expect(formatInteger(56)).toBe("56人");
    expect(formatDistance(2321.6556)).toBe("2.32 km");
    expect(formatDistance(740)).toBe("740 m");
    expect(formatRatio(0.615384)).toBe("61.5%");
    expect(formatScore(0.498135)).toBe("0.498");
    expect(formatPercentile(0.90909)).toBe("91 パーセンタイル");
  });

  it("never invents missing values", () => {
    expect(formatInteger(null)).toBe("—");
    expect(formatDistance(undefined)).toBe("—");
    expect(formatRatio(Number.NaN)).toBe("—");
    expect(formatScore("unknown")).toBe("—");
    expect(makeWhyCityGap({ mesh_code: "missing" })).toEqual([]);
    expect(comparisonMeshScope(undefined)).toBe("秘匿・合算影響のない比較対象メッシュ");
    expect(isTop10Rank(1)).toBe(true);
    expect(isTop10Rank(10)).toBe(true);
    expect(isTop10Rank(11)).toBe(false);
    expect(isTop10Rank(null)).toBe(false);
  });
});

describe("deterministic WHY CITY GAP copy", () => {
  it("derives copy from values and percentiles", () => {
    const lines = makeWhyCityGap({
      mesh_code: "533512753",
      elderly_population: 56,
      nearest_public_transport_distance_m: 2321.6556,
      nearest_medical_distance_m: 3316.8502,
      transport_distance_percentile: 0.90909,
      medical_distance_percentile: 0.87062
    }, 286);
    expect(lines.join(" ")).toContain("65歳以上人口が56人");
    expect(lines.join(" ")).toContain("2.32 km");
    expect(lines.join(" ")).toContain("91パーセンタイル");
    expect(lines.join(" ")).toContain("87パーセンタイル");
    expect(lines.join(" ")).toContain("秘匿・合算影響のない286メッシュ");
  });
});
