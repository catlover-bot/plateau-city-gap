import { Cartesian3, Color, PointPrimitiveCollection, Viewer } from "cesium";
import type { ServicePulseRoute } from "./servicePulse";

export interface ServicePulseRenderer {
  markerCount: number;
  dispose(): void;
}

export function servicePulseMarkerPlan(route: ServicePulseRoute | null, reducedMotion: boolean) {
  return {
    staticDistanceBandCount: route?.distanceBandsM.length ?? 0,
    animatedMarkerCount: route && !reducedMotion ? 1 : 0,
    semantics: "network-distance-only" as const,
  };
}

function pathLengths(coordinates: Array<[number, number]>): number[] {
  const lengths = [0];
  for (let index = 1; index < coordinates.length; index += 1) {
    const previous = coordinates[index - 1];
    const current = coordinates[index];
    const longitudeScale = Math.cos((current[1] * Math.PI) / 180) * 111_320;
    lengths.push(lengths[index - 1] + Math.hypot((current[0] - previous[0]) * longitudeScale, (current[1] - previous[1]) * 111_320));
  }
  return lengths;
}

function positionAt(route: ServicePulseRoute, ratio: number): Cartesian3 {
  const lengths = pathLengths(route.coordinates);
  const total = lengths[lengths.length - 1] || 1;
  const target = Math.max(0, Math.min(1, ratio)) * total;
  let index = lengths.findIndex((length) => length >= target);
  if (index <= 0) index = 1;
  const start = route.coordinates[index - 1];
  const end = route.coordinates[index] ?? start;
  const span = Math.max(0.000001, lengths[index] - lengths[index - 1]);
  const local = (target - lengths[index - 1]) / span;
  return Cartesian3.fromDegrees(
    start[0] + (end[0] - start[0]) * local,
    start[1] + (end[1] - start[1]) * local,
    6,
  );
}

export function renderServicePulse(
  viewer: Viewer,
  route: ServicePulseRoute | null,
  reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches,
): ServicePulseRenderer {
  const collection = viewer.scene.primitives.add(new PointPrimitiveCollection());
  let frame = 0;
  let disposed = false;
  if (!route) return { markerCount: 0, dispose: () => viewer.scene.primitives.remove(collection) };
  const markerPlan = servicePulseMarkerPlan(route, reducedMotion);
  const routePositions = route.coordinates.map(([longitude, latitude]) => Cartesian3.fromDegrees(longitude, latitude, 25));
  const routeCasing = viewer.entities.add({
    id: "city-gap-service-pulse-route-casing",
    polyline: { positions: routePositions, width: 7, clampToGround: false, material: Color.fromCssColorString("#f4f0e5").withAlpha(0.96), depthFailMaterial: Color.fromCssColorString("#f4f0e5").withAlpha(0.96) },
  });
  const routeLine = viewer.entities.add({
    id: "city-gap-service-pulse-route",
    polyline: { positions: routePositions, width: 4, clampToGround: false, material: Color.fromCssColorString("#d08d32").withAlpha(0.98), depthFailMaterial: Color.fromCssColorString("#d08d32").withAlpha(0.98) },
  });

  route.distanceBandsM.forEach((distanceM) => collection.add({
    position: positionAt(route, distanceM / route.networkDistanceM),
    pixelSize: distanceM === route.networkDistanceM ? 10 : 7,
    color: Color.fromCssColorString(distanceM === route.networkDistanceM ? "#b85c3e" : "#315f68").withAlpha(0.95),
    outlineColor: Color.fromCssColorString("#f4f0e5"),
    outlineWidth: 2,
    disableDepthTestDistance: Number.POSITIVE_INFINITY,
  }));
  const pulse = reducedMotion ? null : collection.add({
    position: positionAt(route, 0),
    pixelSize: 12,
    color: Color.fromCssColorString("#f2b544"),
    outlineColor: Color.fromCssColorString("#243235"),
    outlineWidth: 2,
    disableDepthTestDistance: Number.POSITIVE_INFINITY,
  });

  const started = performance.now();
  const tick = (time: number) => {
    if (disposed || !pulse || viewer.isDestroyed()) return;
    const ratio = ((time - started) % 3200) / 3200;
    pulse.position = positionAt(route, ratio);
    viewer.scene.requestRender();
    frame = requestAnimationFrame(tick);
  };
  if (pulse) frame = requestAnimationFrame(tick);
  viewer.scene.requestRender();
  return {
    markerCount: markerPlan.staticDistanceBandCount + markerPlan.animatedMarkerCount,
    dispose() {
      disposed = true;
      if (frame) cancelAnimationFrame(frame);
      if (!viewer.isDestroyed()) {
        viewer.scene.primitives.remove(collection);
        viewer.entities.remove(routeLine);
        viewer.entities.remove(routeCasing);
      }
    },
  };
}
