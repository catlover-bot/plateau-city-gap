import type { GeoJsonFeatureCollection } from "../../../types";

export type TemporalGhostKind = "added" | "removed" | "geometry_changed" | "attribute_changed" | "unchanged";

export interface TemporalGhostRecord {
  id: string;
  kind: TemporalGhostKind;
  longitude: number;
  latitude: number;
  reviewStatus: string;
  officialGeometryAvailable: boolean;
}

const KINDS = new Set<TemporalGhostKind>(["added", "removed", "geometry_changed", "attribute_changed", "unchanged"]);

export function buildTemporalGhostRecords(samples: GeoJsonFeatureCollection | null): TemporalGhostRecord[] {
  if (!samples) return [];
  return samples.features.flatMap((feature) => {
    const properties = feature.properties ?? {};
    const coordinates = feature.geometry?.type === "Point" ? feature.geometry.coordinates : null;
    const kind = String(properties.change_type ?? "") as TemporalGhostKind;
    if (!Array.isArray(coordinates) || !KINDS.has(kind) || !Number.isFinite(coordinates[0]) || !Number.isFinite(coordinates[1])) return [];
    return [{
      id: String(feature.id ?? properties.sample_id ?? "temporal-change"),
      kind,
      longitude: Number(coordinates[0]),
      latitude: Number(coordinates[1]),
      reviewStatus: String(properties.review_status ?? "not_reviewed"),
      officialGeometryAvailable: false,
    }];
  });
}
