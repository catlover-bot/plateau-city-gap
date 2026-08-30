import { useEffect, useMemo, useRef, useState } from "react";
import type { AppData } from "../../types";
import type {
  GuidedStep,
  SpatialSelection,
  SpatialState,
  SpatialViewport,
} from "../../state/spatial/types";
import { AnalyticalMap } from "../../map/2d/AnalyticalMap";
import { Plateau3DMap } from "../../map/3d/Plateau3DMap";
import { UrbanSection } from "../urban-section/UrbanSection";
import {
  loadLocalInvestigationSheet,
  saveLocalInvestigationSheet,
} from "../../lib/fieldOffline";
import {
  createFieldSheet,
  createHumanCheck,
} from "./investigationModel";
import {
  isHumanTriageStatus,
  isMunicipalReviewOutcome,
} from "./investigationDomain";
import {
  CandidateBrief,
  CandidateShortlist,
  DataGapList,
  PlateauFieldContext,
} from "./CandidatePanels";
import {
  FieldChecklist,
  FieldInvestigationSheet,
  InvestigationSummary,
} from "./FieldPanels";
import { InvestigationHeader } from "./ValueLanding";
import type {
  EditableFieldCheck,
  FieldInvestigationSheetRecord,
  InvestigationCandidate,
  InvestigationWorkspace,
} from "./investigationTypes";

const STEP_TITLES: Record<GuidedStep, string> = {
  1: "どこを確認する？",
  2: "なぜ確認する？",
  3: "街のどこを見る？",
  4: "何を確認する？",
  5: "現地調査票を作る",
  6: "庁内で共有する",
};

const NEXT_LABELS: Record<1 | 2 | 3 | 4 | 5, string> = {
  1: "候補理由を見る",
  2: "街の構造を見る",
  3: "確認項目を見る",
  4: "現地確認を開始",
  5: "調査サマリーを見る",
};

interface Props {
  data: AppData;
  workspace: InvestigationWorkspace;
  candidate: InvestigationCandidate;
  state: SpatialState;
  activeLayerIds: string[];
  onCandidateSelect(candidate: InvestigationCandidate): void;
  onBack(): void;
  onNext(): void;
  onRestart(): void;
  onOpenAdvanced(): void;
  onSelectionChange(selection: SpatialSelection | null): void;
  onViewportChange(viewport: SpatialViewport): void;
  onSelectBuilding(id: string, properties: Record<string, unknown>): void;
}

function sheetFromStoredContent(
  value: Record<string, unknown>,
  candidate: InvestigationCandidate,
): FieldInvestigationSheetRecord | null {
  const sheet = value as unknown as FieldInvestigationSheetRecord;
  if (
    sheet.schemaVersion !== "citygap-field-sheet-1.0.0" ||
    sheet.classification !== "internal" ||
    sheet.candidateId !== candidate.id ||
    !Array.isArray(sheet.checks)
  ) {
    return null;
  }
  return {
    ...sheet,
    candidateTriageStatus: isHumanTriageStatus(sheet.candidateTriageStatus)
      ? sheet.candidateTriageStatus
      : candidate.triageStatus,
    photoReferences: Array.isArray(sheet.photoReferences) ? sheet.photoReferences : [],
    municipalReview: {
      outcome: isMunicipalReviewOutcome(sheet.municipalReview?.outcome)
        ? sheet.municipalReview.outcome
        : "unreviewed",
      responsibleDepartment:
        typeof sheet.municipalReview?.responsibleDepartment === "string"
          ? sheet.municipalReview.responsibleDepartment
          : "",
      existingMeasures:
        typeof sheet.municipalReview?.existingMeasures === "string"
          ? sheet.municipalReview.existingMeasures
          : "",
      missingData:
        typeof sheet.municipalReview?.missingData === "string"
          ? sheet.municipalReview.missingData
          : "",
      discussionUse:
        typeof sheet.municipalReview?.discussionUse === "string"
          ? sheet.municipalReview.discussionUse
          : "",
      originalResponse:
        typeof sheet.municipalReview?.originalResponse === "string"
          ? sheet.municipalReview.originalResponse
          : "",
    },
  };
}

