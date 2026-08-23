import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BuildingInfoCard } from "./components/BuildingInfoCard";
import type { CesiumMapHandle } from "./components/CesiumMap";
import { DetailPanel } from "./components/DetailPanel";
import { EmptyState, ErrorState, LoadingState } from "./components/AppStates";
import { LayerPanel } from "./components/LayerPanel";
import { MethodologyModal } from "./components/MethodologyModal";
import { MetricSelector } from "./components/MetricSelector";
import { RankingPanel } from "./components/RankingPanel";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { StoryMode } from "./components/StoryMode";
import { loadAppData, loadValidationCityData } from "./lib/data";
import { finiteNumber } from "./lib/format";
import { summarizePlateauCoverage, top10CoverageLabel } from "./lib/plateau";
import { calculateScenario, type ScenarioResult, type VirtualPoint } from "./lib/scenario";
import type { AppData, BuildingInfo, LayerVisibility, MeshMetrics, MetricMode, PlacementCandidate } from "./types";

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

const LEGENDS: Record<MetricMode, { title: string; low: string; high: string }> = {
  gap: { title: "CITY GAP 探索スコア", low: "相対的に低い", high: "要追加調査" },
  elderly: { title: "65歳以上人口 percentile", low: "少ない", high: "多い" },
  transport: { title: "公共交通距離 percentile", low: "近い", high: "遠い" },
  medical: { title: "医療距離 percentile", low: "近い", high: "遠い" }
};

type SideTab = "ranking" | "detail" | "scenario";
type CityId = "maizuru" | "fujisawa";

