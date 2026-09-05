import type { SectionData, SectionRelation, TerrainSample } from "./sectionTypes";
import type { SpatialSelection } from "../../state/spatial/types";

export const SECTION_VIEW_WIDTH = 1000;
export const SECTION_PLOT_LEFT = 38;
export const SECTION_PLOT_RIGHT_GUTTER = 20;
export const SECTION_TERRAIN_TOP = 32;
export const SECTION_TERRAIN_BOTTOM = 174;

export interface TerrainSegment {
  line: string;
  area: string;
}

type CoveredTerrainSample = TerrainSample & { elevation_m: number };

export interface SectionPlot {
  covered: CoveredTerrainSample[];
  maxDistance: number;
  minimumElevation: number;
  maximumElevation: number;
  viewWidth: number;
  plotLeft: number;
  x(distance: number): number;
  y(elevation: number): number;
  terrainSegments: TerrainSegment[];
  endpointAY: number;
  endpointBY: number;
}

export interface SectionFocusDetail {
  id: string;
  kind: "building" | "road";
  kindLabel: "建物" | "道路";
  label: string;
  distanceM: number;
  elevationM: number | null;
  relation: SectionRelation["relation"];
  offsetDistanceM: number;
}

export interface SectionFocusCallout {
  anchorX: number;
  anchorY: number;
  labelX: number;
  labelWidth: number;
  meta: string;
  relation: string;
}

function terrainSegments(
  samples: TerrainSample[],
  x: (value: number) => number,
  y: (value: number) => number,
): TerrainSegment[] {
  const segments: TerrainSegment[] = [];
  let current: Array<[number, number]> = [];
  const finish = () => {
    if (current.length > 1) {
      const line = current
        .map(([pointX, pointY], index) => `${index ? "L" : "M"}${pointX.toFixed(2)},${pointY.toFixed(2)}`)
        .join(" ");
      const first = current[0];
      const last = current[current.length - 1];
      segments.push({
        line,
        area: `${line} L${last[0].toFixed(2)},${SECTION_TERRAIN_BOTTOM} L${first[0].toFixed(2)},${SECTION_TERRAIN_BOTTOM} Z`,
      });
    }
    current = [];
  };
  samples.forEach((sample) => {
    if (sample.elevation_m === null) {
      finish();
      return;
    }
    current.push([x(sample.distance_m), y(sample.elevation_m)]);
  });
  finish();
  return segments;
}

export function buildSectionPlot(data: SectionData, compact: boolean, containerWidth?: number): SectionPlot {
  const covered = data.terrain_samples.filter(
    (sample): sample is CoveredTerrainSample => sample.elevation_m !== null,
  );
  const maxDistance = Math.max(...data.terrain_samples.map((sample) => sample.distance_m), 1);
  const minimumElevation = Math.min(...covered.map((sample) => sample.elevation_m));
  const maximumElevation = Math.max(...covered.map((sample) => sample.elevation_m));
  const maximumBuildingTop = Math.max(
    ...data.buildings.map((building) => {
      const height = typeof building.properties.measured_height_m === "number"
        ? building.properties.measured_height_m
        : 0;
      const nearest = covered.reduce((best, sample) => (
        Math.abs(sample.distance_m - building.start_distance_m) < Math.abs(best.distance_m - building.start_distance_m)
          ? sample
          : best
      ), covered[0]);
      return nearest.elevation_m + height;
    }),
    ...covered.map((sample) => sample.elevation_m),
  );
  const elevationSpan = Math.max(maximumBuildingTop - minimumElevation, 20);
  const measured = typeof containerWidth === "number" && Number.isFinite(containerWidth) && containerWidth > 0;
  const viewWidth = measured ? containerWidth : compact ? 390 : SECTION_VIEW_WIDTH;
  const plotLeft = measured ? 54 : SECTION_PLOT_LEFT;
  const x = (distance: number) => plotLeft + distance / maxDistance * (viewWidth - plotLeft - SECTION_PLOT_RIGHT_GUTTER);
  const y = (elevation: number) => SECTION_TERRAIN_BOTTOM
    - (elevation - minimumElevation) / elevationSpan * (SECTION_TERRAIN_BOTTOM - SECTION_TERRAIN_TOP);
  const firstCovered = data.terrain_samples.find((sample) => sample.elevation_m !== null);
  const lastCovered = [...data.terrain_samples].reverse().find((sample) => sample.elevation_m !== null);
  return {
    covered,
    maxDistance,
    minimumElevation,
    maximumElevation,
    viewWidth,
    plotLeft,
    x,
    y,
    terrainSegments: terrainSegments(data.terrain_samples, x, y),
    endpointAY: y(firstCovered?.elevation_m ?? minimumElevation),
    endpointBY: y(lastCovered?.elevation_m ?? minimumElevation),
  };
}

