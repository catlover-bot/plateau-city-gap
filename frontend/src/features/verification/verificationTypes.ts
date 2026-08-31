import type { DataGap, InvestigationCandidate } from "../investigation/investigationTypes";

export type PublicVerificationKind =
  | "gtfs_service"
  | "walking_connectivity"
  | "facility_availability"
  | "local_service_context";

export type PublicTargetScope = "mesh" | "plateau_object" | "plateau_object_group";
export type PublicTargetObjectType = "mesh" | "building" | "road" | "facility";

export interface PublicVerificationTarget {
  scope: PublicTargetScope;
  objectType: PublicTargetObjectType;
  sourceObjectId: string;
  label: string;
  datasetVersion: string;
  spatialPackId: string | null;
  role: "primary" | "context";
  provenance: string;
  isPlateauObject: boolean;
}

export interface PublicEvidenceRequirement {
  key: string;
  label: string;
  inputType: "choice" | "text" | "photo";
  relevantWhen?: string;
}

export interface PublicVerificationTask {
  id: string;
  kind: PublicVerificationKind;
  status: "unverified";
  statusLabel: "未確認";
  sourceGap: DataGap;
  importance: string;
  reason: string;
  targets: PublicVerificationTarget[];
  requirements: PublicEvidenceRequirement[];
}

export interface PublicVerificationLoop {
  schemaVersion: "citygap.public-verification-loop@1";
  ruleVersion: "citygap-field-verification@1.0.0";
  findingId: string;
  candidate: InvestigationCandidate;
  tasks: PublicVerificationTask[];
  validation: {
    human: "AWAITING_HUMAN_TEST";
    municipal: "AWAITING_MUNICIPAL_REVIEW";
  };
}
