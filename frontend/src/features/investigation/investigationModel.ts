import type { AppData, MeshMetrics } from "../../types";
import {
  CANDIDATE_SELECTION_RULE_VERSION,
  FIELD_CHECK_RULE_VERSION,
  MUNICIPAL_REVIEW_STATUS,
} from "./investigationDomain";
import {
  BASE_DATA_GAPS,
  CANDIDATE_TYPE_COPY,
  VALUE_HYPOTHESES,
  plateauCoverageGap,
} from "./investigationCopy";
import { MEDICAL_SITE_LOCAL_CHECKS } from "./medicalSiteLocalRules";
import { TRANSPORT_WALKING_CHECKS } from "./transportWalkingRules";
import type {
  CandidateFact,
  CandidateType,
  DataGap,
  EditableFieldCheck,
  FieldCheckDefinition,
  FieldInvestigationSheetRecord,
  InvestigationCandidate,
  InvestigationWorkspace,
} from "./investigationTypes";

const ALL_CHECKS = [...TRANSPORT_WALKING_CHECKS, ...MEDICAL_SITE_LOCAL_CHECKS];

function finite(value: unknown, label: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`現地調査候補の${label}を確認できません`);
  return parsed;
}

function meshByCode(data: AppData, meshCode: string): MeshMetrics {
  const feature = data.meshes.features.find(
    (item) => String(item.properties?.mesh_code ?? "") === meshCode,
  );
  if (!feature?.properties) throw new Error(`500mメッシュ ${meshCode} を確認できません`);
  return { ...feature.properties, mesh_code: meshCode } as MeshMetrics;
}

function facts(mesh: MeshMetrics): InvestigationCandidate["facts"] {
  return [
    {
      id: "elderly",
      label: "65歳以上人口",
      value: finite(mesh.elderly_population, "65歳以上人口"),
      unit: "人",
      source: "国勢調査500mメッシュ",
      year: 2020,
    },
    {
      id: "transport",
      label: "最寄りの収録駅・バス停まで",
      value: finite(mesh.nearest_public_transport_distance_m, "交通距離"),
      unit: "m",
      source: "国土数値情報P11",
      year: 2022,
    },
    {
      id: "medical",
      label: "最寄りの収録医療施設まで",
      value: finite(mesh.nearest_medical_distance_m, "医療距離") / 1000,
      unit: "km",
      source: "国土数値情報P04",
      year: 2020,
    },
  ];
}

function sources(): InvestigationCandidate["sources"] {
  return [
    { id: "population", label: "国勢調査500mメッシュ", year: "2020", detail: "人口・65歳以上人口" },
    { id: "transport", label: "国土数値情報P11", year: "2022", detail: "駅・バス停位置" },
    { id: "medical", label: "国土数値情報P04", year: "2020", detail: "医療施設位置" },
    { id: "plateau", label: "PLATEAU 舞鶴市", year: "2025", detail: "建物・道路・DEM" },
    {
      id: "method",
      label: "CITY GAP算定",
      year: CANDIDATE_SELECTION_RULE_VERSION,
      detail: "500m候補抽出・現地調査準備",
    },
  ];
}

function checkRulesForCoverage(
  plateau: InvestigationCandidate["plateau"],
): FieldCheckDefinition[] {
  if (plateau.status === "verified") return ALL_CHECKS.map((check) => ({ ...check }));
  return ALL_CHECKS.map((check) =>
    check.origin !== "plateau_context"
      ? { ...check }
      : {
          ...check,
          origin: "data_gap",
          reason: `この候補にはPLATEAU詳細coverageがないため、${check.label.replace("確認", "現地確認")}が必要です。`,
          sourceGapIds: Array.from(new Set([...check.sourceGapIds, "plateau_coverage" as const])),
        },
  );
}

