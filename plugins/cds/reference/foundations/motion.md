# Motion and Interaction

Motion is a **configurable element set** — a first-class peer to color and geometry — defined in the elements YAML's `motion:` block (`motion.easing`, `motion.duration`, `motion.patterns`), resolved at `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`. The curves, durations, and pattern parameters below are the **canonical defaults the shipped YAML encodes**; `generate-stylesheets` sources their values from the YAML, not from this prose.

**Emission contract.** `generate-stylesheets` does two things with the `motion:` block, every time:

1. Emits the easing and duration tokens into `tokens.css` (`--ease-{key}`, `--duration-{key}`).
2. Emits the **entrance-motion patterns** — the reveal / stagger / fade keyframes and their pattern classes — into the generated CSS (§15.4), parameterized by the `motion.patterns` tokens, **plus** the global reduced-motion gate (§15.5). The patterns live in the design system so composers apply a class; they never author entrance keyframes per page.

Pattern key → emitted token prefix → emitted class:

| `motion.patterns` key | Token prefix | Emitted class | JS-set per-item var |
|---|---|---|---|
| `reveal` | `--reveal-*` | `.reveal-word` | `--reveal-index` |
| `card` | `--card-*` | `.card-stagger` | `--card-index` |
| `fade` | `--fade-*` | `.content-fade` | (adds `.is-inview`) |
| `fade-up` | `--fade-up-*` | `.content-fade-up` | (adds `.is-inview`) |

**Gating law (non-negotiable).** Entrance motion (reveal, stagger, fade, fade-up) animates in the **base rule** and is disabled **only** inside `@media (prefers-reduced-motion: reduce)`. Never gate entrance motion behind `@media (prefers-reduced-motion: no-preference)`: that silently removes the entrance for every reduce-motion user and, when the base rule starts at `opacity: 0`, can strand content invisible. `no-preference` is reserved for *continuous/ambient* enhancement whose static baseline is the no-animation state (e.g. a looping logo marquee, an optional expand transition) — not for first-paint or scroll-entry reveals. `audit-against-system` fails the `no-preference`-gated-entrance-motion pattern (`compliance.md` §23).

## §15.0 Page-load orchestration (landing & marketing)

On landing and marketing surfaces, treat motion as **one orchestrated page-load**, not scattered micro-interactions. Sequence the first-paint reveals with staggered `animation-delay` (the `--reveal-*` / `--card-*` parameters), let scroll position trigger the subsequent section entrances (`.content-fade` / `.content-fade-up`, with an `IntersectionObserver` adding `.is-inview`), and reserve **one high-impact moment** — a single surprising hover or entrance — rather than animating everything. A page reads as deliberate when a few elements move with intent and noisy when many move a little. All of this obeys the §15 gating law: entrance motion animates in the base rule and is disabled only under `@media (prefers-reduced-motion: reduce)`.

## §15.1 Easing curves

Define these tokens at the root and use them by name everywhere. Values come from `motion.easing` in the elements YAML; the table is the shipped default.

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

These are the exact CSS templates `generate-stylesheets` emits into the generated stylesheet set, parameterized by the `motion.patterns` tokens. Each pattern **animates in the base rule** and resets to its final visible state **only** inside `@media (prefers-reduced-motion: reduce)`. Inline `var(--token, <fallback>)` fallbacks equal the shipped defaults so the rule still resolves if a token is absent.

Hero word-by-word entrance (`reveal` → `.reveal-word`; JS sets `--reveal-index` per word):

```css
.reveal-word {
  opacity: 0;
  transform: translateY(var(--reveal-y, 0.5em));
  animation:
    revealWord
    var(--reveal-duration, 0.75s)
    var(--reveal-easing, var(--ease-out-quart))
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

Card-grid entry (`card` → `.card-stagger`; JS sets `--card-index` per card):

```css
.card-stagger {
  animation: cardRaise var(--card-duration, 0.4s) var(--card-easing, var(--ease-out-power2)) both;
  animation-delay: calc(var(--card-index, 0) * var(--card-stagger, 80ms));
}
@keyframes cardRaise {
  from { opacity: 0; transform: translateY(var(--card-y, 16px)); }
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .card-stagger { animation: none; opacity: 1; transform: none; }
}
```

Scroll-into-view fades (`fade` → `.content-fade`, `fade-up` → `.content-fade-up`):

```css
.content-fade { opacity: 0; }
.content-fade.is-inview {
  opacity: 1;
  transition: opacity var(--fade-duration, 0.4s) var(--fade-easing, var(--ease-in-out-quart)) var(--fade-delay, 0.3s);
}
.content-fade-up {
  opacity: 0;
  transform: translateY(var(--fade-up-y, 32px));
}
.content-fade-up.is-inview {
  opacity: 1;
  transform: translateY(0);
  transition:
    opacity var(--fade-up-duration, 0.5s) var(--fade-up-easing, var(--ease-out-quart)) var(--fade-up-delay, 0.3s),
    transform var(--fade-up-duration, 0.5s) var(--fade-up-easing, var(--ease-out-quart)) var(--fade-up-delay, 0.3s);
}
```

Add the `is-inview` class via an `IntersectionObserver` when the element first enters the viewport. The fade patterns are transition-based: the §15.5 global gate zeroes their transition-duration under reduced motion, so adding `is-inview` snaps the element to its visible state instantly — the content still appears. The entrance is the `.is-inview` add (base behavior), never a `no-preference` gate.

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
