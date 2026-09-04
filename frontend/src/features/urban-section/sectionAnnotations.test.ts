import { describe, expect, it } from "vitest";
import {
  deduplicateNamedRoads,
  estimateSectionTextWidth,
  layoutSectionAnnotations,
  selectDistributedAnnotations,
  type SectionRoadAnnotationInput,
} from "./sectionAnnotations";

const roads: SectionRoadAnnotationInput[] = [
  { id: "a", label: "東椿線", distanceM: 44, offsetDistanceM: 0 },
  { id: "unknown", label: "名称不明の道路", distanceM: 51, offsetDistanceM: 0 },
  { id: "b", label: "椿２号線", distanceM: 133, offsetDistanceM: 0 },
  { id: "c", label: "椿川通線", distanceM: 162, offsetDistanceM: 0 },
  { id: "c-copy", label: "椿川通線", distanceM: 190, offsetDistanceM: 2 },
  { id: "d", label: "青山一号通線", distanceM: 278, offsetDistanceM: 0 },
  { id: "e", label: "京月二号線", distanceM: 354, offsetDistanceM: 0 },
  { id: "f", label: "京月通線", distanceM: 429, offsetDistanceM: 0 },
];

describe("section annotation layout", () => {
  it("deduplicates named roads and excludes unknown labels", () => {
    const result = deduplicateNamedRoads(roads);
    expect(result.map((road) => road.id)).not.toContain("unknown");
    expect(result.filter((road) => road.label === "椿川通線")).toHaveLength(1);
    expect(result.find((road) => road.label === "椿川通線")?.id).toBe("c");
  });

  it("selects labels across the full A-B distance", () => {
    const selected = selectDistributedAnnotations(roads, 4, 462);
    expect(selected).toHaveLength(4);
    expect(selected[0].distanceM).toBeLessThan(140);
    expect(selected.at(-1)?.distanceM).toBeGreaterThan(340);
  });

  it("places a bounded, collision-free desktop set", () => {
    const result = layoutSectionAnnotations({
      candidates: roads,
      maxDistance: 462,
      maxVisible: 4,
      plotLeft: 38,
      plotRight: 980,
      railYs: [28, 46],
      minGap: 8,
      measureText: (label) => estimateSectionTextWidth(label),
    });
    expect(result.placed).toHaveLength(4);
    expect(result.overlapCount).toBe(0);
    expect(result.hiddenCount).toBe(2);
    result.placed.forEach((annotation) => {
      expect(annotation.labelX).toBeGreaterThanOrEqual(38);
      expect(annotation.labelX + annotation.labelWidth).toBeLessThanOrEqual(980);
    });
  });

  it("uses a deterministic fallback estimator for Japanese and Latin text", () => {
    expect(estimateSectionTextWidth("京月通線", 11)).toBe(44);
    expect(estimateSectionTextWidth("AB", 11)).toBeCloseTo(12.76, 5);
  });
});
