# Page Types

The framework recognizes six page types. Each page type carries an opinionated default for theme rotation, body family, container width, and motion register.

## §10 Page-type index

| Page Type | Section | Theme Class | Purpose |
|---|---|---|---|
| Primary Landing Page | Hero | `default` | Set the mapped principal light ground. |
| Primary Landing Page | Feature blocks | `default` → `editorial` → `deep` rotation | Use theme as section punctuation. |
| Primary Landing Page | Pricing or comparison | `clarity` | Push toward higher clarity on dense content. |
| Primary Landing Page | Footer | `deep` | Close on the mapped deepest dark theme. |
| Editorial Detail Page | Header (title block) | `default` | Single-theme surface; no rotation. |
| Editorial Detail Page | Hero illustration tile | Feature-tile ground role (`--tile-ground-1/2/3`, theme-bound, `from_palette: panels`) | Reserve one tile per article; pick a tile number, never a color. |
| Editorial Detail Page | Body | `default` | Editorial Serif body type on the mapped light ground. |
| Editorial Detail Page | Footer | `deep` | Force the deep ground for the footer wrapper. |
| Resource Index Page | Hero | `default` | Set the mapped principal light ground. |
| Resource Index Page | Card grid | `default` with saturated illustration tiles inside each card | The card body is on the principal light ground; the illustration block is saturated. |
| Resource Index Page | Footer | `deep` | Same as editorial. |
| Documentation Page | All sections | `default` | Single-theme surface. |
| Documentation Page | Footer | `deep` | Same as editorial. |
| Conversion or Authentication Page | Surround | `default` | The mapped principal light ground behind the card. |
| Conversion or Authentication Page | Card | `clarity` (or transparent within `default`) | Card sits on the page ground without a wrapper recolor. |
| Conversion or Authentication Page | Footer | Local `data-mode="dark"` wrapper with `--surface-primary: var(--color-backgrounds-absolute-black)` | Absolute-black ground via the `backgrounds` semantic palette; the only place this token is used. |
| Application Shell Page | All panes | `default` | Single-theme surface across the app. |
| Application Shell Page | Code panels | Local `code` wrapper | Always-dark code surface. |

Within a page type, theme rotation is the principal visual rhythm. Marketing pages favor mid-section dark interjections to break up long light scrolls. Editorial pages stay on a single theme and let typography and the centered reading column carry the rhythm.

---

## §20 — Primary Landing Page

### Purpose

The longest page type in the system. Composes through multiple sections to introduce the product, demonstrate it, and close on a conversion moment. This document does not prescribe what sections appear or in what order — that is a content decision. What follows are the style constraints that apply once the content team has chosen the sections.

### Composition

#### The Variety Principle (the central rule)

**Do not let two adjacent sections look alike**

This is the page's identity. Across the page, vary the following dimensions section-to-section:

| Dimension                       | Values to draw from                                         |
| ------------------------------- | ----------------------------------------------------------- |
| Theme state                     | any of the 8 themes (§4)                                    |
| Surface treatment               | solid, or any of the 8 named textures (§22b)  Mix these up. |
| Container vocabulary            | none, or any of §23–§39                                     |
| Width                           | `u-container`, `u-container-small`, or `u-container-full`   |
| Headline measure                | any `ch` token (§15)                                        |
| Body measure                    | any `ch` token (§15), independent of the headline           |
| Type role                       | any of the 17 styles (§7)                                   |
| Alignment                       | any move from §41                                           |
| Density                         | sparse → packed                                             |
| Structural pattern              | any pattern from §44                                        |
| Section padding                 | `none`, `small`, `main`, `large`, or `page-top` (§13)       |
| Radius (where containers round) | `none`, `small`, `main`, `large`, or `xlarge` (§17)         |

**Combine freely.** Treat every section as a fresh composition decision. Do not pick one combination and repeat it across sections.

Unless the shape of the section is intentionally centered, mix up alignment.  For example: If a shape had 2 columns, and one column  was text and the other was an image, then swaw this is on the left and which is on the right to add varienty between sections,

## Alternation of background colors on landing pages

1. First section: surface-secondary 

2. Second section: surface-primary

3. Alter back and forth either each new section

