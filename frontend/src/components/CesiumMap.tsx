import {
  Cartesian3,
  Cartesian2,
  BoundingSphere,
  Cartographic,
  Cesium3DTileStyle,
  Cesium3DTileset,
  Color,
  ColorMaterialProperty,
  ConstantProperty,
  EllipsoidTerrainProvider,
  Entity,
  GeoJsonDataSource,
  HeightReference,
  HeadingPitchRange,
  LabelGraphics,
  Math as CesiumMath,
  PointGraphics,
  PointPrimitive,
  PointPrimitiveCollection,
  ScreenSpaceEventType,
  UrlTemplateImageryProvider,
  Viewer
} from "cesium";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";
import type {
  AppData,
  BuildingInfo,
  FuturesStressMode,
  GeoJsonFeatureCollection,
  LayerVisibility,
  MeshMetrics,
  MetricMode,
  InterventionSite,
  WorkspaceLayerVisibility,
  WorkspaceBuildingPoints,
  WorkspaceMapData,
  WorkspacePhase
} from "../types";
import { finiteNumber, isTop10Rank } from "../lib/format";
import type { VirtualPoint } from "../lib/scenario";

export interface CesiumMapHandle {
  flyToMesh: (mesh: MeshMetrics) => void;
  flyToPlateau: () => void;
  resetView: () => void;
}

interface CesiumMapProps {
  data: AppData;
  metricMode: MetricMode;
  selectedMeshCode: string | null;
  visibility: LayerVisibility;
  plateauVisibility?: { buildings: boolean; roads: boolean };
  meshPresentation?: "analysis" | "outline";
  placementMode: boolean;
  virtualPoint: VirtualPoint | null;
  decisionSites: InterventionSite[];
  afterScores: Record<string, number> | null;
  decisionFlow: { meshLongitude: number; meshLatitude: number; siteLongitude: number; siteLatitude: number } | null;
  workspaceMap: WorkspaceMapData | null;
  workspaceBuildingPoints: WorkspaceBuildingPoints | null;
  futuresMap: GeoJsonFeatureCollection | null;
  futuresStressMode: FuturesStressMode;
  workspacePhase: WorkspacePhase;
  workspaceVisibility: WorkspaceLayerVisibility;
  onMeshSelect: (mesh: MeshMetrics) => void;
  onVirtualPointSelect: (point: VirtualPoint) => void;
  onBuildingSelect: (building: BuildingInfo | null) => void;
  onReady: () => void;
  onError: (message: string | null) => void;
  onWarning: (message: string | null) => void;
}

interface DataSourceRefs {
  meshes?: GeoJsonDataSource;
  stations?: GeoJsonDataSource;
  busStops?: GeoJsonDataSource;
  medical?: GeoJsonDataSource;
  boundary?: GeoJsonDataSource;
  plateauGeoJson?: GeoJsonDataSource;
  plateauRoads?: GeoJsonDataSource;
  plateauTileset?: Cesium3DTileset;
  workspace?: GeoJsonDataSource;
  futures?: GeoJsonDataSource;
  workspacePoints?: WorkspacePointRef[];
}

interface WorkspacePointRef {
  point: PointPrimitive;
  storyId: string;
}

function entityValues(entity: Entity): Record<string, unknown> {
  return (entity.properties?.getValue() as Record<string, unknown> | undefined) ?? {};
}

function entityMesh(entity: Entity): MeshMetrics | null {
  const values = entityValues(entity);
  const code = values.mesh_code;
  if (typeof code !== "string" && typeof code !== "number") return null;
  return { ...values, mesh_code: String(code) } as MeshMetrics;
}

interface TileFeatureLike {
  getProperty: (name: string) => unknown;
}

function isTileFeature(value: unknown): value is TileFeatureLike {
  return typeof value === "object" && value !== null &&
    typeof (value as { getProperty?: unknown }).getProperty === "function";
}

function buildingFromFeature(feature: TileFeatureLike): BuildingInfo {
  const read = (name: string) => feature.getProperty(name);
  const rawAttributes = read("attributes");
  const attributes = typeof rawAttributes === "object" && rawAttributes !== null
    ? rawAttributes as Record<string, unknown>
    : {};
  const readAttribute = (name: string) => read(name) ?? attributes[name];
  const rawDetails = attributes["uro:BuildingDetailAttribute"];
  const details = Array.isArray(rawDetails) && typeof rawDetails[0] === "object" && rawDetails[0] !== null
    ? rawDetails[0] as Record<string, unknown>
    : {};
  const rawId = read("gml_id") ?? readAttribute("uro:BuildingIDAttribute_uro:buildingID");
  const rawUsage = readAttribute("bldg:usage");
  const rawLod = read("_lod");
  const boundedNumber = (value: unknown, minimum: number, maximum: number) => {
    const number = finiteNumber(value);
    return number !== null && number >= minimum && number <= maximum ? number : null;
  };
  return {
    id: typeof rawId === "string" ? rawId : String(rawId ?? "IDなし"),
    usage: typeof rawUsage === "string" && rawUsage.trim() ? rawUsage : null,
    measuredHeight: boundedNumber(readAttribute("bldg:measuredHeight"), 0, 500),
    storeysAboveGround: boundedNumber(readAttribute("bldg:storeysAboveGround"), 0, 200),
    storeysBelowGround: boundedNumber(readAttribute("bldg:storeysBelowGround"), 0, 50),
    footprintArea: boundedNumber(read("uro:buildingFootprintArea") ?? details["uro:buildingFootprintArea"], 0, 1_000_000),
    totalFloorArea: boundedNumber(read("uro:totalFloorArea") ?? details["uro:totalFloorArea"], 0, 10_000_000),
    lod: rawLod === null || rawLod === undefined ? null : `LOD${String(rawLod)}`
  };
}

