import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { AppData, GeoJsonFeature } from "../../types";
import type { SpatialSelection, SpatialState, SpatialViewport } from "../../state/spatial/types";
import { AnalyticalMap } from "../../map/2d/AnalyticalMap";
import { Plateau3DMap } from "../../map/3d/Plateau3DMap";
import { PublicHeader } from "../navigation/PublicHeader";
import { AreaSummaryPanel, TargetTasks } from "./AreaInvestigationJourney";
import {
  AREA_MAX_RADIUS_M,
  AREA_MIN_RADIUS_M,
  resolveAreaSummary,
  type PublicAreaOrigin,
} from "./areaModel";
import type { AreaUnknown, InvestigationAreaFixture, InvestigationAreaSummary } from "./areaTypes";
import {
  PUBLIC_LANDING_COPY,
  PUBLIC_RADIUS_OPTIONS,
  contextual3dEligibility,
  radiusExplanation,
} from "./publicAreaPresentation";
import {
  buildPublicAreaGeometry,
  derivativeAvailableFor,
  publicStoryLegend,
  resolvePublicTarget,
  storyDerivativeAvailableFor,
  type PublicCartographyData,
  type PublicCartographyPresentation,
  type PublicStoryArtifactKind,
  type PublicStoryId,
  type PublicTargetData,
} from "./publicCartography";
import "./publicAreaJourney.css";

export type PublicAreaStep = "intro" | "place" | "radius" | "result" | "target";

const STEP_LABELS = [
  { id: "place", label: "場所" },
  { id: "radius", label: "範囲" },
  { id: "result", label: "確認できたこと" },
  { id: "target", label: "確認場所" },
] as const;

function coordinates(feature: GeoJsonFeature): [number, number] | null {
  if (feature.geometry?.type !== "Point" || !Array.isArray(feature.geometry.coordinates)) return null;
  const [longitude, latitude] = feature.geometry.coordinates;
  return typeof longitude === "number" && typeof latitude === "number" ? [longitude, latitude] : null;
}

