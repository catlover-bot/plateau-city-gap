import { useMemo, useRef, useState } from "react";
import type { AppData, GeoJsonFeature } from "../../types";
import type {
  SpatialSelection,
  SpatialState,
  SpatialViewport,
} from "../../state/spatial/types";
import { AnalyticalMap } from "../../map/2d/AnalyticalMap";
import { InvestigationHeader } from "../investigation/ValueLanding";
import {
  AREA_MAX_RADIUS_M,
  AREA_MIN_RADIUS_M,
  resolveAreaSummary,
  type PublicAreaOrigin,
} from "./areaModel";
import type {
  AreaMetric,
  InvestigationAreaFixture,
  InvestigationAreaSummary,
} from "./areaTypes";
import "./areaInvestigation.css";

type AreaStep = 1 | 2 | 3 | 4;

const COPY = {
  A: ["調べたい場所を選ぶ。", "分かっていることと、まだ確かめるべきことが分かる。"],
  B: ["地域の感覚を、データで確かめる。", "データだけでは分からないことも見つける。"],
  C: ["感じていたまちの姿を、PLATEAUとデータで確かめる。", "その先の「まだ分からない」まで見つける。"],
} as const;

function copyVariant(): keyof typeof COPY {
  const value = new URLSearchParams(window.location.search).get("copy");
  return value === "B" || value === "C" ? value : "A";
}

function coordinates(feature: GeoJsonFeature): [number, number] | null {
  if (feature.geometry?.type !== "Point" || !Array.isArray(feature.geometry.coordinates)) return null;
  const [longitude, latitude] = feature.geometry.coordinates;
  return typeof longitude === "number" && typeof latitude === "number"
    ? [longitude, latitude]
    : null;
}

function displayMetric(metric: AreaMetric) {
  if (metric.status === "unavailable") return <strong>この範囲では未取得</strong>;
  if (typeof metric.value === "number") {
    return <strong>{metric.value.toLocaleString("ja-JP")} <small>{metric.unit}</small></strong>;
  }
  if (metric.key === "age_distribution" && metric.value && typeof metric.value === "object") {
    const value = metric.value as { age_65_plus?: number; total?: number };
    const ratio = value.total ? Math.round((value.age_65_plus ?? 0) / value.total * 100) : null;
    return <strong>65歳以上 {value.age_65_plus?.toLocaleString("ja-JP")}人{ratio !== null ? `（${ratio}%）` : ""}</strong>;
  }
  if (metric.key === "building_use" && Array.isArray(metric.value)) {
    return <strong>{metric.value.slice(0, 3).map((item) => {
      const entry = item as { label?: string; count?: number };
      return `${entry.label ?? "用途不明"} ${entry.count ?? 0}棟`;
    }).join(" / ")}</strong>;
  }
  if (metric.key === "establishments" && metric.value && typeof metric.value === "object") {
    const value = metric.value as { establishments?: number; employees?: number };
    return <strong>事業所 {value.establishments?.toLocaleString("ja-JP")}件 · 従業者 {value.employees?.toLocaleString("ja-JP")}人</strong>;
  }
  if (metric.key === "urban_planning" && Array.isArray(metric.value)) {
    const labels = [...new Set(metric.value.map((item) => String((item as { label?: string }).label ?? "")))].filter(Boolean);
    return <strong>{labels.slice(0, 3).join(" / ") || "公式objectなし"}</strong>;
  }
  if (metric.key === "transport" && metric.value && typeof metric.value === "object") {
    const value = metric.value as { stations?: number; bus_stops?: number };
    return <strong>駅 {value.stations ?? 0} · バス停 {value.bus_stops ?? 0}</strong>;
  }
  return <strong>確認済み</strong>;
}

function MetricCard({ metric }: { metric: AreaMetric }) {
  return (
    <article className={`area-metric status-${metric.status}`}>
      <header>
        <h3>{metric.label}</h3>
        <span>{metric.status === "known" ? "確認できた" : metric.status === "partial" ? "一部確認" : "未取得"}</span>
      </header>
      {displayMetric(metric)}
      <details>
        <summary>出典と限界</summary>
        <p>{metric.source.dataset} · {metric.source.source_date}</p>
        <p>{metric.limitation}</p>
        {metric.coverage_ratio !== null && <p>coverage {(metric.coverage_ratio * 100).toFixed(1)}%</p>}
      </details>
    </article>
  );
}

