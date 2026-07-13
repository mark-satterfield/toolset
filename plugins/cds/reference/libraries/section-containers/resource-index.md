---
kind: section-container
name: resource-index
family: editorial
aliases: [resource index page, blog index, news index, listing page, archive page]
status: stable
default_shell: marketing
sections:
  - { section: index-header, required: true, notes: "always first" }
  - { section: featured-grid, required: true }
  - { section: publication-list, required: true, notes: "always last" }
constraints: []
register:
  type_scale: editorial
  motion_register: editorial
---

# Resource Index Page

An index of editorial or feature entries: a featured-lead pattern with a publication list below. The Shell supplies topbar and footer; this container is content Sections only, in the fixed order above: index header → featured grid → publication list.

## Theme

`editorial` for the entire page. Illustration tiles inside featured cards use saturated panel grounds. The footer's `deep` island belongs to the Shell.

## Register rules

### Layout

- Outer container: `--container-editorial` (calibrates to 1400px).
- Featured grid: lead on grid lines 1–9, side stack on lines 10–13.
- Publication list: 12-column with content on lines 1–10, optional sticky sidebar on lines 11–13.
- The filter input sits above the list at full content width.

### Navigation

- Sticky topbar without hide-on-scroll.

### Typography (editorial scale, `foundations/typography.md` §13.5)

- Page h1: Headline 1.
- Featured card title: Headline 4, underline at 0.2em offset on hover.
- Featured card dek: Body 3 with the `.serif` modifier.
- Date and category meta: Body 3 agate at `--text-tertiary`.
- Publication-list column headers: Caption (the role carries its own letter-spacing), uppercase via CSS.

### Components

- Editorial featured cards, search-input (as inline list filter), pagination indicator (no numbered pages).

### Motion (editorial register, `foundations/motion.md` §15.3)

- Scroll-into-view fades on cards.
- 200ms hover opacity dim on whole cards.

### Responsive

- Featured grid collapses to a single column below the tablet breakpoint.
- Publication list collapses to stacked cards below 700px.
- The sticky sidebar hides below 700px.

### Do not

- No numbered page buttons.
- No photography on the featured lead card.
