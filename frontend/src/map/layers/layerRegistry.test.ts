import { describe, expect, it } from "vitest";
import { LAYER_PRESETS, LAYER_REGISTRY, activeLayerIds } from "./layerRegistry";

describe("renderer-neutral layer registry", () => {
  it("declares complete governance metadata and one primary layer per preset", () => {
    expect(LAYER_REGISTRY.length).toBeGreaterThanOrEqual(24);
    for (const layer of LAYER_REGISTRY) {
      expect(layer.id).toBeTruthy();
      expect(layer.source.kind).toBeTruthy();
      expect(layer.year).toBeTruthy();
      expect(layer.legend.length).toBeGreaterThan(0);
      expect(layer.attribution).toBeTruthy();
      expect(layer.evidenceLink).toBeTruthy();
      expect(layer.minZoom).toBeLessThan(layer.maxZoom);
    }
    expect(new Set(LAYER_PRESETS.map((preset) => preset.primaryLayer)).size).toBe(LAYER_PRESETS.length);
  });

  it("separates every requested PLATEAU theme", () => {
    const themes = LAYER_REGISTRY.filter((layer) => layer.group === "PLATEAU").map((layer) => layer.id);
    expect(themes).toEqual(expect.arrayContaining([
      "plateau-buildings", "plateau-roads", "plateau-terrain", "plateau-landuse", "plateau-planning",
      "plateau-flood", "plateau-landslide", "plateau-tsunami"
    ]));
    expect(activeLayerIds("validation-compare")).toEqual(expect.arrayContaining(["validation-primary-route", "validation-reference-route"]));
  });
});
