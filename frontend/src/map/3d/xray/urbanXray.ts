import type { GeoJsonFeatureCollection } from "../../../types";
import { finiteNumber } from "../../../lib/format";

export const URBAN_XRAY_SEMANTICS = {
  label: "分析レイヤー",
  boundary: "実地形ではありません。既存のCITY GAP計算値を地形・建物から分離して表示します。",
  source: "exploratory_score_c",
} as const;

export interface UrbanXrayCell {
  meshCode: string;
  rawValue: number;
  normalizedIntensity: number;
  displayHeightM: number;
  source: "observed_analysis" | "scenario_analysis";
}

export function meshBounds(meshes: GeoJsonFeatureCollection, meshCode: string | null): [number, number, number, number] | null {
  if (!meshCode) return null;
  const feature = meshes.features.find((candidate) => String(candidate.properties?.mesh_code ?? "") === meshCode);
  const pairs = (function flatten(value: unknown): Array<[number, number]> {
    if (!Array.isArray(value)) return [];
    if (value.length >= 2 && Number.isFinite(value[0]) && Number.isFinite(value[1])) return [[Number(value[0]), Number(value[1])]];
    return value.flatMap(flatten);
  })(feature?.geometry?.coordinates);
  if (pairs.length === 0) return null;
  return [
    Math.min(...pairs.map((pair) => pair[0])),
    Math.min(...pairs.map((pair) => pair[1])),
    Math.max(...pairs.map((pair) => pair[0])),
    Math.max(...pairs.map((pair) => pair[1])),
  ];
}

export function buildUrbanXrayField(
  meshes: GeoJsonFeatureCollection,
  scenarioScores: Record<string, number> | null = null,
): Map<string, UrbanXrayCell> {
  const observations = meshes.features.flatMap((feature) => {
    const properties = feature.properties ?? {};
    const meshCode = String(properties.mesh_code ?? "");
    const scenarioValue = scenarioScores && Object.hasOwn(scenarioScores, meshCode)
      ? finiteNumber(scenarioScores[meshCode])
      : null;
    const observedValue = finiteNumber(properties.exploratory_score_c);
    const rawValue = scenarioValue ?? observedValue;
    return meshCode && rawValue !== null
      ? [{ meshCode, rawValue, source: scenarioValue === null ? "observed_analysis" as const : "scenario_analysis" as const }]
      : [];
  });
  const maximum = Math.max(...observations.map((item) => item.rawValue), 0.000001);
  return new Map(observations.map((item) => {
    const normalizedIntensity = Math.min(1, Math.max(0, item.rawValue / maximum));
    return [item.meshCode, {
      ...item,
      normalizedIntensity,
      displayHeightM: Number((10 + normalizedIntensity * 54).toFixed(3)),
    }];
  }));
}
