import { useRef, useState } from "react";
import type { InvestigationCandidate, InvestigationWorkspace } from "./investigationTypes";
import { GUIDED_3D_EXAMPLE_QUERY } from "../guided-spatial/guided3d";

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
      <p className="value-eyebrow">PLATEAU FIELD VERIFICATION LOOP</p>
      <h1 id="value-heading">地図だけでは分からないことを、<br />現地で確かめる場所とタスクに変える。</h1>
      <p className="value-lead">
        舞鶴市の実データから「まだ分からないこと」を取り出し、
        PLATEAUの建物・道路と実在地点へ結び、
        3〜5件の必須確認に絞ります。
      </p>
      <p className="primary-user">
        地域公共交通計画・デマンド交通・交通空白地域等を検討する自治体職員向け
      </p>
    </div>
  );
}

export function OutputPreview({ candidate }: { candidate: InvestigationCandidate }) {
  return (
    <article className="output-preview" aria-label="舞鶴実データから作る未確認タスクのプレビュー">
      <header>
        <span>REAL MAIZURU DATA · STATUS</span>
        <strong>不明点 → PLATEAU対象 → 未確認タスク</strong>
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
        <h3>まだ分からないこと · 最大4件</h3>
        <ul>
          {candidate.dataGaps.slice(0, 4).map((gap) => <li key={gap.id}>{gap.title}</li>)}
        </ul>
      </section>
      <p className="preview-boundary">
        状態は「未確認」。写真・GPS・回答・自治体reviewのdemo値はありません。
      </p>
    </article>
  );
}

export function InvestigationLanding({
  workspace,
  onStart,
  onStartArea,
  onRestart,
}: {
  workspace: InvestigationWorkspace;
  onStart(): void;
  onStartArea?(): void;
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
              <a className="public-3d-example" href={`${import.meta.env.BASE_URL}${GUIDED_3D_EXAMPLE_QUERY}`}>PLATEAUで街を3Dで見る<small>常団地前周辺の実例</small></a>
              <button type="button" className="investigation-primary" onClick={onStart}>
                地図から確認候補を選ぶ
              </button>
              {onStartArea && <button type="button" className="investigation-secondary" onClick={onStartArea}>
                場所と範囲から調べる（検証中）
              </button>}
              <button type="button" className="investigation-secondary" onClick={openMethod}>
                仕組みを見る
              </button>
            </div>
            <ol className="three-outcomes" aria-label="不明点を現地確認タスクへ変える3段階">
              <li><span>1</span><strong>不明点を分ける</strong><small>分かっていることと判断を変える不足を分離</small></li>
              <li><span>2</span><strong>実在objectへ結ぶ</strong><small>建物・道路・地点のIDと出典を保持</small></li>
              <li><span>3</span><strong>必須確認に絞る</strong><small>3〜5件、状態は未確認のまま</small></li>
            </ol>
          </div>
          <OutputPreview candidate={workspace.candidates[0]} />
        </section>
        {methodOpen && (
          <section className="method-explanation" ref={methodRef} tabIndex={-1} aria-labelledby="method-title">
            <span>分析の限界 → Finding → PLATEAU object → 現地タスク</span>
            <h2 id="method-title">「なぜこの確認が必要か」を、対象objectまで追跡できます。</h2>
            <p>
              500m分析に残る運行・歩行・施設利用・地域サービスの不明点を、
              舞鶴市のversion付きobjectまたは正直なmesh fallbackへ結びます。現地結果はまだ作りません。
            </p>
            <button type="button" onClick={() => setMethodOpen(false)}>閉じる</button>
          </section>
        )}
      </main>
    </div>
  );
}
