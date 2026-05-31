# Imagery, Iconography, and Decorative Elements

## §16.1 Iconography

- All inline SVGs use `fill="none"` on the outer `<svg>` and `fill="currentColor"` on every inner `<path>`.
- Icons inherit `--text-tertiary` by default and recolor automatically with the surrounding theme.
- Use filled shapes, not strokes. Do not use `stroke-width` on marketing icons.
- Common viewbox sizes: `0 0 18 18`, `0 0 20 20`, `0 0 30 30`, `0 0 32 32`.
- Icon container sizes: 20px for link arrows, 24px for marginalia rail icons, 32px for feature icons, 40px for button leading-icon area.
- Application-shell rail icons are 16px line-art with single-pixel strokes (the only stroked-icon context).
- Tertiary text links use a trailing 30×30 SVG arrow as the "read more" affordance.

## §16.2 Mascot and decorative illustration

- Bind decorative mascot artwork — an animated mascot illustration tied to the host project's brand identity — through `--accent-heroes`. The artwork inherits its color from the surrounding theme. Reserve the slot for one piece of mascot art per page maximum.
- Use flat SVG illustration on a tinted ground for editorial featured cards. Place an abstract geometric glyph centered inside a feature-tile at 16:9 (lead) or 1:1 (side) aspect-ratio. The tile ground is a theme-bound `tile-ground-*` role (constrained to the `panels` palette) — never a named color.
- Reserve a small dark sub-panel inside the marketing hero card for a marquee-style accent glyph painted in `--accent-primary` on a deep `--surface-*` ground. Both come from the active theme; the markup names no swatch.

## §16.3 Photography

Use photography sparingly. The default surface set carries zero photography on conversion, legal, and editorial index pages. When photography is needed:

- Confine it to a single hero panel on the marketing home, optionally inside a scroll-driven panel that grows from inset rounded to full-bleed.
- Use `.webp` for all photographic and screenshot content.
- Use `.svg` for logos and illustrations.
- Use `.jpg` for share images only (Open Graph and social-card previews).
- Generate `srcset` with breakpoints at `500w / 800w / 1080w / native`.

## §16.4 Featured illustration tile

For every editorial featured card, place a centered SVG illustration on a saturated tinted ground:

```css
.feature-tile {
  aspect-ratio: 16 / 9;
  border-radius: var(--radius-lg);
  display: grid;
  place-items: center;
  padding: clamp(48px, 8vw, 128px);
}
/* Tile variants are POSITIONAL, never color-named. Ground and ink come from
   the active theme's feature-tile roles — `tile-ground-*` (constrained to the
   `panels` palette) and `tile-ink-*` (constrained to `text`) in the elements
   YAML. The author picks a tile number; the theme, not this CSS, decides the
   color. No `--color-*` swatch ever appears here. */
.feature-tile--1 { background: var(--tile-ground-1); color: var(--tile-ink-1); }
.feature-tile--2 { background: var(--tile-ground-2); color: var(--tile-ink-2); }
.feature-tile--3 { background: var(--tile-ground-3); color: var(--tile-ink-3); }
.feature-tile--accent { background: var(--tile-ground-accent); color: var(--tile-ink-accent); }
```

The SVG inside picks up the tile's `color` value, so a single mark can recolor cleanly per tile. Because the grounds are theme-bound, a light theme can fill them from soft `pastel` colors while a dark theme fills the same roles from deep `stronger` colors — without the tile markup changing.

## Known gaps

- §16.2 references `--accent-heroes` — a role token defined in the palette/role foundations, not in this file. The mascot art itself is supplied by the host project's brand-assets directory.
- §16.4 feature-tiles consume **roles only** (`--tile-ground-1..3`, `--tile-ground-accent`, and their paired `--tile-ink-*`). They name no color and no swatch. The tile-ground roles are constrained (`from_palette: panels`) and bound per theme in the elements YAML, so the palette of grounds is a data decision, not a CSS decision. Variant classes are positional (`.feature-tile--1/2/3/accent`), never color-named.
- §16.3 srcset breakpoint values (`500w / 800w / 1080w / native`) are stated as a generic recommendation; which page types or surfaces invoke them is not specified.
