import { isValidElement, type ReactElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import sectionFixture from "../../../public/data/spatial-packs/maizuru-533513314-plateau-2025-v1/sections.json";
import { UrbanSection } from "./UrbanSection";
import type { SectionData } from "./sectionTypes";

// Inspect the rendered element contract and invoke real event handlers without a DOM renderer.
const hooks = vi.hoisted(() => ({ values: [] as unknown[], cursor: 0 }));
vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useEffect: () => undefined,
    useMemo: (factory: () => unknown) => factory(),
    useState: (initial: unknown) => {
      const index = hooks.cursor++;
      const value = index in hooks.values ? hooks.values[index] : initial;
      return [value, (next: unknown) => { hooks.values[index] = next; }];
    },
  };
});

const data = sectionFixture as unknown as SectionData;
type Element = ReactElement<Record<string, unknown>>;
type Props = Parameters<typeof UrbanSection>[0];

function elements(node: ReactNode): Element[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!isValidElement<Record<string, unknown>>(node)) return [];
  return [node, ...elements(node.props.children as ReactNode)];
}

function render(overrides: Partial<Props> = {}) {
  hooks.cursor = 0;
  return elements(UrbanSection({
    open: true,
    selection: null,
    counterfactualState: "baseline",
    analysisLens: "none",
    dataOverride: data,
    expectedPackId: data.pack_id,
    onSelectBuilding: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  }));
}

function fire(element: Element, handler: string, event?: unknown) {
  expect(typeof element.props[handler]).toBe("function");
  (element.props[handler] as (value?: unknown) => void)(event);
}

beforeEach(() => { hooks.values = []; hooks.cursor = 0; });

describe("readable Advanced Urban Section", () => {
  it("opts into readable annotations without changing the Advanced mode or geometry counts", () => {
    const view = render({ readable: true, areaLabel: "選択Area" });
    expect(view[0].props).toMatchObject({
      className: "urban-section readable",
      "data-ui-mode": "advanced",
      "data-readable": true,
      "aria-label": "選択Areaの街の断面",
      "data-building-count": data.buildings.length,
      "data-road-count": data.roads.length,
      "data-annotation-overlap-count": 0,
    });
    expect(Number(view[0].props["data-road-annotation-count"])).toBeGreaterThan(0);
    expect(view.find((item) => item.type === "svg")?.props).toMatchObject({ role: "group", tabIndex: 0 });
    for (const group of view.filter((item) => item.type === "g" && item.props["aria-label"])) {
      expect(group.props.role).toBe("group");
    }
    expect(view.filter((item) => item.props["data-section-building"])).toHaveLength(data.buildings.length);
    expect(view.filter((item) => item.props["data-section-road"])).toHaveLength(data.roads.length);
  });

  it("preserves exact building click, Enter, Space and arrow-key navigation", () => {
    const onSelectBuilding = vi.fn();
    const onFocusPosition = vi.fn();
    const view = render({ readable: true, onSelectBuilding, onFocusPosition });
    const building = view.find((item) => item.props["data-section-building"])!;
    const svg = view.find((item) => item.type === "svg")!;
    expect(building.props).toMatchObject({ role: "button", tabIndex: 0 });
    expect(building.props["aria-hidden"]).toBeUndefined();
    fire(building, "onClick");
    for (const key of ["Enter", " "]) {
      const preventDefault = vi.fn();
      fire(building, "onKeyDown", { key, preventDefault });
      expect(preventDefault).toHaveBeenCalledOnce();
    }
    expect(onSelectBuilding.mock.calls).toEqual(Array.from({ length: 3 }, () => [
      data.buildings[0].source_object_id, data.buildings[0].properties,
    ]));
    const next = { focus: vi.fn() };
    const current = { parentElement: { querySelectorAll: () => [current, next] } };
    const keyEvent = { key: "ArrowRight", target: current, currentTarget: current, preventDefault: vi.fn() };
    fire(building, "onKeyDown", keyEvent);
    expect(next.focus).toHaveBeenCalledOnce();
    fire(svg, "onKeyDown", { ...keyEvent, currentTarget: {} });
    expect(onFocusPosition).not.toHaveBeenCalled();
  });

  it("shows a bounded focus callout and reports the actual keyboard-focused terrain position", () => {
    const onFocusPosition = vi.fn();
    const svg = render({ readable: true, onFocusPosition }).find((item) => item.type === "svg")!;
    const target = {};
    fire(svg, "onKeyDown", { key: "End", target, currentTarget: target, preventDefault: vi.fn() });
    const sample = data.terrain_samples.at(-1)!;
    expect(onFocusPosition).toHaveBeenLastCalledWith({ longitude: sample.longitude, latitude: sample.latitude });
    const focused = render({ readable: true, onFocusPosition });
    expect(focused[0].props["data-selected-annotation-visible"]).toBe(true);
    expect(focused.some((item) => item.props["data-section-focus-annotation"])).toBe(true);
  });

  it("retains Advanced close and reopen actions when readable", () => {
    const onClose = vi.fn();
    const close = render({ readable: true, onClose }).find((item) => item.props["aria-label"] === "都市断面を閉じる")!;
    fire(close, "onClick");
    const closed = render({ open: false, readable: true, onClose });
    expect(closed).toHaveLength(1);
    expect(closed[0].props.className).toBe("urban-section-open");
    fire(closed[0], "onClick");
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("leaves default Advanced and decorative Guided behavior unchanged", () => {
    const advanced = render();
    expect(advanced[0].props.className).toBe("urban-section");
    expect(advanced[0].props["data-road-annotation-count"]).toBe(0);
    expect(advanced.find((item) => item.type === "svg")?.props.tabIndex).toBeUndefined();
    expect(advanced.find((item) => item.type === "svg")?.props.role).toBe("group");
    for (const group of render({ counterfactualState: "scenario" }).filter((item) => item.type === "g" && item.props["aria-label"])) {
      expect(group.props.role).toBe("group");
    }
    const guided = render({ mode: "guided", open: false });
    expect(guided[0].props.className).toBe("urban-section guided");
    expect(guided[0].props["data-ui-mode"]).toBe("guided");
    expect(guided.find((item) => item.type === "svg")?.props.role).toBe("img");
    expect(guided.some((item) => item.props["aria-label"] === "都市断面を閉じる")).toBe(false);
    for (const building of guided.filter((item) => item.props["data-section-building"])) {
      expect(building.props["aria-hidden"]).toBe(true);
      expect(building.props.onClick).toBeUndefined();
      expect(building.props.onKeyDown).toBeUndefined();
      expect(building.props.tabIndex).toBeUndefined();
    }
  });
});
