import { comparisonMeshScope, formatDistance, formatInteger, formatRatio } from "../lib/format";
import {
  summarizePlateauCoverage,
  top10CoverageSentence,
} from "../lib/plateau";
import type { FinalDemoData, MeshMetrics, PlateauMetadata } from "../types";

interface StoryModeProps {
  step: number | null;
  onStart: () => void;
  onStepChange: (step: number | null) => void;
  plateauMetadata: PlateauMetadata | null;
  comparisonMeshCount?: number;
  ready: boolean;
  finalDemo: FinalDemoData;
  rankOne: MeshMetrics | null;
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
}: StoryModeProps) {
  const plateauCoverage = summarizePlateauCoverage(plateauMetadata);
  const deepDive = finalDemo.deep_dive;
  const bestCandidate = finalDemo.placement_optimization.candidates[0];
  const plateauStepBody = plateauCoverage.referenceIncluded
    ? `${top10CoverageSentence(plateauCoverage)}そこで全市${deepDive.overall_rank}位・${deepDive.area_label}へ移動し、公式建物${deepDive.plateau_building_count.toLocaleString("ja-JP")}棟と実属性を確認します。`
    : `${top10CoverageSentence(plateauCoverage)}3D Deep Dive subsetの収録状況もメタデータから確認できません。`;
  const steps = [
    { label: "重ねて発見", title: "1枚の地図だけでは見えない", body: "高齢者数 → 交通の遠さ → 医療の遠さ → CITY GAPを同じ500mメッシュで切り替えます。必要と届きにくさの重なりが、追加調査候補をつくります。" },
    { label: "Rank 1", title: rankOne?.area_label ?? "全市 Rank 1", body: rankOne ? `人口${formatInteger(rankOne.population)}、65歳以上${formatInteger(rankOne.elderly_population)}・高齢化率${formatRatio(rankOne.elderly_ratio)}。交通まで${formatDistance(rankOne.nearest_public_transport_distance_m)}、医療まで${formatDistance(rankOne.nearest_medical_distance_m)}です。` : `実データと${comparisonMeshScope(comparisonMeshCount)}のpercentileから理由を分解します。` },
    { label: "3D Deep Dive", title: `${deepDive.area_label}へ`, body: plateauStepBody },
    { label: "配置候補を探索", title: "道路面上の候補で Before / After", body: bestCandidate ? `${bestCandidate.area_label}の公式PLATEAU道路面上に探索アンカーを置き、${bestCandidate.improved_mesh_count}メッシュ・65歳以上人口${bestCandidate.affected_elderly_population.toLocaleString("ja-JP")}人が属する範囲の距離変化を再計算します。` : "道路面上の候補で再計算します。" },
    { label: "意思決定へ", title: "これは答えではなく、調査の入口", body: "次は現地の道路・坂・横断、住民ヒアリング、交通事業者との運行条件、医療施設の現況、用地と費用を確認します。" }
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
          <button type="button" className="primary-button" onClick={() => onStepChange(null)}>自由に探索する</button>
        )}
      </div>
    </section>
  );
}
