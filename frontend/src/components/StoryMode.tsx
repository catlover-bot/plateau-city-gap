import { comparisonMeshScope } from "../lib/format";
import {
  summarizePlateauCoverage,
  top10CoverageSentence,
} from "../lib/plateau";
import type { PlateauMetadata } from "../types";

interface StoryModeProps {
  step: number | null;
  onStart: () => void;
  onStepChange: (step: number | null) => void;
  plateauMetadata: PlateauMetadata | null;
  comparisonMeshCount?: number;
  ready: boolean;
}

export function StoryMode({
  step,
  onStart,
  onStepChange,
  plateauMetadata,
  comparisonMeshCount,
  ready,
}: StoryModeProps) {
  const plateauCoverage = summarizePlateauCoverage(plateauMetadata);
  const plateauStepBody = plateauCoverage.referenceIncluded
    ? `公式PLATEAU 2025の実在建物へ移動します。${top10CoverageSentence(plateauCoverage)}整備済み市街地との違いもデータ品質として示します。`
    : `${top10CoverageSentence(plateauCoverage)}駅周辺リファレンスの収録状況もメタデータから確認できません。`;
  const steps = [
    { label: "課題を発見", title: "候補を見つける", body: "495メッシュから、ニーズとサービス到達のズレが大きい追加調査候補を確認します。" },
    { label: "なぜ？", title: "数字を分解する", body: `人口・交通・医療の実データと、${comparisonMeshScope(comparisonMeshCount)}で計算したpercentileから、Rank 1が浮かぶ理由を読み解きます。` },
    { label: "PLATEAUで現地を見る", title: "3D都市の整備範囲を見る", body: plateauStepBody },
    { label: "施策を試す", title: "Before / Afterを計算", body: `Rank 1中心に仮想交通支援拠点を置き、${comparisonMeshScope(comparisonMeshCount)}の距離と探索スコアを再計算します。` }
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
