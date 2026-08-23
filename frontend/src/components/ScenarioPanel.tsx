import type {
  DecisionMapPhase,
  DecisionMode,
  InterventionData,
  InterventionPlan,
  MeshMetrics,
} from "../types";
import type { ScenarioResult } from "../lib/scenario";
import { formatDistance, formatInteger, formatScore } from "../lib/format";

interface ScenarioPanelProps {
  interventions: InterventionData;
  plan: InterventionPlan;
  mode: DecisionMode;
  siteCount: 1 | 2 | 3;
  mapPhase: DecisionMapPhase;
  selectedMesh: MeshMetrics | null;
  freeResult: ScenarioResult | null;
  placementMode: boolean;
  onModeChange: (mode: DecisionMode) => void;
  onSiteCountChange: (count: 1 | 2 | 3) => void;
  onMapPhaseChange: (phase: DecisionMapPhase) => void;
  onSelectMesh: (meshCode: string) => void;
  onStartPlacement: () => void;
  onResetFree: () => void;
  onEvidence: () => void;
}

const MODE_LABELS: Record<DecisionMode, { label: string; description: string }> = {
  overall: { label: "全体改善", description: "市全体のScore C合計純減少を重視" },
  fairness: { label: "取り残し重視", description: "交通距離が長い側10%の平均短縮を重視" },
  robust: { label: "頑健候補", description: "分析条件を変えても残るTop 20の到達を重視" },
};

function ImpactValue({ value, label }: { value: string; label: string }) {
  return <div><strong>{value}</strong><span>{label}</span></div>;
}

