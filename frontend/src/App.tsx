import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BuildingInfoCard } from "./components/BuildingInfoCard";
import type { CesiumMapHandle } from "./components/CesiumMap";
import { DetailPanel } from "./components/DetailPanel";
import { EvidenceModal } from "./components/EvidenceModal";
import { EmptyState, ErrorState, LoadingState } from "./components/AppStates";
import { LayerPanel } from "./components/LayerPanel";
import { MethodologyModal } from "./components/MethodologyModal";
import { MetricSelector } from "./components/MetricSelector";
import { MunicipalAdmin } from "./components/MunicipalAdmin";
import { MunicipalWorkspace } from "./components/MunicipalWorkspace";
import { RankingPanel } from "./components/RankingPanel";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { StoryMode } from "./components/StoryMode";
import { UrbanFuturesWorkspace } from "./components/UrbanFuturesWorkspace";
import { ValidationWorkspace } from "./components/ValidationWorkspace";
import {
  loadAppData,
  loadMunicipalWorkspaceData,
  loadUrbanFuturesData,
  loadValidationWorkspaceData,
  loadValidationCityData
} from "./lib/data";
import { finiteNumber } from "./lib/format";
import { summarizePlateauCoverage, top10CoverageLabel } from "./lib/plateau";
import { calculateScenario, type ScenarioResult, type VirtualPoint } from "./lib/scenario";
import type {
  AppData,
  BuildingInfo,
  DecisionMapPhase,
  DecisionMode,
  LayerVisibility,
  MeshMetrics,
  MetricMode,
  MunicipalWorkspaceData,
  FuturesStressMode,
  RobustCandidate,
  UrbanFuturesData,
  ValidationWorkspaceData,
  WorkspaceLayerVisibility,
  WorkspacePhase
} from "./types";

const CesiumMap = lazy(async () => {
  const module = await import("./components/CesiumMap");
  return { default: module.CesiumMap };
});

const INITIAL_LAYERS: LayerVisibility = {
  meshes: true,
  stations: true,
  busStops: false,
  medical: true,
  boundary: true,
  plateau: false
};

const INITIAL_WORKSPACE_LAYERS: WorkspaceLayerVisibility = {
  meshes: true,
  affectedBuildings: false,
  routes: false,
  plateauBuildings: false,
  roadNetwork: false,
  landuse: false,
  planning: false,
  hazard: false
};

const LEGENDS: Record<MetricMode, { title: string; low: string; high: string }> = {
  gap: { title: "CITY GAP 探索スコア", low: "相対的に低い", high: "要追加調査" },
  elderly: { title: "65歳以上人口 percentile", low: "少ない", high: "多い" },
  transport: { title: "公共交通距離 percentile", low: "近い", high: "遠い" },
  medical: { title: "医療距離 percentile", low: "近い", high: "遠い" }
};

type SideTab = "ranking" | "detail" | "scenario";
type CityId = "maizuru" | "fujisawa";
type ProductView = "demo" | "workspace" | "validation" | "futures" | "admin";

