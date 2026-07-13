# Library Entry Format

Every Building Block is one `.md` file: typed YAML frontmatter + a body. The same format applies in the plugin's `reference/libraries/` and `reference/rules/` trees and in a project's extensions dir (`$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` mirrors both trees; a matching `kind` + basename overrides the plugin entry wholesale).

Terminology is the Building Blocks vocabulary: Element (concept only — never configured), Component (a component library entry is a Component Definition; a Component on a page is an instance of it), Shape, Section, Section Container (user-facing alias: page type), Shell, plus the two rule kinds: Shape Selection Rules (`shape-selection-rule`) and Page-Level Aesthetic Constraints (`page-constraint`). `reference/aliases.md` maps user-facing words onto these; entry bodies use the internal vocabulary only.

## Common frontmatter (every kind)

```yaml
kind: component | shape | section | section-container | shell | shape-selection-rule | page-constraint
name: kebab-case-name          # basename of the file (e.g. hero.md → hero); the entry is cited by this name everywhere
family: landing | editorial | docs | auth | app | shared
aliases: []                    # user-facing names this entry answers to
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
shell_component: false            # true for Components that realize a Shell's persistent Sections: topbar, footer, rail, drawer, skip-links, switcher, account-row
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

### section

```yaml
mode: deterministic | dynamic  # deterministic: layout fixed here; dynamic: Shape assigned at build by the rule engine
content_contract: {}           # the typed signals this section's rule consumes (the completed content_meta fields relevant to it)
theme: default                 # theme class or `scheduled` (takes the constraint-assigned ground)
composition_notes: []          # cross-section notes (e.g. cross-promo may embed inside trust-detail)
```

### section-container

```yaml
sections: []                   # ordered: {section, required, notes} — each names a Section by name
constraints: []                # page-constraint refs applying to this container
register: {}                   # foundations bindings: type scale, motion register
default_shell: marketing      # shell name resolved when the user asks for "the page"
```

### shell

A Shell entry may describe a Shell Template — persistent Sections pinned around a placeholder `content_slot` for a Section Container — or an instantiated Shell persisted for reuse; the composer instantiates a Template into a Shell.

```yaml
sections: []                   # each persistent Section of the Shell, realized by a named Component (topbar, footer, rail, …), with placement
panes: []                      # named regions for app shells: {name, width: token-or-formula, collapse}
content_slot: {}               # what the shell accepts: {kinds: [section-container], families: []}
```

Every Shell is named by its layout (marketing, editorial, docs, auth, rail-main, …). A novel viewport partitioning always takes a new name — never a variant of an existing one.

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
applies_to: {families: [], containers: []}   # scoping; family default overridable per container
check: |                       # the validator statement, written as a decidable rule over the accumulating page
```

Constraints run as a post-selection rejection loop: candidate shape → validate → reject → next candidate → exhausted → fallback generation (recorded in the decisions sidecar).

## Body

Free markdown after the frontmatter: the layout description, ASCII sketch where useful, HTML skeleton for self-contained shapes, Determinations (definitive behaviors and measurements — expressed as token references or derivation formulas, never restated pixel values).

## Dimension rule

A dimension in any entry is one of: (a) a token reference (`var(--sp-2)`, `--container-marketing-primary`); (b) a derivation formula over tokens or parent dimensions (`50% of content_slot minus var(--sp-1) gap`); (c) an intrinsic literal ONLY when the value is a genuine standalone design choice and no token expresses it — in which case it belongs in the YAML geometry scale, not the entry. Frozen consequences of parent dimensions are format violations.

## Prose rule

Descriptions state what a thing IS. No history, no consumer enumeration, no known-gaps commentary, no deferred work. `check_reference_prose.py` enforces this over both library trees.
