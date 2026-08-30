import { formatFact } from "./investigationModel";
import { HUMAN_TRIAGE_LABELS } from "./investigationDomain";
import type {
  HumanTriageStatus,
  InvestigationCandidate,
  InvestigationWorkspace,
} from "./investigationTypes";

export function CandidateShortlist({
  workspace,
  selectedId,
  onSelect,
}: {
  workspace: InvestigationWorkspace;
  selectedId: string;
  onSelect(candidate: InvestigationCandidate): void;
}) {
  return (
    <section className="candidate-shortlist" aria-labelledby="shortlist-title">
      <header className="journey-heading">
        <span>現地調査候補 3件</span>
        <h1 id="shortlist-title">どこを確認する？</h1>
        <p>
          自動的な政策順位ではありません。異なる確認目的の3件から、人が次に調べる地域を選びます。
        </p>
      </header>
      <div className="candidate-list" role="radiogroup" aria-label="舞鶴市の現地調査候補">
        {workspace.candidates.map((candidate) => (
          <button
            type="button"
            role="radio"
            aria-checked={candidate.id === selectedId}
            className={candidate.id === selectedId ? "selected" : ""}
            key={candidate.id}
            onClick={() => onSelect(candidate)}
          >
            <span className={`candidate-type type-${candidate.type}`}>{candidate.typeLabel}</span>
            <strong>{candidate.name}</strong>
            <p>{candidate.reason}</p>
            <small>{candidate.typeExplanation}</small>
            <i>{candidate.plateau.status === "verified" ? "PLATEAU詳細あり" : "500m分析のみ"}</i>
          </button>
        ))}
      </div>
      <details className="selection-rule">
        <summary>候補の選び方</summary>
        <p>選定ルール {workspace.selectionRuleVersion}</p>
        <ul>{workspace.selectionRule.map((rule) => <li key={rule}>{rule}</li>)}</ul>
        <p>単一の点数だけでは決めていません。状態を「確認済み」へ自動変更しません。</p>
      </details>
    </section>
  );
}

export function DataGapList({ candidate }: { candidate: InvestigationCandidate }) {
  return (
    <section className="data-gap-list" aria-labelledby="data-gap-title">
      <header>
        <span>データだけでは分からないこと</span>
        <h2 id="data-gap-title">現地・事業者へ確認する不足情報</h2>
      </header>
      <dl>
        {candidate.dataGaps.map((gap) => (
          <div key={gap.id} data-gap-id={gap.id}>
            <dt>{gap.title}</dt>
            <dd><strong>分かっている：</strong>{gap.known}</dd>
            <dd><strong>分からない：</strong>{gap.unknown}</dd>
            <dd className="gap-boundary">{gap.sourceBoundary}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function CandidateBrief({
  candidate,
  triageStatus,
  onTriageChange,
}: {
  candidate: InvestigationCandidate;
  triageStatus: HumanTriageStatus;
  onTriageChange(status: HumanTriageStatus): void;
}) {
  return (
    <article className="candidate-brief" aria-labelledby="brief-title">
      <header className="journey-heading">
        <span>{candidate.typeLabel}</span>
        <h1 id="brief-title">なぜ確認する？</h1>
        <strong>{candidate.name}</strong>
        <p>{candidate.reason}</p>
      </header>
      <label className="candidate-triage">
        <span>自治体による仕分け</span>
        <select
          aria-label="候補の仕分け状態"
          value={triageStatus}
          onChange={(event) => onTriageChange(event.target.value as HumanTriageStatus)}
        >
          {(Object.entries(HUMAN_TRIAGE_LABELS) as Array<[HumanTriageStatus, string]>).map(
            ([value, label]) => <option value={value} key={value}>{label}</option>,
          )}
        </select>
        <small>初期状態は未確認です。分析だけで確認済みにはなりません。</small>
      </label>
      <dl className="brief-primary-facts" aria-label="候補理由の主要3数値">
        {candidate.facts.map((fact) => (
          <div key={fact.id}>
            <dt>{fact.label}</dt>
            <dd>{formatFact(fact)}</dd>
            <small>{fact.source} {fact.year}</small>
          </div>
        ))}
      </dl>
      {candidate.whyThisExample && <p className="example-boundary">{candidate.whyThisExample}</p>}
      <div className="brief-answer-grid">
        <section>
          <h2>分かっていること</h2>
          <ul>{candidate.knownFacts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
        </section>
        <section>
          <h2>まだ分からないこと</h2>
          <ul>{candidate.dataGaps.slice(0, 4).map((gap) => <li key={gap.id}>{gap.title}</li>)}</ul>
        </section>
      </div>
      <details className="calculation-details">
        <summary>出典と計算</summary>
        <dl>
          <div><dt>市境と交差する人口メッシュ</dt><dd>{candidate.cityIntersectingMeshCount}件</dd></div>
          <div><dt>percentile比較に使用</dt><dd>{candidate.percentileDenominator}件</dd></div>
          <div><dt>Primaryランキング対象</dt><dd>{candidate.rankingDenominator}件</dd></div>
          <div><dt>当該候補順位</dt><dd>{candidate.rankingDenominator}件中{candidate.rank}位</dd></div>
          <div><dt>500mメッシュ</dt><dd>{candidate.meshCode}</dd></div>
        </dl>
        <p>距離はメッシュ中心から収録点までの直線距離で、徒歩距離・所要時間ではありません。</p>
      </details>
    </article>
  );
}

export function PlateauFieldContext({ candidate }: { candidate: InvestigationCandidate }) {
  if (candidate.plateau.status === "unavailable") {
    return (
      <section className="plateau-field-context unavailable" aria-labelledby="plateau-title">
        <header className="journey-heading">
          <span>PLATEAU収録範囲</span>
          <h1 id="plateau-title">街のどこを見る？</h1>
        </header>
        <strong>この候補にはPLATEAU建物モデルがありません。</strong>
        <p>{candidate.plateau.message}</p>
        <p>
          候補を隠したり別の3Dを見せたりせず、この不足を現地確認項目へ変換します。
        </p>
      </section>
    );
  }
  return (
    <section className="plateau-field-context" aria-labelledby="plateau-title">
      <header className="journey-heading">
        <span>500mから現地確認対象へ</span>
        <h1 id="plateau-title">街のどこを見る？</h1>
        <p>
          500mの統計だけでは、どの建物・道路・地形が関係するか分かりません。
          PLATEAUで現地へ行く前の街の構造を具体化します。
        </p>
      </header>
      <ol className="field-resolution-lift">
        <li><span>候補</span><strong>500m</strong></li>
        <li><span>建物群</span><strong>{candidate.plateau.buildings}棟</strong></li>
        <li><span>道路</span><strong>{candidate.plateau.roads}面</strong></li>
        <li><span>地形</span><strong>公式DEM</strong></li>
        <li><span>次</span><strong>現地確認地点</strong></li>
      </ol>
      <div className="plateau-questions">
        <h2>PLATEAUで確認すること</h2>
        <ul>
          <li>住宅建物はどこに分布するか</li>
          <li>道路はどこを通り、建物とどう接するか</li>
          <li>地形と坂の可能性はどう関係するか</li>
          <li>候補地点周辺に何があるか</li>
          <li>どこを現地で確認すべきか</li>
        </ul>
      </div>
      <p className="plateau-boundary">
        建物属性は地域文脈の確認用です。個別建物に人口・危険度・優先度を付けていません。
        DEM勾配は歩行経路の測量値ではありません。
      </p>
    </section>
  );
}
