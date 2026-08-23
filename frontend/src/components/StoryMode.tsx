import { comparisonMeshScope, formatDistance, formatInteger, formatRatio } from "../lib/format";
import {
  summarizePlateauCoverage,
  top10CoverageSentence,
} from "../lib/plateau";
import type { FinalDemoData, InterventionData, MeshMetrics, PlateauMetadata, RobustnessData } from "../types";

interface StoryModeProps {
  step: number | null;
  onStart: () => void;
  onStepChange: (step: number | null) => void;
  plateauMetadata: PlateauMetadata | null;
  comparisonMeshCount?: number;
  ready: boolean;
  finalDemo: FinalDemoData;
  rankOne: MeshMetrics | null;
  robustness: RobustnessData | null;
  interventions: InterventionData | null;
  onOpenValidation: () => void;
}

export function StoryMode({
  step,
  onStart,
  onStepChange,
  plateauMetadata,
  comparisonMeshCount,
  ready,
  finalDemo,
  rankOne,
  robustness,
  interventions,
  onOpenValidation,
}: StoryModeProps) {
  const plateauCoverage = summarizePlateauCoverage(plateauMetadata);
  const deepDive = finalDemo.deep_dive;
  const bestCandidate = finalDemo.placement_optimization.candidates[0];
  const robustRankOne = robustness?.top_candidates[0];
  const oneSite = interventions?.plans.overall["1"];
  const twoSite = interventions?.plans.overall["2"];
  const fairness = interventions?.plans.fairness["2"];
  const plateauStepBody = plateauCoverage.referenceIncluded
    ? `${top10CoverageSentence(plateauCoverage)}そこで全市${deepDive.overall_rank}位・${deepDive.area_label}へ移動し、公式建物${deepDive.plateau_building_count.toLocaleString("ja-JP")}棟と実属性を確認します。`
    : `${top10CoverageSentence(plateauCoverage)}3D Deep Dive subsetの収録状況もメタデータから確認できません。`;
  const steps = [
    { label: "単独データの限界", title: "1枚の地図だけでは見えない", body: "高齢者数 → 交通の遠さ → 医療の遠さを同じ500mメッシュで切り替えます。どれか1つだけでは、必要と届きにくさの重なりを見落とします。" },
    { label: "CITY GAPで発見", title: rankOne?.area_label ?? "全市 Rank 1", body: rankOne ? `人口${formatInteger(rankOne.population)}、65歳以上${formatInteger(rankOne.elderly_population)}・高齢化率${formatRatio(rankOne.elderly_ratio)}。交通まで${formatDistance(rankOne.nearest_public_transport_distance_m)}、医療まで${formatDistance(rankOne.nearest_medical_distance_m)}です。` : `実データと${comparisonMeshScope(comparisonMeshCount)}のpercentileから理由を分解します。` },
    { label: "条件を変えても残る", title: robustRankOne?.area_label ?? "頑健候補を確認", body: robustRankOne ? `${robustRankOne.scenario_count}条件すべてでTop 10に残り、順位範囲は${robustRankOne.rank_min}〜${robustRankOne.rank_max}位です。これは確率ではなく、条件別の出現回数です。` : "複数の分析条件で候補の残り方を確認します。" },
    { label: "PLATEAUで空間確認", title: `${deepDive.area_label}へ`, body: plateauStepBody },
    { label: "1地点なら", title: "PLATEAU道路面から1地点を比較", body: oneSite ? `${oneSite.impact.improved_mesh_count}メッシュで距離が短くなり、対象メッシュに記録された65歳以上人口は${oneSite.impact.affected_elderly_population.toLocaleString("ja-JP")}人。改善メッシュの平均短縮は${formatDistance(oneSite.impact.mean_improvement_among_improved_m)}です。` : bestCandidate ? `${bestCandidate.area_label}の道路面上で再計算します。` : "道路面上の候補で再計算します。" },
    { label: "2地点なら", title: "追加施策の効果を比較", body: twoSite ? `2地点では${twoSite.impact.improved_mesh_count}メッシュ、65歳以上人口${twoSite.impact.affected_elderly_population.toLocaleString("ja-JP")}人が記録された範囲を改善します。2/3地点案は決定論的greedy近似で、全組合せの最適解ではありません。` : "1地点と2地点の追加効果を比較します。" },
    { label: "全体 vs 取り残し", title: "目的を変えると配置も変わる", body: fairness ? `取り残し重視案は、交通距離が長い側10%の平均を${formatDistance(fairness.impact.worst_decile_mean_reduction_m)}短縮します。全体Scoreとのtrade-offも隠さず表示します。` : "全体改善と、アクセスが特に弱い地域の改善を比較します。" },
    { label: "藤沢でも再現", title: "同じEngineを別都市へ", body: "藤沢市263メッシュでも同じ決定論的GIS・統計ロジックを実行済みです。都市間のScore値は直接比較せず、横展開可能性を確認します。" }
  ];
  if (step === null) {
    return (
      <button type="button" className="story-start-button" onClick={onStart} disabled={!ready}>
        <span aria-hidden="true">▶</span> {ready ? "Story Mode" : "3D地図を準備中…"}
      </button>
    );
  }
  const current = steps[step];
  return (
    <section className="story-card" aria-live="polite">
      <div className="story-progress" aria-label={`ストーリー ${step + 1} / ${steps.length}`}>
        {steps.map((item, index) => <i key={item.label} className={index <= step ? "active" : ""} />)}
      </div>
      <div className="story-kicker">STEP {step + 1} / {steps.length} · {current.label}</div>
      <h2>{current.title}</h2>
      <p>{current.body}</p>
      <div className="story-actions">
        <button type="button" className="text-button" onClick={() => onStepChange(null)}>終了</button>
        {step > 0 && <button type="button" className="secondary-button" disabled={!ready} onClick={() => onStepChange(step - 1)}>戻る</button>}
        {step < steps.length - 1 ? (
          <button type="button" className="primary-button" disabled={!ready} onClick={() => onStepChange(step + 1)}>次へ</button>
        ) : (
          <button type="button" className="primary-button" onClick={onOpenValidation}>藤沢の横展開を見る</button>
        )}
      </div>
    </section>
  );
}
