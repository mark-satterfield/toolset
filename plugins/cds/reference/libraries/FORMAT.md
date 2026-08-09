# Library Entry Format

Every Building Block is one `.md` file: typed YAML frontmatter + a body. The same format applies in the plugin's `reference/libraries/` and `reference/rules/` trees and in a project's extensions dir (`$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` mirrors both trees; a matching `kind` + basename overrides the plugin entry wholesale).

Terminology is the Building Blocks vocabulary defined in `reference/model/entity-catalog.md`: Element (concept only — never configured), Component (a component library entry is a Component Definition; a Component on a page is an instance of it), Shape, Frame, Section, Page, ShellDefinition (its stored output is a Shell), plus the two rule kinds: Shape Selection Rules (`shape-selection-rule`) and Page-Level Aesthetic Constraints (`page-constraint`). Entry bodies use this vocabulary only.

## Common frontmatter (every kind)

```yaml
kind: component | shape | section | page | shape-selection-rule | page-constraint
name: kebab-case-name          # basename of the file (e.g. hero.md → hero); the entry is cited by this name everywhere
page_family: landing | editorial | docs | auth | app | shared
                               # the page family this entry serves; shared = all families.
                               # The page family selects the typography and motion register and scopes
                               # which Page-Level Aesthetic Constraints apply (see entity-catalog.md).
aliases: []                    # searchable synonyms this entry answers to (never a routing decision)
status: stable | draft
```

## Per-kind frontmatter

### component

```yaml
slots: []                      # named content positions: {name, required, accepts}
sizing: {}                     # dimension contract: token refs and derivation formulas only — no bare px
behavior: []                   # interaction contracts: events, states, keyboard
accessibility: []              # ARIA pattern, focus, contrast obligations
token_bindings: []             # role tokens the component consumes (semantic vocabulary only)
shell_component: false         # true for Components that typically realize a Shell's Sections
                               # (topbar, footer, rail, drawer, skip-links, switcher, account-row);
                               # consulted by compose-shell when the user composes a Shell
composite: false               # true for multi-component compositions (modal-with-form, field-group, destructive-zone)
content_defaults: {}           # declared example content (e.g. the footer's default column IA); supplied content overrides
```

### shape

```yaml
slots: []                      # {name, required, accepts}
variants: []                   # named variants
self_contained: false          # true ⇒ the fragment carries its own scoped <style> + IIFE <script> implementing the ARIA contract (load-bearing; a fragment deferring behavior to "the stylesheet" is broken)
content_defaults: {}           # declared example content for drafted-mode scaffolds (e.g. rate-table default columns); supplied content overrides — the layout contract itself is content-free
```

A Shape is a layout template — it positions Components and Elements and carries their proportional and other geospatial properties. It is not a DesignElement and has no dimensions of its own; when a Shape is applied to a Frame, the Components become realized.

### section

```yaml
shape: shape-name              # eager Shape assignment: the Shape, by name, from the ShapeLibrary.
                               # Omit for lazy assignment: the Shape is resolved at build time by the
                               # Rule Engine from the Section's content via its shape-selection-rule.
content_contract: {}           # the typed signals this section's rule consumes (the completed content_meta fields relevant to it)
theme: default                 # theme class or `scheduled` (takes the constraint-assigned ground)
composition_notes: []          # cross-section notes (e.g. cross-promo may embed inside trust-detail)
```

A Section never contains its own layout — layout always lives in a Shape in the ShapeLibrary so it stays shareable across Pages. A Section either names its Shape (eager) or carries the content signals its rule needs (lazy).

#### Universal Section slots

Two optional slots are available on **every** Section, whatever Shape it receives, without being declared in any entry:

```yaml
eyebrow: <text>                # a short label line above the Section's heading
media:   {src, alt, kind}      # one image, illustration, or embed belonging to the whole Section
```

Both are supplied-or-absent — present when the brief carries one, rendered as nothing when it does not — and neither alters the receiving Shape's layout contract. Default placement: the eyebrow directly above the Section's heading at the caption type role; the media after the heading stack and before the Shape's own content. A Shape that places either slot differently states that placement in its own Determinations (`libraries/shapes/CONVENTIONS.md`, Universal Section slots).

A Section entry lists these only to constrain them — to mark one required, or to name a non-default placement. An entry that says nothing about them accepts both at their defaults.

### page

```yaml
sections: []                   # ordered: {section, required, notes} — each names a Section by name
constraints: []                # page-constraint refs applying to this Page
```

A Page is one or more Sections in sequence; it nests inside the vacant space of a Shell. A Page entry never names a Shell — Shells are composed by the user (`compose-shell`) and paired with a Page at view time (`compose-view`).

### shape-selection-rule

```yaml
section: hero                  # the Section this rule serves, by name (one file per section)
signals: []                    # content_contract fields consulted
table: []                      # ordered rows: {when: predicate over signals+page_meta, primary: shape, alternates: [shapes]}
default: shape-name            # fallback candidate before agent generation
```

`page_meta` is shared: `buying_mode: commit|browse`, `position_in_page: top|mid|late`.

### page-constraint

```yaml
applies_to: {page_families: [], pages: []}   # scoping; a page-family default overridable per Page
check: |                       # the validator statement, written as a decidable rule over the accumulating page
```

Constraints run as a post-selection rejection loop: candidate shape → validate → reject → next candidate → exhausted → fallback generation (recorded in the decisions sidecar).

## Body

Free markdown after the frontmatter: the layout description, ASCII sketch where useful, HTML skeleton for self-contained shapes, Determinations (definitive behaviors and measurements — expressed as token references or derivation formulas, never restated pixel values).

## Dimension rule

A dimension in any entry is one of: (a) a token reference (`var(--sp-2)`, `--container-marketing-primary`); (b) a derivation formula over tokens or parent dimensions (`50% of the vacant space minus var(--sp-1) gap`); (c) an intrinsic literal ONLY when the value is a genuine standalone design choice and no token expresses it — in which case it belongs in the YAML geometry scale, not the entry. Frozen consequences of parent dimensions are format violations.

## Prose rule

Descriptions state what a thing IS. No history, no consumer enumeration, no known-gaps commentary, no deferred work. `check_reference_prose.py` enforces this over both library trees.
