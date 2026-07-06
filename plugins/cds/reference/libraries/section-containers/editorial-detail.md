---
kind: section-container
name: editorial-detail
family: editorial
aliases: [editorial detail page, blog post, article page, post page]
status: stable
default_shell: marketing
sections:
  - { id: E1, required: true, notes: "always first" }
  - { id: E2, required: true, notes: "the only saturated panel surface on the page" }
  - { id: E3, required: true }
  - { id: E4, required: true, notes: "closes the article body" }
  - { id: E5, required: true, notes: "always last" }
constraints: []
register:
  type_scale: editorial
  motion_register: editorial
---

# Editorial Detail Page

Long-form article reading: legibility, scannability, and a quiet, confident tone. Structurally the simplest Section Container after authentication. The Shell supplies topbar and footer; this container is content Sections only, in the fixed order above.

## Theme

`editorial` for the entire page, single-theme: themes do not rotate inside the article body, and the E2 illustration tile is the only saturated panel. The footer's `deep` island belongs to the Shell.

## Register rules

### Layout

- Outer container: `--container-editorial` (calibrates to 1400px).
- Reading column: `--column-reading` (calibrates to 640px), centered within the outer container.
- Side gutter: responsive, calibrating to 32 / 48 / 64px across the breakpoints.
- Section padding, header to tile to body: `--sp-3` each (calibrates to 48px).

### Navigation

- Sticky topbar with hide-on-scroll: hides on downward scroll past the header height and returns on upward scroll, over a 300ms transform transition.

### Typography (editorial scale, `foundations/typography.md` §13.5)

- Title: Headline 1 (`text-wrap: balance`, `text-align: center`).
- Subjects (eyebrow): Body 3 with the `.bold` modifier (the role's documented editorial-eyebrow weight range, 500–700), sentence case.
- Date: Body 3 agate at `--text-tertiary`.
- Body paragraph: Body 2 with the `.serif` modifier, margin-block `--sp-1` (calibrates to 16px).
- Section h2: Headline 5 (`text-wrap: pretty`, margin `var(--sp-1-5)`/`calc(2 * var(--sp-1))` 0 `var(--sp-0-5)` 0 — calibrates to 24px/32px 0 8px 0).
- Inline link: same ink as body; underline at 0.08em thickness, 0.18em offset.
- Blockquote: text at `--text-secondary`; 1px left rule at `--border-strong`; padding calibrates to `4px 0 4px 16px`.

### Components

- Article hero, related-content rail, social-share row, featured illustration tile.

### Motion (editorial register, `foundations/motion.md` §15.3)

- `.contentFade` and `.contentFadeUp` scroll-into-view fades.
- 150ms inline link color cross-fade.
- 200ms hover opacity dim on featured cards.
- Topbar hide-on-scroll over 300ms.
- No parallax, no image zoom, no scroll-progress bar.

### Responsive

- Reading column takes the full container width below 700px.
- Title follows the Headline 1 role's responsive scale (calibrates 52px → 32px).
- Illustration tile inner padding scales `--sp-6` → `--sp-3` (calibrates 96px → 48px).

### Do not

- No back-link or breadcrumb above the article — readers return via the topbar.
- No scroll-progress bar.
