import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ProductHeader } from "../features/navigation/ProductHeader";
import { TaskNavigation } from "../features/navigation/TaskNavigation";
import { DiscoveryWorkspace } from "../features/discovery/DiscoveryWorkspace";
import { DetailWorkspace } from "../features/detail/DetailWorkspace";
import { ScenarioWorkspace } from "../features/scenario/ScenarioWorkspace";
import { ValidationInspector, type ValidationView } from "../features/validation/ValidationInspector";
import { OperationsWorkspace } from "../features/field/OperationsWorkspace";
import { ContextInspector } from "../features/inspector/ContextInspector";
import { SpatialSearch } from "../features/search/SpatialSearch";
import { AnalyticalMap } from "../map/2d/AnalyticalMap";
import { Plateau3DMap } from "../map/3d/Plateau3DMap";
import { ContextLegend } from "../map/controls/ContextLegend";
import { LayerControls } from "../map/layers/LayerControls";
import { EvidenceModal } from "../components/EvidenceModal";
import { LoadingState, ErrorState } from "../components/AppStates";
import { useSpatialContext } from "./context/SpatialContext";
import { activeLayerIds, layerById } from "../map/layers/layerRegistry";
import { loadAppData, loadMunicipalWorkspaceData, loadUrbanFuturesData, loadValidationCityData, loadValidationWorkspaceData } from "../lib/data";
import type { AppData, FuturesStressMode, GeoJsonFeatureCollection, InterventionPlan, MeshMetrics, MunicipalWorkspaceData, UrbanFuturesData, ValidationWorkspaceData } from "../types";
import { CITY_VIEWPORTS, type ProductTask, type SpatialSelection } from "../state/spatial/types";
import type { MapEngineAdapter } from "../map/core/MapEngineAdapter";

const EMPTY: GeoJsonFeatureCollection = { type: "FeatureCollection", features: [] };

function meshSelection(data: AppData, mesh: MeshMetrics): SpatialSelection {
  return { type: "mesh", id: mesh.mesh_code, city: data.city.id, urbanState: "2025", label: mesh.area_label ? String(mesh.area_label) : `500mメッシュ ${mesh.mesh_code}`, longitude: Number(mesh.centroid_lon), latitude: Number(mesh.centroid_lat), properties: mesh };
}

function scenarioCollections(data: AppData, plan: InterventionPlan | null): { sites: GeoJsonFeatureCollection; meshes: GeoJsonFeatureCollection } {
  if (!plan) return { sites: EMPTY, meshes: data.meshes };
  return {
    sites: { type: "FeatureCollection", features: plan.sites.map((site) => ({ type: "Feature", geometry: { type: "Point", coordinates: [site.longitude, site.latitude] }, properties: { ...site, scenario: site.site_order === 1 ? "A" : site.site_order === 2 ? "B" : "C" } })) },
    meshes: { type: "FeatureCollection", features: data.meshes.features.map((feature) => { const code = String(feature.properties?.mesh_code ?? ""); return { ...feature, properties: { ...feature.properties, ...(plan.mesh_results[code] ?? {}) } }; }) }
  };
}

function MapModeSwitch({ value, onChange }: { value: "map2d" | "plateau3d"; onChange(value: "map2d" | "plateau3d"): void }) {
  return <div className="map-mode-switch" role="group" aria-label="地図表示"><button type="button" className={value === "map2d" ? "active" : ""} aria-pressed={value === "map2d"} onClick={() => onChange("map2d")}>地図</button><button type="button" className={value === "plateau3d" ? "active" : ""} aria-pressed={value === "plateau3d"} onClick={() => onChange("plateau3d")}><b>PLATEAU</b> 3D</button></div>;
}

