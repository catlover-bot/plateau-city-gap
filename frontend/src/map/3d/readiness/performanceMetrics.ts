export type ReadinessMetric =
  | "app_shell"
  | "map_2d_interaction"
  | "three_d_first_meaningful"
  | "pack_interaction"
  | "visual_complete"
  | "capture_strict";

interface TimingSample {
  metric: ReadinessMetric;
  elapsedMs: number;
  rendererClass: "normal-gpu" | "swiftshader";
  scene: string;
  recordedAt: string;
}

const STORAGE_KEY = "citygap.readiness.timings.v1";

function rendererClass(): TimingSample["rendererClass"] {
  const query = new URLSearchParams(window.location.search).get("renderer");
  return query === "swiftshader" ? "swiftshader" : "normal-gpu";
}

export function recordReadinessMetric(metric: ReadinessMetric, scene: string): void {
  const element = document.documentElement;
  const datasetKey = `perf${metric.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join("")}Ms`;
  if (element.dataset[datasetKey]) return;
  const sample: TimingSample = {
    metric,
    elapsedMs: Math.round(performance.now()),
    rendererClass: rendererClass(),
    scene,
    recordedAt: new Date().toISOString(),
  };
  element.dataset[datasetKey] = String(sample.elapsedMs);
  performance.mark(`citygap:${metric}`);
  try {
    const prior = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as TimingSample[];
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...prior.slice(-99), sample]));
  } catch {
    // Metrics are diagnostic only; storage policy must never block interaction.
  }
}
