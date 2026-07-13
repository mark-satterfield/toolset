# Typography

## §13.1 Type families

Define exactly three font families. Refer to them by role, not by foundry or proprietary name. Map your chosen fonts into each role.

The three role slots are:

- **Primary Sans** (`--font-sans`) — humanist variable sans with friendly, contemporary character. Used for UI, body sans, headlines on editorial and authentication, button labels, captions.
- **Editorial Serif** (`--font-serif`) — literary variable serif with high-contrast strokes and editorial gravitas. Used for headings on marketing pages; body prose on long-form editorial and legal; marketing-headline serif on conversion pages.
- **System Mono** (`--font-mono`) — technical monospace with clear digit and bracket forms. Used for code blocks, mono micro-text.

The specific typeface assigned to each role is a project-level choice and is supplied via the elements YAML referenced by `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`. This file does not name typefaces.

Fallback stacks are baked into the role definitions:

| Family Role | CSS Variable | Fallback Stack |
|---|---|---|
| Primary Sans | `--font-sans` | `system-ui, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif` |
| Editorial Serif | `--font-serif` | `Georgia, "Times New Roman", serif` |
| System Mono | `--font-mono` | `"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace` |

## §13.2 Font mapping instructions

Use this subsection to choose and integrate your mapped fonts.

**How to choose replacement fonts**

- For the Primary Sans role: pick a humanist sans with a clear lowercase, moderate stroke contrast, and a complete variable weight axis (300–800). Avoid geometric sans-serifs at this role — they read flat in body type.
- For the Editorial Serif role: pick a serif with strong letterform character at large display sizes, a comfortable body reading weight, and italic and variable weight axes. Avoid slab serifs and monolinear serifs at this role.
- For the System Mono role: pick a monospace with non-ambiguous glyph forms (clear `0` / `O`, `1` / `l` / `I`), a complete weight range, and ligature support.

**What characteristics to preserve**

- A clear hierarchy between Primary Sans and Editorial Serif. The two families should read as visibly different in voice, not merely different in serifs/sans.
- Variable weight axes on Primary Sans and Editorial Serif if possible, because the button-weight compensation rules use intermediate weights such as 480 and 500.
- Italic axes on both Primary Sans and Editorial Serif. Italic emphasis is used in marginalia rails and in legal defined-term notation.

**How to map the chosen fonts into CSS variables**

```css
:root {
  --font-sans: "Your Sans Family", system-ui, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  --font-serif: "Your Serif Family", Georgia, "Times New Roman", serif;
  --font-mono: "Your Mono Family", "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
}
```

Load your fonts with `font-display: swap` to avoid invisible-text flashes during font loading.

**How to handle non-variable fonts**

If a mapped font does not support a variable weight axis, approximate the intermediate weights as follows:

| Required Weight | Variable Font | Non-Variable Substitution |
|---:|---:|---:|
| 330 | 330 | 300 |
| 430 | 430 | 400 |
| 480 | 480 | 500 |
| 500 | 500 | 500 |

Document any substitutions in your team's mapping notes. The button-weight oscillation effect is dampened when both light and dark buttons resolve to 500; consider mapping a slightly lighter weight (e.g., 400 vs 500) instead of 480 vs 500 to preserve perceived contrast.

**How to preserve the typographic hierarchy without preserving the original font identity**

- Keep the **role distinction**: serif for editorial body and marketing headings; sans for UI, editorial headings, and authentication.
- Keep the **scale**: 21-step type ladder from 10px Micro to 80px Display XXL.
- Keep the **line-height ratios**: 100% for display, 110–120% for headlines, 140–155% for body.
- Keep the **letter-spacing rules**: 0 default, 0.01em on caption, 0.05em on uppercase micro.
- Keep the **text-wrap rules**: `balance` on display and centered headlines; `pretty` on body headings.

## §13.3 Weight, line-height, tracking slots

| Token | Value |
|---|---:|
| `--fw-300` | 300 |
| `--fw-400` | 400 |
| `--fw-480` | 480 |
| `--fw-500` | 500 |
| `--fw-600` | 600 |
| `--fw-700` | 700 |
| `--lh-100` | 1 |
| `--lh-110` | 1.1 |
| `--lh-120` | 1.2 |
| `--lh-130` | 1.3 |
| `--lh-140` | 1.4 |
| `--lh-150` | 1.5 |
| `--lh-160` | 1.6 |
| `--lh-170` | 1.7 |
| `--track-0` | 0 |
| `--track-0-01` | 0.01em |
| `--track-0-05` | 0.05em |