export function InvestigationJourney({
  data,
  workspace,
  candidate,
  state,
  activeLayerIds,
  onCandidateSelect,
  onBack,
  onNext,
  onRestart,
  onOpenAdvanced,
  onSelectionChange,
  onViewportChange,
  onSelectBuilding,
}: Props) {
  const step = state.guidedStep;
  const titleRef = useRef<HTMLHeadingElement>(null);
  const [sheet, setSheet] = useState<FieldInvestigationSheetRecord>(
    () => createFieldSheet(candidate),
  );
  const [sheetReady, setSheetReady] = useState(false);
  const [saveStatus, setSaveStatus] = useState("");
  const mapUsesPlateau = step === 3 && candidate.plateau.status === "verified";
  const mapLayerIds = useMemo(
    () => ["reference-gsi-pale", "analysis-city-gap", "infra-stations", "infra-medical"],
    [],
  );

  useEffect(() => {
    titleRef.current?.focus();
  }, [step]);

  useEffect(() => {
    let cancelled = false;
    const fresh = createFieldSheet(candidate);
    setSheetReady(false);
    setSheet(fresh);
    setSaveStatus("端末内の保存済み調査票を確認しています");
    if (typeof indexedDB === "undefined") {
      setSheetReady(true);
      setSaveStatus("この環境では端末内保存を利用できません");
      return () => {
        cancelled = true;
      };
    }
    void loadLocalInvestigationSheet(candidate.id)
      .then((stored) => {
        if (cancelled) return;
        const loaded = stored ? sheetFromStoredContent(stored.content, candidate) : null;
        setSheet(loaded ?? fresh);
        setSheetReady(true);
        setSaveStatus(loaded ? "この端末の保存内容を復元しました" : "未保存の新しい調査票です");
      })
      .catch(() => {
        if (!cancelled) {
          setSheetReady(true);
          setSaveStatus("保存内容を読み込めませんでした。入力は続けられます");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [candidate]);

  useEffect(() => {
    if (step !== 6 || !sheetReady || typeof indexedDB === "undefined") return undefined;
    const timeout = window.setTimeout(() => {
      const updatedAt = new Date().toISOString();
      void saveLocalInvestigationSheet({
        sheet_id: `${sheet.candidateId}-local`,
        candidate_id: sheet.candidateId,
        updated_at: updatedAt,
        classification: "internal",
        content: { ...sheet, updatedAt } as unknown as Record<string, unknown>,
      })
        .then(() => setSaveStatus("レビュー入力をこの端末に自動保存しました"))
        .catch(() => setSaveStatus("レビュー入力を端末内に保存できませんでした"));
    }, 500);
    return () => window.clearTimeout(timeout);
  }, [sheet, sheetReady, step]);

  const patchSheet = (patch: Partial<FieldInvestigationSheetRecord>) => {
    if (step === 6) setSaveStatus("レビュー入力を保存しています");
    setSheet((current) => ({
      ...current,
      ...patch,
      updatedAt: new Date().toISOString(),
    }));
  };

  const patchCheck = (id: string, patch: Partial<EditableFieldCheck>) => {
    setSheet((current) => ({
      ...current,
      updatedAt: new Date().toISOString(),
      checks: current.checks.map((check) =>
        check.id === id ? { ...check, ...patch } : check,
      ),
    }));
  };

  const removeCheck = (id: string) => {
    setSheet((current) => ({
      ...current,
      updatedAt: new Date().toISOString(),
      checks: current.checks.filter((check) => check.id !== id),
    }));
  };

  const addCheck = (label: string) => {
    const humanCount = sheet.checks.filter((check) => check.origin === "human").length;
    const check = createHumanCheck(label, humanCount + 1);
    setSheet((current) => ({
      ...current,
      updatedAt: new Date().toISOString(),
      checks: [...current.checks, check],
    }));
  };

  const saveSheet = async () => {
    const updated = { ...sheet, updatedAt: new Date().toISOString() };
    setSheet(updated);
    try {
      await saveLocalInvestigationSheet({
        sheet_id: `${updated.candidateId}-local`,
        candidate_id: updated.candidateId,
        updated_at: updated.updatedAt,
        classification: "internal",
        content: updated as unknown as Record<string, unknown>,
      });
      setSaveStatus("この端末に保存しました。通信がなくても再表示できます");
    } catch {
      setSaveStatus("端末内に保存できませんでした。印刷して保持できます");
    }
  };

  const captureGps = () => {
    if (!navigator.geolocation) {
      setSaveStatus("この端末では現在地を取得できません");
      return;
    }
    setSaveStatus("現在地を確認しています");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        patchSheet({
          gps: {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          },
        });
        setSaveStatus("現在地を調査票に記録しました");
      },
      () => setSaveStatus("現在地を取得できませんでした。位置情報の許可を確認してください"),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setSaveStatus("この候補のURLをコピーしました。内部メモはURLに含みません");
    } catch {
      setSaveStatus("URLをコピーできませんでした");
    }
  };

  return (
    <div
      className="product-app investigation-journey"
      data-experience="guided"
      data-investigation-step={step}
      data-candidate-type={candidate.type}
    >
      <InvestigationHeader onRestart={onRestart} />
      <main className="investigation-body">
        <section className="investigation-map-stage" aria-label="選択した現地調査候補の地図">
          {mapUsesPlateau ? (
            <>
              <Plateau3DMap
                data={data}
                selection={state.selection}
                viewport={state.viewport}
                activeLayerIds={activeLayerIds}
                scenePreset={state.scenePreset}
                analysisLens={state.analysisLens}
                counterfactualState={state.counterfactualState}
                showUrbanSection
                uiMode="guided"
                preferredBuildingSource="spatial-pack"
                onSelectionChange={onSelectionChange}
              />
              <UrbanSection
                open
                mode="guided"
                selection={state.selection}
                counterfactualState={state.counterfactualState}
                analysisLens={state.analysisLens}
                onClose={() => undefined}
                onSelectBuilding={onSelectBuilding}
              />
            </>
          ) : (
            <AnalyticalMap
              data={data}
              validation={null}
              preset="discovery"
              primaryLayer="analysis-city-gap"
              activeLayerIdsOverride={mapLayerIds}
              selection={state.selection}
              viewport={state.viewport}
              dimNonSelected
              interactive
              ariaLabel={`舞鶴市の現地調査候補地図。${candidate.name}を表示しています`}
              onSelectionChange={onSelectionChange}
              onViewportChange={onViewportChange}
            />
          )}
          <div className="investigation-map-caption">
            <span>{mapUsesPlateau ? "PLATEAU 建物・道路・地形" : "500m候補地図"}</span>
            <strong>{candidate.name}</strong>
            <small>
              {candidate.plateau.status === "verified"
                ? `建物${candidate.plateau.buildings}棟・道路${candidate.plateau.roads}面・公式DEM`
                : "PLATEAU詳細なし。データ不足として保持"}
            </small>
          </div>
        </section>

        <article className="investigation-step-sheet" aria-labelledby="investigation-step-title">
          <div className="investigation-progress">
            <span>{step} / 6</span>
            <ol aria-label="現地調査準備の進み具合">
              {([1, 2, 3, 4, 5, 6] as GuidedStep[]).map((item) => (
                <li
                  key={item}
                  aria-current={item === step ? "step" : undefined}
                  aria-label={`${item} / 6 ${STEP_TITLES[item]}`}
                >
                  <span aria-hidden="true">{item}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="investigation-step-content">
            <h1 id="investigation-step-title" ref={titleRef} tabIndex={-1} className="step-accessible-title">
              {STEP_TITLES[step]}
            </h1>
            {step === 1 && (
              <CandidateShortlist
                workspace={workspace}
                selectedId={candidate.id}
                onSelect={onCandidateSelect}
              />
            )}
            {step === 2 && (
              <>
                <CandidateBrief
                  candidate={candidate}
                  triageStatus={sheet.candidateTriageStatus}
                  onTriageChange={(candidateTriageStatus) => patchSheet({ candidateTriageStatus })}
                />
                <DataGapList candidate={candidate} />
              </>
            )}
            {step === 3 && <PlateauFieldContext candidate={candidate} />}
            {step === 4 && <FieldChecklist candidate={candidate} />}
            {step === 5 && (
              <>
                <FieldInvestigationSheet
                  candidate={candidate}
                  sheet={sheet}
                  onSheetChange={patchSheet}
                  onCheckChange={patchCheck}
                  onRemoveCheck={removeCheck}
                  onAddCheck={addCheck}
                  onSave={() => void saveSheet()}
                  onGps={captureGps}
                />
                <p className="local-save-status" role="status" aria-live="polite">{saveStatus}</p>
              </>
            )}
            {step === 6 && (
              <>
                <InvestigationSummary
                  candidate={candidate}
                  sheet={sheet}
                  onSheetChange={patchSheet}
                />
                <p className="local-save-status" role="status" aria-live="polite">{saveStatus}</p>
              </>
            )}
          </div>

          <footer className="investigation-actions">
            <button type="button" className="investigation-back" onClick={onBack}>
              {step === 1 ? "入口へ戻る" : "戻る"}
            </button>
            {(step === 5 || step === 6) && (
              <button type="button" className="investigation-utility" onClick={() => window.print()}>
                印刷
              </button>
            )}
            {step === 6 && (
              <button type="button" className="investigation-utility" onClick={() => void copyLink()}>
                URLを共有
              </button>
            )}
            {step < 6 ? (
              <button type="button" className="investigation-primary" onClick={onNext}>
                {NEXT_LABELS[step as 1 | 2 | 3 | 4 | 5]}
              </button>
            ) : (
              <button type="button" className="investigation-primary" onClick={onOpenAdvanced}>
                詳細分析を開く
              </button>
            )}
          </footer>
        </article>
      </main>
    </div>
  );
}
