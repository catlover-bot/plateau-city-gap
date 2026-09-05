import type { SpatialSelection, ScenePresetId } from "../../state/spatial/types";

export const VERIFIED_LOCAL_MESH = "533513314";
export const VERIFIED_LOCAL_PACK = "maizuru-533513314-plateau-2025-v1";
export const VERIFIED_LOCAL_READINESS_TIMEOUT_MS = 45_000;

/** A bounded local presentation is an explicit choice, never a citywide fallback. */
export function supportsVerifiedLocalView(input: {
  requested: boolean;
  city: string;
  scenePreset: ScenePresetId;
  selection: SpatialSelection | null;
  metadataMeshCode?: string;
  sectionPackId?: string;
}): boolean {
  const meshCode = input.selection?.type === "mesh" || input.selection?.type === "building_group"
    ? input.selection.id
    : input.selection?.properties?.parent_mesh_code;
  return input.requested && input.city === "maizuru" && input.selection?.city === input.city && input.scenePreset === "plateau_detail"
    && input.metadataMeshCode === VERIFIED_LOCAL_MESH && meshCode === VERIFIED_LOCAL_MESH
    && (!input.sectionPackId || input.sectionPackId === VERIFIED_LOCAL_PACK);
}
