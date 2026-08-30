import { useState, type ChangeEvent, type FormEvent } from "react";
import { formatFact } from "./investigationModel";
import {
  ADOPTION_QUESTIONS,
  MUNICIPAL_REVIEW_QUESTIONS,
  PIVOT_CONDITIONS,
} from "./investigationCopy";
import {
  BASELINE_STATUS,
  HUMAN_TRIAGE_LABELS,
  MUNICIPAL_REVIEW_OUTCOME_LABELS,
  MUNICIPAL_REVIEW_STATUS,
} from "./investigationDomain";
import type {
  CheckCategory,
  EditableFieldCheck,
  FieldInvestigationSheetRecord,
  InvestigationCandidate,
  MunicipalReviewOutcome,
} from "./investigationTypes";

const CATEGORY_LABELS: Record<CheckCategory, string> = {
  transport: "交通",
  walking: "歩行環境",
  medical: "医療・介護",
  site: "候補地点",
  local: "地域事情",
};

const STATUS_LABELS = {
  unconfirmed: "未確認",
  confirmed: "確認済み",
  follow_up: "要追加調査",
  not_applicable: "該当なし",
} as const;

export function FieldChecklist({ candidate }: { candidate: InvestigationCandidate }) {
  return (
    <section className="field-checklist" aria-labelledby="checklist-title">
      <header className="journey-heading">
        <span>不足情報 → 現地確認項目</span>
        <h1 id="checklist-title">何を確認する？</h1>
        <p>
          {candidate.dataGaps.length}件の不足情報と分析上の仮定から、
          {candidate.fieldChecks.length}項目を決定論的に生成しました。
        </p>
      </header>
      <div className="check-category-list">
        {(Object.keys(CATEGORY_LABELS) as CheckCategory[]).map((category, index) => {
          const checks = candidate.fieldChecks.filter((check) => check.category === category);
          return (
            <details key={category} open={index === 0}>
              <summary><strong>{CATEGORY_LABELS[category]}</strong><span>{checks.length}項目</span></summary>
              <ol>
                {checks.map((check) => (
                  <li key={check.id}>
                    <strong>{check.label}</strong>
                    <p><span>確認する理由</span>{check.reason}</p>
                    <small>{check.origin === "data_gap" ? "不足データから生成" : check.origin === "plateau_context" ? "PLATEAU文脈から生成" : "分析上の仮定から生成"}</small>
                  </li>
                ))}
              </ol>
            </details>
          );
        })}
      </div>
      <p className="checklist-boundary">
        初期項目は自動生成ですが、確認結果は自動入力しません。現地担当者が状態・担当・期限・メモを編集します。
      </p>
    </section>
  );
}

