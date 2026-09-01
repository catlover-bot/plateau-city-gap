# Cartographic reference evidence

Goal: `citygap-cartographic-visual-productization-v1`

Captured with Chromium at 1440×900. URLs, final URLs, HTTP status, hashes, and timestamps are recorded in [manifest.json](assets/cartographic-benchmark/manifest.json). Third-party captures are benchmark evidence only and are not Public product assets. Static screenshots do not prove hover, click, motion, camera, or feedback behavior; those fields remain `NOT_OBSERVED` unless the behavior was directly exercised.

## Capture catalog

| Reference | Browser result | Evidence |
|---|---|---|
| PIT Environmental Cost Route Finder | `CAPTURED / HTTP 200` | [screenshot](assets/cartographic-benchmark/pit-route-finder.png) |
| 自治体別課題 Wiki | `NON_VISUAL_REFERENCE / HTTP 200` | [screenshot](assets/cartographic-benchmark/municipal-wiki.png) |
| Urbanor PDF | `ACCESS_UNAVAILABLE / HTTP 404` | no screenshot |
| PLATONE | `PRESENTATION_CAPTURED / HTTP 200` | [screenshot](assets/cartographic-benchmark/platone.png) |
| Tide Viewer | `SHELL_CAPTURED_RENDER_UNCONFIRMED / HTTP 200` | [screenshot](assets/cartographic-benchmark/tide-viewer.png) |
| OnoCoro | `REPOSITORY_DOCUMENTATION_CAPTURED_APP_UNCONFIRMED / HTTP 200` | [screenshot](assets/cartographic-benchmark/onocoro.png) |
| iwagaki repository | `REPOSITORY_DOCUMENTATION_CAPTURED / HTTP 200` | [screenshot](assets/cartographic-benchmark/iwagaki-repository.png) |
| iwagaki viewer | `CAPTURED / HTTP 200` | [screenshot](assets/cartographic-benchmark/iwagaki-viewer.png) |
| PLATEAU Transit POC | `ACCESS_UNAVAILABLE_FOR_VISUAL_CAPTURE / HTTP 200` | no screenshot |

## 22-field teardown

### PIT Environmental Cost Route Finder

- `canvas_share`: map is the largest object in the main working row; not numerically measured.
- `basemap`: light, detailed street map.
- `primary_layer`: route-search map; an active route is not visible in the captured initial state.
- `secondary_layers`: `NOT_OBSERVED`.
- `color_encoding`: green is used for active workflow state and restrained emphasis.
- `selected`: active mode is visibly filled green.
- `hover`: `NOT_OBSERVED`.
- `click`: `NOT_OBSERVED`.
- `legend`: no map legend visible in the captured frame.
- `control_position`: preparation controls above; route conditions to the right; zoom on map.
- `control_density`: medium-high, grouped by task.
- `panel`: right-side search-conditions panel.
- `typography`: large Japanese value heading, smaller task labels.
- `light_dark_hierarchy`: light surface with dark green hierarchy.
- `motion`: `NOT_OBSERVED`.
- `camera`: `NOT_OBSERVED`.
- `direct_manipulation`: map and visible controls suggest it, but it was not exercised.
- `immediate_feedback`: `NOT_OBSERVED`.
- `empty_space`: low within the work area.
- `screenshot_wow`: useful map-first task clarity; not dependent on decoration.
- `plateau_visibility`: `NOT_OBSERVED`.
- `first_3_seconds`: environmental route map plus explicit search conditions.

### 自治体別課題 Wiki

- `canvas_share`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `basemap`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `primary_layer`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `secondary_layers`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `color_encoding`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `selected`: `NOT_OBSERVED`.
- `hover`: `NOT_OBSERVED`.
- `click`: `NOT_OBSERVED`.
- `legend`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `control_position`: GitHub repository navigation only.
- `control_density`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `panel`: text document.
- `typography`: GitHub document hierarchy.
- `light_dark_hierarchy`: standard GitHub light hierarchy.
- `motion`: `NOT_OBSERVED`.
- `camera`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `direct_manipulation`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `immediate_feedback`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `empty_space`: document-dependent.
- `screenshot_wow`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `plateau_visibility`: `NOT_APPLICABLE_NON_VISUAL_REFERENCE`.
- `first_3_seconds`: municipal problem statements, not a visual product.

