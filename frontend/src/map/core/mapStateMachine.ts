import type { MapMode, MapState, ProductTask, SpatialSelection } from "../../state/spatial/types";

export type MapEvent =
  | "CLEAR"
  | "SELECT"
  | "OPEN_3D"
  | "OPEN_2D"
  | "START_COMPARE"
  | "START_PLACEMENT"
  | "OPEN_VALIDATION";

export function transitionMapState(current: MapState, event: MapEvent): MapState {
  const transitions: Record<MapEvent, MapState> = {
    CLEAR: "overview",
    SELECT: "focus",
    OPEN_3D: "detail3d",
    OPEN_2D: current === "validation" ? "validation" : "focus",
    START_COMPARE: "compare",
    START_PLACEMENT: "placement",
    OPEN_VALIDATION: "validation"
  };
  return transitions[event];
}

export function deriveMapState(task: ProductTask, mapMode: MapMode, selection: SpatialSelection | null): MapState {
  if (mapMode === "plateau3d") return "detail3d";
  if (task === "validate") return "validation";
  if (task === "try") return "compare";
  return selection ? "focus" : "overview";
}
