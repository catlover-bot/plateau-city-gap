import type { DataGap, InvestigationCandidate } from "../investigation/investigationTypes";
import type {
  PublicEvidenceRequirement,
  PublicVerificationKind,
  PublicVerificationLoop,
  PublicVerificationTarget,
} from "./verificationTypes";

export const PUBLIC_SPATIAL_PACK_ID = "maizuru-533513314-plateau-2025-v1";
export const PUBLIC_VERIFICATION_RULE_VERSION = "citygap-field-verification@1.0.0";

const PHOTO_REQUIREMENTS: PublicEvidenceRequirement[] = [
  { key: "close_photo", label: "対象の近景を記録する", inputType: "photo" },
  { key: "context_photo", label: "周辺を含む全景を記録する", inputType: "photo" },
];

const REQUIREMENTS: Record<PublicVerificationKind, PublicEvidenceRequirement[]> = {
  gtfs_service: [
    { key: "stop_present", label: "停留所が現地に存在するか", inputType: "choice" },
    { key: "service_notice", label: "運行案内を確認できるか", inputType: "choice" },
    ...PHOTO_REQUIREMENTS,
    {
      key: "removal_or_alternative",
      label: "停留所がなければ撤去痕跡・代替位置を記録する",
      inputType: "text",
      relevantWhen: "stop_present=no",
    },
  ],
  walking_connectivity: [
    { key: "walkable", label: "対象経路を実際に通行できるか", inputType: "choice" },
    { key: "barrier", label: "横断・段差・通行止めがあるか", inputType: "choice" },
    ...PHOTO_REQUIREMENTS,
  ],
  facility_availability: [
    { key: "facility_open", label: "施設が現在利用できるか", inputType: "choice" },
    { key: "entrance_access", label: "入口まで到達できるか", inputType: "choice" },
    ...PHOTO_REQUIREMENTS,
    {
      key: "closure_notice",
      label: "閉鎖時は掲示・移転先の手掛かりを記録する",
      inputType: "text",
      relevantWhen: "facility_open=no",
    },
  ],
  local_service_context: [
    { key: "service_present", label: "公開データにない送迎等があるか", inputType: "choice" },
    { key: "access_condition", label: "利用条件や対象者を記録する", inputType: "text" },
    ...PHOTO_REQUIREMENTS,
  ],
};

const GAP_KIND: Record<DataGap["id"], PublicVerificationKind | null> = {
  gtfs: "gtfs_service",
  walking_network: "walking_connectivity",
  facility_availability: "facility_availability",
  local_services: "local_service_context",
  plateau_coverage: null,
};

const IMPORTANCE: Record<PublicVerificationKind, string> = {
  gtfs_service: "運行がなければ、距離が近くても交通手段として使えません。",
  walking_connectivity: "通れない区間があれば、直線距離による候補判断が変わります。",
  facility_availability: "利用できなければ、医療への近さを支援条件として扱えません。",
  local_service_context: "既存の送迎等があれば、新たな支援の必要性や対象が変わります。",
};

function meshFallback(candidate: InvestigationCandidate): PublicVerificationTarget {
  return {
    scope: "mesh",
    objectType: "mesh",
    sourceObjectId: candidate.meshCode,
    label: `${candidate.name} 500mメッシュ`,
    datasetVersion: "CITY GAP Maizuru mesh metrics / source years 2020–2025",
    spatialPackId: null,
    role: "primary",
    provenance: "frontend/public/data/mesh_metrics.geojson",
    isPlateauObject: false,
  };
}

function targets(
  candidate: InvestigationCandidate,
  kind: PublicVerificationKind,
): PublicVerificationTarget[] {
  if (candidate.plateau.status !== "verified") return [meshFallback(candidate)];

  if (kind === "gtfs_service") {
    return [{
      scope: "plateau_object",
      objectType: "facility",
      sourceObjectId: "bus-071",
      label: "常団地前バス停",
      datasetVersion: "国土数値情報 P11 2022 / CITY GAP tracked derivative",
      spatialPackId: PUBLIC_SPATIAL_PACK_ID,
      role: "primary",
      provenance: "objects.json facility object",
      isPlateauObject: false,
    }];
  }

  if (kind === "walking_connectivity") {
    return [{
      scope: "plateau_object",
      objectType: "road",
      sourceObjectId: "tran_05dbefba-6a77-40ea-88ac-a568a63a2f05-0",
      label: "京月中央通線の道路面",
      datasetVersion: "Project PLATEAU 舞鶴市2025 道路LOD1",
      spatialPackId: PUBLIC_SPATIAL_PACK_ID,
      role: "primary",
      provenance: "objects.json road object",
      isPlateauObject: true,
    }];
  }

  if (kind === "facility_availability") {
    return [
      {
        scope: "plateau_object",
        objectType: "facility",
        sourceObjectId: "medical-105",
        label: "鹿野医院（収録医療施設点）",
        datasetVersion: "国土数値情報 P04 2020 / CITY GAP tracked derivative",
        spatialPackId: PUBLIC_SPATIAL_PACK_ID,
        role: "primary",
        provenance: "objects.json facility object",
        isPlateauObject: false,
      },
      {
        scope: "plateau_object_group",
        objectType: "building",
        sourceObjectId: "bldg_00962182-17d0-4fde-8970-784dd489dcf5",
        label: "対象メッシュの住宅建物群（代表object）",
        datasetVersion: "Project PLATEAU 舞鶴市2025 建築物LOD1",
        spatialPackId: PUBLIC_SPATIAL_PACK_ID,
        role: "context",
        provenance: "objects.json building object; context only",
        isPlateauObject: true,
      },
    ];
  }

  return [meshFallback(candidate)];
}

export function buildPublicVerificationLoop(
  candidate: InvestigationCandidate,
): PublicVerificationLoop {
  const tasks = candidate.dataGaps
    .slice(0, 4)
    .flatMap((sourceGap) => {
      const kind = GAP_KIND[sourceGap.id];
      if (!kind) return [];
      return [{
        id: `${candidate.id}-${kind}`,
        kind,
        status: "unverified" as const,
        statusLabel: "未確認" as const,
        sourceGap,
        importance: IMPORTANCE[kind],
        reason: `${sourceGap.unknown}を公開データだけでは判断できないため。`,
        targets: targets(candidate, kind),
        requirements: REQUIREMENTS[kind].map((requirement) => ({ ...requirement })),
      }];
    });

  return {
    schemaVersion: "citygap.public-verification-loop@1",
    ruleVersion: PUBLIC_VERIFICATION_RULE_VERSION,
    findingId: `mesh-${candidate.meshCode}-accessibility-gap`,
    candidate,
    tasks,
    validation: {
      human: "AWAITING_HUMAN_TEST",
      municipal: "AWAITING_MUNICIPAL_REVIEW",
    },
  };
}
