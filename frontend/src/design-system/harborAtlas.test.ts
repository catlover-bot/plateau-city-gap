import { describe, expect, it } from "vitest";
import { HARBOR_ATLAS_CARTOGRAPHY as color, HARBOR_ATLAS_VISUAL_PRIORITY } from "./harborAtlas";

describe("Harbor Atlas cartography contract", () => {
  it("keeps selected space and exact targets in different color families", () => {
    expect(color.harborStrong).toBe("#164F63");
    expect(color.target).toBe("#D9664D");
    expect(color.harborStrong).not.toBe(color.target);
  });

  it("uses neutral material colors for buildings and roads", () => {
    expect(color.building).toBe("#9BA9AD");
    expect(color.buildingOutline).toBe("#596970");
    expect(color.road).toBe("#E5DDD1");
    expect(color.roadOutline).toBe("#667279");
  });

  it("places exact targets above selected space and all context", () => {
    expect(HARBOR_ATLAS_VISUAL_PRIORITY.slice(0, 3)).toEqual([
      "exact-target",
      "selected-area-and-transect",
      "context-buildings-and-roads",
    ]);
    expect(HARBOR_ATLAS_VISUAL_PRIORITY.at(-1)).toBe("other-areas");
  });
});
