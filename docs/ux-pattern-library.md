# UX pattern library: field-verification loop

This library records principles, not competitor layouts, wording, assets, CSS or branding.

| Pattern | Learned from | M3 application | Anti-copy boundary |
|---|---|---|---|
| One-sentence value | My City Report | “地図だけでは分からないことを、現地で確かめる場所とタスクに変える。” | No citizen-post interface or copied vocabulary |
| Map-first selection | Remix | Start by selecting a real Maizuru candidate | No route drawing, timetable or frequency editing |
| Contextual 3D | ArcGIS Urban | Show 3D only for a renderable PLATEAU target | No scenario/building editor |
| Assignment lifecycle | Field Maps | At M3 show only the initial `未確認` state | No generic task layer or assignment optimization |
| Conditional evidence | Survey123 | Later phases may use fixed templates only | No arbitrary schema or expression builder |
| Submitted-state feedback | My City Report | Deferred beyond M3 and remains provisional | No public report feed |
| Connected loop | Maptionnaire | Keep stable IDs from Finding through target and task | No survey/dashboard platform |

## M3 public sequence

1. Select a real Maizuru candidate on the map.
2. Show at most four unknowns and why each can change the decision.
3. Link each unknown to a real, versioned PLATEAU building, road or mesh fallback.
4. Derive only three to five required checks.
5. End at `未確認`; do not show invented evidence or review.

The public path avoids internal labels where possible. Provenance details remain inspectable so the demonstration is auditable.
