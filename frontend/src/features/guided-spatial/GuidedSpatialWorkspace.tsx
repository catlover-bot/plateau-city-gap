import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AppData, GeoJsonFeatureCollection } from "../../types";
import type { GuidedStory, SpatialSelection, SpatialState, SpatialViewport } from "../../state/spatial/types";
import type { SectionData } from "../urban-section/sectionTypes";
import { EMPTY_GUIDED_COLLECTION, GUIDED_SHORTLIST } from "./guidedData";
import { GUIDED_CONTENT } from "./guidedContent";
import { GuidedInspector } from "./GuidedInspector";
import { GuidedMapStage } from "./GuidedMapStage";
import { buildGuidedTargetChoices, labeledGuidedTarget } from "./guidedTargets";
import type { GuidedMapPresentation } from "./guidedTypes";
import { useGuidedAreaContext } from "./useGuidedAreaContext";
import { useGuidedSelection } from "./useGuidedSelection";
import { guidedObjectFeature, guidedObjectTarget, selectionFromGuidedTarget, supportsGuided3D } from "./guided3d";

function sectionCollections(
  data: SectionData | null,
  focus: { longitude: number; latitude: number } | null,
) {
  const line: GeoJsonFeatureCollection = data ? {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        id: data.transect_id,
        properties: { transect_id: data.transect_id, pack_id: data.pack_id },
        geometry: data.geometry,
      },
      {
        type: "Feature",
        id: `${data.transect_id}:A`,
        properties: { endpoint: "A", pack_id: data.pack_id },
        geometry: { type: "Point", coordinates: data.geometry.coordinates[0] },
      },
      {
        type: "Feature",
        id: `${data.transect_id}:B`,
        properties: { endpoint: "B", pack_id: data.pack_id },
        geometry: { type: "Point", coordinates: data.geometry.coordinates[data.geometry.coordinates.length - 1] },
      },
    ],
  } : EMPTY_GUIDED_COLLECTION;
  const point: GeoJsonFeatureCollection = focus ? {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      properties: { role: "section_focus" },
      geometry: { type: "Point", coordinates: [focus.longitude, focus.latitude] },
    }],
  } : EMPTY_GUIDED_COLLECTION;
  return { line, point };
}

interface Props {
  data: AppData;
  state: SpatialState;
  onStoryChange(story: GuidedStory): void;
  onSelectionChange(selection: SpatialSelection | null): void;
  onViewportChange(viewport: SpatialViewport): void;
  onMapModeChange(mode: "map2d" | "plateau3d"): void;
  onRestart(): void;
  onOpenAdvanced(): void;
}

export function GuidedSpatialLoadingWorkspace() {
  return <div
    className="guided-spatial-app"
    data-guided-story="intro"
    data-context-status="loading"
    aria-busy="true"
  >
    <header className="guided-spatial-header">
      <span className="guided-brand">CITY GAP</span>
      <span>舞鶴市</span>
    </header>
    <main className="guided-spatial-workspace">
      <section className="guided-map-stage guided-map-skeleton" aria-label="舞鶴市の地図を準備中">
        <div className="guided-map-skeleton-grid" aria-hidden="true" />
        <p role="status">{GUIDED_CONTENT.loading.map}</p>
      </section>
      <aside className="guided-story-panel">
        <div className="guided-intro">
          <h1>{GUIDED_CONTENT.intro.titleFirstLine}<br />{GUIDED_CONTENT.intro.titleSecondLine}</h1>
          <p>{GUIDED_CONTENT.intro.description}</p>
        </div>
      </aside>
    </main>
  </div>;
}

