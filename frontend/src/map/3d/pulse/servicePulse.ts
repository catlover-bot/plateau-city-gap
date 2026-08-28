import type { WorkspaceMapData } from "../../../types";
import { finiteNumber } from "../../../lib/format";

export const SERVICE_PULSE_SEMANTICS = {
  quantity: "network_distance",
  boundary: "道路面の隣接関係によるnetwork distanceです。移動時間・歩行時間・到達保証ではありません。",
  units: "m",
} as const;

export interface ServicePulseRoute {
  id: string;
  storyId: "scenario_a" | "scenario_b" | "scenario_c";
  routeKind: "before" | "after";
  coordinates: Array<[number, number]>;
  networkDistanceM: number;
  destinationName: string | null;
  routeSemantics: string;
  distanceBandsM: number[];
}

const STORY_IDS = new Set(["scenario_a", "scenario_b", "scenario_c"]);

export function distanceBands(distanceM: number): number[] {
  if (!Number.isFinite(distanceM) || distanceM <= 0) return [];
  const bands = [500, 1000, 2000].filter((threshold) => threshold < distanceM);
  return [...bands, Number(distanceM.toFixed(3))];
}

export function formatNetworkDistance(distanceM: number): string {
  return distanceM >= 1000
    ? `${Number((distanceM / 1000).toFixed(1))} km`
    : `${Math.round(distanceM)} m`;
}

export function extractServicePulseRoutes(
  workspace: WorkspaceMapData | null,
  storyId: "scenario_a" | "scenario_b" | "scenario_c",
): ServicePulseRoute[] {
  if (!workspace || !STORY_IDS.has(storyId)) return [];
  return workspace.features.flatMap((feature) => {
    const properties = feature.properties ?? {};
    const featureStory = String(properties.story_id ?? "");
    const kind = String(properties.route_kind ?? "");
    const distance = finiteNumber(properties.network_distance_m);
    const coordinates = feature.geometry?.type === "LineString" && Array.isArray(feature.geometry.coordinates)
      ? feature.geometry.coordinates.filter((item): item is [number, number] => (
        Array.isArray(item) && item.length >= 2 && Number.isFinite(item[0]) && Number.isFinite(item[1])
      ))
      : [];
    if (
      properties.layer_type !== "representative_route"
      || featureStory !== storyId
      || (kind !== "before" && kind !== "after")
      || distance === null
      || coordinates.length < 2
    ) return [];
    return [{
      id: String(feature.id ?? `${featureStory}:${kind}`),
      storyId,
      routeKind: kind,
      coordinates,
      networkDistanceM: distance,
      destinationName: typeof properties.destination_name === "string" ? properties.destination_name : null,
      routeSemantics: String(properties.route_semantics ?? "unknown_network_model"),
      distanceBandsM: distanceBands(distance),
    }];
  });
}
