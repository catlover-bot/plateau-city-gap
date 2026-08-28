import { describe, expect, it, vi } from "vitest";
import { loadServiceSnapshot } from "./api";

function response(payload: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => payload } as Response;
}

describe("municipal service API client", () => {
  it("loads only tenant API resources and never substitutes public showcase files", async () => {
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      const payloads: Record<string, unknown> = {
        "/api/v1/me": {
          actor: "fixture-analyst",
          issuer: "fixture",
          roles: ["analyst"],
          organization: { id: "org", organization_key: "fixture", name: "検証組織" },
          user: null,
          memberships: []
        },
        "/api/v1/cities": { items: [{ city_id: "city", city_key: "test-city", name: "検証市", service_status: "active" }] },
        "/api/v1/work-queue": { user: null, assignments: [], notifications: [], unregistered_identity: true },
        "/api/v1/analysis-definitions": { items: [] },
        "/api/v1/cities/test-city/home": { city: { id: "city", city_key: "test-city", name: "検証市" }, summary: {}, capabilities: [], datasets: [], recent_activity: [] },
        "/api/v1/cities/test-city/findings?limit=100": { items: [] },
        "/api/v1/cities/test-city/investigations?limit=100": { items: [] },
        "/api/v1/cities/test-city/scenarios?limit=100": { items: [] },
        "/api/v1/cities/test-city/data-hub": { city: { id: "city", city_key: "test-city", name: "検証市" }, datasets: [], quality_checks: [], plateau_model: [] }
      };
      return response(payloads[url] ?? {}, url in payloads ? 200 : 404);
    }) as unknown as typeof fetch;

    const result = await loadServiceSnapshot(fetcher);
    expect(result.profile.roles).toEqual(["analyst"]);
    expect(result.cityHome?.city.name).toBe("検証市");
    const urls = (fetcher as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]));
    expect(urls.every((url) => url.startsWith("/api/v1/"))).toBe(true);
    expect(urls.some((url) => url.includes("public/data"))).toBe(false);
  });

  it("keeps an organization with no cities as a real onboarding empty state", async () => {
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url === "/api/v1/me") return response({ actor: "admin", issuer: "fixture", roles: ["administrator"], organization: { id: "org", organization_key: "new", name: "新規組織" }, user: null, memberships: [] });
      if (url === "/api/v1/cities") return response({ items: [] });
      if (url === "/api/v1/work-queue") return response({ user: null, assignments: [], notifications: [], unregistered_identity: true });
      if (url === "/api/v1/analysis-definitions") return response({ items: [] });
      return response({}, 404);
    }) as unknown as typeof fetch;
    const result = await loadServiceSnapshot(fetcher);
    expect(result.cities).toEqual([]);
    expect(result.cityHome).toBeNull();
    expect((fetcher as ReturnType<typeof vi.fn>).mock.calls).toHaveLength(4);
  });

  it("preserves request ID and remediation from unified API errors", async () => {
    const fetcher = vi.fn(async () => response({ error: { code: "permission_denied", message: "Organization membership required", request_id: "request-1", remediation: "Confirm membership." } }, 403)) as unknown as typeof fetch;
    await expect(loadServiceSnapshot(fetcher)).rejects.toMatchObject({
      status: 403,
      requestId: "request-1",
      remediation: "Confirm membership."
    });
  });
});