function candidate(
  data: AppData,
  meshCode: string,
  type: CandidateType,
  plateau: InvestigationCandidate["plateau"],
): InvestigationCandidate {
  const mesh = meshByCode(data, meshCode);
  const candidateFacts = facts(mesh);
  const typeCopy = CANDIDATE_TYPE_COPY[type];
  const dataGaps: DataGap[] =
    plateau.status === "verified"
      ? BASE_DATA_GAPS.map((gap) => ({ ...gap }))
      : [...BASE_DATA_GAPS.map((gap) => ({ ...gap })), plateauCoverageGap()];
  const name =
    meshCode === "533513314"
      ? "常団地前周辺"
      : String(mesh.area_label ?? `500mメッシュ ${meshCode}`);
  return {
    id: `maizuru-${meshCode}`,
    meshCode,
    name,
    type,
    typeLabel: typeCopy[0],
    typeExplanation: typeCopy[1],
    reason:
      `65歳以上人口${Math.round(candidateFacts[0].value)}人、` +
      `収録交通まで${Math.round(candidateFacts[1].value)}m、` +
      `収録医療まで${candidateFacts[2].value.toFixed(2)}kmが重なるため、追加確認する候補です。`,
    whyThisExample:
      meshCode === "533513314"
        ? "PLATEAUの建物・道路・地形が揃い、500mから街の構造まで確認できるため、詳細調査例として使用しています。最上位候補ではありません。"
        : null,
    longitude: finite(mesh.centroid_lon, "経度"),
    latitude: finite(mesh.centroid_lat, "緯度"),
    population: finite(mesh.population, "人口"),
    facts: candidateFacts,
    rank: finite(mesh.rank, "順位"),
    rankingDenominator: finite(
      data.summary.record_counts?.primary_rank_eligible_meshes,
      "ランキング母数",
    ),
    percentileDenominator: finite(
      data.summary.audit?.score_comparison_denominator,
      "percentile比較母数",
    ),
    cityIntersectingMeshCount: finite(
      data.summary.record_counts?.population_meshes_intersecting_city,
      "市境交差メッシュ数",
    ),
    plateau,
    knownFacts: [
      `500m人口 ${Math.round(finite(mesh.population, "人口"))}人（国勢調査2020）`,
      `最寄りの収録交通 ${Math.round(candidateFacts[1].value)}m（直線距離）`,
      `最寄りの収録医療 ${candidateFacts[2].value.toFixed(2)}km（直線距離）`,
    ],
    dataGaps,
    fieldChecks: checkRulesForCoverage(plateau),
    triageStatus: "unreviewed",
    municipalReviewStatus: MUNICIPAL_REVIEW_STATUS,
    sources: sources(),
  };
}

export function buildInvestigationWorkspace(data: AppData): InvestigationWorkspace {
  if (!data.finalDemo) {
    throw new Error("舞鶴市のPLATEAU現地調査データを確認できません");
  }
  const first = data.top10[0];
  const second = data.top10[1];
  if (!first || !second) {
    throw new Error("現地調査候補に必要な実データが不足しています");
  }
  const detailed = candidate(data, "533513314", "detailed_investigation", {
    status: "verified",
    buildings: finite(data.finalDemo.deep_dive.plateau_building_count, "PLATEAU建物数"),
    roads: finite(
      data.finalDemo.deep_dive.plateau_road_surfaces_intersecting_mesh,
      "PLATEAU道路数",
    ),
    terrain: "official_dem",
    message: "PLATEAU舞鶴市2025の建物・道路・DEMを確認できます。",
  });
  const screening = candidate(data, first.mesh_code, "screening", {
    status: "unavailable",
    buildings: null,
    roads: null,
    terrain: "unavailable",
    message:
      "500m分析は確認できますが、この範囲にはPLATEAU建物モデルがなく、建物・道路までの詳細調査はできません。",
  });
  const dataGap = candidate(data, second.mesh_code, "data_gap", {
    status: "unavailable",
    buildings: null,
    roads: null,
    terrain: "unavailable",
    message:
      "500m分析は確認できますが、PLATEAU建物と運行情報が不足しています。不足情報の確認を先に行います。",
  });
  return {
    cityName: data.city.name,
    selectionRuleVersion: CANDIDATE_SELECTION_RULE_VERSION,
    fieldCheckRuleVersion: FIELD_CHECK_RULE_VERSION,
    selectionRule: [
      "交通・医療アクセスの追加確認候補であること",
      "ランキング対象・比較母集団が明示できること",
      "PLATEAU詳細coverageとデータ不足を分けて扱うこと",
      "自動順位だけで確認済みにせず、人が仕分けること",
    ],
    candidates: [detailed, screening, dataGap],
    valueHypotheses: VALUE_HYPOTHESES,
  };
}

