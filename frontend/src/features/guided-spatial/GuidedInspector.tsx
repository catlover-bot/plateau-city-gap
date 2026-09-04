import type { RefObject } from "react";
import type { AppData } from "../../types";
import type { GuidedStory, SpatialSelection } from "../../state/spatial/types";
import type { SectionData } from "../urban-section/sectionTypes";
import { GUIDED_DEFAULT_AREA } from "./guidedData";
import { GUIDED_CONTENT } from "./guidedContent";
import type { GuidedAreaCatalogItem, GuidedAreaContext } from "./guidedTypes";
import type { GuidedContextStatus } from "./useGuidedAreaContext";
import type { GuidedTargetChoice } from "./guidedTargets";

function numberValue(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatDistance(value: unknown): string {
  const parsed = numberValue(value);
  if (parsed === null) return "データなし";
  return parsed >= 1000 ? `${(parsed / 1000).toFixed(2)}km` : `${Math.round(parsed)}m`;
}

interface SharedProps {
  titleRef: RefObject<HTMLHeadingElement>;
  onStoryChange(story: GuidedStory): void;
}

function GuidedIntroInspector({ titleRef, onStoryChange }: SharedProps) {
  return <div className="guided-intro">
    <h1 id="guided-story-title" ref={titleRef} tabIndex={-1}>
      {GUIDED_CONTENT.intro.titleFirstLine}<br />{GUIDED_CONTENT.intro.titleSecondLine}
    </h1>
    <p>{GUIDED_CONTENT.intro.description}</p>
    <button type="button" className="guided-primary" onClick={() => onStoryChange("find")}>
      {GUIDED_CONTENT.intro.action}
    </button>
  </div>;
}

interface AreaSelectionProps extends SharedProps {
  data: AppData;
  selectedAreaId: string;
  shortlisted: SpatialSelection[];
  hoveredAreaId: string | null;
  onSelectArea(meshCode: string): void;
  onAreaHover(meshCode: string | null): void;
}

function AreaSelectionInspector({
  data,
  selectedAreaId,
  shortlisted,
  hoveredAreaId,
  titleRef,
  onStoryChange,
  onSelectArea,
  onAreaHover,
}: AreaSelectionProps) {
  return <div className="guided-scene-content">
    <div className="guided-panel-kicker"><span className="guided-eyebrow">{GUIDED_CONTENT.find.eyebrow}</span></div>
    <h1 id="guided-story-title" ref={titleRef} tabIndex={-1}>{GUIDED_CONTENT.find.title}</h1>
    <p className="guided-scene-lead">{GUIDED_CONTENT.find.lead}</p>
    <label className="guided-area-select">選んだ地域
      <select aria-label="495の範囲から選ぶ" value={selectedAreaId} onChange={(event) => onSelectArea(event.target.value)}>
        {data.meshes.features.map((feature) => {
          const meshCode = String(feature.properties?.mesh_code ?? "");
          const label = meshCode === GUIDED_DEFAULT_AREA
            ? "常団地前周辺"
            : String(feature.properties?.area_label ?? `500mメッシュ ${meshCode}`);
          return <option key={meshCode} value={meshCode}>{label}</option>;
        })}
      </select>
    </label>
    <div className="guided-area-list" aria-label="代表的な調査範囲">
      {shortlisted.map((area) => <button
        key={area.id}
        type="button"
        data-area-row={area.id}
        className={[area.id === selectedAreaId ? "selected" : "", area.id === hoveredAreaId ? "hovered" : ""].filter(Boolean).join(" ")}
        aria-pressed={area.id === selectedAreaId}
        aria-current={area.id === selectedAreaId ? "true" : undefined}
        onClick={() => onSelectArea(area.id)}
        onPointerEnter={() => onAreaHover(area.id)}
        onPointerLeave={() => onAreaHover(null)}
        onFocus={() => onAreaHover(area.id)}
        onBlur={() => onAreaHover(null)}
      >
        <strong>{area.label}</strong>
        <span>65歳以上 {Math.round(numberValue(area.properties?.elderly_population) ?? 0).toLocaleString("ja-JP")}人 · 交通 {formatDistance(area.properties?.nearest_public_transport_distance_m)} · 医療 {formatDistance(area.properties?.nearest_medical_distance_m)}</span>
      </button>)}
    </div>
    <button type="button" className="guided-primary" onClick={() => onStoryChange("understand")}>
      {GUIDED_CONTENT.find.action}
    </button>
  </div>;
}

interface AreaUnderstandingProps extends SharedProps {
  areaLabel: string;
  properties: Record<string, unknown>;
  catalogItem: GuidedAreaCatalogItem | null;
  contextStatus: GuidedContextStatus;
  contextError: string | null;
  context: GuidedAreaContext | null;
  activeSectionData: SectionData | null;
  sectionError: string | null;
}

function AreaUnderstandingInspector({
  areaLabel,
  properties,
  catalogItem,
  contextStatus,
  contextError,
  context,
  activeSectionData,
  sectionError,
  titleRef,
  onStoryChange,
}: AreaUnderstandingProps) {
  return <div className="guided-scene-content">
    <div className="guided-panel-kicker">
      <button type="button" className="guided-back" onClick={() => onStoryChange("find")}>{GUIDED_CONTENT.understand.back}</button>
      <span className="guided-eyebrow">{GUIDED_CONTENT.understand.eyebrow}</span>
    </div>
    <h1 id="guided-story-title" ref={titleRef} tabIndex={-1}>{areaLabel}の地形と建物</h1>
    <dl className="guided-known-summary">
      <div><dt>人口 {Math.round(numberValue(properties.population) ?? 0).toLocaleString("ja-JP")}人</dt><dd>うち65歳以上 {Math.round(numberValue(properties.elderly_population) ?? 0).toLocaleString("ja-JP")}人（国勢調査2020）</dd></div>
      <div><dt>街の形</dt><dd>範囲と交差するPLATEAU建物 {catalogItem?.counts.buildings.toLocaleString("ja-JP") ?? "—"}棟・道路面 {catalogItem?.counts.roads.toLocaleString("ja-JP") ?? "—"}件</dd></div>
      <div><dt>都市計画・交通</dt><dd>範囲と交差する公式の都市計画形状 {catalogItem?.counts.planning.toLocaleString("ja-JP") ?? "—"}件・収録駅/バス停まで直線 {formatDistance(properties.nearest_public_transport_distance_m)}</dd></div>
    </dl>
    {contextStatus === "loading" && <p role="status" className="guided-loading">{GUIDED_CONTENT.loading.context}</p>}
    {contextError && <p role="alert" className="guided-error">{contextError}</p>}
    {activeSectionData
      ? <p className="guided-section-note">地図上のA–B線を横から見た断面です。</p>
      : sectionError
        ? <p className="guided-boundary">断面は読み込めません。範囲内の建物・道路・都市計画は引き続き確認できます。</p>
        : <p className="guided-boundary">{context?.section.reason?.replaceAll("Area", "範囲") ?? "この範囲では検証済みの街の断面を表示していません。"}</p>}
    <div className="guided-unknown-bridge">
      <span>{GUIDED_CONTENT.understand.unknownLabel}</span>
      <strong>{GUIDED_CONTENT.understand.unknownTitle}</strong>
      <p>{GUIDED_CONTENT.understand.unknownReason}</p>
    </div>
    <button type="button" className="guided-primary" onClick={() => onStoryChange("verify")}>
      {GUIDED_CONTENT.understand.action}
    </button>
  </div>;
}

interface TargetVerificationProps extends SharedProps {
  areaLabel: string;
  targetChoices: GuidedTargetChoice[];
  target: GuidedTargetChoice | undefined;
  onTargetChange(key: string): void;
  onOpenAdvanced(): void;
}

function TargetVerificationInspector({
  areaLabel,
  targetChoices,
  target,
  titleRef,
  onStoryChange,
  onTargetChange,
  onOpenAdvanced,
}: TargetVerificationProps) {
  return <div className="guided-scene-content">
    <div className="guided-panel-kicker">
      <button type="button" className="guided-back" onClick={() => onStoryChange("understand")}>{GUIDED_CONTENT.verify.back}</button>
      <span className="guided-eyebrow">{GUIDED_CONTENT.verify.eyebrow}</span>
    </div>
    <h1 id="guided-story-title" ref={titleRef} tabIndex={-1}>{GUIDED_CONTENT.verify.title}</h1>
    {targetChoices.length > 1 && <label className="guided-target-select">確認対象
      <select value={target?.key} onChange={(event) => onTargetChange(event.target.value)}>
        {targetChoices.map((choice) => <option key={choice.key} value={choice.key}>{choice.label}</option>)}
      </select>
    </label>}
    <section className="guided-target-summary" data-resolution={target?.resolution} aria-labelledby="guided-target-title">
      <span>{target?.resolution === "exact" ? target.kind === "facility" ? "登録施設" : target.kind === "building" ? "PLATEAU建物" : "PLATEAU道路" : "500mの確認範囲"}</span>
      <h2 id="guided-target-title">{target?.label ?? areaLabel}</h2>
      <p>{target?.reason}</p>
    </section>
    <div className="guided-task-heading"><span>未確認</span><h2>現地で確かめること <small>{target?.checks.length ?? 0}件</small></h2></div>
    <ol className="guided-check-list">
      {target?.checks.map(([id, label, reason]) => <li key={id}><strong>{label}</strong><span>{reason}</span></li>)}
    </ol>
    <p className="guided-boundary">{GUIDED_CONTENT.verify.emptyEvidence}</p>
    <button type="button" className="guided-secondary-action" onClick={onOpenAdvanced}>{GUIDED_CONTENT.verify.advancedAction}</button>
  </div>;
}

interface Props extends SharedProps {
  story: GuidedStory;
  data: AppData;
  selectedAreaId: string;
  areaLabel: string;
  properties: Record<string, unknown>;
  shortlisted: SpatialSelection[];
  hoveredAreaId: string | null;
  catalogItem: GuidedAreaCatalogItem | null;
  catalogError: string | null;
  contextStatus: GuidedContextStatus;
  contextError: string | null;
  context: GuidedAreaContext | null;
  activeSectionData: SectionData | null;
  sectionError: string | null;
  targetChoices: GuidedTargetChoice[];
  target: GuidedTargetChoice | undefined;
  onSelectArea(meshCode: string): void;
  onAreaHover(meshCode: string | null): void;
  onTargetChange(key: string): void;
  onOpenAdvanced(): void;
}

export function GuidedInspector(props: Props) {
  return <aside className="guided-story-panel" aria-labelledby="guided-story-title" data-inspector-story={props.story}>
    {props.catalogError && <p role="alert" className="guided-error">{props.catalogError}</p>}
    {props.story === "intro" && <GuidedIntroInspector {...props} />}
    {props.story === "find" && <AreaSelectionInspector {...props} />}
    {props.story === "understand" && <AreaUnderstandingInspector {...props} />}
    {props.story === "verify" && <TargetVerificationInspector {...props} />}
  </aside>;
}
