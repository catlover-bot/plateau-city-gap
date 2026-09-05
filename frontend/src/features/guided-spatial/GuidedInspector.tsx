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
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatDistance(value: unknown): string {
  const parsed = numberValue(value);
  if (parsed === null) return "データなし";
  return parsed >= 1000 ? `${(parsed / 1000).toFixed(2)}km` : `${Math.round(parsed)}m`;
}

function formatPeople(value: unknown): string {
  const parsed = numberValue(value);
  return parsed === null ? "データなし" : `${Math.round(parsed).toLocaleString("ja-JP")}人`;
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
        <span>65歳以上 {formatPeople(area.properties?.elderly_population)} · 交通 {formatDistance(area.properties?.nearest_public_transport_distance_m)} · 医療 {formatDistance(area.properties?.nearest_medical_distance_m)}</span>
      </button>)}
    </div>
    <p className="guided-data-note">人口は国勢調査2020の500m集計。交通・医療はメッシュ中心からの直線距離で、徒歩時間ではありません。</p>
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
  selectedObject: SpatialSelection | null;
  threeDActive: boolean;
}

function SelectedPlateauObject({ object }: { object: SpatialSelection }) {
  const properties = object.properties ?? {};
  const attributeNumber = (value: unknown, unit: string) => {
    const number = numberValue(value);
    return number === null ? "データなし" : `${number.toLocaleString("ja-JP")}${unit}`;
  };
  return <section className="guided-object-attributes" data-object-id={object.id} data-object-kind={object.type} aria-label="選択したPLATEAU地物の属性">
    <h2>{object.type === "building" ? "選択した建物" : "選択した道路面"}</h2>
    {object.type === "building" ? <dl>
      <div><dt>用途</dt><dd>{String(properties.usage ?? properties.usage_label ?? "データなし")}</dd></div>
      <div><dt>建物高さ</dt><dd>{attributeNumber(properties.measured_height_m, "m")}</dd></div>
      <div><dt>地上階数</dt><dd>{attributeNumber(properties.storeys_above_ground, "階")}</dd></div>
      <div><dt>地下階数</dt><dd>{attributeNumber(properties.storeys_below_ground, "階")}</dd></div>
    </dl> : <p>{String(properties.road_name ?? object.label ?? "PLATEAU道路面")}</p>}
    <p className="guided-object-source">PLATEAU 舞鶴市 {String(properties.source_version ?? object.urbanState)}{properties.lod ? ` · ${String(properties.lod)}` : ""}</p>
    <details><summary>選択対象の出典ID</summary><code>{object.id}</code></details>
  </section>;
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
  selectedObject,
  threeDActive,
  titleRef,
  onStoryChange,
}: AreaUnderstandingProps) {
  return <div className={`guided-scene-content ${threeDActive ? "guided-3d-inspector" : ""}`}>
    <div className="guided-panel-kicker">
      <button type="button" className="guided-back" onClick={() => onStoryChange("find")}>{GUIDED_CONTENT.understand.back}</button>
    </div>
    <h1 id="guided-story-title" ref={titleRef} tabIndex={-1}>{areaLabel}</h1>
    {selectedObject && <SelectedPlateauObject object={selectedObject} />}
    {threeDActive && !selectedObject && <p className="guided-section-note">3Dの建物を選ぶと、収録された用途・高さ・階数を確認できます。</p>}
    <dl className="guided-known-summary">
      <div><dt>この地域の人口 {formatPeople(properties.population)}</dt><dd>うち65歳以上 {formatPeople(properties.elderly_population)}（国勢調査2020・500m集計）</dd></div>
      <div><dt>この範囲の建物・道路</dt><dd>{catalogItem ? `PLATEAU建物 ${catalogItem.counts.buildings.toLocaleString("ja-JP")}棟・道路面 ${catalogItem.counts.roads.toLocaleString("ja-JP")}件` : contextStatus === "loading" ? "読み込み中" : "データなし"}<small>範囲と交差する2D地物の集計。3D画面内の描画数ではありません。</small></dd></div>
      {!threeDActive && <div><dt>都市計画・交通</dt><dd>範囲と交差する公式の都市計画形状 {catalogItem?.counts.planning.toLocaleString("ja-JP") ?? "—"}件・収録駅/バス停まで直線 {formatDistance(properties.nearest_public_transport_distance_m)}</dd></div>}
    </dl>
    {contextStatus === "loading" && <p role="status" className="guided-loading">{GUIDED_CONTENT.loading.context}</p>}
    {contextError && <p role="alert" className="guided-error">{contextError}</p>}
    {!activeSectionData && (sectionError
        ? <p className="guided-boundary">断面は読み込めません。範囲内の建物・道路・都市計画は引き続き確認できます。</p>
        : <p className="guided-boundary">{context?.section.reason?.replaceAll("Area", "範囲") ?? "この範囲では検証済みの街の断面を表示していません。"}</p>)}
    <div className="guided-unknown-bridge">
      <strong>{threeDActive ? "出入口や通行条件は、現地で確認" : GUIDED_CONTENT.understand.unknownTitle}</strong>
      <p>{threeDActive ? "LOD1の形状や道路面は、入口・歩道・段差や通行可能性を確認した記録ではありません。" : GUIDED_CONTENT.understand.unknownReason}</p>
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
    <div className="guided-task-heading"><h2>確認項目 <small>{target?.checks.length ?? 0}件・未確認</small></h2></div>
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
  selectedObject: SpatialSelection | null;
  threeDActive: boolean;
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