## §13.4 Marketing scale (serif headings, sans body)

Clamp between a 20rem viewport (`min`) and a 90rem viewport (`max`).

| Text Role | Min Size | Max Size | Family | Weight | Line Height | Tracking | Use |
|---|---:|---:|---|---:|---:|---:|---|
| Display-1 | 42px | 72px | Serif | 500 | 1.1 | 0 | Above-the-fold hero h1. `text-wrap: balance`, `max-width: 20ch`. |
| Display-2 | 36px | 64px | Serif | 500 | 1.1 | 0 | Alternate hero h1. |
| H1 | 34px | 52px | Serif | 500 | 1.2 | 0 | Major section heading. |
| H2 | 30px | 44px | Serif | 500 | 1.2 | 0 | Section heading. |
| H3 | 28px | 36px | Serif | 500 | 1.2 | 0 | Card titles, pricing-plan names. |
| H4 | 23px | 32px | Serif | 500 | 1.1 | 0 | Card subheading. |
| H5 | 20px | 25px | Serif | 500 | 1.2 | 0 | Compact heading. |
| H6 | 16px | 19px | Serif | 500 | 1.2 | 0 | Icon-label headline. `max-width: 30ch`, `text-wrap: pretty`. |
| Body Large 1 | 22px | 24px | Sans | 400 | 1.6 | 0 | Lead paragraph. |
| Body 1 | 19px | 20px | Sans | 400 | 1.6 | 0 | Default body. |
| Body 2 | 17px | 17px | Sans | 400 | 1.6 | 0 | Button label, small body. |
| Body 3 | 15px | 15px | Sans | 400 | 1.6 | 0 | Nav links, dense text. |
| Caption | 12px | 12px | Sans | 400 | 1.6 | 0.01em | Pill-tab label, eyebrow. `max-width: 30ch`. |
| Micro | 10px | 10px | Sans | 400 | 1.6 | 0.05em | Uppercase legal eyebrow. `text-transform: uppercase`. |

## §13.5 Editorial scale (sans headings, serif body)

Use on long-form editorial, news, documentation, and legal Section Containers. The headline scale uses Primary Sans at heavy weights; the body uses Editorial Serif. Clamp between a 20rem viewport (`min`) and a 90rem viewport (`max`) per layout.md §11.1. Roles whose Min and Max are equal are fixed-value and declare their size directly without `clamp()`.

| Text Role | Min Size | Max Size | Family | Weight | Line Height | Use |
|---|---:|---:|---|---:|---:|---|
| Display XXL | 56px | 80px | Sans | 700 | 100% | Marketing-home hero h1. |
| Display XL | 48px | 64px | Sans | 700 | 100% | Brand mission h1. |
| Editorial-Display-1 | 42px | 72px | Sans | 700 | 100% | Available. |
| Editorial-Display-2 | 36px | 64px | Sans | 700 | 100% | Long-form legal page h1. |
| Display L | 32px | 48px | Sans | 700 | 100% | Available. |
| Display M | 28px | 32px | Sans | 700 | 100% | Available. |
| Display S | 22px | 24px | Sans | 700 | 100% | Tile heading on marketing home. |
| Headline 1 | 32px | 52px | Sans | 700 | 110% | Editorial page H1. `text-wrap: balance`, `text-align: center`. |
| Headline 2 | 30px | 44px | Sans | 600 | 120% | Editorial section H2. |
| Headline 3 | 28px | 36px | Sans | 600 | 120% | Sub-section H3. |
| Headline 4 | 23px | 32px | Sans | 600 | 120% | Featured-card title; "Related content" rail title. Underline at 0.2em offset on links. |
| Headline 5 | 20px | 25px | Sans | 600 | 120% | Legal section H2; long-form section H2. |
| Headline 6 | 17px | 23px | Sans | 600 | 120% | Side-item titles. |
| Paragraph L | 22px | 24px | Sans | 400 | 140% | Subtitle paragraph. `max-width: 40ch`. |
| Paragraph M | 18px | 20px | Sans | 400 | 140% | Default lead paragraph. |
| Paragraph S | 15px | 18px | Sans | 400 | 140% | Compact lead. |
| Body 1 | 19px | 20px | Sans | 400 | 155% | Default sans body on editorial. |
| Body 2 | 17px | 17px | Sans (or Serif with `.serif` modifier) | 400 (Sans) / 500 (Serif) | 155% | Editorial body paragraph. Serif modifier produces long-form reading body. |
| Body 3 | 15px | 15px | Sans (or Serif with `.serif`) | 400 (or 700 with `.bold`) / 500 (Serif) | 140% | Featured-card dek; meta paragraphs; editorial eyebrow (weight range 500–700 via `.serif` / `.bold`). |
| Body 4 | 12px | 12px | Sans | 400 (or 700 with `.bold`) | 140% | Footer column heading. |
| Caption | 14px | 14px | Sans | 400 | 120% | Column headers (uppercase via CSS). `letter-spacing: 0.15px`. |
| Text Label | 16px | 16px | Sans | 600 | 100% | Effective-date stamp, language picker. `letter-spacing: -0.08px`. |

