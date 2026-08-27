# Spatial UX

## Intended first minute

1. In five seconds, the user sees a real basemap, municipal boundary, 500m cells, top candidates, and a legend.
2. In fifteen seconds, the candidate list and map answer where additional investigation may be useful.
3. Selecting a candidate opens human-readable facts and a strong map outline.
4. “詳しく” carries the same location into PLATEAU building/road context.
5. “試す” and “検証” change the question while retaining the same product shell.

The default copy explicitly says the score is a screening signal, not risk or policy priority.

## Purpose navigation

Top-level navigation is task language: 探す, 詳しく, 試す, 検証, 運用. Technical workspaces remain compatible through URL state, but users do not need to understand internal product modules.

## Context Inspector

The hierarchy is human name, key facts, interpretation boundary, task controls, deterministic PLATEAU lineage, evidence entry, then technical ID. Official PLATEAU attributes and model estimates are visually separated. Raw statuses are translated to human language while canonical IDs remain under Technical details.

## Focus and continuity

A selection persists across task and renderer changes. Other thematic features are dimmed, related evidence remains strong, and the Inspector opens automatically. Search supports task, area label, and mesh ID with keyboard shortcut Ctrl/Cmd+K.

## Scenario and municipal flow

Scenario compare labels current/after and shares camera/selection. Stress Test exposes the edge-closure assumption and rejects probability claims. Municipal operation follows 確認 → 比較 → 現地確認 → Evidence rather than exposing every administrative control at once.

## Automated task benchmark

`frontend/scripts/audit-validation.mjs` replays tasks A–F from a clean page, records clicks, elapsed time, dead ends, runtime errors, first-value time, responsive behavior, and cartographic gates. It is explicitly an automated walkthrough, not a human usability study. The tracked JSON preserves the former baseline beside the Product 2.0 measurements.

The final automated run reduced the total A–F path from 15 to 7 clicks and from 120,623ms to 11,368ms in the same headless environment. Task C uses one additional click to make the Stress Test assumption explicit; its measured time fell from 33,564ms to 2,890ms. First rendered analytical value was 7,437ms under software WebGL. These are deterministic automation measurements, not claims about human completion time.