4. Exception: Final CTA (T16) is always surface-secondary

### Section sequence

Not all landing pages will have these sections, and not not all sections will be in this list, and while there is no fixed sequence, this is the typical order of the sections when these sections are present:

| #    | Section type             | Purpose                                                      |
| ---- | ------------------------ | ------------------------------------------------------------ |
| T1   | Hero                     | Primary value prop + first CTA                               |
| T2   | Trust Strip              | Validation via customer/brand logos (no quotes)              |
| T3   | Validation Block         | Validation via customer quotes (with or without logos)       |
| T4   | Capability Showcase      | What the product can do (features, surfaces, tools)          |
| T5   | Workflow / Process       | How the product is used, step by step                        |
| T6   | Use-Case Routing         | Which audience/role/job this is for                          |
| T7   | Path Fork                | Binary fork in the funnel (self-serve vs assisted)           |
| T8   | Interactive Demo         | Let the visitor see/try the product output                   |
| T9   | Pricing                  | Investment tiers or usage rates                              |
| T10  | Trust Detail             | Security, governance, deployment, controls                   |
| T11  | FAQ                      | Anticipated operational/technical questions                  |
| T12  | News / Updates           | Recent releases, changelog, announcements                    |
| T13  | Resource Directory       | Docs, blog posts, guides — content surface to deepen engagement |
| T14  | Cross-Promo              | Surface another product or feature inline                    |
| T15  | Sub-Hero                 | Mid-page restatement of value prop + secondary CTA           |
| T16  | Final CTA                | Closing conversion attempt                                   |
| T17  | Footer                   | Global navigation, legal, copyright                          |
| T18  | Section Header / Eyebrow | Standalone label preceding another content unit              |

### Layout Rules

- Container: 1440px max, side gutter 32–64px clamp.
- Section padding: `--section-pad-main` (96–128px) default, `--section-pad-large` (128–200px) for the hero, `--section-pad-page-top` (192–240px) above the fold only.
- 12-column grid above 700px.

### Navigation Behavior

- Fixed topbar with a five-trigger dropdown nav and a brand CTA on the right.
- No hide-on-scroll. The topbar stays anchored.

### Typography Rules

- Hero h1: Display-1 (Editorial Serif at 42–72px clamp, weight 500, `text-wrap: balance`, `max-width: 20ch`).
- Section h2: Marketing H2 (Editorial Serif at 30–44px).
- Body: Primary Sans Body 1 (19–20px) on light grounds, Body 2 (17px) inside cards.
- Card titles: Editorial Serif H3 (28–36px).

### Component Rules

- Pill-tab strips for in-section navigation.
- Feature cards with left or top hairline anchors.
- Full promo cards with 1px outer border and transparent inner fill.
- Brand-button (mapped accent-interactive) for the principal conversion CTA.
- Primary button (mapped near-black fill) for secondary conversion CTAs.

### Motion Rules

- Hero word-by-word reveal driven by `--reveal-*` properties.
- Card-grid stagger on viewport entry.
- IntersectionObserver-driven fades.
- 600ms dropdown opens.
- Scroll-driven panel that grows from inset to full-bleed in one mid-page section.

### Responsive Rules

- Drop to drawer-style navigation below the tablet breakpoint.
- Stack feature cards vertically below the tablet breakpoint.
- Reduce section padding to 56px on mobile.

### Theme / mode notes

- Hero uses `default`.
- Feature blocks rotate `default` → `editorial` → `deep`.
- Pricing or comparison uses `clarity`.
- Footer uses `deep`.

### Do Not

- Do not put photography in feature cards.
- Do not end the hero h1 with a period.
- Do not use a fixed-width box for the hero — let it inherit the full container.

---

## §20 — Editorial Detail Page

### Purpose

Long-form article reading. Optimize for legibility, scannability, and a quiet, confident tone. The page is structurally the simplest after authentication.

### Required Structure

1. Topbar with `hideOnScroll` enabled.
2. Centered three-line article header: subjects (eyebrow), title, date.
3. Tinted illustration tile (saturated panel ground).
4. Body content inside a 640px centered reading column.
5. Social-share row above a 1px top rule.
6. Related-content rail (3 items).
7. Footer using local `deep`.

