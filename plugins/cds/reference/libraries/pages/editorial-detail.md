---
kind: page
name: editorial-detail
page_family: editorial
aliases: [editorial detail page, blog post, article page, post page]
status: stable
sections:
  - { section: article-header, required: true, notes: "always first" }
  - { section: illustration-tile, required: true, notes: "the only saturated panel surface on the page" }
  - { section: article-body, required: true }
  - { section: social-share, required: true, notes: "closes the article body" }
  - { section: related-content, required: true, notes: "always last" }
constraints: []
---

# Editorial Detail Page

Long-form article reading: legibility, scannability, and a quiet, confident tone. Structurally the simplest Page after authentication. This Page is content Sections only, in the fixed order above; the top-nav and site-footer Sections belong to the user's Shell.

## Theme

`editorial` for the entire page, single-theme: themes do not rotate inside the article body, and the illustration-tile Section is the only saturated panel. Any footer treatment belongs to the user's Shell.

## Register rules

### Layout

- Outer container: `--container-editorial` (calibrates to 1400px).
- Reading column: `--column-reading` (calibrates to 640px), centered within the outer container.
- Side gutter: responsive, calibrating to 32 / 48 / 64px across the breakpoints.
- Section padding, header to tile to body: `--sp-3` each (calibrates to 48px).

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
- No parallax, no image zoom, no scroll-progress bar.

### Responsive

- Reading column takes the full container width below 700px.
- Title follows the Headline 1 role's responsive scale (calibrates 52px → 32px).
- Illustration tile inner padding scales `--sp-6` → `--sp-3` (calibrates 96px → 48px).

### Do not

- No back-link or breadcrumb above the article.
- No scroll-progress bar.
