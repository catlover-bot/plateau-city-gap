import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const read = (relative: string) => readFileSync(new URL(relative, import.meta.url), "utf8").toLowerCase();
const tokens = read("./tokens.css");
const foundation = read("./foundation.css");
const guided = read("../features/guided-spatial/guided-spatial.css");
const publicJourney = read("../features/area-investigation/publicAreaJourney.css");

function token(name: string, value: string) {
  expect(tokens).toContain(`${name}: ${value};`);
}

describe("Harbor Atlas style contract", () => {
  it("locks the neutral seed palette", () => {
    for (const [name, value] of Object.entries({
      "--cg-text-primary": "#15242b", "--cg-text-secondary": "#526269",
      "--cg-bg-page": "#f5f5f1", "--cg-bg-panel": "#fcfcf9",
      "--cg-bg-muted": "#eef1ef", "--cg-border": "#d7ddda", "--cg-border-strong": "#87959a",
    })) token(name, value);
  });

  it("locks the Harbor seed palette", () => {
    for (const [name, value] of Object.entries({
      "--cg-brand-strong": "#164f63", "--cg-brand": "#26758a",
      "--cg-brand-soft": "#77aeb6", "--cg-area-selected-fill": "#c9e1de", "--cg-brand-pale": "#e8f2ef",
    })) token(name, value);
  });

  it("locks the Signal seed palette", () => {
    for (const [name, value] of Object.entries({
      "--cg-target-strong": "#a94736", "--cg-target": "#d9664d",
      "--cg-target-soft": "#f1a085", "--cg-target-pale": "#f7e4de",
    })) token(name, value);
  });

  it("locks map material, focus, and error colors", () => {
    for (const [name, value] of Object.entries({
      "--cg-building": "#9ba9ad", "--cg-building-outline": "#596970",
      "--cg-road": "#e5ddd1", "--cg-road-outline": "#667279",
      "--cg-transect-terrain": "#5d7476", "--cg-focus-ring": "#f0b84b", "--cg-error": "#b34e49",
    })) token(name, value);
  });

  it("separates UI surface roles from cartographic roles", () => {
    for (const name of ["--cg-bg-page", "--cg-bg-panel", "--cg-bg-elevated", "--cg-text-primary", "--cg-border"]) {
      expect(tokens).toContain(`${name}:`);
    }
    for (const name of ["--cg-area-selected", "--cg-building", "--cg-road", "--cg-transect-line", "--cg-target"]) {
      expect(tokens).toContain(`${name}:`);
    }
  });

  it("uses Harbor for Area selection and Signal for exact targets", () => {
    expect(guided).toContain("background: var(--cg-brand-pale)");
    expect(guided).toContain("background: var(--cg-target-pale)");
    expect(guided).toContain("border-left: 3px solid var(--cg-target)");
  });

  it("uses Signal for the single primary action hierarchy", () => {
    expect(guided).toMatch(/\.guided-primary[\s\S]*?background: var\(--cg-target-strong\)/);
    expect(publicJourney).toMatch(/\.public-primary[\s\S]*?background: var\(--cg-target-strong\)/);
  });

  it("keeps interaction motion within the Harbor Atlas timing bands", () => {
    token("--cg-duration-hover", "140ms");
    token("--cg-duration-selection", "190ms");
    token("--cg-duration-inspector", "170ms");
    token("--cg-duration-section", "220ms");
    token("--cg-duration-camera", "420ms");
    expect(`${foundation}\n${guided}`).toContain("prefers-reduced-motion: reduce");
  });

  it("uses no decorative gradients in Public or Guided", () => {
    expect(`${guided}\n${publicJourney}`).not.toMatch(/(?:linear|radial|conic)-gradient\s*\(/);
  });

  it("adds no runtime theme selector or legacy purple Section accent", () => {
    const publicGuided = `${tokens}\n${foundation}\n${guided}\n${publicJourney}`;
    expect(publicGuided).not.toMatch(/data-theme|theme-toggle|theme-selector/);
    expect(publicGuided).not.toContain("#6b4c7d");
    expect(publicGuided).not.toContain("var(--cg-section)");
  });
});