### Urbanor PDF

All 22 fields—`canvas_share`, `basemap`, `primary_layer`, `secondary_layers`, `color_encoding`, `selected`, `hover`, `click`, `legend`, `control_position`, `control_density`, `panel`, `typography`, `light_dark_hierarchy`, `motion`, `camera`, `direct_manipulation`, `immediate_feedback`, `empty_space`, `screenshot_wow`, `plateau_visibility`, and `first_3_seconds`—are `NOT_OBSERVED_ACCESS_404`.

### PLATONE

- `canvas_share`: the presentation slide dominates the viewport.
- `basemap`: grayscale oblique 3D city context.
- `primary_layer`: volumetric building mass.
- `secondary_layers`: restrained gold spatial nodes and connecting cues.
- `color_encoding`: grayscale city plus gold emphasis.
- `selected`: `NOT_OBSERVED_STATIC_SLIDE`.
- `hover`: `NOT_OBSERVED_STATIC_SLIDE`.
- `click`: slide navigation exists; application behavior is not observed.
- `legend`: no legend in the captured title slide.
- `control_position`: presentation navigation at the slide edges.
- `control_density`: low.
- `panel`: no analytical side panel.
- `typography`: large centered product title.
- `light_dark_hierarchy`: dark surrounding frame, high-contrast white title.
- `motion`: `NOT_OBSERVED_STATIC_SLIDE`.
- `camera`: fixed oblique 3D overview.
- `direct_manipulation`: `NOT_OBSERVED_STATIC_SLIDE`.
- `immediate_feedback`: `NOT_OBSERVED_STATIC_SLIDE`.
- `empty_space`: spatial image is deliberately allowed to dominate.
- `screenshot_wow`: strong 3D spatial identity.
- `plateau_visibility`: city objects are the visual subject.
- `first_3_seconds`: a 3D urban spatial platform.

### Tide Viewer

- `canvas_share`: large central canvas.
- `basemap`: `NOT_OBSERVED_RENDER_UNCONFIRMED`.
- `primary_layer`: `NOT_OBSERVED_RENDER_UNCONFIRMED`.
- `secondary_layers`: `NOT_OBSERVED_RENDER_UNCONFIRMED`.
- `color_encoding`: cyan controls on a dark shell.
- `selected`: checkbox and select states are visible.
- `hover`: `NOT_OBSERVED`.
- `click`: `NOT_OBSERVED`.
- `legend`: water-level controls are visible, but a rendered legend is not confirmed.
- `control_position`: vertically grouped left panel; two utilities top-right.
- `control_density`: medium.
- `panel`: compact left-side parameter panel.
- `typography`: small technical labels with a clear viewer heading.
- `light_dark_hierarchy`: dark shell.
- `motion`: `NOT_OBSERVED`.
- `camera`: `NOT_OBSERVED_RENDER_UNCONFIRMED`.
- `direct_manipulation`: visible controls were not exercised.
- `immediate_feedback`: `NOT_OBSERVED`.
- `empty_space`: high because the actual render did not complete in the captured checkpoint.
- `screenshot_wow`: `NOT_ASSESSED_RENDER_UNCONFIRMED`.
- `plateau_visibility`: LOD building availability is stated in copy; geometry is not visibly rendered.
- `first_3_seconds`: specialist tide controls and an unloaded 3D canvas.

### OnoCoro

- `canvas_share`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `basemap`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `primary_layer`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `secondary_layers`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `color_encoding`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `selected`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `hover`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `click`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `legend`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `control_position`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `control_density`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `panel`: repository documentation only.
- `typography`: GitHub README hierarchy.
- `light_dark_hierarchy`: standard GitHub light hierarchy.
- `motion`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `camera`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `direct_manipulation`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `immediate_feedback`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `empty_space`: `NOT_OBSERVED_APP_UNCONFIRMED`.
- `screenshot_wow`: `NOT_ASSESSED_APP_UNCONFIRMED`.
- `plateau_visibility`: README confirms a PLATEAU-based project; the app visual is not captured.
- `first_3_seconds`: project purpose and prototype release, not application cartography.

