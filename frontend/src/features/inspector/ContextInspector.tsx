import type { ReactNode } from "react";
import type { AppData, WorkspaceMapData, WorkspacePhase } from "../../types";
import type { SpatialSelection } from "../../state/spatial/types";
import { buildUrbanObjectGraph, type UrbanObjectNode } from "../../map/core/urbanObjectGraph";
import { ObjectLens } from "./ObjectLens";

interface Props {
  data: AppData;
  selection: SpatialSelection | null;
  primaryLayer: string;
  workspaceMap?: WorkspaceMapData | null;
  workspacePhase?: WorkspacePhase;
  open: boolean;
  children: ReactNode;
  onClose(): void;
  onOpenEvidence(): void;
  onObjectSelect(node: UrbanObjectNode): void;
}

const number = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 });

function SelectionSummary({ selection }: { selection: SpatialSelection }) {
  const properties = selection.properties ?? {};
  if (selection.type === "building") return <>
    <p className="inspector-eyebrow">PLATEAU建物</p><h2>{selection.label ?? "選択した建物"}</h2>
    <div className="attribute-separation"><section><strong>公式PLATEAU属性</strong><dl><div><dt>gml:id</dt><dd><code>{selection.id}</code></dd></div><div><dt>用途</dt><dd>{String(properties.usage ?? "属性なし")}</dd></div><div><dt>高さ</dt><dd>{properties.measured_height_m ? `${properties.measured_height_m} m` : "属性なし"}</dd></div><div><dt>地上階</dt><dd>{String(properties.storeys_above_ground ?? "属性なし")}</dd></div><div><dt>建築面積</dt><dd>{properties.footprint_area_m2 ? `${number.format(Number(properties.footprint_area_m2))} m²` : "属性なし"}</dd></div><div><dt>LOD / source</dt><dd>{String(properties.lod ?? "属性なし")} · {String(properties.source_version ?? "年不明")}</dd></div></dl></section><section className="model-estimate"><strong>モデル推計配分（実居住者数ではない）</strong><p>公開画面では抑制・秘匿対象メッシュから建物別人口を配分・表示しません。公式属性とは別データです。</p></section></div>
  </>;
  if (selection.type === "road") return <>
    <p className="inspector-eyebrow">PLATEAU道路面</p><h2>{selection.label ?? "選択した道路"}</h2>
    <dl className="selection-facts"><div><dt>gml:id</dt><dd><code>{selection.id}</code></dd></div><div><dt>路線名</dt><dd>{String(properties.road_name ?? "属性なし")}</dd></div><div><dt>道路区分</dt><dd>{String(properties.road_class ?? properties.road_function ?? "属性なし")}</dd></div><div><dt>source</dt><dd>{String(properties.source ?? "PLATEAU LOD1 road surface")} · {String(properties.source_version ?? "年不明")}</dd></div></dl>
    <p className="claim-boundary">experimental PLATEAU LOD1 road-surface adjacency。歩行者network・歩行距離・歩行時間ではありません。</p>
  </>;
  if (selection.type === "terrain") return <>
    <p className="inspector-eyebrow">PLATEAU地形</p><h2>{selection.label ?? "選択した地形"}</h2>
    <dl className="selection-facts"><div><dt>source</dt><dd>{String(properties.source ?? "PLATEAU DEM")}</dd></div><div><dt>用途</dt><dd>建物分布・道路形状・標高関係の確認</dd></div><div><dt>鉛直誇張</dt><dd>1.0（なし）</dd></div></dl>
    <p className="claim-boundary">地形から歩行負荷・危険度・斜度を推定しません。X-Ray分析面とは別の実DEMです。</p>
  </>;
  if (selection.type === "planning" || selection.type === "hazard") return <>
    <p className="inspector-eyebrow">{selection.type === "planning" ? "都市計画context" : "災害context"}</p><h2>{selection.label ?? selection.id}</h2>
    <dl className="selection-facts"><div><dt>object id</dt><dd><code>{selection.id}</code></dd></div><div><dt>source</dt><dd>{String(properties.source ?? "PLATEAU")}</dd></div><div><dt>関連</dt><dd>{String(properties.relation ?? "選択objectとの位置関係")}</dd></div></dl>
    <p className="claim-boundary">重なりを調査文脈として表示します。法的判断・災害予測・自動的な政策優先順位ではありません。</p>
  </>;
  if (selection.type === "temporal_change") return <>
    <p className="inspector-eyebrow">PLATEAU年度差分sample</p><h2>{selection.label ?? selection.id}</h2>
    <dl className="selection-facts"><div><dt>変化種別</dt><dd>{String(properties.change_type ?? "要確認")}</dd></div><div><dt>照合状態</dt><dd>{String(properties.review_status ?? "not reviewed")}</dd></div><div><dt>geometry</dt><dd>公開済み代表点</dd></div></dl>
    <p className="claim-boundary">公式の新旧建物polygonが揃わないため、Ghostは実sample pointのみです。形状を補完しません。</p>
  </>;
  if (selection.type === "validation_sample") return <><p className="inspector-eyebrow">参照networkとの差異</p><h2>{selection.label}</h2><dl className="selection-facts"><div><dt>分類</dt><dd>{String(properties.reference_agreement ?? "差異sample")}</dd></div><div><dt>原因候補</dt><dd>{String(properties.cause_candidate ?? "要確認")}</dd></div><div><dt>PLATEAU実験graph</dt><dd>{properties.primary_distance_m ? `${number.format(Number(properties.primary_distance_m))} m` : "経路なし"}</dd></div><div><dt>Reference</dt><dd>{properties.reference_distance_m ? `${number.format(Number(properties.reference_distance_m))} m` : "経路なし"}</dd></div></dl></>;
  return <><p className="inspector-eyebrow">{selection.type === "mesh" ? "500mメッシュ" : "選択地点"}</p><h2>{selection.label ?? selection.id}</h2><dl className="selection-facts"><div><dt>65歳以上人口</dt><dd>{properties.elderly_population !== undefined ? `${number.format(Number(properties.elderly_population))}人` : "集約値なし"}</dd></div><div><dt>公共交通</dt><dd>{properties.nearest_public_transport_distance_m ? `${number.format(Number(properties.nearest_public_transport_distance_m))} m` : "未確認"}</dd></div><div><dt>医療</dt><dd>{properties.nearest_medical_distance_m ? `${number.format(Number(properties.nearest_medical_distance_m))} m` : "未確認"}</dd></div></dl><p className="claim-boundary">集約したモデル値です。危険度・実人数・政策優先順位を意味しません。</p></>;
}