### Section Order

Single-theme surface. Do not rotate themes inside the article body. The illustration tile is the only saturated panel.

### Theme Usage

`editorial` for the entire page. Local `deep` wrapper on the footer.

### Layout Rules

- Outer container: 1400px max.
- Reading column: **640px**, centered within the outer container.
- Side gutter: 32 / 48 / 64px responsive.
- Section padding (header to tile to body): 48px each.

### Navigation Behavior

- Sticky topbar with hide-on-scroll: hides on downward scroll past the header height; returns on upward scroll. 300ms transform transition.

### Typography Rules

- Title: Editorial Headline 1 (Primary Sans 32–52px responsive, weight 700, line-height 110%, `text-wrap: balance`, `text-align: center`).
- Subjects (eyebrow): Body 3 bold (Primary Sans 15px, weight 500–700, sentence case).
- Date: Body 3 agate (Primary Sans 15px, weight 400, line-height 140%, color `--text-tertiary`).
- Body paragraph: Body 2 with `.serif` modifier (Editorial Serif 17px, weight 500, line-height 155%, margin-block 16px).
- Section h2: Headline 5 (Primary Sans 20–25px, weight 600, line-height 120%, `text-wrap: pretty`, margin `1.5rem/2rem 0 0.5rem 0`).
- Inline link: same ink as body; underline at 0.08em thickness, 0.18em offset.
- Blockquote: text at `--text-secondary`; 1px left rule at `--border-strong`; padding `4px 0 4px 16px`.

### Component Rules

- Article hero.
- Related-content rail.
- Social-share row.
- Featured illustration tile.

### Motion Rules

- `.contentFade` and `.contentFadeUp` scroll-into-view fades.
- 150ms inline link color cross-fade.
- 200ms hover opacity dim on featured cards.
- Topbar hide-on-scroll over 300ms.
- No parallax. No image zoom. No scroll-progress bar.

### Responsive Rules

- Reading column drops to full container width below 700px.
- Title scale drops from 52px to 32px.
- Illustration tile inner padding scales 96px → 48px.

### Theme / mode notes

- `editorial` across the entire page.
- Local `deep` wrapper on the footer.
- The illustration tile is the only saturated panel surface.

### Do Not

- Do not place a back-link or breadcrumb above the article. Readers return via the topbar.
- Do not introduce a scroll-progress bar.

---

## §20 — Resource Index Page

### Purpose

Index of editorial or feature entries with a featured-lead pattern and a publication list below.

### Required Structure

1. Topbar.
2. Single-word or short-phrase page H1 (Headline 1 scale).
3. Featured grid: one lead card (col 1–9) plus a side stack (col 10–13).
4. Publication list: row-per-entry with date, category, title columns. Below tablet breakpoint, collapse to stacked cards.
5. Search filter input above the publication list.
6. Footer using local `deep`.

### Section Order

Hero → Featured grid → Publication list → Footer.

### Theme Usage

`editorial` for the entire page. Illustration tiles inside featured cards use saturated panel grounds.

### Layout Rules

- Container 1400px.
- Featured grid: lead 1–9, side stack 10–13.
- Publication list: 12-column with content 1–10, optional sticky sidebar 11–13.
- Search filter input above the list at full content width.

### Navigation Behavior

- Sticky topbar without hide-on-scroll.

### Typography Rules

- Page H1: Headline 1 (Primary Sans 32–52px, weight 700).
- Featured card title: Headline 4 (Primary Sans 23–32px, weight 600). Underline at 0.2em offset on hover.
- Featured card dek: Body 3 with `.serif` modifier.
- Date and category meta: Body 3 agate at `--text-tertiary`.
- Publication-list column headers: Caption with `text-transform: uppercase` and `letter-spacing: 0.15px`.

### Component Rules

- Editorial featured cards.
- Search input.
- Pagination indicator (no numbered pages).

### Motion Rules

- Scroll-into-view fades on cards.
- 200ms hover opacity dim on whole cards.

### Responsive Rules

- Collapse the featured grid to a single column below tablet.
- Collapse the publication list to stacked cards below 700px.
- Hide the sticky sidebar below 700px.

### Theme / mode notes

