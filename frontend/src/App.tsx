import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BuildingInfoCard } from "./components/BuildingInfoCard";
import { CesiumMap, type CesiumMapHandle } from "./components/CesiumMap";
import { DetailPanel } from "./components/DetailPanel";
import { EmptyState, ErrorState, LoadingState } from "./components/AppStates";
import { LayerPanel } from "./components/LayerPanel";
import { MethodologyModal } from "./components/MethodologyModal";
import { MetricSelector } from "./components/MetricSelector";
import { RankingPanel } from "./components/RankingPanel";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { StoryMode } from "./components/StoryMode";
import { loadAppData } from "./lib/data";
import { finiteNumber } from "./lib/format";
import { summarizePlateauCoverage, top10CoverageLabel } from "./lib/plateau";
import { calculateScenario, type ScenarioResult, type VirtualPoint } from "./lib/scenario";
import type { AppData, BuildingInfo, LayerVisibility, MeshMetrics, MetricMode } from "./types";

const INITIAL_LAYERS: LayerVisibility = {
  meshes: true,
  stations: true,
  busStops: false,
  medical: true,
  boundary: true,
  plateau: true
};

const LEGENDS: Record<MetricMode, { title: string; low: string; high: string }> = {
  gap: { title: "CITY GAP 探索スコア", low: "相対的に低い", high: "要追加調査" },
  elderly: { title: "65歳以上人口 percentile", low: "少ない", high: "多い" },
  transport: { title: "公共交通距離 percentile", low: "近い", high: "遠い" },
  medical: { title: "医療距離 percentile", low: "近い", high: "遠い" }
};

type SideTab = "ranking" | "detail" | "scenario";

export default function App() {
  const [data, setData] = useState<AppData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [metricMode, setMetricMode] = useState<MetricMode>("gap");
  const [layers, setLayers] = useState(INITIAL_LAYERS);
  const [layerPanelOpen, setLayerPanelOpen] = useState(false);
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const [selectedMesh, setSelectedMesh] = useState<MeshMetrics | null>(null);
  const [sideTab, setSideTab] = useState<SideTab>("ranking");
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
    setData(null);
    setMapReady(false);
    setMapError(null);
    setMapWarning(null);
    loadAppData()
      .then((loaded) => {
        if (cancelled) return;
        setData(loaded);
        setSelectedMesh(loaded.top10[0] ?? null);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "不明な読み込みエラーです");
      });
    return () => {
      cancelled = true;
    };
  }, [retryKey]);

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
    if (step === null) setLayers((current) => ({ ...current, meshes: true }));
  }, []);

  useEffect(() => {
    if (storyStep === null || !data) return;
    const rankOne = data.top10[0];
    if (!rankOne) return;
    let plateauFlyTimer: number | undefined;
    if (storyStep === 0) {
      setLayers((current) => ({ ...current, meshes: true, plateau: false }));
      setSelectedMesh(rankOne);
      setSelectedBuilding(null);
      setSideTab("ranking");
      mapRef.current?.flyToMesh(rankOne);
    } else if (storyStep === 1) {
      setLayers((current) => ({ ...current, meshes: true, plateau: false }));
      setSelectedMesh(rankOne);
      setSelectedBuilding(null);
      setSideTab("detail");
      mapRef.current?.flyToMesh(rankOne);
    } else if (storyStep === 2) {
      setLayers((current) => ({ ...current, plateau: true, meshes: false }));
      setSelectedMesh(null);
      setSelectedBuilding(null);
      setSideTab("ranking");
      plateauFlyTimer = window.setTimeout(() => mapRef.current?.flyToPlateau(), 120);
    } else if (storyStep === 3) {
      setLayers((current) => ({ ...current, meshes: true, plateau: false }));
      setSelectedBuilding(null);
      tryRankOne();
    }
    return () => {
      if (plateauFlyTimer !== undefined) window.clearTimeout(plateauFlyTimer);
    };
  }, [data, storyStep, tryRankOne]);

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

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true"><i /><i /><i /></div>
          <div className="team-name">まちスコープ</div>
          <div className="brand-rule" />
          <div>
            <h1>CITY GAP</h1>
            <p>まちの「必要」と「サービスの届き方」のズレを見つける</p>
          </div>
        </div>
        <div className="header-actions">
          <span className="real-data-badge"><i /> REAL DATA</span>
          <button type="button" className="methodology-button" onClick={() => setMethodologyOpen(true)}>
            <span aria-hidden="true">ⓘ</span>
            データと計算方法
          </button>
        </div>
      </header>

      <main className="map-stage">
        <CesiumMap
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

        <StoryMode
          step={storyStep}
          onStart={() => changeStoryStep(0)}
          onStepChange={changeStoryStep}
          plateauMetadata={data.plateauMetadata}
          comparisonMeshCount={comparisonMeshCount}
          ready={mapReady && !mapError}
        />

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
          {plateauCoverage.referenceIncluded
            ? `PLATEAU 舞鶴市 ${plateauYear ?? "年次不明"} · 公式3D Tiles`
            : "PLATEAU駅周辺3D Tiles: 収録状況を確認できません"}
        </div>
        <div className="coverage-chip">Top 10内のPLATEAU建物: {top10CoverageLabel(plateauCoverage)}</div>
      </main>

      <aside className="side-panel" aria-label="CITY GAP分析パネル">
        <div className="panel-summary">
          <div>
            <p>舞鶴市・500mメッシュ</p>
            <h2>追加調査候補</h2>
          </div>
          <div className="summary-count">
            <strong>{data.meshes.features.length}</strong>
            <span>mesh</span>
          </div>
        </div>
        <div className="panel-tabs" role="tablist" aria-label="ランキング、詳細、施策シミュレーション">
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
          <button
            type="button"
            role="tab"
            aria-selected={sideTab === "scenario"}
            className={sideTab === "scenario" ? "active" : ""}
            onClick={() => setSideTab("scenario")}
          >
            WHAT-IF<span>施策を試す</span>
          </button>
        </div>
        <div className="panel-scroll" role="tabpanel">
          {sideTab === "ranking" ? (
            <>
              <div className="ranking-intro">
                <div><span aria-hidden="true">⌖</span><strong>優先度の高い候補</strong></div>
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
            <DetailPanel mesh={selectedMesh} comparisonMeshCount={comparisonMeshCount} />
          ) : (
            <ScenarioPanel
              result={scenario}
              selectedMesh={selectedMesh}
              placementMode={placementMode}
              onStartPlacement={() => {
                setPlacementMode(true);
                setSelectedBuilding(null);
              }}
              onTryRankOne={tryRankOne}
              onSelectMesh={selectScenarioMesh}
              onReset={resetScenario}
              comparisonMeshCount={comparisonMeshCount}
            />
          )}
        </div>
      </aside>

      <MethodologyModal open={methodologyOpen} data={data} onClose={() => setMethodologyOpen(false)} />
    </div>
  );
}
