# Public product benchmark

Goal: `public-product-language-and-section-v1`

Observed at: 2026-09-02 JST  
Capture viewport: 1440 × 900 CSS px  
Capture manifest: [`docs/assets/public-product-audit/manifest.json`](assets/public-product-audit/manifest.json)

This benchmark records only public pages that were opened in a real Chromium browser. `PARTIALLY_OBSERVED` means that official documentation was visible but the authenticated product was not. `TEXT_ONLY` means that only a public marketing page was available. No authenticated interface is inferred. The screenshots are research evidence only; CITY GAP does not copy third-party wording, branding, icons, CSS, screenshots, or source code.

## Product observations

| Product | Official URL | Status | What was actually visible | Principle CITY GAP may learn | Boundary |
|---|---|---|---|---|---|
| ArcGIS Field Maps | [Tools and features](https://doc.arcgis.com/en/field-maps/android/use-maps/quick-reference.htm) | `PARTIALLY_OBSERVED` | Official documentation described a map and panel, data collection form/location target, and tasks as separate parts. The authenticated mobile UI was not opened. | Keep the map primary; expose the action that belongs to the selected place instead of showing every tool persistently. | Do not recreate its general field GIS, task management, or data collection system. |
| ArcGIS Survey123 | [Quick reference](https://doc.arcgis.com/en/survey123/capture/field-app/quickreferencegetanswers.htm) | `PARTIALLY_OBSERVED` | Official documentation presented one survey as a focused unit and separated download, contents, survey, and settings. A cookie overlay obscured part of the page; no signed-in survey was inspected. | Use plain field labels and reveal details when required; do not expose schema/rule terminology to respondents. | Do not build a form designer or copy its survey structure. |
| ArcGIS Urban | [User interface items](https://doc.arcgis.com/en/urban/12.1/help/help-intro.htm) | `PARTIALLY_OBSERVED` | Official documentation explicitly separated overview, plan/project viewing, and plan/project editing experiences. It described a city 3D view and a search side panel. No authenticated model was opened. | Keep public viewing separate from Advanced editing/analysis; open detailed tools only after intent is clear. | Do not copy the three-dimensional planning editor or its navigation. |
| Maptionnaire | [Public site](https://www.maptionnaire.com/) | `TEXT_ONLY` | The public landing stated one job in a large heading, one supporting statement, and two actions. Product operation was not accessible without entering the service. | Explain one job in one sentence; connect map actions to the evidence they change. | Do not copy marketing language, visual styling, or participation workflows. |
| My City Report | [Public report entry](https://web.mycityreport.jp/) | `OBSERVED` | A public service page stated the job directly, then offered two clearly named paths. The limitation of the quick path was next to that choice. | Use an ordinary Japanese verb, a short heading, and a local limitation where it changes the choice. | CITY GAP is not a citizen-reporting service and does not copy the two-card layout. |
| ArcGIS StoryMaps | [Map tour documentation](https://doc.arcgis.com/en/arcgis-storymaps/author-and-share/add-guided-tours.htm) | `PARTIALLY_OBSERVED` | Official documentation described map tours as a map combined with media/text. It distinguished a small sequential guided tour from an explorer that allows arbitrary order. No authoring account was used. | A map-linked explanation should answer one spatial question; a sequential flow should stay small. | Do not build a story authoring tool or reuse its layouts. |
| Felt | [Public site](https://felt.com/) | `TEXT_ONLY` | Only the public product landing was observed; the signed-in mapping interface was not. | The opening visual can make the map category obvious before feature explanation. | No claim is made about editor controls, panels, selection states, or legends. |
| CARTO | [Public site](https://carto.com/) | `TEXT_ONLY` | Only a public enterprise-marketing page was observed. | No product-UI principle is adopted from this evidence. | Do not infer the authenticated GIS UI. |
| Mapbox | [Public site](https://www.mapbox.com/) | `TEXT_ONLY` | Only a public platform-marketing page was observed. | Keep a short top-level value statement and strong typography, without adding promotional copy to the working screen. | Do not infer Studio/navigation UI or copy its brand language. |

## Captured evidence

Every entry below has a timestamp, requested/final URL, viewport, HTTP/access status, file hash, and screenshot in the manifest.

- `benchmark-field-maps.png`
- `benchmark-survey123.png`
- `benchmark-arcgis-urban.png`
- `benchmark-maptionnaire.png`
- `benchmark-my-city-report.png`
- `benchmark-storymaps.png`
- `benchmark-felt.png`
- `benchmark-carto.png`
- `benchmark-mapbox.png`

## Adopted principles

1. State one concrete job before explaining method or governance.
2. Keep the map and its selected place visually primary.
3. Present the action for the current place or result, not a permanent toolbox.
4. Separate Public viewing from Advanced analysis.
5. Put a material limitation next to the choice it affects; move provenance and methodology to one disclosure.
6. Use one map-linked explanation for one spatial question.
7. Prefer ordinary labels, typographic hierarchy, and dividers over nested cards and badges.

## Patterns explicitly not copied

- third-party brand, CSS, color tokens, icons, illustrations, screenshots, or exact wording;
- Field Maps task layers or general feature editing;
- Survey123 form design or branching UI;
- ArcGIS Urban plan/project/zoning editing;
- Maptionnaire participation collection;
- My City Report public reporting;
- StoryMaps authoring blocks;
- any signed-in Felt, CARTO, or Mapbox behavior that was not observed.

