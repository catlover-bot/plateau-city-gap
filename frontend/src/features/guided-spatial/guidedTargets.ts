import type { GuidedReferenceData } from "../../lib/data";
import type { AppData, GeoJsonFeature, GeoJsonFeatureCollection } from "../../types";
import { EMPTY_GUIDED_COLLECTION, GUIDED_DEFAULT_AREA, exactOrAreaTarget } from "./guidedData";
import { GUIDED_CHECKS, type GuidedCheck } from "./guidedContent";
import type { GuidedAreaContext } from "./guidedTypes";

export type GuidedTargetKind = "road" | "building" | "facility" | "area";

export interface GuidedTargetChoice {
  key: string;
  kind: GuidedTargetKind;
  label: string;
  reason: string;
  geometry: GeoJsonFeatureCollection;
  resolution: "exact" | "area_fallback";
  checks: readonly GuidedCheck[];
}

function collection(feature: GeoJsonFeature): GeoJsonFeatureCollection {
  return { type: "FeatureCollection", features: [feature] };
}

function collectionBounds(area: GeoJsonFeatureCollection): [number, number, number, number] | null {
  const coordinates: number[][] = [];
  const visit = (value: unknown): void => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") {
      coordinates.push([value[0], value[1]]);
      return;
    }
    value.forEach(visit);
  };
  area.features.forEach((feature) => visit(feature.geometry?.coordinates));
  if (!coordinates.length) return null;
  return [
    Math.min(...coordinates.map(([longitude]) => longitude)),
    Math.min(...coordinates.map(([, latitude]) => latitude)),
    Math.max(...coordinates.map(([longitude]) => longitude)),
    Math.max(...coordinates.map(([, latitude]) => latitude)),
  ];
}

function firstFacilityInArea(
  data: Pick<GuidedReferenceData, "stations" | "busStops" | "medicalFacilities">,
  area: GeoJsonFeatureCollection,
): GeoJsonFeature | null {
  const bounds = collectionBounds(area);
  if (!bounds) return null;
  const [west, south, east, north] = bounds;
  const sources = [data.stations, data.busStops, data.medicalFacilities];
  return sources.flatMap((source) => source?.features ?? []).find((feature) => {
    const coordinates = feature.geometry?.type === "Point" ? feature.geometry.coordinates : null;
    return Array.isArray(coordinates)
      && typeof coordinates[0] === "number"
      && typeof coordinates[1] === "number"
      && coordinates[0] >= west && coordinates[0] <= east
      && coordinates[1] >= south && coordinates[1] <= north;
  }) ?? null;
}

interface TargetChoiceInput {
  activeContext: GuidedAreaContext | null;
  area: GeoJsonFeatureCollection;
  areaId: string;
  areaLabel: string;
  data: AppData;
  referenceData: GuidedReferenceData | null;
}

export function buildGuidedTargetChoices({
  activeContext,
  area,
  areaId,
  areaLabel,
  data,
  referenceData,
}: TargetChoiceInput): GuidedTargetChoice[] {
  const choices: GuidedTargetChoice[] = [];
  const defaultTarget = exactOrAreaTarget(activeContext, area);
  if (defaultTarget.resolution === "exact" && defaultTarget.geometry.features[0]) {
    choices.push({
      key: `road:${String(defaultTarget.geometry.features[0].id ?? GUIDED_DEFAULT_AREA)}`,
      kind: "road",
      label: "京月中央通線の道路面",
      reason: "通れない区間があれば、直線距離による候補判断が変わります。",
      geometry: defaultTarget.geometry,
      resolution: "exact",
      checks: GUIDED_CHECKS.road,
    });
  }

  const building = activeContext?.layers.buildings.features[0];
  if (building) {
    choices.push({
      key: `building:${String(building.id ?? building.properties?.object_id)}`,
      kind: "building",
      label: "範囲内のPLATEAU建物",
      reason: "建物の形が分かっても、入口と現在の利用状況はデータだけでは判断できません。",
      geometry: collection(building),
      resolution: "exact",
      checks: GUIDED_CHECKS.building,
    });
  }

  const facility = firstFacilityInArea(referenceData ?? data, area);
  if (facility) {
    choices.push({
      key: `facility:${String(facility.id ?? facility.properties?.id)}`,
      kind: "facility",
      label: String(facility.properties?.name ?? "範囲内の登録施設"),
      reason: "登録地点が分かっても、現在の利用可否や入口まではデータだけでは判断できません。",
      geometry: collection(facility),
      resolution: "exact",
      checks: GUIDED_CHECKS.facility,
    });
  }

  const areaChoice: GuidedTargetChoice = {
    key: `area:${areaId}`,
    kind: "area",
    label: `${areaLabel}の500m範囲`,
    reason: "個別対象を根拠付きで解決できない場合は、別地域の対象で補わず選択範囲を示します。",
    geometry: area,
    resolution: "area_fallback",
    checks: GUIDED_CHECKS.road,
  };
  if (choices[0]?.kind === "road") choices.push(areaChoice);
  else choices.unshift(areaChoice);
  return choices;
}

export function labeledGuidedTarget(target: GuidedTargetChoice | undefined): GeoJsonFeatureCollection {
  if (!target) return EMPTY_GUIDED_COLLECTION;
  return {
    type: "FeatureCollection",
    features: target.geometry.features.map((feature) => ({
      ...feature,
      properties: {
        ...(feature.properties ?? {}),
        map_label: target.label,
        target_kind: target.kind,
      },
    })),
  };
}