export function GuidedSpatialWorkspace({
  data,
  state,
  onStoryChange,
  onSelectionChange,
  onViewportChange,
  onRestart,
  onOpenAdvanced,
  onMapModeChange,
}: Props) {
  const [hoveredAreaId, setHoveredAreaId] = useState<string | null>(null);
  const [sectionFocus, setSectionFocus] = useState<{ longitude: number; latitude: number } | null>(null);
  const [mobileSurface, setMobileSurface] = useState<"map" | "section">("map");
  const [selectedTargetKey, setSelectedTargetKey] = useState<string | null>(null);
  const [selectedObject, setSelectedObject] = useState<SpatialSelection | null>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  const selection = useGuidedSelection({ data, state, onSelectionChange, onViewportChange });
  const areaContext = useGuidedAreaContext(data, state.guidedStory, selection.selectedAreaId);

  useEffect(() => {
    setSectionFocus(null);
    setMobileSurface("map");
    setSelectedTargetKey(null);
    setSelectedObject(null);
  }, [selection.selectedAreaId]);

  useEffect(() => {
    titleRef.current?.focus();
  }, [state.guidedStory]);

  const selectedCatalogItem = areaContext.catalog?.items.find(
    (candidate) => candidate.mesh_code === selection.selectedAreaId,
  ) ?? null;
  const activeObject = selectedObject?.properties?.parent_mesh_code === selection.selectedAreaId ? selectedObject : null;
  const targetChoices = useMemo(() => {
    const choices = buildGuidedTargetChoices({
    activeContext: areaContext.activeContext,
    area: selection.selectedAreaFeature,
    areaId: selection.selectedAreaId,
    areaLabel: selection.areaLabel,
    data,
    referenceData: areaContext.referenceData,
    });
    const pickedTarget = guidedObjectTarget(activeObject, areaContext.activeContext);
    if (pickedTarget && !choices.some((choice) => choice.key === pickedTarget.key)) choices.push(pickedTarget);
    return choices;
  }, [
    activeObject,
    areaContext.activeContext,
    areaContext.referenceData,
    data,
    selection.areaLabel,
    selection.selectedAreaFeature,
    selection.selectedAreaId,
  ]);
  const target = targetChoices.find((choice) => choice.key === selectedTargetKey) ?? targetChoices[0];
  const mapTarget = useMemo(() => labeledGuidedTarget(target), [target]);
  const activeSectionData = areaContext.activeContext?.section.pack_id === areaContext.sectionData?.pack_id
    ? areaContext.sectionData
    : null;
  const section = useMemo(
    () => sectionCollections(activeSectionData, sectionFocus),
    [activeSectionData, sectionFocus],
  );
  const presentation = useMemo<GuidedMapPresentation>(() => ({
    story: state.guidedStory,
    area: selection.selectedAreaFeature,
    areaId: selection.selectedAreaId,
    hoveredAreaId,
    context: areaContext.activeContext,
    contextStatus: areaContext.contextStatus,
    target: mapTarget,
    targetKind: target?.kind ?? "area",
    targetResolution: target?.resolution ?? "area_fallback",
    showObjectSelection: Boolean(activeObject),
    sectionLine: section.line,
    sectionFocus: section.point,
    shortlistIds: [...GUIDED_SHORTLIST],
  }), [
    areaContext.activeContext,
    areaContext.contextStatus,
    hoveredAreaId,
    mapTarget,
    section.line,
    section.point,
    selection.selectedAreaFeature,
    selection.selectedAreaId,
    state.guidedStory,
    target?.kind,
    target?.resolution,
    activeObject,
  ]);

  const selectObject = useCallback((object: SpatialSelection | null) => {
    if (!object || (object.type !== "building" && object.type !== "road")) return;
    if (!guidedObjectFeature(areaContext.activeContext, object.type, object.id)) return;
    const ownedObject = { ...object, properties: { ...object.properties, parent_mesh_code: selection.selectedAreaId } };
    setSelectedObject(ownedObject);
    const picked = guidedObjectTarget(ownedObject, areaContext.activeContext);
    if (picked) setSelectedTargetKey(picked.key);
  }, [areaContext.activeContext, selection.selectedAreaId]);
  const selectTarget = useCallback((key: string) => {
    setSelectedTargetKey(key);
    const choice = targetChoices.find((item) => item.key === key);
    setSelectedObject(choice && selection.selectedArea ? selectionFromGuidedTarget(choice, selection.selectedArea) : null);
  }, [selection.selectedArea, targetChoices]);
  const handleGuidedObjectSelect = useCallback((kind: "building" | "road", objectId: string) => {
    if (state.guidedStory !== "verify" && state.guidedStory !== "understand") return;
    const feature = guidedObjectFeature(areaContext.activeContext, kind, objectId);
    if (feature && selection.selectedArea) {
      selectObject({ ...selection.selectedArea, type: kind, id: String(feature.id ?? objectId), properties: { ...feature.properties, parent_mesh_code: selection.selectedAreaId } });
      return;
    }
    const choice = targetChoices.find((candidate) => candidate.kind === kind && candidate.key.includes(objectId));
    if (choice) setSelectedTargetKey(choice.key);
  }, [state.guidedStory, targetChoices, areaContext.activeContext, selection.selectedArea, selection.selectedAreaId, selectObject]);
  const threeDSupported = supportsGuided3D(selection.selectedAreaId, areaContext.activeContext);

  return <div
    className="guided-spatial-app"
    data-guided-story={state.guidedStory}
    data-area-id={selection.selectedAreaId}
    data-area-label={selection.areaLabel}
    data-hovered-area-id={hoveredAreaId ?? "none"}
    data-area-geometry-hash={selectedCatalogItem?.area_geometry_sha256 ?? "pending"}
    data-context-hash={selectedCatalogItem?.context_sha256 ?? "pending"}
    data-source-hash={areaContext.catalog?.source.sha256 ?? "pending"}
    data-section-hash={areaContext.activeContext?.section.sha256 ?? "none"}
    data-context-status={areaContext.contextStatus}
    data-context-buildings={areaContext.context?.layers.buildings.features.length ?? 0}
    data-context-roads={areaContext.context?.layers.roads.features.length ?? 0}
    data-context-planning={areaContext.context?.layers.planning.features.length ?? 0}
    data-section-pack={activeSectionData?.pack_id ?? "none"}
    data-target-resolution={target?.resolution ?? "area_fallback"}
    data-target-kind={target?.kind ?? "area"}
    data-target-key={target?.key ?? "none"}
    data-object-kind={activeObject?.type ?? "none"}
    data-object-id={activeObject?.id ?? "none"}
  >
    <header className="guided-spatial-header">
      <button type="button" className="guided-brand" onClick={onRestart}>CITY GAP</button>
      <span>舞鶴市</span>
      <button type="button" className="guided-advanced-link" onClick={onOpenAdvanced}>詳細分析</button>
    </header>
    <main className="guided-spatial-workspace">
      <GuidedMapStage
        data={data}
        state={state}
        selectedArea={selection.selectedArea}
        areaLabel={selection.areaLabel}
        presentation={presentation}
        target={target}
        activeSectionData={activeSectionData}
        expectedSectionPackId={areaContext.activeContext?.section.pack_id}
        mobileSurface={mobileSurface}
        onMobileSurfaceChange={setMobileSurface}
        onSelectionChange={selection.selectAreaFromMap}
        onViewportChange={onViewportChange}
        onAreaHover={setHoveredAreaId}
        onGuidedObjectSelect={handleGuidedObjectSelect}
        onSectionFocus={setSectionFocus}
        sectionFocus={sectionFocus}
        selectedObject={activeObject}
        threeDSupported={threeDSupported}
        onMapModeChange={onMapModeChange}
        onObjectSelect={selectObject}
      />
      <GuidedInspector
        story={state.guidedStory}
        data={data}
        titleRef={titleRef}
        selectedAreaId={selection.selectedAreaId}
        areaLabel={selection.areaLabel}
        properties={selection.properties}
        shortlisted={selection.shortlisted}
        hoveredAreaId={hoveredAreaId}
        catalogItem={selectedCatalogItem}
        catalogError={areaContext.catalogError}
        contextStatus={areaContext.contextStatus}
        contextError={areaContext.contextError}
        context={areaContext.activeContext}
        activeSectionData={activeSectionData}
        sectionError={areaContext.sectionError}
        targetChoices={targetChoices}
        target={target}
        onStoryChange={onStoryChange}
        onSelectArea={selection.selectArea}
        onAreaHover={setHoveredAreaId}
        onTargetChange={selectTarget}
        onOpenAdvanced={onOpenAdvanced}
        selectedObject={activeObject}
        threeDActive={state.mapMode === "plateau3d" && threeDSupported}
      />
    </main>
  </div>;
}
