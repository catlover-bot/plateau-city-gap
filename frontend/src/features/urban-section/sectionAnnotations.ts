export interface SectionRoadAnnotationInput {
  id: string;
  label: string;
  distanceM: number;
  offsetDistanceM: number;
}

export interface SectionAnnotationCandidate extends SectionRoadAnnotationInput {
  priority: number;
}

export interface PlacedSectionAnnotation extends SectionAnnotationCandidate {
  anchorX: number;
  labelX: number;
  labelWidth: number;
  railY: number;
}

export interface SectionAnnotationLayout {
  placed: PlacedSectionAnnotation[];
  hiddenCount: number;
  overlapCount: number;
}

interface LayoutOptions {
  candidates: SectionRoadAnnotationInput[];
  maxDistance: number;
  maxVisible: number;
  plotLeft: number;
  plotRight: number;
  railYs: number[];
  minGap: number;
  measureText(label: string): number;
}

const UNKNOWN_ROAD = /^(?:名称不明(?:の道路)?|道路名なし|不明|unnamed)$/i;

function normalizedLabel(label: string): string {
  return label.trim().replace(/\s+/g, " ");
}

export function deduplicateNamedRoads(inputs: SectionRoadAnnotationInput[]): SectionRoadAnnotationInput[] {
  const byLabel = new Map<string, SectionRoadAnnotationInput>();
  inputs.forEach((input) => {
    const label = normalizedLabel(input.label);
    if (!label || UNKNOWN_ROAD.test(label)) return;
    const candidate = { ...input, label };
    const previous = byLabel.get(label);
    if (
      !previous
      || candidate.offsetDistanceM < previous.offsetDistanceM
      || (candidate.offsetDistanceM === previous.offsetDistanceM && candidate.distanceM < previous.distanceM)
    ) byLabel.set(label, candidate);
  });
  return [...byLabel.values()].sort((left, right) => left.distanceM - right.distanceM || left.label.localeCompare(right.label, "ja"));
}

export function selectDistributedAnnotations(
  inputs: SectionRoadAnnotationInput[],
  maxVisible: number,
  maxDistance: number,
): SectionAnnotationCandidate[] {
  const candidates = deduplicateNamedRoads(inputs);
  const limit = Math.max(0, Math.min(maxVisible, candidates.length));
  if (!limit) return [];
  const available = [...candidates];
  const selected: SectionAnnotationCandidate[] = [];
  for (let index = 0; index < limit; index += 1) {
    const target = maxDistance * ((index + .5) / limit);
    available.sort((left, right) => (
      Math.abs(left.distanceM - target) - Math.abs(right.distanceM - target)
      || left.distanceM - right.distanceM
      || left.label.localeCompare(right.label, "ja")
    ));
    const choice = available.shift();
    if (choice) selected.push({ ...choice, priority: limit - index });
  }
  return selected.sort((left, right) => left.distanceM - right.distanceM);
}

export function estimateSectionTextWidth(label: string, fontSize = 11): number {
  return [...label].reduce((width, character) => {
    if (/\s/.test(character)) return width + fontSize * .32;
    if ((character.codePointAt(0) ?? 0) <= 0xff) return width + fontSize * .58;
    return width + fontSize;
  }, 0);
}

export function browserSectionTextMeasurer(font: string): (label: string) => number {
  if (typeof document === "undefined") return (label) => estimateSectionTextWidth(label);
  const context = document.createElement("canvas").getContext("2d");
  if (!context) return (label) => estimateSectionTextWidth(label);
  context.font = font;
  return (label) => {
    const width = context.measureText(label).width;
    return Number.isFinite(width) && width > 0 ? width : estimateSectionTextWidth(label);
  };
}

function overlaps(left: Pick<PlacedSectionAnnotation, "labelX" | "labelWidth">, right: Pick<PlacedSectionAnnotation, "labelX" | "labelWidth">, gap: number): boolean {
  return left.labelX < right.labelX + right.labelWidth + gap
    && right.labelX < left.labelX + left.labelWidth + gap;
}

function clamped(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

export function layoutSectionAnnotations(options: LayoutOptions): SectionAnnotationLayout {
  const selected = selectDistributedAnnotations(options.candidates, options.maxVisible, options.maxDistance);
  const placed: PlacedSectionAnnotation[] = [];
  const availableWidth = Math.max(1, options.plotRight - options.plotLeft);

  selected
    .sort((left, right) => right.priority - left.priority || left.distanceM - right.distanceM)
    .forEach((candidate) => {
      const anchorX = options.plotLeft + candidate.distanceM / Math.max(options.maxDistance, 1) * availableWidth;
      const labelWidth = Math.min(availableWidth, Math.max(28, options.measureText(candidate.label) + 10));
      const preferred = clamped(anchorX - labelWidth / 2, options.plotLeft, options.plotRight - labelWidth);
      let best: PlacedSectionAnnotation | null = null;
      let bestCost = Number.POSITIVE_INFINITY;

      options.railYs.forEach((railY, railIndex) => {
        const onRail = placed.filter((item) => item.railY === railY).sort((left, right) => left.labelX - right.labelX);
        const positions = new Set<number>([
          preferred,
          options.plotLeft,
          options.plotRight - labelWidth,
          ...onRail.flatMap((item) => [
            item.labelX + item.labelWidth + options.minGap,
            item.labelX - options.minGap - labelWidth,
          ]),
        ]);
        [...positions].forEach((position) => {
          const labelX = clamped(position, options.plotLeft, options.plotRight - labelWidth);
          const next: PlacedSectionAnnotation = { ...candidate, anchorX, labelX, labelWidth, railY };
          if (onRail.some((item) => overlaps(next, item, options.minGap))) return;
          const cost = Math.abs(labelX + labelWidth / 2 - anchorX) + railIndex * 2;
          if (cost < bestCost) {
            best = next;
            bestCost = cost;
          }
        });
      });

      if (best) placed.push(best);
    });

  const ordered = placed.sort((left, right) => left.railY - right.railY || left.labelX - right.labelX);
  let overlapCount = 0;
  ordered.forEach((item, index) => {
    ordered.slice(index + 1).forEach((other) => {
      if (item.railY === other.railY && overlaps(item, other, 0)) overlapCount += 1;
    });
  });
  return {
    placed: ordered,
    hiddenCount: Math.max(0, deduplicateNamedRoads(options.candidates).length - ordered.length),
    overlapCount,
  };
}
