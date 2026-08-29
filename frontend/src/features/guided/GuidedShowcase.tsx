import { useEffect, useMemo, useRef, useState } from "react";
import type {
  AppData,
  GeoJsonFeatureCollection,
  InterventionPlan,
} from "../../types";
import type {
  GuidedStep,
  SpatialSelection,
  SpatialState,
  SpatialViewport,
} from "../../state/spatial/types";
import { AnalyticalMap } from "../../map/2d/AnalyticalMap";
import { Plateau3DMap } from "../../map/3d/Plateau3DMap";
import { UrbanSection } from "../urban-section/UrbanSection";
import { buildGuidedCase } from "./guidedCase";

interface HeaderProps {
  onRestart(): void;
}

function ShowcaseHeader({ onRestart }: HeaderProps) {
  return (
    <header className="showcase-header">
      <button type="button" className="showcase-brand" onClick={onRestart} aria-label="CITY GAPを最初から見る">
        CITY GAP
      </button>
      <strong className="showcase-city">舞鶴市</strong>
      <button type="button" className="showcase-restart" onClick={onRestart}>最初から見る</button>
      <span className="showcase-advanced-label">詳しい分析</span>
    </header>
  );
}

interface LandingProps {
  onStart(): void;
  onExplore(): void;
  onRestart(): void;
}

export function ShowcaseLanding({ onStart, onExplore, onRestart }: LandingProps) {
  return (
    <div className="product-app showcase-landing" data-experience="landing">
      <ShowcaseHeader onRestart={onRestart} />
      <main className="landing-main">
        <div className="landing-map-context" aria-hidden="true">
          <span className="landing-mesh mesh-a" />
          <span className="landing-mesh mesh-b" />
          <span className="landing-mesh mesh-c" />
          <span className="landing-route" />
          <span className="landing-target" />
        </div>
        <section className="landing-message" aria-labelledby="landing-title">
          <p className="landing-eyebrow">舞鶴市の実データで見る都市調査</p>
          <h1 id="landing-title">CITY GAP</h1>
          <p className="landing-lead">高齢者が多いのに、交通や医療へ届きにくい地域を見つけます。</p>
          <p className="landing-support">500mで候補を見つけ、PLATEAUの建物・道路・地形まで掘り下げて確認します。</p>
          <div className="landing-actions">
            <button type="button" className="showcase-primary" onClick={onStart}>舞鶴の例を1分で見る</button>
            <button type="button" className="showcase-secondary" onClick={onExplore}>自分で地図を調べる</button>
          </div>
        </section>
        <section className="landing-promises" aria-label="CITY GAPでできること">
          <div><span>1</span><strong>見つける</strong><p>サービスが届きにくい地域候補を探す</p></div>
          <div><span>2</span><strong>掘り下げる</strong><p>PLATEAUで建物・道路・地形まで確認する</p></div>
          <div><span>3</span><strong>比較する</strong><p>施策を変えた場合の違いを確認する</p></div>
        </section>
      </main>
    </div>
  );
}

interface GuidedProps {
  data: AppData;
  state: SpatialState;
  activeLayerIds: string[];
  plan: InterventionPlan;
  scenarioSites: GeoJsonFeatureCollection;
  scenarioMeshes: GeoJsonFeatureCollection;
  scenarioScores: Record<string, number> | null;
  decisionFlow: {
    meshLongitude: number;
    meshLatitude: number;
    siteLongitude: number;
    siteLatitude: number;
  } | null;
  evidenceReviewed: boolean;
  onBack(): void;
  onNext(): void;
  onRestart(): void;
  onOpenEvidence(): void;
  onOpenAdvanced(): void;
  onSelectionChange(selection: SpatialSelection | null): void;
  onViewportChange(viewport: SpatialViewport): void;
  onSelectBuilding(id: string, properties: Record<string, unknown>): void;
}

const STEP_TITLES: Record<GuidedStep, string> = {
  1: "どこが気になる？",
  2: "なぜ候補になった？",
  3: "街のどこで起きている？",
  4: "施策を変えるとどうなる？",
  5: "その数字の根拠は？",
};

const NEXT_LABELS: Record<1 | 2 | 3 | 4, string> = {
  1: "理由を見る",
  2: "建物・道路・地形を見る",
  3: "条件を変えて比べる",
  4: "数字の根拠を見る",
};

