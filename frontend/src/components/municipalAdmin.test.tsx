import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MunicipalAdmin, type AdminSnapshot, type PilotReadiness } from "./MunicipalAdmin";

const snapshot: AdminSnapshot = {
  cities: [{ city_code: "26202", name: "舞鶴市", analysis_crs: "EPSG:6674" }],
  datasets: [{ city_code: "26202", dataset_version_id: "v1", title: "PLATEAU", dataset_key: "plateau", version_key: "2025", verification_status: "verified", lifecycle_status: "active", quality_status: "passed", analysis_ready: true }],
  capabilities: [{ city_code: "26202", capability: "road_network", status: "partial", note: "experimental" }],
  networks: [{ network_version_id: "n1", city_code: "maizuru", graph_version: "exp-1", source_type: "experimental_surface_adjacency", node_count: 10, edge_count: 20 }],
  jobs: [{ job_id: "j1", city_code: "26202", job_type: "plateau_ingestion", state: "succeeded", retry_count: 0, max_retries: 2 }],
  users: [{ user_id: "u1", display_name: "Pilot Admin", issuer: "https://id.example", active: true, roles: [{ city_code: "26202", role: "administrator" }] }]
};
const readiness: PilotReadiness = { status: "READY_WITH_LIMITATIONS", blockers: [], limitations: ["gtfs"], checks: [{ name: "postgis", passed: true, required: true, detail: "ready" }] };

describe("Municipal admin", () => {
  it("renders the required operational inventory from authenticated API data", () => {
    const html = renderToStaticMarkup(<MunicipalAdmin cityId="maizuru" initialSnapshot={snapshot} initialReadiness={readiness} />);
    for (const label of ["Cities", "Datasets / Versions", "Capabilities", "Network Versions", "Jobs", "Users / Roles", "Pilot Readiness"]) expect(html).toContain(label);
    expect(html).toContain("experimental_surface_adjacency");
    expect(html).toContain("administrator (26202)");
    expect(html).toContain("READY_WITH_LIMITATIONS");
  });
});
