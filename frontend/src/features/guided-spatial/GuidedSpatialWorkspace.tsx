import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AppData, GeoJsonFeature, GeoJsonFeatureCollection } from "../../types";
import { loadGuidedReferenceData, type GuidedReferenceData } from "../../lib/data";
import type { GuidedStory, SpatialSelection, SpatialState, SpatialViewport } from "../../state/spatial/types";
import { AnalyticalMap } from "../../map/2d/AnalyticalMap";
import { UrbanSection, type SectionData } from "../urban-section/UrbanSection";
import {
  EMPTY_GUIDED_COLLECTION,
  GUIDED_DEFAULT_AREA,
  GUIDED_SHORTLIST,
  exactOrAreaTarget,
  loadGuidedAreaCatalog,
  loadGuidedAreaContext,
  loadGuidedSectionData,
  oneAreaCollection,
} from "./guidedData";
import type { GuidedAreaContext, GuidedAreaContextCatalog, GuidedMapPresentation } from "./guidedTypes";

const MAP_LAYERS = ["reference-gsi-pale", "analysis-city-gap"];
const ROAD_CHECKS = [
  ["walking-passability", "道路を実際に歩いて通行できるか", "PLATEAU道路面は歩行可能性を表さないため。"],
  ["walking-sidewalk", "歩道の有無と有効幅員", "公式歩行ネットワークと歩道属性を収録していないため。"],
  ["walking-crossing", "横断箇所と横断時の見通し", "道路形状だけでは安全な横断可否を判断できないため。"],
  ["walking-building-link", "建物から道路までの接続", "建物と道路の形だけでは入口・私道・階段を特定できないため。"],
] as const;

const BUILDING_CHECKS = [
  ["building-entrance", "建物の入口と道路のつながり", "建物形状からは実際の入口を特定できないため。"],
  ["building-current-use", "建物が現在使われているか", "PLATEAUの用途・形状は現在の利用状況を保証しないため。"],
  ["building-access-barrier", "入口までに段差や通行制限があるか", "公開データだけでは現地の障害を判断できないため。"],
] as const;

const FACILITY_CHECKS = [
  ["facility-open", "施設が現在利用できるか", "登録時点以後の休止・閉鎖を公開データだけでは判断できないため。"],
  ["facility-entrance", "利用者用の入口がどこにあるか", "登録地点は入口位置を示すものではないため。"],
  ["facility-access", "道路から入口まで支障なく移動できるか", "段差・階段・通行制限を収録していないため。"],
] as const;

type GuidedCheck = readonly [string, string, string];

interface GuidedTargetChoice {
  key: string;
  kind: "road" | "building" | "facility" | "area";
  label: string;
  reason: string;
  geometry: GeoJsonFeatureCollection;
  resolution: "exact" | "area_fallback";
  checks: readonly GuidedCheck[];
}

interface GuidedLegendItem {
  label: string;
  symbol: "area" | "candidate" | "building" | "road" | "section" | "target" | "context";
}

function collection(feature: GeoJsonFeature): GeoJsonFeatureCollection {
  return { type: "FeatureCollection", features: [feature] };
}

function labeledTarget(
  geometry: GeoJsonFeatureCollection,
  label: string,
  kind: GuidedTargetChoice["kind"],
): GeoJsonFeatureCollection {
  return {
    type: "FeatureCollection",
    features: geometry.features.map((feature) => ({
      ...feature,
      properties: {
        ...(feature.properties ?? {}),
        map_label: label,
        target_kind: kind,
      },
    })),
  };
}

function collectionBoundsValue(area: GeoJsonFeatureCollection): [number, number, number, number] | null {
  const coordinates: number[][] = [];
  const visit = (value: unknown): void => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") {
      coordinates.push([value[0], value[1]]);
      return;
    }
    value.forEach(visit);
  };
  area.features.forEach((feature) => visit(feature.geometry?.coordinates));
  if (!coordinates.length) return null;
  return [
    Math.min(...coordinates.map(([longitude]) => longitude)),
    Math.min(...coordinates.map(([, latitude]) => latitude)),
    Math.max(...coordinates.map(([longitude]) => longitude)),
    Math.max(...coordinates.map(([, latitude]) => latitude)),
  ];
}