export function createEditableChecks(
  candidate: InvestigationCandidate,
): EditableFieldCheck[] {
  return candidate.fieldChecks.map((check) => ({
    ...check,
    status: "unconfirmed",
    assignee: "",
    dueDate: "",
    note: "",
    priority: check.defaultPriority,
  }));
}

export function createHumanCheck(
  label: string,
  sequence: number,
): EditableFieldCheck {
  const cleaned = label.trim();
  if (!cleaned) throw new Error("追加する確認項目を入力してください");
  return {
    id: `human-${sequence}`,
    category: "local",
    label: cleaned,
    reason: "自治体職員が地域事情に基づいて追加した確認項目です。",
    origin: "human",
    sourceGapIds: [],
    defaultPriority: "medium",
    priority: "medium",
    status: "unconfirmed",
    assignee: "",
    dueDate: "",
    note: "",
  };
}

export function createFieldSheet(
  candidate: InvestigationCandidate,
  checks = createEditableChecks(candidate),
  now = new Date(),
): FieldInvestigationSheetRecord {
  return {
    schemaVersion: "citygap-field-sheet-1.0.0",
    candidateId: candidate.id,
    meshCode: candidate.meshCode,
    candidateName: candidate.name,
    classification: "internal",
    ruleVersion: FIELD_CHECK_RULE_VERSION,
    candidateTriageStatus: candidate.triageStatus,
    updatedAt: now.toISOString(),
    checks,
    generalNote: "",
    gps: { latitude: null, longitude: null },
    investigationDate: "",
    photoReferences: [],
    municipalReview: {
      outcome: "unreviewed",
      responsibleDepartment: "",
      existingMeasures: "",
      missingData: "",
      discussionUse: "",
      originalResponse: "",
    },
  };
}

export function toPublicFieldSheet(sheet: FieldInvestigationSheetRecord) {
  return {
    schemaVersion: sheet.schemaVersion,
    candidateId: sheet.candidateId,
    meshCode: sheet.meshCode,
    candidateName: sheet.candidateName,
    ruleVersion: sheet.ruleVersion,
    checks: sheet.checks.map(
      ({ id, category, label, reason, origin, sourceGapIds }) => ({
        id,
        category,
        label,
        reason,
        origin,
        sourceGapIds,
      }),
    ),
  };
}

export function preserveMunicipalReviewOutcome(outcome: string): {
  status: "PARTIALLY_SUPPORTED" | "CONTRADICTED";
  outcome: string;
} {
  const contradicted = new Set([
    "既存施策で対応済み",
    "選定業務自体が存在しない",
    "現地調査票は不要",
    "対象外",
    "地域事情と異なる",
  ]);
  return {
    status: contradicted.has(outcome) ? "CONTRADICTED" : "PARTIALLY_SUPPORTED",
    outcome,
  };
}

export function isAutomaticConfirmationAllowed(): false {
  return false;
}

export function formatFact(fact: CandidateFact): string {
  const value =
    fact.unit === "km"
      ? fact.value.toFixed(2)
      : Math.round(fact.value).toLocaleString("ja-JP");
  return `${value}${fact.unit}`;
}
