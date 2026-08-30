import { useRef, useState } from "react";
import type { InvestigationCandidate, InvestigationWorkspace } from "./investigationTypes";

export function InvestigationHeader({ onRestart }: { onRestart(): void }) {
  return (
    <header className="investigation-header">
      <button
        type="button"
        className="investigation-brand"
        onClick={onRestart}
        aria-label="CITY GAPを最初から見る"
      >
        CITY GAP
      </button>
      <span>地域交通・医療</span>
      <strong>舞鶴市</strong>
    </header>
  );
}

export function ValueStatement() {
  return (
    <div className="value-statement">
      <p className="value-eyebrow">地域公共交通・医療アクセスの現地調査準備</p>
      <h1 id="value-heading">どこから現地確認するかを、<br />データから絞る。</h1>
      <p className="value-lead">
        人口・交通・医療から候補地域を見つけ、PLATEAUの建物・道路・地形まで確認して、
        現地調査票にまとめます。
      </p>
      <p className="primary-user">
        地域公共交通計画・デマンド交通・交通空白地域等を検討する自治体職員向け
      </p>
    </div>
  );
}

export function OutputPreview({ candidate }: { candidate: InvestigationCandidate }) {
  return (
    <article className="output-preview" aria-label="実データから作る現地調査票のプレビュー">
      <header>
        <span>実データから作る最終成果物</span>
        <strong>現地調査候補 + 現地調査票</strong>
      </header>
      <div className="preview-location">
        <span>{candidate.typeLabel}</span>
        <h2>{candidate.name}</h2>
        <small>500mメッシュ {candidate.meshCode}</small>
      </div>
      <p>{candidate.reason}</p>
      <dl>
        <div><dt>PLATEAU建物</dt><dd>{candidate.plateau.buildings}棟</dd></div>
        <div><dt>道路面</dt><dd>{candidate.plateau.roads}面</dd></div>
        <div><dt>地形</dt><dd>実DEM</dd></div>
      </dl>
      <section>
        <h3>現地で確認</h3>
        <ul>
          {candidate.fieldChecks.slice(0, 5).map((check) => <li key={check.id}>{check.label}</li>)}
        </ul>
      </section>
      <p className="preview-boundary">
        実データと不足情報から生成。政策推奨・危険判定・実施効果予測ではありません。
      </p>
    </article>
  );
}

export function InvestigationLanding({
  workspace,
  onStart,
  onRestart,
}: {
  workspace: InvestigationWorkspace;
  onStart(): void;
  onRestart(): void;
}) {
  const [methodOpen, setMethodOpen] = useState(false);
  const methodRef = useRef<HTMLElement>(null);
  const openMethod = () => {
    setMethodOpen(true);
    window.requestAnimationFrame(() => methodRef.current?.focus());
  };
  return (
    <div className="product-app investigation-landing" data-experience="landing">
      <InvestigationHeader onRestart={onRestart} />
      <main>
        <section className="value-hero" aria-labelledby="value-heading">
          <div>
            <ValueStatement />
            <div className="value-actions">
              <button type="button" className="investigation-primary" onClick={onStart}>
                舞鶴の現地調査候補を見る
              </button>
              <button type="button" className="investigation-secondary" onClick={openMethod}>
                仕組みを見る
              </button>
            </div>
            <ol className="three-outcomes" aria-label="CITY GAPで得られる3つの成果">
              <li><span>1</span><strong>候補を絞る</strong><small>3〜5地域から現地確認先を考える</small></li>
              <li><span>2</span><strong>街の構造を確認する</strong><small>PLATEAUで建物・道路・地形へ具体化</small></li>
              <li><span>3</span><strong>現地調査票を作る</strong><small>不足情報を確認項目へ変換</small></li>
            </ol>
          </div>
          <OutputPreview candidate={workspace.candidates[0]} />
        </section>
        {methodOpen && (
          <section className="method-explanation" ref={methodRef} tabIndex={-1} aria-labelledby="method-title">
            <span>500m → PLATEAU → 現地調査票</span>
            <h2 id="method-title">指標を見るだけで終わらせず、次に調べることまで整理します。</h2>
            <p>
              500mの統計だけでは、どの建物・道路・地形が関係するか分かりません。
              PLATEAUを使って街の構造を具体化し、公開データにない運行頻度・歩行可否・施設利用条件を現地確認項目へ変えます。
            </p>
            <button type="button" onClick={() => setMethodOpen(false)}>閉じる</button>
          </section>
        )}
      </main>
    </div>
  );
}