function firstFacilityInArea(data: Pick<GuidedReferenceData, "stations" | "busStops" | "medicalFacilities">, area: GeoJsonFeatureCollection): GeoJsonFeature | null {
  const bounds = collectionBoundsValue(area);
  if (!bounds) return null;
  const [west, south, east, north] = bounds;
  const sources = [data.stations, data.busStops, data.medicalFacilities];
  return sources.flatMap((source) => source?.features ?? []).find((feature) => {
    const coordinates = feature.geometry?.type === "Point" ? feature.geometry.coordinates : null;
    return Array.isArray(coordinates)
      && typeof coordinates[0] === "number"
      && typeof coordinates[1] === "number"
      && coordinates[0] >= west && coordinates[0] <= east
      && coordinates[1] >= south && coordinates[1] <= north;
  }) ?? null;
}

function meshSelection(data: AppData, meshCode: string): SpatialSelection | null {
  const feature = data.meshes.features.find((candidate) => String(candidate.properties?.mesh_code) === meshCode);
  if (!feature?.properties) return null;
  return {
    type: "mesh",
    id: meshCode,
    city: "maizuru",
    urbanState: "2025",
    label: meshCode === GUIDED_DEFAULT_AREA
      ? "常団地前周辺"
      : String(feature.properties.area_label ?? `500mメッシュ ${meshCode}`),
    longitude: Number(feature.properties.centroid_lon),
    latitude: Number(feature.properties.centroid_lat),
    properties: feature.properties,
  };
}

