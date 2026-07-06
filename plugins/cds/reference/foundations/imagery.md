# Imagery, Iconography, and Decorative Elements

## §16.1 Iconography

- All inline SVGs use `fill="none"` on the outer `<svg>` and `fill="currentColor"` on every inner `<path>`.
- Icons inherit `--text-tertiary` by default and recolor automatically with the surrounding theme.
- Use filled shapes, not strokes. Do not use `stroke-width` on marketing icons.
- Tertiary text links use a trailing SVG arrow (the `--icon-viewbox-lg` drawing grid) as the "read more" affordance.

**Icon scale.** The drawing grids and container sizes below are the icon scale's intrinsic tokens — standalone design choices no other scale derives. Viewbox tokens are unitless drawing grids (`--icon-viewbox-md` = 20 ⇒ `viewBox="0 0 20 20"`); size tokens are rendered container dimensions.

| Token | Value | Applies to |
|---|---:|---|
| `--icon-viewbox-sm` | 18 | Small glyph drawing grid. |
| `--icon-viewbox-md` | 20 | Default glyph drawing grid. |
| `--icon-viewbox-lg` | 30 | Read-more arrow drawing grid. |
| `--icon-viewbox-xl` | 32 | Feature-glyph drawing grid. |
| `--icon-size-inline` | 20px | Link-arrow container. |
| `--icon-size-marginalia` | 24px | Marginalia rail icon container. |
| `--icon-size-feature` | 32px | Feature icon container. |
| `--icon-size-button` | 40px | Button leading-icon area. |
| `--icon-size-app-rail` | 16px | Application-shell rail glyph — line-art with single-pixel strokes (the only stroked-icon context). |

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
  /* §11.1 interpolation, Min 48px -> Max 128px (3 and 8 units of the §11.4
     spacing scale; Min calibrates to the --sp-3 1440px-anchor value). */
  padding: clamp(48px, calc(48px + 80 * (100vw - 320px) / 1120), 128px);
}
/* Variant classes are emitted DATA-DRIVENLY — generate-stylesheets emits one
   `.feature-tile--N` (and one shape-agnostic `.ground--N`) per `tile-ground-N`
   role declared in the YAML, so the variant set's size follows the data, not
   this file. Ground and ink come from the theme's `tile-ground-*` (constrained
   to `panels`) and `tile-ink-*` (constrained to `text`) roles; the author picks
   a ground number, the theme decides the color. No `--color-*` swatch appears
   here. The shipped YAML declares 1/2/3/accent (shown below as illustration);
   adding `tile-ground-4` yields `.feature-tile--4` / `.ground--4` automatically. */
.feature-tile--1 { background: var(--tile-ground-1); color: var(--tile-ink-1); }
.feature-tile--2 { background: var(--tile-ground-2); color: var(--tile-ink-2); }
.feature-tile--3 { background: var(--tile-ground-3); color: var(--tile-ink-3); }
.feature-tile--accent { background: var(--tile-ground-accent); color: var(--tile-ink-accent); }
```

The SVG inside picks up the tile's `color` value, so a single mark can recolor cleanly per tile. Because the grounds are theme-bound, a light theme can fill them from soft `pastel` colors while a dark theme fills the same roles from deep `stronger` colors — without the tile markup changing.
