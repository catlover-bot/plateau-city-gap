import type {
  FuturesStressMode,
  UrbanFuturesData
} from "../types";

interface UrbanFuturesWorkspaceProps {
  data: UrbanFuturesData;
  cityId: "maizuru" | "fujisawa";
  futureYear: number;
  stressMode: FuturesStressMode;
  onFutureYearChange: (year: number) => void;
  onStressModeChange: (mode: FuturesStressMode) => void;
}

const number = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 1 });
const STRESS_LABELS: Record<FuturesStressMode, string> = {
  normal: "通常時",
  flood: "洪水",
  landslide: "土砂",
  tsunami: "津波"
};

export function UrbanFuturesWorkspace({
  data,
  cityId,
  futureYear,
  stressMode,
  onFutureYearChange,
  onStressModeChange
}: UrbanFuturesWorkspaceProps) {
  const city = data.cities[cityId];
  const availableStressModes = (["normal", "flood", "landslide", "tsunami"] as const)
    .filter((mode) => mode === "normal" || city.stress_tests[mode] !== undefined);
  const stress = stressMode === "normal" ? undefined : city.stress_tests[stressMode];
  const service = stress?.result.service_metrics.medical;
  const topCritical = city.criticality.top_candidates[0];

  return (
    <div className="futures-workspace">
      <header className="futures-heading">
        <p>URBAN FUTURES &amp; RESILIENCE</p>
        <h2>時間状態とサービス継続性</h2>
        <span>公式データと明示的仮定を分離して比較</span>
      </header>

      <section className="temporal-context" aria-label="現在選択中の時間状態">
        <div><small>City</small><strong>{city.city_name}</strong></div>
        <div><small>Data year</small><strong>2025 observed</strong></div>
        <label>
          <small>Scenario year</small>
          <select value={futureYear} onChange={(event) => onFutureYearChange(Number(event.target.value))}>
            {[2030, 2035, 2040, 2045, 2050].map((year) => <option key={year}>{year}</option>)}
          </select>
        </label>
        <label>
          <small>Stress test</small>
          <select value={stressMode} onChange={(event) => onStressModeChange(event.target.value as FuturesStressMode)}>
            {availableStressModes.map((mode) => <option key={mode} value={mode}>{STRESS_LABELS[mode]}</option>)}
          </select>
        </label>
      </section>

      <section className="futures-section">
        <div className="futures-section-title"><span>01</span><h3>3 state comparison</h3></div>
        <div className="state-comparison-grid">
          <article><small>CURRENT</small><strong>2025</strong><span>PLATEAU observed</span></article>
          <article><small>FUTURE</small><strong>{futureYear}</strong><span>公式人口・施設固定</span></article>
          <article className={stress ? "alert" : ""}><small>STRESS</small><strong>{STRESS_LABELS[stressMode]}</strong><span>{stress ? "明示的な道路利用不可仮定" : "通常ネットワーク"}</span></article>
        </div>
        <p className="futures-boundary">将来人口は公式人口シナリオを空間配分したものです。建物居住者や将来を予測していません。</p>
      </section>

      <section className="futures-section">
        <div className="futures-section-title"><span>02</span><h3>Service continuity</h3></div>
        {stress && service ? <>
          <div className="resilience-metrics">
            <div><small>仮定上の利用不可edge</small><strong>{number.format(stress.result.closed_edge_count)}</strong></div>
            <div><small>医療へ新規到達不能</small><strong>{number.format(service.newly_unreachable_buildings)}</strong><em>building</em></div>
            <div><small>影響推定65歳以上人口</small><strong>{number.format(service.estimated_elderly_population_disconnected)}</strong><em>推定</em></div>
            <div><small>連結成分の増加</small><strong>+{number.format(stress.result.component_fragmentation_increase)}</strong></div>
            <div><small>平均距離増</small><strong>+{decimal.format(service.mean_network_distance_increase_m)}m</strong></div>
            <div><small>最大距離増</small><strong>+{decimal.format(service.maximum_network_distance_increase_m)}m</strong></div>
          </div>
          <p className="stress-contract">仮定: hazard重複edgeを利用不可 · {stress.assumption.explicitly_confirmed ? "明示確認済み" : "未確認"}<br />これは災害時の実通行可否を予測したものではありません。</p>
        </> : <div className="normal-state-card"><strong>通常ネットワーク</strong><span>ストレス仮定を選ぶと、同じ都市状態で到達性変化を比較します。</span></div>}
      </section>

      <section className="futures-section">
        <div className="futures-section-title"><span>03</span><h3>Network criticality</h3></div>
        <div className="criticality-card">
          <small>network criticality candidate · 全{number.format(city.criticality.candidate_count)}件</small>
          {topCritical ? <>
            <code>{topCritical.edge_id}</code>
            <div><span>影響建物</span><strong>{number.format(topCritical.affected_buildings)}</strong></div>
            <div><span>影響推定65歳以上人口</span><strong>{decimal.format(topCritical.affected_estimated_elderly_population)}</strong></div>
          </> : <p>公開候補なし</p>}
        </div>
        <p className="futures-boundary">「危険道路」の判定ではありません。道路面隣接モデル上の自治体レビュー候補です。</p>
      </section>

      <section className="futures-section offline-field-section">
        <div className="futures-section-title"><span>04</span><h3>Field &amp; re-evaluate</h3></div>
        <ol>
          <li><strong>選択地点のみ保存</strong><span>地図文脈・PLATEAU属性・checklist・根拠要約</span></li>
          <li><strong>offline queue</strong><span>notes・確認状態・GPS確認を端末へ保持</span></li>
          <li><strong>explicit conflict</strong><span>版が違う場合は自動上書きせず自治体が解決</span></li>
        </ol>
        <span className="pilot-api-note">認証済みPilot API接続時に有効 · 公開Demoは閲覧のみ</span>
      </section>

      <footer className="futures-footer">
        <span>{city.network.nodes.toLocaleString()} nodes · {city.network.edges.toLocaleString()} edges</span>
        <strong>集約済み実データ</strong>
      </footer>
    </div>
  );
}