### iwagaki repository documentation

- `canvas_share`: README comparison image is the dominant content in its documented frame.
- `basemap`: grayscale 3D urban and terrain context.
- `primary_layer`: three inundation/difference views presented side by side.
- `secondary_layers`: buildings and terrain.
- `color_encoding`: blue inundation, warm difference points, grayscale context.
- `selected`: three fixed comparison states.
- `hover`: `NOT_OBSERVED_STATIC_DOCUMENTATION`.
- `click`: `NOT_OBSERVED_STATIC_DOCUMENTATION`.
- `legend`: comparison meaning is explained by the caption.
- `control_position`: `NOT_OBSERVED_STATIC_DOCUMENTATION`.
- `control_density`: `NOT_OBSERVED_STATIC_DOCUMENTATION`.
- `panel`: no application panel in the documented comparison image.
- `typography`: short caption immediately below the comparison.
- `light_dark_hierarchy`: light README around a dark map comparison.
- `motion`: `NOT_OBSERVED_STATIC_DOCUMENTATION`.
- `camera`: consistent oblique comparison camera.
- `direct_manipulation`: `NOT_OBSERVED_STATIC_DOCUMENTATION`.
- `immediate_feedback`: `NOT_OBSERVED_STATIC_DOCUMENTATION`.
- `empty_space`: low in the comparison image.
- `screenshot_wow`: clear spatial difference in one glance.
- `plateau_visibility`: PLATEAU roads/buildings are part of the compared spatial evidence.
- `first_3_seconds`: three comparable spatial states with a clear difference encoding.

### iwagaki viewer

- `canvas_share`: 3D map occupies most of the viewport.
- `basemap`: detailed grayscale terrain, harbor, road, and building context.
- `primary_layer`: flood accumulation and water-surface state.
- `secondary_layers`: terrain/buildings, left parameters, and bottom profile chart.
- `color_encoding`: blue water, grayscale city/terrain, yellow/cyan chart lines.
- `selected`: active depth and time values are explicit in the left panel.
- `hover`: `NOT_OBSERVED`.
- `click`: `NOT_OBSERVED`.
- `legend`: chart and state keys are integrated along the bottom.
- `control_position`: left vertical controls, orientation cube top-right, chart bottom.
- `control_density`: high and specialist-oriented.
- `panel`: left control panel plus bottom analytical chart.
- `typography`: compact technical labels.
- `light_dark_hierarchy`: dark high-density analytical interface.
- `motion`: `NOT_OBSERVED_STATIC_CAPTURE`.
- `camera`: oblique 3D overview connecting harbor and terrain.
- `direct_manipulation`: visible controls were not exercised.
- `immediate_feedback`: `NOT_OBSERVED_STATIC_CAPTURE`.
- `empty_space`: low.
- `screenshot_wow`: strong spatial relationship among terrain, urban fabric, and water.
- `plateau_visibility`: PLATEAU objects are central evidence, not decoration.
- `first_3_seconds`: specialist 3D inundation model plus linked profile.

### PLATEAU Transit POC

All 22 fields—`canvas_share`, `basemap`, `primary_layer`, `secondary_layers`, `color_encoding`, `selected`, `hover`, `click`, `legend`, `control_position`, `control_density`, `panel`, `typography`, `light_dark_hierarchy`, `motion`, `camera`, `direct_manipulation`, `immediate_feedback`, `empty_space`, `screenshot_wow`, `plateau_visibility`, and `first_3_seconds`—are `NOT_OBSERVED_RENDER_UNAVAILABLE`.

## Applied and rejected principles

Applied:

- make spatial evidence the largest and first-read element;
- keep one active story at a time;
- synchronize panel selection, object geometry, legend, and camera;
- treat PLATEAU geometry as an evidence target;
- preserve orientation context while emphasizing the Area.

Not copied:

- product brands, words, CSS, composition, or screenshots;
- iwagaki's dark specialist shell, inundation colors, hazard grammar, dense controls, or persistent 3D;
- PIT's route-planning workflow;
- PLATONE's constant 3D composition;
- any visual claim from inaccessible or incompletely rendered references.