function tilesetUrl(data: AppData): string | null {
  const path = data.plateauMetadata?.reference_layer?.tileset_url;
  if (typeof path !== "string" || !path.trim()) return null;
  const relative = path.replace(/^\/+/, "");
  return `${import.meta.env.BASE_URL}${relative}`;
}

function modeValue(properties: Record<string, unknown>, mode: MetricMode): number | null {
  if (mode === "elderly") return finiteNumber(properties.elderly_population_percentile);
  if (mode === "transport") return finiteNumber(properties.transport_distance_percentile);
  if (mode === "medical") return finiteNumber(properties.medical_distance_percentile);
  return finiteNumber(properties.exploratory_score_c);
}

function colorScale(value: number, mode: MetricMode): Color {
  const normalized = Math.min(1, Math.max(0, value));
  const starts: Record<MetricMode, Color> = {
    gap: Color.fromCssColorString("#39b9b2"),
    elderly: Color.fromCssColorString("#769b8b"),
    transport: Color.fromCssColorString("#50849a"),
    medical: Color.fromCssColorString("#9a7760")
  };
  const ends: Record<MetricMode, Color> = {
    gap: Color.fromCssColorString("#ffae57"),
    elderly: Color.fromCssColorString("#ffb259"),
    transport: Color.fromCssColorString("#f1b45d"),
    medical: Color.fromCssColorString("#efa75b")
  };
  return Color.lerp(starts[mode], ends[mode], normalized, new Color()).withAlpha(0.54);
}

function styledValue(
  properties: Record<string, unknown>,
  mode: MetricMode,
  afterScores: Record<string, number> | null
): number | null {
  const code = String(properties.mesh_code ?? "");
  if (mode === "gap" && afterScores && Object.hasOwn(afterScores, code)) return finiteNumber(afterScores[code]);
  return modeValue(properties, mode);
}

function styleMeshes(
  dataSource: GeoJsonDataSource,
  mode: MetricMode,
  selectedMeshCode: string | null,
  afterScores: Record<string, number> | null,
  presentation: "analysis" | "outline" = "analysis"
) {
  const values = dataSource.entities.values.map((entity) => styledValue(entityValues(entity), mode, afterScores));
  const maxGap = mode === "gap" ? Math.max(...values.filter((value): value is number => value !== null), 0.01) : 1;

  for (const entity of dataSource.entities.values) {
    if (!entity.polygon) continue;
    const properties = entityValues(entity);
    const code = String(properties.mesh_code ?? "");
    const value = styledValue(properties, mode, afterScores);
    const normalized = value === null ? null : value / maxGap;
    const isSelected = selectedMeshCode === code;
    const isTop10 = isTop10Rank(properties.rank);
    const baseColor = presentation === "outline"
      ? Color.fromCssColorString("#7b8c86").withAlpha(0.045)
      : normalized === null ? Color.fromCssColorString("#72828a").withAlpha(0.12) : colorScale(normalized, mode);
    entity.polygon.material = new ColorMaterialProperty(
      isSelected ? Color.fromCssColorString("#e6b64d").withAlpha(presentation === "outline" ? 0.16 : 0.8) : baseColor
    );
    entity.polygon.outline = new ConstantProperty(true);
    entity.polygon.outlineColor = new ConstantProperty(
      isSelected
        ? Color.fromCssColorString(presentation === "outline" ? "#173f3c" : "#fff4c9")
        : isTop10
          ? Color.fromCssColorString(presentation === "outline" ? "#4d7770" : "#fff0bd")
          : Color.fromCssColorString("#53766f").withAlpha(presentation === "outline" ? 0.2 : 0.45)
    );
    entity.polygon.outlineWidth = new ConstantProperty(isSelected ? 4 : isTop10 ? 2 : 1);
  }
}

async function addGeoJson(
  viewer: Viewer,
  collection: GeoJsonFeatureCollection | null,
  options: Parameters<typeof GeoJsonDataSource.load>[1] = {}
): Promise<GeoJsonDataSource | undefined> {
  if (!collection || collection.features.length === 0) return undefined;
  const source = await GeoJsonDataSource.load(collection as object, {
    clampToGround: false,
    ...options
  });
  if (viewer.isDestroyed()) return undefined;
  await viewer.dataSources.add(source);
  return source;
}

function stylePoints(source: GeoJsonDataSource | undefined, color: Color, size: number) {
  if (!source) return;
  for (const entity of source.entities.values) {
    entity.billboard = undefined;
    entity.point = new PointGraphics({
      color,
      pixelSize: size,
      outlineColor: Color.fromCssColorString("#06151b"),
      outlineWidth: 2,
      heightReference: HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: Number.POSITIVE_INFINITY
    });
  }
}