const PRIMARY_METRIC_GROUPS = [
  { id: "population-age", label: "人口・年齢", groups: ["population", "age_distribution"] },
  { id: "building-use", label: "建物の使われ方", groups: ["building_use"] },
  { id: "establishments", label: "事業所", groups: ["establishments"] },
  { id: "urban-planning", label: "都市計画", groups: ["urban_planning"] },
  { id: "transport", label: "交通", groups: ["transport"] },
] as const;

export function AreaSummaryPanel({ summary, publicMode = false }: { summary: InvestigationAreaSummary; publicMode?: boolean }) {
  const secondaryMetrics = summary.metrics.filter((metric) => metric.group === "secondary");
  return (
    <div className="area-summary-flow">
      <section aria-labelledby="area-known-title">
        {!publicMode && <p className="area-kicker">QUANTIFIED EVIDENCE</p>}
        <h2 id="area-known-title">この範囲で、データから確認できたこと</h2>
        <div className="area-metric-groups">
          {PRIMARY_METRIC_GROUPS.map((group) => (
            <section className="area-metric-group" key={group.id}>
              <h3>{group.label}</h3>
              <div className="area-metric-grid">
                {summary.metrics.filter((metric) => group.groups.some((name) => name === metric.group)).map((metric) => <MetricCard key={metric.key} metric={metric} />)}
              </div>
            </section>
          ))}
        </div>
        {secondaryMetrics.length > 0 && (
          <details className="area-secondary-metrics">
            <summary>医療・介護・公共施設などの詳細データ</summary>
            <div className="area-metric-grid">
              {secondaryMetrics.map((metric) => <MetricCard key={metric.key} metric={metric} />)}
            </div>
          </details>
        )}
      </section>
      <section className="area-unknown-section" aria-labelledby="area-unknown-title">
        {!publicMode && <p className="area-kicker">KNOWN / UNKNOWN</p>}
        <h2 id="area-unknown-title">ただし、まだデータだけでは分からないことがあります</h2>
        <div className="area-unknown-list">
          {summary.unknowns.slice(0, publicMode ? 3 : 4).map((unknown) => (
            <article key={unknown.id}>
              <span>未確認</span>
              <h3>{unknown.title}</h3>
              <p>{unknown.importance}</p>
              <small>{unknown.source_boundary}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export function TargetTasks({ summary, publicMode = false }: { summary: InvestigationAreaSummary; publicMode?: boolean }) {
  return (
    <div className="area-task-flow">
      <header>
        {!publicMode && <p className="area-kicker">PLATEAU TARGET → VERIFICATION</p>}
        <h2>{summary.label}の{publicMode ? "確認場所" : "未確認タスク"}</h2>
        <p>{publicMode ? "データの限界から、現地で確かめる場所と3〜5件の確認項目を示します。" : "「なぜ必要か」と実在object IDを保ったまま、3〜5件の確認へ絞ります。"}</p>
      </header>
      <div className="area-task-list">
        {summary.unknowns.map((unknown) => (
          <article key={unknown.id}>
            <div className="area-task-target">
              <span>{unknown.target.scope === "mesh" ? "範囲単位の確認" : "確認場所"}</span>
              <strong>{unknown.target.label}</strong>
              {publicMode ? (
                <details className="area-target-source">
                  <summary>対象データの出典</summary>
                  <code>{unknown.target.source_object_id}</code>
                  <small>{unknown.target.dataset}</small>
                </details>
              ) : (
                <>
                  <code>{unknown.target.source_object_id}</code>
                  <small>{unknown.target.dataset}</small>
                </>
              )}
            </div>
            <div>
              <span className="area-unverified">未確認</span>
              <h3>{unknown.title}</h3>
              <ol>
                {unknown.checks.map((check) => <li key={check}>{check}</li>)}
              </ol>
            </div>
          </article>
        ))}
      </div>
      <p className="area-privacy-boundary">
        写真・GPS・回答・担当者・自治体の確認結果は作成も表示もしていません。
      </p>
    </div>
  );
}

interface Props {
  data: AppData;
  fixture: InvestigationAreaFixture;
  state: SpatialState;
  onClose(): void;
  onOpenExistingM3(): void;
  onOpenAdvanced(): void;
  onSelectionChange(selection: SpatialSelection | null): void;
  onViewportChange(viewport: SpatialViewport): void;
}

export function AreaInvestigationJourney({
  data,
  fixture,
  state,
  onClose,
  onOpenExistingM3,
  onOpenAdvanced,
  onSelectionChange,
  onViewportChange,
}: Props) {
  const [step, setStep] = useState<AreaStep>(1);
  const [origin, setOrigin] = useState<PublicAreaOrigin | null>(null);
  const [radius, setRadius] = useState(800);
  const [customRadius, setCustomRadius] = useState("650");
  const [error, setError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const variant = copyVariant();
  const summary = useMemo(
    () => origin ? resolveAreaSummary(fixture, data, origin, radius) : null,
    [data, fixture, origin, radius],
  );
  const stations = useMemo(() => {
    const features = data.stations?.features ?? [];
    return [...features].sort((left, right) => {
      const leftName = String(left.properties?.name ?? "");
      const rightName = String(right.properties?.name ?? "");
      if (leftName === "西舞鶴駅") return -1;
      if (rightName === "西舞鶴駅") return 1;
      return leftName.localeCompare(rightName, "ja");
    });
  }, [data.stations]);

  const chooseOrigin = (next: PublicAreaOrigin) => {
    setOrigin(next);
    setError(null);
    onViewportChange({
      longitude: next.coordinates[0],
      latitude: next.coordinates[1],
      zoom: 13.4,
      bearing: 0,
      pitch: 0,
    });
    setStep(2);
  };
  const chooseRadius = (value: number) => {
    setRadius(value);
    setError(null);
    setStep(3);
    window.requestAnimationFrame(() => headingRef.current?.focus());
  };
  const submitCustom = () => {
    const value = Number(customRadius);
    if (!Number.isInteger(value) || value < AREA_MIN_RADIUS_M || value > AREA_MAX_RADIUS_M) {
      setError("その他の半径は100〜3000mの整数で入力してください。");
      return;
    }
    chooseRadius(value);
  };
  const back = () => {
    if (step === 1) onClose();
    else setStep((step - 1) as AreaStep);
  };

  return (
    <div
      className="product-app area-investigation"
      data-experience="area-investigation"
      data-area-step={step}
      data-copy-variant={variant}
    >
      <InvestigationHeader onRestart={onClose} />
      <main className="area-body">
        <section className="area-map-stage" aria-label="舞鶴市の調査範囲を選ぶ地図">
          <AnalyticalMap
            data={data}
            validation={null}
            preset="discovery"
            primaryLayer="analysis-city-gap"
            activeLayerIdsOverride={["reference-gsi-pale", "infra-stations", "infra-medical"]}
            selection={state.selection}
            viewport={state.viewport}
            interactive
            ariaLabel="舞鶴市の地図。移動した地図の中心を任意の起点にできます"
            onSelectionChange={onSelectionChange}
            onViewportChange={onViewportChange}
          />
          <div className="area-map-caption">
            <span>INVESTIGATION AREA · VERSION 1 PREVIEW</span>
            <strong>{origin?.label ?? "起点を選択してください"}</strong>
            <small>{origin ? `単純な半径 ${radius}m · 実歩行時間圏ではありません` : "駅 または 地図中心の任意地点"}</small>
          </div>
        </section>

        <article className="area-sheet">
          <div className="area-progress">
            <span>{step} / 4</span>
            <ol aria-label="調査範囲から未確認タスクまでの進み具合">
              {["場所", "範囲", "Known / Unknown", "確認タスク"].map((label, index) => (
                <li key={label} aria-current={step === index + 1 ? "step" : undefined}>
                  <span>{index + 1}</span><small>{label}</small>
                </li>
              ))}
            </ol>
          </div>

          <div className="area-content">
            {step === 1 && (
              <section>
                <p className="area-kicker">LOCAL INTUITION → QUANTIFIED EVIDENCE</p>
                <h1 ref={headingRef} tabIndex={-1}>{COPY[variant][0]}<br />{COPY[variant][1]}</h1>
                <p>職員の地域感覚を置き換えるのではなく、公開データで確かめ、データの限界も続けて示します。</p>
                <div className="area-origin-choices">
                  <div>
                    <h2>駅を選ぶ</h2>
                    <div className="area-station-list">
                      {stations.map((station) => {
                        const point = coordinates(station);
                        if (!point) return null;
                        return (
                          <button
                            key={String(station.properties?.id ?? station.properties?.name)}
                            type="button"
                            onClick={() => chooseOrigin({
                              kind: "station",
                              label: String(station.properties?.name ?? "駅"),
                              coordinates: point,
                              sourceFeatureId: String(station.properties?.id ?? ""),
                            })}
                          >
                            {String(station.properties?.name ?? "駅")}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div>
                    <h2>地図上の任意地点</h2>
                    <p>地図を動かし、現在の中心を起点にします。</p>
                    <button type="button" onClick={() => chooseOrigin({
                      kind: "map_point",
                      label: `任意地点（${state.viewport.longitude.toFixed(4)}, ${state.viewport.latitude.toFixed(4)}）`,
                      coordinates: [state.viewport.longitude, state.viewport.latitude],
                    })}>
                      地図中心を起点にする
                    </button>
                  </div>
                </div>
                <details className="area-boundary-candidate">
                  <summary>2020年国勢調査小地域（町丁・字等）から選ぶ</summary>
                  <p>統計調査用の境界です。現在の行政上の町界、住所上の町丁目、自治会区域、自治体独自の業務区域と一致するとは限りません。</p>
                  <p>舞鶴市のversioned境界fixtureが未登録のため、この公開版では選択できません。別境界で補完しません。</p>
                </details>
              </section>
            )}

            {step === 2 && (
              <section>
                <p className="area-kicker">POINT RADIUS</p>
                <h1 ref={headingRef} tabIndex={-1}>どの範囲を見ますか？</h1>
                <p>{origin?.label}</p>
                <div className="area-radius-presets">
                  <button type="button" onClick={() => chooseRadius(500)}>
                    <strong>500m</strong><small>高齢者徒歩圏の目安</small>
                  </button>
                  <button type="button" onClick={() => chooseRadius(800)}>
                    <strong>800m</strong><small>徒歩圏の目安</small>
                  </button>
                  <button type="button" onClick={() => chooseRadius(1000)}>
                    <strong>1km</strong><small>広域確認</small>
                  </button>
                </div>
                <details className="area-methodology" open>
                  <summary>800mの意味</summary>
                  <p>国土交通省「都市構造の評価に関するハンドブック」の一般的な徒歩圏800mを用いた半径ベースの分析範囲です。実際の徒歩10分到達圏を示すものではありません。</p>
                </details>
                <div className="area-custom-radius">
                  <label htmlFor="custom-radius">その他の半径（100〜3000m）</label>
                  <div><input id="custom-radius" inputMode="numeric" value={customRadius} onChange={(event) => setCustomRadius(event.target.value)} /><span>m</span><button type="button" onClick={submitCustom}>この半径を使う</button></div>
                </div>
                {error && <p role="alert" className="area-error">{error}</p>}
              </section>
            )}

            {step === 3 && summary && (
              <section>
                <h1 ref={headingRef} tabIndex={-1}>この場所について、分かっていることと、まだ分からないこと</h1>
                <p className="area-summary-label">{summary.label} · version {summary.version} · status 未確認</p>
                <AreaSummaryPanel summary={summary} />
              </section>
            )}

            {step === 4 && summary && (
              <section>
                <h1 ref={headingRef} tabIndex={-1}>確かめる対象とタスク</h1>
                <TargetTasks summary={summary} />
              </section>
            )}
          </div>

          <footer className="area-actions">
            <button type="button" onClick={back}>{step === 1 ? "入口へ戻る" : "戻る"}</button>
            {step === 3 && <button type="button" className="investigation-primary" onClick={() => setStep(4)}>PLATEAU上の確認対象を見る</button>}
            {step === 4 && (
              <>
                <button type="button" onClick={onOpenExistingM3}>現在のM3を見る</button>
                <button type="button" className="investigation-primary" onClick={onOpenAdvanced}>高度分析を開く</button>
              </>
            )}
          </footer>
        </article>
      </main>
    </div>
  );
}
