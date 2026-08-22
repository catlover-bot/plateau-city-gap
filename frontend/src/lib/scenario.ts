import proj4 from "proj4";

import type { MeshMetrics } from "../types";

const WGS84 = "EPSG:4326";
const JGD2011_ZONE_VI =
  "+proj=tmerc +lat_0=36 +lon_0=136 +k=0.9999 +x_0=0 +y_0=0 +ellps=GRS80 +units=m +no_defs +type=crs";

export interface VirtualPoint {
  longitude: number;
  latitude: number;
}

export interface ScenarioMeshResult {
  meshCode: string;
  beforeDistanceM: number;
  afterDistanceM: number;
  beforeTransportPercentile: number;
  afterTransportPercentile: number;
  beforeScore: number;
  afterScore: number;
  scoreReduction: number;
  improvementRate: number;
  elderlyPopulation: number;
  distanceImproved: boolean;
}

export interface ScenarioResult {
  point: VirtualPoint;
  meshes: ScenarioMeshResult[];
  comparisonMeshCount: number;
  improvedMeshCount: number;
  affectedElderlyPopulation: number;
  mostImproved: ScenarioMeshResult[];
}

interface Candidate {
  mesh: MeshMetrics;
  meshCode: string;
  distance: number;
  newDistance: number;
  elderlyPercentile: number;
  medicalPercentile: number;
  transportPercentile: number;
  score: number;
  elderlyPopulation: number;
}

const finite = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

export const projectToAnalysisCrs = (point: VirtualPoint): [number, number] =>
  proj4(WGS84, JGD2011_ZONE_VI, [point.longitude, point.latitude]) as [number, number];

export const percentileRanks = (values: number[]): number[] => {
  if (values.length === 0) return [];
  const positions = values
    .map((value, index) => ({ value, index }))
    .sort((left, right) => left.value - right.value);
  const ranks = new Array<number>(values.length);
  let start = 0;
  while (start < positions.length) {
    let end = start;
    while (end + 1 < positions.length && positions[end + 1].value === positions[start].value) {
      end += 1;
    }
    // pandas rank(method="average", pct=True): one-based average rank / n.
    const percentile = ((start + 1 + (end + 1)) / 2) / positions.length;
    for (let cursor = start; cursor <= end; cursor += 1) {
      ranks[positions[cursor].index] = percentile;
    }
    start = end + 1;
  }
  return ranks;
};

const toCandidate = (
  mesh: MeshMetrics,
  virtualProjected: [number, number],
): Candidate | null => {
  if (
    !finite(mesh.centroid_lon) ||
    !finite(mesh.centroid_lat) ||
    !finite(mesh.nearest_public_transport_distance_m) ||
    !finite(mesh.elderly_population_percentile) ||
    !finite(mesh.transport_distance_percentile) ||
    !finite(mesh.medical_distance_percentile) ||
    !finite(mesh.exploratory_score_c)
  ) {
    return null;
  }
  const [meshX, meshY] = projectToAnalysisCrs({
    longitude: mesh.centroid_lon,
    latitude: mesh.centroid_lat,
  });
  const distanceToVirtual = Math.hypot(meshX - virtualProjected[0], meshY - virtualProjected[1]);
  return {
    mesh,
    meshCode: String(mesh.mesh_code),
    distance: mesh.nearest_public_transport_distance_m,
    newDistance: Math.min(mesh.nearest_public_transport_distance_m, distanceToVirtual),
    elderlyPercentile: mesh.elderly_population_percentile,
    medicalPercentile: mesh.medical_distance_percentile,
    transportPercentile: mesh.transport_distance_percentile,
    score: mesh.exploratory_score_c,
    elderlyPopulation: finite(mesh.elderly_population) ? mesh.elderly_population : 0,
  };
};

export const calculateScenario = (
  meshes: MeshMetrics[],
  point: VirtualPoint,
): ScenarioResult => {
  const virtualProjected = projectToAnalysisCrs(point);
  const candidates = meshes
    .map((mesh) => toCandidate(mesh, virtualProjected))
    .filter((candidate): candidate is Candidate => candidate !== null);
  const afterPercentiles = percentileRanks(candidates.map((candidate) => candidate.newDistance));
  const results = candidates.map((candidate, index): ScenarioMeshResult => {
    const afterScore =
      candidate.elderlyPercentile * afterPercentiles[index] * candidate.medicalPercentile;
    const scoreReduction = candidate.score - afterScore;
    return {
      meshCode: candidate.meshCode,
      beforeDistanceM: candidate.distance,
      afterDistanceM: candidate.newDistance,
      beforeTransportPercentile: candidate.transportPercentile,
      afterTransportPercentile: afterPercentiles[index],
      beforeScore: candidate.score,
      afterScore,
      scoreReduction,
      improvementRate: candidate.score > 0 ? scoreReduction / candidate.score : 0,
      elderlyPopulation: candidate.elderlyPopulation,
      distanceImproved: candidate.newDistance < candidate.distance - 1e-6,
    };
  });
  const improved = results.filter((result) => result.distanceImproved);
  return {
    point,
    meshes: results,
    comparisonMeshCount: candidates.length,
    improvedMeshCount: improved.length,
    affectedElderlyPopulation: improved.reduce(
      (total, result) => total + result.elderlyPopulation,
      0,
    ),
    mostImproved: [...results]
      .filter((result) => result.scoreReduction > 1e-12)
      .sort((left, right) => right.scoreReduction - left.scoreReduction)
      .slice(0, 5),
  };
};
