import type { LayerSpecification } from "maplibre-gl";
import { HARBOR_ATLAS_CARTOGRAPHY as atlas } from "../../design-system/harborAtlas";

export const GUIDED_SOURCE_IDS = [
  "guided-area",
  "guided-buildings",
  "guided-roads",
  "guided-planning",
  "guided-target",
  "guided-section",
  "guided-section-focus",
] as const;

// The array order is the rendering order. Context materials sit below the
// selected Area, A-B transect, active focus, and exact target in that order.
export const GUIDED_LAYER_DEFINITIONS = [
  { id: "guided-planning-fill", type: "fill", source: "guided-planning", layout: { visibility: "none" }, paint: { "fill-color": atlas.seaGlass, "fill-opacity": .09 } },
  { id: "guided-planning-line", type: "line", source: "guided-planning", layout: { visibility: "none" }, paint: { "line-color": atlas.harborSoft, "line-width": 1.1, "line-dasharray": [3, 2], "line-opacity": .48 } },
  { id: "guided-roads-fill", type: "fill", source: "guided-roads", minzoom: 12, layout: { visibility: "none" }, paint: { "fill-color": atlas.road, "fill-opacity": .42 } },
  { id: "guided-roads-line", type: "line", source: "guided-roads", minzoom: 12, layout: { visibility: "none" }, paint: { "line-color": atlas.roadOutline, "line-width": ["interpolate", ["linear"], ["zoom"], 12, .55, 17, 2.2], "line-opacity": .72 } },
  { id: "guided-buildings-fill", type: "fill", source: "guided-buildings", minzoom: 12, layout: { visibility: "none" }, paint: { "fill-color": atlas.building, "fill-opacity": .46 } },
  { id: "guided-buildings-line", type: "line", source: "guided-buildings", minzoom: 12, layout: { visibility: "none" }, paint: { "line-color": atlas.buildingOutline, "line-width": ["interpolate", ["linear"], ["zoom"], 12, .3, 17, 1.05], "line-opacity": .6 } },
  { id: "guided-area-fill", type: "fill", source: "guided-area", layout: { visibility: "none" }, paint: { "fill-color": atlas.seaGlass, "fill-opacity": .14 } },
  { id: "guided-area-halo", type: "line", source: "guided-area", layout: { visibility: "none" }, paint: { "line-color": atlas.white, "line-width": 7, "line-opacity": .94 } },
  { id: "guided-area-line", type: "line", source: "guided-area", layout: { visibility: "none" }, paint: { "line-color": atlas.harborStrong, "line-width": 3.8, "line-opacity": 1 } },
  { id: "guided-area-label", type: "symbol", source: "guided-area", minzoom: 9.4, layout: { visibility: "none", "text-field": ["coalesce", ["get", "area_label"], ["get", "mesh_code"]], "text-size": 15, "text-font": ["Open Sans Bold", "Arial Unicode MS Regular"], "text-allow-overlap": true, "text-offset": [0, 1.25] }, paint: { "text-color": atlas.harborStrong, "text-halo-color": atlas.white, "text-halo-width": 3 } },
  { id: "guided-section-halo", type: "line", source: "guided-section", layout: { visibility: "none" }, paint: { "line-color": atlas.white, "line-width": 7, "line-opacity": .94 } },
  { id: "guided-section-line", type: "line", source: "guided-section", layout: { visibility: "none", "line-cap": "round" }, paint: { "line-color": atlas.harbor, "line-width": 4, "line-opacity": 1 } },
  { id: "guided-section-endpoint-dots", type: "circle", source: "guided-section", filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none" }, paint: { "circle-color": atlas.harborStrong, "circle-radius": 6.5, "circle-stroke-color": atlas.white, "circle-stroke-width": 2.5 } },
  { id: "guided-section-endpoints", type: "symbol", source: "guided-section", filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none", "text-field": ["get", "endpoint"], "text-size": 15, "text-font": ["Open Sans Bold", "Arial Unicode MS Regular"], "text-offset": [0, -1.2], "text-allow-overlap": true }, paint: { "text-color": atlas.harborStrong, "text-halo-color": atlas.white, "text-halo-width": 2.5 } },
  { id: "guided-section-focus", type: "circle", source: "guided-section-focus", layout: { visibility: "none" }, paint: { "circle-color": atlas.target, "circle-radius": 6, "circle-stroke-color": atlas.white, "circle-stroke-width": 2 } },
  { id: "guided-target-fill", type: "fill", source: "guided-target", layout: { visibility: "none" }, paint: { "fill-color": atlas.target, "fill-opacity": .42 } },
  { id: "guided-target-halo", type: "line", source: "guided-target", layout: { visibility: "none" }, paint: { "line-color": atlas.white, "line-width": 11, "line-opacity": .98 } },
  { id: "guided-target-line", type: "line", source: "guided-target", layout: { visibility: "none" }, paint: { "line-color": atlas.targetStrong, "line-width": 5, "line-opacity": 1 } },
  { id: "guided-target-point", type: "circle", source: "guided-target", filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none" }, paint: { "circle-color": atlas.target, "circle-radius": 11, "circle-stroke-color": atlas.white, "circle-stroke-width": 4, "circle-opacity": 1 } },
  { id: "guided-target-label", type: "symbol", source: "guided-target", layout: { visibility: "none", "text-field": ["get", "map_label"], "text-size": 14, "text-font": ["Open Sans Semibold", "Arial Unicode MS Regular"], "text-offset": [0, 1.5], "text-padding": 12, "text-allow-overlap": true, "text-ignore-placement": true }, paint: { "text-color": atlas.targetStrong, "text-halo-color": atlas.white, "text-halo-width": 3 } },
] satisfies LayerSpecification[];
