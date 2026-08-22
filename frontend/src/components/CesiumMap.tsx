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
  Math as CesiumMath,
  PointGraphics,
  ScreenSpaceEventType,
  TileMapServiceImageryProvider,
  Viewer
} from "cesium";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type {
  AppData,
  BuildingInfo,
  GeoJsonFeatureCollection,
  LayerVisibility,
  MeshMetrics,
  MetricMode
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
  placementMode: boolean;
  virtualPoint: VirtualPoint | null;
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
}

const MAIZURU_VIEW = {
  longitude: 135.33,
  latitude: 35.47,
  height: 30_000
};

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
  return {
    id: typeof rawId === "string" ? rawId : String(rawId ?? "IDなし"),
    usage: typeof rawUsage === "string" && rawUsage.trim() ? rawUsage : null,
    measuredHeight: finiteNumber(readAttribute("bldg:measuredHeight")),
    storeysAboveGround: finiteNumber(readAttribute("bldg:storeysAboveGround")),
    storeysBelowGround: finiteNumber(readAttribute("bldg:storeysBelowGround")),
    footprintArea: finiteNumber(read("uro:buildingFootprintArea")) ?? finiteNumber(details["uro:buildingFootprintArea"]),
    totalFloorArea: finiteNumber(read("uro:totalFloorArea")) ?? finiteNumber(details["uro:totalFloorArea"]),
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
    elderly: Color.fromCssColorString("#58b4d1"),
    transport: Color.fromCssColorString("#5c9cd7"),
    medical: Color.fromCssColorString("#8e85d8")
  };
  const ends: Record<MetricMode, Color> = {
    gap: Color.fromCssColorString("#ffae57"),
    elderly: Color.fromCssColorString("#ffb259"),
    transport: Color.fromCssColorString("#f1b45d"),
    medical: Color.fromCssColorString("#efa75b")
  };
  return Color.lerp(starts[mode], ends[mode], normalized, new Color()).withAlpha(0.54);
}

