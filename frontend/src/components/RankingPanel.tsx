import type { MeshMetrics } from "../types";
import { formatDistance, formatInteger, formatRatio, formatScore } from "../lib/format";

interface RankingPanelProps {
  items: MeshMetrics[];
  selectedMeshCode: string | null;
  onSelect: (mesh: MeshMetrics) => void;
}
export function RankingPanel({ items, selectedMeshCode, onSelect }: RankingPanelProps) {
  if (items.length === 0) {
    return (
      <div className="panel-empty" role="status">
        <span aria-hidden="true">◇</span>
        <strong>ランキングがありません</strong>
        <p>Primary条件を満たすTop 10データを確認してください。</p>
      </div>
    );
  }

  return (
    <div className="ranking-list" aria-label="CITY GAP Top 10">
      {items.map((mesh, index) => {
        const rank = typeof mesh.rank === "number" ? mesh.rank : index + 1;
        const selected = mesh.mesh_code === selectedMeshCode;
        return (
          <button
            type="button"
            key={mesh.mesh_code}
            className={`ranking-card ${selected ? "selected" : ""} ${rank <= 3 ? "top-three" : ""}`}
            aria-pressed={selected}
            onClick={() => onSelect(mesh)}
          >
            <span className="rank-number" aria-label={`順位 ${rank}`}>
              <small>#</small>{rank}
            </span>
            <span className="rank-content">
              <span className="rank-title-row">
                <span><strong className="rank-area">{mesh.area_label ?? "名称未確認の地域"}</strong><small className="rank-mesh">Mesh {mesh.mesh_code}</small></span>
                {mesh.pareto_frontier && <span className="pareto-badge">PARETO</span>}
              </span>
              <span className="rank-metrics">
                <span><small>65歳以上</small>{formatInteger(mesh.elderly_population)}</span>
                <span><small>交通</small>{formatDistance(mesh.nearest_public_transport_distance_m)}</span>
                <span><small>医療</small>{formatDistance(mesh.nearest_medical_distance_m)}</span>
              </span>
              <span className="rank-footer">
                <span>人口 {formatInteger(mesh.population)}</span>
                <span>高齢化率 {formatRatio(mesh.elderly_ratio)}</span>
                <span className="rank-score">探索スコア {formatScore(mesh.exploratory_score_c)}</span>
              </span>
            </span>
            <span className="rank-chevron" aria-hidden="true">›</span>
          </button>
        );
      })}
    </div>
  );
}
