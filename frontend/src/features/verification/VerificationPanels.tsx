import { formatFact } from "../investigation/investigationModel";
import type { PublicVerificationLoop, PublicVerificationTarget } from "./verificationTypes";

const TARGET_LABELS: Record<PublicVerificationTarget["objectType"], string> = {
  mesh: "500mメッシュ",
  building: "PLATEAU建物",
  road: "PLATEAU道路",
  facility: "実在地点",
};

export function UncertaintyPanel({ loop }: { loop: PublicVerificationLoop }) {
  return (
    <section className="verification-panel" aria-labelledby="uncertainty-title">
      <header className="journey-heading">
        <span>分析結果 → まだ分からないこと</span>
        <h1 id="uncertainty-title">この場所について、まだ分からないこと</h1>
        <p>分かっている事実と、判断を変え得る不足情報を分けて表示します。</p>
      </header>
      <dl className="verification-known-facts" aria-label="公開データで分かっている3つの事実">
        {loop.candidate.facts.map((fact) => (
          <div key={fact.id}>
            <dt>{fact.label}</dt>
            <dd>{formatFact(fact)}</dd>
            <small>{fact.source} {fact.year}</small>
          </div>
        ))}
      </dl>
      <div className="uncertainty-cards">
        {loop.tasks.map((task, index) => (
          <article key={task.id} data-uncertainty-kind={task.kind}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div>
              <h2>{task.sourceGap.title}</h2>
              <p><strong>まだ分からない：</strong>{task.sourceGap.unknown}</p>
              <p className="uncertainty-importance"><strong>なぜ重要？</strong>{task.importance}</p>
              <small>{task.sourceGap.sourceBoundary}</small>
            </div>
          </article>
        ))}
      </div>
      <p className="verification-boundary">最大4件。分析だけで確認済みにはしません。</p>
    </section>
  );
}

export function VerificationTargetsPanel({ loop }: { loop: PublicVerificationLoop }) {
  return (
    <section className="verification-panel" aria-labelledby="target-title">
      <header className="journey-heading">
        <span>まだ分からないこと → 確かめる場所</span>
        <h1 id="target-title">どこを現地で確かめる？</h1>
        <p>不明点を、version付きの実在objectまたは正直な500m fallbackへ結びます。</p>
      </header>
      <div className="verification-targets">
        {loop.tasks.map((task, index) => (
          <article key={task.id} data-verification-task-id={task.id}>
            <header>
              <span>{index + 1}</span>
              <div>
                <strong>{task.sourceGap.title}</strong>
                <small>{task.importance}</small>
              </div>
            </header>
            <div className="target-arrow" aria-hidden="true">↓</div>
            {task.targets.map((target) => (
              <section key={`${task.id}-${target.sourceObjectId}`} data-target-object-id={target.sourceObjectId}>
                <span>{TARGET_LABELS[target.objectType]} · {target.role === "primary" ? "主対象" : "文脈"}</span>
                <strong>{target.label}</strong>
                <code>{target.sourceObjectId}</code>
                <small>{target.datasetVersion}</small>
                {target.spatialPackId && <small>pack: {target.spatialPackId}</small>}
                {!target.isPlateauObject && target.objectType === "mesh" && (
                  <em>PLATEAU詳細がないため、別地域objectで補わない</em>
                )}
              </section>
            ))}
          </article>
        ))}
      </div>
      <details className="verification-provenance">
        <summary>追跡できるID</summary>
        <p>Finding: <code>{loop.findingId}</code></p>
        <p>Rule: <code>{loop.ruleVersion}</code></p>
      </details>
    </section>
  );
}

export function VerificationTasksPanel({ loop }: { loop: PublicVerificationLoop }) {
  return (
    <section className="verification-panel" aria-labelledby="task-title">
      <header className="journey-heading">
        <span>確かめる場所 → 現地確認タスク</span>
        <h1 id="task-title">現地で確かめる4つのタスク</h1>
        <p>各タスクの必須確認を3〜5件に限定し、回答はまだ入れません。</p>
      </header>
      <div className="verification-tasks">
        {loop.tasks.map((task, index) => (
          <article key={task.id} data-verification-task-id={task.id}>
            <header>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <strong>{task.sourceGap.title}</strong>
                <small>{task.targets.map((target) => target.label).join(" / ")}</small>
              </div>
              <b>{task.statusLabel}</b>
            </header>
            <p><strong>このタスクが必要な理由：</strong>{task.importance}</p>
            <ol>
              {task.requirements.map((requirement) => (
                <li key={requirement.key}>
                  <span>{requirement.label}</span>
                  {requirement.relevantWhen && <small>条件付き: {requirement.relevantWhen}</small>}
                </li>
              ))}
            </ol>
            <footer>
              <span>必須 {task.requirements.length}件</span>
              <code>{task.id}</code>
            </footer>
          </article>
        ))}
      </div>
      <div className="verification-stop">
        <strong>ここでは未確認のまま停止します。</strong>
        <p>写真・GPS・現地回答・自治体reviewのdemo値はありません。人が現地確認するまで結論は変わりません。</p>
        <span>{loop.validation.human}</span>
        <span>{loop.validation.municipal}</span>
      </div>
    </section>
  );
}
