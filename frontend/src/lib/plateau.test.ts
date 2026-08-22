import { describe, expect, it } from "vitest";

import {
  formatBuildingCount,
  referenceCoverageSentence,
  summarizePlateauCoverage,
  top10CoverageLabel,
  top10CoverageSentence,
} from "./plateau";

describe("PLATEAU coverage copy", () => {
  it("derives verified counts from loaded metadata", () => {
    const coverage = summarizePlateauCoverage({
      building_layer: {
        status: "verified_empty_for_top10",
        records: 0,
        source_distribution_unique_buildings: 44_640,
      },
      reference_layer: { status: "included", records: 856 },
    });

    expect(coverage).toEqual({
      distributionCount: 44_640,
      top10Count: 0,
      referenceCount: 856,
      top10Status: "verified-empty",
      referenceIncluded: true,
    });
    expect(top10CoverageLabel(coverage)).toBe("0棟（公式データ検証済み）");
    expect(top10CoverageSentence(coverage)).toContain("公式データ検証で0棟");
    expect(referenceCoverageSentence(coverage)).toContain("856棟");
  });

  it("uses honest unavailable wording instead of fallback counts", () => {
    const coverage = summarizePlateauCoverage(null);

    expect(formatBuildingCount(coverage.distributionCount)).toBe("棟数を確認できません");
    expect(top10CoverageLabel(coverage)).toBe("確認状況を取得できません");
    expect(top10CoverageSentence(coverage)).toContain("確認状況を取得できません");
    expect(referenceCoverageSentence(coverage)).toContain("収録状況はメタデータから確認できません");
  });

  it("does not call an unverified zero count verified", () => {
    const coverage = summarizePlateauCoverage({ building_layer: { records: 0 } });

    expect(coverage.top10Status).toBe("reported");
    expect(top10CoverageLabel(coverage)).toBe("0棟（メタデータ記載）");
  });
});
