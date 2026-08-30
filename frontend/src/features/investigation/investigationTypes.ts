export type CandidateType = "screening" | "detailed_investigation" | "data_gap";
export type HumanTriageStatus =
  | "unreviewed"
  | "additional_investigation"
  | "check_existing_measures"
  | "data_insufficient"
  | "field_check_in_progress"
  | "confirmed"
  | "out_of_scope";
export type MunicipalReviewOutcome =
  | "unreviewed"
  | "worth_checking"
  | "partially_useful"
  | "existing_measures"
  | "local_mismatch"
  | "data_insufficient"
  | "out_of_scope";

export interface MunicipalReviewRecord {
  outcome: MunicipalReviewOutcome;
  responsibleDepartment: string;
  existingMeasures: string;
  missingData: string;
  discussionUse: string;
  originalResponse: string;
}

export type CheckCategory = "transport" | "walking" | "medical" | "site" | "local";
export type CheckOrigin = "data_gap" | "analysis_assumption" | "plateau_context" | "human";
export type FieldCheckStatus = "unconfirmed" | "confirmed" | "follow_up" | "not_applicable";
export type ValueHypothesisStatus =
  | "ASSUMPTION"
  | "AWAITING_MUNICIPAL_REVIEW"
  | "PARTIALLY_SUPPORTED"
  | "SUPPORTED"
  | "CONTRADICTED"
  | "REJECTED";

export interface CandidateFact {
  id: "elderly" | "transport" | "medical";
  label: string;
  value: number;
  unit: "人" | "m" | "km";
  source: string;
  year: number;
}

export interface DataGap {
  id: "gtfs" | "walking_network" | "facility_availability" | "plateau_coverage" | "local_services";
  title: string;
  known: string;
  unknown: string;
  sourceBoundary: string;
}

export interface FieldCheckDefinition {
  id: string;
  category: CheckCategory;
  label: string;
  reason: string;
  origin: CheckOrigin;
  sourceGapIds: DataGap["id"][];
  defaultPriority: "high" | "medium" | "low";
}

export interface EditableFieldCheck extends FieldCheckDefinition {
  status: FieldCheckStatus;
  assignee: string;
  dueDate: string;
  note: string;
  priority: "high" | "medium" | "low";
}

export interface InvestigationCandidate {
  id: string;
  meshCode: string;
  name: string;
  type: CandidateType;
  typeLabel: string;
  typeExplanation: string;
  reason: string;
  whyThisExample: string | null;
  longitude: number;
  latitude: number;
  population: number;
  facts: [CandidateFact, CandidateFact, CandidateFact];
  rank: number;
  rankingDenominator: number;
  percentileDenominator: number;
  cityIntersectingMeshCount: number;
  plateau: {
    status: "verified" | "unavailable";
    buildings: number | null;
    roads: number | null;
    terrain: "official_dem" | "unavailable";
    message: string;
  };
  knownFacts: string[];
  dataGaps: DataGap[];
  fieldChecks: FieldCheckDefinition[];
  triageStatus: HumanTriageStatus;
  municipalReviewStatus: "AWAITING_MUNICIPAL_REVIEW";
  sources: Array<{ id: string; label: string; year: string; detail: string }>;
}

export interface InvestigationWorkspace {
  cityName: string;
  selectionRuleVersion: string;
  fieldCheckRuleVersion: string;
  selectionRule: string[];
  candidates: [InvestigationCandidate, InvestigationCandidate, InvestigationCandidate];
  valueHypotheses: Array<{
    id: "H1" | "H2" | "H3" | "H4";
    statement: string;
    status: ValueHypothesisStatus;
  }>;
}

export interface FieldInvestigationSheetRecord {
  schemaVersion: "citygap-field-sheet-1.0.0";
  candidateId: string;
  meshCode: string;
  candidateName: string;
  classification: "internal";
  ruleVersion: string;
  candidateTriageStatus: HumanTriageStatus;
  updatedAt: string;
  checks: EditableFieldCheck[];
  generalNote: string;
  gps: { latitude: number | null; longitude: number | null };
  investigationDate: string;
  photoReferences: string[];
  municipalReview: MunicipalReviewRecord;
}
