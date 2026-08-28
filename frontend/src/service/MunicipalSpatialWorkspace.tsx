import { useEffect, useMemo, useRef } from "react";
import {
  AttributionControl,
  GeoJSONSource,
  LngLatBounds,
  Map as MapLibreMap,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type MapLayerMouseEvent,
  type StyleSpecification,
} from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

export interface MunicipalViewport {
  longitude: number;
  latitude: number;
  zoom: number;
}

export interface MunicipalSpatialEntity {
  entity_type: string;
  entity_id: string;
  label: string;
  source?: string;
  source_year?: number | null;
  geometry?: { type: string; coordinates: unknown } | null;
}

interface Props {
  entities: MunicipalSpatialEntity[];
  viewport: MunicipalViewport;
  visibleEntityTypes: string[];
  onViewportChange(viewport: MunicipalViewport): void;
  onVisibleEntityTypesChange(types: string[]): void;
  onEntitySelect?(entityId: string): void;
}

const EMPTY = { type: "FeatureCollection", features: [] };
const GSI_ATTRIBUTION =
  '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noreferrer">地理院タイル</a>';
const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    "gsi-pale": {
      type: "raster",
      tiles: ["https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png"],
      tileSize: 256,
      minzoom: 5,
      maxzoom: 18,
      attribution: GSI_ATTRIBUTION,
    },
  },
  layers: [
    {
      id: "municipal-map-background",
      type: "background",
      paint: { "background-color": "#e9ebe7" },
    },
    {
      id: "gsi-pale",
      type: "raster",
      source: "gsi-pale",
      paint: {
        "raster-opacity": 0.78,
        "raster-saturation": -0.72,
        "raster-contrast": -0.08,
      },
    },
  ],
};

setWorkerUrl(maplibreWorkerUrl);

function entityCollection(entities: MunicipalSpatialEntity[]) {
  return {
    type: "FeatureCollection",
    features: entities
      .filter((entity) => entity.geometry)
      .map((entity) => ({
        type: "Feature",
        id: entity.entity_id,
        geometry: entity.geometry,
        properties: {
          entity_type: entity.entity_type,
          entity_id: entity.entity_id,
          label: entity.label,
          source: entity.source ?? "",
          source_year: entity.source_year ?? null,
        },
      })),
  };
}

function visitCoordinates(
  value: unknown,
  visit: (longitude: number, latitude: number) => void,
) {
  if (!Array.isArray(value)) return;
  if (
    value.length >= 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number"
  ) {
    visit(value[0], value[1]);
    return;
  }
  value.forEach((child) => visitCoordinates(child, visit));
}

function typeFilter(types: string[]): unknown[] {
  return [
    "in",
    ["get", "entity_type"],
    ["literal", types.length ? types : ["__none__"]],
  ];
}