/** A selected annotation exists only for an exact object recorded in this section. */
export function selectedSectionObject(data: SectionData, selection: SpatialSelection | null): SectionFocusDetail | null {
  if (!selection || (selection.type !== "building" && selection.type !== "road")) return null;
  const kind = selection.type;
  const rendererId = kind === "road" && typeof selection.properties?.renderer_road_id === "string"
    ? selection.properties.renderer_road_id : null;
  const ids = [selection.id, rendererId, kind === "road" ? selection.id.replace(/:(\d+)$/, "-$1") : null];
  const relation = (kind === "building" ? data.buildings : data.roads).find((item) => ids.includes(item.source_object_id));
  if (!relation) return null;
  const distanceM = (relation.start_distance_m + relation.end_distance_m) / 2;
  const sample = data.terrain_samples.reduce<TerrainSample | null>((best, item) => (
    !best || Math.abs(item.distance_m - distanceM) < Math.abs(best.distance_m - distanceM) ? item : best
  ), null);
  return {
    id: relation.source_object_id,
    kind,
    kindLabel: kind === "road" ? "道路" : "建物",
    label: kind === "road" ? String(relation.properties.road_name ?? "名称不明の道路")
      : String(relation.properties.usage_label ?? relation.properties.usage ?? "用途不明の建物"),
    distanceM,
    elevationM: sample?.elevation_m ?? null,
    relation: relation.relation,
    offsetDistanceM: relation.offset_distance_m,
  };
}

function distanceFromRelation(relation: SectionRelation, distanceM: number): number {
  if (distanceM < relation.start_distance_m) return relation.start_distance_m - distanceM;
  if (distanceM > relation.end_distance_m) return distanceM - relation.end_distance_m;
  return 0;
}

export function nearestSectionObject(
  data: SectionData,
  distanceM: number,
  elevationM: number | null,
): SectionFocusDetail | null {
  const candidates = [
    ...data.buildings.map((relation) => ({ relation, kind: "building" as const })),
    ...data.roads.map((relation) => ({ relation, kind: "road" as const })),
  ];
  candidates.sort((left, right) => (
    distanceFromRelation(left.relation, distanceM) - distanceFromRelation(right.relation, distanceM)
    || Number(right.relation.relation === "direct") - Number(left.relation.relation === "direct")
    || left.relation.start_distance_m - right.relation.start_distance_m
  ));
  const nearest = candidates[0];
  if (!nearest) return null;
  const relation = nearest.relation;
  return {
    id: relation.source_object_id,
    kind: nearest.kind,
    kindLabel: nearest.kind === "road" ? "道路" : "建物",
    label: nearest.kind === "road"
      ? String(relation.properties.road_name ?? "名称不明の道路")
      : String(relation.properties.usage_label ?? relation.properties.usage ?? "用途不明の建物"),
    distanceM: (relation.start_distance_m + relation.end_distance_m) / 2,
    elevationM,
    relation: relation.relation,
    offsetDistanceM: relation.offset_distance_m,
  };
}

export function buildSectionFocusCallout(
  detail: SectionFocusDetail,
  plot: SectionPlot,
  compact: boolean,
  measureName: (text: string) => number,
  measureMeta: (text: string) => number,
): SectionFocusCallout {
  const anchorX = plot.x(detail.distanceM);
  const elevationLabel = detail.elevationM === null ? "—" : `${detail.elevationM.toFixed(1)}m`;
  const meta = `${detail.kindLabel} · ${Math.round(detail.distanceM)}m · 標高${elevationLabel}`;
  const relation = detail.relation === "direct"
    ? "直接交差"
    : `断面から約${Math.round(detail.offsetDistanceM)}m`;
  const labelWidth = Math.min(
    plot.viewWidth - plot.plotLeft - SECTION_PLOT_RIGHT_GUTTER,
    compact ? 210 : 250,
    Math.max(156, measureName(detail.label) + 18, measureMeta(meta) + 16, measureMeta(relation) + 16),
  );
  const labelX = Math.min(
    plot.viewWidth - SECTION_PLOT_RIGHT_GUTTER - labelWidth,
    Math.max(plot.plotLeft, anchorX - labelWidth / 2),
  );
  const anchorY = detail.elevationM === null ? SECTION_TERRAIN_BOTTOM : plot.y(detail.elevationM);
  return { anchorX, anchorY, labelX, labelWidth, meta, relation };
}

export function sectionSampleIndexAtViewX(
  data: SectionData,
  plot: SectionPlot,
  viewX: number,
): number {
  const distance = Math.max(
    0,
    Math.min(
      plot.maxDistance,
      (viewX - plot.plotLeft) / (plot.viewWidth - plot.plotLeft - SECTION_PLOT_RIGHT_GUTTER) * plot.maxDistance,
    ),
  );
  return data.terrain_samples.reduce((bestIndex, candidate, index) => (
    Math.abs(candidate.distance_m - distance) < Math.abs(data.terrain_samples[bestIndex].distance_m - distance)
      ? index
      : bestIndex
  ), 0);
}
