import { useMemo, useState } from "react";
import type {
  MunicipalWorkspaceData,
  NetworkScenarioStoryPlan,
  WorkspaceLayerVisibility,
  WorkspacePhase
} from "../types";
import {
  MAX_SCENARIO_COMPARISON,
  toggleScenarioComparison,
  transitionScenario,
  type ScenarioLifecycleStatus
} from "../lib/workspace";

type WorkflowStep =
  | "discover"
  | "area"
  | "plateau"
  | "network"
  | "context"
  | "scenario"
  | "compare"
  | "review";

type FieldStatus = "unknown" | "confirmed" | "attention" | "not_applicable";

interface MunicipalWorkspaceProps {
  data: MunicipalWorkspaceData;
  cityCode: string;
  phase: WorkspacePhase;
  layers: WorkspaceLayerVisibility;
  onPhaseChange: (phase: WorkspacePhase) => void;
  onLayersChange: (layers: WorkspaceLayerVisibility) => void;
}

const WORKFLOW: Array<{ id: WorkflowStep; number: string; label: string }> = [
  { id: "discover", number: "01", label: "課題発見" },
  { id: "area", number: "02", label: "地域を見る" },
  { id: "plateau", number: "03", label: "PLATEAU詳細" },
  { id: "network", number: "04", label: "道路ネットワーク" },
  { id: "context", number: "05", label: "計画・災害" },
  { id: "scenario", number: "06", label: "シナリオ作成" },
  { id: "compare", number: "07", label: "複数案比較" },
  { id: "review", number: "08", label: "現地確認・根拠" }
];

const CAPABILITY_LABELS: Record<string, string> = {
  screening: "500mスクリーニング",
  building_detail: "建物詳細",
  road_network: "道路ネットワーク",
  terrain: "地形",
  land_use: "土地利用",
  urban_planning: "都市計画",
  hazard: "災害",
  scenario: "シナリオ",
  gtfs: "GTFS"
};

const LIFECYCLE_LABELS: Record<ScenarioLifecycleStatus, string> = {
  draft: "下書き",
  under_review: "庁内レビュー中",
  field_check_required: "現地確認待ち",
  reviewed: "確認済み",
  archived: "アーカイブ"
};

const FIELD_ITEMS = [
  ["site_access", "候補地点への進入・動線"],
  ["road_safety", "道路・歩行環境の安全性"],
  ["land_ownership_unknown", "用地所有・利用条件"],
  ["existing_service", "既存サービスとの関係"],
  ["facility_condition", "施設・設置場所の状態"],
  ["hazard_confirmation", "災害リスクの現況"],
  ["operator_consultation", "運行・管理者との協議"]
] as const;

const INITIAL_FIELD_STATUS = Object.fromEntries(
  FIELD_ITEMS.map(([key]) => [key, "unknown"])
) as Record<(typeof FIELD_ITEMS)[number][0], FieldStatus>;

const number = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 1 });

function scenarioName(plan: NetworkScenarioStoryPlan): string {
  if (plan.story_id === "scenario_a") return "Scenario A";
  if (plan.story_id === "scenario_b") return "Scenario B";
  return "Scenario C";
}

function planningContextCount(plan: NetworkScenarioStoryPlan): number {
  return new Set(
    plan.sites.flatMap((site) => site.planning_context.split("|").map((value) => value.trim()))
  ).size;
}

