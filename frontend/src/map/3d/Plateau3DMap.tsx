import { forwardRef, lazy, Suspense, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import type { AppData, BuildingInfo, FuturesStressMode, GeoJsonFeatureCollection, InterventionSite, MeshMetrics, RoadInfo, WorkspaceBuildingPoints, WorkspaceMapData, WorkspacePhase } from "../../types";
import type { AnalysisLens, CounterfactualState, SpatialSelection, SpatialViewport } from "../../state/spatial/types";
import type { ScenePresetId } from "../../state/spatial/types";
import type { MapEngineAdapter } from "../core/MapEngineAdapter";
import type { CesiumMapHandle } from "../../components/CesiumMap";
import { SCENE_PRESETS } from "../core/scenePresets";
import type { VisualReadinessResult, VisualReadinessSnapshot } from "./readiness/visualReadiness";
import type { SectionData } from "../../features/urban-section/sectionTypes";
import { recordReadinessMetric } from "./readiness/performanceMetrics";
import { supportsVerifiedLocalView, VERIFIED_LOCAL_READINESS_TIMEOUT_MS } from "./verifiedLocalView";

const CesiumMap = lazy(async () => {
  const module = await import("../../components/CesiumMap");
  return { default: module.CesiumMap };
});

interface Props {
  data: AppData;
  selection: SpatialSelection | null;
  viewport: SpatialViewport;
  activeLayerIds: string[];
  scenePreset: ScenePresetId;
  analysisLens: AnalysisLens;
  counterfactualState: CounterfactualState;
  showUrbanSection?: boolean;
  sectionData?: SectionData | null;
  sectionFocus?: { longitude: number; latitude: number } | null;
  uiMode?: "advanced" | "guided";
  preferredBuildingSource?: "spatial-pack" | "verified-local";
  verifiedLocalPresentation?: boolean;
  workspaceMap?: WorkspaceMapData | null;
  workspaceBuildingPoints?: WorkspaceBuildingPoints | null;
  workspacePhase?: WorkspacePhase;
  futuresMap?: GeoJsonFeatureCollection | null;
  stressMode?: FuturesStressMode;
  decisionSites?: InterventionSite[];
  afterScores?: Record<string, number> | null;
  decisionFlow?: { meshLongitude: number; meshLatitude: number; siteLongitude: number; siteLatitude: number } | null;
  onSelectionChange(selection: SpatialSelection | null): void;
  onReady?(): void;
  onVisualReadinessChange?(snapshot: VisualReadinessSnapshot, result: VisualReadinessResult): void;
  onError?(message: string | null): void;
  onReturnTo2D?(): void;
}

const EMPTY_WORKSPACE_LAYERS = {
  meshes: false,
  affectedBuildings: false,
  routes: false,
  plateauBuildings: false,
  roadNetwork: false,
  landuse: false,
  planning: false,
  hazard: false
};

function meshFromSelection(data: AppData, selection: SpatialSelection | null): MeshMetrics | null {
  const meshCode = selection?.type === "mesh" || selection?.type === "building_group" ? selection.id : selection?.properties?.parent_mesh_code;
  if (typeof meshCode !== "string") return null;
  const ranked = data.top10.find((mesh) => mesh.mesh_code === meshCode);
  if (ranked) return ranked;
  const feature = data.meshes.features.find((candidate) => String(candidate.properties?.mesh_code) === meshCode);
  return feature?.properties ? { ...feature.properties, mesh_code: meshCode } as MeshMetrics : null;
}

function buildingSelection(data: AppData, building: BuildingInfo, current: SpatialSelection | null): SpatialSelection {
  return {
    type: "building",
    id: building.id,
    city: data.city.id,
    urbanState: "2025",
    label: building.usage ? `${building.usage}の建物` : "PLATEAU建物",
    longitude: building.longitude ?? current?.longitude,
    latitude: building.latitude ?? current?.latitude,
    properties: {
      usage: building.usage,
      measured_height_m: building.measuredHeight,
      storeys_above_ground: building.storeysAboveGround,
      storeys_below_ground: building.storeysBelowGround,
      footprint_area_m2: building.footprintArea,
      total_floor_area_m2: building.totalFloorArea,
      lod: building.lod,
      attribute_kind: "official_plateau"
      ,source_version: String(data.plateauMetadata?.year ?? 2025)
      ,parent_mesh_code: current?.type === "mesh" || current?.type === "building_group"
        ? current.id
        : current?.properties?.parent_mesh_code ?? data.plateauMetadata?.reference_layer?.deep_dive_mesh_code
      ,parent_finding_id: current?.type === "mesh" ? `finding:${current.id}` : current?.properties?.parent_finding_id
      ,position_semantics: building.positionSemantics
    }
  };
}

function roadSelection(data: AppData, road: RoadInfo, current: SpatialSelection | null): SpatialSelection {
  return {
    type: "road",
    id: road.id,
    city: data.city.id,
    urbanState: "2025",
    label: road.name ?? "PLATEAU道路",
    longitude: road.longitude ?? current?.longitude,
    latitude: road.latitude ?? current?.latitude,
    properties: {
      road_name: road.name,
      road_class: road.roadClass,
      road_function: road.roadFunction,
      source: road.source,
      source_version: String(data.plateauMetadata?.year ?? 2025),
      graph_semantics: road.graphSemantics,
      parent_mesh_code: current?.type === "mesh" || current?.type === "building_group"
        ? current.id
        : current?.properties?.parent_mesh_code,
    },
  };
}

function collectCoordinates(value: unknown, output: Array<[number, number]>) {
  if (!Array.isArray(value)) return;
  if (value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") {
    output.push([value[0], value[1]]);
    return;
  }
  value.forEach((item) => collectCoordinates(item, output));
}

function workspaceCamera(
  workspace: WorkspaceMapData | null,
  phase: WorkspacePhase,
  intent: "route" | "scenario" | "hazard",
): { longitude: number; latitude: number; range: number } | null {
  if (!workspace || phase === "baseline") return null;
  const layers = intent === "scenario"
    ? new Set(["representative_route", "representative_building", "scenario_site"])
    : new Set(["representative_route", "representative_building"]);
  const coordinates: Array<[number, number]> = [];
  workspace.features.forEach((feature) => {
    if (feature.properties?.story_id !== phase || !layers.has(String(feature.properties?.layer_type))) return;
    collectCoordinates(feature.geometry && "coordinates" in feature.geometry ? feature.geometry.coordinates : null, coordinates);
  });
  if (!coordinates.length) return null;
  const longitudes = coordinates.map(([longitude]) => longitude);
  const latitudes = coordinates.map(([, latitude]) => latitude);
  const minLongitude = Math.min(...longitudes);
  const maxLongitude = Math.max(...longitudes);
  const minLatitude = Math.min(...latitudes);
  const maxLatitude = Math.max(...latitudes);
  const latitude = (minLatitude + maxLatitude) / 2;
  const spanMeters = Math.hypot(
    (maxLongitude - minLongitude) * 111_000 * Math.cos(latitude * Math.PI / 180),
    (maxLatitude - minLatitude) * 111_000,
  );
  return {
    longitude: (minLongitude + maxLongitude) / 2,
    latitude,
    range: Math.max(intent === "scenario" ? 4_000 : 1_500, spanMeters * (intent === "scenario" ? 1.55 : 1.35)),
  };
}

export const Plateau3DMap = forwardRef<MapEngineAdapter, Props>(function Plateau3DMap({
  data,
  selection,
  viewport,
  activeLayerIds,
  scenePreset,
  analysisLens,
  counterfactualState,
  showUrbanSection = false,
  sectionData,
  sectionFocus,
  uiMode = "advanced",
  preferredBuildingSource,
  verifiedLocalPresentation = false,
  workspaceMap = null,
  workspaceBuildingPoints = null,
  workspacePhase = "baseline",
  futuresMap = null,
  stressMode = "normal",
  decisionSites = [],
  afterScores = null,
  decisionFlow = null,
  onSelectionChange,
  onReady,
  onVisualReadinessChange,
  onError,
  onReturnTo2D,
}, ref) {
  const cesiumRef = useRef<CesiumMapHandle>(null);
  const [ready, setReady] = useState(false);
  const [progressiveReady, setProgressiveReady] = useState(false);
  const [readiness, setReadiness] = useState<VisualReadinessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [verifiedLoadComplete, setVerifiedLoadComplete] = useState(false);
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;
  const readinessEventsRef = useRef({ interaction: false, visual: false, strict: false });
  const mesh = useMemo(() => meshFromSelection(data, selection), [data, selection]);
  const decisionTwinContext = scenePreset === "scenario_compare" || scenePreset === "hazard_stress";
  const buildings = activeLayerIds.includes("plateau-buildings") || decisionTwinContext;
  const roads = activeLayerIds.includes("plateau-roads") || decisionTwinContext;
  const terrain = activeLayerIds.includes("plateau-terrain") || decisionTwinContext;
  const deepDiveCode = data.plateauMetadata?.reference_layer?.deep_dive_mesh_code;
  const scene = SCENE_PRESETS[scenePreset];
  const guidedLocal = uiMode === "guided" && preferredBuildingSource === "verified-local";
  const advancedLocal = uiMode === "advanced" && supportsVerifiedLocalView({
    requested: verifiedLocalPresentation,
    city: data.city.id,
    scenePreset,
    selection,
    metadataMeshCode: deepDiveCode,
    sectionPackId: sectionData?.pack_id,
  });
  const localPresentation = guidedLocal || advancedLocal;
  const sceneReadiness = useMemo(() => localPresentation
    ? { ...scene.readiness, requiresVerifiedPack: true }
    : scene.readiness, [localPresentation, scene.readiness]);

  useEffect(() => {
    setVerifiedLoadComplete(false);
  }, [advancedLocal, attempt, deepDiveCode]);

  useEffect(() => {
    if (!advancedLocal || verifiedLoadComplete || error) return;
    const timer = window.setTimeout(() => {
      const message = "建物・道路・実DEMの描画を完了できませんでした。再試行するか、2D地図へ戻れます。";
      setError(message);
      onErrorRef.current?.(message);
    }, VERIFIED_LOCAL_READINESS_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [advancedLocal, attempt, error, verifiedLoadComplete]);

  useEffect(() => {
    setReady(false);
    setReadiness(null);
    readinessEventsRef.current = { interaction: false, visual: false, strict: false };
    document.documentElement.dataset.interactionReady = "false";
    document.documentElement.dataset.visualComplete = "false";
    document.documentElement.dataset.captureStrictReady = "false";
    document.documentElement.dataset.visualReady = "false";
  }, [analysisLens, attempt, counterfactualState, localPresentation, scenePreset]);

  const updateVisualReadiness = (snapshot: VisualReadinessSnapshot, result: VisualReadinessResult) => {
    onVisualReadinessChange?.(snapshot, result);
    setReadiness(result);
    setReady(result.interactionReady);
    if (result.captureStrictReady) setVerifiedLoadComplete(true);
    document.documentElement.dataset.interactionReady = String(result.interactionReady);
    document.documentElement.dataset.visualComplete = String(result.visualComplete);
    document.documentElement.dataset.captureStrictReady = String(result.captureStrictReady);
    document.documentElement.dataset.visualReady = String(result.captureStrictReady);
    document.documentElement.dataset.visualScene = scenePreset;
    document.documentElement.dataset.visualUnmet = result.unmet.join(",");
    if (result.interactionReady && !readinessEventsRef.current.interaction) {
      readinessEventsRef.current.interaction = true;
      window.dispatchEvent(new CustomEvent("citygap:interaction-ready", { detail: { scenePreset, snapshot } }));
      recordReadinessMetric("pack_interaction", scenePreset);
      onReady?.();
    }
    if (result.visualComplete && !readinessEventsRef.current.visual) {
      readinessEventsRef.current.visual = true;
      window.dispatchEvent(new CustomEvent("citygap:visual-complete", { detail: { scenePreset, snapshot } }));
      recordReadinessMetric("visual_complete", scenePreset);
    }
    if (result.captureStrictReady && !readinessEventsRef.current.strict) {
      readinessEventsRef.current.strict = true;
      window.dispatchEvent(new CustomEvent("citygap:visual-ready", { detail: { scenePreset, snapshot } }));
      recordReadinessMetric("capture_strict", scenePreset);
    }
  };

  useImperativeHandle(ref, () => ({
    setViewport() { if (!selection) cesiumRef.current?.resetView(); },
    getViewport() { return { ...viewport, pitch: 48 }; },
    fitBounds() { cesiumRef.current?.resetView(); },
    setSelection(next) {
      const target = meshFromSelection(data, next);
      if (target) cesiumRef.current?.flyToMesh(target);
    },
    setLayers() {},
    highlight(next) {
      const target = meshFromSelection(data, next);
      if (target) cesiumRef.current?.flyToMesh(target);
    },
    clearHighlight() { onSelectionChange(null); },
    async exportView() { return null; }
  }), [data, onSelectionChange, selection, viewport]);

  useEffect(() => {
    if (!progressiveReady) return;
    // The bounded local camera starts at the city model. Object/Section
    // selections update highlights without moving away from the same A–B scene.
    if (localPresentation) return;
    const cameraIntent = scene.camera === "route" || scene.camera === "scenario" || scene.camera === "hazard" ? scene.camera : null;
    const workspaceTarget = cameraIntent ? workspaceCamera(workspaceMap, workspacePhase, cameraIntent) : null;
    const deepDiveLongitude = data.plateauMetadata?.reference_layer?.viewpoint?.longitude;
    const deepDiveLatitude = data.plateauMetadata?.reference_layer?.viewpoint?.latitude;
    if (workspaceTarget && cameraIntent) cesiumRef.current?.flyToLocation(workspaceTarget.longitude, workspaceTarget.latitude, cameraIntent, workspaceTarget.range);
    else if (mesh?.mesh_code === deepDiveCode && scene.camera === "building" && typeof deepDiveLongitude === "number" && typeof deepDiveLatitude === "number") {
      cesiumRef.current?.flyToLocation(deepDiveLongitude, deepDiveLatitude, "building", 750);
    }
    else if (mesh?.mesh_code === deepDiveCode) cesiumRef.current?.flyToPlateau(scene.camera === "city" || scene.camera === "mesh" ? "building" : scene.camera);
    else if (mesh) cesiumRef.current?.flyToMesh(mesh);
    else if ((selection?.type === "road" || selection?.type === "terrain" || selection?.type === "planning" || selection?.type === "hazard") && selection.longitude !== undefined && selection.latitude !== undefined) {
      cesiumRef.current?.flyToLocation(selection.longitude, selection.latitude, selection.type === "road" ? "route" : selection.type === "hazard" ? "hazard" : "building", selection.type === "road" ? 760 : 920);
    }
    else if (selection?.type === "building") cesiumRef.current?.flyToPlateau(scene.camera === "city" || scene.camera === "mesh" ? "building" : scene.camera);
    else cesiumRef.current?.resetView();
  }, [data.plateauMetadata, deepDiveCode, localPresentation, mesh, progressiveReady, scene.camera, selection, workspaceMap, workspacePhase]);

  return (
    <div className="plateau-3d-shell" data-map-engine="cesium" data-ready={ready} data-ui-mode={uiMode} data-local-presentation={localPresentation} data-load-state={error ? "error" : verifiedLoadComplete ? "ready" : "loading"}>
      <Suspense fallback={<div className="map-engine-loading" role="status"><span />{uiMode === "guided" ? "建物・道路・地形を準備しています" : "PLATEAU 3Dを読み込み中"}</div>}>
        <CesiumMap
          key={attempt}
          ref={cesiumRef}
          data={data}
          metricMode="gap"
          selectedMeshCode={mesh?.mesh_code ?? null}
          selectedBuildingId={selection?.type === "building" ? selection.id : null}
          selectedRoadId={selection?.type === "road" ? typeof selection.properties?.renderer_road_id === "string" ? selection.properties.renderer_road_id : selection.id : null}
          analysisLens={analysisLens}
          counterfactualState={counterfactualState}
          readinessRequirements={sceneReadiness}
          showUrbanSection={showUrbanSection}
          sectionData={sectionData}
          sectionFocus={sectionFocus}
          preferredBuildingSource={advancedLocal ? "verified-local" : preferredBuildingSource}
          guidedPresentation={localPresentation}
          visibility={{ meshes: true, stations: false, busStops: false, medical: false, boundary: true, plateau: buildings || roads }}
          plateauVisibility={{ buildings, roads, terrain }}
          meshPresentation="outline"
          placementMode={false}
          virtualPoint={null}
          decisionSites={decisionSites}
          afterScores={afterScores}
          decisionFlow={decisionFlow}
          workspaceMap={workspaceMap}
          workspaceBuildingPoints={workspaceBuildingPoints}
          futuresMap={futuresMap}
          futuresStressMode={stressMode}
          workspacePhase={workspacePhase}
          workspaceVisibility={{
            ...EMPTY_WORKSPACE_LAYERS,
            affectedBuildings: scene.intent === "scenario",
            routes: scene.intent === "scenario" || scene.intent === "resilience",
            plateauBuildings: buildings,
            roadNetwork: roads,
            landuse: activeLayerIds.includes("plateau-landuse"),
            planning: activeLayerIds.includes("plateau-planning"),
            hazard: scene.intent === "resilience" || activeLayerIds.includes("hazard-composite"),
          }}
          onMeshSelect={(selected) => onSelectionChange({ type: "mesh", id: selected.mesh_code, city: data.city.id, urbanState: "2025", label: selected.area_label ? String(selected.area_label) : `500mメッシュ ${selected.mesh_code}`, longitude: Number(selected.centroid_lon), latitude: Number(selected.centroid_lat), properties: selected })}
          onVirtualPointSelect={() => undefined}
          onBuildingSelect={(building) => building ? onSelectionChange(buildingSelection(data, building, selection)) : undefined}
          onRoadSelect={(road) => onSelectionChange(roadSelection(data, road, selection))}
          onVisualReadinessChange={updateVisualReadiness}
          onReady={() => {
            setProgressiveReady(true);
            recordReadinessMetric("three_d_first_meaningful", scenePreset);
          }}
          onError={(message) => { setError(message); onError?.(message); }}
          onWarning={setWarning}
        />
      </Suspense>
      {!progressiveReady && !error && <div className="map-engine-loading" role="status"><span />{uiMode === "guided" ? "建物・道路・地形を準備しています" : "PLATEAU地物と背景図を読み込み中"}</div>}
      {progressiveReady && !ready && !error && <div className="visual-readiness-status" role="status">
        <span />
        {uiMode === "guided" ? "建物・道路・地形を確認しています" : "操作用の建物・道路・DEMを確認中"}
        {uiMode === "advanced" && <small>{readiness?.interactionUnmet.join(" · ")}</small>}
      </div>}
      {uiMode === "advanced" && !advancedLocal && <div className="plateau-3d-context"><strong>PLATEAU都市構造調査 · {scene.label}</strong><span>{scene.description}</span><small>全市建物はcamera配信 · 実DEM面は常団地前Deep Diveのみ · {scene.intent === "resilience" ? "災害予測ではなく仮定比較" : "公式地物とモデル結果を分離"}</small></div>}
      {warning && <div className="map-inline-warning" role="status">
        {uiMode === "guided" ? "一部の3D表示を読み込めません。街の断面で確認を続けられます。" : warning}
      </div>}
      {error && <div className="map-engine-fallback" role="alert">
        <strong>3Dを表示できません</strong>
        {uiMode === "advanced" && <p>{error}</p>}
        <span>{uiMode === "guided" ? "検証済みの建物・道路・地形データと街の断面で確認を続けられます。" : "2D地図と候補一覧は引き続き利用できます。"}</span>
        {advancedLocal && <div className="map-engine-fallback-actions">
          <button type="button" onClick={() => { setError(null); setWarning(null); setProgressiveReady(false); setAttempt((value) => value + 1); }}>3Dを再試行</button>
          {onReturnTo2D && <button type="button" onClick={onReturnTo2D}>2D地図に戻る</button>}
        </div>}
      </div>}
    </div>
  );
});
