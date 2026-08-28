import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ServiceTable } from "./components";

describe("municipal table system", () => {
  it("provides filtering, sorting, column visibility and pagination controls", () => {
    const html = renderToStaticMarkup(
      <ServiceTable
        caption="Findings"
        empty="Findingはありません"
        rows={[{ id: "1", title: "候補", status: "new" }]}
        rowKey={(row) => String(row.id)}
        columns={[
          { key: "title", label: "Finding" },
          { key: "status", label: "状態" },
        ]}
      />,
    );
    expect(html).toContain("表を絞り込む");
    expect(html).toContain("表示列");
    expect(html).toContain("Findingで並べ替え");
    expect(html).toContain("1件 · 1/1ページ");
    expect(html).toContain("前へ");
    expect(html).toContain("次へ");
  });
});