export default function App() {
  const [datasets, setDatasets] = useState<Record<CityId, AppData> | null>(null);
  const [cityId, setCityId] = useState<CityId>("maizuru");
  const data = datasets?.[cityId] ?? null;
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [metricMode, setMetricMode] = useState<MetricMode>("gap");
  const [layers, setLayers] = useState(INITIAL_LAYERS);
  const [layerPanelOpen, setLayerPanelOpen] = useState(false);
  const [methodologyOpen, setMethodologyOpen] = useState(false);
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
  const mapRef = useRef<CesiumMapHandle>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setDatasets(null);
    setMapReady(false);
    setMapError(null);
    setMapWarning(null);
    Promise.all([loadAppData(), loadValidationCityData()])
      .then(([maizuru, fujisawa]) => {
        if (cancelled) return;
        setDatasets({ maizuru, fujisawa });
        setSelectedMesh(maizuru.top10[0] ?? null);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "不明な読み込みエラーです");
      });
    return () => {
      cancelled = true;
    };
  }, [retryKey]);

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

  const runScenario = useCallback((point: VirtualPoint) => {
    const result = calculateScenario(allMeshes, point);
    setVirtualPoint(point);
    setScenario(result);
    setPlacementMode(false);
    setSideTab("scenario");
  }, [allMeshes]);

  const tryRankOne = useCallback(() => {
    const rankOne = data?.top10[0];
    const longitude = finiteNumber(rankOne?.centroid_lon);
    const latitude = finiteNumber(rankOne?.centroid_lat);
    if (!rankOne || longitude === null || latitude === null) return;
    setSelectedMesh(rankOne);
    setSelectedBuilding(null);
    mapRef.current?.flyToMesh(rankOne);
    runScenario({ longitude, latitude });
  }, [data, runScenario]);

  const tryCandidate = useCallback((candidate: PlacementCandidate) => {
    const mesh = allMeshes.find((item) => item.mesh_code === candidate.top_improvement_mesh);
    if (mesh) {
      setSelectedMesh(mesh);
      setSelectedBuilding(null);
      mapRef.current?.flyToMesh(mesh);
    }
    runScenario({ longitude: candidate.longitude, latitude: candidate.latitude });
  }, [allMeshes, runScenario]);

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
    } else if (storyStep === 3) {
      setLayers((current) => ({ ...current, meshes: true, plateau: true, stations: true, busStops: true, medical: true }));
      setSelectedBuilding(null);
      const best = data.finalDemo?.placement_optimization.candidates[0];
      if (best) tryCandidate(best);
    } else if (storyStep === 4) {
      setSideTab("scenario");
    }
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [allMeshes, data, storyStep, tryCandidate]);

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

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <div>
            <h1>CITY GAP</h1>
            <p>まちスコープ · 都市の必要とサービス到達性を読む</p>
          </div>
        </div>
        <div className="header-actions">
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

      <main className="map-stage">
        <Suspense fallback={<div className="map-loading" role="status"><span /> 地図エンジンを準備中</div>}>
          <CesiumMap
            key={cityId}
            ref={mapRef}
            data={data}
            metricMode={metricMode}
            selectedMeshCode={selectedMesh?.mesh_code ?? null}
            visibility={layers}
            placementMode={placementMode}
            virtualPoint={virtualPoint}
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

        <div className="map-toolbar">
          <span className="toolbar-label">何を見る？</span>
          <MetricSelector value={metricMode} onChange={setMetricMode} />
        </div>

        <LayerPanel
          data={data}
          value={layers}
          open={layerPanelOpen}
          onOpenChange={setLayerPanelOpen}
          onChange={(nextLayers) => {
            setLayers(nextLayers);
            if (!nextLayers.plateau) setSelectedBuilding(null);
          }}
          onResetView={() => mapRef.current?.resetView()}
        />

        {isPrimary && data.finalDemo && storyStep === null && (
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

        {!isPrimary && storyStep === null && (
          <section className="validation-intro">
            <p>藤沢市 横展開検証</p>
            <strong>同じCITY GAP Engineを実データへ適用</strong>
            <span>市内263メッシュの相対比較。都市間でスコア値を直接比較しません。</span>
          </section>
        )}

        {isPrimary && data.finalDemo && storyStep !== null && (
          <StoryMode
            step={storyStep}
            onStart={() => changeStoryStep(0)}
            onStepChange={changeStoryStep}
            plateauMetadata={data.plateauMetadata}
            comparisonMeshCount={comparisonMeshCount}
            ready={mapReady && !mapError}
            finalDemo={data.finalDemo}
            rankOne={data.top10[0] ?? null}
          />
        )}

        {selectedBuilding && <BuildingInfoCard building={selectedBuilding} onClose={() => setSelectedBuilding(null)} />}

        {placementMode && (
          <div className="placement-banner" role="status">
            <span aria-hidden="true">⌖</span> 地図をクリックして仮想交通支援拠点を配置
            <button type="button" onClick={() => setPlacementMode(false)}>キャンセル</button>
          </div>
        )}

        <div className="map-legend" aria-label={`${legend.title}の凡例`}>
          <strong>{legend.title}</strong>
          <div><span>{legend.low}</span><i /><span>{legend.high}</span></div>
          <small>色は地域間の相対比較です</small>
        </div>

        <div className="source-chip">
          {isPrimary && plateauCoverage.referenceIncluded
            ? `PLATEAU 舞鶴市 ${plateauYear ?? "年次不明"} · 3D建物 + 道路面`
            : `PLATEAU ${data.city.name} 2025 · 行政界 + 駅`}
        </div>
        {isPrimary && <div className="coverage-chip">Top 10内の公式建物 {top10CoverageLabel(plateauCoverage)} · 3Dは別候補で検証</div>}
      </main>

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
            WHAT-IF<span>施策を試す</span>
          </button>}
        </div>
        <div className="panel-scroll" role="tabpanel">
          {sideTab === "ranking" ? (
            <>
              <div className="ranking-intro">
                <div><span aria-hidden="true">⌖</span><strong>追加調査候補</strong></div>
                <p>{eligibleCount ? `${eligibleCount}件のPrimary対象から` : "Primary対象から"}探索スコア順に表示。カードを押すと現地へ移動します。</p>
              </div>
              <RankingPanel
                items={data.top10}
                selectedMeshCode={selectedMesh?.mesh_code ?? null}
                onSelect={selectMesh}
              />
              <p className="ranking-disclaimer">探索スコアは政策的な公式指標や危険度ではありません。</p>
            </>
          ) : sideTab === "detail" ? (
            <DetailPanel mesh={selectedMesh} comparisonMeshCount={comparisonMeshCount} cityName={data.city.name} audit={data.summary.audit} />
          ) : sideTab === "scenario" && isPrimary && data.finalDemo ? (
              <ScenarioPanel
              result={scenario}
              selectedMesh={selectedMesh}
              placementMode={placementMode}
              onStartPlacement={() => {
                setPlacementMode(true);
                setSelectedBuilding(null);
              }}
                onTryRankOne={tryRankOne}
              candidates={data.finalDemo.placement_optimization.candidates}
                onTryCandidate={tryCandidate}
              onSelectMesh={selectScenarioMesh}
              onReset={resetScenario}
              comparisonMeshCount={comparisonMeshCount}
            />
          ) : (
            <DetailPanel mesh={selectedMesh} comparisonMeshCount={comparisonMeshCount} cityName={data.city.name} audit={data.summary.audit} />
          )}
        </div>
      </aside>

      <MethodologyModal open={methodologyOpen} data={data} onClose={() => setMethodologyOpen(false)} />
    </div>
  );
}
