# Motion and Interaction

## §15.1 Easing curves

Define these tokens at the root and use them by name everywhere.

| Token | cubic-bezier | Use For |
|---|---|---|
| `--ease-snap` | `cubic-bezier(0.165, 0.85, 0.45, 1)` | Authentication CTA transforms. |
| `--ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | General-purpose color and border-color transitions. |
| `--ease-out-quart` | `cubic-bezier(0.165, 0.84, 0.44, 1)` | Scroll-into-view settles. |
| `--ease-in-quart` | `cubic-bezier(0.895, 0.03, 0.685, 0.22)` | "Read more" CTA color shifts; tab background-color transitions. |
| `--ease-in-out-quart` | `cubic-bezier(0.77, 0, 0.175, 1)` | Inline link color cross-fades; opacity fades. |
| `--ease-in-out-expo` | `cubic-bezier(1, 0, 0, 1)` | Max-height and dropdown opacity over longer durations. |
| `--ease-out-power2` | `cubic-bezier(0.165, 0.84, 0.44, 1)` | Stagger animations on cards and panels. |

## §15.2 Durations

| Duration | Use For |
|---|---|
| 100ms | Pill-tab color shift; auth secondary button 10-property transition. |
| 150ms | Inline link color cross-fade; auth primary button transform. |
| 200ms | Pill-tab background; button box-shadow ring; hover opacity dim on featured cards; auth `::after` highlight; footer link color. |
| 300ms | Button leading-icon color; scroll-into-view delay; sticky header hide-on-scroll. |
| 400–500ms | Scroll-into-view opacity and transform settle. |
| 600ms | Dropdown panel grow. |
| 750–1000ms | Hero word-by-word reveal stagger. |
| 0ms | Topbar at rest (no animation on the nav paint). |

## §15.3 Motion register by surface

| Surface | Motion Register |
|---|---|
| Primary landing page | Liveliest. Word-by-word hero reveal driven by `--reveal-index`, `--reveal-duration`, `--reveal-delay`, `--reveal-y`, `--reveal-stagger` CSS custom properties set by JavaScript on viewport entry. Card-grid in-view animation driven by `--card-index`. IntersectionObservers on the hero stack. Pill-tab swap. Status-spinner glyph animation inside code blocks. |
| Product overview page | Lighter. Scroll-driven panel that grows from an inset rounded panel to a full-bleed edge with `border-radius: 0; margin: 0; max-width: 100%`. Wrap the entire effect in `@media (prefers-reduced-motion: no-preference)` and reset the final state inside the reduced-motion media query. |
| Editorial detail page | Quiet. Scroll-into-view `.contentFade` opacity over 400ms with a 300ms delay. `.contentFadeUp` opacity + translateY(gutter) over 500ms with the same delay. Stagger items at 250ms / 500ms / 750ms / 1000ms for items 1–4. 200ms hover opacity dim on featured cards. 150ms inline link color cross-fade. 300ms header hide-on-scroll. No parallax. No image zoom. No scroll-progress bar. |
| Documentation page | Near-zero. Header has no transition. Footer links carry the only motion: a 200ms color transition. |
| Conversion page | Small. 100ms color and border-color on hover. 150–200ms transform plus radial-gradient highlight on the primary CTA. Lighter border on focus rather than a discrete ring. |
| Application shell page | Quiet. Toggle slide on switches (200ms). Dropdown chevron rotation. Standard cross-fade on tab and route changes. |

## §15.4 Reveal animation patterns

Use a CSS custom-property-driven reveal for hero word-by-word entrance:

```css
.reveal-word {
  opacity: 0;
  transform: translateY(var(--reveal-y, 0.5em));
  animation:
    revealWord
    var(--reveal-duration, 0.75s)
    var(--ease-out-quart)
    calc(var(--reveal-delay, 0s) + var(--reveal-index, 0) * var(--reveal-stagger, 60ms))
    forwards;
}
@keyframes revealWord {
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .reveal-word { animation: none; opacity: 1; transform: none; }
}
```

For card grids, use `--card-index` to stagger entry:

```css
.card-stagger {
  animation: cardRaise 0.4s var(--ease-out-power2) both;
  animation-delay: calc(var(--card-index, 0) * 80ms);
}
@keyframes cardRaise {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
```

For scroll-into-view fades:

```css
.content-fade { opacity: 0; }
.content-fade.is-inview {
  opacity: 1;
  transition: opacity 0.4s var(--ease-in-out-quart) 0.3s;
}
.content-fade-up {
  opacity: 0;
  transform: translateY(32px);
}
.content-fade-up.is-inview {
  opacity: 1;
  transform: translateY(0);
  transition: opacity 0.2s var(--ease-out-quart) 0.3s, transform 0.5s var(--ease-out-quart) 0.3s;
}
```

Add the `is-inview` class via an `IntersectionObserver` when the element first enters the viewport.

## §15.5 Reduced-motion

Wrap every keyframe animation in a reduced-motion gate:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Then opt back in only for transitions that carry essential information (focus rings, error appearance) by overriding inside more specific rules.

## §15.6 Signature motion details

- Text-selection background is the `selection-bg` role, applied globally: `::selection { background-color: var(--selection-bg); }`. The actual tint (a 50% accent mix) lives in that role's fallback in the elements YAML — the CSS names no swatch.
- The `--accent-heroes` slot recolors decorative mascot or hero SVG art per theme. The artwork inherits the slot via `currentColor`. Do not author per-theme artwork.

## Known gaps

- §15.2 lists a "750–1000ms" range for hero word-by-word reveal stagger without prescribing how to choose a value inside the range.
- §15.3 references CSS classes (`.contentFade`, `.contentFadeUp`) and CSS custom properties (`--reveal-index`, `--card-index`, etc.) whose authoring contracts live in §15.4; the surface-by-surface register is descriptive prose, not enumerated tokens.
- §15.6 references the `selection-bg` and `accent-heroes` roles — defined and bound in the elements YAML, not in this file. No swatch is named here.
