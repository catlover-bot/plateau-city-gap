import { describe, expect, it } from "vitest";
import type { ScenePresetId, SpatialSelection } from "../../state/spatial/types";
import { supportsVerifiedLocalView, VERIFIED_LOCAL_MESH, VERIFIED_LOCAL_PACK, VERIFIED_LOCAL_READINESS_TIMEOUT_MS } from "./verifiedLocalView";

const area: SpatialSelection = { type: "mesh", id: VERIFIED_LOCAL_MESH, city: "maizuru", urbanState: "2025" };
const input = { requested: true, city: "maizuru", scenePreset: "plateau_detail" as const, selection: area, metadataMeshCode: VERIFIED_LOCAL_MESH, sectionPackId: VERIFIED_LOCAL_PACK };

describe("Advanced bounded PLATEAU presentation eligibility", () => {
  it("requires explicit opt-in and matching verified Area, metadata and Section", () => {
    expect(supportsVerifiedLocalView(input)).toBe(true);
    expect(supportsVerifiedLocalView({ ...input, requested: false })).toBe(false);
    expect(supportsVerifiedLocalView({ ...input, metadataMeshCode: "other-area" })).toBe(false);
    expect(supportsVerifiedLocalView({ ...input, sectionPackId: "other-section" })).toBe(false);
  });

  it.each(["building", "road"] as const)("keeps the same bounded scene for an exact %s with a known parent Area", (type) => {
    const selected = { ...area, type, id: `${type}:actual-object`, properties: { parent_mesh_code: VERIFIED_LOCAL_MESH } };
    expect(supportsVerifiedLocalView({ ...input, selection: selected })).toBe(true);
    expect(supportsVerifiedLocalView({ ...input, selection: { ...selected, properties: {} } })).toBe(false);
  });

  it("supports a building group at the same Area without assigning another Area its model", () => {
    expect(supportsVerifiedLocalView({ ...input, selection: { ...area, type: "building_group" } })).toBe(true);
    expect(supportsVerifiedLocalView({ ...input, selection: { ...area, id: "533512753" } })).toBe(false);
    expect(supportsVerifiedLocalView({ ...input, selection: null })).toBe(false);
    expect(supportsVerifiedLocalView({ ...input, city: "fujisawa" })).toBe(false);
  });

  it.each<ScenePresetId>(["city_overview", "gap_discovery", "network_access", "scenario_compare", "hazard_stress", "temporal_change", "validation_disagreement"])("preserves the existing %s engine policy", (scenePreset) => {
    expect(supportsVerifiedLocalView({ ...input, scenePreset })).toBe(false);
  });

  it("has a bounded readiness deadline", () => {
    expect(VERIFIED_LOCAL_READINESS_TIMEOUT_MS).toBeGreaterThan(0);
    expect(VERIFIED_LOCAL_READINESS_TIMEOUT_MS).toBeLessThanOrEqual(45_000);
  });
});
