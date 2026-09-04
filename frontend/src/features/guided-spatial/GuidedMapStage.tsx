import { useMemo } from "react";
import type { AppData } from "../../types";
import type { SpatialSelection, SpatialState, SpatialViewport } from "../../state/spatial/types";
import { AnalyticalMap } from "../../map/2d/AnalyticalMap";
import { UrbanSection } from "../urban-section/UrbanSection";
import type { SectionData } from "../urban-section/sectionTypes";
import type { GuidedMapPresentation } from "./guidedTypes";
import type { GuidedTargetChoice } from "./guidedTargets";

const MAP_LAYERS = ["reference-gsi-pale", "analysis-city-gap"];

interface GuidedLegendItem {
  label: string;
  symbol: "area" | "candidate" | "building" | "road" | "section" | "target" | "context";
}

function GuidedContextLegend({ title, items }: { title: string; items: GuidedLegendItem[] }) {
  return <aside className="guided-context-legend" aria-label={title}>
    <strong>{title}</strong>
    <div>{items.map((item) => <span key={item.label}>
      <i className={`symbol-${item.symbol}`} aria-hidden="true" />{item.label}
    </span>)}</div>
  </aside>;
}

interface Props {
  data: AppData;
  state: SpatialState;
  selectedArea: SpatialSelection | null;
  areaLabel: string;
  presentation: GuidedMapPresentation;
  target: GuidedTargetChoice | undefined;
  activeSectionData: SectionData | null;
  expectedSectionPackId?: string;
  mobileSurface: "map" | "section";
  onMobileSurfaceChange(surface: "map" | "section"): void;
  onSelectionChange(selection: SpatialSelection | null): void;
  onViewportChange(viewport: SpatialViewport): void;
  onAreaHover(meshCode: string | null): void;
  onGuidedObjectSelect(kind: "building" | "road", objectId: string): void;
  onSectionFocus(position: { longitude: number; latitude: number } | null): void;
}

export function GuidedMapStage({
  data,
  state,
  selectedArea,
  areaLabel,
  presentation,
  target,
  activeSectionData,
  expectedSectionPackId,
  mobileSurface,
  onMobileSurfaceChange,
  onSelectionChange,
  onViewportChange,
  onAreaHover,
  onGuidedObjectSelect,
  onSectionFocus,
}: Props) {
  const mapLegend = useMemo<{ title: string; items: GuidedLegendItem[] } | null>(() => {
    if (state.guidedStory === "find") return {
      title: "地図の見方",
      items: [
        { label: "選んだ地域", symbol: "area" },
        { label: "候補の地域", symbol: "candidate" },
      ],
    };
    if (state.guidedStory === "understand") return {
      title: "街の形",
      items: [
        { label: "建物", symbol: "building" },
        { label: "道路", symbol: "road" },
        ...(activeSectionData ? [{ label: "A–B断面", symbol: "section" as const }] : []),
      ],
    };
    if (state.guidedStory === "verify") return {
      title: "確認する場所",
      items: [
        {
          label: target?.resolution === "exact" ? "選んだ対象" : "確認する範囲",
          symbol: target?.resolution === "exact" ? "target" : "area",
        },
        { label: "選んだ地域", symbol: "context" },
      ],
    };
    return null;
  }, [activeSectionData, state.guidedStory, target?.resolution]);

  const captionLabel = state.guidedStory === "intro"
    ? "舞鶴市全域"
    : state.guidedStory === "find"
      ? "地域を選ぶ"
      : state.guidedStory === "understand" ? "街の形" : "確認する場所";
  const captionDetail = state.guidedStory === "intro"
    ? "495の500m範囲から調べる地域を選べます"
    : state.guidedStory === "find"
      ? "選んだ500m範囲"
      : state.guidedStory === "understand"
        ? "PLATEAU 舞鶴市2025"
        : target?.resolution === "exact"
          ? `実在する${target.kind === "road" ? "PLATEAU道路面" : target.kind === "building" ? "PLATEAU建物" : "登録地点"}`
          : "個別対象は未解決・選んだ範囲で確認";

  return <section className="guided-map-stage" aria-label="舞鶴市の調査範囲とPLATEAU表示">
    <AnalyticalMap
      data={data}
      validation={null}
      preset="discovery"
      primaryLayer="analysis-city-gap"
      activeLayerIdsOverride={MAP_LAYERS}
      selection={selectedArea}
      viewport={state.viewport}
      dimNonSelected={state.guidedStory !== "intro" && state.guidedStory !== "find"}
      interactive
      ariaLabel="舞鶴市の調査地図。地図または一覧から500mの範囲を選べます"
      guidedPresentation={presentation}
      onSelectionChange={onSelectionChange}
      onViewportChange={onViewportChange}
      onAreaHover={onAreaHover}
      onGuidedObjectSelect={onGuidedObjectSelect}
    />
    <div className="guided-map-caption" aria-live="polite">
      <span>{captionLabel}</span>
      <strong>{state.guidedStory === "intro" ? "地域を地図からたどる" : state.guidedStory === "verify" ? target?.label ?? areaLabel : areaLabel}</strong>
      <small>{captionDetail}</small>
    </div>
    {mapLegend && <GuidedContextLegend {...mapLegend} />}
    {state.guidedStory === "understand" && activeSectionData && <div className={`guided-section-dock ${mobileSurface === "section" ? "mobile-visible" : ""}`}>
      <UrbanSection
        open
        mode="guided"
        selection={selectedArea}
        counterfactualState="baseline"
        analysisLens="none"
        dataOverride={activeSectionData}
        expectedPackId={expectedSectionPackId}
        areaLabel={areaLabel}
        onFocusPosition={onSectionFocus}
        onClose={() => undefined}
        onSelectBuilding={() => undefined}
      />
    </div>}
    {state.guidedStory === "understand" && activeSectionData && <div className="guided-mobile-surface-switch" role="group" aria-label="地図と断面の表示">
      <button type="button" aria-pressed={mobileSurface === "map"} onClick={() => onMobileSurfaceChange("map")}>地図</button>
      <button type="button" aria-pressed={mobileSurface === "section"} onClick={() => onMobileSurfaceChange("section")}>街の断面</button>
    </div>}
  </section>;
}
