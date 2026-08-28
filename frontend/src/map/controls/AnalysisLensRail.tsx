import type { AnalysisLens, CounterfactualState, SpatialResolution, SpatialSelection } from "../../state/spatial/types";
import type { WorkspaceMapData, WorkspacePhase } from "../../types";
import { extractServicePulseRoutes, formatNetworkDistance, SERVICE_PULSE_SEMANTICS } from "../3d/pulse/servicePulse";
import { COUNTERFACTUAL_BOUNDARY } from "../3d/comparison/counterfactualTwin";
import { URBAN_XRAY_SEMANTICS } from "../3d/xray/urbanXray";

interface Props {
  value: AnalysisLens;
  counterfactual: CounterfactualState;
  resolution: SpatialResolution;
  selection: SpatialSelection | null;
  workspace: WorkspaceMapData | null;
  workspacePhase: WorkspacePhase;
  onChange(value: AnalysisLens): void;
  onCounterfactualChange(value: CounterfactualState): void;
}

const LENSES: Array<{ id: AnalysisLens; label: string; short: string }> = [
  { id: "none", label: "通常表示", short: "通常" },
  { id: "urban-xray", label: "建物群まで調べる", short: "X-RAY" },
  { id: "service-pulse", label: "道路距離をたどる", short: "PULSE" },
  { id: "changed-only", label: "施策差分だけを見る", short: "TWIN" },
  { id: "temporal-ghost", label: "年次地物差分", short: "GHOST" },
];

function boundary(lens: AnalysisLens): string {
  if (lens === "urban-xray") return URBAN_XRAY_SEMANTICS.boundary;
  if (lens === "service-pulse") return SERVICE_PULSE_SEMANTICS.boundary;
  if (lens === "changed-only") return COUNTERFACTUAL_BOUNDARY;
  if (lens === "temporal-ghost") return "PLATEAU版間の実差分sampleです。公式形状がないsampleは点・輪郭記号で示します。";
  return "実地物と分析結果を分離して表示します。";
}

export function AnalysisLensRail({ value, counterfactual, resolution, selection, workspace, workspacePhase, onChange, onCounterfactualChange }: Props) {
  const pulseRoutes = extractServicePulseRoutes(workspace, workspacePhase === "baseline" ? "scenario_a" : workspacePhase);
  const activeRoute = pulseRoutes.find((route) => route.routeKind === (counterfactual === "baseline" ? "before" : "after"));
  return (
    <section className="analysis-lens-rail" aria-label="都市分析レンズ" data-lens={value}>
      <header>
        <span>INVESTIGATION LENS</span>
        <strong>{selection?.label ?? "都市全体"}</strong>
        <small>解像度 {resolution.replace("building_group", "building group")}</small>
      </header>
      <div className="analysis-lens-tabs" role="tablist" aria-label="分析表示">
        {LENSES.map((lens) => <button key={lens.id} type="button" role="tab" aria-selected={value === lens.id} title={lens.label} onClick={() => onChange(lens.id)}>{lens.short}</button>)}
      </div>
      {value === "urban-xray" && <div className="lens-legend xray-legend"><span><i />分析面</span><strong>既存のCITY GAP計算値</strong><small>半透明面は実地形ではありません。建物色は対象メッシュへの所属を示します。</small></div>}
      {value === "service-pulse" && <div className="lens-legend pulse-legend"><span><i />NETWORK DISTANCE · 表示線は地形から分離</span><strong>{activeRoute ? formatNetworkDistance(activeRoute.networkDistanceM) : "経路を準備中"}</strong><small>{activeRoute ? activeRoute.distanceBandsM.map(formatNetworkDistance).join(" / ") : "実計算済みrouteを読み込みます"}</small></div>}
      {value === "changed-only" && <div className="counterfactual-switch" role="group" aria-label="比較状態">
        {(["baseline", "scenario", "stress"] as const).map((state) => <button key={state} type="button" className={counterfactual === state ? "active" : ""} aria-pressed={counterfactual === state} onClick={() => onCounterfactualChange(state)}>{state === "baseline" ? "現況" : state === "scenario" ? "施策案" : "災害仮定"}</button>)}
      </div>}
      <p className="lens-claim-boundary">{boundary(value)}</p>
    </section>
  );
}
