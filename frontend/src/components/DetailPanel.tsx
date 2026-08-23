import type { MeshMetrics, RobustCandidate, Summary } from "../types";
import {
  formatDistance,
  formatInteger,
  formatPercentile,
  formatRatio,
  formatScore,
  makeWhyCityGap,
  comparisonMeshScope,
  percentileValue,
  textValue
} from "../lib/format";

interface DetailPanelProps {
  mesh: MeshMetrics | null;
  comparisonMeshCount?: number;
  cityName?: string;
  audit?: Summary["audit"];
  robustness?: RobustCandidate | null;
  onEvidence?: () => void;
}

interface PercentileBarProps {
  label: string;
  value: unknown;
  tone: string;
}

function PercentileBar({ label, value, tone }: PercentileBarProps) {
  const percentile = percentileValue(value);
  return (
    <div className="percentile-row">
      <div>
        <span>{label}</span>
        <strong>{formatPercentile(value)}</strong>
      </div>
      <div
        className="percentile-track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentile === null ? undefined : Math.round(percentile * 100)}
      >
        {percentile !== null && (
          <span className={`percentile-fill ${tone}`} style={{ width: `${Math.max(2, percentile * 100)}%` }} />
        )}
      </div>
    </div>
  );
}

function NearestRow({ label, name, distance }: { label: string; name: unknown; distance: unknown }) {
  return (
    <div className="nearest-row">
      <span>{label}</span>
      <strong>{textValue(name) ?? "—"}</strong>
      <small>{formatDistance(distance)}</small>
    </div>
  );
}

function relativeDistance(value: unknown, cityName = "市内"): string {
  const percentile = percentileValue(value);
  if (percentile === null) return `${cityName}の相対位置 —`;
  return `${cityName}では遠い側 上位約${Math.max(1, Math.round((1 - percentile) * 100))}%`;
}

