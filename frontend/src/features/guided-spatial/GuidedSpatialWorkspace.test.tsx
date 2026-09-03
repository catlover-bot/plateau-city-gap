import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GuidedSpatialLoadingWorkspace } from "./GuidedSpatialWorkspace";

describe("Guided spatial first render", () => {
  it("shows the story and a map loading surface before the Area catalog is ready", () => {
    const html = renderToStaticMarkup(<GuidedSpatialLoadingWorkspace />);
    expect(html).toContain('data-guided-story="intro"');
    expect(html).toContain('data-context-status="loading"');
    expect(html).toContain("舞鶴の地域を、");
    expect(html).toContain("地図からたどる。");
    expect(html).toContain("舞鶴市の500m範囲を読み込んでいます");
    expect(html).not.toContain("デモを始める");
  });
});
