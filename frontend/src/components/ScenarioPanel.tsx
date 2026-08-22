import type { MeshMetrics } from "../types";
import type { ScenarioResult } from "../lib/scenario";
import { comparisonMeshScope, formatDistance, formatInteger, formatScore } from "../lib/format";

interface ScenarioPanelProps {
  result: ScenarioResult | null;
  selectedMesh: MeshMetrics | null;
  placementMode: boolean;
  onStartPlacement: () => void;
  onTryRankOne: () => void;
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
  onSelectMesh,
  onReset,
  comparisonMeshCount
}: ScenarioPanelProps) {
  const selected = selectedMesh
    ? result?.meshes.find((mesh) => mesh.meshCode === selectedMesh.mesh_code) ?? null
    : null;
  const comparisonScope = comparisonMeshScope(result?.comparisonMeshCount ?? comparisonMeshCount);

  return (
    <article className="scenario-panel">
      <div className="scenario-heading">
        <div>
          <p>WHAT-IF SIMULATION</p>
          <h2>仮想交通支援拠点</h2>
        </div>
        {result && <button type="button" className="text-button" onClick={onReset}>リセット</button>}
      </div>

      <p className="scenario-lead">
        地図上の1点を仮想拠点とし、メッシュ中心から最寄り交通までの直線距離と探索スコアを再計算します。
        交通距離percentileの比較母集団は{comparisonScope}です。
      </p>

      {!result && (
        <div className="scenario-empty">
          <span className="scenario-pin" aria-hidden="true">＋</span>
          <strong>{placementMode ? "地図上の設置地点をクリック" : "施策地点を1つ置いてみる"}</strong>
          <p>既存距離と仮想地点までの距離の短い方を使います。</p>
          <button type="button" className={placementMode ? "primary-button active" : "primary-button"} onClick={onStartPlacement}>
            {placementMode ? "配置地点を選択中…" : "地図で配置する"}
          </button>
          <button type="button" className="secondary-button" onClick={onTryRankOne}>Rank 1中心で試す</button>
        </div>
      )}

      {result && (
        <>
          <div className="scenario-location">
            <span>仮想地点</span>
            <code>{result.point.latitude.toFixed(5)}, {result.point.longitude.toFixed(5)}</code>
          </div>
          <div className="scenario-summary-grid">
            <div><strong>{result.improvedMeshCount}</strong><span>距離が改善するmesh</span></div>
            <div><strong>{formatInteger(result.affectedElderlyPopulation)}</strong><span>対象meshの65歳以上人口</span></div>
          </div>

          <section className="before-after">
            <h3>{selectedMesh ? `選択中 Mesh ${selectedMesh.mesh_code}` : "メッシュを選択"}</h3>
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
                <strong>Mesh {mesh.meshCode}</strong>
                <small>{formatScore(mesh.beforeScore)} → {formatScore(mesh.afterScore)}</small>
              </button>
            )) : <p>探索スコアが下がるメッシュはありません。</p>}
          </section>
        </>
      )}

      <p className="scenario-disclaimer">
        直線距離だけによる仮想シナリオです。土地利用、道路、運行可能性、需要、費用は評価していません。実際の設置判断ではありません。
      </p>
    </article>
  );
}
