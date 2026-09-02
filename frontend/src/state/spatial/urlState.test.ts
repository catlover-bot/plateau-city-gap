import { describe, expect, it } from "vitest";
import { parseSpatialUrl, spatialStateToSearch } from "./urlState";

describe("spatial URL state", () => {
  it("opens the public landing unless guided or advanced is explicit", () => {
    expect(parseSpatialUrl("")).toMatchObject({ experience: "landing", guidedStep: 1, guidedStory: "intro" });
    expect(parseSpatialUrl("?scene=plateau_detail")).toMatchObject({ experience: "landing" });
    expect(parseSpatialUrl("?experience=guided&guide=2")).toMatchObject({ experience: "guided", guidedStep: 2, guidedStory: "find" });
    expect(parseSpatialUrl("?experience=guided&guide=3")).toMatchObject({ experience: "guided", guidedStep: 3, guidedStory: "understand" });
    expect(parseSpatialUrl("?experience=guided&guide=4")).toMatchObject({ experience: "guided", guidedStep: 4, guidedStory: "verify" });
    expect(parseSpatialUrl("?experience=guided&guide=6")).toMatchObject({ experience: "advanced", guidedStep: 6, guidedStory: "verify", task: "operate" });
    expect(parseSpatialUrl("?experience=guided&guide=99")).toMatchObject({ experience: "guided", guidedStep: 1, guidedStory: "find" });
    expect(parseSpatialUrl("?experience=guided&story=understand")).toMatchObject({ experience: "guided", guidedStory: "understand" });
    expect(parseSpatialUrl("?experience=guided")).toMatchObject({ experience: "guided", guidedStep: 1, guidedStory: "intro" });
    expect(parseSpatialUrl("?experience=guided&story=intro")).toMatchObject({ experience: "guided", guidedStep: 1, guidedStory: "intro" });
    expect(parseSpatialUrl("?experience=advanced")).toMatchObject({ experience: "advanced" });
    expect(parseSpatialUrl("?advanced=1")).toMatchObject({ experience: "advanced" });
  });

  it("accepts a legacy guided step and serializes the canonical story", () => {
    const state = parseSpatialUrl("?experience=guided&guide=3&mesh=533513314");
    const serialized = spatialStateToSearch(state);
    expect(serialized).toContain("experience=guided");
    expect(serialized).toContain("story=understand");
    expect(serialized).not.toContain("guide=");
    expect(serialized).toContain("mesh=533513314");
  });

  it("maps all legacy guided links without clamping field and review views into Guided", () => {
    const expected = [
      ["1", "experience=guided", "story=find"],
      ["2", "experience=guided", "detail=reason"],
      ["3", "experience=guided", "story=understand"],
      ["4", "experience=guided", "story=verify"],
      ["5", "experience=advanced", "view=field-sheet"],
      ["6", "experience=advanced", "view=municipal-review"],
    ];
    expected.forEach(([guide, experience, destination]) => {
      const input = `?experience=guided&guide=${guide}&city=maizuru&mesh=533513314`;
      const serialized = spatialStateToSearch(parseSpatialUrl(input), new URLSearchParams(input));
      expect(serialized).toContain(experience);
      expect(serialized).toContain(destination);
      expect(serialized).toContain("selection=533513314");
      expect(serialized).not.toContain("guide=");
    });
  });

  it("hydrates every shareable spatial dimension", () => {
    const state = parseSpatialUrl("?city=fujisawa&task=validate&urbanState=2023&mesh=523973982&scenario=B&validationSample=route-1&mapMode=plateau3d&intent=validate&resolution=road&scene=validation_disagreement&lens=service-pulse&twin=stress&lng=139.47&lat=35.36&z=14");
    expect(state.city).toBe("fujisawa");
    expect(state.task).toBe("validate");
    expect(state.selection).toMatchObject({ type: "mesh", id: "523973982" });
    expect(state.scenario).toBe("B");
    expect(state.validationSample).toBe("route-1");
    expect(state.mapMode).toBe("plateau3d");
    expect(state.intent).toBe("validate");
    expect(state.resolution).toBe("road");
    expect(state.scenePreset).toBe("validation_disagreement");
    expect(state.analysisLens).toBe("service-pulse");
    expect(state.counterfactualState).toBe("stress");
  });

  it("keeps legacy workspace links compatible and serializes canonical state", () => {
    const state = parseSpatialUrl("?workspace=futures&city=maizuru");
    expect(state.task).toBe("try");
    const serialized = spatialStateToSearch({ ...state, urbanState: "2040", scenario: "scenario_c" });
    expect(serialized).toContain("workspace=futures");
    expect(serialized).toContain("urbanState=2040");
    expect(serialized).toContain("scenario=scenario_c");
    expect(serialized).toContain("scene=gap_discovery");
    expect(serialized).toContain("lens=none");
    expect(serialized).toContain("twin=baseline");
  });

  it("restores the complete workspace from a scene-only deep link", () => {
    const state = parseSpatialUrl("?city=maizuru&scene=plateau_detail");
    expect(state).toMatchObject({
      scenePreset: "plateau_detail",
      task: "detail",
      intent: "inspect",
      resolution: "city",
      mapMode: "plateau3d",
      preset: "plateau-detail",
      primaryLayer: "plateau-buildings",
      mapState: "detail3d",
    });
  });

  it("preserves only the approved deterministic building source fixture", () => {
    const state = parseSpatialUrl("?city=maizuru&scene=plateau_detail&resolution=building_group");
    const serialized = spatialStateToSearch(state, new URLSearchParams("buildingSource=verified-local&unknown=discard"));
    expect(serialized).toContain("buildingSource=verified-local");
    expect(spatialStateToSearch(state, new URLSearchParams("buildingSource=spatial-pack"))).toContain("buildingSource=spatial-pack");
    expect(spatialStateToSearch(state, new URLSearchParams("section=closed"))).toContain("section=closed");
    const area = spatialStateToSearch(state, new URLSearchParams("journey=area&copy=B"));
    expect(area).toContain("journey=area");
    expect(area).toContain("copy=B");
    expect(serialized).not.toContain("unknown");
  });
});
