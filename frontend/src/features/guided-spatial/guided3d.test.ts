import { describe, expect, it } from "vitest";
import supportedContextFixture from "../../../public/data/guided/area-context/533513314.json";
import unsupportedContextFixture from "../../../public/data/guided/area-context/533512753.json";
import type { SpatialSelection } from "../../state/spatial/types";
import type { GuidedAreaContext } from "./guidedTypes";
import { GUIDED_CHECKS } from "./guidedContent";
import { guidedObjectFeature, guidedObjectTarget, selectionFromGuidedTarget, supportsGuided3D } from "./guided3d";

const supported = supportedContextFixture as unknown as GuidedAreaContext;
const unsupported = unsupportedContextFixture as unknown as GuidedAreaContext;
const area: SpatialSelection = {
  type: "mesh", id: supported.mesh_code, city: "maizuru", urbanState: "2025", label: "常団地前周辺",
};
const objectSelection = (kind: "building" | "road"): SpatialSelection => ({
  ...area,
  type: kind,
  id: String(supported.layers[kind === "building" ? "buildings" : "roads"].features[0].id),
  properties: { parent_mesh_code: supported.mesh_code },
});

describe("Guided 3D coverage and object continuity", () => {
  it("opens the verified 3D Area only with its matching ready context", () => {
    expect(supportsGuided3D(supported.mesh_code, supported)).toBe(true);
    expect(supportsGuided3D(supported.mesh_code, null)).toBe(false);
    expect(supportsGuided3D(supported.mesh_code, unsupported)).toBe(false);
  });

  it("never reuses the example model for an unsupported Area or unavailable pack", () => {
    expect(supportsGuided3D(unsupported.mesh_code, unsupported)).toBe(false);
    expect(supportsGuided3D(unsupported.mesh_code, supported)).toBe(false);
    expect(supportsGuided3D(supported.mesh_code, {
      ...supported, section: { ...supported.section, status: "unavailable" },
    })).toBe(false);
    expect(supportsGuided3D(supported.mesh_code, {
      ...supported, section: { ...supported.section, pack_id: "another-area-pack" },
    })).toBe(false);
  });

  it.each(["building", "road"] as const)("keeps a real %s geometry and its own existing checks", (kind) => {
    const selected = objectSelection(kind);
    const feature = guidedObjectFeature(supported, kind, selected.id);
    const target = guidedObjectTarget(selected, supported);
    expect(feature).not.toBeNull();
    expect(target).toMatchObject({ key: `${kind}:${selected.id}`, kind, resolution: "exact" });
    expect(target?.geometry.features).toEqual([feature]);
    expect(target?.checks).toEqual(GUIDED_CHECKS[kind]);
    expect(target?.checks.length).toBeGreaterThanOrEqual(3);
    expect(target?.checks.length).toBeLessThanOrEqual(5);
    expect(target?.checks).not.toEqual(GUIDED_CHECKS[kind === "building" ? "road" : "building"]);
    expect(selectionFromGuidedTarget(target!, area)).toMatchObject({
      type: kind, id: selected.id, properties: { parent_mesh_code: supported.mesh_code },
    });
  });

  it.each(["building", "road"] as const)("drops a stale %s when the selected Area changes", (kind) => {
    const selected = objectSelection(kind);
    expect(guidedObjectTarget(selected, unsupported)).toBeNull();
    expect(guidedObjectTarget({ ...selected, properties: { parent_mesh_code: unsupported.mesh_code } }, supported)).toBeNull();
    expect(guidedObjectTarget(selected, null)).toBeNull();
    expect(guidedObjectTarget({ ...selected, id: "object-not-in-this-area" }, supported)).toBeNull();
  });

  it("does not reinterpret a building ID as a road or an Area as an exact object", () => {
    const building = objectSelection("building");
    expect(guidedObjectTarget({ ...building, type: "road" }, supported)).toBeNull();
    expect(guidedObjectTarget(area, supported)).toBeNull();
    expect(guidedObjectTarget(null, supported)).toBeNull();
  });
});
