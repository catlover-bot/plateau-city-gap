# Cartographic guidelines

## Hierarchy

1. One primary thematic layer.
2. Selected location with a dark, high-contrast outline.
3. Top candidate or scenario site labels.
4. Relevant context such as facilities or roads.
5. Low-saturation GSI pale basemap.

The basemap must support orientation without competing with the analysis. Attribution is always visible and links to the GSI tile catalogue.

## Scale rules

- Low zoom: municipal boundary, 500m screening surface, top candidates only.
- Medium zoom: mesh structure and major clustered facilities.
- High zoom: roads, unclustered facilities, scenario routes.
- Very high zoom / 3D: PLATEAU buildings and attributes.

Normal mesh outlines are absent or extremely subtle at overview. Hover introduces an outline. Selection uses a strong outline. In 3D the mesh is context, not a competing heatmap.

## Symbols and labels

Priority is selected entity, scenario site, top candidate, then major facility. MapLibre collision handling remains enabled. Bus stops begin later than stations/medical facilities. Labels must not be used as a substitute for a selection outline.

## Comparison conventions

- PLATEAU experimental route: solid blue.
- Reference route: dashed green.
- Disagreement: amber emphasis.
- Temporal added: teal `＋`; removed: brick dashed `−`; changed: amber outline `△`.
- Scenario A/B/C: stable teal/amber/mauve.

## QA gate

Browser QA checks that the active layer is named, selected state has a non-color outline, labels use collision avoidance, a contextual legend exists, attribution is visible, map controls do not critically occlude each other, symbols are zoom-filtered, and 390/768/1024/1280/1440 widths have no horizontal overflow.
