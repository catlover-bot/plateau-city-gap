import type { FuturesStressMode, InterventionPlan, UrbanFuturesData } from "../../types";

type ScenarioMode = "compare" | "stress";

interface Props {
  plan: InterventionPlan | null;
  mode: ScenarioMode;
  siteCount: 1 | 2 | 3;
  futures: UrbanFuturesData | null;
  city: "maizuru" | "fujisawa";
  stress: FuturesStressMode;
  onModeChange(value: ScenarioMode): void;
  onSiteCountChange(value: 1 | 2 | 3): void;
  onStressChange(value: FuturesStressMode): void;
}

const integer = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 1 });

export function ScenarioWorkspace({ plan, mode, siteCount, futures, city, stress, onModeChange, onSiteCountChange, onStressChange }: Props) {
  const stressResult = stress === "normal" ? null : futures?.cities[city].stress_tests[stress];
  return (
    <section className="task-workspace scenario-workspace">
      <header className="workspace-intro"><p>SCENARIO / STRESS TEST</p><h3>現在と仮定を並べて試す</h3><span>予測ではなく、明示した条件の反実仮想です。</span></header>
      <div className="segmented-control" role="tablist" aria-label="試す内容">
        <button type="button" className={mode === "compare" ? "active" : ""} onClick={() => onModeChange("compare")}>施策案比較</button>
        <button type="button" className={mode === "stress" ? "active" : ""} onClick={() => onModeChange("stress")}>災害Stress Test</button>
      </div>
      {mode === "compare" ? <>
        <label className="compact-field"><span>候補地点数</span><select value={siteCount} onChange={(event) => onSiteCountChange(Number(event.target.value) as 1 | 2 | 3)}><option value="1">A · 1地点</option><option value="2">B · 2地点</option><option value="3">C · 3地点</option></select></label>
        {plan ? <div className="scenario-impact"><div><small>改善mesh</small><strong>{integer.format(plan.impact.improved_mesh_count)}</strong></div><div><small>影響65歳以上人口</small><strong>{integer.format(plan.impact.affected_elderly_population)}人</strong></div><div><small>平均距離改善</small><strong>{decimal.format(plan.impact.mean_improvement_among_improved_m)}m</strong></div></div> : <p className="workspace-hint">この都市では施策案を公開していません。</p>}
        <p className="claim-boundary">左が現況、右が施策仮定後。カメラ・選択地点は同期します。</p>
      </> : <>
        <label className="compact-field"><span>利用不可と仮定するhazard重複edge</span><select value={stress} onChange={(event) => onStressChange(event.target.value as FuturesStressMode)}><option value="normal">通常時</option><option value="flood">洪水</option><option value="landslide">土砂</option><option value="tsunami">津波</option></select></label>
        {stressResult ? <div className="scenario-impact"><div><small>閉鎖仮定edge</small><strong>{integer.format(stressResult.result.closed_edge_count)}</strong></div><div><small>連結成分増</small><strong>+{integer.format(stressResult.result.component_fragmentation_increase)}</strong></div><div><small>計算時間</small><strong>{decimal.format(stressResult.runtime_seconds)}秒</strong></div></div> : <p className="workspace-hint">hazardを選ぶと、同じ都市状態でネットワークの変化を表示します。</p>}
        <p className="claim-boundary">災害時の実通行可否や発生確率を予測するものではありません。</p>
      </>}
    </section>
  );
}
