import type { GeoJsonFeatureCollection } from "../../../types";
import { finiteNumber } from "../../../lib/format";

export type CounterfactualState = "baseline" | "scenario" | "stress";

export interface CounterfactualMeshChange {
  meshCode: string;
  before: number;
  after: number;
  delta: number;
  changed: boolean;
}

export const COUNTERFACTUAL_BOUNDARY = "実在都市の改変ではなく、同じ都市・camera・選択対象で計算条件の差だけを比較します。";

export function deriveCounterfactualChanges(
  meshes: GeoJsonFeatureCollection,
  afterScores: Record<string, number> | null,
  tolerance = 0.000001,
): Map<string, CounterfactualMeshChange> {
  if (!afterScores) return new Map();
  return new Map(meshes.features.flatMap((feature) => {
    const properties = feature.properties ?? {};
    const meshCode = String(properties.mesh_code ?? "");
    const before = finiteNumber(properties.exploratory_score_c);
    const after = meshCode && Object.hasOwn(afterScores, meshCode) ? finiteNumber(afterScores[meshCode]) : null;
    if (!meshCode || before === null || after === null) return [];
    const delta = Number((after - before).toFixed(9));
    return [[meshCode, { meshCode, before, after, delta, changed: Math.abs(delta) > tolerance }]];
  }));
}
