# cds — visual proof suite

A standalone, offline visual proof / smoke-test gallery for the **cds** plugin design system.
Open `index.html` in any browser to browse it.

## What it proves

The cds plugin emits page sections, app surfaces, and components driven by a project's design
tokens. This suite renders every shape the plugin can produce against a fixed fixture so you can
see, at a glance, that:

- Every **landing section shape** (29 of them), every **app surface** (20), and every
  **component group** (7) renders without breaking.
- All of them re-skin coherently across the **seven themes** when you set
  `data-theme="<key>"` on the document root.
- The kebab-case component classes (e.g. `.button-primary`, `.feature-card`,
  `.pill-tab-strip`, with BEM `__element` / `--modifier` suffixes) and the theme role tokens
  (`--role-{role}` plus the bare `--{role}` aliases) resolve as documented, so verbatim
  reference snippets work as written.

It is a coherence / smoke test, **not** a pixel-diff or determinism test (see Known limitation).

## Theme contract

- Set `data-theme="<key>"` on `document.documentElement`.
- Available theme keys: `clarity`, `default`, `punctuation`, `statement`, `feature-dark`,
  `code`, `deep`.
- Initial theme: `default`.

Every page in the suite ships the same theme-switcher in its top bar, wired to the same contract.

## Contents

| File                        | Proves                                                   |
| --------------------------- | -------------------------------------------------------- |
| `index.html`                | Entry point — links the galleries, lists themes          |
| `landing-kitchen-sink.html` | 29 landing section shapes                                |
| `app-kitchen-sink.html`     | 20 application surfaces                                  |
| `components-gallery.html`   | 7 component groups                                       |
| `styles/design-system.css`  | The compiled design system the suite renders             |
| `_fragments/landing/`       | The 29 raw landing fragments assembled into the gallery  |
| `_fragments/app/`           | The 20 raw app-surface fragments                         |
| `_fragments/components/`    | The 7 raw component-group fragments                      |

## How to view

Just open `index.html` in a browser:

```
open index.html        # macOS
xdg-open index.html    # Linux
```

No server, no build step, no network access. The pages link `styles/design-system.css` with a
relative path, so the whole suite works straight off the filesystem.

## How it was generated

This suite is produced by the cds visual-proof workflow:

1. Read the fixture design tokens from
   `../../setup/customizable-design-elements.yaml` (the canonical example values — these are
   intentional and load-bearing).
2. Compile those tokens into `styles/design-system.css` (theme role tokens follow the YAML
   `$conventions` `--role-{role key}` pattern, mirrored by bare `--{role}` aliases).
3. Generate one fragment per shape / surface / component group into `_fragments/` —
   `_fragments/landing/` (29), `_fragments/app/` (20), `_fragments/components/` (7).
4. Assemble the fragments into the three gallery pages, wrapping each in spec-card chrome and
   wiring the shared theme switcher.
5. Write this `index.html` entry point and `README.md`.

## How to regenerate

Re-run the cds visual-proof workflow after you change either input:

- **The elements YAML** (`../../setup/customizable-design-elements.yaml`) — e.g. new tokens,
  changed roles, palette edits. Note: if you change its *structure*, update the schema first.
- **The reference tree** (the components / sections / surfaces reference docs the fragments are
  generated from).

Regenerating recompiles `styles/design-system.css`, re-emits the `_fragments/` (landing, app,
components), and rebuilds the three gallery pages and this entry point. When the number of
fragments changes, update the per-gallery counts in `index.html` and the tables above to match
the actual on-disk fragment counts.

## Known limitation

The fragments are **LLM-generated**. They prove that the shapes **render and look coherent** —
that every section, surface, and component appears, themes cleanly across all seven keys, and uses
the documented class and token names. They do **not** prove byte-level determinism: regenerating
may produce different-but-equivalent markup for the same shape. Treat this as a visual coherence
check, not a golden-file / snapshot diff.
