import type { ValidationWorkspaceData } from "../../types";

export type ValidationView = "reference" | "sensitivity" | "temporal";

interface Props {
  data: ValidationWorkspaceData | null;
  city: "maizuru" | "fujisawa";
  view: ValidationView;
  onViewChange(value: ValidationView): void;
}

const integer = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 2 });

export function ValidationInspector({ data, city, view, onViewChange }: Props) {
  const network = data?.network.cities.find((item) => item.city_id === city);
  const temporal = data?.temporal;
  return (
    <section className="task-workspace validation-workspace-v2">
      <header className="workspace-intro"><p>VALIDATION</p><h3>どこまで確かめたかを見る</h3><span>モデル間の一致・仮定感度・実データ年次差分を分離します。</span></header>
      <div className="segmented-control" role="tablist" aria-label="検証方法">
        <button type="button" className={view === "reference" ? "active" : ""} onClick={() => onViewChange("reference")}>参照比較</button>
        <button type="button" className={view === "sensitivity" ? "active" : ""} onClick={() => onViewChange("sensitivity")}>仮定感度</button>
        <button type="button" className={view === "temporal" ? "active" : ""} onClick={() => onViewChange("temporal")}>年次差分</button>
      </div>
      {!data ? <div className="panel-loading" role="status">検証データを読み込み中…</div> : view === "reference" && network ? <>
        <div className="validation-summary"><div><small>同一OD sample</small><strong>{integer.format(network.metrics.sample_count)}</strong></div><div><small>接続性一致</small><strong>{decimal.format(network.metrics.connectivity_agreement_fraction * 100)}%</strong></div><div><small>距離MAE</small><strong>{integer.format(network.metrics.distance_mae_m)}m</strong></div></div>
        <p className="status-human"><i />参照データと比較済み</p><p className="claim-boundary">OSMは独立した完全な正解ではなく、参照ネットワークです。</p>
      </> : view === "sensitivity" ? <><p className="status-human"><i />S1–S5の仮定行列を検証</p><p className="workspace-hint">hazard重複edgeの除外規則とcriticalityモデルを変え、順位と連結性の変化を確認しています。</p></> : <><p className="status-human"><i />{temporal?.city.city_name} 2023→2025実データ</p><div className="temporal-key"><span className="added">＋ 追加</span><span className="removed">− 削除</span><span className="changed">△ 変更</span></div><p className="claim-boundary">舞鶴・藤沢の変化を示すものではなく、年次差分パイプラインの実データ検証です。</p></>}
    </section>
  );
}