function styleBoundary(source: GeoJsonDataSource | undefined) {
  if (!source) return;
  for (const entity of source.entities.values) {
    if (entity.polygon) {
      entity.polygon.material = new ColorMaterialProperty(Color.TRANSPARENT);
      entity.polygon.outline = new ConstantProperty(true);
      entity.polygon.outlineColor = new ConstantProperty(Color.fromCssColorString("#53766f").withAlpha(0.9));
      entity.polygon.outlineWidth = new ConstantProperty(2);
    }
    if (entity.polyline) {
      entity.polyline.material = new ColorMaterialProperty(Color.fromCssColorString("#53766f").withAlpha(0.9));
      entity.polyline.width = new ConstantProperty(2);
    }
  }
}

function styleBuildings(source: GeoJsonDataSource | undefined) {
  if (!source) return;
  for (const entity of source.entities.values) {
    if (!entity.polygon) continue;
    const values = entityValues(entity);
    const height =
      finiteNumber(values.measuredHeight) ??
      finiteNumber(values.measured_height) ??
      finiteNumber(values.height_m);
    entity.polygon.material = new ColorMaterialProperty(Color.fromCssColorString("#d8dde1").withAlpha(0.72));
    entity.polygon.outline = new ConstantProperty(true);
    entity.polygon.outlineColor = new ConstantProperty(Color.fromCssColorString("#ffffff").withAlpha(0.6));
    if (height !== null && height > 0) entity.polygon.extrudedHeight = new ConstantProperty(height);
  }
}

function styleRoads(source: GeoJsonDataSource | undefined) {
  if (!source) return;
  for (const entity of source.entities.values) {
    if (!entity.polygon) continue;
    entity.polygon.material = new ColorMaterialProperty(Color.fromCssColorString("#f4b860").withAlpha(0.34));
    entity.polygon.outline = new ConstantProperty(true);
    entity.polygon.outlineColor = new ConstantProperty(Color.fromCssColorString("#ffd28a").withAlpha(0.8));
  }
}

function workspaceStoryColor(storyId: string): Color {
  if (storyId === "scenario_b") return Color.fromCssColorString("#a45f2a");
  if (storyId === "scenario_c") return Color.fromCssColorString("#6c5c82");
  return Color.fromCssColorString("#1e6a82");
}

function workspaceBuildingColor(band: string): Color {
  if (band === "500_plus") return Color.fromCssColorString("#164f68");
  if (band === "250_499") return Color.fromCssColorString("#4d8293");
  return Color.fromCssColorString("#91adb5");
}

async function addWorkspacePoints(
  viewer: Viewer,
  collection: WorkspaceBuildingPoints | null,
  storyId: "scenario_a" | "scenario_b" | "scenario_c"
): Promise<WorkspacePointRef[]> {
  if (!collection) return [];
  const primitives = viewer.scene.primitives.add(new PointPrimitiveCollection());
  const points: WorkspacePointRef[] = [];
  const coordinatesList = collection.stories[storyId] ?? [];
  for (const [index, coordinates] of coordinatesList.entries()) {
    if (viewer.isDestroyed()) break;
    if (index > 0 && index % 10 === 0) {
      await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
    }
    const band = collection.band_codes[String(coordinates[2])] ?? "under_250";
    const point = primitives.add({
      position: Cartesian3.fromDegrees(coordinates[0], coordinates[1], 2),
      color: workspaceBuildingColor(band).withAlpha(0.86),
      pixelSize: band === "500_plus" ? 6 : 4,
      outlineColor: Color.fromCssColorString("#f5f7f6").withAlpha(0.78),
      outlineWidth: 1,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      show: false
    });
    points.push({ point, storyId });
  }
  return points;
}

function styleWorkspace(source: GeoJsonDataSource | undefined) {
  if (!source) return;
  for (const entity of source.entities.values) {
    const values = entityValues(entity);
    const layer = String(values.layer_type ?? "");
    const storyId = String(values.story_id ?? "");
    const storyColor = workspaceStoryColor(storyId);
    entity.billboard = undefined;
    if (layer === "scenario_site") {
      const siteOrder = String(values.site_order ?? "");
      entity.point = new PointGraphics({
        color: storyColor,
        pixelSize: 16,
        outlineColor: Color.fromCssColorString("#f7f6f2"),
        outlineWidth: 3,
        heightReference: HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY
      });
      entity.label = new LabelGraphics({
        text: `${storyId === "scenario_b" ? "B" : storyId === "scenario_c" ? "C" : "A"}-${siteOrder}`,
        font: "700 13px sans-serif",
        fillColor: Color.fromCssColorString("#f7f6f2"),
        outlineColor: Color.fromCssColorString("#273238"),
        outlineWidth: 3,
        style: 2,
        pixelOffset: new Cartesian2(0, -25),
        disableDepthTestDistance: Number.POSITIVE_INFINITY
      });
    } else if (layer === "representative_building") {
      entity.point = new PointGraphics({
        color: Color.fromCssColorString("#f2c14d"),
        pixelSize: 11,
        outlineColor: Color.fromCssColorString("#273238"),
        outlineWidth: 3,
        heightReference: HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY
      });
    } else if (layer === "representative_route" && entity.polyline) {
      const isAfter = values.route_kind === "after";
      entity.polyline.material = new ColorMaterialProperty(
        isAfter ? storyColor.withAlpha(0.95) : Color.fromCssColorString("#59666d").withAlpha(0.82)
      );
      entity.polyline.width = new ConstantProperty(isAfter ? 5 : 3);
      entity.polyline.clampToGround = new ConstantProperty(true);
    } else if (entity.polygon) {
      const colors: Record<string, Color> = {
        landuse_context: Color.fromCssColorString("#7d8c58"),
        planning_context: Color.fromCssColorString("#526f91"),
        hazard_context: Color.fromCssColorString("#a4544e")
      };
      const color = colors[layer] ?? Color.fromCssColorString("#78858a");
      entity.polygon.material = new ColorMaterialProperty(color.withAlpha(0.26));
      entity.polygon.outline = new ConstantProperty(true);
      entity.polygon.outlineColor = new ConstantProperty(color.withAlpha(0.84));
      entity.polygon.outlineWidth = new ConstantProperty(2);
    }
  }
}

