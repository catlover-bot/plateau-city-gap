import { useCallback, useEffect, useState } from "react";
import type { AppData } from "../../types";
import type { SpatialSelection, SpatialViewport } from "../../state/spatial/types";
import { Plateau3DMap } from "../../map/3d/Plateau3DMap";
import type { VisualReadinessResult, VisualReadinessSnapshot } from "../../map/3d/readiness/visualReadiness";
import type { SectionData } from "../urban-section/sectionTypes";
import { loadGuided3DData } from "./guided3d";

const LAYERS = ["plateau-buildings", "plateau-roads", "plateau-terrain"];

export function Guided3DView({ data, selection, viewport, sectionData, sectionFocus, onSelectionChange, onReturnTo2D }: {
  data: AppData;
  selection: SpatialSelection;
  viewport: SpatialViewport;
  sectionData: SectionData | null;
  sectionFocus: { longitude: number; latitude: number } | null;
  onSelectionChange(selection: SpatialSelection | null): void;
  onReturnTo2D(): void;
}) {
  const [threeDData, setThreeDData] = useState<AppData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [rendered, setRendered] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      controller.abort();
      setError("3Dの準備に時間がかかっています。再試行するか、2D地図で確認を続けられます。");
    }, 30_000);
    setError(null);
    setRendered(false);
    setThreeDData(null);
    loadGuided3DData(data, controller.signal).then((value) => {
      window.clearTimeout(timer);
      if (!controller.signal.aborted) setThreeDData(value);
    }).catch((reason: unknown) => {
      window.clearTimeout(timer);
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "3Dを読み込めません");
    });
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [attempt, data]);
  // Rendering has its own bounded wait, separate from the metadata request.
  useEffect(() => {
    if (!threeDData || rendered) return;
    const timer = window.setTimeout(() => setError("建物・道路・地形の描画が完了しませんでした。"), 45_000);
    return () => window.clearTimeout(timer);
  }, [threeDData, rendered]);
  const onReadiness = useCallback((_snapshot: VisualReadinessSnapshot, result: VisualReadinessResult) => {
    if (result.captureStrictReady) setRendered(true);
  }, []);
  return <div className="guided-3d-view" data-guided-3d-state={error ? "error" : rendered ? "ready" : "loading"}>
    {threeDData && !error && <Plateau3DMap
      key={attempt}
      data={threeDData}
      selection={selection}
      viewport={viewport}
      activeLayerIds={LAYERS}
      scenePreset="plateau_detail"
      analysisLens="none"
      counterfactualState="baseline"
      uiMode="guided"
      preferredBuildingSource="verified-local"
      showUrbanSection={Boolean(sectionData)}
      sectionData={sectionData}
      sectionFocus={sectionFocus}
      onSelectionChange={onSelectionChange}
      onVisualReadinessChange={onReadiness}
      onError={(message) => { if (message) setError(message); }}
    />}
    {threeDData && rendered && !error && <aside className="guided-3d-source" aria-label="3Dモデルの出典と対象範囲">
      <strong>PLATEAUの建物・道路・地形 · 舞鶴市 {String(threeDData.plateauMetadata?.year ?? "データなし")}</strong>
      <span>LOD1・局所DEM · 検証済み3D対象 {threeDData.plateauMetadata?.reference_layer?.deep_dive_buildings?.toLocaleString("ja-JP") ?? "—"}棟（画面内の描画数ではありません）</span>
      <small>背景：地理院タイル（平面） · ドラッグで移動、右ドラッグで拡大、中ドラッグで角度</small>
    </aside>}
    {!threeDData && !error && <div className="guided-3d-message" role="status">PLATEAUの建物・道路・地形を準備しています</div>}
    {error && <div className="guided-3d-message" role="alert">
      <strong>3Dを表示できません</strong><p>{error}</p>
      <button type="button" className="guided-secondary-action" onClick={() => setAttempt((value) => value + 1)}>3Dを再試行</button>
      <button type="button" className="guided-secondary-action" onClick={onReturnTo2D}>2D地図に戻る</button>
    </div>}
  </div>;
}
