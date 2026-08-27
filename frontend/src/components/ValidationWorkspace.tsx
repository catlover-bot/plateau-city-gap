import { useEffect, useMemo, useState } from "react";
import type {
  GeoJsonFeature,
  ValidationWorkspaceData
} from "../types";

interface Props {
  data: ValidationWorkspaceData;
  cityId: "maizuru" | "fujisawa";
  baseUrl?: string;
}

type ValidationSection = "comparison" | "sensitivity" | "temporal" | "evidence" | "disagreements";

const integer = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 1 });
const SECTION_LABELS: Record<ValidationSection, string> = {
  comparison: "モデル比較",
  sensitivity: "仮定感度",
  temporal: "年次差分",
  evidence: "Evidence強度",
  disagreements: "差異レビュー"
};
const CLAIMS = [
  ["建物人口配分", "validated_against_reference", "統計整合・配分保存則"],
  ["道路ネットワーク", "cross_validated", "同一ODでOSM参照網と比較"],
  ["施設到達性", "cross_validated", "経路・到達先・snap差異"],
  ["災害重複", "sensitivity_tested", "S1–S5仮定行列"],
  ["network criticality", "sensitivity_tested", "5モデルの順位範囲"],
  ["将来人口配分", "sensitivity_tested", "配分方式の比較"],
  ["施策効果", "internal_validation_only", "counterfactual内部整合"],
  ["年次差分", "cross_validated", "国立市2023/2025実データ"],
  ["現地妥当性", "awaiting_field_validation", "自治体・現地確認待ち"]
] as const;

function geometryLines(feature: GeoJsonFeature): number[][][] {
  if (!feature.geometry || !Array.isArray(feature.geometry.coordinates)) return [];
  const raw = feature.geometry.type === "LineString"
    ? [feature.geometry.coordinates]
    : feature.geometry.type === "MultiLineString" ? feature.geometry.coordinates : [];
  return raw.map((line) => Array.isArray(line) ? line.filter((point): point is number[] =>
    Array.isArray(point) && typeof point[0] === "number" && typeof point[1] === "number"
  ) : []).filter((line) => line.length > 1);
}