export function ProductApp() {
  const { state, dispatch, shareUrl } = useSpatialContext();
  const [datasets, setDatasets] = useState<Partial<Record<"maizuru" | "fujisawa", AppData>>>({});
  const [validation, setValidation] = useState<ValidationWorkspaceData | null>(null);
  const [municipal, setMunicipal] = useState<MunicipalWorkspaceData | null>(null);
  const [futures, setFutures] = useState<UrbanFuturesData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeLayers, setActiveLayers] = useState<string[]>(activeLayerIds(state.preset));
  const [siteCount, setSiteCount] = useState<1 | 2 | 3>(2);
  const [scenarioMode, setScenarioMode] = useState<"compare" | "stress">("compare");
  const [stress, setStress] = useState<FuturesStressMode>("normal");
  const [validationView, setValidationView] = useState<ValidationView>("reference");
  const mapRef = useRef<MapEngineAdapter>(null);

  useEffect(() => {
    let cancelled = false; setError(null);
    loadAppData().then((data) => !cancelled && setDatasets((current) => ({ ...current, maizuru: data }))).catch((reason: unknown) => !cancelled && setError(reason instanceof Error ? reason.message : "データを読み込めませんでした"));
    return () => { cancelled = true; };
  }, [retry]);

  useEffect(() => {
    if (state.city !== "fujisawa" || datasets.fujisawa) return;
    let cancelled = false;
    loadValidationCityData().then((data) => !cancelled && setDatasets((current) => ({ ...current, fujisawa: data }))).catch((reason: unknown) => !cancelled && setError(reason instanceof Error ? reason.message : "藤沢データを読み込めませんでした"));
    return () => { cancelled = true; };
  }, [datasets.fujisawa, state.city]);

  useEffect(() => {
    if (state.task !== "validate" || validation) return;
    void loadValidationWorkspaceData().then(setValidation).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "検証データを読み込めませんでした"));
  }, [state.task, validation]);
  useEffect(() => {
    if ((state.task !== "try" && state.task !== "operate") || futures) return;
    void loadUrbanFuturesData().then(setFutures).catch(() => undefined);
  }, [futures, state.task]);
  useEffect(() => {
    if (state.task !== "operate" || municipal) return;
    void loadMunicipalWorkspaceData().then(setMunicipal).catch(() => undefined);
  }, [municipal, state.task]);

  useEffect(() => { setActiveLayers(activeLayerIds(state.preset)); }, [state.preset]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler);
  }, []);

  const data = datasets[state.city] ?? datasets.maizuru;
  const plan = data?.interventions?.plans.overall[String(siteCount) as "1" | "2" | "3"] ?? null;
  const scenario = useMemo(() => data ? scenarioCollections(data, plan) : { sites: EMPTY, meshes: EMPTY }, [data, plan]);

  const selectMesh = useCallback((mesh: MeshMetrics) => {
    if (!data) return;
    dispatch({ type: "set-selection", selection: meshSelection(data, mesh) });
  }, [data, dispatch]);
  const select = useCallback((selection: SpatialSelection | null) => dispatch({ type: "set-selection", selection }), [dispatch]);
  const changeTask = useCallback((task: ProductTask) => { dispatch({ type: "set-task", task }); if (task !== "detail") dispatch({ type: "set-map-mode", mapMode: "map2d" }); }, [dispatch]);
  const changeValidation = useCallback((view: ValidationView) => {
    setValidationView(view);
    if (view === "temporal") { dispatch({ type: "set-primary-layer", primaryLayer: "validation-temporal" }); dispatch({ type: "set-viewport", viewport: { longitude: 139.4465, latitude: 35.684, zoom: 13.2, bearing: 0, pitch: 0 } }); setActiveLayers(["reference-gsi-pale", "validation-temporal"]); }
    else if (view === "reference") { dispatch({ type: "set-primary-layer", primaryLayer: "validation-disagreement" }); dispatch({ type: "set-viewport", viewport: CITY_VIEWPORTS[state.city] }); setActiveLayers(activeLayerIds("validation-compare")); }
  }, [dispatch, state.city]);
  const share = useCallback(() => { void navigator.clipboard?.writeText(shareUrl); setMenuOpen(false); }, [shareUrl]);

  if (error && !data) return <ErrorState message={error} onRetry={() => setRetry((value) => value + 1)} />;
  if (!data) return <LoadingState />;

  const inspectorContent = state.task === "discover" ? <DiscoveryWorkspace data={data} selection={state.selection} onSelect={selectMesh} />
    : state.task === "detail" ? <DetailWorkspace selection={state.selection} onOpen3D={() => dispatch({ type: "set-map-mode", mapMode: "plateau3d" })} />
      : state.task === "try" ? <ScenarioWorkspace plan={plan} mode={scenarioMode} siteCount={siteCount} futures={futures} city={state.city} stress={stress} onModeChange={(value) => { setScenarioMode(value); if (value === "stress") { dispatch({ type: "set-preset", preset: "hazard", primaryLayer: "hazard-composite" }); } else dispatch({ type: "set-preset", preset: "scenario-compare", primaryLayer: "scenario-footprint" }); }} onSiteCountChange={setSiteCount} onStressChange={setStress} />
        : state.task === "validate" ? <ValidationInspector data={validation} city={state.city} view={validationView} onViewChange={changeValidation} />
          : <OperationsWorkspace data={municipal} onShare={share} onEvidence={() => setEvidenceOpen(true)} />;

  const compare = state.task === "try" && scenarioMode === "compare" && state.mapMode === "map2d" && Boolean(plan);
  return <div className="product-app" data-task={state.task} data-map-state={state.mapState}>
    <ProductHeader evidenceStatus={validation ? "検証済み" : "根拠あり"} onOpenMenu={() => setMenuOpen((value) => !value)} onOpenSearch={() => setSearchOpen(true)} />
    <TaskNavigation value={state.task} onChange={changeTask} />
    <main className="spatial-workbench">
      <section className={`map-stage ${compare ? "compare" : ""}`} aria-label="共通Spatial Map">
        <div className="map-toolbar">
          <MapModeSwitch value={state.mapMode} onChange={(mapMode) => dispatch({ type: "set-map-mode", mapMode })} />
          <button type="button" className="share-map-button" onClick={share}>URLを共有</button>
        </div>
        <LayerControls city={state.city} preset={state.preset} mapMode={state.mapMode} primaryLayer={state.primaryLayer} activeLayerIds={activeLayers} onPresetChange={(preset, primaryLayer, layerIds) => { dispatch({ type: "set-preset", preset, primaryLayer }); setActiveLayers(layerIds); }} onPrimaryLayerChange={(primaryLayer) => dispatch({ type: "set-primary-layer", primaryLayer })} onContextLayerToggle={(layerId) => setActiveLayers((current) => current.includes(layerId) ? current.filter((id) => id !== layerId) : [...current, layerId])} />
        {compare ? <div className="synchronized-maps"><div className="compare-map"><header><span>BEFORE</span><strong>2025 現況</strong></header><AnalyticalMap data={data} validation={validation} preset="discovery" primaryLayer="analysis-city-gap" activeLayerIdsOverride={["reference-gsi-pale"]} selection={state.selection} viewport={state.viewport} interactive onSelectionChange={select} onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })} /></div><div className="compare-map"><header><span>AFTER</span><strong>Scenario {siteCount === 1 ? "A" : siteCount === 2 ? "B" : "C"} · {siteCount}地点</strong></header><AnalyticalMap data={data} validation={validation} preset="scenario-compare" primaryLayer="scenario-footprint" activeLayerIdsOverride={activeLayers} selection={state.selection} viewport={state.viewport} scenarioSites={scenario.sites} scenarioMeshes={scenario.meshes} interactive onSelectionChange={select} onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })} /></div></div>
          : state.mapMode === "map2d" ? <AnalyticalMap ref={mapRef} data={data} validation={validation} preset={state.preset} primaryLayer={state.primaryLayer} activeLayerIdsOverride={activeLayers} selection={state.selection} viewport={state.viewport} scenarioSites={scenario.sites} scenarioMeshes={scenario.meshes} resilienceMap={futures?.cities[state.city].resilience_map ?? null} stressMode={stress} dimNonSelected={Boolean(state.selection)} onSelectionChange={select} onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })} onError={setError} />
            : <Plateau3DMap ref={mapRef} data={data} selection={state.selection} viewport={state.viewport} activeLayerIds={activeLayers} onSelectionChange={select} />}
        <ContextLegend layerId={state.primaryLayer} />
        {state.primaryLayer === "validation-temporal" && <div className="map-reference-badge"><span>VALIDATION REFERENCE</span><strong>国立市 · 2023→2025</strong></div>}
        {!state.inspectorOpen && <button type="button" className="open-inspector" onClick={() => dispatch({ type: "set-inspector-open", open: true })}>地点情報を開く</button>}
      </section>
      <ContextInspector data={data} selection={state.selection} primaryLayer={state.primaryLayer} open={state.inspectorOpen} onClose={() => dispatch({ type: "set-inspector-open", open: false })} onOpenEvidence={() => setEvidenceOpen(true)}>{inspectorContent}</ContextInspector>
    </main>
    {menuOpen && <aside className="utility-menu" aria-label="設定と管理"><header><strong>運用メニュー</strong><button type="button" onClick={() => setMenuOpen(false)}>×</button></header><button type="button" onClick={() => { changeTask("operate"); setMenuOpen(false); }}>自治体ワークフロー</button><button type="button" onClick={() => { changeTask("validate"); setMenuOpen(false); }}>検証状態</button><button type="button" onClick={share}>現在のURLをコピー</button><small>分析値と公開境界は既存パイプラインを維持</small></aside>}
    <SpatialSearch open={searchOpen} data={data} onClose={() => setSearchOpen(false)} onMesh={selectMesh} onTask={changeTask} />
    <EvidenceModal open={evidenceOpen} evidence={data.evidence} plan={plan} onClose={() => setEvidenceOpen(false)} />
    {error && <div className="nonblocking-error" role="alert">{error}<button type="button" onClick={() => setError(null)}>閉じる</button></div>}
    <div className="screen-reader-map-summary" aria-live="polite">{layerById(state.primaryLayer)?.name}を表示。{state.selection ? `${state.selection.label ?? state.selection.id}を選択中。` : "地点は未選択。"}</div>
  </div>;
}