export function MunicipalSpatialWorkspace({
  entities,
  viewport,
  visibleEntityTypes,
  onViewportChange,
  onVisibleEntityTypesChange,
  onEntitySelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const viewportCallback = useRef(onViewportChange);
  const selectionCallback = useRef(onEntitySelect);
  const visibleTypesRef = useRef(visibleEntityTypes);
  viewportCallback.current = onViewportChange;
  selectionCallback.current = onEntitySelect;
  visibleTypesRef.current = visibleEntityTypes;
  const collection = useMemo(() => entityCollection(entities), [entities]);
  const entityTypes = useMemo(
    () => [...new Set(entities.map((entity) => entity.entity_type))].sort(),
    [entities],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: BASE_STYLE,
      center: [viewport.longitude, viewport.latitude],
      zoom: viewport.zoom,
      attributionControl: false,
      cooperativeGestures: true,
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.addControl(
      new ScaleControl({ unit: "metric", maxWidth: 100 }),
      "bottom-left",
    );
    map.addControl(
      new AttributionControl({ compact: true, customAttribution: "CITY GAP" }),
      "bottom-right",
    );
    const canvas = map.getCanvas();
    canvas.tabIndex = 0;
    canvas.setAttribute("role", "application");
    canvas.setAttribute(
      "aria-label",
      "調査対象の空間地図。矢印キーで移動し、プラスとマイナスで拡大縮小できます",
    );
    map.on("load", () => {
      map.addSource("municipal-case-entities", {
        type: "geojson",
        data: (collection.features.length ? collection : EMPTY) as never,
      });
      const filter = typeFilter(visibleTypesRef.current) as never;
      map.addLayer({
        id: "municipal-case-polygons",
        type: "fill",
        source: "municipal-case-entities",
        filter: ["all", ["==", ["geometry-type"], "Polygon"], filter],
        paint: { "fill-color": "#397b72", "fill-opacity": 0.28 },
      });
      map.addLayer({
        id: "municipal-case-polygon-outline",
        type: "line",
        source: "municipal-case-entities",
        filter: ["all", ["==", ["geometry-type"], "Polygon"], filter],
        paint: { "line-color": "#1e514c", "line-width": 2 },
      });
      map.addLayer({
        id: "municipal-case-lines",
        type: "line",
        source: "municipal-case-entities",
        filter: ["all", ["==", ["geometry-type"], "LineString"], filter],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#9a672b", "line-width": 4 },
      });
      map.addLayer({
        id: "municipal-case-points",
        type: "circle",
        source: "municipal-case-entities",
        filter: ["all", ["==", ["geometry-type"], "Point"], filter],
        paint: {
          "circle-color": "#9a5746",
          "circle-radius": 7,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "municipal-case-labels",
        type: "symbol",
        source: "municipal-case-entities",
        minzoom: 12,
        filter,
        layout: {
          "text-field": ["get", "label"],
          "text-size": 11,
          "text-offset": [0, 1.25],
          "text-anchor": "top",
        },
        paint: {
          "text-color": "#173b39",
          "text-halo-color": "#ffffff",
          "text-halo-width": 1.5,
        },
      });
      const bounds = new LngLatBounds();
      entities.forEach((entity) =>
        visitCoordinates(entity.geometry?.coordinates, (longitude, latitude) =>
          bounds.extend([longitude, latitude]),
        ),
      );
      if (!bounds.isEmpty())
        map.fitBounds(bounds, { padding: 54, maxZoom: 15, duration: 0 });
      for (const layer of [
        "municipal-case-polygons",
        "municipal-case-lines",
        "municipal-case-points",
      ]) {
        map.on("click", layer, select);
      }
    });
    const select = (event: MapLayerMouseEvent) => {
      const entityId = event.features?.[0]?.properties?.entity_id;
      if (entityId) selectionCallback.current?.(String(entityId));
    };
    map.on("moveend", () => {
      const center = map.getCenter();
      viewportCallback.current({
        longitude: center.lng,
        latitude: center.lat,
        zoom: map.getZoom(),
      });
    });
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // The map engine is intentionally created once; data and controls update below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const source = mapRef.current?.getSource("municipal-case-entities");
    if (source instanceof GeoJSONSource) source.setData(collection as never);
  }, [collection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    const filter = typeFilter(visibleEntityTypes) as never;
    for (const layer of [
      "municipal-case-polygons",
      "municipal-case-polygon-outline",
      "municipal-case-lines",
      "municipal-case-points",
      "municipal-case-labels",
    ]) {
      if (map.getLayer(layer)) {
        const geometry = layer.includes("polygon")
          ? ["==", ["geometry-type"], "Polygon"]
          : layer.includes("lines")
            ? ["==", ["geometry-type"], "LineString"]
            : layer.includes("points")
              ? ["==", ["geometry-type"], "Point"]
              : null;
        map.setFilter(
          layer,
          (geometry ? ["all", geometry, filter] : filter) as never,
        );
      }
    }
  }, [visibleEntityTypes]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const center = map.getCenter();
    if (
      Math.abs(center.lng - viewport.longitude) > 0.0001 ||
      Math.abs(center.lat - viewport.latitude) > 0.0001 ||
      Math.abs(map.getZoom() - viewport.zoom) > 0.1
    ) {
      map.jumpTo({
        center: [viewport.longitude, viewport.latitude],
        zoom: viewport.zoom,
      });
    }
  }, [viewport]);

  const toggleType = (entityType: string) => {
    onVisibleEntityTypesChange(
      visibleEntityTypes.includes(entityType)
        ? visibleEntityTypes.filter((candidate) => candidate !== entityType)
        : [...visibleEntityTypes, entityType],
    );
  };

  return (
    <section
      className="municipal-spatial-workspace"
      data-entity-count={entities.length}
    >
      <header>
        <div>
          <span>SPATIAL WORKSPACE</span>
          <h3>調査対象と空間文脈</h3>
        </div>
        <div className="municipal-layer-controls" aria-label="空間レイヤー">
          {entityTypes.map((entityType) => (
            <label key={entityType}>
              <input
                type="checkbox"
                checked={visibleEntityTypes.includes(entityType)}
                onChange={() => toggleType(entityType)}
              />
              {entityType.replaceAll("_", " ")}
            </label>
          ))}
        </div>
      </header>
      <div ref={containerRef} className="municipal-spatial-map" />
      <p className="service-muted">
        地理院タイル上に、このInvestigationへ保存された実在entityだけを表示します。
      </p>
      <ul className="screen-reader-map-summary">
        {entities.map((entity) => (
          <li key={`${entity.entity_type}-${entity.entity_id}`}>
            {entity.label}（{entity.entity_type} /{" "}
            {entity.source ?? "出典未記載"}）
          </li>
        ))}
      </ul>
    </section>
  );
}