export default function App() {
  const [datasets, setDatasets] = useState<Record<CityId, AppData> | null>(null);
  const [cityId, setCityId] = useState<CityId>("maizuru");
  const [productView, setProductView] = useState<ProductView>("demo");
  const [workspaceData, setWorkspaceData] = useState<MunicipalWorkspaceData | null>(null);
  const [futuresData, setFuturesData] = useState<UrbanFuturesData | null>(null);
  const [validationData, setValidationData] = useState<ValidationWorkspaceData | null>(null);
  const [futureYear, setFutureYear] = useState(2040);
  const [futuresStressMode, setFuturesStressMode] = useState<FuturesStressMode>("normal");
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [workspaceRetry, setWorkspaceRetry] = useState(0);
  const [workspacePhase, setWorkspacePhase] = useState<WorkspacePhase>("baseline");
  const [workspaceLayers, setWorkspaceLayers] = useState(INITIAL_WORKSPACE_LAYERS);
  const data = datasets?.[cityId] ?? null;
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [metricMode, setMetricMode] = useState<MetricMode>("gap");
  const [layers, setLayers] = useState(INITIAL_LAYERS);
  const [layerPanelOpen, setLayerPanelOpen] = useState(false);
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [selectedMesh, setSelectedMesh] = useState<MeshMetrics | null>(null);
  const [sideTab, setSideTab] = useState<SideTab>("detail");
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapWarning, setMapWarning] = useState<string | null>(null);
  const [placementMode, setPlacementMode] = useState(false);
  const [scenario, setScenario] = useState<ScenarioResult | null>(null);
  const [virtualPoint, setVirtualPoint] = useState<VirtualPoint | null>(null);
  const [storyStep, setStoryStep] = useState<number | null>(null);
  const [selectedBuilding, setSelectedBuilding] = useState<BuildingInfo | null>(null);
  const [rankingView, setRankingView] = useState<"score" | "robust">("score");
  const [decisionMode, setDecisionMode] = useState<DecisionMode>("overall");
  const [siteCount, setSiteCount] = useState<1 | 2 | 3>(1);
  const [mapPhase, setMapPhase] = useState<DecisionMapPhase>("before");
  const mapRef = useRef<CesiumMapHandle>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setDatasets(null);
    setMapReady(false);
    setMapError(null);
    setMapWarning(null);
    Promise.all([loadAppData(), loadValidationCityData(), loadUrbanFuturesData(), loadValidationWorkspaceData()])
      .then(([maizuru, fujisawa, urbanFutures, validation]) => {
        if (cancelled) return;
        setDatasets({ maizuru, fujisawa });
        setFuturesData(urbanFutures);
        setValidationData(validation);
        setSelectedMesh(maizuru.top10[0] ?? null);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "不明な読み込みエラーです");
      });
    return () => {
      cancelled = true;
    };
  }, [retryKey]);

  useEffect(() => {
    if ((productView !== "workspace" && productView !== "futures") || workspaceData) return;
    let cancelled = false;
    setWorkspaceError(null);
    loadMunicipalWorkspaceData()
      .then((result) => {
        if (!cancelled) setWorkspaceData(result);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setWorkspaceError(reason instanceof Error ? reason.message : "Workspaceデータを読み込めませんでした");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [productView, workspaceData, workspaceRetry]);

  useEffect(() => {
    if (productView !== "futures") return;
    setWorkspaceLayers((current) => ({
      ...current,
      meshes: false,
      roadNetwork: true,
      hazard: futuresStressMode !== "normal"
    }));
  }, [futuresStressMode, productView]);

  const switchCity = useCallback((nextCity: CityId) => {
    if (!datasets || nextCity === cityId) return;
    const next = datasets[nextCity];
    setCityId(nextCity);
    setSelectedMesh(next.top10[0] ?? null);
    setSelectedBuilding(null);
    setSideTab("detail");
    setMetricMode("gap");
    setLayers({ ...INITIAL_LAYERS, plateau: false });
    setStoryStep(null);
    setScenario(null);
    setVirtualPoint(null);
    setPlacementMode(false);
    setRankingView("score");
    setDecisionMode("overall");
    setSiteCount(1);
    setMapPhase("before");
    setEvidenceOpen(false);
    setFuturesStressMode("normal");
    setMapReady(false);
    setMapError(null);
    setMapWarning(null);
  }, [cityId, datasets]);

  const selectMesh = useCallback((mesh: MeshMetrics) => {
    if (!data) return;
    const ranked = data.top10.find((item) => item.mesh_code === mesh.mesh_code);
    const selected = ranked ? { ...mesh, ...ranked } : mesh;
    setSelectedMesh(selected);
    setSelectedBuilding(null);
    setSideTab("detail");
    mapRef.current?.flyToMesh(selected);
  }, [data]);

  const allMeshes = useMemo(() => data?.meshes.features.flatMap((feature) => {
    const properties = feature.properties;
    const code = properties?.mesh_code;
    if (!properties || (typeof code !== "string" && typeof code !== "number")) return [];
    return [{ ...properties, mesh_code: String(code) } as MeshMetrics];
  }) ?? [], [data]);

  const robustLookup = useMemo(() => Object.fromEntries(
    (data?.robustness?.candidates ?? []).map((candidate) => [candidate.mesh_code, candidate])
  ) as Record<string, RobustCandidate>, [data]);
  const robustRanking = useMemo(() => (data?.robustness?.top_candidates ?? []).slice(0, 10).flatMap((candidate) => {
    const mesh = allMeshes.find((item) => item.mesh_code === candidate.mesh_code);
    return mesh ? [{ ...mesh, rank: candidate.robust_rank }] : [];
  }), [allMeshes, data]);
  const decisionPlan = data?.interventions?.plans[decisionMode][String(siteCount) as "1" | "2" | "3"] ?? null;
  const afterScores = useMemo(() => {
    if (mapPhase !== "after" || !decisionPlan) return null;
    return Object.fromEntries(Object.entries(decisionPlan.mesh_results).map(([code, result]) => [code, result.after_score_c]));
  }, [decisionPlan, mapPhase]);
  const decisionFlow = useMemo(() => {
    if (!decisionPlan || !selectedMesh) return null;
    const result = decisionPlan.mesh_results[selectedMesh.mesh_code];
    const site = decisionPlan.sites.find((item) => item.candidate_id === result?.assigned_site_id);
    const meshLongitude = finiteNumber(selectedMesh.centroid_lon);
    const meshLatitude = finiteNumber(selectedMesh.centroid_lat);
    if (!site || meshLongitude === null || meshLatitude === null || result.distance_reduction_m <= 0) return null;
    return { meshLongitude, meshLatitude, siteLongitude: site.longitude, siteLatitude: site.latitude };
  }, [decisionPlan, selectedMesh]);

  const runScenario = useCallback((point: VirtualPoint) => {
    const result = calculateScenario(allMeshes, point);
    setVirtualPoint(point);
    setScenario(result);
    setPlacementMode(false);
    setSideTab("scenario");
  }, [allMeshes]);

  const selectScenarioMesh = useCallback((meshCode: string) => {
    if (!data) return;
    const mesh = allMeshes.find((item) => item.mesh_code === meshCode);
    if (!mesh) return;
    const ranked = data.top10.find((item) => item.mesh_code === meshCode);
    const selected = ranked ? { ...mesh, ...ranked } : mesh;
    setSelectedMesh(selected);
    setSelectedBuilding(null);
    setSideTab("scenario");
    mapRef.current?.flyToMesh(selected);
  }, [allMeshes, data]);

  const resetScenario = useCallback(() => {
    setScenario(null);
    setVirtualPoint(null);
    setPlacementMode(false);
  }, []);

  const changeStoryStep = useCallback((step: number | null) => {
    setStoryStep(step);
    if (step === null) {
      setLayers((current) => ({ ...current, meshes: true }));
      setMetricMode("gap");
      setMapPhase("before");
    }
  }, []);

  const changeProductView = useCallback((next: ProductView) => {
    setProductView(next);
    setMapError(null);
    setMapWarning(null);
    setStoryStep(null);
    setSelectedBuilding(null);
    setPlacementMode(false);
    if (next === "workspace" || next === "futures") {
      setWorkspacePhase("baseline");
      setWorkspaceLayers(next === "futures"
        ? { ...INITIAL_WORKSPACE_LAYERS, meshes: false, roadNetwork: true, hazard: false }
        : INITIAL_WORKSPACE_LAYERS);
    }
  }, []);

  useEffect(() => {
    if (storyStep === null || !data?.finalDemo) return;
    const rankOne = data.top10[0];
    if (!rankOne) return;
    const timers: number[] = [];
    if (storyStep === 0) {
      setLayers((current) => ({ ...current, meshes: true, plateau: false }));
      setMetricMode("elderly");
      timers.push(window.setTimeout(() => setMetricMode("transport"), 1_300));
      timers.push(window.setTimeout(() => setMetricMode("medical"), 2_600));
      timers.push(window.setTimeout(() => setMetricMode("gap"), 3_900));
      setSelectedMesh(null);
      setSelectedBuilding(null);
      setSideTab("ranking");
      mapRef.current?.resetView();
    } else if (storyStep === 1) {
      setLayers((current) => ({ ...current, meshes: true, plateau: false }));
      setMetricMode("gap");
      setSelectedMesh(rankOne);
      setSelectedBuilding(null);
      setSideTab("detail");
      mapRef.current?.flyToMesh(rankOne);
    } else if (storyStep === 2) {
      setLayers((current) => ({ ...current, meshes: true, plateau: false }));
      setMetricMode("gap");
      setRankingView("robust");
      setSelectedMesh(rankOne);
      setSideTab("detail");
      mapRef.current?.flyToMesh(rankOne);
    } else if (storyStep === 3) {
      const deepMesh = allMeshes.find((mesh) => mesh.mesh_code === data.finalDemo?.deep_dive.mesh_code) ?? null;
      setLayers((current) => ({ ...current, plateau: true, meshes: false, stations: true, busStops: true, medical: true }));
      setMetricMode("gap");
      setSelectedMesh(deepMesh);
      const featured = data.plateauMetadata?.reference_layer?.featured_building;
      setSelectedBuilding(featured?.id ? {
        id: featured.id,
        usage: featured.usage ?? null,
        measuredHeight: finiteNumber(featured.measured_height_m),
        storeysAboveGround: finiteNumber(featured.storeys_above_ground),
        storeysBelowGround: finiteNumber(featured.storeys_below_ground),
        footprintArea: finiteNumber(featured.building_footprint_area_m2),
        totalFloorArea: finiteNumber(featured.total_floor_area_m2),
        lod: featured.lod === undefined ? null : `LOD${featured.lod}`
      } : null);
      setSideTab("detail");
      timers.push(window.setTimeout(() => mapRef.current?.flyToPlateau(), 120));
    } else if (storyStep === 4) {
      setLayers((current) => ({ ...current, meshes: true, plateau: true, stations: true, busStops: true, medical: true }));
      setSelectedBuilding(null);
      setSideTab("scenario");
      setDecisionMode("overall");
      setSiteCount(1);
      setMapPhase("after");
    } else if (storyStep === 5) {
      setSideTab("scenario");
      setDecisionMode("overall");
      setSiteCount(2);
      setMapPhase("after");
    } else if (storyStep === 6) {
      setSideTab("scenario");
      setDecisionMode("fairness");
      setSiteCount(2);
      setMapPhase("after");
    } else if (storyStep === 7) {
      setLayers((current) => ({ ...current, meshes: true, plateau: false }));
      setMapPhase("before");
    }
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [allMeshes, data, storyStep]);

  if (error) return <ErrorState message={error} onRetry={() => setRetryKey((key) => key + 1)} />;
  if (!data) return <LoadingState />;

  if (data.meshes.features.length === 0) {
    return (
      <>
        <EmptyState onMethodology={() => setMethodologyOpen(true)} />
        <MethodologyModal open={methodologyOpen} data={data} onClose={() => setMethodologyOpen(false)} />
      </>
    );
  }

  const legend = LEGENDS[metricMode];
  const eligibleCount = data.summary.record_counts?.primary_rank_eligible_meshes;
  const comparisonMeshCount = data.summary.record_counts?.population_unaffected;
  const plateauCoverage = summarizePlateauCoverage(data.plateauMetadata);
  const plateauYear = data.plateauMetadata?.year ?? data.plateauMetadata?.source_year;
  const isPrimary = data.city.mode === "primary_demo";
  const workspaceActive = productView === "workspace" && workspaceData !== null;
  const futuresMap = productView === "futures" && futuresData
    ? futuresData.cities[cityId].resilience_map
    : null;
  const mapLayers: LayerVisibility = productView === "workspace" || productView === "futures"
    ? {
        meshes: workspaceLayers.meshes,
        stations: false,
        busStops: false,
        medical: false,
        boundary: true,
        plateau: false
      }
    : layers;

  return (
    <div className={`app-shell ${productView === "workspace" ? "workspace-mode" : productView === "validation" ? "validation-mode" : productView === "futures" ? "futures-mode" : productView === "admin" ? "admin-mode" : ""}`}>
      <header className="app-header">
        <div className="brand-block">
          <div>
            <h1>CITY GAP</h1>
            <p>まちスコープ · 都市の必要とサービス到達性を読む</p>
          </div>
        </div>
        <div className="header-actions">
          <div className="product-switch" role="group" aria-label="CITY GAPの表示モード">
            <button type="button" className={productView === "demo" ? "active" : ""} aria-pressed={productView === "demo"} onClick={() => changeProductView("demo")}>公開デモ</button>
            <button type="button" className={productView === "workspace" ? "active" : ""} aria-pressed={productView === "workspace"} onClick={() => changeProductView("workspace")}>自治体Workspace</button>
            <button type="button" className={productView === "validation" ? "active" : ""} aria-pressed={productView === "validation"} onClick={() => changeProductView("validation")}>検証Evidence</button>
            <button type="button" className={productView === "futures" ? "active" : ""} aria-pressed={productView === "futures"} onClick={() => changeProductView("futures")}>時間・レジリエンス</button>
            <button type="button" className={productView === "admin" ? "active" : ""} aria-pressed={productView === "admin"} onClick={() => changeProductView("admin")}>運用管理</button>
          </div>
          <div className="city-switch" role="group" aria-label="分析都市を選択">
            <button type="button" className={cityId === "maizuru" ? "active" : ""} aria-pressed={cityId === "maizuru"} onClick={() => switchCity("maizuru")}>
              <strong>舞鶴市</strong><span>実証・施策シミュレーション</span>
            </button>
            <button type="button" className={cityId === "fujisawa" ? "active" : ""} aria-pressed={cityId === "fujisawa"} onClick={() => switchCity("fujisawa")}>
              <strong>藤沢市</strong><span>横展開検証</span>
            </button>
          </div>
          <button type="button" className="methodology-button" onClick={() => setMethodologyOpen(true)}>
            分析方法
          </button>
        </div>
      </header>

      {productView === "validation" ? (
        validationData ? <ValidationWorkspace data={validationData} cityId={cityId} /> : <LoadingState />
      ) : productView === "admin" ? (
        <MunicipalAdmin cityId={cityId} />
      ) : <>
      <main className="map-stage">
        <Suspense fallback={<div className="map-loading" role="status"><span /> 地図エンジンを準備中</div>}>
          <CesiumMap
            key={cityId}
            ref={mapRef}
            data={data}
            metricMode={metricMode}
            selectedMeshCode={selectedMesh?.mesh_code ?? null}
            visibility={mapLayers}
            placementMode={productView === "demo" && placementMode}
            virtualPoint={productView === "demo" ? virtualPoint : null}
            decisionSites={productView === "demo" && sideTab === "scenario" && decisionPlan ? decisionPlan.sites : []}
            afterScores={productView === "demo" && sideTab === "scenario" ? afterScores : null}
            decisionFlow={productView === "demo" && sideTab === "scenario" ? decisionFlow : null}
            workspaceMap={workspaceActive ? workspaceData.map : null}
            workspaceBuildingPoints={workspaceActive ? workspaceData.buildingPoints : null}
            futuresMap={futuresMap}
            futuresStressMode={futuresStressMode}
            workspacePhase={workspacePhase}
            workspaceVisibility={workspaceLayers}
            onMeshSelect={selectMesh}
            onVirtualPointSelect={runScenario}
            onBuildingSelect={setSelectedBuilding}
            onReady={() => setMapReady(true)}
            onError={setMapError}
            onWarning={setMapWarning}
          />
        </Suspense>

        {!mapReady && (
          <div className="map-loading" role="status"><span /> 3D地図を描画中</div>
        )}

        {mapError && (
          <div className="map-error-fallback" role="alert">
            <strong>3D地図を表示できません</strong>
            <p>{mapError}</p>
            <small>ランキング・地域詳細・計算方法は右側のパネルで引き続き確認できます。</small>
          </div>
        )}

        {mapWarning && !mapError && (
          <div className="map-warning" role="status">
            <span>{mapWarning}</span>
            <button type="button" aria-label="PLATEAU 3D読み込み警告を閉じる" onClick={() => setMapWarning(null)}>×</button>
          </div>
        )}

        {productView === "demo" && <div className="map-toolbar">
          <span className="toolbar-label">何を見る？</span>
          <MetricSelector value={metricMode} onChange={setMetricMode} />
        </div>}

        {productView === "demo" && <LayerPanel
          data={data}
          value={layers}
          open={layerPanelOpen}
          onOpenChange={setLayerPanelOpen}
          onChange={(nextLayers) => {
            setLayers(nextLayers);
            if (!nextLayers.plateau) setSelectedBuilding(null);
          }}
          onResetView={() => mapRef.current?.resetView()}
        />}

        {productView === "workspace" && (
          <div className="workspace-map-toolbar" role="group" aria-label="地図で表示する比較状態">
            <span>地図比較</span>
            <button type="button" className={workspacePhase === "baseline" ? "active" : ""} aria-pressed={workspacePhase === "baseline"} onClick={() => setWorkspacePhase("baseline")}>Baseline</button>
            <button type="button" disabled={!workspaceActive} className={workspacePhase === "scenario_a" ? "active" : ""} aria-pressed={workspacePhase === "scenario_a"} onClick={() => setWorkspacePhase("scenario_a")}>Scenario A</button>
            <button type="button" disabled={!workspaceActive} className={workspacePhase === "scenario_b" ? "active" : ""} aria-pressed={workspacePhase === "scenario_b"} onClick={() => setWorkspacePhase("scenario_b")}>Scenario B</button>
            <button type="button" disabled={!workspaceActive} className={workspacePhase === "scenario_c" ? "active" : ""} aria-pressed={workspacePhase === "scenario_c"} onClick={() => setWorkspacePhase("scenario_c")}>Scenario C</button>
          </div>
        )}

        {productView === "futures" && (
          <div className="futures-map-context" aria-label="地図の時間状態">
            <span><small>CITY</small>{data.city.name}</span>
            <span><small>DATA</small>2025 observed</span>
            <span><small>SCENARIO</small>{futureYear}</span>
            <span className={futuresStressMode === "normal" ? "" : "active"}><small>STRESS</small>{futuresStressMode}</span>
          </div>
        )}

        {productView === "demo" && isPrimary && data.finalDemo && storyStep === null && (
          <section className="product-intro">
            <p>舞鶴市 実証・施策シミュレーション</p>
            <h2>必要と、届きにくさの<br />重なりを見つける。</h2>
            <span>舞鶴市の人口・交通・医療・PLATEAUを重ね、単独の地図では見えない地域課題候補を発見します。</span>
            <div>
              <button type="button" className="primary-button" onClick={() => changeStoryStep(0)}>デモを見る</button>
              <button type="button" className="text-button" onClick={() => setMethodologyOpen(true)}>分析方法</button>
            </div>
          </section>
        )}

        {productView === "demo" && !isPrimary && storyStep === null && (
          <section className="validation-intro">
            <p>藤沢市 横展開検証</p>
            <strong>同じCITY GAP Engineを実データへ適用</strong>
            <span>市内263メッシュの相対比較。都市間でスコア値を直接比較しません。</span>
          </section>
        )}

        {productView === "demo" && isPrimary && data.finalDemo && storyStep !== null && (
          <StoryMode
            step={storyStep}
            onStart={() => changeStoryStep(0)}
            onStepChange={changeStoryStep}
            plateauMetadata={data.plateauMetadata}
            comparisonMeshCount={comparisonMeshCount}
            ready={mapReady && !mapError}
            finalDemo={data.finalDemo}
            rankOne={data.top10[0] ?? null}
            robustness={data.robustness}
            interventions={data.interventions}
            onOpenValidation={() => switchCity("fujisawa")}
          />
        )}

        {selectedBuilding && <BuildingInfoCard building={selectedBuilding} onClose={() => setSelectedBuilding(null)} />}

        {productView === "demo" && placementMode && (
          <div className="placement-banner" role="status">
            <span aria-hidden="true">⌖</span> 地図をクリックして仮想交通支援拠点を配置
            <button type="button" onClick={() => setPlacementMode(false)}>キャンセル</button>
          </div>
        )}

        {productView === "demo" && <div className="map-legend" aria-label={`${legend.title}の凡例`}>
          <strong>{legend.title}</strong>
          <div><span>{legend.low}</span><i /><span>{legend.high}</span></div>
          <small>色は地域間の相対比較です</small>
        </div>}

        {productView === "workspace" && (
          <div className="workspace-map-legend" aria-label="改善対象建物の凡例">
            <strong>建物のネットワーク距離改善帯</strong>
            <span><i className="band-low" />250m未満</span>
            <span><i className="band-mid" />250–499m</span>
            <span><i className="band-high" />500m以上</span>
            <small>建物別人数と厳密な改善値は表示しません</small>
          </div>
        )}

        {productView === "futures" && (
          <div className="futures-map-legend" aria-label="レジリエンス地図の凡例">
            <strong>地図表示</strong>
            <span><i className="normal" />選択node間の通常経路</span>
            <span><i className="alternative" />選択edge除外時の第2経路</span>
            <span><i className="critical" />network criticality候補</span>
            {futuresStressMode !== "normal" && <span><i className="area" />医療到達不能nodeの集約域</span>}
            {futuresStressMode !== "normal" && <span><i className="facility" />baseline医療到達先</span>}
            <small>経路・集約域はレビュー材料であり通行可否・被災予測ではありません</small>
          </div>
        )}

        <div className="source-chip">
          {productView === "workspace"
            ? "PLATEAU 2025 · 実ネットワーク · 公式計画/災害コンテキスト"
            : productView === "futures"
            ? "PLATEAU 2025 · 公式将来人口 · counterfactual stress test"
            : isPrimary && plateauCoverage.referenceIncluded
            ? `PLATEAU 舞鶴市 ${plateauYear ?? "年次不明"} · 3D建物 + 道路面`
            : `PLATEAU ${data.city.name} 2025 · 行政界 + 駅`}
        </div>
        {productView === "demo" && isPrimary && <div className="coverage-chip">Top 10内の公式建物 {top10CoverageLabel(plateauCoverage)} · 3Dは別候補で検証</div>}
      </main>

      {productView === "workspace" ? (
        <aside className="side-panel workspace-side-panel" aria-label="CITY GAP自治体Workspace">
          {workspaceData ? (
            <MunicipalWorkspace
              data={workspaceData}
              cityCode={data.city.code}
              phase={workspacePhase}
              layers={workspaceLayers}
              onPhaseChange={setWorkspacePhase}
              onLayersChange={setWorkspaceLayers}
            />
          ) : workspaceError ? (
            <div className="workspace-load-state" role="alert">
              <strong>Workspaceデータを読み込めません</strong>
              <p>{workspaceError}</p>
              <button type="button" onClick={() => {
                setWorkspaceError(null);
                setWorkspaceRetry((value) => value + 1);
              }}>再読み込み</button>
            </div>
          ) : (
            <div className="workspace-load-state" role="status"><span /> 自治体Workspaceを準備中</div>
          )}
        </aside>
      ) : productView === "futures" ? (
        <aside className="side-panel futures-side-panel" aria-label="CITY GAP時間・レジリエンスWorkspace">
          {futuresData ? (
            <UrbanFuturesWorkspace
              data={futuresData}
              cityId={cityId}
              futureYear={futureYear}
              stressMode={futuresStressMode}
              onFutureYearChange={setFutureYear}
              onStressModeChange={setFuturesStressMode}
            />
          ) : (
            <div className="workspace-load-state" role="status"><span /> 時間状態を準備中</div>
          )}
        </aside>
      ) : (
      <aside className="side-panel" aria-label="CITY GAP分析パネル">
        <div className="panel-summary">
          <div>
            <p>{isPrimary ? "PRIMARY DEMO" : "CROSS-CITY VALIDATION"} · {data.city.prefecture}</p>
            <h2>{data.city.name}・500mメッシュ</h2>
            <small>{isPrimary ? "実証・施策シミュレーション" : "同じ計算ロジックによる横展開検証"}</small>
          </div>
          <div className="summary-count">
            <strong>{data.meshes.features.length}</strong>
            <span>mesh</span>
          </div>
        </div>
        <div className="data-years" aria-label="使用データの年次">
          <span>人口 2020</span><span>医療 2020</span><span>バス停 2022</span><span>PLATEAU 2025</span>
        </div>
        <div className={`panel-tabs ${isPrimary ? "" : "validation"}`} role="tablist" aria-label="ランキング、詳細、施策シミュレーション">
          <button
            type="button"
            role="tab"
            aria-selected={sideTab === "ranking"}
            className={sideTab === "ranking" ? "active" : ""}
            onClick={() => setSideTab("ranking")}
          >
            TOP {data.top10.length}<span>ランキング</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={sideTab === "detail"}
            className={sideTab === "detail" ? "active" : ""}
            onClick={() => setSideTab("detail")}
          >
            DETAIL<span>選択地域</span>
          </button>
          {isPrimary && <button
            type="button"
            role="tab"
            aria-selected={sideTab === "scenario"}
            className={sideTab === "scenario" ? "active" : ""}
            onClick={() => setSideTab("scenario")}
          >
            DECISION<span>施策配置</span>
          </button>}
        </div>
        <div className="panel-scroll" role="tabpanel">
          {sideTab === "ranking" ? (
            <>
              <div className="ranking-intro">
                <div><span aria-hidden="true">⌖</span><strong>追加調査候補</strong></div>
                <p>{rankingView === "robust" ? "9条件でTop 10に残る回数と順位の安定性を表示。" : `${eligibleCount ? `${eligibleCount}件のPrimary対象から` : "Primary対象から"}探索スコア順に表示。`}カードを押すと現地へ移動します。</p>
              </div>
              {isPrimary && data.robustness && <div className="ranking-view-switch" role="group" aria-label="ランキング表示">
                <button type="button" className={rankingView === "score" ? "active" : ""} aria-pressed={rankingView === "score"} onClick={() => setRankingView("score")}>基準スコア</button>
                <button type="button" className={rankingView === "robust" ? "active" : ""} aria-pressed={rankingView === "robust"} onClick={() => setRankingView("robust")}>頑健ランキング</button>
              </div>}
              <RankingPanel
                items={rankingView === "robust" && robustRanking.length ? robustRanking : data.top10}
                selectedMeshCode={selectedMesh?.mesh_code ?? null}
                onSelect={selectMesh}
                mode={rankingView}
                robustness={robustLookup}
              />
              <p className="ranking-disclaimer">{rankingView === "robust" ? "出現回数は確率・信頼度ではありません。" : "探索スコアは政策的な公式指標や危険度ではありません。"}</p>
            </>
          ) : sideTab === "detail" ? (
            <DetailPanel mesh={selectedMesh} comparisonMeshCount={comparisonMeshCount} cityName={data.city.name} audit={data.summary.audit} robustness={selectedMesh ? robustLookup[selectedMesh.mesh_code] : undefined} plateauDetail={selectedMesh?.mesh_code === data.finalDemo?.deep_dive.mesh_code ? data.finalDemo?.deep_dive.building_demographics_detail ?? null : null} onEvidence={data.evidence ? () => setEvidenceOpen(true) : undefined} />
          ) : sideTab === "scenario" && isPrimary && data.interventions && decisionPlan ? (
              <ScenarioPanel
              interventions={data.interventions}
              plan={decisionPlan}
              mode={decisionMode}
              siteCount={siteCount}
              mapPhase={mapPhase}
              selectedMesh={selectedMesh}
              freeResult={scenario}
              placementMode={placementMode}
              onModeChange={(mode) => { setDecisionMode(mode); setMapPhase("before"); }}
              onSiteCountChange={(count) => { setSiteCount(count); setMapPhase("before"); }}
              onMapPhaseChange={(phase) => { setMapPhase(phase); setMetricMode("gap"); setLayers((current) => ({ ...current, meshes: true })); }}
              onSelectMesh={selectScenarioMesh}
              onStartPlacement={() => {
                setPlacementMode(true);
                setSelectedBuilding(null);
              }}
              onResetFree={resetScenario}
              onEvidence={() => setEvidenceOpen(true)}
            />
          ) : (
            <DetailPanel mesh={selectedMesh} comparisonMeshCount={comparisonMeshCount} cityName={data.city.name} audit={data.summary.audit} robustness={selectedMesh ? robustLookup[selectedMesh.mesh_code] : undefined} onEvidence={data.evidence ? () => setEvidenceOpen(true) : undefined} />
          )}
        </div>
      </aside>
      )}

      <MethodologyModal open={methodologyOpen} data={data} onClose={() => setMethodologyOpen(false)} />
      <EvidenceModal open={evidenceOpen} evidence={data.evidence} plan={decisionPlan} onClose={() => setEvidenceOpen(false)} />
      </>}
    </div>
  );
}
