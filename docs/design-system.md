# Product design system

## Visual character

CITY GAP uses a restrained Japanese civic/GIS language: paper-like off-white surfaces, dark ink, thin administrative rules, compact type, and map-first hierarchy. It avoids gradients, glass effects, neon, giant KPI cards, decorative illustration, chatbot motifs, and dashboard tile walls.

## Tokens

`design-system/tokens.css` defines role-based color, spacing, radius, shadow, font, z-index, and map layers. Teal means analysis/PLATEAU continuity; amber means candidates or explicit assumptions; brick means medical/removal; blue-gray means transport/reference; purple-gray means hazard context; near-black is the selected outline.

Color is not the sole carrier. Selection adds a heavy outline, reference routes are dashed, temporal removal is dashed and prefixed by “−”, additions use “＋”, changes use “△”, and status includes text.

## CSS ownership

The 3,012-line `styles.css` is frozen as a legacy regression surface for retained components. New work is split by responsibility:

- `design-system/tokens.css`: primitives
- `app/product-shell.css`: shell, header, purpose navigation, responsive layout
- `map/map.css`: renderer controls, presets, legend, compare
- `features/inspector/inspector.css`: Inspector and task workspaces

New selectors are scoped under product components where legacy class names overlap.

## Responsive behavior

- Desktop: map plus 370px Context Inspector.
- 1024px/tablet landscape: map plus 330px Inspector and reduced preset set.
- 768×1024: full-width map with a floating 330px Inspector.
- 390px: full-screen map and a bottom sheet, compact purpose navigation, and progressive layer disclosure.

The desktop Inspector is not merely scaled down on mobile. It changes placement, height, handle, header, and initial content density.
