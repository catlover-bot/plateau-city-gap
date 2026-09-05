import type { AppData } from "../../types";
import type { SpatialSelection } from "../../state/spatial/types";
import type { GuidedAreaContext } from "../guided-spatial/guidedTypes";
import { guidedObjectFeature } from "../guided-spatial/guided3d";

export function advancedAreaId(selection: SpatialSelection | null): string | null {
  if (!selection) return null;
  const id = selection.type === "mesh" || selection.type === "building_group"
    ? selection.id : selection.properties?.parent_mesh_code;
  return typeof id === "string" && /^\d{9}$/.test(id) ? id : null;
}

export function advancedAreaSelection(data: AppData, selection: SpatialSelection | null): SpatialSelection | null {
  if (selection?.city !== data.city.id) return null;
  const id = advancedAreaId(selection);
  const properties = data.meshes.features.find((feature) => feature.properties?.mesh_code === id)?.properties;
  if (!id || !properties) return null;
  return {
    type: "mesh", id, city: data.city.id, urbanState: "2025",
    label: String(properties.area_label ?? `500mメッシュ ${id}`), properties,
    longitude: typeof properties.centroid_lon === "number" ? properties.centroid_lon : undefined,
    latitude: typeof properties.centroid_lat === "number" ? properties.centroid_lat : undefined,
  };
}

/** URL identity alone is not evidence of an exact object: require matching Area geometry. */
export function advancedExactObject(selection: SpatialSelection | null, context: GuidedAreaContext | null): SpatialSelection | null {
  if (!selection || selection.city !== "maizuru" || advancedAreaId(selection) !== context?.mesh_code
    || (selection.type !== "building" && selection.type !== "road")) return null;
  const feature = guidedObjectFeature(context, selection.type, selection.id)
    ?? (selection.type === "road" ? guidedObjectFeature(context, "road", selection.id.replace(/-(\d+)$/, ":$1")) : null);
  if (!feature) return null;
  return {
    ...selection,
    id: String(feature.id ?? selection.id),
    properties: {
      ...feature.properties, ...selection.properties, parent_mesh_code: context!.mesh_code,
      ...(selection.type === "road" ? { renderer_road_id: selection.properties?.renderer_road_id ?? selection.id } : {}),
    },
  };
}

export function advancedNumber(value: unknown, unit = "", round = false): string {
  if (value === null || value === undefined || (typeof value === "string" && !value.trim()) || (typeof value !== "number" && typeof value !== "string")) return "データなし";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${(round ? Math.round(numeric) : numeric).toLocaleString("ja-JP")}${unit}` : "データなし";
}
