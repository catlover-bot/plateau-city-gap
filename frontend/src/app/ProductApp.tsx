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
import { PresentationGuide } from "../map/controls/PresentationGuide";
import { ResolutionRail } from "../map/controls/ResolutionRail";
import { LayerControls } from "../map/layers/LayerControls";
import { EvidenceModal } from "../components/EvidenceModal";
import { LoadingState, ErrorState } from "../components/AppStates";
import { useSpatialContext } from "./context/SpatialContext";
import { layerById } from "../map/layers/layerRegistry";
import { sceneForLayerPreset, sceneLayerIds, SCENE_PRESETS } from "../map/core/scenePresets";
import { loadAppData, loadMunicipalWorkspaceData, loadUrbanFuturesData, loadValidationCityData, loadValidationWorkspaceData } from "../lib/data";
import type { AppData, FuturesStressMode, GeoJsonFeatureCollection, InterventionPlan, MeshMetrics, MunicipalWorkspaceData, UrbanFuturesData, ValidationWorkspaceData } from "../types";
import { CITY_VIEWPORTS, type ProductTask, type ScenePresetId, type SpatialResolution, type SpatialSelection } from "../state/spatial/types";
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
  const [activeLayers, setActiveLayers] = useState<string[]>(sceneLayerIds(state.scenePreset));
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
    if ((state.task !== "try" && state.task !== "operate") || municipal) return;
    void loadMunicipalWorkspaceData().then(setMunicipal).catch(() => undefined);
  }, [municipal, state.task]);

  useEffect(() => { setActiveLayers(sceneLayerIds(state.scenePreset)); }, [state.scenePreset]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler);
  }, []);

  const data = datasets[state.city] ?? datasets.maizuru;
  const plan = data?.interventions?.plans.overall[String(siteCount) as "1" | "2" | "3"] ?? null;
  const scenario = useMemo(() => data ? scenarioCollections(data, plan) : { sites: EMPTY, meshes: EMPTY }, [data, plan]);
  const scenarioScores = useMemo(() => plan ? Object.fromEntries(Object.entries(plan.mesh_results).map(([code, result]) => [code, Number(result.after_score_c)]).filter((entry) => Number.isFinite(entry[1]))) : null, [plan]);
  const decisionFlow = useMemo(() => {
    if (!plan?.sites[0] || state.selection?.type !== "mesh" || state.selection.longitude === undefined || state.selection.latitude === undefined) return null;
    return { meshLongitude: state.selection.longitude, meshLatitude: state.selection.latitude, siteLongitude: plan.sites[0].longitude, siteLatitude: plan.sites[0].latitude };
  }, [plan, state.selection]);

  const selectMesh = useCallback((mesh: MeshMetrics) => {
    if (!data) return;
    dispatch({ type: "set-selection", selection: meshSelection(data, mesh) });
  }, [data, dispatch]);
  const select = useCallback((selection: SpatialSelection | null) => dispatch({ type: "set-selection", selection }), [dispatch]);
  const openPlateau3D = useCallback(() => {
    if (!data) return;
    const preserveDemo = state.demoMode;
    if (state.task !== "try" && state.task !== "operate" && state.task !== "detail") {
      dispatch({ type: "set-task", task: "detail" });
    }
    const deepDiveCode = data.plateauMetadata?.reference_layer?.deep_dive_mesh_code;
    const viewpoint = data.plateauMetadata?.reference_layer?.viewpoint;
    if (state.selection?.type !== "building" && state.selection?.id !== deepDiveCode && deepDiveCode) {
      const feature = data.meshes.features.find((candidate) => String(candidate.properties?.mesh_code) === deepDiveCode);
      const longitude = Number(feature?.properties?.centroid_lon ?? viewpoint?.longitude);
      const latitude = Number(feature?.properties?.centroid_lat ?? viewpoint?.latitude);
      dispatch({ type: "set-selection", selection: {
        type: "mesh",
        id: deepDiveCode,
        city: data.city.id,
        urbanState: "2025",
        label: data.plateauMetadata?.reference_layer?.area_label ?? `500mメッシュ ${deepDiveCode}`,
        longitude,
        latitude,
        properties: {
          ...(feature?.properties ?? {}),
          mesh_code: deepDiveCode,
          plateau_coverage: "verified_deep_dive",
          official_buildings_in_mesh: data.plateauMetadata?.reference_layer?.deep_dive_buildings,
        },
      } });
      if (Number.isFinite(longitude) && Number.isFinite(latitude)) {
        dispatch({ type: "set-viewport", viewport: { longitude, latitude, zoom: 15.2, bearing: 14, pitch: 42 } });
      }
    }
    dispatch({ type: "set-scene-preset", scenePreset: "plateau_detail" });
    if (preserveDemo) dispatch({ type: "set-demo-mode", enabled: true });
  }, [data, dispatch, state.demoMode, state.selection, state.task]);
  const changeTask = useCallback((task: ProductTask) => { if (state.primaryLayer === "validation-temporal" && task !== "validate") dispatch({ type: "set-viewport", viewport: CITY_VIEWPORTS[state.city] }); dispatch({ type: "set-task", task }); if (task !== "detail") dispatch({ type: "set-map-mode", mapMode: "map2d" }); }, [dispatch, state.city, state.primaryLayer]);
  const changeValidation = useCallback((view: ValidationView) => {
    setValidationView(view);
    if (view === "temporal") { dispatch({ type: "set-scene-preset", scenePreset: "temporal_change" }); dispatch({ type: "set-viewport", viewport: { longitude: 139.4465, latitude: 35.684, zoom: 13.2, bearing: 0, pitch: 0 } }); }
    else if (view === "reference") { dispatch({ type: "set-scene-preset", scenePreset: "validation_disagreement" }); dispatch({ type: "set-viewport", viewport: CITY_VIEWPORTS[state.city] }); }
  }, [dispatch, state.city]);
  const changeScene = useCallback((scenePreset: ScenePresetId) => {
    if (scenePreset === "plateau_detail") {
      openPlateau3D();
      return;
    }
    const preserveDemo = state.demoMode;
    const scene = SCENE_PRESETS[scenePreset];
    const task: ProductTask = scene.intent === "discover" ? "discover" : scene.intent === "inspect" ? "detail" : scene.intent === "scenario" || scene.intent === "resilience" ? "try" : "validate";
    dispatch({ type: "set-task", task });
    dispatch({ type: "set-scene-preset", scenePreset });
    if (preserveDemo) dispatch({ type: "set-demo-mode", enabled: true });
  }, [dispatch, openPlateau3D, state.demoMode]);
  const changeResolution = useCallback((resolution: SpatialResolution) => {
    if (resolution === "city") changeScene("city_overview");
    else if (resolution === "mesh") changeScene("gap_discovery");
    else if (resolution === "building") openPlateau3D();
    else if (resolution === "route") { openPlateau3D(); dispatch({ type: "set-scene-preset", scenePreset: "network_access" }); }
    else changeScene("scenario_compare");
  }, [changeScene, dispatch, openPlateau3D]);
  const share = useCallback(() => { void navigator.clipboard?.writeText(shareUrl); setMenuOpen(false); }, [shareUrl]);
  const selectContribution = useCallback((layerId: string) => {
    if (layerId === "plateau-buildings" || layerId === "plateau-terrain") {
      openPlateau3D();
      setActiveLayers((current) => [...new Set([...current, layerId, "plateau-buildings", "plateau-roads"])]);
      return;
    }
    if (layerId === "plateau-roads") {
      openPlateau3D();
      dispatch({ type: "set-scene-preset", scenePreset: "network_access" });
      return;
    }
    dispatch({ type: "set-map-mode", mapMode: "map2d" });
    dispatch({ type: "set-primary-layer", primaryLayer: layerId });
    setActiveLayers((current) => [...new Set([...current, "reference-gsi-pale", layerId])]);
  }, [dispatch, openPlateau3D]);

  if (error && !data) return <ErrorState message={error} onRetry={() => setRetry((value) => value + 1)} />;
  if (!data) return <LoadingState />;

  const inspectorContent = state.task === "discover" ? <DiscoveryWorkspace data={data} selection={state.selection} onSelect={selectMesh} />
    : state.task === "detail" ? <DetailWorkspace selection={state.selection} onOpen3D={openPlateau3D} />
      : state.task === "try" ? <ScenarioWorkspace plan={plan} mode={scenarioMode} siteCount={siteCount} futures={futures} city={state.city} stress={stress} onModeChange={(value) => { setScenarioMode(value); dispatch({ type: "set-scene-preset", scenePreset: value === "stress" ? "hazard_stress" : "scenario_compare" }); }} onSiteCountChange={setSiteCount} onStressChange={setStress} />
        : state.task === "validate" ? <ValidationInspector data={validation} city={state.city} view={validationView} onViewChange={changeValidation} />
          : <OperationsWorkspace data={municipal} onShare={share} onEvidence={() => setEvidenceOpen(true)} />;

  const compare = state.task === "try" && scenarioMode === "compare" && state.mapMode === "map2d" && Boolean(plan);
  return <div className="product-app" data-task={state.task} data-map-state={state.mapState} data-spatial-intent={state.intent} data-spatial-resolution={state.resolution} data-scene-preset={state.scenePreset}>
    <ProductHeader evidenceStatus={validation ? "検証済み" : "根拠あり"} onOpenMenu={() => setMenuOpen((value) => !value)} onOpenSearch={() => setSearchOpen(true)} />
    <TaskNavigation value={state.task} onChange={changeTask} />
    <main className="spatial-workbench">
      <section className={`map-stage ${compare ? "compare" : ""}`} aria-label="共通Spatial Map">
        <div className="map-toolbar">
          <MapModeSwitch value={state.mapMode} onChange={(mapMode) => {
            if (mapMode === "map2d") dispatch({ type: "set-map-mode", mapMode });
            else if (state.task === "try") { const scene = state.scenePreset; openPlateau3D(); dispatch({ type: "set-scene-preset", scenePreset: scene === "hazard_stress" ? "hazard_stress" : "scenario_compare" }); dispatch({ type: "set-map-mode", mapMode: "plateau3d" }); }
            else openPlateau3D();
          }} />
          <button type="button" className="share-map-button" onClick={share}>URLを共有</button>
          <button type="button" className={`presentation-trigger ${state.demoMode ? "active" : ""}`} aria-pressed={state.demoMode} onClick={() => dispatch({ type: "set-demo-mode", enabled: !state.demoMode })}>4分デモ</button>
        </div>
        <ResolutionRail value={state.resolution} onChange={changeResolution} />
        <LayerControls city={state.city} preset={state.preset} mapMode={state.mapMode} primaryLayer={state.primaryLayer} activeLayerIds={activeLayers} onPresetChange={(preset) => dispatch({ type: "set-scene-preset", scenePreset: sceneForLayerPreset(preset) })} onPrimaryLayerChange={(primaryLayer) => dispatch({ type: "set-primary-layer", primaryLayer })} onContextLayerToggle={(layerId) => setActiveLayers((current) => current.includes(layerId) ? current.filter((id) => id !== layerId) : [...current, layerId])} />
        <PresentationGuide open={state.demoMode} value={state.scenePreset} onClose={() => dispatch({ type: "set-demo-mode", enabled: false })} onSelect={changeScene} />
        {compare ? <div className="synchronized-maps"><div className="compare-map"><header><span>BEFORE</span><strong>2025 現況</strong></header><AnalyticalMap data={data} validation={validation} preset="discovery" primaryLayer="analysis-city-gap" activeLayerIdsOverride={["reference-gsi-pale"]} selection={state.selection} viewport={state.viewport} interactive onSelectionChange={select} onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })} /></div><div className="compare-map"><header><span>AFTER</span><strong>Scenario {siteCount === 1 ? "A" : siteCount === 2 ? "B" : "C"} · {siteCount}地点</strong></header><AnalyticalMap data={data} validation={validation} preset="scenario-compare" primaryLayer="scenario-footprint" activeLayerIdsOverride={activeLayers} selection={state.selection} viewport={state.viewport} scenarioSites={scenario.sites} scenarioMeshes={scenario.meshes} interactive onSelectionChange={select} onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })} /></div></div>
          : state.mapMode === "map2d" ? <AnalyticalMap ref={mapRef} data={data} validation={validation} preset={state.preset} primaryLayer={state.primaryLayer} activeLayerIdsOverride={activeLayers} selection={state.selection} viewport={state.viewport} scenarioSites={scenario.sites} scenarioMeshes={scenario.meshes} resilienceMap={futures?.cities[state.city].resilience_map ?? null} stressMode={stress} dimNonSelected={Boolean(state.selection)} onSelectionChange={select} onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })} onError={setError} />
            : <Plateau3DMap ref={mapRef} data={data} selection={state.selection} viewport={state.viewport} activeLayerIds={activeLayers} scenePreset={state.scenePreset} workspaceMap={state.task === "operate" ? municipal?.map ?? null : null} workspaceBuildingPoints={state.task === "operate" ? municipal?.buildingPoints ?? null : null} workspacePhase={state.task === "operate" ? (siteCount === 1 ? "scenario_a" : siteCount === 2 ? "scenario_b" : "scenario_c") : "baseline"} futuresMap={futures?.cities[state.city].resilience_map ?? null} stressMode={stress} decisionSites={state.task === "try" ? plan?.sites ?? [] : []} afterScores={state.task === "try" ? scenarioScores : null} decisionFlow={state.task === "try" ? decisionFlow : null} onSelectionChange={select} />}
        <ContextLegend layerId={state.primaryLayer} />
        {state.primaryLayer === "validation-temporal" && <div className="map-reference-badge"><span>VALIDATION REFERENCE</span><strong>国立市 · 2023→2025</strong></div>}
        {!state.inspectorOpen && <button type="button" className="open-inspector" onClick={() => dispatch({ type: "set-inspector-open", open: true })}>地点情報を開く</button>}
      </section>
      <ContextInspector data={data} selection={state.selection} primaryLayer={state.primaryLayer} open={state.inspectorOpen} onClose={() => dispatch({ type: "set-inspector-open", open: false })} onOpenEvidence={() => setEvidenceOpen(true)} onContributionSelect={selectContribution}>{inspectorContent}</ContextInspector>
    </main>
    {menuOpen && <aside className="utility-menu" aria-label="設定と管理"><header><strong>運用メニュー</strong><button type="button" onClick={() => setMenuOpen(false)}>×</button></header><button type="button" onClick={() => { changeTask("operate"); setMenuOpen(false); }}>自治体ワークフロー</button><button type="button" onClick={() => { changeTask("validate"); setMenuOpen(false); }}>検証状態</button><button type="button" onClick={share}>現在のURLをコピー</button><small>分析値と公開境界は既存パイプラインを維持</small></aside>}
    <SpatialSearch open={searchOpen} data={data} onClose={() => setSearchOpen(false)} onMesh={selectMesh} onTask={changeTask} />
    <EvidenceModal open={evidenceOpen} evidence={data.evidence} plan={plan} onClose={() => setEvidenceOpen(false)} />
    {error && <div className="nonblocking-error" role="alert">{error}<button type="button" onClick={() => setError(null)}>閉じる</button></div>}
    <div className="screen-reader-map-summary" aria-live="polite">{layerById(state.primaryLayer)?.name}を表示。{state.selection ? `${state.selection.label ?? state.selection.id}を選択中。` : "地点は未選択。"}</div>
  </div>;
}