export function ContextInspector({ data, selection, primaryLayer, workspaceMap = null, workspacePhase = "baseline", open, children, onClose, onOpenEvidence, onObjectSelect }: Props) {
  const objectGraph = buildUrbanObjectGraph({ data, selection, primaryLayer, workspace: workspaceMap, workspacePhase });
  return (
    <aside className={`context-inspector ${open ? "open" : "closed"}`} aria-label="選択地点のContext Inspector" aria-live="polite">
      <div className="inspector-handle" aria-hidden="true" />
      <header className="inspector-header"><div><span>CONTEXT INSPECTOR</span><strong>{data.city.name} · {selection ? "選択中" : "都市overview"}</strong></div><button type="button" aria-label="Inspectorを閉じる" onClick={onClose}>×</button></header>
      <div className="inspector-scroll">
        {selection ? <SelectionSummary selection={selection} /> : <section className="onboarding-actions"><p className="inspector-eyebrow">最初の3アクション</p><h2>{data.city.name}の課題候補を見る</h2><ol><li><span>1</span><strong>色が濃い場所を探す</strong></li><li><span>2</span><strong>地図か候補一覧を選ぶ</strong></li><li><span>3</span><strong>PLATEAU 3Dで詳しく確認</strong></li></ol><p>濃い色は追加調査候補であり、危険度ではありません。</p></section>}
        {children}
        <ObjectLens graph={objectGraph} onSelectObject={onObjectSelect} />
        <button type="button" className="evidence-entry" onClick={onOpenEvidence}><span>根拠を見る</span><strong>出典・計算方法・検証状態</strong><i aria-hidden="true">→</i></button>
        <details className="technical-details"><summary>Technical details</summary><dl><div><dt>selection type</dt><dd>{selection?.type ?? "none"}</dd></div><div><dt>technical ID</dt><dd><code>{selection?.id ?? "—"}</code></dd></div><div><dt>primary layer</dt><dd><code>{primaryLayer}</code></dd></div></dl></details>
      </div>
    </aside>
  );
}