function setWorkspacePointVisibility(
  points: WorkspacePointRef[] | undefined,
  phase: WorkspacePhase,
  visibility: WorkspaceLayerVisibility
) {
  const activeStory = phase === "scenario_a" || phase === "scenario_b" || phase === "scenario_c" ? phase : null;
  for (const item of points ?? []) {
    item.point.show = visibility.affectedBuildings && item.storyId === activeStory;
  }
}

function setWorkspaceVisibility(
  source: GeoJsonDataSource | undefined,
  phase: WorkspacePhase,
  visibility: WorkspaceLayerVisibility
) {
  if (!source) return;
  const activeStory = phase === "scenario_a" || phase === "scenario_b" || phase === "scenario_c" ? phase : null;
  for (const entity of source.entities.values) {
    const values = entityValues(entity);
    const layer = String(values.layer_type ?? "");
    const isActive = activeStory !== null && values.story_id === activeStory;
    entity.show = isActive && (
      layer === "scenario_site" ||
      (layer === "affected_building" && visibility.affectedBuildings) ||
      ((layer === "representative_route" || layer === "representative_building") && visibility.routes) ||
      (layer === "landuse_context" && visibility.landuse) ||
      (layer === "planning_context" && visibility.planning) ||
      (layer === "hazard_context" && visibility.hazard)
    );
  }
}

function styleFuturesMap(source: GeoJsonDataSource | undefined) {
  if (!source) return;
  for (const entity of source.entities.values) {
    const values = entityValues(entity);
    const layer = String(values.layer_type ?? "");
    entity.billboard = undefined;
    if (entity.polyline) {
      const colors: Record<string, Color> = {
        normal_route: Color.fromCssColorString("#dce8e6"),
        disrupted_route: Color.fromCssColorString("#e7a949"),
        critical_edge: Color.fromCssColorString("#d74d4d")
      };
      entity.polyline.material = new ColorMaterialProperty(
        (colors[layer] ?? Color.fromCssColorString("#8fa3a4")).withAlpha(0.96)
      );
      entity.polyline.width = new ConstantProperty(layer === "critical_edge" ? 8 : 5);
      entity.polyline.clampToGround = new ConstantProperty(true);
      entity.polyline.zIndex = new ConstantProperty(layer === "critical_edge" ? 40 : 30);
    }
    if (layer === "disconnected_area" && entity.polygon) {
      const areaColor = Color.fromCssColorString("#cf5b45");
      entity.polygon.material = new ColorMaterialProperty(areaColor.withAlpha(0.34));
      entity.polygon.outline = new ConstantProperty(true);
      entity.polygon.outlineColor = new ConstantProperty(areaColor.withAlpha(0.96));
      entity.polygon.outlineWidth = new ConstantProperty(3);
      entity.polygon.heightReference = new ConstantProperty(HeightReference.CLAMP_TO_GROUND);
      entity.polygon.zIndex = new ConstantProperty(1);
    }
    if (layer === "affected_facility") {
      entity.point = new PointGraphics({
        color: Color.fromCssColorString("#ff8769"),
        pixelSize: 13,
        outlineColor: Color.fromCssColorString("#441d1b"),
        outlineWidth: 3,
        heightReference: HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY
      });
      entity.label = new LabelGraphics({
        text: String(values.facility_name ?? "medical service destination"),
        font: "700 11px sans-serif",
        fillColor: Color.fromCssColorString("#fff5ef"),
        outlineColor: Color.fromCssColorString("#441d1b"),
        outlineWidth: 3,
        style: 2,
        pixelOffset: new Cartesian2(0, -22),
        disableDepthTestDistance: Number.POSITIVE_INFINITY
      });
    }
  }
}

function setFuturesVisibility(
  source: GeoJsonDataSource | undefined,
  stressMode: FuturesStressMode
): number {
  let visible = 0;
  for (const entity of source?.entities.values ?? []) {
    const featureStressMode = String(entityValues(entity).stress_mode ?? "");
    entity.show = featureStressMode === "all" || featureStressMode === stressMode;
    if (entity.show) visible += 1;
  }
  return visible;
}

function setInitialView(viewer: Viewer, data: AppData) {
  const view = data.city.map_view;
  viewer.camera.setView({
    destination: Cartesian3.fromDegrees(view.longitude, view.latitude, view.height),
    orientation: {
      heading: CesiumMath.toRadians(0),
      pitch: CesiumMath.toRadians(-90),
      roll: 0
    }
  });
}