export function GuidedInvestigation({
  data,
  state,
  activeLayerIds,
  plan,
  scenarioSites,
  scenarioMeshes,
  scenarioScores,
  decisionFlow,
  evidenceReviewed,
  onBack,
  onNext,
  onRestart,
  onOpenEvidence,
  onOpenAdvanced,
  onSelectionChange,
  onViewportChange,
  onSelectBuilding,
}: GuidedProps) {
  const guided = useMemo(() => buildGuidedCase(data), [data]);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const [threeDReadyStep, setThreeDReadyStep] = useState<GuidedStep | null>(null);
  const [prefersStaticSection, setPrefersStaticSection] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const step = state.guidedStep;
  const uses3D = step >= 3;
  const shouldRender3D = uses3D && !prefersStaticSection;
  const threeDReady = shouldRender3D && threeDReadyStep === step;
  const renderPath = threeDReady ? "three-d" : "static-section";

  useEffect(() => {
    titleRef.current?.focus();
  }, [step]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setPrefersStaticSection(media.matches);
    updatePreference();
    media.addEventListener("change", updatePreference);
    return () => media.removeEventListener("change", updatePreference);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.guidedStep = String(step);
    document.documentElement.dataset.guidedRenderPath = uses3D ? renderPath : "map-2d";
    return () => {
      delete document.documentElement.dataset.guidedStep;
      delete document.documentElement.dataset.guidedRenderPath;
    };
  }, [renderPath, step, uses3D]);

  return (
    <div
      className="product-app guided-showcase"
      data-experience="guided"
      data-guided-step={step}
      data-guided-render-path={uses3D ? renderPath : "map-2d"}
    >
      <ShowcaseHeader onRestart={onRestart} />
      <main className="guided-body">
        <section
          className="guided-map-stage"
          aria-label="案内中の地図"
          data-static-fallback={uses3D && prefersStaticSection ? "true" : undefined}
        >
          {uses3D ? (
            shouldRender3D ? (
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
                decisionSites={step >= 4 ? plan.sites : []}
                afterScores={step >= 4 ? scenarioScores : null}
                decisionFlow={step >= 4 ? decisionFlow : null}
                onSelectionChange={onSelectionChange}
                onReady={() => setThreeDReadyStep(step)}
              />
            ) : (
              <div className="guided-static-map" data-render-source="verified-section" role="img" aria-label="PLATEAUの実データから作った街の断面">
                <strong>検証済みの街の断面を表示</strong>
                <span>実際の地形・建物・道路を軽量表示しています</span>
              </div>
            )
          ) : (
            <AnalyticalMap
              data={data}
              validation={null}
              preset="discovery"
              primaryLayer="analysis-city-gap"
              activeLayerIdsOverride={["reference-gsi-pale", "analysis-city-gap", "infra-stations", "infra-medical"]}
              selection={state.selection}
              viewport={state.viewport}
              scenarioSites={scenarioSites}
              scenarioMeshes={scenarioMeshes}
              dimNonSelected
              interactive
              ariaLabel="舞鶴市の500m候補地図。常団地前周辺を選択しています"
              onSelectionChange={onSelectionChange}
              onViewportChange={onViewportChange}
            />
          )}
          {uses3D && (
            <UrbanSection
              open
              mode="guided"
              selection={state.selection}
              counterfactualState={state.counterfactualState}
              analysisLens={state.analysisLens}
              onClose={() => undefined}
              onSelectBuilding={onSelectBuilding}
            />
          )}
          <div className="guided-map-legend" aria-label="この段階の凡例">
            {step <= 2 && <><i className="legend-candidate" /><span>色の濃い500mほど追加調査候補</span><b>選択中：常団地前周辺</b></>}
            {step === 3 && <><i className="legend-building" /><span>建物</span><i className="legend-road" /><span>道路</span><i className="legend-terrain" /><span>実際の地形</span></>}
            {step >= 4 && <><i className="legend-current" /><span>現在</span><i className="legend-condition" /><span>仮想地点を加えた条件</span></>}
          </div>
          {uses3D && (
            <div className="guided-render-status" role="status" aria-live="polite">
              {prefersStaticSection
                ? "動きを抑える設定に合わせ、検証済みの街の断面を表示しています"
                : threeDReady
                  ? "建物・道路・地形を3Dでも確認できます"
                  : "3Dを準備中です。検証済みの街の断面を先に表示しています"}
            </div>
          )}
        </section>

        <article className="guided-step-sheet" aria-labelledby="guided-question">
          <div className="guided-progress-row">
            <span aria-live="polite">{step} / 5</span>
            <ol aria-label="調査の進み具合">
              {([1, 2, 3, 4, 5] as GuidedStep[]).map((item) => (
                <li key={item} aria-current={item === step ? "step" : undefined} aria-label={`${item} / 5 ${STEP_TITLES[item]}`}>
                  <span aria-hidden="true">{item}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="guided-step-copy">
            <p className="guided-kicker">舞鶴市・同じ地域を5つの問いで確認</p>
            <h1 id="guided-question" ref={titleRef} tabIndex={-1}>{STEP_TITLES[step]}</h1>

            {step === 1 && (
              <>
                <p className="guided-explanation">舞鶴市{guided.meshCount}メッシュの中から、人口・交通・医療を重ねて追加調査候補を探しています。</p>
                <div className="guided-place-card" data-guided-target={guided.mesh.mesh_code}>
                  <span>選択した500m</span>
                  <strong>{guided.areaName}</strong>
                  <small>500mメッシュ {guided.mesh.mesh_code}</small>
                </div>
                <dl className="guided-compact-facts">
                  <div><dt>全市での順位</dt><dd>{guided.overallRank}位</dd></div>
                  <div><dt>比較した範囲</dt><dd>{guided.meshCount}メッシュ</dd></div>
                </dl>
                <p className="guided-boundary">順位は詳しく確認する候補の比較で、危険度や政策優先順位ではありません。</p>
              </>
            )}

            {step === 2 && (
              <>
                <p className="guided-explanation">高齢者が一定数暮らす一方、交通・医療への距離があるため、詳しく確認する候補です。</p>
                <dl className="guided-primary-facts">
                  <div data-primary-fact="elderly"><dt>65歳以上</dt><dd>{Math.round(guided.elderlyPopulation)}<small>人</small></dd></div>
                  <div data-primary-fact="transport"><dt>公共交通まで</dt><dd>{Math.round(guided.transportDistanceM)}<small>m</small></dd></div>
                  <div data-primary-fact="medical"><dt>医療まで</dt><dd>{(guided.medicalDistanceM / 1000).toFixed(2)}<small>km</small></dd></div>
                </dl>
                <p className="guided-optional-fact">参考：この500mの人口は{Math.round(guided.population)}人です。</p>
                <details className="guided-calculation">
                  <summary>詳しい計算</summary>
                  <p>舞鶴市内で高齢者数・公共交通距離・医療距離をそれぞれ比較し、3つが重なる場所を候補にしています。</p>
                </details>
              </>
            )}

            {step === 3 && (
              <>
                <p className="guided-explanation">500mだけでは、地域のどの建物・道路が関係するか分かりません。</p>
                <ol className="resolution-lift" aria-label="500mから街の形へ掘り下げる順序">
                  <li><span>500m</span><strong>候補の範囲</strong></li>
                  <li><span>{guided.plateauBuildingCount}棟</span><strong>実際のPLATEAU建物</strong></li>
                  <li><span>{guided.plateauRoadCount}面</span><strong>範囲を通る道路</strong></li>
                  <li><span>実データ</span><strong>PLATEAUの地形</strong></li>
                </ol>
                <p className="guided-spatial-summary">PLATEAUを使うと、この500m内の実際の建物{guided.plateauBuildingCount}棟、道路、地形まで確認できます。街の断面に表示する棟数は、そのうち断面付近の建物だけを数えています。</p>
              </>
            )}

            {step === 4 && (
              <>
                <p className="guided-explanation">既に計算した仮想支援地点の条件を、同じ常団地前周辺で現在と比べます。</p>
                <div className="guided-comparison" aria-label="現在と仮想地点条件の比較">
                  <div><span>現在の交通距離</span><strong>{Math.round(guided.scenarioBeforeM)}m</strong></div>
                  <div><span>仮想支援地点を加えた条件</span><strong>{Math.round(guided.scenarioAfterM)}m</strong></div>
                  <div className="comparison-change"><span>分析上の変化</span><strong>−{Math.round(guided.scenarioReductionM)}m</strong></div>
                </div>
                <p className="guided-boundary">これは実施効果の予測ではありません。仮想地点を置いた場合の分析上の距離比較です。建物と道路の形は変えていません。</p>
              </>
            )}

            {step === 5 && (
              <>
                <p className="guided-explanation">人口・施設・PLATEAUの出典と年を分けて確認できます。</p>
                <ul className="guided-sources">
                  {guided.sources.map((source) => (
                    <li key={source.id} data-source-id={source.id}><strong>{source.label}</strong><span>{source.detail}</span></li>
                  ))}
                </ul>
                <p className="guided-boundary">年の異なるデータを、同じ年の観測値のようには扱っていません。</p>
              </>
            )}
          </div>

          <footer className="guided-actions">
            <button type="button" className="guided-back" onClick={onBack}>{step === 1 ? "入口へ戻る" : "戻る"}</button>
            {step < 5 && (
              <button type="button" className="guided-next" onClick={onNext}>{NEXT_LABELS[step as 1 | 2 | 3 | 4]}</button>
            )}
            {step === 5 && (
              <button type="button" className="guided-next" onClick={evidenceReviewed ? onOpenAdvanced : onOpenEvidence}>
                {evidenceReviewed ? "詳しい分析を開く" : "詳しい出典を見る"}
              </button>
            )}
          </footer>
        </article>
      </main>
    </div>
  );
}
