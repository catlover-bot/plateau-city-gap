# Public product language and visual audit

Goal: `public-product-language-and-section-v1`  
Baseline commit: `a365dc04ccbcfad020d8f6ff2cd63db6e7865d60`

## Mandatory CI red gate

The source-branch Municipal Pilot CI run [33547106592](https://github.com/catlover-bot/plateau-city-gap/actions/runs/33547106592) was inspected before product edits. It completed successfully with all nine required jobs green: `validation-gates`, `security`, `migration`, `public-assets`, `api-integration`, `build`, `frontend`, `python-unit`, and `postgis-integration`. The exact run is the gate for this branch; no test or assertion was removed or weakened.

## Separate baselines

| Baseline | URL | Status | Evidence |
|---|---|---|---|
| GitHub Pages production | `https://catlover-bot.github.io/plateau-city-gap/` | `OBSERVED`, unchanged by this goal | `production-landing-desktop/mobile.png`, `production-guided-section.png`, `production-guided-task.png`, `production-advanced-section.png` |
| Feature production preview | `http://127.0.0.1:4180/plateau-city-gap/` | `OBSERVED` at source HEAD | `feature-landing/place/radius/result/target-{desktop,mobile}.png` |

The production root is the older guided product. The feature root is the Area first-run journey. Findings are not transferred between them unless the same DOM/CSS is present.

## Baseline findings from DOM, CSS, and screenshots

| Anti-pattern | Evidence | Severity | Planned response |
|---|---|---:|---|
| Card inside card | Target step uses an outer task card and an inner tinted target card. Place uses two rounded cards within the panel. | high | Replace target nesting with a location block, divider, and checklist. Keep place choices as two simple rows/sections. |
| Repeated card shape | Place, methodology, secondary metrics, source notes, target, privacy notice, and unknown rows all use bordered rounded containers. | high | Reserve a bordered surface for an interactive selection only; use section spacing and rules elsewhere. |
| Pill/badge overuse | Result has an Area/status pill; every metric has a status pill; every task repeats `未確認`. | high | Remove the Area pill and Public metric pills. Show `未確認` once for the selected field check. |
| Rounded rectangle overuse | CSS contains 6–16 px radius on most panel components plus 999 px pills. | high | Use three restrained radii: 0, 4 px, and 8 px; avoid pill geometry unless it is a map point. |
| Equal section weight | Five stories, unknowns, methodology, source notes, and status all appear as component surfaces. | medium | Make result heading and metric values primary; map action and details secondary. |
| Border everywhere | Progress, panel, five groups, metrics, disclosures, target cards, actions, and notices each add a border. | high | Use one panel boundary and section dividers; remove borders around explanatory text. |
| Unnecessary shadow | Public information surfaces mostly avoid shadows; the map reference marker uses one meaningful halo. | low | Preserve the marker halo; do not add panel shadows. |
| Meaningless gradient | None in the Public Area baseline. | none | Keep it absent. |
| Oversized dark callout | Unknown is a full dark rounded block with light text; selection adds amber, resembling warning severity. | high | Use a light section and simple selectable rows; retain amber only for keyboard focus, not uncertainty severity. |
| Abstract kicker | `舞鶴市の公開データを使った確認`, `選んだ範囲の結果`, `確認場所と未確認項目` repeat context above headings. | high | Remove Public kickers; use one small current-stage label. |
| ALL CAPS English heading | Public Area hides shared `QUANTIFIED EVIDENCE` and `KNOWN / UNKNOWN`, but legacy/Advanced still contains English technical headings. | Public low | Keep Public suppression; do not redesign Advanced in this goal. |
| Mechanical verbs | `確認`, `分からない`, `場所`, `データの限界` repeat in heading, lead, target card, legend, and privacy note. | high | Assign one phrase to each stage and remove paraphrases of visible UI. |
| Long explanation for short content | Target heading, area heading, lead, target label, task title, and privacy paragraph restate the same action. | high | Use `現地で確認する場所`, one location name, one checklist heading, one short boundary note. |
| UI re-explained in prose | Source notes say content was “separated from what you read first”; target lead explains that 3–5 checks are displayed immediately above them. | high | Delete meta-UI prose. |
| Repeated status | `未確認` appears in the Area label and again in each task. | high | One state label in the target section. |
| Internal concepts leak | First view includes `PLATEAU上の確認対象`; source details expose `coverage`, `version`, `content`, object IDs without Japanese labels. | high | Rename first-view terms; keep exact provenance only inside a clearly labeled disclosure with Japanese field names. |
| Duplicate CTA meaning | On result, each story has `地図で見る` plus the primary `確認場所を見る`; these are distinct but visually close. | medium | Keep story links quiet and textual; keep one filled primary CTA. |
| Explanation dominates label | Place cards and target screen use multiple sentences before the core action. | medium | Make labels and values scan first; one sentence maximum per choice. |
| Everything is boxed | Unknown and task screens depend on boxes more than spacing. | high | Convert to a reading sequence with headings, rows, ordered list, and dividers. |
| Decorative color | Dark green unknown surface and amber selected state imply severity not in the model. | high | Use neutral background; retain semantic Area/known/target map colors. |
| Decoration instead of typography | Progress circles and repeated bordered surfaces carry hierarchy. | high | Replace circles with `step / total + stage`; use heading/value scale and 16/24/32 px section gaps. |

## Language diagnosis

- Landing heading is concrete and can remain. Its long subcopy and disclaimer make the first panel read like product documentation.
- Result repeats “分かっている／確認できた” in page heading, section heading, metric badges, and story button state.
- Unknown is conceptually important but is styled like a danger alert. The data contract does not assign danger or severity.
- Target uses system language (`PLATEAU上の確認対象`, `対象データ`, `未確認項目`) where a field user needs place and action words.
- Provenance exists and must remain, but public labels should be Japanese and exact IDs must not be in the initial reading path.
- The four numbered circles make a short map flow resemble a tutorial wizard. A stage label is sufficient.

## Baseline strengths to preserve

- one header utility action (`詳細分析`) and one Landing primary CTA;
- 67.9/32.1 desktop map/panel relation;
- map semantics for Area, five stories, exact building, exact road, facility position, and honest fallback;
- 390 × 844 zero-overflow/zero-overlap behavior;
- focus outlines and 44 px touch targets;
- source dates, methodology, coverage/provenance, and claim boundaries;
- no decorative gradients and almost no unnecessary shadows;
- exact-target fast path and performance gates.

## H2 target

The Public surface tree should be no deeper than:

```text
page
  map
  panel
    stage content
```

Interactive choices may have one local boundary. Information groups use headings, rows, spacing, and dividers. The after inventory will be generated at H5; this audit is not a human aesthetic result.