function RouteEvidenceMap({ features, selectedId, onSelect }: {
  features: GeoJsonFeature[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const lines = features.flatMap((feature) => geometryLines(feature).map((points, part) => ({ feature, points, part })));
  const points = lines.flatMap((line) => line.points);
  if (!points.length) return <div className="validation-map-unavailable" role="status">経路形状は NOT_AVAILABLE です。距離指標のみ表示します。</div>;
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const minX = Math.min(...xs); const maxX = Math.max(...xs);
  const minY = Math.min(...ys); const maxY = Math.max(...ys);
  const x = (value: number) => 24 + ((value - minX) / Math.max(maxX - minX, 0.000001)) * 752;
  const y = (value: number) => 316 - ((value - minY) / Math.max(maxY - minY, 0.000001)) * 292;
  return (
    <div className="validation-route-map">
      <svg viewBox="0 0 800 340" role="img" aria-label="実在する差異サンプル経路の地図。線を選択して確認できます">
        <rect x="0" y="0" width="800" height="340" className="validation-map-ground" />
        <path d="M 0 85 H 800 M 0 170 H 800 M 0 255 H 800 M 200 0 V 340 M 400 0 V 340 M 600 0 V 340" className="validation-map-grid" />
        {lines.map(({ feature, points: route, part }, index) => {
          const id = String(feature.properties?.sample_id ?? index);
          const active = id === selectedId;
          const d = route.map((point, pointIndex) => `${pointIndex ? "L" : "M"} ${x(point[0]).toFixed(1)} ${y(point[1]).toFixed(1)}`).join(" ");
          const model = String(feature.properties?.route_model ?? "reference_model");
          return <path key={`${id}-${model}-${part}-${index}`} d={d} className={`validation-route ${model} ${active ? "active" : ""}`} onClick={() => onSelect(id)} />;
        })}
      </svg>
      <span className="validation-north" aria-hidden="true">N ↑</span>
      <small>実座標を表示領域へ正規化 · 背景図なし · 道路線は参照/実験網の差異経路</small>
    </div>
  );
}

export function ValidationWorkspace({ data, cityId, baseUrl = import.meta.env.BASE_URL }: Props) {
  const [section, setSection] = useState<ValidationSection>("comparison");
  const [hazard, setHazard] = useState("flood");
  const [assumption, setAssumption] = useState("S1_all_overlap_edges");
  const [selectedRoute, setSelectedRoute] = useState<string | null>(null);
  const [demoStep, setDemoStep] = useState<number | null>(null);
  const city = data.network.cities.find((item) => item.city_id === cityId) ?? data.network.cities[0];
  const sensitivity = data.sensitivity.cities[cityId];
  const routes = useMemo(() => data.disagreementRoutes.features.filter((feature) => feature.properties?.city_id === cityId), [cityId, data]);
  const routeCases = useMemo(() => routes.filter((feature, index) =>
    routes.findIndex((candidate) => candidate.properties?.sample_id === feature.properties?.sample_id) === index
  ), [routes]);
  const selected = routes.find((feature) => feature.properties?.sample_id === selectedRoute) ?? routes[0];
  const assumptions = sensitivity?.hazard_assumption_matrix ?? [];
  const assumptionRow = assumptions.find((row) => row.hazard_type === hazard && row.assumption === assumption)
    ?? assumptions.find((row) => row.hazard_type === hazard) ?? assumptions[0];

  useEffect(() => {
    setSelectedRoute(String(routes[0]?.properties?.sample_id ?? ""));
  }, [routes]);
  useEffect(() => {
    if (demoStep === null) return;
    const timer = window.setTimeout(() => setDemoStep((step) => step === null || step >= 5 ? null : step + 1), 5_000);
    return () => window.clearTimeout(timer);
  }, [demoStep]);
  useEffect(() => {
    if (demoStep === null) return;
    setSection((["comparison", "disagreements", "sensitivity", "temporal", "evidence", "disagreements"] as ValidationSection[])[demoStep]);
  }, [demoStep]);

  const evidenceBase = `${baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`}data/validation/`;
  return (
    <main className="validation-workspace" aria-label="CITY GAP Validation Workspace">
      <header className="validation-heading">
        <div><p>VALIDATION &amp; MUNICIPAL EVIDENCE</p><h1>計算結果を、検証可能な判断材料へ。</h1></div>
        <div className="validation-heading-actions">
          <span className={`validation-status ${city.validation_status}`}>{city.validation_status}</span>
          <button type="button" onClick={() => setDemoStep(0)}>30秒で検証を見る</button>
        </div>
      </header>
      {demoStep !== null && <div className="validation-demo-progress" role="status" aria-live="polite"><span style={{ width: `${((demoStep + 1) / 6) * 100}%` }} />STEP {demoStep + 1}/6 · 5秒後に次の検証へ</div>}
      <nav className="validation-tabs" aria-label="検証セクション">
        {(Object.keys(SECTION_LABELS) as ValidationSection[]).map((key) => <button key={key} type="button" className={section === key ? "active" : ""} aria-current={section === key ? "page" : undefined} onClick={() => { setDemoStep(null); setSection(key); }}>{SECTION_LABELS[key]}</button>)}
      </nav>

      <div className="validation-layout">
        <section className="validation-map-column" aria-label="検証地図">
          <div className="validation-map-context"><strong>{city.city_name}</strong><span>同一OD・決定的sampling</span><span>n={city.metrics.sample_count}</span></div>
          <RouteEvidenceMap features={routes} selectedId={String(selected?.properties?.sample_id ?? "")} onSelect={setSelectedRoute} />
          <div className="validation-route-legend"><span><i className="route-primary" />PLATEAU実験graph</span><span><i className="route-reference" />OSM reference</span><span><i className="route-selected" />選択経路</span><small>利用不能な経路は詳細でNOT_AVAILABLE表示。差異を隠さず保持します。</small></div>
          <div className="validation-route-list" role="list" aria-label="差異経路サンプル">
            {routeCases.slice(0, 8).map((feature) => {
              const id = String(feature.properties?.sample_id ?? "");
              return <button role="listitem" key={id} type="button" className={id === selected?.properties?.sample_id ? "active" : ""} onClick={() => setSelectedRoute(id)}><code>{id.slice(-8)}</code><span>{String(feature.properties?.cause_candidate ?? "未分類")}</span></button>;
            })}
          </div>
        </section>

        <aside className="validation-panel" aria-live="polite">
          {section === "comparison" && <section>
            <h2>モデル比較</h2><p className="validation-boundary">PLATEAU由来の実験道路網とOSM参照網を同じ起終点で比較。参照網は正解データではありません。</p>
            <div className="validation-kpis">
              <div><small>到達可否一致</small><strong>{decimal.format(city.metrics.connectivity_agreement_fraction * 100)}%</strong></div>
              <div><small>距離中央値差</small><strong>{decimal.format(city.metrics.median_absolute_difference_m)}m</strong></div>
              <div><small>順位相関</small><strong>{city.metrics.spearman_rank_correlation.toFixed(3)}</strong></div>
              <div><small>経路重複中央値</small><strong>{decimal.format(city.metrics.median_route_overlap_fraction * 100)}%</strong></div>
            </div>
            <dl className="validation-details"><div><dt>実験網snap中央値</dt><dd>{decimal.format(city.metrics.median_primary_snap_m)}m</dd></div><div><dt>参照網snap中央値</dt><dd>{decimal.format(city.metrics.median_reference_snap_m)}m</dd></div><div><dt>到達先一致</dt><dd>{decimal.format(city.metrics.destination_agreement_fraction * 100)}%</dd></div><div><dt>未一致</dt><dd>{city.metrics.connectivity_disagreement_count} sample</dd></div></dl>
          </section>}
          {section === "sensitivity" && <section>
            <h2>Assumption Explorer</h2><p className="validation-boundary">確率・被災予測ではなく、道路利用不可の置き方を変えた境界付き感度分析です。</p>
            <div className="validation-selects"><label>災害種<select value={hazard} onChange={(event) => setHazard(event.target.value)}>{[...new Set(assumptions.map((row) => row.hazard_type))].map((value) => <option key={value}>{value}</option>)}</select></label><label>仮定<select value={assumption} onChange={(event) => setAssumption(event.target.value)}>{assumptions.filter((row) => row.hazard_type === hazard).map((row) => <option key={row.assumption}>{row.assumption}</option>)}</select></label></div>
            {assumptionRow && <><div className="validation-kpis"><div><small>対象edge</small><strong>{integer.format(assumptionRow.affected_edges)}</strong></div><div><small>到達不能建物</small><strong>{integer.format(assumptionRow.disconnected_buildings)}</strong></div><div><small>fragment増</small><strong>{integer.format(assumptionRow.component_fragmentation)}</strong></div><div><small>確率表示</small><strong>なし</strong></div></div><p className="validation-rule">{assumptionRow.rule}</p></>}
            <h3>Criticality robustness</h3><div className="validation-models">{Object.entries(sensitivity?.criticality_sensitivity.models ?? {}).map(([name, model]) => <div key={name}><code>{name.replace(/_/g, " ")}</code><strong>{integer.format(model.candidate_count)}</strong><span>candidate</span></div>)}</div>
          </section>}
          {section === "temporal" && <section>
            <h2>実データ年次差分</h2><p className="validation-boundary">{data.temporal.city.city_name} PLATEAU 2023→2025。製品都市への推論ではなく、差分エンジンの実データ検証です。</p>
            <div className="validation-temporal-table" role="table" aria-label="テーマ別差分"><div role="row"><strong>Theme</strong><span>追加</span><span>削除</span><span>形状</span><span>属性</span></div>{data.temporal.themes.map((theme) => <div role="row" key={theme.theme_label}><strong>{theme.theme_label}</strong><span>{integer.format(theme.diff_counts.added)}</span><span>{integer.format(theme.diff_counts.removed)}</span><span>{integer.format(theme.diff_counts.geometry_changed)}</span><span>{integer.format(theme.diff_counts.attribute_changed)}</span></div>)}</div>
            <p className="validation-rule">incremental/full rebuild: {data.temporal.themes.every((theme) => theme.incremental_vs_full.hash_agreement) ? "全テーマで件数・state hash一致" : "要レビュー"}</p>
          </section>}
          {section === "evidence" && <section>
            <h2>Evidence strength</h2><p className="validation-boundary">ステータスは現地確認を自動昇格させません。百分率の「信頼度」も表示しません。</p>
            <div className="validation-claims">{CLAIMS.map(([claim, status, evidence]) => <article key={claim}><strong>{claim}</strong><span className={`validation-status ${status}`}>{status}</span><small>{evidence}</small></article>)}</div>
            <div className="validation-evidence-actions"><a href={`${evidenceBase}validation_evidence.json`} download>Evidence JSON</a><a href={`${evidenceBase}validation_evidence.csv`} download>Evidence CSV</a><button type="button" onClick={() => window.print()}>印刷 / PDF</button></div>
          </section>}
          {section === "disagreements" && <section>
            <h2>差異レビュー</h2><p className="validation-boundary">未一致を失敗として削除せず、自治体レビューの優先対象にします。</p>
            {selected ? <dl className="validation-details"><div><dt>sample</dt><dd><code>{String(selected.properties?.sample_id)}</code></dd></div><div><dt>分類</dt><dd>{String(selected.properties?.reference_agreement)}</dd></div><div><dt>原因候補</dt><dd>{String(selected.properties?.cause_candidate)}</dd></div><div><dt>実験網</dt><dd>{selected.properties?.primary_reachable ? `${decimal.format(Number(selected.properties?.primary_distance_m))}m` : "経路 NOT_AVAILABLE"}</dd></div><div><dt>参照網</dt><dd>{selected.properties?.reference_reachable ? `${decimal.format(Number(selected.properties?.reference_distance_m))}m` : "経路 NOT_AVAILABLE"}</dd></div><div><dt>レビュー</dt><dd>{String(selected.properties?.review_status)}</dd></div></dl> : <p>差異サンプルなし</p>}
            <p className="validation-rule">優先順: 到達可否不一致 → 距離差 → snap差 → 経路重複。これは政策優先順位ではありません。</p>
          </section>}
        </aside>
      </div>
      <footer className="validation-footer"><span>Field validation: {city.field_validation}</span><span>Municipal review: {city.municipal_review}</span><strong>GROUND TRUTH CLAIMED: NO</strong></footer>
    </main>
  );
}
