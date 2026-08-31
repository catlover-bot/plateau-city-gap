import { useEffect, useMemo, useRef } from "react";
import type { AppData } from "../../types";
import type {
  SpatialSelection,
  SpatialState,
  SpatialViewport,
} from "../../state/spatial/types";
import { AnalyticalMap } from "../../map/2d/AnalyticalMap";
import { Plateau3DMap } from "../../map/3d/Plateau3DMap";
import { UrbanSection } from "../urban-section/UrbanSection";
import { CandidateShortlist } from "../investigation/CandidatePanels";
import { InvestigationHeader } from "../investigation/ValueLanding";
import type {
  InvestigationCandidate,
  InvestigationWorkspace,
} from "../investigation/investigationTypes";
import { buildPublicVerificationLoop } from "./verificationModel";
import {
  UncertaintyPanel,
  VerificationTargetsPanel,
  VerificationTasksPanel,
} from "./VerificationPanels";

type PublicStep = 1 | 2 | 3 | 4;

const STEP_TITLES: Record<PublicStep, string> = {
  1: "候補を選ぶ",
  2: "まだ分からないこと",
  3: "確かめる場所",
  4: "現地確認タスク",
};

const NEXT_LABELS: Record<1 | 2 | 3, string> = {
  1: "まだ分からないことを見る",
  2: "確かめる場所を見る",
  3: "現地確認タスクを見る",
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

export function VerificationJourney({
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
  const step = Math.min(state.guidedStep, 4) as PublicStep;
  const titleRef = useRef<HTMLHeadingElement>(null);
  const loop = useMemo(() => buildPublicVerificationLoop(candidate), [candidate]);
  const mapUsesPlateau = step === 3 && candidate.plateau.status === "verified";
  const mapLayerIds = useMemo(
    () => ["reference-gsi-pale", "analysis-city-gap", "infra-stations", "infra-medical"],
    [],
  );

  useEffect(() => {
    titleRef.current?.focus();
  }, [step]);

  return (
    <div
      className="product-app investigation-journey verification-journey"
      data-experience="guided"
      data-investigation-step={step}
      data-candidate-type={candidate.type}
    >
      <InvestigationHeader onRestart={onRestart} />
      <main className="investigation-body">
        <section className="investigation-map-stage" aria-label="選択した確認候補の地図">
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
              ariaLabel={`舞鶴市の確認候補地図。${candidate.name}を表示しています`}
              onSelectionChange={onSelectionChange}
              onViewportChange={onViewportChange}
            />
          )}
          <div className="investigation-map-caption">
            <span>{mapUsesPlateau ? "PLATEAU OBJECT TARGET" : "REAL MAIZURU CANDIDATE"}</span>
            <strong>{candidate.name}</strong>
            <small>
              {candidate.plateau.status === "verified"
                ? `500mメッシュ ${candidate.meshCode} · 建物${candidate.plateau.buildings}棟 · 道路${candidate.plateau.roads}面`
                : `500mメッシュ ${candidate.meshCode} · PLATEAU詳細なし`}
            </small>
          </div>
        </section>

        <article className="investigation-step-sheet" aria-labelledby="verification-step-title">
          <div className="investigation-progress verification-progress">
            <span>{step} / 4</span>
            <ol aria-label="不明点を現地確認タスクへ変える進み具合">
              {([1, 2, 3, 4] as PublicStep[]).map((item) => (
                <li
                  key={item}
                  aria-current={item === step ? "step" : undefined}
                  aria-label={`${item} / 4 ${STEP_TITLES[item]}`}
                >
                  <span aria-hidden="true">{item}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="investigation-step-content">
            <h1
              id="verification-step-title"
              ref={titleRef}
              tabIndex={-1}
              className="step-accessible-title"
            >
              {STEP_TITLES[step]}
            </h1>
            {step === 1 && (
              <CandidateShortlist
                workspace={workspace}
                selectedId={candidate.id}
                onSelect={onCandidateSelect}
              />
            )}
            {step === 2 && <UncertaintyPanel loop={loop} />}
            {step === 3 && <VerificationTargetsPanel loop={loop} />}
            {step === 4 && <VerificationTasksPanel loop={loop} />}
          </div>

          <footer className="investigation-actions">
            <button type="button" className="investigation-back" onClick={onBack}>
              {step === 1 ? "入口へ戻る" : "戻る"}
            </button>
            {step < 4 ? (
              <button type="button" className="investigation-primary" onClick={onNext}>
                {NEXT_LABELS[step as 1 | 2 | 3]}
              </button>
            ) : (
              <button type="button" className="investigation-primary" onClick={onOpenAdvanced}>
                高度分析を開く
              </button>
            )}
          </footer>
        </article>
      </main>
    </div>
  );
}
