import { useEffect, useMemo, useState } from "react";
import type { AppData } from "../../types";
import type { SpatialSelection, SpatialViewport } from "../../state/spatial/types";
import { Plateau3DMap } from "../../map/3d/Plateau3DMap";
import { UrbanSection } from "../urban-section/UrbanSection";
import type { SectionData } from "../urban-section/sectionTypes";
import type { GuidedAreaContext } from "../guided-spatial/guidedTypes";
import { loadGuidedAreaCatalog, loadGuidedAreaContext, loadGuidedSectionData } from "../guided-spatial/guidedData";
import { guidedObjectTarget, supportsGuided3D } from "../guided-spatial/guided3d";
import { advancedExactObject, advancedNumber } from "./advanced3dModel";
import "./advanced-3d.css";

interface Props {
  data: AppData;
  area: SpatialSelection;
  selection: SpatialSelection | null;
  viewport: SpatialViewport;
  onSelectionChange(selection: SpatialSelection | null): void;
  onReturnTo2D(): void;
  onGuided(): void;
  onTools(): void;
  onShare(): void;
}

export function Advanced3DWorkspace({ data, area, selection, viewport, onSelectionChange, onReturnTo2D, onGuided, onTools, onShare }: Props) {
  const [bundle, setBundle] = useState<{ context: GuidedAreaContext; section: SectionData } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [sectionOpen, setSectionOpen] = useState(false);
  const [sectionFocus, setSectionFocus] = useState<{ longitude: number; latitude: number } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setBundle(null);
    setError(null);
    setSectionFocus(null);
    const timeout = window.setTimeout(() => {
      controller.abort();
      if (active) setError("地域と断面の準備が時間内に終わりませんでした。再読み込みするか、地図に戻れます。");
    }, 20_000);
    void (async () => {
      const catalog = await loadGuidedAreaCatalog(controller.signal);
      const item = catalog.items.find((candidate) => candidate.mesh_code === area.id);
      if (!item) throw new Error("選択した地域のデータが見つかりません。");
      const context = await loadGuidedAreaContext(item, controller.signal);
      if (!supportsGuided3D(area.id, context)) throw new Error("この地域には、対応する3D・断面データがありません。");
      const section = await loadGuidedSectionData(context.section, controller.signal);
      if (active && !controller.signal.aborted) setBundle({ context, section });
    })().catch((reason: unknown) => {
      if (active && !controller.signal.aborted) setError(reason instanceof Error ? reason.message : "地域データを読み込めませんでした。");
    }).finally(() => window.clearTimeout(timeout));
    return () => { active = false; controller.abort(); window.clearTimeout(timeout); };
  }, [area.id, attempt]);
  const context = bundle?.context.mesh_code === area.id ? bundle.context : null;
  const section = context ? bundle!.section : null;
  const object = useMemo(() => advancedExactObject(selection, context), [selection, context]);
  const target = useMemo(() => guidedObjectTarget(object, context), [object, context]);
  const properties = object?.properties ?? {};
  const areaProperties = area.properties ?? {};
  const selectedUnmatched = selection?.type === "building" || selection?.type === "road";
  const selectSectionBuilding = (id: string, attrs: Record<string, unknown>) => {
    // Section-only nearby objects are not automatically exact in the selected Area.
    onSelectionChange({ ...area, type: "building", id, label: "断面のPLATEAU建物", properties: { ...attrs, parent_mesh_code: area.id } });
  };
  return <div className="product-app advanced-3d-product" data-experience="advanced" data-area-id={area.id}
    data-selected-object={object?.id ?? ""} data-target-resolution={target?.resolution ?? "area_fallback"} data-context-status={error ? "error" : bundle ? "ready" : "loading"}>
    <header className="advanced-3d-header">
      <a className="advanced-wordmark" href={import.meta.env.BASE_URL}>CITY GAP</a>
      <div className="advanced-journey" aria-label="同じ地域を深掘り"><span>Guided</span><i aria-hidden="true">→</i><strong>詳細分析</strong></div>
      <nav aria-label="表示の切り替え"><button type="button" onClick={onGuided}>Guidedへ戻る</button><button type="button" onClick={onTools}>分析ツール</button><button type="button" onClick={onShare}>URLを共有</button></nav>
    </header>
    <main className="advanced-3d-layout">
      <section className={`advanced-3d-stage${sectionOpen ? " section-open" : ""}`} aria-label="選択地域のPLATEAU 3DとA–B断面">
        <div className="advanced-scene-heading"><h1>{area.label}</h1><p>PLATEAU 3D · 舞鶴市 {String(data.plateauMetadata?.year ?? "—")}</p></div>
        <div className="advanced-scene-controls"><button type="button" onClick={onReturnTo2D}>地図に戻る</button><button type="button" aria-pressed={sectionOpen} onClick={() => { setSectionOpen((value) => !value); setSectionFocus(null); }}>A–B断面</button></div>
        {bundle && section ? <div className="advanced-3d-viewport"><Plateau3DMap data={data} selection={object ?? selection ?? area} viewport={viewport}
          activeLayerIds={["plateau-buildings", "plateau-roads", "plateau-terrain"]} scenePreset="plateau_detail" analysisLens="none" counterfactualState="baseline"
          verifiedLocalPresentation showUrbanSection={sectionOpen} sectionData={section} sectionFocus={sectionFocus}
          onSelectionChange={(next) => onSelectionChange(next ?? area)} onReturnTo2D={onReturnTo2D} />
        </div> : <div className="advanced-scene-loading" role={error ? "alert" : "status"}><strong>{error ?? "同じ地域の3Dと断面を準備しています"}</strong>{error && <button type="button" onClick={() => setAttempt((value) => value + 1)}>再読み込み</button>}<button type="button" onClick={onReturnTo2D}>地図に戻る</button></div>}
        {sectionOpen && section && <UrbanSection open readable mode="advanced" selection={object ?? selection} counterfactualState="baseline" analysisLens="none"
          dataOverride={section} expectedPackId={context?.section.pack_id} areaLabel={area.label}
          onSelectBuilding={selectSectionBuilding} onClose={() => { setSectionOpen(false); setSectionFocus(null); }} onFocusPosition={setSectionFocus} />}
        {!sectionOpen && <div className="advanced-map-key"><span><i className="model" />公式の建物形状</span><span><i className="selected" />選んだ対象</span><small>ドラッグで視点移動 · 建物をクリックして属性を確認</small></div>}
        <p className="advanced-map-source">PLATEAU 舞鶴市 {String(data.plateauMetadata?.year ?? "—")} · LOD1 / 地理院地図・標高データ</p>
      </section>
      <aside className="advanced-reading-panel" aria-label="同じ地域と選択対象の分析">
        <section className={`advanced-target-card${target ? " exact" : ""}`} data-target-key={target?.key ?? `area:${area.id}`} data-object-id={object?.id ?? ""} data-unconfirmed={target?.checks.length ?? 0} aria-live="polite">
          {target && <span className="advanced-eyebrow">対象を特定</span>}
          <h2>{target ? object?.type === "building" ? "選択した建物" : "選択した道路面" : "建物を選ぶ"}</h2>
          {target && object ? <>
            {object.type === "building" ? <dl className="advanced-object-stats"><div><dt>用途</dt><dd>{String(properties.usage ?? properties.usage_label ?? "データなし")}</dd></div><div><dt>建物高さ</dt><dd>{advancedNumber(properties.measured_height_m, "m")}</dd></div><div><dt>地上階数</dt><dd>{advancedNumber(properties.storeys_above_ground, "階")}</dd></div><div><dt>地下階数</dt><dd>{advancedNumber(properties.storeys_below_ground, "階")}</dd></div></dl> : <p>{String(properties.road_name ?? object.label ?? "名称データなし")}</p>}
            <p className="advanced-source-note">公式PLATEAU属性 · 舞鶴市 {String(data.plateauMetadata?.year ?? "—")}{properties.lod ? ` · ${String(properties.lod)}` : ""}</p>
            <div className="advanced-field-checks"><h3>現地で確認すること <span>{target.checks.length}件・未確認</span></h3><ul>{target.checks.map(([id, title, reason]) => <li key={id} data-check-id={id} data-status="unconfirmed"><span aria-hidden="true">○</span><div><strong>{title}</strong><small>{reason}</small></div></li>)}</ul></div>
            <button type="button" className="advanced-clear-target" onClick={() => onSelectionChange(area)}>選択を解除</button>
            <details className="advanced-object-identity"><summary>対象IDと出典</summary><code>{object.id}</code><p>{context?.source.dataset} / {context?.source.version}</p></details>
          </> : <>
            <p>3Dの建物をクリックすると、用途・高さ・階数と現地確認項目を表示します。</p>
            {selectedUnmatched && context && <p className="advanced-unmatched" role="status">この地物は選択地域の対象データと一致しません。対象の特定はせず、地域単位で確認します。</p>}
            <p>A–B断面では、地図上の線に沿った地形と建物の高さを見比べられます。</p>
          </>}
        </section>
        <section className="advanced-area-context"><h2>この地域の集計</h2><p className="advanced-area-code">500mメッシュ {area.id}</p>
          <dl className="advanced-area-stats"><div><dt>65歳以上</dt><dd>{advancedNumber(areaProperties.elderly_population, "人", true)}</dd></div><div><dt>駅・バス停まで</dt><dd>{advancedNumber(areaProperties.nearest_public_transport_distance_m, "m", true)}</dd></div></dl>
          <p className="advanced-source-note">人口は国勢調査2020の地域集計で、選択した建物の居住者数ではありません。距離はメッシュ中心から収録地点への直線距離で、歩行距離ではありません。</p>
        </section>
        <p className="advanced-model-boundary">モデルが示すのは収録時点の形と属性。入口、現在の利用、歩きやすさは現地での確認が必要です。</p>
      </aside>
    </main>
  </div>;
}
