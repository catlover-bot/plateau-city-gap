import { useEffect, useMemo, useState } from "react";
import type { CounterfactualState, SpatialSelection } from "../../state/spatial/types";

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
  selection: SpatialSelection | null;
  counterfactualState: CounterfactualState;
  onSelectBuilding(id: string, properties: Record<string, unknown>): void;
  onClose(): void;
}

export function UrbanSection({ open, selection, counterfactualState, onSelectBuilding, onClose }: Props) {
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
    return { covered, maxDistance, minimumElevation, x, y, terrainPaths: lineSegments(data.terrain_samples, x, y) };
  }, [data]);

  if (!open) return <button type="button" className="urban-section-open" onClick={onClose}>都市断面を開く</button>;
  return (
    <section
      className="urban-section"
      aria-label="PLATEAU Urban Section"
      data-transect-ready={Boolean(data)}
      data-building-count={data?.buildings.length ?? 0}
      data-road-count={data?.roads.length ?? 0}
      data-terrain-samples={data?.terrain_samples.length ?? 0}
      data-terrain-covered={data?.terrain_samples.filter((sample) => sample.elevation_m !== null).length ?? 0}
      data-pack-id={data?.pack_id ?? "none"}
    >
      <header>
        <div><span>PLATEAU URBAN SECTION</span><strong>実DEM × 建物 × 道路</strong></div>
        {data && <dl><div><dt>PACK</dt><dd>{data.pack_id}</dd></div><div><dt>TIN sample</dt><dd>{data.terrain_samples.filter((sample) => sample.elevation_m !== null).length}/{data.terrain_samples.length}</dd></div><div><dt>建物</dt><dd>{data.buildings.length}</dd></div><div><dt>道路</dt><dd>{data.roads.length}</dd></div></dl>}
        <button type="button" onClick={onClose} aria-label="都市断面を閉じる">閉じる</button>
      </header>
      {error && <p role="alert">Urban Section: {error}</p>}
      {!data || !plot ? <p role="status">実PLATEAU断面を読み込み中</p> : <>
        <svg viewBox={`0 0 ${VIEW_WIDTH} 220`} role="img" aria-labelledby="section-title section-description">
          <title id="section-title">常団地前500mメッシュのPLATEAU都市断面</title>
          <desc id="section-description">{data.terrain_source}を三角形内で補間した地形、直接交差と近傍を区別した建物、PLATEAU道路、計画・災害帯を表示。人口や建物高さの補完は行っていません。</desc>
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
                tabIndex={0}
                role="button"
                aria-label={`${String(building.properties.usage ?? "用途不明")} ${height === null ? "高さ不明" : `高さ${height}m`} ${building.relation === "direct" ? "断面交差" : `断面から${building.offset_distance_m}m`}`}
                onClick={() => onSelectBuilding(building.source_object_id, building.properties)}
                onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelectBuilding(building.source_object_id, building.properties); }}
              ><title>{building.source_object_id} · {String(building.properties.usage ?? "用途不明")} · {height === null ? "高さ不明（補完なし）" : `${height}m`}</title></rect>;
            })}
          </g>
          <g className="section-roads" aria-label="PLATEAU道路">
            {data.roads.map((road) => <path key={road.source_object_id} d={`M${plot.x(road.start_distance_m) - 4},180 h8 l-2,-7 h-4 z`}><title>{String(road.properties.road_name ?? road.source_object_id)}</title></path>)}
          </g>
          <g className="section-services" aria-label="施設位置">
            {data.service_locations.slice(0, 6).map((facility, index) => <g key={facility.source_object_id} transform={`translate(${plot.x(facility.start_distance_m)},${24 + index * 8})`}><circle r="2.5" /><text x="5" y="2">{String(facility.properties.name ?? facility.source_object_id)} · offset {Math.round(facility.offset_distance_m)}m</text></g>)}
          </g>
          <g className="section-terrain" aria-label="PLATEAU DEM TIN地形">
            {plot.terrainPaths.map((path, index) => <path key={index} d={path} />)}
          </g>
          {counterfactualState !== "baseline" && <text className="section-counterfactual-note" x="660" y="18">{counterfactualState.toUpperCase()} · 建物geometry不変 · 該当route relationのみ比較</text>}
        </svg>
        <footer>
          <span>高さ基準: {data.vertical_datum}</span>
          <span>断面: TIN barycentric / exaggeration 1.0</span>
          <span>直接交差 {data.buildings.filter((item) => item.relation === "direct").length} · 近傍 {data.buildings.filter((item) => item.relation === "nearby").length}</span>
        </footer>
      </>}
    </section>
  );
}
