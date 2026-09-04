import { useEffect, useMemo, useState, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import type { AnalysisLens, CounterfactualState, SpatialSelection } from "../../state/spatial/types";
import {
  browserSectionTextMeasurer,
  layoutSectionAnnotations,
  type SectionAnnotationLayout,
} from "./sectionAnnotations";

interface TerrainSample {
  sample_order: number;
  distance_m: number;
  longitude: number;
  latitude: number;
  elevation_m: number | null;
  source_triangle_id: string | null;
  quality: "direct_tin" | "boundary" | "no_coverage";
}

interface SectionRelation {
  source_object_id: string;
  relation: "direct" | "nearby";
  start_distance_m: number;
  end_distance_m: number;
  offset_distance_m: number;
  properties: Record<string, unknown>;
}

interface SectionBand {
  source_object_id: string;
  start_distance_m: number;
  end_distance_m: number;
  planning?: Record<string, unknown>;
  hazards?: Array<Record<string, unknown>>;
}

export interface SectionData {
  transect_id: string;
  pack_id: string;
  geometry: { type: "LineString"; coordinates: Array<[number, number]> };
  buffer_m: number;
  sample_interval_m: number;
  vertical_datum: string;
  terrain_source: string;
  terrain_interpolation: string;
  terrain_samples: TerrainSample[];
  buildings: SectionRelation[];
  roads: SectionRelation[];
  service_locations: SectionRelation[];
  scenario_sites: SectionRelation[];
  counterfactual: {
    plan_id: string;
    building_group_count: number;
    baseline: { distance_m: number; score_c: number };
    scenario: { distance_m: number; score_c: number; distance_reduction_m: number; score_c_reduction: number };
    distance_semantics: string;
    geometry_policy: string;
    limitations: string[];
  };
  planning_bands: SectionBand[];
  hazard_bands: SectionBand[];
}

const PACK_ID = "maizuru-533513314-plateau-2025-v1";
const VIEW_WIDTH = 1000;
const TERRAIN_TOP = 32;
const TERRAIN_BOTTOM = 174;

function publicUrl(path: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`;
  return `${base}${path}`;
}

interface TerrainSegment {
  line: string;
  area: string;
}

function terrainSegments(samples: TerrainSample[], x: (value: number) => number, y: (value: number) => number): TerrainSegment[] {
  const segments: TerrainSegment[] = [];
  let current: Array<[number, number]> = [];
  const finish = () => {
    if (current.length > 1) {
      const line = current.map(([pointX, pointY], index) => `${index ? "L" : "M"}${pointX.toFixed(2)},${pointY.toFixed(2)}`).join(" ");
      const first = current[0];
      const last = current[current.length - 1];
      segments.push({ line, area: `${line} L${last[0].toFixed(2)},${TERRAIN_BOTTOM} L${first[0].toFixed(2)},${TERRAIN_BOTTOM} Z` });
    }
    current = [];
  };
  samples.forEach((sample) => {
    if (sample.elevation_m === null) {
      finish();
      return;
    }
    current.push([x(sample.distance_m), y(sample.elevation_m)]);
  });
  finish();
  return segments;
}

interface SectionFocusDetail {
  id: string;
  kind: "building" | "road";
  kindLabel: "建物" | "道路";
  label: string;
  distanceM: number;
  elevationM: number | null;
  relation: SectionRelation["relation"];
  offsetDistanceM: number;
}

function distanceFromRelation(relation: SectionRelation, distanceM: number): number {
  if (distanceM < relation.start_distance_m) return relation.start_distance_m - distanceM;
  if (distanceM > relation.end_distance_m) return distanceM - relation.end_distance_m;
  return 0;
}

function nearestSectionObject(data: SectionData, distanceM: number, elevationM: number | null): SectionFocusDetail | null {
  const candidates = [
    ...data.buildings.map((relation) => ({ relation, kind: "building" as const })),
    ...data.roads.map((relation) => ({ relation, kind: "road" as const })),
  ];
  candidates.sort((left, right) => (
    distanceFromRelation(left.relation, distanceM) - distanceFromRelation(right.relation, distanceM)
    || Number(right.relation.relation === "direct") - Number(left.relation.relation === "direct")
    || left.relation.start_distance_m - right.relation.start_distance_m
  ));
  const nearest = candidates[0];
  if (!nearest) return null;
  const relation = nearest.relation;
  return {
    id: relation.source_object_id,
    kind: nearest.kind,
    kindLabel: nearest.kind === "road" ? "道路" : "建物",
    label: nearest.kind === "road"
      ? String(relation.properties.road_name ?? "名称不明の道路")
      : String(relation.properties.usage_label ?? relation.properties.usage ?? "用途不明の建物"),
    distanceM: (relation.start_distance_m + relation.end_distance_m) / 2,
    elevationM,
    relation: relation.relation,
    offsetDistanceM: relation.offset_distance_m,
  };
}

interface Props {
  open: boolean;
  mode?: "advanced" | "guided";
  selection: SpatialSelection | null;
  counterfactualState: CounterfactualState;
  analysisLens: AnalysisLens;
  onSelectBuilding(id: string, properties: Record<string, unknown>): void;
  onClose(): void;
  dataOverride?: SectionData | null;
  sourcePath?: string | null;
  expectedPackId?: string;
  areaLabel?: string;
  onFocusPosition?(position: { longitude: number; latitude: number } | null): void;
}

function moveSectionFocus(event: ReactKeyboardEvent<SVGRectElement>) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  const objects = Array.from(event.currentTarget.parentElement?.querySelectorAll<SVGRectElement>("[data-section-building]") ?? []);
  const index = objects.indexOf(event.currentTarget);
  if (index < 0 || objects.length === 0) return;
  event.preventDefault();
  const direction = event.key === "ArrowRight" ? 1 : -1;
  objects[(index + direction + objects.length) % objects.length]?.focus();
}

export function UrbanSection({ open, mode = "advanced", selection, counterfactualState, analysisLens, onSelectBuilding, onClose, dataOverride, sourcePath, expectedPackId, areaLabel = "常団地前周辺", onFocusPosition }: Props) {
  const [loadedData, setLoadedData] = useState<SectionData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [guidedSampleIndex, setGuidedSampleIndex] = useState(0);
  const [guidedFocusActive, setGuidedFocusActive] = useState(false);
  const [compactSection, setCompactSection] = useState(false);
  useEffect(() => {
    if (mode !== "guided") return;
    const media = window.matchMedia("(max-width: 900px)");
    const update = () => setCompactSection(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [mode]);
  useEffect(() => {
    if (dataOverride !== undefined) return;
    const resolvedPath = sourcePath === undefined
      ? `data/spatial-packs/${PACK_ID}/sections.json`
      : sourcePath;
    if (!resolvedPath) return;
    const controller = new AbortController();
    setLoadedData(null);
    setError(null);
    fetch(publicUrl(resolvedPath), { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<SectionData>;
      })
      .then((value) => {
        if (expectedPackId && value.pack_id !== expectedPackId) throw new Error("断面とAreaのpackが一致しません");
        setLoadedData(value);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "断面を読み込めません");
      });
    return () => controller.abort();
  }, [dataOverride, expectedPackId, sourcePath]);
  const data = dataOverride !== undefined ? dataOverride : loadedData;
  const guided = mode === "guided";

  const plot = useMemo(() => {
    if (!data) return null;
    const covered = data.terrain_samples.filter((sample): sample is TerrainSample & { elevation_m: number } => sample.elevation_m !== null);
    const maxDistance = Math.max(...data.terrain_samples.map((sample) => sample.distance_m), 1);
    const minimumElevation = Math.min(...covered.map((sample) => sample.elevation_m));
    const maximumElevation = Math.max(...covered.map((sample) => sample.elevation_m));
    const maximumBuildingTop = Math.max(
      ...data.buildings.map((building) => {
        const height = typeof building.properties.measured_height_m === "number" ? building.properties.measured_height_m : 0;
        const nearest = covered.reduce((best, sample) => Math.abs(sample.distance_m - building.start_distance_m) < Math.abs(best.distance_m - building.start_distance_m) ? sample : best, covered[0]);
        return nearest.elevation_m + height;
      }),
      ...covered.map((sample) => sample.elevation_m),
    );
    const elevationSpan = Math.max(maximumBuildingTop - minimumElevation, 20);
    const viewWidth = guided && compactSection ? 390 : VIEW_WIDTH;
    const x = (distance: number) => 38 + distance / maxDistance * (viewWidth - 58);
    const y = (elevation: number) => TERRAIN_BOTTOM - (elevation - minimumElevation) / elevationSpan * (TERRAIN_BOTTOM - TERRAIN_TOP);
    const firstCovered = data.terrain_samples.find((sample) => sample.elevation_m !== null);
    const lastCovered = [...data.terrain_samples].reverse().find((sample) => sample.elevation_m !== null);
    return {
      covered,
      maxDistance,
      minimumElevation,
      maximumElevation,
      viewWidth,
      x,
      y,
      terrainSegments: terrainSegments(data.terrain_samples, x, y),
      endpointAY: y(firstCovered?.elevation_m ?? minimumElevation),
      endpointBY: y(lastCovered?.elevation_m ?? minimumElevation),
    };
  }, [compactSection, data, guided]);

  const roadAnnotations = useMemo<SectionAnnotationLayout & { calculationMs: number }>(() => {
    if (!guided || !data || !plot) return { placed: [], hiddenCount: 0, overlapCount: 0, calculationMs: 0 };
    const measureText = browserSectionTextMeasurer("600 11px system-ui, sans-serif");
    const started = performance.now();
    const layout = layoutSectionAnnotations({
      candidates: data.roads
        .filter((road) => road.relation === "direct")
        .map((road) => ({
          id: road.source_object_id,
          label: String(road.properties.road_name ?? "名称不明の道路"),
          distanceM: (road.start_distance_m + road.end_distance_m) / 2,
          offsetDistanceM: road.offset_distance_m,
        })),
      maxDistance: plot.maxDistance,
      maxVisible: compactSection ? 2 : 4,
      plotLeft: 38,
      plotRight: plot.viewWidth - 20,
      railYs: [28, 46],
      minGap: compactSection ? 6 : 8,
      measureText,
    });
    return { ...layout, calculationMs: Number((performance.now() - started).toFixed(3)) };
  }, [compactSection, data, guided, plot]);

  const focusedDetail = useMemo(() => {
    if (!guided || !guidedFocusActive || !data) return null;
    const sample = data.terrain_samples[guidedSampleIndex];
    return sample ? nearestSectionObject(data, sample.distance_m, sample.elevation_m) : null;
  }, [data, guided, guidedFocusActive, guidedSampleIndex]);

  const xTickFractions = compactSection ? [0, 1 / 3, 2 / 3, 1] : [0, .25, .5, .75, 1];
  const yTickValues = plot ? [plot.minimumElevation, (plot.minimumElevation + plot.maximumElevation) / 2, plot.maximumElevation] : [];
  const focusedCallout = useMemo(() => {
    if (!focusedDetail || !plot) return null;
    const anchorX = plot.x(focusedDetail.distanceM);
    const elevationLabel = focusedDetail.elevationM === null ? "—" : `${focusedDetail.elevationM.toFixed(1)}m`;
    const meta = `${focusedDetail.kindLabel} · ${Math.round(focusedDetail.distanceM)}m · 標高${elevationLabel}`;
    const relation = focusedDetail.relation === "direct"
      ? "直接交差"
      : `断面から約${Math.round(focusedDetail.offsetDistanceM)}m`;
    const measureName = browserSectionTextMeasurer("800 11.5px system-ui, sans-serif");
    const measureMeta = browserSectionTextMeasurer("500 9.5px system-ui, sans-serif");
    const labelWidth = Math.min(
      compactSection ? 180 : 220,
      Math.max(132, measureName(focusedDetail.label) + 16, measureMeta(meta) + 14, measureMeta(relation) + 14),
    );
    const labelX = Math.min(plot.viewWidth - 20 - labelWidth, Math.max(38, anchorX - labelWidth / 2));
    const anchorY = focusedDetail.elevationM === null ? TERRAIN_BOTTOM : plot.y(focusedDetail.elevationM);
    return { anchorX, anchorY, labelX, labelWidth, meta, relation };
  }, [compactSection, focusedDetail, plot]);

  useEffect(() => {
    if (!guided) return;
    const debugWindow = window as Window & {
      __cityGapSectionAnnotationMetrics?: { hiddenCount: number; calculationMs: number; overlapCount: number };
    };
    const metrics = {
      hiddenCount: roadAnnotations.hiddenCount,
      calculationMs: roadAnnotations.calculationMs,
      overlapCount: roadAnnotations.overlapCount,
    };
    debugWindow.__cityGapSectionAnnotationMetrics = metrics;
    return () => {
      if (debugWindow.__cityGapSectionAnnotationMetrics === metrics) delete debugWindow.__cityGapSectionAnnotationMetrics;
    };
  }, [guided, roadAnnotations]);

  const focusSection = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!data || !plot || !onFocusPosition) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const viewX = (event.clientX - bounds.left) / Math.max(bounds.width, 1) * plot.viewWidth;
    const distance = Math.max(0, Math.min(plot.maxDistance, (viewX - 38) / (plot.viewWidth - 58) * plot.maxDistance));
    const sampleIndex = data.terrain_samples.reduce((bestIndex, candidate, index) =>
      Math.abs(candidate.distance_m - distance) < Math.abs(data.terrain_samples[bestIndex].distance_m - distance) ? index : bestIndex,
    0);
    const sample = data.terrain_samples[sampleIndex];
    setGuidedSampleIndex(sampleIndex);
    setGuidedFocusActive(true);
    onFocusPosition({ longitude: sample.longitude, latitude: sample.latitude });
  };
  const focusSectionByKeyboard = (event: ReactKeyboardEvent<SVGSVGElement>) => {
    if (!guided || !data?.terrain_samples.length || !onFocusPosition) return;
    const direction = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!direction && event.key !== "Home" && event.key !== "End") return;
    event.preventDefault();
    const next = event.key === "Home"
      ? 0
      : event.key === "End"
        ? data.terrain_samples.length - 1
        : Math.max(0, Math.min(data.terrain_samples.length - 1, guidedSampleIndex + direction));
    setGuidedSampleIndex(next);
    setGuidedFocusActive(true);
    const sample = data.terrain_samples[next];
    onFocusPosition({ longitude: sample.longitude, latitude: sample.latitude });
  };

  if (!open && !guided) return <button type="button" className="urban-section-open" onClick={onClose}>都市断面を開く</button>;
  return (
    <section
      className={`urban-section ${guided ? "guided" : ""}`.trim()}
      aria-label={guided ? `${areaLabel}の街の断面` : "PLATEAU Urban Section"}
      data-ui-mode={mode}
      data-transect-ready={Boolean(data)}
      data-building-count={data?.buildings.length ?? 0}
      data-direct-building-count={data?.buildings.filter((item) => item.relation === "direct").length ?? 0}
      data-road-count={data?.roads.length ?? 0}
      data-direct-road-count={data?.roads.filter((item) => item.relation === "direct").length ?? 0}
      data-terrain-samples={data?.terrain_samples.length ?? 0}
      data-terrain-covered={data?.terrain_samples.filter((sample) => sample.elevation_m !== null).length ?? 0}
      data-pack-id={data?.pack_id ?? "none"}
      data-static-annotation-count={guided && data ? roadAnnotations.placed.length + 2 : 0}
      data-road-annotation-count={guided ? roadAnnotations.placed.length : 0}
      data-hidden-low-priority-annotations={guided ? roadAnnotations.hiddenCount : 0}
      data-annotation-overlap-count={guided ? roadAnnotations.overlapCount : 0}
      data-annotation-calculation-ms={guided ? roadAnnotations.calculationMs : 0}
      data-selected-annotation-visible={guidedFocusActive && Boolean(focusedDetail)}
      data-focused-object-kind={focusedDetail?.kind ?? "none"}
      data-focused-object-id={focusedDetail?.id ?? "none"}
      data-counterfactual-ready={counterfactualState !== "scenario" || Boolean(data?.counterfactual && data.scenario_sites.length > 0)}
      data-service-section-ready={analysisLens !== "service-pulse" || Boolean(data?.service_locations.length)}
    >
      <header>
        <div><span>{guided ? "街の断面" : "PLATEAU URBAN SECTION"}</span><strong>{guided ? "実際の地形・建物・道路" : "実DEM × 建物 × 道路"}</strong></div>
        {data && (guided ? <dl className="guided-section-facts"><div><dt>断面付近の建物</dt><dd>{data.buildings.length}棟</dd></div><div><dt>交差する道路</dt><dd>{data.roads.length}本</dd></div></dl> : <dl><div><dt>PACK</dt><dd>{data.pack_id}</dd></div><div><dt>TIN sample</dt><dd>{data.terrain_samples.filter((sample) => sample.elevation_m !== null).length}/{data.terrain_samples.length}</dd></div><div><dt>建物</dt><dd>{data.buildings.length}</dd></div><div><dt>道路</dt><dd>{data.roads.length}</dd></div></dl>)}
        {!guided && <button type="button" onClick={onClose} aria-label="都市断面を閉じる">閉じる</button>}
      </header>
      {error && <p className="section-load-message error" role="alert">{guided ? "街の断面データを読み込めませんでした。地図と確認済みの集計値は引き続き確認できます。" : `Urban Section: ${error}`}</p>}
      {!data || !plot ? (!error || !guided) && <p className="section-load-message" role="status">{guided ? "PLATEAUの地形・建物・道路を読み込んでいます。読み込み中も次の手順へ進めます。" : "実PLATEAU断面を読み込み中"}</p> : <>
        <p id="section-accessible-summary" className="section-text-summary" aria-live={guided ? "polite" : undefined}>
          {guided ? <>
            AからBまで約{Math.round(plot.maxDistance)}m。標高は{plot.minimumElevation.toFixed(1)}mから{plot.maximumElevation.toFixed(1)}m。直接交差する建物は{data.buildings.filter((item) => item.relation === "direct").length}棟、道路は{data.roads.filter((item) => item.relation === "direct").length}本です。
            {focusedDetail && ` 選択位置に最も近い${focusedDetail.kindLabel}は${focusedDetail.label}。Aから約${Math.round(focusedDetail.distanceM)}m、標高${focusedDetail.elevationM === null ? "データなし" : `${focusedDetail.elevationM.toFixed(1)}m`}、${focusedDetail.relation === "direct" ? "断面と直接交差" : `断面から約${Math.round(focusedDetail.offsetDistanceM)}m`}です。`}
            {counterfactualState === "scenario" && ` 仮想地点を加えた条件では、500m集計の直線距離が${data.counterfactual.baseline.distance_m}mから${data.counterfactual.scenario.distance_m}mへ変わります。建物と道路の形は変えていません。`}
            データに建物高さがない場合は、推測で補っていません。
          </> : <>
            地形標高 {plot.minimumElevation.toFixed(1)}〜{plot.maximumElevation.toFixed(1)}m。建物 {data.buildings.length}棟（直接交差 {data.buildings.filter((item) => item.relation === "direct").length}、近傍 {data.buildings.filter((item) => item.relation === "nearby").length}）。道路交差 {data.roads.length}、周辺施設 {data.service_locations.length}。
            {counterfactualState === "scenario" ? ` Scenario ${data.counterfactual.plan_id}では500m集計直線距離が${data.counterfactual.baseline.distance_m}mから${data.counterfactual.scenario.distance_m}mへ変化。建物・道路geometryは不変。` : " Scenario relationは未選択。"}
            高さ不明は補完せず、施設は断面からのoffsetを表示します。
          </>}
        </p>
        <svg
          viewBox={`0 0 ${plot.viewWidth} 220`}
          role="img"
          tabIndex={guided ? 0 : undefined}
          aria-labelledby="section-title"
          aria-describedby={guided ? "section-description section-accessible-summary guided-section-keyboard-help" : "section-description"}
          onPointerMove={focusSection}
          onPointerLeave={() => {
            setGuidedFocusActive(false);
            onFocusPosition?.(null);
          }}
          onFocus={() => {
            const sample = data.terrain_samples[guidedSampleIndex];
            if (guided && sample) {
              setGuidedFocusActive(true);
              onFocusPosition?.({ longitude: sample.longitude, latitude: sample.latitude });
            }
          }}
          onBlur={() => {
            if (guided) {
              setGuidedFocusActive(false);
              onFocusPosition?.(null);
            }
          }}
          onKeyDown={focusSectionByKeyboard}
        >
          <title id="section-title">{guided ? `${areaLabel}の街の断面` : "常団地前500mメッシュのPLATEAU都市断面"}</title>
          <desc id="section-description">{guided ? "PLATEAUの地形、建物、道路を同じ断面で表示しています。データにない人口や建物高さは補っていません。" : `${data.terrain_source}を三角形内で補間した地形、直接交差と近傍を区別した建物、PLATEAU道路、計画・災害帯を表示。人口や建物高さの補完は行っていません。`}</desc>
          <g className="section-grid" aria-hidden="true">
            {xTickFractions.map((fraction) => <line key={`x-${fraction}`} x1={plot.x(plot.maxDistance * fraction)} x2={plot.x(plot.maxDistance * fraction)} y1="54" y2="198" />)}
            {yTickValues.map((value) => <line key={`y-${value}`} x1="38" x2={plot.viewWidth - 20} y1={plot.y(value)} y2={plot.y(value)} />)}
          </g>
          <g className="section-axis" aria-hidden="true">
            <circle className="endpoint-dot" cx="38" cy={plot.endpointAY} r="3" />
            <circle className="endpoint-dot" cx={plot.viewWidth - 20} cy={plot.endpointBY} r="3" />
            <text className="endpoint" data-section-endpoint="A" x="38" y="16">A</text>
            <text className="endpoint" data-section-endpoint="B" x={plot.viewWidth - 20} y="16">B</text>
            {yTickValues.map((value) => <text key={value} data-section-axis-tick="elevation" x="34" y={plot.y(value) + 4} textAnchor="end">{value.toFixed(1)}</text>)}
            {xTickFractions.map((fraction) => <text key={fraction} data-section-axis-tick="distance" x={plot.x(plot.maxDistance * fraction)} y="215" textAnchor="middle">{Math.round(plot.maxDistance * fraction)}</text>)}
            <text className="axis-title" x="10" y="113" transform="rotate(-90 10 113)" textAnchor="middle">標高（m）</text>
            <text className="axis-title" x={plot.viewWidth / 2} y="204" textAnchor="middle">Aからの距離（m）</text>
          </g>
          <g className="section-terrain-area" aria-hidden="true">
            {plot.terrainSegments.map((segment, index) => <path key={index} d={segment.area} />)}
          </g>
          {!guided && <g className="section-planning" aria-label="都市計画帯">
            {data.planning_bands.map((band) => <rect key={band.source_object_id} x={plot.x(band.start_distance_m)} y="184" width={Math.max(2, plot.x(band.end_distance_m) - plot.x(band.start_distance_m))} height="7"><title>{String(band.planning?.districts_and_zones ?? "都市計画属性")}</title></rect>)}
          </g>}
          {!guided && <g className="section-hazard" aria-label="災害帯">
            {data.hazard_bands.map((band) => <rect key={band.source_object_id} x={plot.x(band.start_distance_m)} y="194" width={Math.max(2, plot.x(band.end_distance_m) - plot.x(band.start_distance_m))} height="7"><title>公式属性に記録された災害範囲</title></rect>)}
          </g>}
          <g className="section-buildings" aria-label={guided ? undefined : "PLATEAU建物"} aria-hidden={guided ? true : undefined}>
            {data.buildings.map((building) => {
              const height = typeof building.properties.measured_height_m === "number" ? building.properties.measured_height_m : null;
              const midpoint = (building.start_distance_m + building.end_distance_m) / 2;
              const nearest = plot.covered.reduce((best, sample) => Math.abs(sample.distance_m - midpoint) < Math.abs(best.distance_m - midpoint) ? sample : best, plot.covered[0]);
              const top = height === null ? plot.y(nearest.elevation_m) - 5 : plot.y(nearest.elevation_m + height);
              const selected = selection?.type === "building" && selection.id === building.source_object_id;
              return <rect
                key={building.source_object_id}
                className={`${building.relation} ${selected ? "selected" : ""} ${focusedDetail?.kind === "building" && focusedDetail.id === building.source_object_id ? "focused" : ""}`}
                x={plot.x(building.start_distance_m)}
                y={top}
                width={Math.max(3, plot.x(building.end_distance_m) - plot.x(building.start_distance_m))}
                height={Math.max(5, plot.y(nearest.elevation_m) - top)}
                data-section-building="true"
                tabIndex={guided ? undefined : 0}
                role={guided ? undefined : "button"}
                aria-hidden={guided ? true : undefined}
                aria-label={`${String(building.properties.usage ?? "用途不明")} ${height === null ? "高さ不明" : `高さ${height}m`} ${building.relation === "direct" ? "断面交差" : `断面から${building.offset_distance_m}m`}`}
                onClick={guided ? undefined : () => onSelectBuilding(building.source_object_id, building.properties)}
                onKeyDown={guided ? undefined : (event) => {
                  if (event.key === "Enter" || event.key === " ") onSelectBuilding(building.source_object_id, building.properties);
                  moveSectionFocus(event);
                }}
              ><title>{guided ? `${String(building.properties.usage ?? "用途不明")} · ${height === null ? "高さはデータなし" : `高さ${height}m`}` : `${building.source_object_id} · ${String(building.properties.usage ?? "用途不明")} · ${height === null ? "高さ不明（補完なし）" : `${height}m`}`}</title></rect>;
            })}
          </g>
          <g className="section-roads" aria-label={guided ? undefined : "PLATEAU道路"} aria-hidden={guided ? true : undefined}>
            {data.roads.filter((road) => !guided || road.relation === "direct").map((road) => <path
              key={road.source_object_id}
              className={focusedDetail?.kind === "road" && focusedDetail.id === road.source_object_id ? "focused" : undefined}
              data-section-road="true"
              d={`M${plot.x((road.start_distance_m + road.end_distance_m) / 2) - 4},180 h8 l-2,-8 h-4 z`}
            ><title>{String(road.properties.road_name ?? (guided ? "名称不明の道路" : road.source_object_id))}</title></path>)}
          </g>
          {!guided && <g className="section-services" aria-label="施設位置">
            {data.service_locations.slice(0, 6).map((facility, index) => <g key={facility.source_object_id} transform={`translate(${plot.x(facility.start_distance_m)},${24 + index * 8})`}><circle r="2.5" /><text x="5" y="2">{`${String(facility.properties.name ?? facility.source_object_id)} · offset ${Math.round(facility.offset_distance_m)}m`}</text></g>)}
          </g>}
          <g className="section-terrain" aria-label={guided ? undefined : "PLATEAU DEM TIN地形"} aria-hidden={guided ? true : undefined}>
            {plot.terrainSegments.map((segment, index) => <path key={index} d={segment.line} />)}
          </g>
          {guided && <g className="section-road-annotations" aria-hidden="true">
            {roadAnnotations.placed.map((annotation) => <g key={annotation.id}>
              <line x1={annotation.anchorX} x2={annotation.labelX + annotation.labelWidth / 2} y1="171" y2={annotation.railY + 3} />
              <text
                x={annotation.labelX + annotation.labelWidth / 2}
                y={annotation.railY}
                textAnchor="middle"
                data-section-static-annotation="road"
                data-section-annotation-kind="road"
                data-section-road-label={annotation.label}
                data-section-label-left={annotation.labelX.toFixed(2)}
                data-section-label-right={(annotation.labelX + annotation.labelWidth).toFixed(2)}
              >{annotation.label}</text>
            </g>)}
          </g>}
          {guided && focusedDetail && focusedCallout && <g className="section-focus-callout" aria-hidden="true" data-section-focus-annotation="true" data-section-annotation-selected="true">
            <line x1={focusedCallout.anchorX} x2={focusedCallout.labelX + focusedCallout.labelWidth / 2} y1={focusedCallout.anchorY} y2="62" />
            <circle cx={focusedCallout.anchorX} cy={focusedCallout.anchorY} r="4" />
            <rect x={focusedCallout.labelX} y="58" width={focusedCallout.labelWidth} height="44" rx="3" />
            <text className="focus-name" x={focusedCallout.labelX + 7} y="70">{focusedDetail.label}</text>
            <text className="focus-meta" x={focusedCallout.labelX + 7} y="83">{focusedCallout.meta}</text>
            <text className="focus-meta" x={focusedCallout.labelX + 7} y="96">{focusedCallout.relation}</text>
          </g>}
          {analysisLens === "service-pulse" && <text className="section-pulse-note" x="610" y="18">{guided ? "施設の位置は断面上への投影です。徒歩時間ではありません。" : "3D: experimental network距離 · 断面: 実施設のoffset投影（徒歩時間ではない）"}</text>}
          {counterfactualState === "scenario" && <g className="section-counterfactual" aria-label={guided ? "現在と仮想地点を加えた条件の比較" : `Counterfactual comparison ${data.counterfactual.plan_id}`}>
            <rect className="affected-group" x={plot.x(0)} y="3" width={plot.x(plot.maxDistance) - plot.x(0)} height="12"><title>{data.counterfactual.building_group_count}棟に関連する500m集計値。建物固有の改善ではありません。</title></rect>
            <text x="42" y="12">{guided ? "変わるのは距離の関係です。建物・道路の形は変えていません" : "CHANGED RELATION · 建物/道路geometry固定"}</text>
            <line className="baseline" x1="664" x2="940" y1="8" y2="8" />
            <line className="scenario" x1="664" x2={664 + 276 * data.counterfactual.scenario.distance_m / data.counterfactual.baseline.distance_m} y1="14" y2="14" />
            <text x="660" y="26">500m集計直線距離 {data.counterfactual.baseline.distance_m}m → {data.counterfactual.scenario.distance_m}m（−{data.counterfactual.scenario.distance_reduction_m}m）</text>
            {data.scenario_sites.map((site) => <g key={site.source_object_id} className="scenario-site">
              <line x1={plot.x(site.start_distance_m)} x2={plot.x(site.start_distance_m)} y1="154" y2="181" />
              <path d={`M${plot.x(site.start_distance_m) - 4},154 h8 l-4,-8 z`} />
              <title>{guided ? `仮想地点 ${String(site.properties.road_name ?? "道路名なし")}付近 · 断面から${site.offset_distance_m}m · 設置場所は未確定` : `候補地点 ${String(site.properties.road_name ?? site.source_object_id)} · 断面offset ${site.offset_distance_m}m · siting未確定`}</title>
            </g>)}
          </g>}
          {counterfactualState === "stress" && <text className="section-counterfactual-note" x="660" y="18">{guided ? "この断面には災害条件による形の変化を加えていません" : "STRESS · このpackに断面固有stress relationなし · geometry不変"}</text>}
        </svg>
        {guided && <span id="guided-section-keyboard-help" className="guided-section-keyboard-help">左右矢印キーで断面上の地形位置を移動すると、地図上の同じ位置が示されます。</span>}
        <footer className={guided ? "guided-section-footer" : undefined}>
          {guided ? <>
            <div className="section-visual-legend" aria-label="断面の凡例">
              <span><i className="terrain" aria-hidden="true" />地形</span>
              <span><i className="building" aria-hidden="true" />建物</span>
              <span><i className="road" aria-hidden="true" />道路</span>
            </div>
            <span className="guided-section-source">PLATEAU 舞鶴市2025 · 高さのない建物は補完なし</span>
          </> : <>
            <span>高さ基準: {data.vertical_datum}</span>
            <span>断面: TIN barycentric / exaggeration 1.0</span>
            <span>直接交差 {data.buildings.filter((item) => item.relation === "direct").length} · 近傍 {data.buildings.filter((item) => item.relation === "nearby").length}</span>
          </>}
        </footer>
      </>}
    </section>
  );
}