- `editorial` across the page; illustration tiles inside featured cards use saturated panel grounds.
- Footer uses local `deep`.

### Do Not

- Do not use numbered page buttons.
- Do not put photography on the featured card lead.

---

## §20 — Documentation Page

### Purpose

Long-form reference content. Optimize for legibility and stability. Closest in style to editorial but with optional side navigation.

### Required Structure

1. Topbar.
2. Page H1 (Display 2 scale).
3. Body content inside a 640px reading column, centered or left-aligned with a sticky sidebar to the right.
4. Footer using local `deep`.

### Section Order

Title → Body → Footer.

### Theme Usage

`editorial` only. No theme rotation.

### Layout Rules

- Outer offset: 316px on each side at the widest viewport.
- Reading column: 640px.
- Smooth-scroll on the root: `html { scroll-behavior: smooth; }`.

### Navigation Behavior

- Sticky topbar.
- Optional in-page anchor links honoring `scroll-behavior: smooth`.

### Typography Rules

- Title: Display 2 (Primary Sans 64px desktop, weight 700, line-height 100%).
- Section h2: Headline 5 (Primary Sans 25px, weight 600, line-height 30px, margin `32px 0 8px`).
- Body paragraph: Body 2 with `.serif` modifier (Editorial Serif 17px, weight 400, line-height 155%, margin 16px 0).
- Ordered list: Editorial Serif 17px / 400 / 23.8px, decimal markers at every level (no alphabetic nesting).
- Inline `<strong>`: same family as surrounding text, weight 600.
- Defined terms: `<strong>` with bare quote marks in running text.
- Effective-date stamp and "Previous Version" link: Text Label class (Primary Sans 16px, weight 600, letter-spacing -0.08px).

### Component Rules

- Hand-numbered h2 headings (e.g., "1. Section name.", "11. Next section.").
- Single hard 1px rule at `--border-strong` between the metadata row and the body. No other line work on the page.
- Language picker (single-option dropdown by default).
- No cards. No badges. No shadows.

### Motion Rules

- Only footer link colors transition (200ms).
- Topbar has no transition.

### Responsive Rules

- Reading column scales to full content width below 700px.
- Outer offset reduces to standard page gutter below the desktop breakpoint.

### Theme / mode notes

- `editorial` only across all sections; footer uses local `deep`.
- Long-form pages use zero radius — structure relies on whitespace and hairlines.

### Do Not

- Do not use `text-transform: uppercase` on all-caps disclaimers. Set the source text as upper-case.
- Do not introduce shadows or boxes.
- Do not use state colors anywhere in the body.

---

## §20 — Conversion or Authentication Page

### Purpose

Single-action conversion surface. Show one prominent input, two-to-three secondary actions, and minimal surrounding chrome.

### Required Structure

1. Topbar with a single secondary link and one primary CTA.
2. Marketing headline outside the card (two-line, Editorial Serif at ultralight weight 330).
3. Centered card on the mapped principal light ground.
4. Inside the card: input field, primary CTA, OR-divider, 2–3 secondary CTAs, legal blurb.
5. Footer using a local `data-mode="dark"` wrapper that resolves `--surface-primary` to the mapped absolute-black neutral.

### Section Order

Top nav → Marketing headline → Card → Footer.

### Theme Usage

`default` for the surround. The card uses transparent surface against the page ground. Footer uses local `data-mode="dark"` with `--surface-primary: var(--color-backgrounds-absolute-black)`.

### Layout Rules

- Card: 448px max-width, centered, inner padding 28px.
- Card radius: 32px (the top of the radius scale).
- Card border: 0.5px-feeling (1px solid `rgba(<ink>, 0.15)`).
- Card shadow: 4-layer low-opacity stack from the shadow scale.

### Navigation Behavior

- Fixed topbar at 84px height (`5.25rem`).
- Topbar background matches the page ground exactly. No border. No shadow.

### Typography Rules

- Marketing headline: Editorial Serif 56px, weight 330, line-height 1.2.
- Input label: hidden via CSS; the placeholder serves as the visible label.
- Required asterisk: separate `<span aria-hidden="true">` at `--field-required` with 4px left margin.
- Button label: Primary Sans 16px, weight 500.
- OR-divider: Primary Sans 12px, weight 400, uppercase via CSS, color `--text-secondary`. Typography only — no rules, no decorative line work.
- Legal blurb: Primary Sans 14px, weight 400. Underlined inline link at 40% opacity at rest; 100% on hover.

