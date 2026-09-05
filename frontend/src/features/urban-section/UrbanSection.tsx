import { useEffect, useMemo, useState, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import type { AnalysisLens, CounterfactualState, SpatialSelection } from "../../state/spatial/types";
import {
  browserSectionTextMeasurer,
  layoutSectionAnnotations,
  type SectionAnnotationLayout,
} from "./sectionAnnotations";
import {
  buildSectionFocusCallout,
  buildSectionPlot,
  nearestSectionObject,
  sectionSampleIndexAtViewX,
} from "./sectionLayout";
import type { SectionData } from "./sectionTypes";
import { useSectionData } from "./useSectionData";

export type { SectionData } from "./sectionTypes";

interface Props {
  open: boolean;
  mode?: "advanced" | "guided";
  readable?: boolean;
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

export function UrbanSection({ open, mode = "advanced", readable = false, selection, counterfactualState, analysisLens, onSelectBuilding, onClose, dataOverride, sourcePath, expectedPackId, areaLabel = "常団地前周辺", onFocusPosition }: Props) {
  const [guidedSampleIndex, setGuidedSampleIndex] = useState(0);
  const [guidedFocusActive, setGuidedFocusActive] = useState(false);
  const [compactSection, setCompactSection] = useState(false);
  const guided = mode === "guided";
  const readableSection = guided || readable;
  const { data, error } = useSectionData({ dataOverride, sourcePath, expectedPackId });
  useEffect(() => {
    if (!readableSection) return;
    const media = window.matchMedia("(max-width: 900px)");
    const update = () => setCompactSection(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [readableSection]);

  const plot = useMemo(
    () => data ? buildSectionPlot(data, readableSection && compactSection) : null,
    [compactSection, data, readableSection],
  );

  const roadAnnotations = useMemo<SectionAnnotationLayout & { calculationMs: number }>(() => {
    if (!readableSection || !data || !plot) return { placed: [], hiddenCount: 0, overlapCount: 0, calculationMs: 0 };
    const measureText = browserSectionTextMeasurer("750 12px system-ui, sans-serif");
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
  }, [compactSection, data, readableSection, plot]);

  const focusedDetail = useMemo(() => {
    if (!readableSection || !guidedFocusActive || !data) return null;
    const sample = data.terrain_samples[guidedSampleIndex];
    return sample ? nearestSectionObject(data, sample.distance_m, sample.elevation_m) : null;
  }, [data, readableSection, guidedFocusActive, guidedSampleIndex]);

  const xTickFractions = compactSection ? [0, 1 / 3, 2 / 3, 1] : [0, .25, .5, .75, 1];
  const yTickValues = plot ? [plot.minimumElevation, (plot.minimumElevation + plot.maximumElevation) / 2, plot.maximumElevation] : [];
  const focusedCallout = useMemo(() => {
    if (!focusedDetail || !plot) return null;
    const measureName = browserSectionTextMeasurer("800 13px system-ui, sans-serif");
    const measureMeta = browserSectionTextMeasurer("600 12px system-ui, sans-serif");
    return buildSectionFocusCallout(focusedDetail, plot, compactSection, measureName, measureMeta);
  }, [compactSection, focusedDetail, plot]);

  useEffect(() => {
    if (!readableSection) return;
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
  }, [readableSection, roadAnnotations]);

  const focusSection = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!data || !plot || !onFocusPosition) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const viewX = (event.clientX - bounds.left) / Math.max(bounds.width, 1) * plot.viewWidth;
    const sampleIndex = sectionSampleIndexAtViewX(data, plot, viewX);
    const sample = data.terrain_samples[sampleIndex];
    setGuidedSampleIndex(sampleIndex);
    setGuidedFocusActive(true);
    onFocusPosition({ longitude: sample.longitude, latitude: sample.latitude });
  };
  const focusSectionByKeyboard = (event: ReactKeyboardEvent<SVGSVGElement>) => {
    if (!readableSection || event.target !== event.currentTarget || !data?.terrain_samples.length || !onFocusPosition) return;
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
      className={`urban-section ${guided ? "guided" : readable ? "readable" : ""}`.trim()}
      aria-label={readableSection ? `${areaLabel}の街の断面` : "PLATEAU Urban Section"}
      data-ui-mode={mode}
      data-readable={readableSection}
      data-transect-ready={Boolean(data)}
      data-building-count={data?.buildings.length ?? 0}
      data-direct-building-count={data?.buildings.filter((item) => item.relation === "direct").length ?? 0}
      data-road-count={data?.roads.length ?? 0}
      data-direct-road-count={data?.roads.filter((item) => item.relation === "direct").length ?? 0}
      data-terrain-samples={data?.terrain_samples.length ?? 0}
      data-terrain-covered={data?.terrain_samples.filter((sample) => sample.elevation_m !== null).length ?? 0}
      data-pack-id={data?.pack_id ?? "none"}
      data-static-annotation-count={readableSection && data ? roadAnnotations.placed.length + 2 : 0}
      data-road-annotation-count={readableSection ? roadAnnotations.placed.length : 0}
      data-hidden-low-priority-annotations={readableSection ? roadAnnotations.hiddenCount : 0}
      data-annotation-overlap-count={readableSection ? roadAnnotations.overlapCount : 0}
      data-annotation-calculation-ms={readableSection ? roadAnnotations.calculationMs : 0}
      data-selected-annotation-visible={guidedFocusActive && Boolean(focusedDetail)}
      data-focused-object-kind={focusedDetail?.kind ?? "none"}
      data-focused-object-id={focusedDetail?.id ?? "none"}
      data-counterfactual-ready={counterfactualState !== "scenario" || Boolean(data?.counterfactual && data.scenario_sites.length > 0)}
      data-service-section-ready={analysisLens !== "service-pulse" || Boolean(data?.service_locations.length)}
    >
      <header>
        <div><span>{readableSection ? "街の断面" : "PLATEAU URBAN SECTION"}</span><strong>{readableSection ? "実際の地形・建物・道路" : "実DEM × 建物 × 道路"}</strong></div>
        {data && (readableSection ? <dl className="guided-section-facts"><div><dt>断面付近の建物</dt><dd>{data.buildings.length}棟</dd></div><div><dt>交差する道路</dt><dd>{data.roads.length}本</dd></div></dl> : <dl><div><dt>PACK</dt><dd>{data.pack_id}</dd></div><div><dt>TIN sample</dt><dd>{data.terrain_samples.filter((sample) => sample.elevation_m !== null).length}/{data.terrain_samples.length}</dd></div><div><dt>建物</dt><dd>{data.buildings.length}</dd></div><div><dt>道路</dt><dd>{data.roads.length}</dd></div></dl>)}
        {!guided && <button type="button" onClick={onClose} aria-label="都市断面を閉じる">閉じる</button>}
      </header>
      {error && <p className="section-load-message error" role="alert">{guided ? "街の断面データを読み込めませんでした。地図と確認済みの集計値は引き続き確認できます。" : `Urban Section: ${error}`}</p>}
      {!data || !plot ? (!error || !guided) && <p className="section-load-message" role="status">{guided ? "PLATEAUの地形・建物・道路を読み込んでいます。読み込み中も次の手順へ進めます。" : "実PLATEAU断面を読み込み中"}</p> : <>
        <p id="section-accessible-summary" className="section-text-summary" aria-live={readableSection ? "polite" : undefined}>
          {readableSection ? <>
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
          tabIndex={readableSection ? 0 : undefined}
          aria-labelledby="section-title"
          aria-describedby={readableSection ? "section-description section-accessible-summary guided-section-keyboard-help" : "section-description"}
          onPointerMove={focusSection}
          onPointerLeave={() => {
            setGuidedFocusActive(false);
            onFocusPosition?.(null);
          }}
          onFocus={(event) => {
            const sample = data.terrain_samples[guidedSampleIndex];
            if (readableSection && event.target === event.currentTarget && sample) {
              setGuidedFocusActive(true);
              onFocusPosition?.({ longitude: sample.longitude, latitude: sample.latitude });
            }
          }}
          onBlur={() => {
            if (readableSection) {
              setGuidedFocusActive(false);
              onFocusPosition?.(null);
            }
          }}
          onKeyDown={focusSectionByKeyboard}
        >
          <title id="section-title">{readableSection ? `${areaLabel}の街の断面` : "常団地前500mメッシュのPLATEAU都市断面"}</title>
          <desc id="section-description">{readableSection ? "PLATEAUの地形、建物、道路を同じ断面で表示しています。データにない人口や建物高さは補っていません。" : `${data.terrain_source}を三角形内で補間した地形、直接交差と近傍を区別した建物、PLATEAU道路、計画・災害帯を表示。人口や建物高さの補完は行っていません。`}</desc>
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
                  if (event.key === "Enter" || event.key === " ") {
                    if (readableSection) event.preventDefault();
                    onSelectBuilding(building.source_object_id, building.properties);
                  }
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
            {data.service_locations.slice(0, 6).map((facility, index) => <g key={facility.source_object_id} transform={`translate(${plot.x(facility.start_distance_m)},${24 + index * 8})`}><circle r="2.5" />{readableSection ? <title>{`${String(facility.properties.name ?? facility.source_object_id)} · offset ${Math.round(facility.offset_distance_m)}m`}</title> : <text x="5" y="2">{`${String(facility.properties.name ?? facility.source_object_id)} · offset ${Math.round(facility.offset_distance_m)}m`}</text>}</g>)}
          </g>}
          <g className="section-terrain" aria-label={guided ? undefined : "PLATEAU DEM TIN地形"} aria-hidden={guided ? true : undefined}>
            {plot.terrainSegments.map((segment, index) => <path key={index} d={segment.line} />)}
          </g>
          {readableSection && <g className="section-road-annotations" aria-hidden="true">
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
          {readableSection && focusedDetail && focusedCallout && <g className="section-focus-callout" aria-hidden="true" data-section-focus-annotation="true" data-section-annotation-selected="true">
            <line x1={focusedCallout.anchorX} x2={focusedCallout.labelX + focusedCallout.labelWidth / 2} y1={focusedCallout.anchorY} y2="59" />
            <circle cx={focusedCallout.anchorX} cy={focusedCallout.anchorY} r="4" />
            <rect x={focusedCallout.labelX} y="55" width={focusedCallout.labelWidth} height="51" rx="3" />
            <text className="focus-name" x={focusedCallout.labelX + 8} y="69">{focusedDetail.label}</text>
            <text className="focus-meta" x={focusedCallout.labelX + 8} y="85">{focusedCallout.meta}</text>
            <text className="focus-meta" x={focusedCallout.labelX + 8} y="100">{focusedCallout.relation}</text>
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
        {readableSection && <span id="guided-section-keyboard-help" className="guided-section-keyboard-help">左右矢印キーで断面上の地形位置を移動すると、地図上の同じ位置が示されます。{!guided && "建物にはTabキーで移動し、Enterまたはスペースキーで選択できます。"}</span>}
        <footer className={readableSection ? "guided-section-footer" : undefined}>
          {readableSection ? <>
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
