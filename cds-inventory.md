# CDS Plugin Inventory

A catalog of the `plugins/cds` design system: components, composition patterns
(shapes / shell layouts / page shapes), and page types.

> **Terminology note (read first).** This plugin has exactly three *closed
> catalogs of composition patterns* — section shapes (`S0–S28`), shell layouts
> (`A1–A5`), and intra-shell page shapes — plus one closed catalog of **page
> types** and one open library of **components**. It does **not** have a catalog
> called "surfaces." In the plugin's own `reference/vocabulary.md`, *"Surface"*
> is an **umbrella noun** ("an umbrella over component, page, and section") and a
> word for a **composed/rendered artifact** ("production surfaces", "app
> surfaces"). A surface is the *thing you build*; a shape is the *reusable
> pattern you build it from*. There is no enumerable list of surfaces because a
> surface is an instance, not a taxonomy. See the closing section for the full
> shape-vs-surface explanation.

---

## Components

Source: `reference/components.md`. Chrome components (§12) + the component
catalog (§14). A component is a single reusable visual/operational element; it
is named by its shape and behavior, never by the content poured into it.

### Navigation & chrome (§12)
| Name | Description |
|---|---|
| Topbar | Fixed desktop top bar anchoring global nav + conversion CTAs, no visible boundary. |
| Dropdown panels | Hover/click panels (flat / mega / lift-and-scale) under a topbar trigger. |
| Mobile drawer | Full-viewport navigation takeover the topbar collapses into at mobile widths. |
| Sticky header | Header that hides on downward scroll, reappears on upward scroll (editorial only). |
| App shell left rail | Three-pane navigation chrome (rail → list → detail) for app-shell pages. |
| Workspace switcher | Rail-top workspace switcher; compact (icon) and full (named) variants. |
| Account row | Rail-bottom identity row + account menu; full / compact / footer-strip variants. |
| Skip links | Off-screen keyboard jump targets that snap into view on focus. |
| Footer | Multi-column site footer: secondary nav, legal, social. |

### Buttons (§14 / §14.1–14.2)
| Name | Description |
|---|---|
| Primary button | Dominant conversion/commit action; inverts ground with page mode. |
| Secondary button | Supporting peer action on the same surface. |
| Tertiary button | Quietest, link-like control with a hairline border. |
| Brand button | Paints the brand accent regardless of mode (does not invert). |
| Destructive button | Red-fill variant for delete/revoke/irreversible actions. |
| Authentication primary CTA | Conversion CTA with a richer "bloom" radial-gradient hover. |

### Cards (§14)
| Name | Description |
|---|---|
| Feature card | Marginalia-style card with a hairline anchor on the left/top edge. |
| Full promo card | Bordered, transparent-fill card for product/feature callouts. |
| Link card | Card linking to another page/asset, emphasizing the title. |
| Pricing card | Tier card with title + feature list + CTA; default/featured variants. |
| Catalog card | Grid-item card with a label badge plus title/body/meta. |
| Editorial featured card | Tinted illustration tile + title/dek/date; lead vs. side variants. |
| Application stat card | In-app KPI card: caption + display number + optional inline action. |
| Hero promo card | Landing hero-adjacent promo with a decorative dark sub-panel inside. |
| Empty-state card | Occupies an absent list/grid: glyph + caption + action. |
| Setting card | One preference: title, explanation, inline toggle or primary action. |
| Editor card | One labelled turn (system/user/assistant) with a rich-text editor body. |

### Inputs & controls (§14 / §14.3)
| Name | Description |
|---|---|
| Standard text input | Single-line input, hairline border, placeholder-as-label. |
| Search input | Text input with a leading magnifier glyph for search contexts. |
| Textarea | Multi-line variant of the standard text input. |
| Search field | In-list filter input (wrapper owns chrome); debounced live filtering. |
| Toggle switch | Boolean on/off control with a sliding thumb. |
| Switch active | Spec reserving the chromatic accent for the toggle's ON state. |
| Pill-tab strip | Segmented control; active option painted as an inset pill. |
| Filter chip | Compact pill picker (label + value + caret) opening a dialog popover. |
| Period picker | Filter-chip-shaped trigger opening a date-range picker dialog. |
| Stepper | Horizontal numbered progress indicator for multi-step flows. |

### Badges (§14)
| Name | Description |
|---|---|
| Outline pill badge | Hairline-border tag for categorical/meta labels. |
| Inverted pill badge | Filled, inverse-ink pill for emphasis labels and counters. |
| Status badge | State-keyed indicator (ok/warning/error/neutral). |

### Overlays & menus (§14)
| Name | Description |
|---|---|
| Centered dialog | Modal card on a dimmed (no-blur) backdrop; full-screen on mobile. |
| Video / lightbox dialog | Modal for video/image; the only dialog applying backdrop blur. |
| Consent / cookie banner | Bottom-right pinned, non-blocking consent card. |
| Kebab menu | 3-dot trigger opening a small floating menu of record actions. |

### Editorial & misc (§14)
| Name | Description |
|---|---|
| Marginalia row | Editorial row: icon + 35ch content stack + optional left-rail TOC. |
| Code block | Monospaced dark-ground block with language picker + Copy/View-Docs. |
| Article hero | Editorial detail hero — three-line header above a tinted tile. |
| Related-content rail | Sibling-article 3-item link grid at the foot of editorial pages. |
| Social-share row | Two-icon share row above a hairline rule. |
| Pagination | Indicator + Prev/Next links (explicitly not numbered pages). |
| Three-pane app shell | In-app icon rail + list column + detail viewport (= shell layout A4). |
| Stat tile | Smaller stat-card variant for status/progress glyphs. |
| Read-only identifier row | Label + monospaced value + copy button for system IDs. |

> `§14.1 Button base` is the shared base spec for all button variants, not a
> standalone component.

---

## Composition patterns

All three of these are "shapes" in the ordinary sense — reusable patterns that
arrange components. They are split into separate catalogs only because they
operate at **different scopes** and obey different composition rules.

### Section shapes — `S0–S28` (scope: one vertically-scrolling landing section)

Source: `reference/shapes.md`. Governed by the landing-page Variety Principle and
adjacency rules.

| Code | Name | Description |
|---|---|---|
| S0 | Standalone heading strip | Just an H2 (+ optional eyebrow) as a section label. |
| S1 | Centered text + visual below | Centered headline/subhead/CTAs; visual below. |
| S2 | Two-column text/visual | Text + CTAs one side, single visual the other. |
| S3 | Centered text + embedded affordance | Centered headline; interactive element where the visual would be. |
| S4 | Static card grid | N cards in M columns, identical structure. |
| S5 | Tagged card grid | S4 plus an eyebrow tag/pill above each card title. |
| S6 | Tabs with one panel per tab | Tab strip + a large panel that swaps. |
| S7 | Alternating image+text rows | Rows alternating image-left/text-right. |
| S8 | Horizontal carousel | Card row with prev/next arrows; overflow. |
| S9 | Marquee strip | Continuously scrolling horizontal row (logos/icons). |
| S10 | Numbered step row | 3-column row with explicit step ordering. |
| S11 | 3-up stacked pull-quotes | Three unframed quote blocks with attribution. |
| S12 | Quote swiper with logos | Rotating quote + synced logo carousel. |
| S13 | Single hero quote | One large near-hero quote, often with a metric. |
| S14 | Accordion list | Vertical stack of collapsible items (e.g. FAQ). |
| S15 | Tier card row + segment toggle | 2–4 tier cards; toggle swaps the tier set. |
| S16 | Rate table | Tabular usage rates (Input/Output/Cache). |
| S17 | Banner strip | Narrow full-width strip: headline + 1–2 CTAs. |
| S18 | Full-width CTA panel | Tall band: headline + subhead + CTAs. |
| S19 | CTA panel + newsletter form | S18 plus inline email-capture form. |
| S20 | Path picker (2-card fork) | Two large parallel exclusive-path cards. |
| S21 | Pictogram + nested sub-cards | Animated pictogram anchor; sub-cards below. |
| S22 | Pill/tag cloud columns | 3–5 vertical columns of category pills. |
| S23 | Lead card + companion carousel | One featured card + secondary carousel beside it. |
| S24 | Resource grid with source tags | Card grid; each card carries a source-type tag. |
| S25 | Two-column prompt/artifact panel | Left: mock prompt; right: mock artifact. |
| S26 | Download/install button strip | Row of platform-specific install buttons. |
| S27 | Footer navigation grid | Multi-column nav grid + legal/copyright row. |
| S28 | Sub-hero with video + CTA pair | Mid-page restatement: video + headline/CTA pair. |

### Shell layouts — `A1–A5` (scope: the whole app viewport)

Source: `skills/compose-app-surface/reference/app-shapes.md`. Partition the
viewport into rails/main/panels for authenticated app screens. Governed by
pane-partitioning rules, not the Variety Principle. **Distinct from section
shapes** (per `vocabulary.md`).

| Code | Name | Description |
|---|---|---|
| A1 | Single side rail + main | Persistent left nav rail; remaining width is one scrollable main pane. |
| A2 | Side rail + main + right info panel | A1 plus a persistent right column of contextual help/info. |
| A3 | Side rail + main + bottom prompt strip | A1 plus a viewport-floor prompt/action strip. |
| A4 | Mini-icon rail + list column + detail viewport | Icon rail + list column + fluid detail (library/registry browsing). |
| A5 | Form-driven sidebar + canvas/gallery | Left sidebar drives config; right pane is a live canvas or template gallery. |

### Page shapes (scope: the `main` pane inside a shell)

Source: `skills/compose-app-surface/reference/app-shapes.md`. Reusable across
shells wherever the structure fits (e.g. a "Settings form" can fill A1's main
pane or A4's detail viewport). Named descriptively, not letter-coded.

| Name | Description |
|---|---|
| Greeting + KPI card row + content stack | Greeting heading + 3 KPI cards + activity/empty card (dashboard home). |
| Filter strip + KPI grid + chart with empty state | Filter chips + KPI tiles + time-series chart panel. |
| Multi-step breadcrumb + central empty state + template grid + bottom prompt | Stepper at top; two-column "start blank vs. start from template" body. |
| Hero promo card + KPI pair + chart pair | Promo card + 1×2 KPI tiles + 1×2 chart cards + info note. |
| Empty list state — centered icon + helper + CTA | Heading + table-header strip + centered empty plate with CTA. |
| Settings form — two-column field groups + destructive zone | Metadata row + 2-col field groups + bottom destructive action. |
| Stacked setting cards with toggles + destructive zone | Vertical stack of setting cards; destructive actions live in their cards. |
| Code block as primary content + actions | Heading + subhead + a full-width code block as the page's primary content. |
| Modal over list — form with grouped checkboxes | List page overlaid with a centered modal carrying a grouped-checkbox form. |
| Command palette overlay over a list page | Centered floating search palette over a dimmed list page (⌘K launcher). |
| Editor card stack — composition surface | Vertical stack of editor cards + an action row (prompt/message builders). |
| Tool-permission detail — read/write groups with per-row controls | Connector permission editor with collapsible read/write groups. |
| Skill detail — metadata strip + body | Single record: title + dt/dd metadata strip + description + content body. |
| Template gallery — example cards with control panels | Gallery of example/template cards with per-template descriptor panels. |
| Project picker / new-prototype gallery | Gallery of existing projects + a new-object entry path. |

> The same file also documents **cross-context component compositions** (Modal
> dialog with form, Grouped checkbox tree, Two-/four-column field-group form,
> Destructive zone, Setting card with toggle + destructive sub-row, Approval-mode
> tool-permission control). These are reusable sub-compositions, not page shapes.

---

## Page types

Source: `reference/page-types.md`. Six recognized page types, each with
opinionated defaults for theme rotation, body family, container width, and
motion register.

| Name | Description |
|---|---|
| Primary Landing Page | Longest page type; many sections to introduce, demonstrate, convert. Variety Principle applies. |
| Editorial Detail Page | Long-form article reading; 640px centered reading column, single `editorial` theme. |
| Resource Index Page | Index of entries — featured lead card + publication list with search filter. |
| Documentation Page | Long-form reference; legibility-first, optional sticky sidebar, no cards/badges/shadows. |
| Conversion or Authentication Page | Single-action surface — one input, 2–3 secondary actions, minimal chrome. |
| Application Shell Page | Authenticated app — persistent rail, list column, fluid detail viewport. |

---

## Adjacent catalogs (referenced, not enumerated here)

- **Section types `T1–T18`** (`reference/section-types.md`) — the *purpose* of a
  landing section (Hero, Trust Strip, Pricing, FAQ, Final CTA, …). A section type
  is realized *by* a section shape; the two are orthogonal.

---

## Why there is no "surfaces" catalog

A **shape** is a reusable composition *pattern* — a closed, enumerable catalog
(`S0–S28`, `A1–A5`, the named page shapes). A **surface** is a *rendered
artifact*: the actual screen, page, or section you compose by applying shapes,
components, and a theme. `vocabulary.md` defines "surface" as an umbrella noun
over component/page/section, and uses it elsewhere to mean the composed output
("production surfaces", "app surfaces").

Because a surface is an instance and a shape is a template, "list all surfaces"
has no fixed answer — you'd be listing every screen anyone could ever build. The
enumerable catalogs are shapes, shell layouts, page shapes, page types, and
components. "Surface" stays a noun, not a taxonomy.
