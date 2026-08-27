import type { ReactNode } from "react";
import type { AppData } from "../../types";
import type { SpatialSelection } from "../../state/spatial/types";
import { PlateauLineage } from "./PlateauLineage";

interface Props {
  data: AppData;
  selection: SpatialSelection | null;
  primaryLayer: string;
  open: boolean;
  children: ReactNode;
  onClose(): void;
  onOpenEvidence(): void;
  onContributionSelect(layerId: string): void;
}

const number = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 });

function SelectionSummary({ selection }: { selection: SpatialSelection }) {
  const properties = selection.properties ?? {};
  if (selection.type === "building") return <>
    <p className="inspector-eyebrow">PLATEAU建物</p><h2>{selection.label ?? "選択した建物"}</h2>
    <div className="attribute-separation"><section><strong>公式PLATEAU属性</strong><dl><div><dt>用途</dt><dd>{String(properties.usage ?? "属性なし")}</dd></div><div><dt>高さ</dt><dd>{properties.measured_height_m ? `${properties.measured_height_m} m` : "属性なし"}</dd></div><div><dt>地上階</dt><dd>{String(properties.storeys_above_ground ?? "属性なし")}</dd></div><div><dt>延床</dt><dd>{properties.total_floor_area_m2 ? `${number.format(Number(properties.total_floor_area_m2))} m²` : "属性なし"}</dd></div><div><dt>LOD</dt><dd>{String(properties.lod ?? "属性なし")}</dd></div></dl></section><section className="model-estimate"><strong>モデル推計</strong><p>建物別人口は公開画面へ表示しません。公式属性とは別データです。</p></section></div>
  </>;
  if (selection.type === "validation_sample") return <><p className="inspector-eyebrow">参照networkとの差異</p><h2>{selection.label}</h2><dl className="selection-facts"><div><dt>分類</dt><dd>{String(properties.reference_agreement ?? "差異sample")}</dd></div><div><dt>原因候補</dt><dd>{String(properties.cause_candidate ?? "要確認")}</dd></div><div><dt>PLATEAU実験graph</dt><dd>{properties.primary_distance_m ? `${number.format(Number(properties.primary_distance_m))} m` : "経路なし"}</dd></div><div><dt>Reference</dt><dd>{properties.reference_distance_m ? `${number.format(Number(properties.reference_distance_m))} m` : "経路なし"}</dd></div></dl></>;
  return <><p className="inspector-eyebrow">{selection.type === "mesh" ? "500mメッシュ" : "選択地点"}</p><h2>{selection.label ?? selection.id}</h2><dl className="selection-facts"><div><dt>65歳以上人口</dt><dd>{properties.elderly_population !== undefined ? `${number.format(Number(properties.elderly_population))}人` : "集約値なし"}</dd></div><div><dt>公共交通</dt><dd>{properties.nearest_public_transport_distance_m ? `${number.format(Number(properties.nearest_public_transport_distance_m))} m` : "未確認"}</dd></div><div><dt>医療</dt><dd>{properties.nearest_medical_distance_m ? `${number.format(Number(properties.nearest_medical_distance_m))} m` : "未確認"}</dd></div></dl><p className="claim-boundary">集約したモデル値です。危険度・実人数・政策優先順位を意味しません。</p></>;
}

export function ContextInspector({ data, selection, primaryLayer, open, children, onClose, onOpenEvidence, onContributionSelect }: Props) {
  return (
    <aside className={`context-inspector ${open ? "open" : "closed"}`} aria-label="選択地点のContext Inspector" aria-live="polite">
      <div className="inspector-handle" aria-hidden="true" />
      <header className="inspector-header"><div><span>CONTEXT INSPECTOR</span><strong>{data.city.name} · {selection ? "選択中" : "都市overview"}</strong></div><button type="button" aria-label="Inspectorを閉じる" onClick={onClose}>×</button></header>
      <div className="inspector-scroll">
        {selection ? <SelectionSummary selection={selection} /> : <section className="onboarding-actions"><p className="inspector-eyebrow">最初の3アクション</p><h2>{data.city.name}の課題候補を見る</h2><ol><li><span>1</span><strong>色が濃い場所を探す</strong></li><li><span>2</span><strong>地図か候補一覧を選ぶ</strong></li><li><span>3</span><strong>PLATEAU 3Dで詳しく確認</strong></li></ol><p>濃い色は追加調査候補であり、危険度ではありません。</p></section>}
        {children}
        <PlateauLineage primaryLayer={primaryLayer} selection={selection} onSelectLayer={onContributionSelect} />
        <button type="button" className="evidence-entry" onClick={onOpenEvidence}><span>根拠を見る</span><strong>出典・計算方法・検証状態</strong><i aria-hidden="true">→</i></button>
        <details className="technical-details"><summary>Technical details</summary><dl><div><dt>selection type</dt><dd>{selection?.type ?? "none"}</dd></div><div><dt>technical ID</dt><dd><code>{selection?.id ?? "—"}</code></dd></div><div><dt>primary layer</dt><dd><code>{primaryLayer}</code></dd></div></dl></details>
      </div>
    </aside>
  );
}