function styleMeshes(dataSource: GeoJsonDataSource, mode: MetricMode, selectedMeshCode: string | null) {
  const values = dataSource.entities.values.map((entity) => modeValue(entityValues(entity), mode));
  const maxGap = mode === "gap" ? Math.max(...values.filter((value): value is number => value !== null), 0.01) : 1;

  for (const entity of dataSource.entities.values) {
    if (!entity.polygon) continue;
    const properties = entityValues(entity);
    const code = String(properties.mesh_code ?? "");
    const value = modeValue(properties, mode);
    const normalized = value === null ? null : value / maxGap;
    const isSelected = selectedMeshCode === code;
    const isTop10 = isTop10Rank(properties.rank);
    const baseColor = normalized === null ? Color.fromCssColorString("#72828a").withAlpha(0.12) : colorScale(normalized, mode);
    entity.polygon.material = new ColorMaterialProperty(
      isSelected ? Color.fromCssColorString("#ffe29a").withAlpha(0.8) : baseColor
    );
    entity.polygon.outline = new ConstantProperty(true);
    entity.polygon.outlineColor = new ConstantProperty(
      isSelected
        ? Color.fromCssColorString("#fff4c9")
        : isTop10
          ? Color.fromCssColorString("#fff0bd")
          : Color.fromCssColorString("#d5f3f1").withAlpha(0.45)
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
      entity.polygon.outlineColor = new ConstantProperty(Color.fromCssColorString("#67e2d6"));
      entity.polygon.outlineWidth = new ConstantProperty(2);
    }
    if (entity.polyline) {
      entity.polyline.material = new ColorMaterialProperty(Color.fromCssColorString("#67e2d6"));
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

function setInitialView(viewer: Viewer) {
  viewer.camera.setView({
    destination: Cartesian3.fromDegrees(MAIZURU_VIEW.longitude, MAIZURU_VIEW.latitude, MAIZURU_VIEW.height),
    orientation: {
      heading: CesiumMath.toRadians(0),
      pitch: CesiumMath.toRadians(-67),
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
    placementMode,
    virtualPoint,
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
  const onMeshSelectRef = useRef(onMeshSelect);
  const onVirtualPointSelectRef = useRef(onVirtualPointSelect);
  const onBuildingSelectRef = useRef(onBuildingSelect);
  const placementModeRef = useRef(placementMode);
  const onReadyRef = useRef(onReady);
  const onErrorRef = useRef(onError);
  const onWarningRef = useRef(onWarning);
  const metricModeRef = useRef(metricMode);
  const selectedMeshCodeRef = useRef(selectedMeshCode);
  const visibilityRef = useRef(visibility);
  onMeshSelectRef.current = onMeshSelect;
  onVirtualPointSelectRef.current = onVirtualPointSelect;
  onBuildingSelectRef.current = onBuildingSelect;
  placementModeRef.current = placementMode;
  onReadyRef.current = onReady;
  onErrorRef.current = onError;
  onWarningRef.current = onWarning;
  metricModeRef.current = metricMode;
  selectedMeshCodeRef.current = selectedMeshCode;
  visibilityRef.current = visibility;

  useImperativeHandle(ref, () => ({
    flyToMesh(mesh) {
      const longitude = finiteNumber(mesh.centroid_lon);
      const latitude = finiteNumber(mesh.centroid_lat);
      if (!viewerRef.current || longitude === null || latitude === null) return;
      viewerRef.current.camera.flyTo({
        destination: Cartesian3.fromDegrees(longitude, latitude, 2_700),
        orientation: {
          heading: CesiumMath.toRadians(2),
          pitch: CesiumMath.toRadians(-52),
          roll: 0
        },
        duration: 1.15
      });
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
      if (viewerRef.current) setInitialView(viewerRef.current);
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
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.scene.globe.baseColor = Color.fromCssColorString("#10282d");
    viewer.scene.backgroundColor = Color.fromCssColorString("#06151b");
    viewer.scene.highDynamicRange = true;
    setInitialView(viewer);

    async function loadLayers() {
      try {
        const localImagery = await TileMapServiceImageryProvider.fromUrl(
          `${import.meta.env.BASE_URL}cesium/Assets/Textures/NaturalEarthII`
        );
        viewer.imageryLayers.addImageryProvider(localImagery);
        const boundary = await addGeoJson(viewer, data.boundary);
        const plateauGeoJson = await addGeoJson(viewer, data.plateauBuildings);
        const plateauRoads = await addGeoJson(viewer, data.plateauRoads);
        const meshes = await addGeoJson(viewer, data.meshes);
        const stations = await addGeoJson(viewer, data.stations);
        const busStops = await addGeoJson(viewer, data.busStops);
        const medical = await addGeoJson(viewer, data.medicalFacilities);
        if (cancelled || viewer.isDestroyed()) return;

        let plateauTileset: Cesium3DTileset | undefined;
        const officialTilesetUrl = tilesetUrl(data);
        if (officialTilesetUrl) {
          try {
            plateauTileset = await Cesium3DTileset.fromUrl(officialTilesetUrl, {
              maximumScreenSpaceError: 12,
              skipLevelOfDetail: false
            });
            plateauTileset.style = new Cesium3DTileStyle({
              color: "color('#eef4f2', 0.98)"
            });
            viewer.scene.primitives.add(plateauTileset);
          } catch (error) {
            console.warn("Optional PLATEAU 3D Tiles loading failed; continuing with core map layers", error);
            onWarningRef.current(
              "PLATEAU 3D建物だけを読み込めませんでした。500mメッシュと施設レイヤーは引き続き操作できます。"
            );
          }
        }
        if (cancelled || viewer.isDestroyed()) return;

        sourcesRef.current = { boundary, plateauGeoJson, plateauRoads, plateauTileset, meshes, stations, busStops, medical };
        styleBoundary(boundary);
        styleBuildings(plateauGeoJson);
        styleRoads(plateauRoads);
        if (meshes) styleMeshes(meshes, metricModeRef.current, selectedMeshCodeRef.current);
        stylePoints(stations, Color.fromCssColorString("#ffd166"), 11);
        stylePoints(busStops, Color.fromCssColorString("#4fd1c5"), 7);
        stylePoints(medical, Color.fromCssColorString("#ff7f91"), 9);

        const currentVisibility = visibilityRef.current;
        if (boundary) boundary.show = currentVisibility.boundary;
        if (plateauGeoJson) plateauGeoJson.show = currentVisibility.plateau;
        if (plateauRoads) plateauRoads.show = currentVisibility.plateau;
        if (plateauTileset) plateauTileset.show = currentVisibility.plateau;
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
    if (sourcesRef.current.meshes) styleMeshes(sourcesRef.current.meshes, metricMode, selectedMeshCode);
    viewerRef.current?.scene.requestRender();
  }, [metricMode, selectedMeshCode]);

  useEffect(() => {
    const sources = sourcesRef.current;
    if (sources.meshes) sources.meshes.show = visibility.meshes;
    if (sources.stations) sources.stations.show = visibility.stations;
    if (sources.busStops) sources.busStops.show = visibility.busStops;
    if (sources.medical) sources.medical.show = visibility.medical;
    if (sources.boundary) sources.boundary.show = visibility.boundary;
    if (sources.plateauGeoJson) sources.plateauGeoJson.show = visibility.plateau;
    if (sources.plateauRoads) sources.plateauRoads.show = visibility.plateau;
    if (sources.plateauTileset) sources.plateauTileset.show = visibility.plateau;
    viewerRef.current?.scene.requestRender();
  }, [visibility]);

  return <div ref={containerRef} className="cesium-map" aria-label="舞鶴市の3D地図" />;
});
