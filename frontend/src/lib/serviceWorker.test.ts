import { describe, expect, it } from "vitest";
import serviceWorkerSource from "../../public/sw.js?raw";

describe("public offline shell", () => {
  it("pre-caches every mandatory field-investigation data contract", () => {
    for (const filename of [
      "manifest.json",
      "mesh_metrics.geojson",
      "top10.json",
      "summary.json",
      "final_demo.json",
      "robustness.json",
      "intervention_scenarios.json",
      "evidence.json",
      "plateau_metadata.json",
    ]) {
      expect(serviceWorkerSource).toContain(`./data/${filename}`);
    }
    expect(serviceWorkerSource).toContain("citygap-shell-v6");
    expect(serviceWorkerSource).toContain("objects.json");
    expect(serviceWorkerSource).toContain("sections.json");
  });

  it("excludes APIs and internal field records from the public runtime cache", () => {
    expect(serviceWorkerSource).toContain('url.pathname.includes("/api/")');
    expect(serviceWorkerSource).toContain('url.pathname.includes("/offline-field/")');
    expect(serviceWorkerSource).not.toContain("CACHE_LOCAL_INVESTIGATION_SHEET");
    expect(serviceWorkerSource).not.toContain("generalNote");
  });

  it("keeps navigation and versioned public assets recoverable offline", () => {
    expect(serviceWorkerSource).toContain('event.request.mode === "navigate"');
    expect(serviceWorkerSource).toContain("ignoreSearch: true");
    expect(serviceWorkerSource).toContain('"document", "script", "style", "worker"');
  });
});