function number(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatDistance(value: unknown): string {
  const parsed = number(value);
  if (parsed === null) return "データなし";
  return parsed >= 1000 ? `${(parsed / 1000).toFixed(2)}km` : `${Math.round(parsed)}m`;
}

function sectionCollections(data: SectionData | null, focus: { longitude: number; latitude: number } | null) {
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
        <p role="status">舞鶴市の500m範囲を読み込んでいます</p>
      </section>
      <aside className="guided-story-panel">
        <div className="guided-intro">
          <h1>舞鶴の地域を、<br />地図からたどる。</h1>
          <p>地域を選び、街の形と、データだけでは判断できない場所を地図でたどります。</p>
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
}: Props) {
  const [catalog, setCatalog] = useState<GuidedAreaContextCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [context, setContext] = useState<GuidedAreaContext | null>(null);
  const [contextStatus, setContextStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [contextError, setContextError] = useState<string | null>(null);
  const [hoveredAreaId, setHoveredAreaId] = useState<string | null>(null);
  const [sectionData, setSectionData] = useState<SectionData | null>(null);
  const [sectionError, setSectionError] = useState<string | null>(null);
  const [sectionFocus, setSectionFocus] = useState<{ longitude: number; latitude: number } | null>(null);
  const [mobileSurface, setMobileSurface] = useState<"map" | "section">("map");
  const [selectedTargetKey, setSelectedTargetKey] = useState<string | null>(null);
  const [referenceData, setReferenceData] = useState<GuidedReferenceData | null>(() => (
    data.stations || data.busStops || data.medicalFacilities
      ? { stations: data.stations, busStops: data.busStops, medicalFacilities: data.medicalFacilities, warnings: [] }
      : null
  ));
  const requestSequence = useRef(0);
  const contextCache = useRef(new Map<string, GuidedAreaContext>());
  const activeContextRef = useRef<GuidedAreaContext | null>(null);
  const sectionDataRef = useRef<SectionData | null>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  const validSelectedArea = state.selection?.type === "mesh"
    && data.meshes.features.some((feature) => String(feature.properties?.mesh_code) === state.selection?.id)
    ? state.selection.id
    : null;
  const selectedAreaId = validSelectedArea ?? GUIDED_DEFAULT_AREA;
  const selectedArea = useMemo(() => meshSelection(data, selectedAreaId), [data, selectedAreaId]);
  const selectedAreaFeature = useMemo(() => oneAreaCollection(data.meshes, selectedAreaId), [data.meshes, selectedAreaId]);
  const properties = selectedArea?.properties ?? {};
  const activeContext = context?.mesh_code === selectedAreaId ? context : null;

  useEffect(() => {
    const controller = new AbortController();
    loadGuidedAreaCatalog(controller.signal)
      .then(setCatalog)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setCatalogError(reason instanceof Error ? reason.message : "Area catalogを読み込めません");
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (state.guidedStory === "intro" || state.guidedStory === "find" || referenceData) return;
    let cancelled = false;
    loadGuidedReferenceData(fetch, import.meta.env.BASE_URL)
      .then((value) => { if (!cancelled) setReferenceData(value); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [referenceData, state.guidedStory]);

  useEffect(() => {
    if (validSelectedArea || !selectedArea) return;
    onSelectionChange(selectedArea);
  }, [onSelectionChange, selectedArea, validSelectedArea]);

  useEffect(() => {
    const item = catalog?.items.find((candidate) => candidate.mesh_code === selectedAreaId);
    const sequence = ++requestSequence.current;
    setContextError(null);
    if (activeContextRef.current?.mesh_code !== selectedAreaId) {
      activeContextRef.current = null;
      sectionDataRef.current = null;
      setContext(null);
      setSectionData(null);
      setSectionError(null);
      setSectionFocus(null);
      setMobileSurface("map");
      setSelectedTargetKey(null);
    }
    if (state.guidedStory === "intro" || state.guidedStory === "find") {
      setContextStatus("idle");
      return;
    }
    if (activeContextRef.current?.mesh_code === selectedAreaId) {
      setContextStatus("ready");
      return;
    }
    if (!item) {
      setContextStatus(catalog ? "error" : "idle");
      if (catalog) setContextError("選択した範囲のPLATEAUデータを確認できません");
      return;
    }
    const cached = contextCache.current.get(selectedAreaId);
    if (cached) {
      activeContextRef.current = cached;
      setContext(cached);
      setContextStatus("ready");
      return;
    }
    const controller = new AbortController();
    setContextStatus("loading");
    loadGuidedAreaContext(item, controller.signal)
      .then((value) => {
        if (requestSequence.current !== sequence) return;
        contextCache.current.set(selectedAreaId, value);
        activeContextRef.current = value;
        setContext(value);
        setContextStatus("ready");
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted || requestSequence.current !== sequence) return;
        setContextStatus("error");
        setContextError(reason instanceof Error ? reason.message : "範囲のPLATEAUデータを読み込めません");
      });
    return () => controller.abort();
  }, [catalog, selectedAreaId, state.guidedStory]);

  useEffect(() => {
    setSectionError(null);
    if (state.guidedStory !== "understand" || activeContext?.section.status !== "available") return;
    if (sectionDataRef.current?.pack_id === activeContext.section.pack_id) {
      setSectionData(sectionDataRef.current);
      return;
    }
    setSectionData(null);
    setSectionFocus(null);
    const controller = new AbortController();
    loadGuidedSectionData(activeContext.section, controller.signal)
      .then((value) => {
        sectionDataRef.current = value;
        setSectionData(value);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setSectionError(reason instanceof Error ? reason.message : "断面を読み込めません");
      });
    return () => controller.abort();
  }, [activeContext, state.guidedStory]);

  useEffect(() => {
    titleRef.current?.focus();
  }, [state.guidedStory]);

  const selectedCatalogItem = catalog?.items.find((candidate) => candidate.mesh_code === selectedAreaId) ?? null;
  const areaLabel = selectedArea?.label ?? `500mメッシュ ${selectedAreaId}`;
  const shortlisted = GUIDED_SHORTLIST.map((meshCode) => meshSelection(data, meshCode)).filter((item): item is SpatialSelection => Boolean(item));
  const targetChoices = useMemo<GuidedTargetChoice[]>(() => {
    const choices: GuidedTargetChoice[] = [];
    const defaultTarget = exactOrAreaTarget(activeContext, selectedAreaFeature);
    if (defaultTarget.resolution === "exact" && defaultTarget.geometry.features[0]) {
      choices.push({
        key: `road:${String(defaultTarget.geometry.features[0].id ?? GUIDED_DEFAULT_AREA)}`,
        kind: "road",
        label: "京月中央通線の道路面",
        reason: "通れない区間があれば、直線距離による候補判断が変わります。",
        geometry: defaultTarget.geometry,
        resolution: "exact",
        checks: ROAD_CHECKS,
      });
    }
    const building = activeContext?.layers.buildings.features[0];
    if (building) choices.push({
      key: `building:${String(building.id ?? building.properties?.object_id)}`,
      kind: "building",
      label: "範囲内のPLATEAU建物",
      reason: "建物の形が分かっても、入口と現在の利用状況はデータだけでは判断できません。",
      geometry: collection(building),
      resolution: "exact",
      checks: BUILDING_CHECKS,
    });
    const facility = firstFacilityInArea(referenceData ?? data, selectedAreaFeature);
    if (facility) choices.push({
      key: `facility:${String(facility.id ?? facility.properties?.id)}`,
      kind: "facility",
      label: String(facility.properties?.name ?? "範囲内の登録施設"),
      reason: "登録地点が分かっても、現在の利用可否や入口まではデータだけでは判断できません。",
      geometry: collection(facility),
      resolution: "exact",
      checks: FACILITY_CHECKS,
    });
    const areaChoice: GuidedTargetChoice = {
      key: `area:${selectedAreaId}`,
      kind: "area",
      label: `${areaLabel}の500m範囲`,
      reason: "個別対象を根拠付きで解決できない場合は、別地域の対象で補わず選択範囲を示します。",
      geometry: selectedAreaFeature,
      resolution: "area_fallback",
      checks: ROAD_CHECKS,
    };
    if (choices[0]?.kind === "road") choices.push(areaChoice);
    else choices.unshift(areaChoice);
    return choices;
  }, [activeContext, areaLabel, data, referenceData, selectedAreaFeature, selectedAreaId]);
  const target = targetChoices.find((choice) => choice.key === selectedTargetKey) ?? targetChoices[0];
  const mapTarget = useMemo(
    () => target ? labeledTarget(target.geometry, target.label, target.kind) : EMPTY_GUIDED_COLLECTION,
    [target],
  );
  const activeSectionData = activeContext?.section.pack_id === sectionData?.pack_id ? sectionData : null;
  const section = useMemo(() => sectionCollections(activeSectionData, sectionFocus), [activeSectionData, sectionFocus]);
  const presentation = useMemo<GuidedMapPresentation>(() => ({
    story: state.guidedStory,
    area: selectedAreaFeature,
    areaId: selectedAreaId,
    hoveredAreaId,
    context: activeContext,
    contextStatus,
    target: mapTarget,
    targetKind: target?.kind ?? "area",
    targetResolution: target?.resolution ?? "area_fallback",
    sectionLine: section.line,
    sectionFocus: section.point,
    shortlistIds: [...GUIDED_SHORTLIST],
  }), [activeContext, contextStatus, hoveredAreaId, mapTarget, section.line, section.point, selectedAreaFeature, selectedAreaId, state.guidedStory, target?.kind, target?.resolution]);
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
        { label: target?.resolution === "exact" ? "選んだ対象" : "確認する範囲", symbol: target?.resolution === "exact" ? "target" : "area" },
        { label: "選んだ地域", symbol: "context" },
      ],
    };
    return null;
  }, [activeSectionData, state.guidedStory, target?.resolution]);

  const selectArea = useCallback((meshCode: string) => {
    const selection = meshSelection(data, meshCode);
    if (!selection) return;
    onSelectionChange(selection);
    if (selection.longitude !== undefined && selection.latitude !== undefined) {
      onViewportChange({ longitude: selection.longitude, latitude: selection.latitude, zoom: 12.4, bearing: 0, pitch: 0 });
    }
  }, [data, onSelectionChange, onViewportChange]);
  const handleMapSelection = useCallback((selection: SpatialSelection | null) => {
    if (selection?.type === "mesh") selectArea(selection.id);
  }, [selectArea]);
  const handleViewport = useCallback((viewport: SpatialViewport) => onViewportChange(viewport), [onViewportChange]);
  const handleMapHover = useCallback((meshCode: string | null) => setHoveredAreaId(meshCode), []);
  const handleGuidedObjectSelect = useCallback((kind: "building" | "road", objectId: string) => {
    if (state.guidedStory !== "verify") return;
    const choice = targetChoices.find((candidate) => candidate.kind === kind && candidate.key.includes(objectId));
    if (choice) setSelectedTargetKey(choice.key);
  }, [state.guidedStory, targetChoices]);

  return <div
    className="guided-spatial-app"
    data-guided-story={state.guidedStory}
    data-area-id={selectedAreaId}
    data-area-label={areaLabel}
    data-hovered-area-id={hoveredAreaId ?? "none"}
    data-area-geometry-hash={selectedCatalogItem?.area_geometry_sha256 ?? "pending"}
    data-context-hash={selectedCatalogItem?.context_sha256 ?? "pending"}
    data-source-hash={catalog?.source.sha256 ?? "pending"}
    data-section-hash={activeContext?.section.sha256 ?? "none"}
    data-context-status={contextStatus}
    data-context-buildings={context?.layers.buildings.features.length ?? 0}
    data-context-roads={context?.layers.roads.features.length ?? 0}
    data-context-planning={context?.layers.planning.features.length ?? 0}
    data-section-pack={activeSectionData?.pack_id ?? "none"}
    data-target-resolution={target?.resolution ?? "area_fallback"}
    data-target-kind={target?.kind ?? "area"}
    data-target-key={target?.key ?? "none"}
  >
    <header className="guided-spatial-header">
      <button type="button" className="guided-brand" onClick={onRestart}>CITY GAP</button>
      <span>舞鶴市</span>
      <button type="button" className="guided-advanced-link" onClick={onOpenAdvanced}>詳細分析</button>
    </header>
    <main className="guided-spatial-workspace">
      <section className="guided-map-stage" aria-label="舞鶴市の調査範囲とPLATEAU表示">
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
          onSelectionChange={handleMapSelection}
          onViewportChange={handleViewport}
          onAreaHover={handleMapHover}
          onGuidedObjectSelect={handleGuidedObjectSelect}
        />
        <div className="guided-map-caption" aria-live="polite">
          <span>{state.guidedStory === "intro" ? "舞鶴市全域" : state.guidedStory === "find" ? "地域を選ぶ" : state.guidedStory === "understand" ? "街の形" : "確認する場所"}</span>
          <strong>{state.guidedStory === "intro" ? "地域を地図からたどる" : state.guidedStory === "verify" ? target?.label ?? areaLabel : areaLabel}</strong>
          <small>{state.guidedStory === "intro" ? "495の500m範囲から調べる地域を選べます" : state.guidedStory === "find" ? "選んだ500m範囲" : state.guidedStory === "understand" ? "PLATEAU 舞鶴市2025" : target?.resolution === "exact" ? `実在する${target.kind === "road" ? "PLATEAU道路面" : target.kind === "building" ? "PLATEAU建物" : "登録地点"}` : "個別対象は未解決・選んだ範囲で確認"}</small>
        </div>
        {mapLegend && <aside className="guided-context-legend" aria-label={mapLegend.title}>
          <strong>{mapLegend.title}</strong>
          <div>{mapLegend.items.map((item) => <span key={item.label}><i className={`symbol-${item.symbol}`} aria-hidden="true" />{item.label}</span>)}</div>
        </aside>}
        {state.guidedStory === "understand" && activeSectionData && <div className={`guided-section-dock ${mobileSurface === "section" ? "mobile-visible" : ""}`}>
          <UrbanSection
            open
            mode="guided"
            selection={selectedArea}
            counterfactualState="baseline"
            analysisLens="none"
            dataOverride={activeSectionData}
            expectedPackId={activeContext?.section.pack_id}
            areaLabel={areaLabel}
            onFocusPosition={setSectionFocus}
            onClose={() => undefined}
            onSelectBuilding={() => undefined}
          />
        </div>}
        {state.guidedStory === "understand" && activeSectionData && <div className="guided-mobile-surface-switch" role="group" aria-label="地図と断面の表示">
          <button type="button" aria-pressed={mobileSurface === "map"} onClick={() => setMobileSurface("map")}>地図</button>
          <button type="button" aria-pressed={mobileSurface === "section"} onClick={() => setMobileSurface("section")}>街の断面</button>
        </div>}
      </section>

      <aside className="guided-story-panel" aria-labelledby="guided-story-title" data-inspector-story={state.guidedStory}>
        {catalogError && <p role="alert" className="guided-error">{catalogError}</p>}
        {state.guidedStory === "intro" && <div className="guided-intro">
          <h1 id="guided-story-title" ref={titleRef} tabIndex={-1}>舞鶴の地域を、<br />地図からたどる。</h1>
          <p>地域を選び、街の形と、データだけでは判断できない場所を地図でたどります。</p>
          <button type="button" className="guided-primary" onClick={() => onStoryChange("find")}>地域を選ぶ</button>
        </div>}
        {state.guidedStory === "find" && <div className="guided-scene-content">
          <div className="guided-panel-kicker"><span className="guided-eyebrow">地域を選ぶ</span></div>
          <h1 id="guided-story-title" ref={titleRef} tabIndex={-1}>どの地域を詳しく見る？</h1>
          <p className="guided-scene-lead">地域を選ぶと、人口・交通・医療の情報と街の形をたどれます。</p>
          <label className="guided-area-select">選んだ地域
            <select aria-label="495の範囲から選ぶ" value={selectedAreaId} onChange={(event) => selectArea(event.target.value)}>
              {data.meshes.features.map((feature) => {
                const meshCode = String(feature.properties?.mesh_code ?? "");
                const label = meshCode === GUIDED_DEFAULT_AREA ? "常団地前周辺" : String(feature.properties?.area_label ?? `500mメッシュ ${meshCode}`);
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
              onClick={() => selectArea(area.id)}
              onPointerEnter={() => setHoveredAreaId(area.id)}
              onPointerLeave={() => setHoveredAreaId(null)}
              onFocus={() => setHoveredAreaId(area.id)}
              onBlur={() => setHoveredAreaId(null)}
            ><strong>{area.label}</strong><span>65歳以上 {Math.round(number(area.properties?.elderly_population) ?? 0).toLocaleString("ja-JP")}人 · 交通 {formatDistance(area.properties?.nearest_public_transport_distance_m)} · 医療 {formatDistance(area.properties?.nearest_medical_distance_m)}</span></button>)}
          </div>
          <button type="button" className="guided-primary" onClick={() => onStoryChange("understand")}>街の形を見る</button>
        </div>}

        {state.guidedStory === "understand" && <div className="guided-scene-content">
          <div className="guided-panel-kicker">
            <button type="button" className="guided-back" onClick={() => onStoryChange("find")}>範囲選択へ戻る</button>
            <span className="guided-eyebrow">データから見える地域の姿</span>
          </div>
          <h1 id="guided-story-title" ref={titleRef} tabIndex={-1}>{areaLabel}の地形と建物</h1>
          <dl className="guided-known-summary">
            <div><dt>人口 {Math.round(number(properties.population) ?? 0).toLocaleString("ja-JP")}人</dt><dd>うち65歳以上 {Math.round(number(properties.elderly_population) ?? 0).toLocaleString("ja-JP")}人（国勢調査2020）</dd></div>
            <div><dt>街の形</dt><dd>範囲と交差するPLATEAU建物 {selectedCatalogItem?.counts.buildings.toLocaleString("ja-JP") ?? "—"}棟・道路面 {selectedCatalogItem?.counts.roads.toLocaleString("ja-JP") ?? "—"}件</dd></div>
            <div><dt>都市計画・交通</dt><dd>範囲と交差する公式の都市計画形状 {selectedCatalogItem?.counts.planning.toLocaleString("ja-JP") ?? "—"}件・収録駅/バス停まで直線 {formatDistance(properties.nearest_public_transport_distance_m)}</dd></div>
          </dl>
          {contextStatus === "loading" && <p role="status" className="guided-loading">選択した範囲のPLATEAU建物・道路を読み込んでいます</p>}
          {contextError && <p role="alert" className="guided-error">{contextError}</p>}
          {activeSectionData ? <p className="guided-section-note">地図上のA–B線を横から見た断面です。</p>
            : sectionError ? <p className="guided-boundary">断面は読み込めません。範囲内の建物・道路・都市計画は引き続き確認できます。</p>
              : <p className="guided-boundary">{context?.section.reason?.replaceAll("Area", "範囲") ?? "この範囲では検証済みの街の断面を表示していません。"}</p>}
          <div className="guided-unknown-bridge">
            <span>まだ分からないこと</span>
            <strong>形が見えても、実際の歩きやすさまでは判断できません。</strong>
            <p>PLATEAU道路面は、歩道・横断・入口や、実際に人が通れることを確認した経路データではないためです。</p>
          </div>
          <button type="button" className="guided-primary" onClick={() => onStoryChange("verify")}>確認場所を見る</button>
        </div>}

        {state.guidedStory === "verify" && <div className="guided-scene-content">
          <div className="guided-panel-kicker">
            <button type="button" className="guided-back" onClick={() => onStoryChange("understand")}>街の形へ戻る</button>
            <span className="guided-eyebrow">データだけでは判断できないこと</span>
          </div>
          <h1 id="guided-story-title" ref={titleRef} tabIndex={-1}>ここで何を確かめる？</h1>
          {targetChoices.length > 1 && <label className="guided-target-select">確認対象
            <select value={target?.key} onChange={(event) => setSelectedTargetKey(event.target.value)}>
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
          <p className="guided-boundary">回答や確認結果はまだありません。</p>
          <button type="button" className="guided-secondary-action" onClick={onOpenAdvanced}>詳細な調査票を見る</button>
        </div>}
      </aside>
    </main>
  </div>;
}