function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function downloadEvidenceCsv(plan: NetworkScenarioStoryPlan) {
  const rows: unknown[][] = [["record_type", "key", "value", "unit", "source_id"]];
  for (const [key, value] of Object.entries(plan.impact)) {
    if (typeof value === "number") rows.push(["aggregate_impact", key, value, "reported_metric", plan.plan_id]);
  }
  for (const site of plan.sites) {
    rows.push(["site", `site_${site.site_order}`, site.road_name ?? "", "", site.candidate_id]);
    rows.push(["site_context", "landuse", site.landuse_context, "", site.candidate_id]);
    rows.push(["site_context", "planning", site.planning_context, "", site.candidate_id]);
    rows.push(["site_context", "hazard", site.hazard_context, "", site.candidate_id]);
  }
  const evidence = plan.representative_evidence;
  rows.push(["representative_route", "before_network_distance", evidence.before.network_distance_m, "m", evidence.building_gml_id]);
  rows.push(["representative_route", "after_network_distance", evidence.after.network_distance_m, "m", evidence.building_gml_id]);
  const blob = new Blob([rows.map((row) => row.map(csvCell).join(",")).join("\n") + "\n"], {
    type: "text/csv;charset=utf-8"
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${plan.plan_id}-evidence.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function ScenarioSummary({ plan }: { plan: NetworkScenarioStoryPlan }) {
  return (
    <div className="workspace-metric-grid">
      <div><span>配置候補</span><strong>{plan.site_count}</strong><small>地点</small></div>
      <div><span>改善建物</span><strong>{number.format(plan.impact.improved_building_count)}</strong><small>棟</small></div>
      <div><span>改善メッシュ</span><strong>{number.format(plan.impact.improved_mesh_count)}</strong><small>mesh</small></div>
      <div><span>改善建物の平均</span><strong>{decimal.format(plan.impact.mean_reduction_improved_buildings_m)}</strong><small>m</small></div>
    </div>
  );
}

export function MunicipalWorkspace({
  data,
  cityCode,
  phase,
  layers,
  onPhaseChange,
  onLayersChange
}: MunicipalWorkspaceProps) {
  const [step, setStep] = useState<WorkflowStep>("discover");
  const [comparison, setComparison] = useState<string[]>([
    "scenario_a",
    "scenario_b",
    "scenario_c"
  ]);
  const [lifecycle, setLifecycle] = useState<Record<string, ScenarioLifecycleStatus>>({
    scenario_a: "draft",
    scenario_b: "draft",
    scenario_c: "draft"
  });
  const [fieldStatus, setFieldStatus] = useState(INITIAL_FIELD_STATUS);
  const [fieldNote, setFieldNote] = useState("");
  const stories = data.story.scenario_story;
  const activeStoryId = phase === "scenario_b" || phase === "scenario_c" ? phase : "scenario_a";
  const activePlan = stories.find((item) => item.story_id === activeStoryId) ?? stories[0];
  const cityCapabilities = useMemo(
    () => data.registry.capabilities.filter((item) => item.city_code === cityCode),
    [cityCode, data.registry.capabilities]
  );
  const isAvailable = cityCapabilities.some(
    (item) => item.capability === "scenario" && item.status === "available"
  );

  const chooseStep = (next: WorkflowStep) => {
    setStep(next);
    const base: WorkspaceLayerVisibility = {
      meshes: false,
      affectedBuildings: false,
      routes: false,
      plateauBuildings: false,
      roadNetwork: false,
      landuse: false,
      planning: false,
      hazard: false
    };
    if (next === "discover" || next === "area") {
      onPhaseChange("baseline");
      onLayersChange({ ...base, meshes: true });
    } else if (next === "plateau") {
      onPhaseChange("scenario_a");
      onLayersChange({ ...base, plateauBuildings: true });
    } else if (next === "network") {
      onPhaseChange("scenario_a");
      onLayersChange({ ...base, roadNetwork: true, routes: true });
    } else if (next === "context") {
      onPhaseChange("scenario_a");
      onLayersChange({ ...base, roadNetwork: true, planning: true });
    } else if (next === "scenario") {
      onPhaseChange("scenario_a");
      onLayersChange({ ...base, affectedBuildings: true, roadNetwork: true });
    } else if (next === "compare") {
      onPhaseChange("scenario_a");
      onLayersChange({ ...base, affectedBuildings: true, roadNetwork: true, routes: true });
    } else {
      onPhaseChange(activeStoryId);
      onLayersChange({ ...base, affectedBuildings: true, roadNetwork: true, routes: true, hazard: true });
    }
  };

  const setContextLayer = (context: "none" | "landuse" | "planning" | "hazard") => {
    onLayersChange({
      ...layers,
      landuse: context === "landuse",
      planning: context === "planning",
      hazard: context === "hazard"
    });
  };

  if (!isAvailable) {
    return (
      <div className="municipal-workspace unavailable-workspace">
        <div className="workspace-heading">
          <p>MUNICIPAL WORKSPACE</p>
          <h2>この都市ではシナリオ機能を利用できません</h2>
          <span>登録済み実データだけを表示しています。未計算の機能を舞鶴市の結果で代用しません。</span>
        </div>
        <div className="capability-list">
          {cityCapabilities.map((capability) => (
            <div key={capability.capability}>
              <span>{CAPABILITY_LABELS[capability.capability] ?? capability.capability}</span>
              <strong className={`capability-status ${capability.status}`}>{capability.status}</strong>
              <small>{capability.note}</small>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const currentStatus = lifecycle[activePlan.story_id];
  const fieldComplete = Object.values(fieldStatus).every((value) => value !== "unknown");
  const transition = (next: ScenarioLifecycleStatus) => {
    setLifecycle((current) => ({
      ...current,
      [activePlan.story_id]: transitionScenario(current[activePlan.story_id], next)
    }));
  };

  return (
    <div className="municipal-workspace">
      <div className="workspace-heading">
        <div><p>MUNICIPAL WORKSPACE · 京都府</p><span className="workspace-version">実データ / {data.story.schema_version}</span></div>
        <h2>舞鶴市 Urban Digital Twin</h2>
        <span>課題候補の発見から現地確認まで。同じ根拠チェーンで案を検証します。</span>
      </div>

      <nav className="workspace-steps" aria-label="自治体分析ワークフロー">
        {WORKFLOW.map((item) => (
          <button
            key={item.id}
            type="button"
            className={step === item.id ? "active" : ""}
            aria-current={step === item.id ? "step" : undefined}
            onClick={() => chooseStep(item.id)}
          >
            <span>{item.number}</span>{item.label}
          </button>
        ))}
      </nav>

      <div className="workspace-scroll">
        <section className="workspace-layer-controls" aria-label="地図レイヤー">
          <div className="section-heading"><h3>地図レイヤー</h3><span>表示中の案に連動</span></div>
          <div className="layer-checks">
            {([
              ["meshes", "500mメッシュ"],
              ["plateauBuildings", "PLATEAU建物"],
              ["roadNetwork", "道路ネットワーク"],
              ["affectedBuildings", "改善対象建物"],
              ["routes", "代表経路"]
            ] as const).map(([key, label]) => (
              <label key={key}><input type="checkbox" checked={layers[key]} onChange={() => onLayersChange({ ...layers, [key]: !layers[key] })} /><span>{label}</span></label>
            ))}
          </div>
          <div className="context-layer-switch" role="group" aria-label="重ねる都市コンテキスト">
            <span>都市コンテキスト</span>
            {([
              ["none", "なし"], ["landuse", "土地利用"], ["planning", "都市計画"], ["hazard", "災害"]
            ] as const).map(([key, label]) => {
              const selected = key === "none" ? !layers.landuse && !layers.planning && !layers.hazard : layers[key];
              return <button key={key} type="button" className={selected ? "active" : ""} aria-pressed={selected} onClick={() => setContextLayer(key)}>{label}</button>;
            })}
          </div>
        </section>

        {(step === "discover" || step === "area") && (
          <section className="workspace-section">
            <div className="section-heading"><h3>データ解像度を段階的に上げる</h3><span>発見 → 検証</span></div>
            <div className="resolution-strip" aria-label="分析解像度">
              <span className="active">500m</span><i />
              <span>建物</span><i />
              <span>道路網</span><i />
              <span>計画・災害</span><i />
              <span>施策案</span>
            </div>
            <p className="workspace-note">500mメッシュは課題候補を絞る入口です。建物単位人口は推計値であり、地図には個別人数を表示しません。</p>
            <div className="capability-list compact">
              {cityCapabilities.map((capability) => (
                <div key={capability.capability}>
                  <span>{CAPABILITY_LABELS[capability.capability] ?? capability.capability}</span>
                  <strong className={`capability-status ${capability.status}`}>{capability.status}</strong>
                  <small>{capability.note}</small>
                </div>
              ))}
            </div>
          </section>
        )}

        {step === "plateau" && (
          <section className="workspace-section">
            <div className="section-heading"><h3>PLATEAU建物詳細</h3><span>LOD1 / LOD2参照</span></div>
            <p className="workspace-note">公式CityGMLの建物属性と形状を、建物人口配分と到達性の検証単位に利用しています。用途・階数・床面積は存在する属性だけを表示します。</p>
            <dl className="workspace-definition">
              <div><dt>建物人口</dt><dd>2020国勢調査を住宅系建物へ面積配分した推計</dd></div>
              <div><dt>公開地図</dt><dd>建物位置と距離改善帯のみ。建物別人数は非公開</dd></div>
              <div><dt>座標系</dt><dd>分析 EPSG:6674 / 表示 EPSG:4326</dd></div>
            </dl>
          </section>
        )}

        {step === "network" && (
          <section className="workspace-section">
            <div className="section-heading"><h3>道路ネットワーク検証</h3><span className="capability-status partial">partial</span></div>
            <p className="workspace-note">PLATEAU LOD1道路面の隣接グラフです。歩行者通行可否を確認済みの歩行ネットワークではないため、代表経路は現地確認対象です。</p>
            <dl className="workspace-definition">
              <div><dt>代表建物</dt><dd>{activePlan.representative_evidence.building_gml_id}</dd></div>
              <div><dt>現況経路</dt><dd>{decimal.format(activePlan.representative_evidence.before.network_distance_m)}m</dd></div>
              <div><dt>配置後経路</dt><dd>{decimal.format(activePlan.representative_evidence.after.network_distance_m)}m</dd></div>
              <div><dt>判定</dt><dd>経路形状は解析上の根拠。歩行可能性は未確定</dd></div>
            </dl>
          </section>
        )}

        {step === "context" && (
          <section className="workspace-section">
            <div className="section-heading"><h3>候補地点の計画・災害文脈</h3><span>自動判定しない</span></div>
            <div className="site-context-list">
              {activePlan.sites.map((site) => (
                <article key={site.candidate_id}>
                  <div><strong>候補 {site.site_order} · {site.road_name ?? "道路名なし"}</strong><span>{site.candidate_id}</span></div>
                  <dl>
                    <div><dt>土地利用</dt><dd>{site.landuse_context}</dd></div>
                    <div><dt>都市計画</dt><dd>{site.planning_context}</dd></div>
                    <div><dt>災害</dt><dd>{site.hazard_context}</dd></div>
                  </dl>
                  <p>配置可否: 未判定 / {site.hazard_review_status}</p>
                </article>
              ))}
            </div>
          </section>
        )}

        {step === "scenario" && (
          <section className="workspace-section">
            <div className="section-heading"><h3>{scenarioName(activePlan)} · {activePlan.label}</h3><span>{activePlan.site_count}地点案</span></div>
            <div className="scenario-choice" role="group" aria-label="シナリオ案">
              {stories.map((plan) => (
                <button key={plan.story_id} type="button" className={activeStoryId === plan.story_id ? "active" : ""} onClick={() => onPhaseChange(plan.story_id)}>
                  <strong>{scenarioName(plan)}</strong><span>{plan.label}</span>
                </button>
              ))}
            </div>
            <ScenarioSummary plan={activePlan} />
            <p className="objective-copy"><strong>目的関数</strong>{activePlan.objective}</p>
            <p className="workspace-note">候補集合に対する前向き貪欲近似。施策の推奨・採否を自動決定するものではありません。</p>
          </section>
        )}

        {step === "compare" && (
          <section className="workspace-section comparison-section">
            <div className="section-heading"><h3>複数案比較</h3><span>最大{MAX_SCENARIO_COMPARISON}案</span></div>
            <div className="comparison-select">
              {stories.map((plan) => (
                <label key={plan.story_id}>
                  <input type="checkbox" checked={comparison.includes(plan.story_id)} onChange={() => setComparison((current) => toggleScenarioComparison(current, plan.story_id))} />
                  <span>{scenarioName(plan)} · {plan.label}</span>
                </label>
              ))}
            </div>
            <div className="comparison-table-wrap">
              <table className="comparison-table">
                <thead><tr><th>指標</th><th>Baseline</th>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <th key={plan.story_id}>{scenarioName(plan)}</th>)}</tr></thead>
                <tbody>
                  <tr><th>配置地点</th><td>0</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{plan.site_count}</td>)}</tr>
                  <tr><th>改善建物</th><td>0</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{number.format(plan.impact.improved_building_count)}</td>)}</tr>
                  <tr><th>影響する高齢者推計</th><td>0</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{number.format(plan.impact.affected_estimated_elderly_population)}人相当</td>)}</tr>
                  <tr><th>network距離総改善</th><td>0km</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{decimal.format(plan.impact.total_building_distance_reduction_m / 1000)}km</td>)}</tr>
                  <tr><th>改善建物の平均</th><td>—</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{decimal.format(plan.impact.mean_reduction_improved_buildings_m)}m</td>)}</tr>
                  <tr><th>最遠10%の平均改善</th><td>0m</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{decimal.format(plan.impact.worst_decile_mean_reduction_m)}m</td>)}</tr>
                  <tr><th>災害確認flag</th><td>—</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{plan.sites.filter((site) => site.hazard_overlap).length}/{plan.site_count}地点</td>)}</tr>
                  <tr><th>都市計画context</th><td>—</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{planningContextCount(plan)}属性</td>)}</tr>
                  <tr><th>Robust Top20改善</th><td>0</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{number.format(plan.impact.robust_top20_improved_mesh_count)} mesh</td>)}</tr>
                  <tr><th>algorithm</th><td>現況</td>{stories.filter((plan) => comparison.includes(plan.story_id)).map((plan) => <td key={plan.story_id}>{plan.exactness.includes("approx") ? "決定論的貪欲近似" : "検証済"}</td>)}</tr>
                </tbody>
              </table>
            </div>
            <p className="workspace-note">指標を横並びで確認します。どの案を採用するかは自治体レビューで決定してください。</p>
          </section>
        )}

        {step === "review" && (
          <section className="workspace-section review-section">
            <div className="section-heading"><h3>レビューと現地確認</h3><span className={`lifecycle-chip ${currentStatus}`}>{LIFECYCLE_LABELS[currentStatus]}</span></div>
            <div className="lifecycle-actions">
              {currentStatus === "draft" && <button type="button" onClick={() => transition("under_review")}>庁内レビューを開始</button>}
              {currentStatus === "under_review" && <button type="button" onClick={() => transition("field_check_required")}>現地確認へ送る</button>}
              {currentStatus === "field_check_required" && <button type="button" disabled={!fieldComplete} onClick={() => transition("reviewed")}>確認済みにする</button>}
              {currentStatus === "reviewed" && <button type="button" onClick={() => transition("archived")}>アーカイブ</button>}
            </div>
            <p className="workspace-note">公開プレビューでは状態をブラウザ内だけで保持します。運用版はScenario APIへ履歴・コメントとともに保存します。</p>
            <div className="field-check-list">
              {FIELD_ITEMS.map(([key, label]) => (
                <label key={key}><span>{label}</span><select value={fieldStatus[key]} onChange={(event) => setFieldStatus((current) => ({ ...current, [key]: event.target.value as FieldStatus }))}><option value="unknown">未確認</option><option value="confirmed">確認</option><option value="attention">要対応</option><option value="not_applicable">対象外</option></select></label>
              ))}
              <label className="field-note"><span>現地メモ</span><textarea value={fieldNote} onChange={(event) => setFieldNote(event.target.value)} placeholder="確認日、担当、判断根拠を記録" rows={3} /></label>
            </div>
            <div className="evidence-chain">
              <h4>Evidence chain</h4>
              <ol>
                <li><span>01</span><div><strong>入力</strong><small>PLATEAU 2025 / 国勢調査 2020 / 施設・交通</small></div></li>
                <li><span>02</span><div><strong>解析</strong><small>{activePlan.plan_id} / {data.story.schema_version}</small></div></li>
                <li><span>03</span><div><strong>代表建物</strong><small>{activePlan.representative_evidence.building_gml_id}</small></div></li>
                <li><span>04</span><div><strong>代表経路</strong><small>{decimal.format(activePlan.representative_evidence.before.network_distance_m)}m → {decimal.format(activePlan.representative_evidence.after.network_distance_m)}m</small></div></li>
              </ol>
            </div>
            <div className="evidence-actions">
              <a href={`${import.meta.env.BASE_URL}data/municipal_workspace_story.json`} download>JSON</a>
              <button type="button" onClick={() => downloadEvidenceCsv(activePlan)}>CSV</button>
              <button type="button" onClick={() => window.print()}>印刷</button>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