export function ScenarioPanel({
  interventions,
  plan,
  mode,
  siteCount,
  mapPhase,
  selectedMesh,
  freeResult,
  placementMode,
  onModeChange,
  onSiteCountChange,
  onMapPhaseChange,
  onSelectMesh,
  onStartPlacement,
  onResetFree,
  onEvidence,
}: ScenarioPanelProps) {
  const selected = selectedMesh ? plan.mesh_results[selectedMesh.mesh_code] : null;
  const maximumReduction = Math.max(
    ...interventions.diminishing_returns.map((row) => row.total_score_c_reduction ?? 0),
    0.001,
  );
  return (
    <article className="scenario-panel decision-studio">
      <div className="scenario-heading">
        <div><p>DECISION STUDIO</p><h2>施策配置を比較</h2></div>
        <button type="button" className="evidence-link compact" onClick={onEvidence}>根拠を見る</button>
      </div>
      <p className="scenario-lead">複数の目的と1〜3地点を比較します。配置候補であり、政策の正解や設置判断ではありません。</p>

      <section className="decision-controls" aria-label="施策配置条件">
        <div><span>目的</span><div className="decision-segments three">
          {(Object.keys(MODE_LABELS) as DecisionMode[]).map((value) => (
            <button type="button" key={value} className={mode === value ? "active" : ""} aria-pressed={mode === value} onClick={() => onModeChange(value)}>{MODE_LABELS[value].label}</button>
          ))}
        </div></div>
        <small>{MODE_LABELS[mode].description}</small>
        <div><span>配置数</span><div className="decision-segments">
          {([1, 2, 3] as const).map((count) => (
            <button type="button" key={count} className={siteCount === count ? "active" : ""} aria-pressed={siteCount === count} onClick={() => onSiteCountChange(count)}>{count}地点</button>
          ))}
        </div></div>
      </section>

      <section className="decision-plan">
        <div className="decision-plan-title"><span>比較案 · {MODE_LABELS[mode].label}</span><strong>{siteCount}地点</strong></div>
        <div className="decision-sites">
          {plan.sites.map((site) => (
            <div key={site.candidate_id}>
              <span>{site.site_order}</span>
              <p><strong>{site.road_name ? `${site.road_name}付近` : `${site.nearest_existing_transport_name}周辺`}</strong><small>PLATEAU道路面代表点 · 既存交通まで{formatDistance(site.existing_transport_distance_m)}</small></p>
            </div>
          ))}
        </div>
        <div className="scenario-summary-grid">
          <ImpactValue value={`${plan.impact.improved_mesh_count}`} label="距離が短くなるmesh" />
          <ImpactValue value={formatInteger(plan.impact.affected_elderly_population)} label="対象meshに記録された65歳以上" />
          <ImpactValue value={formatDistance(plan.impact.mean_improvement_among_improved_m)} label="改善meshの平均短縮" />
          <ImpactValue value={formatScore(plan.impact.total_score_c_reduction)} label="Score C合計の純減少" />
        </div>
        {mode === "fairness" && plan.impact.total_score_c_reduction < 0 && (
          <p className="decision-tradeoff">距離が長い側を優先するため、相対順位を再計算したScore C合計は減っていません。目的間のtrade-offとして表示しています。</p>
        )}
      </section>

      {siteCount === 1 && (
        <details className="one-site-objectives">
          <summary>1地点を4つの目的で比較</summary>
          <div>
            <span>A</span><p><strong>Score C合計</strong><small>{interventions.plans.overall["1"].sites[0].road_name ?? "道路名なし"} · 純減少 {formatScore(interventions.plans.overall["1"].impact.total_score_c_reduction)}</small></p>
          </div>
          <div>
            <span>B</span><p><strong>65歳以上記録人口</strong><small>{interventions.one_site_objective_comparison.affected_elderly.sites[0].road_name ?? "道路名なし"} · {formatInteger(interventions.one_site_objective_comparison.affected_elderly.impact.affected_elderly_population)}</small></p>
          </div>
          <div>
            <span>C</span><p><strong>改善mesh平均短縮</strong><small>{interventions.one_site_objective_comparison.mean_distance.sites[0].road_name ?? "道路名なし"} · {formatDistance(interventions.one_site_objective_comparison.mean_distance.impact.mean_improvement_among_improved_m)}</small></p>
          </div>
          <div>
            <span>D</span><p><strong>距離が長い側10%</strong><small>{interventions.plans.fairness["1"].sites[0].road_name ?? "道路名なし"} · 平均{formatDistance(interventions.plans.fairness["1"].impact.worst_decile_mean_reduction_m)}</small></p>
          </div>
          <p>目的ごとに候補とtrade-offが変わります。おすすめ順ではありません。</p>
        </details>
      )}

      <section className="map-comparison-control">
        <div><h3>施策前 / 施策後</h3><small>地図色を同じ尺度で切り替え</small></div>
        <div className="decision-segments">
          <button type="button" className={mapPhase === "before" ? "active" : ""} aria-pressed={mapPhase === "before"} onClick={() => onMapPhaseChange("before")}>施策前</button>
          <button type="button" className={mapPhase === "after" ? "active" : ""} aria-pressed={mapPhase === "after"} onClick={() => onMapPhaseChange("after")}>施策後</button>
        </div>
      </section>

      {selected && selectedMesh && (
        <section className="before-after">
          <h3>{selectedMesh.area_label ?? `Mesh ${selectedMesh.mesh_code}`}</h3>
          <div className="compare-row">
            <div><small>BEFORE</small><strong>{formatDistance(selected.before_distance_m)}</strong><span>Score {formatScore(selected.before_score_c)}</span></div>
            <span aria-hidden="true">→</span>
            <div><small>AFTER</small><strong>{formatDistance(selected.after_distance_m)}</strong><span>Score {formatScore(selected.after_score_c)}</span></div>
          </div>
          <div className="improvement-chip">直線距離 −{formatDistance(selected.distance_reduction_m)}</div>
        </section>
      )}

      <section className="diminishing-returns">
        <h3>追加施策の効果</h3>
        <p>全体改善案の0→1→2→3地点を同じ指標で比較します。費用便益やROIではありません。</p>
        {interventions.diminishing_returns.map((row) => (
          <div key={row.site_count}>
            <span>{row.site_count}地点</span>
            <i><b style={{ width: `${((row.total_score_c_reduction ?? 0) / maximumReduction) * 100}%` }} /></i>
            <strong>{(row.total_score_c_reduction ?? 0).toFixed(3)}</strong>
            <small>{row.improved_mesh_count ?? 0} mesh</small>
          </div>
        ))}
      </section>

      <section className="scenario-ranking">
        <h3>変化を確認するmesh</h3>
        {plan.top_improvements.slice(0, 5).map((mesh, index) => (
          <button type="button" key={mesh.mesh_code} onClick={() => onSelectMesh(mesh.mesh_code)}>
            <span>{index + 1}</span><strong>{mesh.area_label}</strong><small>{formatDistance(mesh.before_distance_m)} → {formatDistance(mesh.after_distance_m)}</small>
          </button>
        ))}
      </section>

      <details className="candidate-method">
        <summary>探索方法と近似性</summary>
        <p>{interventions.metadata.algorithm}</p>
        <p>{interventions.metadata.exactness}。候補{interventions.metadata.candidate_count.toLocaleString("ja-JP")}点、実行{interventions.metadata.runtime_seconds.toFixed(1)}秒。</p>
      </details>

      <details className="free-placement-option">
        <summary>任意の1地点を地図で試す</summary>
        <p>既存の自由配置What-ifも維持しています。こちらは事前計算した複数案とは別の診断です。</p>
        <button type="button" className="secondary-button" onClick={onStartPlacement}>{placementMode ? "配置地点を選択中…" : "地図から1地点を選ぶ"}</button>
        {freeResult && <div className="free-result"><span>{freeResult.improvedMeshCount} mesh</span><span>{formatInteger(freeResult.affectedElderlyPopulation)}</span><button type="button" className="text-button" onClick={onResetFree}>クリア</button></div>}
      </details>

      <p className="scenario-disclaimer">仮想交通支援拠点以外は公式データです。道路面は用地確認ではなく、効果は直線距離です。表示人口は対象メッシュの2020年記録値で、利用者・需要・受益者予測ではありません。</p>
    </article>
  );
}