export function DetailPanel({ mesh, comparisonMeshCount, cityName, audit, robustness, onEvidence }: DetailPanelProps) {
  if (!mesh) {
    return (
      <div className="panel-empty" role="status">
        <span aria-hidden="true">⌖</span>
        <strong>メッシュを選択してください</strong>
        <p>地図またはランキングから地域の数値を確認できます。</p>
      </div>
    );
  }

  const rank = typeof mesh.rank === "number" ? mesh.rank : null;
  const why = makeWhyCityGap(mesh, comparisonMeshCount);
  return (
    <article className="detail-panel">
      <div className="detail-heading">
        <div>
          <p>{rank ? `CITY GAP候補 #${rank}` : "メッシュ詳細"}</p>
          <h2>{mesh.area_label ?? "名称未確認の地域"}</h2>
          <small>最寄りの実在公共交通名称を使った周辺ラベル</small>
        </div>
        {mesh.pareto_frontier && <span className="pareto-badge large">PARETO FRONTIER</span>}
      </div>

      <div className="detail-hero-metrics">
        <div className="elderly-composition">
          <small>この500mメッシュの65歳以上</small>
          <strong>{formatInteger(mesh.elderly_population)} <span>/ {formatInteger(mesh.population)}</span></strong>
          <em>{formatRatio(mesh.elderly_ratio)}</em>
        </div>
      </div>

      <div className="distance-cards">
        <div className="distance-card transport">
          <small>最寄りの収録駅・バス停</small>
          <strong>{formatDistance(mesh.nearest_public_transport_distance_m)}</strong>
          <span>{relativeDistance(mesh.transport_distance_percentile, cityName)}</span>
        </div>
        <div className="distance-card medical">
          <small>最寄りの収録医療機関</small>
          <strong>{formatDistance(mesh.nearest_medical_distance_m)}</strong>
          <span>{relativeDistance(mesh.medical_distance_percentile, cityName)}</span>
        </div>
      </div>
      {onEvidence && <button type="button" className="evidence-link" onClick={onEvidence}>根拠を見る — 距離・Scoreの計算過程</button>}

      <section className="why-section">
        <div className="section-kicker"><span>WHY</span> なぜ候補になったか</div>
        {why.length > 0 ? why.map((line) => <p key={line}>{line}</p>) : <p>説明に必要な指標がありません。</p>}
        <div className="percentiles">
          <small className="percentile-scope">比較母集団: {comparisonMeshScope(comparisonMeshCount)}</small>
          <PercentileBar label="65歳以上人口" value={mesh.elderly_population_percentile} tone="elderly" />
          <PercentileBar label="収録交通までの距離" value={mesh.transport_distance_percentile} tone="transport" />
          <PercentileBar label="収録医療までの距離" value={mesh.medical_distance_percentile} tone="medical" />
        </div>
      </section>

      {robustness && (
        <section className="robustness-section">
          <div className="section-kicker"><span>ROBUSTNESS</span> 分析条件を変えると？</div>
          <p>{robustness.scenario_count}つの分析条件のうち、Top 10に<strong>{robustness.top10_frequency}条件</strong>、Top 20に<strong>{robustness.top20_frequency}条件</strong>で残ります。</p>
          <div className="robustness-facts">
            <div><small>順位範囲</small><strong>{robustness.rank_min}–{robustness.rank_max}位</strong></div>
            <div><small>中央値</small><strong>{robustness.median_rank}位</strong></div>
            <div><small>Pareto候補</small><strong>{robustness.pareto_frequency}/{robustness.scenario_count}</strong></div>
          </div>
          <div className="robustness-matrix" aria-label="分析条件別のTop 10残存状況">
            {Object.entries(robustness.scenarios).map(([id, result]) => (
              <span key={id} className={result.top10 ? "active" : ""} title={`${id}: ${result.rank ? `${result.rank}位` : "対象外"}`}>
                <i />{id}<small>{result.rank ?? "—"}</small>
              </span>
            ))}
          </div>
          <small className="robustness-note">出現回数であり、確率や信頼度ではありません。</small>
        </section>
      )}

      <section className="nearest-section">
        <h3>最寄りの収録サービス</h3>
        <NearestRow label="駅" name={mesh.nearest_station_name} distance={mesh.nearest_station_distance_m} />
        <NearestRow label="バス停" name={mesh.nearest_bus_stop_name} distance={mesh.nearest_bus_stop_distance_m} />
        <NearestRow label="医療機関" name={mesh.nearest_medical_name} distance={mesh.nearest_medical_distance_m} />
        {mesh.nearest_medical_access_class === "uncertain_access" && (
          <p className="medical-access-warning">施設名から一般利用可否が確認できないため、現地確認が必要です。</p>
        )}
        <NearestRow label="病院" name={mesh.nearest_hospital_name} distance={mesh.nearest_hospital_distance_m} />
      </section>

      {rank === 1 && audit?.rank_one_two_km_buffer && (
        <details className="boundary-audit-note">
          <summary>市境を越える施設の感度確認</summary>
          <p>上の実測値は市内収録施設だけを検索したbaselineです。市境外2kmまで含め、利用可否が不確かな医療を除くと、収録交通まで{formatDistance(audit.rank_one_two_km_buffer.public_transport_distance_m)}、医療まで{formatDistance(audit.rank_one_two_km_buffer.medical_distance_excluding_uncertain_m)}でした。</p>
          <small>Primary Top 10との一致 {audit.buffer_top10_overlap ?? "—"}/10。行政界は住民移動の障壁ではないため、確定評価では両方を確認します。</small>
        </details>
      )}

      <details className="score-note">
        <summary>計算値とメッシュ情報</summary>
        <div><span>CITY GAP探索スコア</span><strong>{formatScore(mesh.exploratory_score_c)}</strong></div>
        <p>Mesh {mesh.mesh_code} · 高齢者数・交通距離・医療距離の市内percentileを掛け合わせた追加調査用の相対指標です。</p>
      </details>
    </article>
  );
}
