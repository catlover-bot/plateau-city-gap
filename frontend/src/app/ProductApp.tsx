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
import { SavedInvestigationRail } from "../map/controls/SavedInvestigationRail";
import { ResolutionRail } from "../map/controls/ResolutionRail";
import { AnalysisLensRail } from "../map/controls/AnalysisLensRail";
import { LayerControls } from "../map/layers/LayerControls";
import { EvidenceModal } from "../components/EvidenceModal";
import { LoadingState, ErrorState } from "../components/AppStates";
import { useSpatialContext } from "./context/SpatialContext";
import { layerById } from "../map/layers/layerRegistry";
import { sceneForLayerPreset, sceneLayerIds, SCENE_PRESETS } from "../map/core/scenePresets";
import { loadAppData, loadGuidedAppData, loadMunicipalWorkspaceData, loadUrbanFuturesData, loadValidationCityData, loadValidationWorkspaceData } from "../lib/data";
import type { AppData, FuturesStressMode, GeoJsonFeatureCollection, InterventionPlan, MeshMetrics, MunicipalWorkspaceData, UrbanFuturesData, ValidationWorkspaceData } from "../types";
import { CITY_VIEWPORTS, type AnalysisLens, type ProductTask, type ScenePresetId, type SpatialResolution, type SpatialSelection, type SpatialViewport } from "../state/spatial/types";
import type { MapEngineAdapter } from "../map/core/MapEngineAdapter";
import type { UrbanObjectNode } from "../map/core/urbanObjectGraph";
import { recordReadinessMetric } from "../map/3d/readiness/performanceMetrics";
import { UrbanSection } from "../features/urban-section/UrbanSection";
import { InvestigationLanding } from "../features/investigation/ValueLanding";
import { GuidedSpatialWorkspace } from "../features/guided-spatial/GuidedSpatialWorkspace";
import { PublicAreaJourney } from "../features/area-investigation/PublicAreaJourney";
import { buildInvestigationWorkspace } from "../features/investigation/investigationModel";
import { loadInvestigationAreaFixture } from "../features/area-investigation/areaModel";
import type { InvestigationAreaFixture } from "../features/area-investigation/areaTypes";
import {
  loadPublicCartographyManifest,
  loadPublicStoryArtifact,
  loadPublicTargetData,
  type PublicCartographyData,
  type PublicStoryArtifactKind,
  type PublicStoryId,
  type PublicTargetData,
} from "../features/area-investigation/publicCartography";

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
  const initialMaizuruMode = useRef<"guided" | "full">(state.experience === "guided" ? "guided" : "full");
  const [maizuruDataMode, setMaizuruDataMode] = useState<"none" | "guided" | "full" | "loading-full" | "full-error">("none");
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
  const [areaFixture, setAreaFixture] = useState<InvestigationAreaFixture | null>(null);
  const [publicCartography, setPublicCartography] = useState<PublicCartographyData | null>(null);
  const [publicTargets, setPublicTargets] = useState<PublicTargetData | null>(null);
  const [areaError, setAreaError] = useState<string | null>(null);
  const [cartographyError, setCartographyError] = useState<string | null>(null);
  const [cartographyRequested, setCartographyRequested] = useState(false);
  const [storyCartographyRequested, setStoryCartographyRequested] = useState<PublicStoryArtifactKind | null>(null);
  const [storyCartographyLoading, setStoryCartographyLoading] = useState<PublicStoryArtifactKind | null>(null);
  const [targetCartographyError, setTargetCartographyError] = useState<string | null>(null);
  const [targetCartographyRequested, setTargetCartographyRequested] = useState(false);
  const [areaJourneyOpen, setAreaJourneyOpen] = useState(
    () => new URLSearchParams(window.location.search).get("journey") !== "m3",
  );
  const [urbanSectionOpen, setUrbanSectionOpen] = useState(
    () => new URLSearchParams(window.location.search).get("section") !== "closed",
  );
  const mapRef = useRef<MapEngineAdapter>(null);
  const visual2dParts = useRef(new Set<string>());

  useEffect(() => {
    let cancelled = false; setError(null);
    setMaizuruDataMode("none");
    const mode = initialMaizuruMode.current;
    const loader = mode === "guided" ? loadGuidedAppData : loadAppData;
    loader().then((data) => {
      if (cancelled) return;
      setDatasets((current) => ({ ...current, maizuru: data }));
      setMaizuruDataMode(mode);
    }).catch((reason: unknown) => !cancelled && setError(reason instanceof Error ? reason.message : "データを読み込めませんでした"));
    return () => { cancelled = true; };
  }, [retry]);

  useEffect(() => {
    if (state.experience === "guided" || maizuruDataMode !== "guided") return;
    let cancelled = false;
    setError(null);
    setMaizuruDataMode("loading-full");
    loadAppData()
      .then((data) => {
        if (cancelled) return;
        setDatasets((current) => ({ ...current, maizuru: data }));
        setMaizuruDataMode("full");
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : "詳細分析データを読み込めませんでした");
        setMaizuruDataMode("full-error");
      });
    return () => { cancelled = true; };
  }, [maizuruDataMode, state.experience]);

  useEffect(() => {
    let cancelled = false;
    loadInvestigationAreaFixture()
      .then((fixture) => { if (!cancelled) setAreaFixture(fixture); })
      .catch((reason: unknown) => {
        if (!cancelled) setAreaError(reason instanceof Error ? reason.message : "調査範囲データを読み込めませんでした");
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!datasets.maizuru || !areaFixture || !cartographyRequested || publicCartography || cartographyError) return;
    let cancelled = false;
    loadPublicCartographyManifest()
      .then((manifest) => { if (!cancelled) setPublicCartography({ manifest }); })
      .catch((reason: unknown) => {
        if (!cancelled) setCartographyError(reason instanceof Error ? reason.message : "PLATEAU表示用データを読み込めませんでした");
      });
    return () => { cancelled = true; };
  }, [areaFixture, cartographyError, cartographyRequested, datasets.maizuru, publicCartography]);

  useEffect(() => {
    const kind = storyCartographyRequested;
    if (!kind || publicCartography?.[kind] || cartographyError) return;
    const controller = new AbortController();
    setStoryCartographyLoading(kind);
    loadPublicStoryArtifact(kind, fetch, import.meta.env.BASE_URL, controller.signal)
      .then(({ manifest, collection }) => {
        setPublicCartography((current) => ({
          ...(current ?? { manifest }),
          manifest,
          [kind]: collection,
        }));
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setCartographyError(reason instanceof Error ? reason.message : "PLATEAU表示用データを読み込めませんでした");
      })
      .finally(() => {
        setStoryCartographyLoading((current) => current === kind ? null : current);
      });
    return () => controller.abort("superseded story request");
  }, [cartographyError, publicCartography, storyCartographyRequested]);

  useEffect(() => {
    if (!targetCartographyRequested || publicTargets || targetCartographyError) return;
    let cancelled = false;
    loadPublicTargetData()
      .then((targets) => { if (!cancelled) setPublicTargets(targets); })
      .catch((reason: unknown) => {
        if (!cancelled) setTargetCartographyError(reason instanceof Error ? reason.message : "確認対象の表示データを読み込めませんでした");
      });
    return () => { cancelled = true; };
  }, [publicTargets, targetCartographyError, targetCartographyRequested]);

  const requestTargetCartography = useCallback(() => {
    setTargetCartographyError(null);
    setTargetCartographyRequested(true);
  }, []);

  const requestStoryCartography = useCallback((story: PublicStoryId) => {
    const kind = story === "building-use" ? "buildings" : story === "urban-planning" ? "planning" : null;
    if (!kind) return;
    setCartographyError(null);
    setStoryCartographyRequested(kind);
  }, []);
  const cancelStoryCartography = useCallback(() => setStoryCartographyRequested(null), []);
  const updatePublicViewport = useCallback((viewport: SpatialViewport) => {
    dispatch({ type: "set-viewport", viewport });
  }, [dispatch]);

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
    if ((state.task !== "try" && state.task !== "operate" && state.task !== "detail" && state.mapMode !== "plateau3d") || municipal) return;
    void loadMunicipalWorkspaceData().then(setMunicipal).catch(() => undefined);
  }, [municipal, state.mapMode, state.task]);

  useEffect(() => { setActiveLayers(sceneLayerIds(state.scenePreset)); }, [state.scenePreset]);
  useEffect(() => {
    visual2dParts.current.clear();
    document.documentElement.dataset.interactionReady = "false";
    document.documentElement.dataset.visualComplete = "false";
    document.documentElement.dataset.captureStrictReady = "false";
    document.documentElement.dataset.visualReady = "false";
    document.documentElement.dataset.visualScene = state.scenePreset;
  }, [state.analysisLens, state.city, state.counterfactualState, state.mapMode, state.primaryLayer, state.scenePreset]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler);
  }, []);

  const data = datasets[state.city] ?? datasets.maizuru;
  const guidedData = datasets.maizuru ?? null;
  const investigationWorkspace = useMemo(
    () => guidedData ? buildInvestigationWorkspace(guidedData) : null,
    [guidedData],
  );
  useEffect(() => {
    if (data) recordReadinessMetric("app_shell", state.scenePreset);
  }, [data, state.scenePreset]);
  const plan = data?.interventions?.plans.overall[String(siteCount) as "1" | "2" | "3"] ?? null;
  const scenario = useMemo(() => data ? scenarioCollections(data, plan) : { sites: EMPTY, meshes: EMPTY }, [data, plan]);
  const scenarioScores = useMemo(() => plan ? Object.fromEntries(Object.entries(plan.mesh_results).map(([code, result]) => [code, Number(result.after_score_c)]).filter((entry) => Number.isFinite(entry[1]))) : null, [plan]);
  const selectedWorkspaceStory = siteCount === 1
      ? "scenario_a" as const
      : siteCount === 2
        ? "scenario_b" as const
        : "scenario_c" as const;
  const workspacePhase = state.analysisLens === "service-pulse"
    ? selectedWorkspaceStory
    : state.counterfactualState === "baseline" || (state.task !== "try" && state.task !== "operate")
      ? "baseline" as const
      : selectedWorkspaceStory;
  const decisionFlow = useMemo(() => {
    if (!plan?.sites[0] || state.selection?.type !== "mesh" || state.selection.longitude === undefined || state.selection.latitude === undefined) return null;
    return { meshLongitude: state.selection.longitude, meshLatitude: state.selection.latitude, siteLongitude: plan.sites[0].longitude, siteLatitude: plan.sites[0].latitude };
  }, [plan, state.selection]);

  const selectMesh = useCallback((mesh: MeshMetrics) => {
    if (!data) return;
    dispatch({ type: "set-selection", selection: meshSelection(data, mesh) });
  }, [data, dispatch]);
  const select = useCallback((selection: SpatialSelection | null) => dispatch({ type: "set-selection", selection }), [dispatch]);
  const startGuided = useCallback(() => {
    setEvidenceOpen(false);
    setAreaJourneyOpen(false);
    dispatch({ type: "set-guided-story", story: "intro" });
  }, [dispatch]);
  const restartGuided = useCallback(() => {
    setEvidenceOpen(false);
    setSearchOpen(false);
    setMenuOpen(false);
    setAreaJourneyOpen(true);
    dispatch({ type: "set-experience", experience: "landing" });
  }, [dispatch]);
  const openGuidedAdvanced = useCallback(() => {
    setEvidenceOpen(false);
    dispatch({ type: "set-task", task: "operate" });
    dispatch({ type: "set-experience", experience: "advanced" });
  }, [dispatch]);
  const startAreaJourney = useCallback(() => {
    setAreaJourneyOpen(true);
  }, []);
  const closeAreaJourney = useCallback(() => {
    setAreaJourneyOpen(false);
  }, []);
  const openAdvancedFromArea = useCallback(() => {
    setAreaJourneyOpen(false);
    openGuidedAdvanced();
  }, [openGuidedAdvanced]);
  const openPlateau3D = useCallback(() => {
    if (!data) return;
    const preserveSavedInvestigation = state.savedInvestigationOpen;
    if (state.task !== "try" && state.task !== "operate" && state.task !== "detail") {
      dispatch({ type: "set-task", task: "detail" });
    }
    const deepDiveCode = data.plateauMetadata?.reference_layer?.deep_dive_mesh_code;
    const viewpoint = data.plateauMetadata?.reference_layer?.viewpoint;
    if (!state.selection && deepDiveCode) {
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
    if (preserveSavedInvestigation) dispatch({ type: "set-saved-investigation-open", open: true });
  }, [data, dispatch, state.savedInvestigationOpen, state.selection, state.task]);
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
    const preserveSavedInvestigation = state.savedInvestigationOpen;
    const scene = SCENE_PRESETS[scenePreset];
    const task: ProductTask = scene.intent === "discover" ? "discover" : scene.intent === "inspect" ? "detail" : scene.intent === "scenario" || scene.intent === "resilience" ? "try" : "validate";
    dispatch({ type: "set-task", task });
    dispatch({ type: "set-scene-preset", scenePreset });
    if (preserveSavedInvestigation) dispatch({ type: "set-saved-investigation-open", open: true });
  }, [dispatch, openPlateau3D, state.savedInvestigationOpen]);
  const changeResolution = useCallback((resolution: SpatialResolution) => {
    dispatch({ type: "set-resolution", resolution });
    if (resolution === "city") {
      dispatch({ type: "set-map-mode", mapMode: "map2d" });
      dispatch({ type: "set-viewport", viewport: CITY_VIEWPORTS[state.city] });
      return;
    }
    if (resolution === "district") {
      dispatch({ type: "set-map-mode", mapMode: "map2d" });
      dispatch({ type: "set-viewport", viewport: { ...state.viewport, zoom: Math.max(12, state.viewport.zoom), bearing: 0, pitch: 0 } });
      return;
    }
    if (resolution === "mesh") {
      dispatch({ type: "set-map-mode", mapMode: "map2d" });
      dispatch({ type: "set-viewport", viewport: { ...state.viewport, zoom: Math.max(14.1, state.viewport.zoom), bearing: 0, pitch: 0 } });
      return;
    }
    if (resolution === "building_group" || resolution === "building") {
      openPlateau3D();
      dispatch({ type: "set-resolution", resolution });
      return;
    }
    if (resolution === "road") {
      openPlateau3D();
      dispatch({ type: "set-scene-preset", scenePreset: "network_access" });
      dispatch({ type: "set-resolution", resolution });
      return;
    }
    dispatch({ type: "set-scene-preset", scenePreset: "scenario_compare" });
    dispatch({ type: "set-resolution", resolution });
  }, [dispatch, openPlateau3D, state.city, state.viewport]);
  const share = useCallback(() => { void navigator.clipboard?.writeText(shareUrl); setMenuOpen(false); }, [shareUrl]);
  const mark2dReady = useCallback((part: string, expected = 1) => {
    visual2dParts.current.add(part);
    if (visual2dParts.current.size < expected) return;
    document.documentElement.dataset.interactionReady = "true";
    document.documentElement.dataset.visualComplete = "true";
    document.documentElement.dataset.captureStrictReady = "true";
    document.documentElement.dataset.visualReady = "true";
    document.documentElement.dataset.visualUnmet = "";
    recordReadinessMetric("map_2d_interaction", state.scenePreset);
    const detail = { scenePreset: state.scenePreset, engine: "maplibre", stableFrames: 3 };
    window.dispatchEvent(new CustomEvent("citygap:interaction-ready", { detail }));
    window.dispatchEvent(new CustomEvent("citygap:visual-complete", { detail }));
    window.dispatchEvent(new CustomEvent("citygap:visual-ready", { detail }));
  }, [state.scenePreset]);
  const markMapReady = useCallback(() => mark2dReady("map"), [mark2dReady]);
  const markBeforeReady = useCallback(() => mark2dReady("before", 2), [mark2dReady]);
  const markAfterReady = useCallback(() => mark2dReady("after", 2), [mark2dReady]);
  const selectObject = useCallback((node: UrbanObjectNode) => {
    const prefix = `${node.kind}:`;
    const id = node.id.startsWith(prefix) ? node.id.slice(prefix.length) : node.id;
    const type = node.kind === "site" ? "scenario_site" : node.kind;
    if (!["mesh", "building_group", "building", "road", "terrain", "planning", "hazard", "scenario_site"].includes(type)) return;
    dispatch({ type: "set-selection", selection: {
      type: type as SpatialSelection["type"],
      id,
      city: state.city,
      urbanState: state.urbanState,
      label: node.label,
      longitude: state.selection?.longitude,
      latitude: state.selection?.latitude,
      properties: {
        ...node.attributes,
        parent_mesh_code: state.selection?.type === "mesh"
          ? state.selection.id
          : state.selection?.properties?.parent_mesh_code,
      },
    } });
  }, [dispatch, state.city, state.selection, state.urbanState]);
  const selectPlateauBuilding = useCallback((id: string, properties: Record<string, unknown>) => {
    dispatch({ type: "set-selection", selection: {
      type: "building",
      id,
      city: state.city,
      urbanState: state.urbanState,
      label: `${String(properties.usage ?? "用途不明")}のPLATEAU建物`,
      longitude: state.selection?.longitude,
      latitude: state.selection?.latitude,
      properties: {
        ...properties,
        parent_mesh_code: "533513314",
        pack_id: "maizuru-533513314-plateau-2025-v1",
      },
    } });
  }, [dispatch, state.city, state.selection?.latitude, state.selection?.longitude, state.urbanState]);
  const changeAnalysisLens = useCallback((lens: AnalysisLens) => {
    if (lens === "urban-xray") {
      openPlateau3D();
      dispatch({ type: "set-resolution", resolution: "building_group" });
    } else if (lens === "service-pulse") {
      openPlateau3D();
      dispatch({ type: "set-scene-preset", scenePreset: "network_access" });
      dispatch({ type: "set-resolution", resolution: "road" });
    } else if (lens === "changed-only") {
      dispatch({ type: "set-task", task: "try" });
      dispatch({ type: "set-scene-preset", scenePreset: "scenario_compare" });
      dispatch({ type: "set-map-mode", mapMode: "plateau3d" });
      dispatch({ type: "set-resolution", resolution: "site" });
    } else if (lens === "temporal-ghost") {
      dispatch({ type: "set-task", task: "validate" });
      dispatch({ type: "set-scene-preset", scenePreset: "temporal_change" });
      dispatch({ type: "set-resolution", resolution: "building" });
    }
    dispatch({ type: "set-analysis-lens", lens });
  }, [dispatch, openPlateau3D]);

  if (state.experience === "landing") {
    if (areaJourneyOpen) {
      if (areaError) return <ErrorState message={areaError} onRetry={closeAreaJourney} />;
      if (!guidedData || !areaFixture) return <LoadingState />;
      return <PublicAreaJourney
        data={guidedData}
        fixture={areaFixture}
        cartography={publicCartography}
        cartographyError={cartographyError}
        targetCartography={publicTargets}
        targetCartographyError={targetCartographyError}
        storyCartographyLoading={storyCartographyLoading}
        onRequestCartography={() => {
          setCartographyError(null);
          setCartographyRequested(true);
        }}
        onRequestTargetCartography={requestTargetCartography}
        onRequestStoryCartography={requestStoryCartography}
        onCancelStoryCartography={cancelStoryCartography}
        state={state}
        onOpenAdvanced={openAdvancedFromArea}
        onSelectionChange={select}
        onViewportChange={updatePublicViewport}
      />;
    }
    if (error && !guidedData) return <ErrorState message={error} onRetry={() => setRetry((value) => value + 1)} />;
    if (!investigationWorkspace) return <LoadingState />;
    return <InvestigationLanding workspace={investigationWorkspace} onStart={startGuided} onStartArea={startAreaJourney} onRestart={restartGuided} />;
  }

  if (state.experience === "guided") {
    if (error && !guidedData) return <ErrorState message={error} onRetry={() => setRetry((value) => value + 1)} />;
    if (!guidedData) return <LoadingState />;
    return <>
      <GuidedSpatialWorkspace
        data={guidedData}
        state={state}
        onStoryChange={(story) => dispatch({ type: "set-guided-story", story })}
        onRestart={restartGuided}
        onOpenAdvanced={openGuidedAdvanced}
        onSelectionChange={select}
        onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })}
      />
      {error && <div className="nonblocking-error" role="alert">{error}<button type="button" onClick={() => setError(null)}>閉じる</button></div>}
    </>;
  }

  if (maizuruDataMode === "loading-full") return <LoadingState />;
  if (maizuruDataMode === "full-error" && error) return <ErrorState message={error} onRetry={() => setRetry((value) => value + 1)} />;

  if (error && !data) return <ErrorState message={error} onRetry={() => setRetry((value) => value + 1)} />;
  if (!data) return <LoadingState />;

  const inspectorContent = state.task === "discover" ? <DiscoveryWorkspace data={data} selection={state.selection} onSelect={selectMesh} />
    : state.task === "detail" ? <DetailWorkspace selection={state.selection} onOpen3D={openPlateau3D} />
      : state.task === "try" ? <ScenarioWorkspace plan={plan} mode={scenarioMode} siteCount={siteCount} futures={futures} city={state.city} stress={stress} onModeChange={(value) => { setScenarioMode(value); dispatch({ type: "set-scene-preset", scenePreset: value === "stress" ? "hazard_stress" : "scenario_compare" }); }} onSiteCountChange={setSiteCount} onStressChange={setStress} />
        : state.task === "validate" ? <ValidationInspector data={validation} city={state.city} view={validationView} onViewChange={changeValidation} />
          : <OperationsWorkspace data={municipal} onShare={share} onEvidence={() => setEvidenceOpen(true)} />;

  const compare = state.task === "try" && scenarioMode === "compare" && state.mapMode === "map2d" && Boolean(plan);
  return <div className="product-app" data-experience="advanced" data-task={state.task} data-map-state={state.mapState} data-spatial-intent={state.intent} data-spatial-resolution={state.resolution} data-scene-preset={state.scenePreset}>
    <ProductHeader evidenceStatus={validation ? "検証済み" : "根拠あり"} onOpenMenu={() => setMenuOpen((value) => !value)} onOpenSearch={() => setSearchOpen(true)} onRestart={restartGuided} />
    <main className="spatial-workbench">
      <TaskNavigation value={state.task} onChange={changeTask} />
      <section className={`map-stage ${compare ? "compare" : ""}`} aria-label="共通Spatial Map">
        <div className="map-toolbar">
          <MapModeSwitch value={state.mapMode} onChange={(mapMode) => {
            if (mapMode === "map2d") dispatch({ type: "set-map-mode", mapMode });
            else if (state.task === "try") { const scene = state.scenePreset; openPlateau3D(); dispatch({ type: "set-scene-preset", scenePreset: scene === "hazard_stress" ? "hazard_stress" : "scenario_compare" }); dispatch({ type: "set-map-mode", mapMode: "plateau3d" }); }
            else openPlateau3D();
          }} />
          <button type="button" className="share-map-button" onClick={share}>URLを共有</button>
          <button type="button" className={`saved-investigation-trigger ${state.savedInvestigationOpen ? "active" : ""}`} aria-pressed={state.savedInvestigationOpen} onClick={() => dispatch({ type: "set-saved-investigation-open", open: !state.savedInvestigationOpen })}>保存済み調査</button>
        </div>
        <ResolutionRail value={state.resolution} onChange={changeResolution} />
        <AnalysisLensRail value={state.analysisLens} counterfactual={state.counterfactualState} resolution={state.resolution} selection={state.selection} workspace={municipal?.map ?? null} workspacePhase={workspacePhase} onChange={changeAnalysisLens} onCounterfactualChange={(counterfactualState) => dispatch({ type: "set-counterfactual-state", state: counterfactualState })} />
        <LayerControls city={state.city} preset={state.preset} mapMode={state.mapMode} primaryLayer={state.primaryLayer} activeLayerIds={activeLayers} onPresetChange={(preset) => dispatch({ type: "set-scene-preset", scenePreset: sceneForLayerPreset(preset) })} onPrimaryLayerChange={(primaryLayer) => dispatch({ type: "set-primary-layer", primaryLayer })} onContextLayerToggle={(layerId) => setActiveLayers((current) => current.includes(layerId) ? current.filter((id) => id !== layerId) : [...current, layerId])} />
        <SavedInvestigationRail open={state.savedInvestigationOpen} value={state.scenePreset} onClose={() => dispatch({ type: "set-saved-investigation-open", open: false })} onSelect={changeScene} />
        {compare ? <div className="synchronized-maps"><div className="compare-map"><header><span>BEFORE</span><strong>2025 現況</strong></header><AnalyticalMap data={data} validation={validation} preset="discovery" primaryLayer="analysis-city-gap" activeLayerIdsOverride={["reference-gsi-pale"]} selection={state.selection} viewport={state.viewport} interactive onSelectionChange={select} onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })} onReady={markBeforeReady} /></div><div className="compare-map"><header><span>AFTER</span><strong>Scenario {siteCount === 1 ? "A" : siteCount === 2 ? "B" : "C"} · {siteCount}地点</strong></header><AnalyticalMap data={data} validation={validation} preset="scenario-compare" primaryLayer="scenario-footprint" activeLayerIdsOverride={activeLayers} selection={state.selection} viewport={state.viewport} scenarioSites={scenario.sites} scenarioMeshes={scenario.meshes} interactive onSelectionChange={select} onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })} onReady={markAfterReady} /></div></div>
          : state.mapMode === "map2d" ? <AnalyticalMap ref={mapRef} data={data} validation={validation} preset={state.preset} primaryLayer={state.primaryLayer} activeLayerIdsOverride={activeLayers} selection={state.selection} viewport={state.viewport} scenarioSites={scenario.sites} scenarioMeshes={scenario.meshes} resilienceMap={futures?.cities[state.city].resilience_map ?? null} stressMode={stress} dimNonSelected={Boolean(state.selection)} onSelectionChange={select} onViewportChange={(viewport) => dispatch({ type: "set-viewport", viewport })} onReady={markMapReady} onError={setError} />
            : <Plateau3DMap ref={mapRef} data={data} selection={state.selection} viewport={state.viewport} activeLayerIds={activeLayers} scenePreset={state.scenePreset} analysisLens={state.analysisLens} counterfactualState={state.counterfactualState} showUrbanSection={urbanSectionOpen} workspaceMap={municipal?.map ?? null} workspaceBuildingPoints={municipal?.buildingPoints ?? null} workspacePhase={workspacePhase} futuresMap={futures?.cities[state.city].resilience_map ?? null} stressMode={stress} decisionSites={state.task === "try" ? plan?.sites ?? [] : []} afterScores={state.task === "try" ? scenarioScores : null} decisionFlow={state.task === "try" ? decisionFlow : null} onSelectionChange={select} />}
        {state.mapMode === "plateau3d" && state.city === "maizuru" && <UrbanSection
          open={urbanSectionOpen}
          selection={state.selection}
          counterfactualState={state.counterfactualState}
          analysisLens={state.analysisLens}
          onClose={() => setUrbanSectionOpen((value) => !value)}
          onSelectBuilding={selectPlateauBuilding}
        />}
        <ContextLegend layerId={state.primaryLayer} />
        {state.primaryLayer === "validation-temporal" && <div className="map-reference-badge"><span>VALIDATION REFERENCE</span><strong>国立市 · 2023→2025</strong></div>}
        {!state.inspectorOpen && <button type="button" className="open-inspector" onClick={() => dispatch({ type: "set-inspector-open", open: true })}>地点情報を開く</button>}
      </section>
      <ContextInspector data={data} selection={state.selection} primaryLayer={state.primaryLayer} workspaceMap={municipal?.map ?? null} workspacePhase={workspacePhase} open={state.inspectorOpen} onClose={() => dispatch({ type: "set-inspector-open", open: false })} onOpenEvidence={() => setEvidenceOpen(true)} onObjectSelect={selectObject}>{inspectorContent}</ContextInspector>
    </main>
    {menuOpen && <aside className="utility-menu" aria-label="設定と管理"><header><strong>運用メニュー</strong><button type="button" onClick={() => setMenuOpen(false)}>×</button></header><button type="button" onClick={() => { changeTask("operate"); setMenuOpen(false); }}>自治体ワークフロー</button><button type="button" onClick={() => { changeTask("validate"); setMenuOpen(false); }}>検証状態</button><button type="button" onClick={share}>現在のURLをコピー</button><small>分析値と公開境界は既存パイプラインを維持</small></aside>}
    <SpatialSearch open={searchOpen} data={data} onClose={() => setSearchOpen(false)} onMesh={selectMesh} onTask={changeTask} />
    <EvidenceModal open={evidenceOpen} evidence={data.evidence} plan={plan} onClose={() => setEvidenceOpen(false)} />
    {error && <div className="nonblocking-error" role="alert">{error}<button type="button" onClick={() => setError(null)}>閉じる</button></div>}
    <div className="screen-reader-map-summary" aria-live="polite">{layerById(state.primaryLayer)?.name}を表示。{state.selection ? `${state.selection.label ?? state.selection.id}を選択中。` : "地点は未選択。"}</div>
  </div>;
}
