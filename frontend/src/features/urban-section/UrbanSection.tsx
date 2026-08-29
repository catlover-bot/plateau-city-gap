import { useEffect, useMemo, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import type { AnalysisLens, CounterfactualState, SpatialSelection } from "../../state/spatial/types";

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

interface SectionData {
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

function lineSegments(samples: TerrainSample[], x: (value: number) => number, y: (value: number) => number): string[] {
  const segments: string[] = [];
  let current: string[] = [];
  samples.forEach((sample) => {
    if (sample.elevation_m === null) {
      if (current.length > 1) segments.push(current.join(" "));
      current = [];
      return;
    }
    current.push(`${current.length ? "L" : "M"}${x(sample.distance_m).toFixed(2)},${y(sample.elevation_m).toFixed(2)}`);
  });
  if (current.length > 1) segments.push(current.join(" "));
  return segments;
}

interface Props {
  open: boolean;
  mode?: "advanced" | "guided";
  selection: SpatialSelection | null;
  counterfactualState: CounterfactualState;
  analysisLens: AnalysisLens;
  onSelectBuilding(id: string, properties: Record<string, unknown>): void;
  onClose(): void;
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

export function UrbanSection({ open, mode = "advanced", selection, counterfactualState, analysisLens, onSelectBuilding, onClose }: Props) {
  const [data, setData] = useState<SectionData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch(publicUrl(`data/spatial-packs/${PACK_ID}/sections.json`))
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<SectionData>;
      })
      .then((value) => { if (!cancelled) setData(value); })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "断面を読み込めません"); });
    return () => { cancelled = true; };
  }, []);

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
    const x = (distance: number) => 38 + distance / maxDistance * (VIEW_WIDTH - 58);
    const y = (elevation: number) => TERRAIN_BOTTOM - (elevation - minimumElevation) / elevationSpan * (TERRAIN_BOTTOM - TERRAIN_TOP);
    return { covered, maxDistance, minimumElevation, maximumElevation, x, y, terrainPaths: lineSegments(data.terrain_samples, x, y) };
  }, [data]);

  const guided = mode === "guided";

  if (!open && !guided) return <button type="button" className="urban-section-open" onClick={onClose}>都市断面を開く</button>;
  return (
    <section
      className={`urban-section ${guided ? "guided" : ""}`.trim()}
      aria-label={guided ? "常団地前周辺の街の断面" : "PLATEAU Urban Section"}
      data-ui-mode={mode}
      data-transect-ready={Boolean(data)}
      data-building-count={data?.buildings.length ?? 0}
      data-road-count={data?.roads.length ?? 0}
      data-terrain-samples={data?.terrain_samples.length ?? 0}
      data-terrain-covered={data?.terrain_samples.filter((sample) => sample.elevation_m !== null).length ?? 0}
      data-pack-id={data?.pack_id ?? "none"}
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
        <p className="section-text-summary">
          {guided ? <>
            実際の地形に沿った断面です。断面付近では建物 {data.buildings.length}棟と道路 {data.roads.length}本を確認できます。
            {counterfactualState === "scenario" && ` 仮想地点を加えた条件では、500m集計の直線距離が${data.counterfactual.baseline.distance_m}mから${data.counterfactual.scenario.distance_m}mへ変わります。建物と道路の形は変えていません。`}
            データに建物高さがない場合は、推測で補っていません。
          </> : <>
            地形標高 {plot.minimumElevation.toFixed(1)}〜{plot.maximumElevation.toFixed(1)}m。建物 {data.buildings.length}棟（直接交差 {data.buildings.filter((item) => item.relation === "direct").length}、近傍 {data.buildings.filter((item) => item.relation === "nearby").length}）。道路交差 {data.roads.length}、周辺施設 {data.service_locations.length}。
            {counterfactualState === "scenario" ? ` Scenario ${data.counterfactual.plan_id}では500m集計直線距離が${data.counterfactual.baseline.distance_m}mから${data.counterfactual.scenario.distance_m}mへ変化。建物・道路geometryは不変。` : " Scenario relationは未選択。"}
            高さ不明は補完せず、施設は断面からのoffsetを表示します。
          </>}
        </p>
        <svg viewBox={`0 0 ${VIEW_WIDTH} 220`} role="img" aria-labelledby="section-title section-description">
          <title id="section-title">{guided ? "常団地前周辺の街の断面" : "常団地前500mメッシュのPLATEAU都市断面"}</title>
          <desc id="section-description">{guided ? "PLATEAUの地形、建物、道路を同じ断面で表示しています。データにない人口や建物高さは補っていません。" : `${data.terrain_source}を三角形内で補間した地形、直接交差と近傍を区別した建物、PLATEAU道路、計画・災害帯を表示。人口や建物高さの補完は行っていません。`}</desc>
          <g className="section-grid" aria-hidden="true">
            {[0, .25, .5, .75, 1].map((fraction) => <g key={fraction}><line x1={plot.x(plot.maxDistance * fraction)} x2={plot.x(plot.maxDistance * fraction)} y1="20" y2="205" /><text x={plot.x(plot.maxDistance * fraction)} y="216">{Math.round(plot.maxDistance * fraction)}m</text></g>)}
          </g>
          <g className="section-planning" aria-label="都市計画帯">
            {data.planning_bands.map((band) => <rect key={band.source_object_id} x={plot.x(band.start_distance_m)} y="184" width={Math.max(2, plot.x(band.end_distance_m) - plot.x(band.start_distance_m))} height="7"><title>{String(band.planning?.districts_and_zones ?? "都市計画属性")}</title></rect>)}
          </g>
          <g className="section-hazard" aria-label="災害帯">
            {data.hazard_bands.map((band) => <rect key={band.source_object_id} x={plot.x(band.start_distance_m)} y="194" width={Math.max(2, plot.x(band.end_distance_m) - plot.x(band.start_distance_m))} height="7"><title>公式属性に記録された災害範囲</title></rect>)}
          </g>
          <g className="section-buildings" aria-label="PLATEAU建物">
            {data.buildings.map((building) => {
              const height = typeof building.properties.measured_height_m === "number" ? building.properties.measured_height_m : null;
              const midpoint = (building.start_distance_m + building.end_distance_m) / 2;
              const nearest = plot.covered.reduce((best, sample) => Math.abs(sample.distance_m - midpoint) < Math.abs(best.distance_m - midpoint) ? sample : best, plot.covered[0]);
              const top = height === null ? plot.y(nearest.elevation_m) - 5 : plot.y(nearest.elevation_m + height);
              const selected = selection?.type === "building" && selection.id === building.source_object_id;
              return <rect
                key={building.source_object_id}
                className={`${building.relation} ${selected ? "selected" : ""}`}
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
          <g className="section-roads" aria-label="PLATEAU道路">
            {data.roads.map((road) => <path key={road.source_object_id} d={`M${plot.x(road.start_distance_m) - 4},180 h8 l-2,-7 h-4 z`}><title>{String(road.properties.road_name ?? (guided ? "名称不明の道路" : road.source_object_id))}</title></path>)}
          </g>
          <g className="section-services" aria-label="施設位置">
            {data.service_locations.slice(0, 6).map((facility, index) => <g key={facility.source_object_id} transform={`translate(${plot.x(facility.start_distance_m)},${24 + index * 8})`}><circle r="2.5" /><text x="5" y="2">{guided ? `${String(facility.properties.name ?? "名称不明の施設")} · 断面から約${Math.round(facility.offset_distance_m)}m` : `${String(facility.properties.name ?? facility.source_object_id)} · offset ${Math.round(facility.offset_distance_m)}m`}</text></g>)}
          </g>
          <g className="section-terrain" aria-label={guided ? "PLATEAUの地形" : "PLATEAU DEM TIN地形"}>
            {plot.terrainPaths.map((path, index) => <path key={index} d={path} />)}
          </g>
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
        <footer>
          {guided ? <>
            <span>地形・建物・道路：PLATEAU 舞鶴市2025</span>
            <span>データにない建物高さは補っていません</span>
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