function hasWebgl() {
  if (typeof document === "undefined") return false;
  const canvas = document.createElement("canvas");
  return Boolean(window.WebGLRenderingContext && (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")));
}

function targetSelection(unknown: AreaUnknown, summary: InvestigationAreaSummary, data: AppData): SpatialSelection {
  const type = unknown.target.object_type === "facility" ? "facility" : unknown.target.object_type;
  return {
    type,
    id: unknown.target.source_object_id,
    city: "maizuru",
    urbanState: "2025",
    label: unknown.target.label,
    longitude: unknown.target.longitude,
    latitude: unknown.target.latitude,
    properties: {
      source_dataset: unknown.target.dataset,
      area_id: summary.id,
      area_version: summary.version,
      area_content_sha256: summary.content_sha256,
      parent_mesh_code: data.plateauMetadata?.reference_layer?.deep_dive_mesh_code,
    },
  };
}

interface Props {
  data: AppData;
  fixture: InvestigationAreaFixture;
  cartography: PublicCartographyData | null;
  cartographyError?: string | null;
  targetCartography: PublicTargetData | null;
  targetCartographyError?: string | null;
  storyCartographyLoading?: PublicStoryArtifactKind | null;
  onRequestCartography(): void;
  onRequestTargetCartography(): void;
  onRequestStoryCartography(story: PublicStoryId): void;
  onCancelStoryCartography(): void;
  state: SpatialState;
  onOpenAdvanced(): void;
  onSelectionChange(selection: SpatialSelection | null): void;
  onViewportChange(viewport: SpatialViewport): void;
}

export function PublicAreaJourney({
  data,
  fixture,
  cartography,
  cartographyError = null,
  targetCartography,
  targetCartographyError = null,
  storyCartographyLoading = null,
  onRequestCartography,
  onRequestTargetCartography,
  onRequestStoryCartography,
  onCancelStoryCartography,
  state,
  onOpenAdvanced,
  onSelectionChange,
  onViewportChange,
}: Props) {
  const [step, setStep] = useState<PublicAreaStep>("intro");
  const [origin, setOrigin] = useState<PublicAreaOrigin | null>(null);
  const [radius, setRadius] = useState(800);
  const [customOpen, setCustomOpen] = useState(false);
  const [customRadius, setCustomRadius] = useState("650");
  const [stationId, setStationId] = useState("station-007");
  const [selectedUnknownId, setSelectedUnknownId] = useState("");
  const [mapMode, setMapMode] = useState<"map2d" | "plateau3d">("map2d");
  const [error, setError] = useState<string | null>(null);
  const [activeStory, setActiveStory] = useState<PublicStoryId>("population-age");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const summary = useMemo(() => origin ? resolveAreaSummary(fixture, data, origin, radius) : null, [data, fixture, origin, radius]);
  const selectedUnknown = summary?.unknowns.find((unknown) => unknown.id === selectedUnknownId) ?? summary?.unknowns[0] ?? null;
  const stations = useMemo(() => [...(data.stations?.features ?? [])].sort((left, right) => {
    const leftName = String(left.properties?.name ?? "");
    const rightName = String(right.properties?.name ?? "");
    if (leftName === "西舞鶴駅") return -1;
    if (rightName === "西舞鶴駅") return 1;
    return leftName.localeCompare(rightName, "ja");
  }), [data.stations]);
  const areaGeometry = useMemo(
    () => origin ? buildPublicAreaGeometry(origin.coordinates, radius) : null,
    [origin, radius],
  );
  const derivativeAvailable = storyDerivativeAvailableFor(cartography, summary, activeStory);
  const targetDerivativeAvailable = derivativeAvailableFor(targetCartography ?? cartography, summary);
  const targetRender = useMemo(
    () => resolvePublicTarget(
      selectedUnknown?.target ?? null,
      cartography,
      targetDerivativeAvailable,
      targetCartography,
    ),
    [cartography, selectedUnknown, targetCartography, targetDerivativeAvailable],
  );
  const mapPresentation = useMemo<PublicCartographyPresentation>(() => ({
    data: step === "target" ? null : cartography,
    area: areaGeometry,
    activeStory: step === "result" ? activeStory : null,
    target: step === "result" || step === "target" ? targetRender : null,
    showTarget: step === "target",
    derivativeAvailable: step === "target" ? targetDerivativeAvailable : derivativeAvailable,
  }), [activeStory, areaGeometry, cartography, derivativeAvailable, step, targetDerivativeAvailable, targetRender]);
  const activeStoryArtifact = activeStory === "building-use"
    ? "buildings"
    : activeStory === "urban-planning" ? "planning" : null;
  const activeStoryPending = Boolean(activeStoryArtifact && !derivativeAvailable);
  const cartographyStatusLegend = step === "result" && (!cartography || activeStoryPending) ? {
    title: "地図表示",
    note: cartographyError ?? "PLATEAU表示用データを準備中です",
    items: [],
  } : null;
  const legend = cartographyStatusLegend ?? (step === "target"
    ? {
        title: targetRender?.resolution === "exact" ? "PLATEAU上の確認対象" : "確認対象の位置",
        note: targetRender?.resolution === "exact" ? "PLATEAUの実形状" : "登録された位置情報のみ",
        items: [{ label: selectedUnknown?.target.label ?? "確認対象", color: "#6b4c7d", shape: "fill" as const }],
      }
    : publicStoryLegend(step === "result" ? activeStory : null, derivativeAvailable));
  const eligibility = summary && selectedUnknown
    ? contextual3dEligibility(summary, selectedUnknown.target, data.plateauMetadata?.year, hasWebgl())
    : { eligible: false, technicalEligible: false, uxValuable: false, reasonCode: "no_target", reason: "確認場所を選んでください。" };

  useEffect(() => {
    if (summary?.unknowns.length && !summary.unknowns.some((unknown) => unknown.id === selectedUnknownId)) {
      setSelectedUnknownId(summary.unknowns[0].id);
    }
  }, [selectedUnknownId, summary]);

  useEffect(() => {
    if (
      (step === "result" || step === "target")
      && (selectedUnknown?.target.object_type === "building" || selectedUnknown?.target.object_type === "road")
    ) {
      onRequestTargetCartography();
    }
  }, [onRequestTargetCartography, selectedUnknown, step]);

  useEffect(() => {
    if (step === "result") onRequestStoryCartography(activeStory);
    else onCancelStoryCartography();
  }, [activeStory, onCancelStoryCartography, onRequestStoryCartography, step]);

  useEffect(() => {
    if (step !== "result" || activeStory !== "population-age") return;
    const connection = (navigator as Navigator & {
      connection?: { saveData?: boolean; effectiveType?: string };
    }).connection;
    if (connection?.saveData || connection?.effectiveType === "slow-2g" || connection?.effectiveType === "2g") return;
    const prefetch = () => onRequestStoryCartography("building-use");
    if ("requestIdleCallback" in window) {
      const handle = window.requestIdleCallback(prefetch, { timeout: 1_200 });
      return () => window.cancelIdleCallback(handle);
    }
    const handle = setTimeout(prefetch, 900);
    return () => clearTimeout(handle);
  }, [activeStory, onRequestStoryCartography, step]);

  useEffect(() => {
    if (step !== "target" || !summary || !selectedUnknown) return;
    onSelectionChange(targetSelection(selectedUnknown, summary, data));
  }, [data, onSelectionChange, selectedUnknown, step, summary]);

  useEffect(() => {
    window.requestAnimationFrame(() => headingRef.current?.focus());
  }, [step]);

  const restart = () => {
    setStep("intro");
    setOrigin(null);
    setRadius(800);
    setCustomOpen(false);
    setSelectedUnknownId("");
    setMapMode("map2d");
    setActiveStory("population-age");
    setError(null);
    onSelectionChange(null);
  };
  const chooseOrigin = (next: PublicAreaOrigin) => {
    setOrigin(next);
    setSelectedUnknownId("");
    setMapMode("map2d");
    setError(null);
    setActiveStory("population-age");
    onViewportChange({ longitude: next.coordinates[0], latitude: next.coordinates[1], zoom: 13.4, bearing: 0, pitch: 0 });
    setStep("radius");
  };
  const chooseStation = () => {
    const station = stations.find((feature) => String(feature.properties?.id ?? "") === stationId) ?? stations[0];
    const point = station && coordinates(station);
    if (!station || !point) {
      setError("駅の位置を確認できませんでした。");
      return;
    }
    chooseOrigin({ kind: "station", label: String(station.properties?.name ?? "駅"), coordinates: point, sourceFeatureId: String(station.properties?.id ?? "") });
  };
  const selectRadius = (value: number, keepCustomOpen = false) => {
    setRadius(value);
    setCustomOpen(keepCustomOpen);
    setSelectedUnknownId("");
    setMapMode("map2d");
    setError(null);
    setActiveStory("population-age");
  };
  const submitCustom = () => {
    const value = Number(customRadius);
    if (!Number.isInteger(value) || value < AREA_MIN_RADIUS_M || value > AREA_MAX_RADIUS_M) {
      setError("その他の半径は100〜3000mの整数で入力してください。");
      return;
    }
    selectRadius(value, true);
  };
  const customValue = Number(customRadius);
  const customRadiusApplied = Number.isInteger(customValue)
    && customValue >= AREA_MIN_RADIUS_M
    && customValue <= AREA_MAX_RADIUS_M
    && radius === customValue;
  const back = () => {
    if (step === "place") setStep("intro");
    else if (step === "radius") setStep("place");
    else if (step === "result") setStep("radius");
    else if (step === "target") {
      setMapMode("map2d");
      setStep("result");
    }
  };

  const progressIndex = STEP_LABELS.findIndex((item) => item.id === step);
  const mapSelection = step === "target" && summary && selectedUnknown ? targetSelection(selectedUnknown, summary, data) : state.selection;

  return (
    <div
      className="product-app public-area"
      data-experience="public-first-run"
      data-public-step={step}
      data-map-mode={mapMode}
      data-active-story={step === "result" ? activeStory : "none"}
      data-cartography-state={cartography && !activeStoryPending ? "ready" : cartographyError ? "degraded" : "loading"}
      data-story-cartography-loading={storyCartographyLoading ?? "none"}
      data-target-cartography-state={targetCartography ? "ready" : targetCartographyError ? "degraded" : "idle"}
      data-presentation-target-kind={targetRender?.kind ?? "none"}
      data-presentation-target-resolution={targetRender?.resolution ?? "none"}
    >
      <PublicHeader onRestart={restart} onOpenAdvanced={onOpenAdvanced} />
      <main className={`public-area-body step-${step}`}>
        <section className="public-map-stage" aria-label="舞鶴市の調査場所を選ぶ地図">
          {mapMode === "plateau3d" && eligibility.eligible && selectedUnknown ? (
            <Plateau3DMap
              data={data}
              selection={mapSelection}
              viewport={state.viewport}
              activeLayerIds={["plateau-buildings", "plateau-roads"]}
              scenePreset={selectedUnknown.target.object_type === "road" ? "network_access" : "plateau_detail"}
              analysisLens="none"
              counterfactualState="baseline"
              uiMode="guided"
              preferredBuildingSource="spatial-pack"
              onSelectionChange={onSelectionChange}
            />
          ) : (
            <AnalyticalMap
              data={data}
              validation={null}
              preset="discovery"
              primaryLayer="public-cartography"
              activeLayerIdsOverride={["reference-gsi-pale"]}
              selection={mapSelection}
              viewport={state.viewport}
              publicCartography={mapPresentation}
              interactive
              ariaLabel="舞鶴市の地図。地図の中心を任意の起点にできます"
              onSelectionChange={onSelectionChange}
              onViewportChange={onViewportChange}
            />
          )}
          <div className="public-map-area-badge">
            <span>{origin ? "調査範囲" : "舞鶴市"}</span>
            <strong>{origin?.label ?? "調べたい場所を選ぶ"}</strong>
            <small>{origin ? `半径 ${radius}m` : "駅または地図上の任意地点から始めます"}</small>
          </div>
          {legend && <aside className="public-map-legend" aria-label={`地図の凡例: ${legend.title}`}>
            <strong>{legend.title}</strong>
            {legend.items.map((item) => <span key={item.label}>
              <i className={`shape-${item.shape ?? "fill"}`} style={{ "--legend-color": item.color } as CSSProperties} />
              {item.label}
            </span>)}
            {legend.note && <small>{legend.note}</small>}
          </aside>}
          {step === "target" && targetRender && <div className="public-map-target-label" data-target-resolution={targetRender.resolution}>
            <span>{targetRender.resolution === "exact" ? "実データ上の確認対象" : "確認対象の位置"}</span>
            <strong>{targetRender.label}</strong>
          </div>}
        </section>

        <article className="public-area-panel">
          {step !== "intro" && (
            <div className="public-progress">
              <span>{progressIndex + 1} / 4</span>
              <ol aria-label="場所を選んで確認場所を見るまでの進み具合">
                {STEP_LABELS.map((item, index) => (
                  <li key={item.id} aria-current={item.id === step ? "step" : undefined} className={index < progressIndex ? "complete" : ""}>
                    <span>{index + 1}</span><small>{item.label}</small>
                  </li>
                ))}
              </ol>
            </div>
          )}

          <div className="public-area-content">
            {step === "intro" && (
              <section className="public-intro">
                <p>舞鶴市の公開データを使った確認</p>
                <h1 ref={headingRef} tabIndex={-1}>気になる場所を、<br />地図とデータで確かめる。</h1>
                <p className="public-intro-copy">{PUBLIC_LANDING_COPY.subcopy}</p>
                <button type="button" className="public-primary" onClick={() => setStep("place")}>{PUBLIC_LANDING_COPY.primaryCta}</button>
                <small>公開データの出典・時点・限界を表示します。政策判断や危険判定は行いません。</small>
              </section>
            )}

            {step === "place" && (
              <section>
                <p className="public-kicker">場所を選ぶ</p>
                <h1 ref={headingRef} tabIndex={-1}>どこを調べますか？</h1>
                <div className="public-origin-grid">
                  <div>
                    <h2>駅から選ぶ</h2>
                    <label htmlFor="public-station">駅</label>
                    <select id="public-station" value={stationId} onChange={(event) => setStationId(event.target.value)}>
                      {stations.map((station) => <option key={String(station.properties?.id)} value={String(station.properties?.id)}>{String(station.properties?.name)}</option>)}
                    </select>
                    <button type="button" className="public-primary" onClick={chooseStation}>選んだ駅を起点にする</button>
                  </div>
                  <div>
                    <h2>地図上の任意地点</h2>
                    <p>地図を動かし、現在の中心を起点にします。</p>
                    <button type="button" className="public-secondary" onClick={() => chooseOrigin({ kind: "map_point", label: "地図上で選んだ地点", coordinates: [state.viewport.longitude, state.viewport.latitude] })}>地図中心を起点にする</button>
                  </div>
                </div>
                <details className="public-boundary-note">
                  <summary>2020年国勢調査小地域（町丁・字等）について</summary>
                  <p>統計調査用の境界です。現在の行政上の町界、住所上の町丁目、自治会区域、自治体独自の業務区域と一致するとは限りません。</p>
                  <p>舞鶴市のversioned境界fixtureが未登録のため、この公開版では選択できません。別境界で補完しません。</p>
                </details>
                {error && <p role="alert" className="public-error">{error}</p>}
              </section>
            )}

            {step === "radius" && (
              <section>
                <p className="public-kicker">範囲を選ぶ</p>
                <h1 ref={headingRef} tabIndex={-1}>どの範囲を見ますか？</h1>
                <p>{origin?.label}</p>
                <div className="public-radius-grid" role="group" aria-label="調べる半径">
                  {PUBLIC_RADIUS_OPTIONS.map((option) => (
                    <button
                      type="button"
                      key={option.value}
                      aria-pressed={!customOpen && radius === option.value}
                      className={!customOpen && radius === option.value ? "selected" : ""}
                      onClick={() => selectRadius(option.value)}
                    >
                      {option.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    aria-pressed={customOpen}
                    aria-expanded={customOpen}
                    className={customOpen ? "selected" : ""}
                    onClick={() => setCustomOpen(true)}
                  >
                    その他
                  </button>
                </div>
                {customOpen && (
                  <div className="public-custom-radius">
                    <label htmlFor="public-custom-radius">半径（100〜3000m）</label>
                    <div><input id="public-custom-radius" inputMode="numeric" value={customRadius} onChange={(event) => setCustomRadius(event.target.value)} /><span>m</span><button type="button" onClick={submitCustom}>この半径を使う</button></div>
                  </div>
                )}
                {error && <p role="alert" className="public-error">{error}</p>}
                <button
                  type="button"
                  className="public-primary public-radius-submit"
                  disabled={customOpen && !customRadiusApplied}
                  onClick={() => {
                    onRequestCartography();
                    setStep("result");
                  }}
                >
                  この範囲を調べる
                </button>
              </section>
            )}

            {step === "result" && summary && (
              <section>
                <p className="public-kicker">選んだ範囲の結果</p>
                <h1 ref={headingRef} tabIndex={-1}>分かっていることと、まだ分からないこと</h1>
                <p className="public-area-label">{summary.label} · 未確認</p>
                <details className="public-methodology">
                  <summary>{radius}mの分析範囲について</summary>
                  <p>{radiusExplanation(radius)}</p>
                </details>
                <AreaSummaryPanel
                  summary={summary}
                  publicMode
                  activeStoryId={activeStory}
                  selectedUnknownId={selectedUnknown?.id}
                  onStorySelect={(story) => {
                    setActiveStory(story);
                    onRequestStoryCartography(story);
                  }}
                  onUnknownSelect={setSelectedUnknownId}
                />
              </section>
            )}

            {step === "target" && summary && selectedUnknown && (
              <section>
                <p className="public-kicker">確認場所と未確認項目</p>
                <h1 ref={headingRef} tabIndex={-1}>データだけでは分からないことを、場所で確かめる</h1>
                <TargetTasks summary={{ ...summary, unknowns: [selectedUnknown] }} publicMode />
                <div
                  className="public-3d-decision"
                  data-contextual-3d-eligible={eligibility.eligible}
                  data-contextual-3d-technical-eligible={eligibility.technicalEligible}
                  data-contextual-3d-ux-valuable={eligibility.uxValuable}
                  data-contextual-3d-reason-code={eligibility.reasonCode}
                  data-contextual-3d-reason={eligibility.reason}
                >
                  {eligibility.eligible && (
                    <div className="public-3d-choice">
                      <p>{eligibility.reason}</p>
                      <button type="button" className="public-secondary" aria-pressed={mapMode === "plateau3d"} onClick={() => setMapMode((value) => value === "map2d" ? "plateau3d" : "map2d")}>
                        {mapMode === "plateau3d" ? "2D地図に戻す" : "3Dで周辺を見る"}
                      </button>
                    </div>
                  )}
                </div>
              </section>
            )}
          </div>

          {step !== "intro" && (
            <footer className="public-area-actions">
              <button type="button" className="public-back" onClick={back}>戻る</button>
              {step === "result" && <button type="button" className="public-primary" onClick={() => setStep("target")}>確認場所を見る</button>}
            </footer>
          )}
        </article>
      </main>
    </div>
  );
}
