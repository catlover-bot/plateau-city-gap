import { describe, expect, it } from "vitest";
import { parseSpatialUrl, spatialStateToSearch } from "./urlState";

describe("spatial URL state", () => {
  it("hydrates every shareable spatial dimension", () => {
    const state = parseSpatialUrl("?city=fujisawa&task=validate&urbanState=2023&mesh=523973982&scenario=B&validationSample=route-1&mapMode=plateau3d&intent=validate&resolution=route&scene=validation_disagreement&lng=139.47&lat=35.36&z=14");
    expect(state.city).toBe("fujisawa");
    expect(state.task).toBe("validate");
    expect(state.selection).toMatchObject({ type: "mesh", id: "523973982" });
    expect(state.scenario).toBe("B");
    expect(state.validationSample).toBe("route-1");
    expect(state.mapMode).toBe("plateau3d");
    expect(state.intent).toBe("validate");
    expect(state.resolution).toBe("route");
    expect(state.scenePreset).toBe("validation_disagreement");
  });

  it("keeps legacy workspace links compatible and serializes canonical state", () => {
    const state = parseSpatialUrl("?workspace=futures&city=maizuru");
    expect(state.task).toBe("try");
    const serialized = spatialStateToSearch({ ...state, urbanState: "2040", scenario: "scenario_c" });
    expect(serialized).toContain("workspace=futures");
    expect(serialized).toContain("urbanState=2040");
    expect(serialized).toContain("scenario=scenario_c");
    expect(serialized).toContain("scene=gap_discovery");
  });

  it("restores the complete workspace from a scene-only deep link", () => {
    const state = parseSpatialUrl("?city=maizuru&scene=plateau_detail");
    expect(state).toMatchObject({
      scenePreset: "plateau_detail",
      task: "detail",
      intent: "inspect",
      resolution: "building",
      mapMode: "plateau3d",
      preset: "plateau-detail",
      primaryLayer: "plateau-buildings",
      mapState: "detail3d",
    });
  });
});
