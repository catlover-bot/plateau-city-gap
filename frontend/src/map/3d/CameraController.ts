import {
  BoundingSphere,
  Cartesian3,
  HeadingPitchRange,
  Math as CesiumMath,
  Viewer
} from "cesium";
import type { AppData, MeshMetrics } from "../../types";
import { finiteNumber } from "../../lib/format";

export type CameraIntent = "city" | "mesh" | "building" | "route" | "hazard" | "scenario";

const CAMERA = {
  city: { heading: 0, pitch: -82, range: 18_000, duration: 0 },
  mesh: { heading: 8, pitch: -48, range: 2_700, duration: 1.15 },
  building: { heading: 24, pitch: -36, range: 520, duration: 1.15 },
  route: { heading: 18, pitch: -42, range: 1_450, duration: 1.2 },
  hazard: { heading: 0, pitch: -62, range: 2_600, duration: 1.2 },
  scenario: { heading: 16, pitch: -46, range: 1_150, duration: 1.2 }
} as const;

function flyTo(
  viewer: Viewer,
  longitude: number,
  latitude: number,
  radius: number,
  intent: Exclude<CameraIntent, "city">,
  rangeOverride?: number,
) {
  const preset = CAMERA[intent];
  viewer.camera.flyToBoundingSphere(
    new BoundingSphere(Cartesian3.fromDegrees(longitude, latitude, 0), radius),
    {
      offset: new HeadingPitchRange(
        CesiumMath.toRadians(preset.heading),
        CesiumMath.toRadians(preset.pitch),
        rangeOverride ?? preset.range,
      ),
      duration: preset.duration,
    },
  );
}

export class CameraController {
  constructor(private readonly viewer: Viewer, private readonly data: AppData) {}

  city() {
    const view = this.data.city.map_view;
    this.viewer.camera.setView({
      destination: Cartesian3.fromDegrees(view.longitude, view.latitude, view.height),
      orientation: {
        heading: CesiumMath.toRadians(CAMERA.city.heading),
        pitch: CesiumMath.toRadians(CAMERA.city.pitch),
        roll: 0,
      },
    });
    this.viewer.scene.requestRender();
  }

  mesh(mesh: MeshMetrics) {
    const longitude = finiteNumber(mesh.centroid_lon);
    const latitude = finiteNumber(mesh.centroid_lat);
    if (longitude === null || latitude === null) return;
    flyTo(this.viewer, longitude, latitude, 380, "mesh");
  }

  plateau(intent: "building" | "route" | "hazard" | "scenario" = "building") {
    const viewpoint = this.data.plateauMetadata?.reference_layer?.viewpoint;
    const longitude = finiteNumber(viewpoint?.longitude);
    const latitude = finiteNumber(viewpoint?.latitude);
    if (longitude === null || latitude === null) return;
    flyTo(this.viewer, longitude, latitude, intent === "building" ? 120 : 300, intent);
  }

  focus(longitude: number, latitude: number, intent: "building" | "route" | "hazard" | "scenario", range?: number) {
    flyTo(this.viewer, longitude, latitude, Math.max(120, (range ?? CAMERA[intent].range) * 0.22), intent, range);
  }
}