export function FieldInvestigationSheet({
  candidate,
  sheet,
  onSheetChange,
  onCheckChange,
  onRemoveCheck,
  onAddCheck,
  onSave,
  onGps,
}: {
  candidate: InvestigationCandidate;
  sheet: FieldInvestigationSheetRecord;
  onSheetChange(patch: Partial<FieldInvestigationSheetRecord>): void;
  onCheckChange(id: string, patch: Partial<EditableFieldCheck>): void;
  onRemoveCheck(id: string): void;
  onAddCheck(label: string): void;
  onSave(): void;
  onGps(): void;
}) {
  const [newCheck, setNewCheck] = useState("");
  const submitNew = (event: FormEvent) => {
    event.preventDefault();
    onAddCheck(newCheck);
    setNewCheck("");
  };
  const updateCheck = (
    id: string,
    key: keyof EditableFieldCheck,
    event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) => onCheckChange(id, { [key]: event.target.value });

  return (
    <section className="field-investigation-sheet" aria-labelledby="sheet-title">
      <header className="journey-heading">
        <span>この端末に保存する内部調査票</span>
        <h1 id="sheet-title">現地調査票を作る</h1>
        <strong>{candidate.name}</strong>
        <p>公開用の候補情報と、端末内だけに保存する担当・メモ・GPSを分けています。</p>
      </header>
      <section className="sheet-location">
        <div>
          <span>対象位置</span>
          <strong>{candidate.latitude.toFixed(6)}, {candidate.longitude.toFixed(6)}</strong>
          <small>500mメッシュ {candidate.meshCode}</small>
        </div>
        <div>
          <span>候補理由</span>
          <p>{candidate.reason}</p>
        </div>
      </section>
      <section className="sheet-evidence" aria-labelledby="sheet-evidence-title">
        <h2 id="sheet-evidence-title">調査前に持っていく情報</h2>
        <dl className="sheet-context-facts">
          {candidate.facts.map((fact) => (
            <div key={fact.id}>
              <dt>{fact.label}</dt>
              <dd>{formatFact(fact)}</dd>
              <small>{fact.source} {fact.year}</small>
            </div>
          ))}
          <div>
            <dt>PLATEAU</dt>
            <dd>
              {candidate.plateau.status === "verified"
                ? `建物${candidate.plateau.buildings}棟・道路${candidate.plateau.roads}面・公式DEM`
                : "建物・道路詳細なし"}
            </dd>
            <small>{candidate.plateau.message}</small>
          </div>
        </dl>
        <p><strong>未確認データ：</strong>{candidate.dataGaps.map((gap) => gap.title).join("、")}</p>
        <p><strong>出典：</strong>{candidate.sources.map((source) => `${source.label} ${source.year}`).join("、")}</p>
      </section>
      <div className="sheet-meta">
        <label>
          調査日
          <input
            type="date"
            value={sheet.investigationDate}
            onChange={(event) => onSheetChange({ investigationDate: event.target.value })}
          />
        </label>
        <button type="button" onClick={onGps}>現在地を記録</button>
        <span>
          GPS: {sheet.gps.latitude === null ? "未記録" : `${sheet.gps.latitude.toFixed(6)}, ${sheet.gps.longitude?.toFixed(6)}`}
        </span>
      </div>
      <ol className="editable-checks">
        {sheet.checks.map((check) => (
          <li key={check.id} data-check-origin={check.origin}>
            <header>
              <span>{CATEGORY_LABELS[check.category]}</span>
              <strong>{check.label}</strong>
              <small>{check.origin === "human" ? "人が追加" : "初期自動生成"}</small>
            </header>
            <p>{check.reason}</p>
            <div className="check-edit-grid">
              <label>
                状態
                <select value={check.status} onChange={(event) => updateCheck(check.id, "status", event)}>
                  {(Object.entries(STATUS_LABELS) as Array<[EditableFieldCheck["status"], string]>).map(([value, label]) => (
                    <option value={value} key={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label>
                優先度
                <select value={check.priority} onChange={(event) => updateCheck(check.id, "priority", event)}>
                  <option value="high">高</option>
                  <option value="medium">中</option>
                  <option value="low">低</option>
                </select>
              </label>
              <label>
                担当
                <input value={check.assignee} onChange={(event) => updateCheck(check.id, "assignee", event)} />
              </label>
              <label>
                期限
                <input type="date" value={check.dueDate} onChange={(event) => updateCheck(check.id, "dueDate", event)} />
              </label>
            </div>
            <label className="check-note">
              メモ
              <textarea value={check.note} onChange={(event) => updateCheck(check.id, "note", event)} rows={2} />
            </label>
            <button type="button" className="remove-check" onClick={() => onRemoveCheck(check.id)}>
              この項目を削除
            </button>
          </li>
        ))}
      </ol>
      <form className="add-check" onSubmit={submitNew}>
        <label>
          地域事情に合わせて確認項目を追加
          <input value={newCheck} onChange={(event) => setNewCheck(event.target.value)} required />
        </label>
        <button type="submit">追加</button>
      </form>
      <label className="general-note">
        現地メモ
        <textarea
          rows={4}
          value={sheet.generalNote}
          onChange={(event) => onSheetChange({ generalNote: event.target.value })}
        />
      </label>
      <label className="photo-references">
        写真参照（ファイル名・庁内保管先を1行に1件）
        <textarea
          rows={2}
          value={sheet.photoReferences.join("\n")}
          onChange={(event) =>
            onSheetChange({
              photoReferences: event.target.value
                .split("\n")
                .map((item) => item.trim())
                .filter(Boolean),
            })}
        />
      </label>
      <div className="sheet-save-row">
        <button type="button" className="investigation-secondary" onClick={onSave}>この端末に保存</button>
        <span role="status">通信なし対応・内部情報として保存</span>
      </div>
    </section>
  );
}

export function MunicipalReview({
  candidate,
  sheet,
  onSheetChange,
}: {
  candidate: InvestigationCandidate;
  sheet: FieldInvestigationSheetRecord;
  onSheetChange(patch: Partial<FieldInvestigationSheetRecord>): void;
}) {
  const patchReview = (patch: Partial<FieldInvestigationSheetRecord["municipalReview"]>) =>
    onSheetChange({
      municipalReview: { ...sheet.municipalReview, ...patch },
    });
  return (
    <section className="municipal-review" aria-labelledby="review-title">
      <header className="journey-heading">
        <span>自治体レビュー</span>
        <h2 id="review-title">この候補をどう扱う？</h2>
      </header>
      <div className="review-status">
        <span>現在の状態</span>
        <strong>{HUMAN_TRIAGE_LABELS[sheet.candidateTriageStatus]}</strong>
        <code>{MUNICIPAL_REVIEW_STATUS}</code>
      </div>
      <p>
        {sheet.municipalReview.outcome === "unreviewed"
          ? "実自治体からの回答はまだありません。候補を「確認済み」や価値仮説を「SUPPORTED」にはしていません。"
          : "入力されたレビュー結果を内部記録として保持しています。価値仮説を自動で「SUPPORTED」にはしません。"}
      </p>
      <div className="municipal-review-form">
        <label>
          実回答の結果
          <select
            aria-label="自治体レビュー結果"
            value={sheet.municipalReview.outcome}
            onChange={(event) =>
              patchReview({ outcome: event.target.value as MunicipalReviewOutcome })}
          >
            {(Object.entries(MUNICIPAL_REVIEW_OUTCOME_LABELS) as Array<
              [MunicipalReviewOutcome, string]
            >).map(([value, label]) => (
              <option value={value} key={value}>{label}</option>
            ))}
          </select>
        </label>
        <label>
          確認すべき部署
          <input
            value={sheet.municipalReview.responsibleDepartment}
            onChange={(event) => patchReview({ responsibleDepartment: event.target.value })}
          />
        </label>
        <label>
          既存施策
          <textarea
            rows={2}
            value={sheet.municipalReview.existingMeasures}
            onChange={(event) => patchReview({ existingMeasures: event.target.value })}
          />
        </label>
        <label>
          不足しているデータ
          <textarea
            rows={2}
            value={sheet.municipalReview.missingData}
            onChange={(event) => patchReview({ missingData: event.target.value })}
          />
        </label>
        <label>
          協議での利用方法
          <textarea
            rows={2}
            value={sheet.municipalReview.discussionUse}
            onChange={(event) => patchReview({ discussionUse: event.target.value })}
          />
        </label>
        <label className="review-original-response">
          自治体・関係者の原文メモ
          <textarea
            rows={3}
            value={sheet.municipalReview.originalResponse}
            onChange={(event) => patchReview({ originalResponse: event.target.value })}
          />
        </label>
        <small>実回答を得た後だけ入力します。入力内容はこの端末へ自動保存されます。</small>
      </div>
      <details>
        <summary>自治体・交通担当へ確認する質問</summary>
        <ol>{MUNICIPAL_REVIEW_QUESTIONS.map((question) => <li key={question}>{question}</li>)}</ol>
      </details>
      <details>
        <summary>否定的な回答を受けた場合</summary>
        <p>都合よく読み替えず、PARTIALLY_SUPPORTEDまたはCONTRADICTEDとして元の回答を保持します。</p>
        <ul>{PIVOT_CONDITIONS.map((condition) => <li key={condition}>{condition}</li>)}</ul>
      </details>
      <small>候補: {candidate.name} · 自動分析から確認済みへは進みません。</small>
    </section>
  );
}

export function InvestigationSummary({
  candidate,
  sheet,
  onSheetChange,
}: {
  candidate: InvestigationCandidate;
  sheet: FieldInvestigationSheetRecord;
  onSheetChange(patch: Partial<FieldInvestigationSheetRecord>): void;
}) {
  const confirmed = sheet.checks.filter((check) => check.status === "confirmed").length;
  return (
    <article className="investigation-summary" aria-labelledby="summary-title">
      <header className="journey-heading">
        <span>庁内共有用調査サマリー</span>
        <h1 id="summary-title">調査前の論点を一枚にまとめる</h1>
        <strong>{candidate.name}</strong>
      </header>
      <section className="summary-block">
        <h2>候補になった理由</h2>
        <p>{candidate.reason}</p>
      </section>
      <section className="summary-block">
        <h2>PLATEAUで分かったこと</h2>
        <p>{candidate.plateau.message}</p>
      </section>
      <section className="summary-block">
        <h2>データだけでは分からないこと</h2>
        <ul>{candidate.dataGaps.map((gap) => <li key={gap.id}>{gap.title}</li>)}</ul>
      </section>
      <section className="summary-block">
        <h2>現地確認</h2>
        <p>{sheet.checks.length}項目中 {confirmed}項目を確認済み。未確認の状態を推測で埋めません。</p>
        <ul>{sheet.checks.slice(0, 8).map((check) => <li key={check.id}>{check.label} — {STATUS_LABELS[check.status]}</li>)}</ul>
      </section>
      <section className="summary-block">
        <h2>関係部署・確認先</h2>
        <p>地域公共交通担当、高齢福祉担当、都市計画担当、公共施設担当、交通事業者・施設管理者</p>
      </section>
      <section className="summary-block sources">
        <h2>出典・年次</h2>
        <ul>{candidate.sources.map((source) => <li key={source.id}><strong>{source.label}</strong> {source.year} — {source.detail}</li>)}</ul>
      </section>
      <section className="summary-block limitations">
        <h2>分析上の限界</h2>
        <p>直線距離は徒歩距離・所要時間ではありません。候補は政策推奨、危険地域、施策効果の予測ではありません。</p>
      </section>
      <MunicipalReview candidate={candidate} sheet={sheet} onSheetChange={onSheetChange} />
      <section className="adoption-questions">
        <h2>採用判断で確認すること</h2>
        <ul>{ADOPTION_QUESTIONS.map((question) => <li key={question}>{question}</li>)}</ul>
        <p>現行業務の時間・費用は未収集です。<code>{BASELINE_STATUS}</code></p>
      </section>
    </article>
  );
}
