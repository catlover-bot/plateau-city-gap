import type { AppData, MeshMetrics } from "../../types";
import type { SpatialSelection } from "../../state/spatial/types";

interface Props {
  data: AppData;
  selection: SpatialSelection | null;
  onSelect(mesh: MeshMetrics): void;
}

const integer = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 });

export function DiscoveryWorkspace({ data, selection, onSelect }: Props) {
  return (
    <section className="task-workspace discovery-workspace" aria-label="追加調査候補">
      <header className="workspace-intro">
        <p>SCREENING · 2020–2025</p>
        <h3>追加調査する場所を絞る</h3>
        <span>高齢人口・交通・医療の相対値を500m単位で重ねています。</span>
      </header>
      <div className="screening-contract"><strong>読み方</strong><span>濃い色ほど追加調査候補。危険度や政策優先順位ではありません。</span></div>
      <ol className="candidate-list" aria-label="上位候補一覧">
        {data.top10.slice(0, 6).map((mesh, index) => (
          <li key={mesh.mesh_code}>
            <button type="button" className={selection?.type === "mesh" && selection.id === mesh.mesh_code ? "active" : ""} onClick={() => onSelect(mesh)}>
              <span className="candidate-rank">{String(index + 1).padStart(2, "0")}</span>
              <span><strong>{mesh.area_label || `500mメッシュ ${mesh.mesh_code}`}</strong><small>Mesh {mesh.mesh_code}</small></span>
              <span className="candidate-distance"><b>{integer.format(Number(mesh.nearest_public_transport_distance_m ?? 0))}m</b><small>公共交通</small></span>
              <i aria-hidden="true">→</i>
            </button>
          </li>
        ))}
      </ol>
      <p className="candidate-list-note">上位6件を表示 · 同順位を含む全候補は地図で確認</p>
    </section>
  );
}
