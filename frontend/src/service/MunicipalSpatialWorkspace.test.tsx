import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MunicipalSpatialWorkspace } from "./MunicipalSpatialWorkspace";

describe("authenticated municipal spatial workspace", () => {
  it("renders real investigation entities, layer controls and an accessible map shell", () => {
    const html = renderToStaticMarkup(
      <MunicipalSpatialWorkspace
        entities={[
          {
            entity_type: "facility",
            entity_id: "facility-001",
            label: "公開施設",
            source: "自治体公開データ",
            source_year: 2025,
            geometry: { type: "Point", coordinates: [135.33, 35.47] },
          },
        ]}
        viewport={{ longitude: 135.33, latitude: 35.47, zoom: 13 }}
        visibleEntityTypes={["facility"]}
        onViewportChange={() => undefined}
        onVisibleEntityTypesChange={() => undefined}
      />,
    );
    expect(html).toContain("SPATIAL WORKSPACE");
    expect(html).toContain('data-entity-count="1"');
    expect(html).toContain("facility");
    expect(html).toContain("公開施設");
    expect(html).toContain("自治体公開データ");
  });
});