### Component Rules

- Single primary input (44px height, 9.6px radius, 12px horizontal padding).
- Primary CTA with bloom hover.
- 2–3 secondary CTAs with 0.5px-feeling border and transparent fill.
- Provider-specific 16×16 logo on relevant secondary CTAs with 8px gap to label.
- The single SSO-style secondary action takes `tabindex="-1"` to skip the keyboard tab order.

### Motion Rules

- Hover transforms: scale 1.005 × 1.015 on the primary CTA.
- 200ms `::after` radial-gradient highlight bloom on hover.
- 100ms color and border on secondary buttons.
- No nav animation.

### Responsive Rules

- Card width holds at 448px on every breakpoint.
- Marketing headline scales from 56px desktop down to 36px mobile.
- Topbar collapses to a compact row.

### Theme / mode notes

- `default` surround; card transparent against the page ground.
- Footer is the only place in the system that uses the mapped absolute-black neutral via a local `data-mode="dark"` wrapper.

### Do Not

- Do not put avatar or hero illustration on the card.
- Do not introduce a "Welcome back" or "Sign in to continue" greeting.
- Do not use a green or yellow state color on the card.
- Do not add a border to the topbar.

---

## §20 — Application Shell Page

### Purpose

Authenticated application surface. Persistent left rail, list column, and detail viewport. Calm motion, dense content, clear active states.

### Required Structure

1. Left icon rail (64px).
2. List column (280–320px).
3. Detail viewport (fluid).
4. Optional inline modal for create / edit dialogs.

### Section Order

Three columns persist across routes. The detail viewport is the only column that swaps.

### Theme Usage

`default` for all panes. Local `code` wrapper for code panels.

### Layout Rules

- Icon rail: 64px wide; mapped light ground; icons at 16px; 24px gap vertically.
- List column: 280–320px; same mapped light ground; subtle whitespace separation from the icon rail.
- Detail viewport: fluid; inner cards at 960–1100px max width with 24–32px padding.
- Card radius: 12px on stat cards, 16px on hero and empty-state cards.

### Navigation Behavior

- No topbar. The workspace switcher sits at the top of the list column.
- Active list-row: filled pill behind the label using `--surface-tertiary`.
- Sub-items indent under section headers; no icon for sub-items.

### Typography Rules

- Page title: Headline 5 (Primary Sans 25px, weight 600).
- Section header in left rail: Body 3 (15px), weight 500, ink at `--text-tertiary`.
- Item row label: Body 3, weight 400.
- Stat caption: Body 3.
- Stat display number: 32–40px Primary Sans, weight 600–700, prefixed by `$` for currency.
- Form-field label: Body 3 sans above the field.

### Component Rules

- Stat cards.
- Empty-state cards.
- Hero promo cards for in-app announcements.
- Toggle switches with the chromatic active fill (`--switch-active-bg`).
- Destructive buttons with `--error-fill` background and light text.
- Modal dialogs centered on dimmed-light backdrop (no blur).

### Motion Rules

- 200ms toggle slide.
- Dropdown chevron rotation.
- Cross-fade on tab and route changes.
- No hero reveal animations.

### Responsive Rules

- Below tablet, collapse the list column into a slide-over.
- Detail viewport takes full width.
- Icon rail collapses into a hamburger trigger.

### Theme / mode notes

- `default` across all panes.
- Local `code` wrapper for code panels — these stay dark in light mode and continue dark in dark mode.

### Do Not

- Do not introduce a topbar at the top of the detail viewport.
- Do not use the brand-button (mapped accent-interactive) for primary actions in the shell — reserve it for marketing surfaces.
- Do not paint code panels in light mode.

---

## Known gaps

- None. The page-type index and every per-page-type entry (Primary Landing, Editorial Detail, Resource Index, Documentation, Conversion or Authentication, Application Shell) are complete: section sequence, per-page rules, theme/mode notes, and explicit Do-Not lists are specified for each.