export const CesiumMap = forwardRef<CesiumMapHandle, CesiumMapProps>(function CesiumMap(
  {
    data,
    metricMode,
    selectedMeshCode,
    visibility,
    plateauVisibility,
    meshPresentation = "analysis",
    placementMode,
    virtualPoint,
    decisionSites,
    afterScores,
    decisionFlow,
    workspaceMap,
    workspaceBuildingPoints,
    futuresMap,
    futuresStressMode,
    workspacePhase,
    workspaceVisibility,
    onMeshSelect,
    onVirtualPointSelect,
    onBuildingSelect,
    onReady,
    onError,
    onWarning
  },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const sourcesRef = useRef<DataSourceRefs>({});
  const plateauLoadRef = useRef<Promise<void> | null>(null);
  const workspacePointLoadRef = useRef<Promise<WorkspacePointRef[]> | null>(null);
  const workspaceSourceLoadRef = useRef<Promise<GeoJsonDataSource | undefined> | null>(null);
  const futuresSourceLoadRef = useRef<Promise<GeoJsonDataSource | undefined> | null>(null);
  const workspaceMapRef = useRef(workspaceMap);
  const futuresMapRef = useRef(futuresMap);
  const onMeshSelectRef = useRef(onMeshSelect);
  const onVirtualPointSelectRef = useRef(onVirtualPointSelect);
  const onBuildingSelectRef = useRef(onBuildingSelect);
  const placementModeRef = useRef(placementMode);
  const onReadyRef = useRef(onReady);
  const onErrorRef = useRef(onError);
  const onWarningRef = useRef(onWarning);
  const metricModeRef = useRef(metricMode);
  const selectedMeshCodeRef = useRef(selectedMeshCode);
  const afterScoresRef = useRef(afterScores);
  const decisionSiteIdsRef = useRef<string[]>([]);
  const visibilityRef = useRef(visibility);
  const plateauVisibilityRef = useRef(plateauVisibility);
  const meshPresentationRef = useRef(meshPresentation);
  const workspacePhaseRef = useRef(workspacePhase);
  const workspaceVisibilityRef = useRef(workspaceVisibility);
  const futuresStressModeRef = useRef(futuresStressMode);
  onMeshSelectRef.current = onMeshSelect;
  onVirtualPointSelectRef.current = onVirtualPointSelect;
  onBuildingSelectRef.current = onBuildingSelect;
  placementModeRef.current = placementMode;
  onReadyRef.current = onReady;
  onErrorRef.current = onError;
  onWarningRef.current = onWarning;
  metricModeRef.current = metricMode;
  selectedMeshCodeRef.current = selectedMeshCode;
  afterScoresRef.current = afterScores;
  visibilityRef.current = visibility;
  plateauVisibilityRef.current = plateauVisibility;
  meshPresentationRef.current = meshPresentation;
  workspacePhaseRef.current = workspacePhase;
  workspaceVisibilityRef.current = workspaceVisibility;
  workspaceMapRef.current = workspaceMap;
  futuresMapRef.current = futuresMap;
  futuresStressModeRef.current = futuresStressMode;

  const loadPlateauTileset = useCallback(() => {
    if (sourcesRef.current.plateauTileset || plateauLoadRef.current) {
      return plateauLoadRef.current ?? Promise.resolve();
    }
    const viewer = viewerRef.current;
    const officialTilesetUrl = tilesetUrl(data);
    if (!viewer || viewer.isDestroyed() || !officialTilesetUrl) return Promise.resolve();
    plateauLoadRef.current = (async () => {
      try {
        const tileset = await Cesium3DTileset.fromUrl(officialTilesetUrl, {
          maximumScreenSpaceError: 12,
          skipLevelOfDetail: false
        });
        if (viewer.isDestroyed()) return;
        tileset.style = new Cesium3DTileStyle({
          color: "color('#eef4f2', 0.98)"
        });
        viewer.scene.primitives.add(tileset);
        tileset.show = (plateauVisibilityRef.current?.buildings ?? visibilityRef.current.plateau) || (
          workspaceMap !== null && workspaceVisibilityRef.current.plateauBuildings
        );
        sourcesRef.current.plateauTileset = tileset;
        viewer.scene.requestRender();
      } catch (error) {
        console.warn("Optional PLATEAU 3D Tiles loading failed; continuing with core map layers", error);
        onWarningRef.current(
          "PLATEAU 3D建物だけを読み込めませんでした。500mメッシュと施設レイヤーは引き続き操作できます。"
        );
      } finally {
        plateauLoadRef.current = null;
      }
    })();
    return plateauLoadRef.current;
  }, [data, workspaceMap]);

  useImperativeHandle(ref, () => ({
    flyToMesh(mesh) {
      const longitude = finiteNumber(mesh.centroid_lon);
      const latitude = finiteNumber(mesh.centroid_lat);
      if (!viewerRef.current || longitude === null || latitude === null) return;
      viewerRef.current.camera.flyToBoundingSphere(
        new BoundingSphere(Cartesian3.fromDegrees(longitude, latitude, 0), 380),
        { offset: new HeadingPitchRange(CesiumMath.toRadians(8), CesiumMath.toRadians(-48), 2_700), duration: 1.15 }
      );
    },
    flyToPlateau() {
      const viewer = viewerRef.current;
      const tileset = sourcesRef.current.plateauTileset;
      const viewpoint = data.plateauMetadata?.reference_layer?.viewpoint;
      const longitude = finiteNumber(viewpoint?.longitude);
      const latitude = finiteNumber(viewpoint?.latitude);
      const range = finiteNumber(viewpoint?.height) ?? 520;
      if (viewer && longitude !== null && latitude !== null) {
        viewer.camera.flyToBoundingSphere(
          new BoundingSphere(Cartesian3.fromDegrees(longitude, latitude, 0), 120),
          {
          offset: new HeadingPitchRange(
            CesiumMath.toRadians(14),
            CesiumMath.toRadians(-34),
            range
          ),
          duration: 1.35
          }
        );
      } else if (viewer && tileset) {
        void viewer.flyTo(tileset, { duration: 1.35 });
      }
    },
    resetView() {
      if (viewerRef.current) setInitialView(viewerRef.current, data);
    }
  }));

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let cancelled = false;
    onErrorRef.current(null);
    onWarningRef.current(null);

    let viewer: Viewer;
    try {
      viewer = new Viewer(container, {
        baseLayer: false,
        terrainProvider: new EllipsoidTerrainProvider(),
        animation: false,
        timeline: false,
        geocoder: false,
        homeButton: false,
        navigationHelpButton: false,
        sceneModePicker: false,
        baseLayerPicker: false,
        fullscreenButton: false,
        selectionIndicator: false,
        infoBox: false,
        shouldAnimate: false,
        requestRenderMode: true,
        maximumRenderTimeChange: Number.POSITIVE_INFINITY
      });
    } catch (error) {
      console.error("Cesium viewer initialization failed", error);
      container.replaceChildren();
      onErrorRef.current("3D地図を初期化できませんでした。WebGLが利用できるブラウザ環境で再度お試しください。");
      onReadyRef.current();
      return;
    }
    viewerRef.current = viewer;
    (window as Window & { __cityGapCesiumViewer?: Viewer }).__cityGapCesiumViewer = viewer;
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.scene.globe.baseColor = Color.fromCssColorString("#d8dfda");
    viewer.scene.backgroundColor = Color.fromCssColorString("#dfe5e1");
    viewer.scene.highDynamicRange = true;
    setInitialView(viewer, data);

    async function loadLayers() {
      try {
        const paleImagery = new UrlTemplateImageryProvider({
          url: "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png",
          minimumLevel: 5,
          maximumLevel: 18,
          credit: "地理院タイル"
        });
        viewer.imageryLayers.addImageryProvider(paleImagery);
        const boundary = await addGeoJson(viewer, data.boundary);
        const plateauGeoJson = await addGeoJson(viewer, data.plateauBuildings);
        const plateauRoads = await addGeoJson(viewer, data.plateauRoads);
        const meshes = await addGeoJson(viewer, data.meshes);
        const stations = await addGeoJson(viewer, data.stations);
        const busStops = await addGeoJson(viewer, data.busStops);
        const medical = await addGeoJson(viewer, data.medicalFacilities);
        if (cancelled || viewer.isDestroyed()) return;

        if (cancelled || viewer.isDestroyed()) return;

        sourcesRef.current = { ...sourcesRef.current, boundary, plateauGeoJson, plateauRoads, meshes, stations, busStops, medical };
        styleBoundary(boundary);
        styleBuildings(plateauGeoJson);
        styleRoads(plateauRoads);
        if (meshes) styleMeshes(meshes, metricModeRef.current, selectedMeshCodeRef.current, afterScoresRef.current, meshPresentationRef.current);
        stylePoints(stations, Color.fromCssColorString("#d5a43c"), 11);
        stylePoints(busStops, Color.fromCssColorString("#28766f"), 7);
        stylePoints(medical, Color.fromCssColorString("#a64f3f"), 9);

        const currentVisibility = visibilityRef.current;
        if (boundary) boundary.show = currentVisibility.boundary;
        if (plateauGeoJson) plateauGeoJson.show = (plateauVisibilityRef.current?.buildings ?? currentVisibility.plateau) || (workspaceMapRef.current !== null && workspaceVisibilityRef.current.plateauBuildings);
        if (plateauRoads) plateauRoads.show = (plateauVisibilityRef.current?.roads ?? currentVisibility.plateau) || (workspaceMapRef.current !== null && workspaceVisibilityRef.current.roadNetwork);
        if (meshes) meshes.show = currentVisibility.meshes;
        if (stations) stations.show = currentVisibility.stations;
        if (busStops) busStops.show = currentVisibility.busStops;
        if (medical) medical.show = currentVisibility.medical;
        viewer.scene.requestRender();
        onReadyRef.current();
      } catch (error) {
        console.error("Cesium layer loading failed", error);
        if (!cancelled) {
          onErrorRef.current("3D地図のデータを読み込めませんでした。通信状態を確認して再読み込みしてください。");
          onReadyRef.current();
        }
      }
    }

    void loadLayers();

    viewer.screenSpaceEventHandler.setInputAction((movement: { position: Cartesian2 }) => {
      if (placementModeRef.current) {
        const cartesian = viewer.camera.pickEllipsoid(movement.position, viewer.scene.globe.ellipsoid);
        if (!cartesian) return;
        const coordinate = Cartographic.fromCartesian(cartesian);
        onVirtualPointSelectRef.current({
          longitude: CesiumMath.toDegrees(coordinate.longitude),
          latitude: CesiumMath.toDegrees(coordinate.latitude)
        });
        return;
      }
      const drilled = viewer.scene.drillPick(movement.position, 20) as Array<({ id?: Entity } & Partial<TileFeatureLike>)>;
      const building = drilled.find(isTileFeature);
      if (building) {
        onBuildingSelectRef.current(buildingFromFeature(building));
        return;
      }
      const picked = drilled[0] ?? viewer.scene.pick(movement.position) as ({ id?: Entity } & Partial<TileFeatureLike>) | undefined;
      if (!picked?.id) return;
      const mesh = entityMesh(picked.id);
      if (mesh) onMeshSelectRef.current(mesh);
    }, ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      cancelled = true;
      sourcesRef.current = {};
      viewerRef.current = null;
      delete (window as Window & { __cityGapCesiumViewer?: Viewer }).__cityGapCesiumViewer;
      if (!viewer.isDestroyed()) viewer.destroy();
    };
  }, [data]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    (viewer.container as HTMLElement).style.cursor = placementMode ? "crosshair" : "default";
  }, [placementMode]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    const markerId = "city-gap-virtual-transport-point";
    viewer.entities.removeById(markerId);
    if (!virtualPoint) {
      viewer.scene.requestRender();
      return;
    }
    viewer.entities.add({
      id: markerId,
      name: "仮想交通支援拠点",
      position: Cartesian3.fromDegrees(virtualPoint.longitude, virtualPoint.latitude, 8),
      point: {
        pixelSize: 18,
        color: Color.fromCssColorString("#ffcf5c"),
        outlineColor: Color.fromCssColorString("#06151b"),
        outlineWidth: 4,
        disableDepthTestDistance: Number.POSITIVE_INFINITY
      },
      label: {
        text: "仮想交通支援拠点",
        font: "600 14px sans-serif",
        fillColor: Color.WHITE,
        outlineColor: Color.fromCssColorString("#06151b"),
        outlineWidth: 4,
        style: 2,
        pixelOffset: new Cartesian2(0, -28),
        disableDepthTestDistance: Number.POSITIVE_INFINITY
      }
    });
    viewer.scene.requestRender();
  }, [virtualPoint]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    for (const id of decisionSiteIdsRef.current) viewer.entities.removeById(id);
    decisionSiteIdsRef.current = decisionSites.map((site) => {
      const id = `city-gap-decision-site-${site.candidate_id}`;
      viewer.entities.add({
        id,
        name: `施策候補 ${site.site_order}`,
        position: Cartesian3.fromDegrees(site.longitude, site.latitude, 10),
        point: {
          pixelSize: 17,
          color: Color.fromCssColorString("#d39b31"),
          outlineColor: Color.fromCssColorString("#262c2b"),
          outlineWidth: 4,
          disableDepthTestDistance: Number.POSITIVE_INFINITY
        },
        label: {
          text: `候補 ${site.site_order}`,
          font: "700 13px sans-serif",
          fillColor: Color.fromCssColorString("#fffdf7"),
          outlineColor: Color.fromCssColorString("#262c2b"),
          outlineWidth: 4,
          style: 2,
          pixelOffset: new Cartesian2(0, -27),
          disableDepthTestDistance: Number.POSITIVE_INFINITY
        }
      });
      return id;
    });
    viewer.scene.requestRender();
  }, [decisionSites]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    const id = "city-gap-decision-flow";
    viewer.entities.removeById(id);
    if (decisionFlow) {
      viewer.entities.add({
        id,
        name: "選択meshの直線距離計算対応",
        polyline: {
          positions: Cartesian3.fromDegreesArray([
            decisionFlow.meshLongitude,
            decisionFlow.meshLatitude,
            decisionFlow.siteLongitude,
            decisionFlow.siteLatitude
          ]),
          width: 2,
          material: Color.fromCssColorString("#a87723").withAlpha(0.82),
          clampToGround: false
        }
      });
    }
    viewer.scene.requestRender();
  }, [decisionFlow]);

  useEffect(() => {
    if (sourcesRef.current.meshes) styleMeshes(sourcesRef.current.meshes, metricMode, selectedMeshCode, afterScores, meshPresentation);
    viewerRef.current?.scene.requestRender();
  }, [afterScores, meshPresentation, metricMode, selectedMeshCode]);

  useEffect(() => {
    const sources = sourcesRef.current;
    if (sources.meshes) sources.meshes.show = visibility.meshes;
    if (sources.stations) sources.stations.show = visibility.stations;
    if (sources.busStops) sources.busStops.show = visibility.busStops;
    if (sources.medical) sources.medical.show = visibility.medical;
    if (sources.boundary) sources.boundary.show = visibility.boundary;
    const workspaceBuildings = workspaceMap !== null && workspaceVisibility.plateauBuildings;
    const workspaceRoads = workspaceMap !== null && workspaceVisibility.roadNetwork;
    const plateauBuildings = plateauVisibility?.buildings ?? visibility.plateau;
    const plateauRoads = plateauVisibility?.roads ?? visibility.plateau;
    if (sources.plateauGeoJson) sources.plateauGeoJson.show = plateauBuildings || workspaceBuildings;
    if (sources.plateauRoads) sources.plateauRoads.show = plateauRoads || workspaceRoads;
    if (sources.plateauTileset) sources.plateauTileset.show = plateauBuildings || workspaceBuildings;
    if ((plateauBuildings || workspaceBuildings) && !sources.plateauTileset) void loadPlateauTileset();
    viewerRef.current?.scene.requestRender();
  }, [loadPlateauTileset, plateauVisibility, visibility, workspaceMap, workspaceVisibility]);

  useEffect(() => {
    setWorkspaceVisibility(sourcesRef.current.workspace, workspacePhase, workspaceVisibility);
    setWorkspacePointVisibility(sourcesRef.current.workspacePoints, workspacePhase, workspaceVisibility);
    viewerRef.current?.scene.requestRender();
  }, [workspacePhase, workspaceVisibility]);

  useEffect(() => {
    const visible = setFuturesVisibility(sourcesRef.current.futures, futuresStressMode);
    if (sourcesRef.current.futures) {
      containerRef.current?.setAttribute("data-futures-visible", String(visible));
    }
    viewerRef.current?.scene.requestRender();
  }, [futuresStressMode]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    if (!futuresMap) {
      if (sourcesRef.current.futures) sourcesRef.current.futures.show = false;
      containerRef.current?.setAttribute("data-futures-map", "idle");
      containerRef.current?.setAttribute("data-futures-visible", "0");
      viewer.scene.requestRender();
      return;
    }
    if (sourcesRef.current.futures) {
      sourcesRef.current.futures.show = true;
      const visible = setFuturesVisibility(
        sourcesRef.current.futures,
        futuresStressModeRef.current
      );
      containerRef.current?.setAttribute("data-futures-map", "ready");
      containerRef.current?.setAttribute("data-futures-visible", String(visible));
      viewer.scene.requestRender();
      return;
    }
    if (futuresSourceLoadRef.current) return;
    containerRef.current?.setAttribute("data-futures-map", "loading");
    futuresSourceLoadRef.current = addGeoJson(viewer, futuresMap);
    void futuresSourceLoadRef.current
      .then((source) => {
        if (!viewer.isDestroyed() && source) {
          sourcesRef.current.futures = source;
          styleFuturesMap(source);
          source.show = futuresMapRef.current !== null;
          const visible = setFuturesVisibility(source, futuresStressModeRef.current);
          containerRef.current?.setAttribute("data-futures-map", "ready");
          containerRef.current?.setAttribute("data-futures-visible", String(visible));
          viewer.scene.requestRender();
        }
      })
      .catch((error: unknown) => {
        console.warn("Urban futures map rendering failed", error);
        containerRef.current?.setAttribute("data-futures-map", "error");
        onWarningRef.current("時間・レジリエンスの集約地図を描画できませんでした。");
      })
      .finally(() => {
        futuresSourceLoadRef.current = null;
      });
  }, [futuresMap]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    if (!workspaceMap) {
      if (sourcesRef.current.workspace) sourcesRef.current.workspace.show = false;
      for (const item of sourcesRef.current.workspacePoints ?? []) item.point.show = false;
      viewer.scene.requestRender();
      return;
    }
    if (sourcesRef.current.workspace) {
      sourcesRef.current.workspace.show = true;
      setWorkspaceVisibility(
        sourcesRef.current.workspace,
        workspacePhaseRef.current,
        workspaceVisibilityRef.current
      );
      viewer.scene.requestRender();
      return;
    }
    if (workspaceSourceLoadRef.current) return;
    const workspaceGeometry = {
      ...workspaceMap,
      features: workspaceMap.features.filter(
        (feature) => feature.properties?.layer_type !== "affected_building"
      )
    };
    workspaceSourceLoadRef.current = addGeoJson(viewer, workspaceGeometry);
    void workspaceSourceLoadRef.current.then((source) => {
      if (!viewer.isDestroyed() && source) {
        sourcesRef.current.workspace = source;
        styleWorkspace(source);
        source.show = workspaceMapRef.current !== null;
        setWorkspaceVisibility(
          source,
          workspacePhaseRef.current,
          workspaceVisibilityRef.current
        );
        viewer.scene.requestRender();
      }
      workspaceSourceLoadRef.current = null;
    });
  }, [workspaceMap]);

  useEffect(() => {
    const viewer = viewerRef.current;
    const activeScenario = workspacePhase === "scenario_a" || workspacePhase === "scenario_b" || workspacePhase === "scenario_c";
    if (
      !viewer ||
      viewer.isDestroyed() ||
      !workspaceBuildingPoints ||
      !workspaceVisibility.affectedBuildings ||
      !activeScenario ||
      sourcesRef.current.workspacePoints?.some((item) => item.storyId === workspacePhase) ||
      workspacePointLoadRef.current
    ) return;
    containerRef.current?.setAttribute("data-workspace-points", "loading");
    workspacePointLoadRef.current = new Promise((resolve) => {
      window.setTimeout(
        () => resolve(addWorkspacePoints(viewer, workspaceBuildingPoints, workspacePhase)),
        100
      );
    });
    void workspacePointLoadRef.current
      .then((points) => {
        if (!viewer.isDestroyed()) {
          sourcesRef.current.workspacePoints = [
            ...(sourcesRef.current.workspacePoints ?? []),
            ...points
          ];
          setWorkspacePointVisibility(
            sourcesRef.current.workspacePoints,
            workspacePhaseRef.current,
            workspaceVisibilityRef.current
          );
          viewer.scene.requestRender();
        }
        containerRef.current?.setAttribute("data-workspace-points", "ready");
      })
      .catch((error: unknown) => {
        console.warn("Workspace building point rendering failed", error);
        containerRef.current?.setAttribute("data-workspace-points", "error");
        onWarningRef.current("改善対象建物の点レイヤーを描画できませんでした。");
      })
      .finally(() => {
        workspacePointLoadRef.current = null;
      });
  }, [workspaceBuildingPoints, workspacePhase, workspaceVisibility]);

  return <div ref={containerRef} className="cesium-map" aria-label="舞鶴市の3D地図" />;
});
