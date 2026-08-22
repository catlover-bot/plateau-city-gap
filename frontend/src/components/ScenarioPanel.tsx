import type { MeshMetrics, PlacementCandidate } from "../types";
import type { ScenarioResult } from "../lib/scenario";
import { comparisonMeshScope, formatDistance, formatInteger, formatScore } from "../lib/format";

interface ScenarioPanelProps {
  result: ScenarioResult | null;
  selectedMesh: MeshMetrics | null;
  placementMode: boolean;
  onStartPlacement: () => void;
  onTryRankOne: () => void;
  candidates: PlacementCandidate[];
  onTryCandidate: (candidate: PlacementCandidate) => void;
  onSelectMesh: (meshCode: string) => void;
  onReset: () => void;
  comparisonMeshCount?: number;
}

function signedPercent(value: number): string {
  return `${value >= 0 ? "−" : "+"}${Math.abs(value * 100).toFixed(1)}%`;
}

export function ScenarioPanel({
  result,
  selectedMesh,
  placementMode,
  onStartPlacement,
  onTryRankOne,
  candidates,
  onTryCandidate,
  onSelectMesh,
  onReset,
  comparisonMeshCount
}: ScenarioPanelProps) {
  const selected = selectedMesh
    ? result?.meshes.find((mesh) => mesh.meshCode === selectedMesh.mesh_code) ?? null
    : null;
  const comparisonScope = comparisonMeshScope(result?.comparisonMeshCount ?? comparisonMeshCount);
  const activeCandidate = result ? candidates.find((candidate) =>
    Math.abs(candidate.longitude - result.point.longitude) < 1e-7 &&
    Math.abs(candidate.latitude - result.point.latitude) < 1e-7
  ) : null;

  return (
    <article className="scenario-panel">
      <div className="scenario-heading">
        <div>
          <p>WHAT-IF SIMULATION</p>
          <h2>配置候補を探す</h2>
        </div>
        {result && <button type="button" className="text-button" onClick={onReset}>リセット</button>}
      </div>

      <p className="scenario-lead">
        公式PLATEAU道路面上の候補点、または地図上の1点を仮想拠点とし、メッシュ中心から最寄り交通までの直線距離と探索スコアを再計算します。
        交通距離percentileの比較母集団は{comparisonScope}です。
      </p>

      {!result && (
        <div className="scenario-empty">
          <strong>実在する道路面から探索した Top 3</strong>
          <p>既存交通から150m超、候補間1.5km以上。Score C合計の純減少量を最大化しました。</p>
          <div className="candidate-list">
            {candidates.map((candidate) => (
              <button type="button" key={candidate.candidate_id} onClick={() => onTryCandidate(candidate)}>
                <span>候補 {candidate.candidate_rank}</span>
                <strong>{candidate.area_label}</strong>
                <small>{candidate.road_name ? `${candidate.road_name} · ` : ""}{candidate.improved_mesh_count} mesh改善見込み</small>
              </button>
            ))}
          </div>
          <button type="button" className={placementMode ? "secondary-button active" : "secondary-button"} onClick={onStartPlacement}>
            {placementMode ? "配置地点を選択中…" : "別の地点を地図で試す"}
          </button>
          <details className="diagnostic-option">
            <summary>診断用シナリオ</summary>
            <p>Rank 1中心への0m配置は計算確認用で、発表のPrimary案ではありません。</p>
            <button type="button" className="text-button" onClick={onTryRankOne}>Rank 1中心で試す</button>
          </details>
        </div>
      )}

      {result && (
        <>
          <div className="scenario-location">
            <span>{activeCandidate?.area_label ?? "自由配置した仮想地点"}</span>
            <code>{result.point.latitude.toFixed(5)}, {result.point.longitude.toFixed(5)}</code>
          </div>
          <div className="scenario-summary-grid">
            <div><strong>{result.improvedMeshCount}</strong><span>距離が改善するmesh</span></div>
            <div><strong>{formatInteger(result.affectedElderlyPopulation)}</strong><span>対象meshの65歳以上人口</span></div>
            <div><strong>{formatDistance(result.averageTransportDistanceImprovementM)}</strong><span>改善meshの平均距離短縮</span></div>
            <div><strong>{formatScore(result.totalScoreReduction)}</strong><span>Score C合計の純減少</span></div>
          </div>

          <section className="before-after">
            <h3>{selectedMesh ? (selectedMesh.area_label ?? `Mesh ${selectedMesh.mesh_code}`) : "メッシュを選択"}</h3>
            {selected ? (
              <>
                <div className="compare-row">
                  <div><small>BEFORE</small><strong>{formatDistance(selected.beforeDistanceM)}</strong><span>Score {formatScore(selected.beforeScore)}</span></div>
                  <span aria-hidden="true">→</span>
                  <div><small>AFTER</small><strong>{formatDistance(selected.afterDistanceM)}</strong><span>Score {formatScore(selected.afterScore)}</span></div>
                </div>
                <div className="improvement-chip">探索スコア {signedPercent(selected.improvementRate)}</div>
              </>
            ) : (
              <p className="scenario-unavailable">このメッシュは秘匿・合算影響のない比較対象外、または再計算に必要な値がありません。</p>
            )}
          </section>

          <section className="scenario-ranking">
            <h3>探索スコアの改善幅 Top 5</h3>
            {result.mostImproved.length > 0 ? result.mostImproved.map((mesh, index) => (
              <button type="button" key={mesh.meshCode} onClick={() => onSelectMesh(mesh.meshCode)}>
                <span>{index + 1}</span>
                <strong>{mesh.areaLabel}</strong>
                <small>{formatScore(mesh.beforeScore)} → {formatScore(mesh.afterScore)}</small>
              </button>
            )) : <p>探索スコアが下がるメッシュはありません。</p>}
          </section>
        </>
      )}

      <p className="scenario-disclaimer">
        候補生成には公式道路面を使いますが、効果計算は直線距離です。用地、道路ネットワーク、横断、運行可能性、需要、費用は未評価で、設置判断ではありません。「影響高齢者人口」は利用者予測ではありません。
      </p>
    </article>
  );
}
