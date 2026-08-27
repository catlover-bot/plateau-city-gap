import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import network from "../../public/data/validation/network_cross_validation.json";
import sensitivity from "../../public/data/validation/sensitivity_validation.json";
import temporal from "../../public/data/validation/real_temporal_validation.json";
import type { ValidationWorkspaceData } from "../types";
import { ValidationWorkspace } from "./ValidationWorkspace";

const data = {
  network,
  sensitivity,
  temporal,
  disagreementRoutes: {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      geometry: { type: "LineString", coordinates: [[135.2, 35.4], [135.3, 35.5]] },
      properties: {
        sample_id: "route-maizuru-fixture",
        city_id: "maizuru",
        cause_candidate: "topology",
        reference_agreement: "large_difference",
        primary_reachable: true,
        primary_distance_m: 500,
        reference_reachable: true,
        reference_distance_m: 1100,
        review_status: "not_reviewed"
      }
    }, {
      type: "Feature",
      geometry: { type: "LineString", coordinates: [[139.4, 35.3], [139.5, 35.4]] },
      properties: {
        sample_id: "route-fujisawa-fixture",
        city_id: "fujisawa",
        cause_candidate: "snap",
        reference_agreement: "moderate_difference"
      }
    }]
  },
  temporalSamples: { type: "FeatureCollection", features: [] },
  criticalityAudit: { type: "FeatureCollection", features: [] }
} as unknown as ValidationWorkspaceData;

describe("Validation Workspace", () => {
  it("renders real model comparison without ground-truth or confidence claims", () => {
    const html = renderToStaticMarkup(<ValidationWorkspace data={data} cityId="maizuru" baseUrl="/plateau-city-gap/" />);
    expect(html).toContain("VALIDATION &amp; MUNICIPAL EVIDENCE");
    expect(html).toContain("n=125");
    expect(html).toContain("88");
    expect(html).toContain("参照網は正解データではありません");
    expect(html).toContain("GROUND TRUTH CLAIMED: NO");
    expect(html).not.toContain("信頼度 82%");
  });

  it("exposes bounded sensitivity, temporal, evidence and disagreement sections", () => {
    const html = renderToStaticMarkup(<ValidationWorkspace data={data} cityId="fujisawa" baseUrl="/" />);
    for (const label of ["モデル比較", "仮定感度", "年次差分", "Evidence強度", "差異レビュー"]) {
      expect(html).toContain(label);
    }
    expect(data.sensitivity.cities.fujisawa.hazard_assumption_matrix.some((row) => row.assumption === "S1_all_overlap_edges")).toBe(true);
    expect(data.network.reference_warning.length).toBeGreaterThan(0);
    expect(html).toContain("実座標を表示領域へ正規化");
  });
});
