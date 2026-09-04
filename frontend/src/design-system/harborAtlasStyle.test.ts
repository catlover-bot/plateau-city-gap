import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const read = (relative: string) => readFileSync(new URL(relative, import.meta.url), "utf8").toLowerCase();
const tokens = read("./tokens.css");
const foundation = read("./foundation.css");
const guided = read("../features/guided-spatial/guided-spatial.css");
const publicJourney = read("../features/area-investigation/publicAreaJourney.css");
const urbanSection = read("../features/urban-section/urban-section.css");
const analyticalMap = read("../map/2d/AnalyticalMap.tsx");
const guidedCartography = read("../features/guided-spatial/guidedCartography.ts");
const mapSource = `${analyticalMap}\n${guidedCartography}`;

function token(name: string, value: string) {
  expect(tokens).toContain(`${name}: ${value};`);
}

function tokenHex(name: string): string {
  const match = tokens.match(new RegExp(`${name}:\\s*(#[\\da-f]{6});`));
  if (!match) throw new Error(`missing hex token ${name}`);
  return match[1];
}

function rgb(hex: string): [number, number, number] {
  return [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16)) as [number, number, number];
}

function luminance(hex: string): number {
  const channels = rgb(hex).map((channel) => {
    const value = channel / 255;
    return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
  });
  return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
}

function contrast(left: string, right: string): number {
  const values = [luminance(left), luminance(right)].sort((a, b) => b - a);
  return (values[0] + .05) / (values[1] + .05);
}

function simulatedDistance(matrix: number[]): number {
  const transform = (value: [number, number, number]) => [0, 1, 2].map((row) => (
    value[0] * matrix[row * 3] + value[1] * matrix[row * 3 + 1] + value[2] * matrix[row * 3 + 2]
  ));
  const area = transform(rgb(tokenHex("--cg-brand-strong")));
  const target = transform(rgb(tokenHex("--cg-target-strong")));
  return Math.hypot(...area.map((channel, index) => channel - target[index]));
}

