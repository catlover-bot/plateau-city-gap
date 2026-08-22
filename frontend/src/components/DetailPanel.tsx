import type { MeshMetrics } from "../types";
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

export function DetailPanel({ mesh, comparisonMeshCount }: DetailPanelProps) {
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
          <p>{rank ? `CITY GAP #${rank}` : "メッシュ詳細"}</p>
          <h2>Mesh {mesh.mesh_code}</h2>
        </div>
        {mesh.pareto_frontier && <span className="pareto-badge large">PARETO FRONTIER</span>}
      </div>

      <div className="detail-hero-metrics">
        <div><small>人口</small><strong>{formatInteger(mesh.population)}</strong></div>
        <div><small>65歳以上</small><strong>{formatInteger(mesh.elderly_population)}</strong></div>
        <div><small>高齢化率</small><strong>{formatRatio(mesh.elderly_ratio)}</strong></div>
      </div>

      <div className="distance-cards">
        <div className="distance-card transport">
          <span className="distance-icon" aria-hidden="true">↔</span>
          <small>公共交通まで</small>
          <strong>{formatDistance(mesh.nearest_public_transport_distance_m)}</strong>
          <span>メッシュ中心からの直線距離</span>
        </div>
        <div className="distance-card medical">
          <span className="distance-icon" aria-hidden="true">＋</span>
          <small>医療機関まで</small>
          <strong>{formatDistance(mesh.nearest_medical_distance_m)}</strong>
          <span>メッシュ中心からの直線距離</span>
        </div>
      </div>

      <section className="why-section">
        <div className="section-kicker"><span>WHY</span> なぜCITY GAP候補？</div>
        {why.length > 0 ? why.map((line) => <p key={line}>{line}</p>) : <p>説明に必要な指標がありません。</p>}
        <div className="percentiles">
          <small className="percentile-scope">比較母集団: {comparisonMeshScope(comparisonMeshCount)}</small>
          <PercentileBar label="65歳以上人口" value={mesh.elderly_population_percentile} tone="elderly" />
          <PercentileBar label="交通アクセス不足" value={mesh.transport_distance_percentile} tone="transport" />
          <PercentileBar label="医療アクセス不足" value={mesh.medical_distance_percentile} tone="medical" />
        </div>
      </section>

      <section className="nearest-section">
        <h3>最寄りのサービス</h3>
        <NearestRow label="駅" name={mesh.nearest_station_name} distance={mesh.nearest_station_distance_m} />
        <NearestRow label="バス停" name={mesh.nearest_bus_stop_name} distance={mesh.nearest_bus_stop_distance_m} />
        <NearestRow label="医療機関" name={mesh.nearest_medical_name} distance={mesh.nearest_medical_distance_m} />
        <NearestRow label="病院" name={mesh.nearest_hospital_name} distance={mesh.nearest_hospital_distance_m} />
      </section>

      <section className="score-note">
        <div><span>CITY GAP探索スコア</span><strong>{formatScore(mesh.exploratory_score_c)}</strong></div>
        <p>高齢者数・交通距離・医療距離の各percentileを掛け合わせた、追加調査候補を比較するための指標です。</p>
      </section>
    </article>
  );
}
