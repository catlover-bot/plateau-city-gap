import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ServiceApp } from "./ServiceApp";
import type { ServiceSnapshot } from "./types";

const snapshot: ServiceSnapshot = {
  profile: {
    actor: "fixture-planner",
    issuer: "fixture",
    roles: ["planner"],
    organization: {
      id: "org-1",
      organization_key: "fixture-org",
      name: "検証組織",
    },
    user: { id: "user-1", display_name: "検証担当" },
    memberships: [{ role: "planner", granted_at: "2026-08-28T00:00:00Z" }],
  },
  cities: [
    {
      city_id: "city-1",
      city_code: "00000",
      city_key: "fixture-city",
      name: "検証市",
      service_status: "active",
      open_findings: 2,
      active_investigations: 1,
      pending_reviews: 1,
      pending_field_checks: 0,
      latest_activity_at: "2026-08-28T00:00:00Z",
    },
  ],
  cityHome: {
    city: {
      id: "city-1",
      city_code: "00000",
      city_key: "fixture-city",
      name: "検証市",
      prefecture_name: "検証県",
      analysis_crs: "EPSG:6674",
      service_status: "active",
    },
    summary: {
      city_id: "city-1",
      city_code: "00000",
      city_key: "fixture-city",
      name: "検証市",
      service_status: "active",
      open_findings: 2,
      active_investigations: 1,
      pending_reviews: 1,
      pending_field_checks: 0,
      latest_activity_at: "2026-08-28T00:00:00Z",
    },
    capabilities: [],
    datasets: [],
    recent_activity: [],
  },
  findings: [],
  investigations: [],
  workQueue: {
    user: { id: "user-1", display_name: "検証担当" },
    assignments: [],
    notifications: [],
    unregistered_identity: false,
  },
  analyses: [],
  analysisRuns: [],
  scenarios: [],
  scenarioComparisons: [],
  dataHub: null,
  evidence: null,
  operations: null,
  onboarding: null,
};

describe("Municipal Service shell", () => {
  it("renders service navigation, role home and the human decision boundary", () => {
    const html = renderToStaticMarkup(
      <ServiceApp initialSnapshot={snapshot} />,
    );
    for (const label of [
      "Home",
      "Cities",
      "Data",
      "Analysis",
      "Measures",
      "Review",
      "Evidence",
    ])
      expect(html).toContain(label);
    expect(html).toContain("企画・計画担当 HOME");
    expect(html).toContain("検証市の業務状況");
    expect(html).toContain("人がレビューし、人が判断を記録");
    expect(html).toContain("分析結果は候補であり行政判断ではありません");
    expect(html).not.toContain("推奨案");
    expect(html).not.toContain("4分デモ");
  });
});