## §13.6 Authentication card scale

Use this scale on conversion or authentication card surfaces. The weight values below are intentionally precise (430, 480, 500) and depend on a variable-axis font. Substitute per §13.2 if mapping a non-variable font. Line heights are size × a `--lh-*` ratio token (§13.3); each expression's calibration value is the pixel rendering it reproduces.

| Text Role | Family | Size | Weight | Line Height | Notes |
|---|---|---:|---:|---|---|
| Marketing headline outside card | Serif | 56px | 330 | `--lh-120` (calibrates to 67.2px) | Sits behind the card; weight 330 reads as ultralight on Serif. |
| Marketing subhead | Serif | 18px | 400 | `--lh-160` (calibrates to 28px) | |
| Input label | Sans | 14px | 430 | `--lh-140` (calibrates to 19.6px) | Ink at `--text-secondary`. |
| Required asterisk | Sans | 14px | 430 (inherit) | — | Ink at `--field-required`. |
| Input value and placeholder | Sans | 16px | 430 | `--lh-140` (calibrates to 22.4px) | Placeholder at `--text-tertiary`. |
| Button label | Sans | 16px | 500 | `--lh-150` (calibrates to 24px) | All button variants. |
| "OR" divider | Sans | 12px | 400 | `--lh-130` (calibrates to 16px) | Uppercase via CSS. |
| Legal blurb | Sans | 14px | 400 | `--lh-150` (calibrates to 21px) | Underlined inline link at 40% opacity at rest. |
| Top-nav link | Sans | 14px | 500 | — | Ink at `--text-tertiary`. |
| Top-nav primary button | Sans | 14px | 500 | `--lh-140` (calibrates to 19.6px) | |
| Footer column heading | Sans | 12px | 400 | `--lh-140` (calibrates to 16.8px) | Ink at `var(--text-tertiary)` (low-contrast cool gray when resolved through the footer's theme). |
| Footer link | Sans | 14px | 400 | `--lh-150` (calibrates to 21px) | No underline. |

## §13.7 Inline rules

| Rule | Applies To |
|---|---|
| Inline link in body type | Same ink as surrounding text; `text-decoration: underline`; thickness `0.08em` (= `~1.36px` at 17px body); offset `0.18em`. |
| Inline link hover | Color shifts toward `--text-tertiary` over 150ms; underline color follows text color via `text-decoration-color: currentColor`. |
| Inline `<strong>` in body | Same family as surrounding text; weight 600 in body-2 contexts, 700 inside list items. |
| Inline `<em>` | Italic axis of the same family. Do not substitute a different italic family. |
| Blockquote | Text at `--text-secondary`; 1px solid `--border-strong` left rule; padding `4px 0 4px 16px`. |
| Code (inline) | Mono family at 0.9em of surrounding size; subtle `--surface-tertiary` background; 4px radius; 2px horizontal padding. |
| Footnote | Color at `--text-tertiary`. |
| All-caps legal disclaimers | Set characters as upper-case in the source; do not apply `text-transform`. Render at the same body scale as surrounding prose. |
