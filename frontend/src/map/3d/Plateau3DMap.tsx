import { forwardRef, lazy, Suspense, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import type { AppData, BuildingInfo, MeshMetrics } from "../../types";
import type { SpatialSelection, SpatialViewport } from "../../state/spatial/types";
import type { MapEngineAdapter } from "../core/MapEngineAdapter";
import type { CesiumMapHandle } from "../../components/CesiumMap";

const CesiumMap = lazy(async () => {
  const module = await import("../../components/CesiumMap");
  return { default: module.CesiumMap };
});

interface Props {
  data: AppData;
  selection: SpatialSelection | null;
  viewport: SpatialViewport;
  activeLayerIds: string[];
  onSelectionChange(selection: SpatialSelection | null): void;
  onReady?(): void;
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
  if (selection?.type !== "mesh") return null;
  const ranked = data.top10.find((mesh) => mesh.mesh_code === selection.id);
  if (ranked) return ranked;
  const feature = data.meshes.features.find((candidate) => String(candidate.properties?.mesh_code) === selection.id);
  return feature?.properties ? { ...feature.properties, mesh_code: selection.id } as MeshMetrics : null;
}

function buildingSelection(data: AppData, building: BuildingInfo, current: SpatialSelection | null): SpatialSelection {
  return {
    type: "building",
    id: building.id,
    city: data.city.id,
    urbanState: "2025",
    label: building.usage ? `${building.usage}の建物` : "PLATEAU建物",
    longitude: current?.longitude,
    latitude: current?.latitude,
    properties: {
      usage: building.usage,
      measured_height_m: building.measuredHeight,
      storeys_above_ground: building.storeysAboveGround,
      storeys_below_ground: building.storeysBelowGround,
      footprint_area_m2: building.footprintArea,
      total_floor_area_m2: building.totalFloorArea,
      lod: building.lod,
      attribute_kind: "official_plateau"
    }
  };
}

export const Plateau3DMap = forwardRef<MapEngineAdapter, Props>(function Plateau3DMap({
  data,
  selection,
  viewport,
  activeLayerIds,
  onSelectionChange,
  onReady
}, ref) {
  const cesiumRef = useRef<CesiumMapHandle>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const mesh = useMemo(() => meshFromSelection(data, selection), [data, selection]);
  const buildings = activeLayerIds.includes("plateau-buildings");
  const roads = activeLayerIds.includes("plateau-roads");

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
    if (!ready) return;
    if (mesh) cesiumRef.current?.flyToMesh(mesh);
    else if (selection?.type === "building") cesiumRef.current?.flyToPlateau();
    else cesiumRef.current?.resetView();
  }, [mesh, ready, selection]);

  return (
    <div className="plateau-3d-shell" data-map-engine="cesium" data-ready={ready}>
      <Suspense fallback={<div className="map-engine-loading" role="status"><span />PLATEAU 3Dを読み込み中</div>}>
        <CesiumMap
          ref={cesiumRef}
          data={data}
          metricMode="gap"
          selectedMeshCode={mesh?.mesh_code ?? null}
          visibility={{ meshes: true, stations: false, busStops: false, medical: false, boundary: true, plateau: buildings || roads }}
          plateauVisibility={{ buildings, roads }}
          meshPresentation="outline"
          placementMode={false}
          virtualPoint={null}
          decisionSites={[]}
          afterScores={null}
          decisionFlow={null}
          workspaceMap={null}
          workspaceBuildingPoints={null}
          futuresMap={null}
          futuresStressMode="normal"
          workspacePhase="baseline"
          workspaceVisibility={EMPTY_WORKSPACE_LAYERS}
          onMeshSelect={(selected) => onSelectionChange({ type: "mesh", id: selected.mesh_code, city: data.city.id, urbanState: "2025", label: selected.area_label ? String(selected.area_label) : `500mメッシュ ${selected.mesh_code}`, longitude: Number(selected.centroid_lon), latitude: Number(selected.centroid_lat), properties: selected })}
          onVirtualPointSelect={() => undefined}
          onBuildingSelect={(building) => building ? onSelectionChange(buildingSelection(data, building, selection)) : undefined}
          onReady={() => { setReady(true); onReady?.(); }}
          onError={setError}
          onWarning={setWarning}
        />
      </Suspense>
      <div className="plateau-3d-context"><strong>PLATEAU 3D</strong><span>選択地点だけを詳しく確認</span><small>meshは薄い輪郭 · 建物と道路を個別表示</small></div>
      {warning && <div className="map-inline-warning" role="status">{warning}</div>}
      {error && <div className="map-engine-fallback" role="alert"><strong>3Dを表示できません</strong><p>{error}</p><span>2D地図と候補一覧は引き続き利用できます。</span></div>}
    </div>
  );
});
