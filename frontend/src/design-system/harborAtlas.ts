/**
 * MapLibre cannot resolve CSS custom properties inside style expressions, so
 * cartographic colors live beside the CSS token source as typed constants.
 * Keep these values aligned with tokens.css and Harbor Atlas style tests.
 */
export const HARBOR_ATLAS_CARTOGRAPHY = {
  page: "#F5F5F1",
  muted: "#EEF1EF",
  ink: "#15242B",
  inkSoft: "#526269",
  line: "#D7DDDA",
  lineStrong: "#87959A",
  harborStrong: "#164F63",
  harbor: "#26758A",
  harborSoft: "#77AEB6",
  seaGlass: "#C9E1DE",
  harborPale: "#E8F2EF",
  targetStrong: "#A94736",
  target: "#D9664D",
  targetSoft: "#F1A085",
  targetPale: "#F7E4DE",
  building: "#9BA9AD",
  buildingOutline: "#596970",
  road: "#E5DDD1",
  roadOutline: "#667279",
  terrain: "#5D7476",
  focus: "#F0B84B",
  white: "#FFFFFF",
} as const;

/** Strongest to quietest; non-color cues preserve the same order. */
export const HARBOR_ATLAS_VISUAL_PRIORITY = [
  "exact-target",
  "selected-area-and-transect",
  "context-buildings-and-roads",
  "shortlist",
  "city-context",
  "basemap",
  "other-areas",
] as const;