describe("Harbor Atlas style contract", () => {
  it("limits Public and Guided first views to Harbor and Signal accent families", () => {
    const experienceCss = `${guided}\n${publicJourney}\n${urbanSection}`;
    const families = new Set([...experienceCss.matchAll(/var\(--cg-(brand|target)(?:-[a-z]+)?\)/g)].map((match) => match[1]));
    expect([...families].sort()).toEqual(["brand", "target"]);
    expect(experienceCss).not.toMatch(/var\(--cg-(?:amber|brick|bluegray|hazard|section)\)/);
    for (const [name, value] of Object.entries({
      "--cg-text-primary": "#15242b", "--cg-text-secondary": "#526269",
      "--cg-bg-page": "#f5f5f1", "--cg-bg-panel": "#fcfcf9", "--cg-bg-muted": "#eef1ef",
      "--cg-brand-strong": "#164f63", "--cg-brand": "#26758a", "--cg-brand-soft": "#77aeb6",
      "--cg-area-selected-fill": "#c9e1de", "--cg-brand-pale": "#e8f2ef",
      "--cg-target-strong": "#a94736", "--cg-target": "#d9664d", "--cg-target-soft": "#f1a085", "--cg-target-pale": "#f7e4de",
    })) token(name, value);
  });

  it("keeps selection distinguishable from context in grayscale", () => {
    expect(mapSource).toContain('id: "guided-area-halo"');
    expect(mapSource).toMatch(/id: "guided-area-line"[\s\S]*?"line-width": 3\.8/);
    expect(mapSource).toContain('id: "guided-area-label"');
    expect(mapSource).toContain('id: "guided-target-halo"');
    expect(mapSource).toMatch(/id: "guided-target-line"[\s\S]*?"line-width": 5/);
    expect(urbanSection).toContain("stroke-dasharray: 3 2");
  });

  it("keeps Area and target colors separated in protanopia and deuteranopia simulations", () => {
    const protanopia = [.567, .433, 0, .558, .442, 0, 0, .242, .758];
    const deuteranopia = [.625, .375, 0, .7, .3, 0, 0, .3, .7];
    expect(simulatedDistance(protanopia)).toBeGreaterThan(40);
    expect(simulatedDistance(deuteranopia)).toBeGreaterThan(40);
    expect(mapSource).toContain('id: "guided-target-label"');
  });

  it("keeps primary CTA text at WCAG AA contrast", () => {
    expect(contrast(tokenHex("--cg-target-strong"), tokenHex("--cg-bg-elevated"))).toBeGreaterThanOrEqual(4.5);
    expect(guided).toMatch(/\.guided-primary[\s\S]*?background: var\(--cg-target-strong\)[\s\S]*?color: var\(--cg-bg-elevated\)/);
    expect(publicJourney).toMatch(/\.public-primary[\s\S]*?background: var\(--cg-target-strong\)[\s\S]*?color: var\(--cg-bg-elevated\)/);
  });

  it("keeps secondary controls at WCAG AA contrast", () => {
    expect(contrast(tokenHex("--cg-brand-strong"), tokenHex("--cg-bg-elevated"))).toBeGreaterThanOrEqual(4.5);
    expect(guided).toMatch(/\.guided-secondary-action[\s\S]*?color: var\(--cg-brand-strong\)/);
    expect(publicJourney).toMatch(/\.public-secondary,[\s\S]*?color: var\(--cg-brand-strong\)/);
  });

  it("pairs the focus color with a contrasting perimeter", () => {
    token("--cg-focus-ring", "#f0b84b");
    expect(contrast(tokenHex("--cg-focus-ring"), tokenHex("--cg-text-primary"))).toBeGreaterThanOrEqual(3);
    expect(tokens).toMatch(/:focus-visible[\s\S]*?outline: 3px solid var\(--cg-focus-ring\)[\s\S]*?box-shadow: 0 0 0 7px var\(--cg-text-primary\)/);
  });

  it("gives map labels a readable halo", () => {
    expect(contrast(tokenHex("--cg-brand-strong"), tokenHex("--cg-bg-elevated"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(tokenHex("--cg-target-strong"), tokenHex("--cg-bg-elevated"))).toBeGreaterThanOrEqual(4.5);
    expect(mapSource).toMatch(/id: "guided-area-label"[\s\S]*?"text-halo-width": 3/);
    expect(mapSource).toMatch(/id: "guided-target-label"[\s\S]*?"text-halo-width": 3/);
  });

  it("keeps the A-B line readable over light and dark map portions", () => {
    expect(contrast(tokenHex("--cg-brand"), tokenHex("--cg-bg-elevated"))).toBeGreaterThanOrEqual(3);
    expect(mapSource).toMatch(/id: "guided-section-halo"[\s\S]*?"line-width": 7/);
    expect(mapSource).toMatch(/id: "guided-section-line"[\s\S]*?"line-width": 4/);
    expect(urbanSection).toContain("fill: var(--cg-transect-endpoint)");
  });

  it("uses no decorative gradients and preserves restrained motion", () => {
    expect(`${guided}\n${publicJourney}`).not.toMatch(/(?:linear|radial|conic)-gradient\s*\(/);
    token("--cg-duration-hover", "140ms");
    token("--cg-duration-selection", "190ms");
    token("--cg-duration-inspector", "170ms");
    token("--cg-duration-section", "220ms");
    token("--cg-duration-camera", "420ms");
    expect(`${foundation}\n${guided}`).toContain("prefers-reduced-motion: reduce");
  });

  it("adds no runtime theme selector or legacy purple Section accent", () => {
    const publicGuided = `${tokens}\n${foundation}\n${guided}\n${publicJourney}\n${urbanSection}`;
    expect(publicGuided).not.toMatch(/data-theme|theme-toggle|theme-selector/);
    expect(publicGuided).not.toContain("#6b4c7d");
    expect(publicGuided).not.toContain("var(--cg-section)");
    for (const [name, value] of Object.entries({
      "--cg-building": "#9ba9ad", "--cg-building-outline": "#596970",
      "--cg-road": "#e5ddd1", "--cg-road-outline": "#667279",
      "--cg-transect-terrain": "#5d7476", "--cg-error": "#b34e49",
    })) token(name, value);
    expect(urbanSection).toContain("fill: var(--cg-transect-building)");
    expect(urbanSection).toContain("fill: var(--cg-transect-road)");
    expect(urbanSection).toContain("stroke: var(--cg-target-strong)");
  });
});
