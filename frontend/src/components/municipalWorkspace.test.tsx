import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import workspaceStoryJson from "../../public/data/municipal_workspace_story.json";
import buildingPointsJson from "../../public/data/network_scenario_building_points.json";
import registryJson from "../../public/data/platform_registry.json";
import type { MunicipalWorkspaceData, WorkspaceLayerVisibility } from "../types";
import { MunicipalWorkspace } from "./MunicipalWorkspace";

const data = {
  story: workspaceStoryJson,
  map: { type: "FeatureCollection", features: [] },
  buildingPoints: buildingPointsJson,
  registry: registryJson
} as unknown as MunicipalWorkspaceData;

const layers: WorkspaceLayerVisibility = {
  meshes: true,
  affectedBuildings: false,
  routes: false,
  plateauBuildings: false,
  roadNetwork: false,
  landuse: false,
  planning: false,
  hazard: false
};

describe("Municipal Workspace UI", () => {
  it("exposes the complete review workflow without a recommendation", () => {
    const html = renderToStaticMarkup(
      <MunicipalWorkspace
        data={data}
        cityCode="26202"
        phase="baseline"
        layers={layers}
        onPhaseChange={() => undefined}
        onLayersChange={() => undefined}
      />
    );
    for (const label of [
      "課題発見",
      "地域を見る",
      "PLATEAU詳細",
      "道路ネットワーク",
      "計画・災害",
      "シナリオ作成",
      "複数案比較",
      "現地確認・根拠"
    ]) expect(html).toContain(label);
    expect(html).toContain("地図には個別人数を表示しません");
    expect(html).not.toContain("推奨案");
  });

  it("does not substitute Maizuru scenarios for an unavailable city", () => {
    const html = renderToStaticMarkup(
      <MunicipalWorkspace
        data={data}
        cityCode="14205"
        phase="baseline"
        layers={layers}
        onPhaseChange={() => undefined}
        onLayersChange={() => undefined}
      />
    );
    expect(html).toContain("この都市ではシナリオ機能を利用できません");
    expect(html).toContain("未計算の機能を舞鶴市の結果で代用しません");
    expect(html).not.toContain("2,911");
  });
});
