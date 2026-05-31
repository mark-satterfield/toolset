# CDS — Customizable Design System

A brand-neutral design system you install in any project. CDS gives you a stylesheet set, a way to mock pages and components, a way to ship in-app surfaces, and an audit tool — all derived from one YAML file of design choices you supply.

---

## What's in the box

- **6 slash commands** for direct invocation: `/cds:setup`, `/cds:generate-stylesheets`, `/cds:compose-page`, `/cds:compose-app-surface`, `/cds:apply-design-system`, `/cds:audit-against-system`.
- **6 skills** the commands invoke. Five also auto-route from natural-language phrasing (the model recognizes "build me a landing page", "audit this UI", "regenerate the CSS", etc.). The `setup` skill is gated by `disable-model-invocation: true` and fires only from `/cds:setup`.
- **2 sub-agents** that bundle the right skills with an identity: `cds-ui-author` (for UI work), `cds-code-companion` (for non-UI code that touches UI).
- **A reference tree** of every fixed design decision — spacing, motion, type scales, component anatomy, accessibility rules — that the skills consult deterministically.
- **A schema** for the one file you customize (`customizable-design-elements.yaml`).

What you supply: the YAML. Optionally, environment variables for default paths.

---

## Install

1. Install the plugin from its marketplace location (or `--plugin-dir ./cds` during development).
2. Choose how to scope it:
   - **Global** — one design system across all your projects.
   - **Project** — design system scoped to this project; does not bleed into others.
3. Set up your environment variables (next section). You can do this by hand using this README, or by running `/cds:setup` for a guided walkthrough.

---

## Configure: environment variables

CDS reads its configuration from environment variables in your `settings.json`'s `env` block. All variables are optional — when one is unset, the relevant skill asks you for the value at call time.

Prefix: `CUSTOMIZABLE_DESIGN_SYSTEM_` (underscores; not hyphens — POSIX env-var rules).

| Variable | Required? | Resolves | Consumed by |
|---|---|---|---|
| `CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` | Recommended | Path to your populated `customizable-design-elements.yaml` | All skills |
| `CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE` | Recommended | `global` or `project` — gates where per-skill state is stored | `compose-page`, `compose-app-surface` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR` | Optional | Directory holding brand assets (SVGs, images, illustrations) | `compose-page`, `compose-app-surface` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR` | Optional | Default output directory for the generated CSS files | `generate-stylesheets`, stale-detection in compose skills |
| `CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR` | Optional | Default output directory for HTML mocks | `compose-page` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR` | Optional | Default output directory for framework-native component code | `compose-app-surface` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK` | Required for `compose-app-surface` | Framework target (e.g., `react-tsx`, `vue-sfc`, `plain-html`) | `compose-app-surface` |

When a variable is unset, the relevant skill asks for the value at call time. If the user does not provide one, the skill halts with the appropriate `STOP:` code (e.g., `ELEMENTS_YAML_UNSET`, `FRAMEWORK_UNSET`, `OUTPUT_PATH_UNRESOLVABLE`).

### Settings file location

- Global install → `~/.claude/settings.json`
- Project install → `<project-root>/.claude/settings.local.json` (gitignored — env vars often contain user-specific paths)

### Configure by hand

Edit the chosen settings file directly. Example for global install:

```json
{
  "env": {
    "CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS": "/Users/you/.claude/customizable-design-system/customizable-design-elements.yaml",
    "CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE": "global",
    "CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR": "/Users/you/projects/my-app/src/styles/design-system",
    "CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR": "/Users/you/projects/my-app/design-mocks",
    "CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR": "/Users/you/projects/my-app/src/components/cds",
    "CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK": "react-tsx"
  }
}
```

### Configure with `/cds:setup`

Type `/cds:setup` in Claude Code. The skill walks through:

1. Whether you already have a populated `customizable-design-elements.yaml`. If yes: it asks for the path.
2. If no: it asks whether to scope globally or per-project, then copies the shipped template to your chosen location:
   - Global → `~/.claude/customizable-design-system/customizable-design-elements.yaml`
   - Project → `<project-root>/.customizable-design-elements.yaml`
3. It captures any other defaults you want (assets dir, output dirs, framework).
4. It writes everything to the right `settings.json` `env` block, preserving any other keys you have there.

`/cds:setup` is idempotent — running it again reads your current values and presents them as defaults. The setup skill is never required; this README is a complete substitute.

---

## Populate `customizable-design-elements.yaml`

This is the only file you really customize. It carries:

- **Color catalog**: common colors (white, black) + named palettes (Ramp type for stepwise progressions, Discrete type for named-color sets). Each color has a hex value and optional display name.
- **Typefaces**: variable + static fonts with their axes (weights, optical size, italic).
- **Fonts**: semantic font roles (`sans`, `serif`, `mono`) → typeface assignments with CSS fallback chains.
- **Roles**: semantic CSS roles (surface/text/border/accent families) + component CSS roles (button/footer/etc.). Each role has a type (color/dimension/weight/etc.), a scope (semantic/component), a description, and an optional fallback.
- **Themes**: named theme classes (e.g., `default`, `clarity`, `deep`). Each theme defines `light` and `dark` mode bindings — what color each role resolves to.

The schema at `validation/customizable-design-elements.schema.json` is the authoritative shape. The shipped setup file at `setup/customizable-design-elements.yaml` is a worked example you can copy and edit.

What you do NOT put in this YAML:

- Spacing, type scales, motion durations, radius, shadows — those are FIXED by the design system and live in the reference tree.
- Output paths, framework target, install mode — those are env vars.

---

## Core workflows

### Regenerate the stylesheet set

When you edit `customizable-design-elements.yaml` (or when CDS itself updates):

> "Regenerate the design-system CSS."

`generate-stylesheets` reads your YAML + the reference, writes three files (`tokens.css`, `components.css`, `themes.css`) to your stylesheets output directory, plus a `manifest.json` with SHA-256 fingerprints. Other CDS skills detect stale stylesheets by comparing the YAML's hash to the manifest.

### Mock a page

> "Build a landing page for our launch."

`compose-page` walks discovery (handoff-or-not, page type, content mode, asset paths, output path) and produces one self-contained HTML file you can open directly in a browser, attach to a spec, or send for review. The file inlines the stylesheet set and includes a light/dark mode toggle.

If you have content already:

> "Render this blog post: docs/announcements/launch.md"

Same skill, supplied-content branch — the skill parses the content into section candidates and renders them through the chosen page type.

To iterate:

> "Tweak the mock — make the hero darker and swap the second feature card."

The skill detects the prior run by `output_path` match, loads the prior brief from state, applies your changes, writes the next version. No metadata in the mock; iteration intelligence lives in the skill's state directory.

### Mock a single component or section

> "Mock this Button component."

`compose-page` wraps the component in a minimal HTML page (1440px viewport, 64px padding, light-mode default with toggle) so the browser can render it. Same skill, surface-kind=component.

### Build an in-app surface

> "Build the settings page in the app."

`compose-app-surface` produces framework-native component code (TSX, Vue SFC, etc.) at your `CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR`, plus integration diffs (nav entry, route table, parent component update). The emitted code links to your stylesheet set as external assets — it does NOT inline CSS (that is mock-only), and it does NOT emit theme controllers or routing (your host project owns those).

### Consult the design system while writing handlers

> "I'm wiring up the form-submit for the sign-up page. What classes, tokens, events, and ARIA contracts should I bind to?"

`apply-design-system` loads the relevant reference content into the calling agent's context, structured as:

- `## Class names` — CSS classes you may select
- `## Token names` — CSS custom properties you may read
- `## Event hooks` — DOM events you should listen for or emit
- `## ARIA contracts` — accessibility patterns to honor
- `## Reference pointers` — files to read for deeper context
- `## Halt conditions` — situations where the design system does not cover what you need (add to `missing-components.md` instead of inventing)

No code is generated — your handler stays yours; CDS surfaces the contract you should bind to.

### Audit existing UI

> "Audit the search results page."

`audit-against-system` checks the target against `compliance.md` rules, scoped by rendering context (in-app vs. standalone). Output is either inline annotations on the file(s) or a structured report. Each violation cites the relevant reference file.

---

## Sub-agent usage patterns

For one-shot operations (regenerate stylesheets after editing YAML, audit a single file), call the skill directly.

For sustained UI work (a multi-page mock session, building several in-app surfaces, iterating on a design across many changes), spawn the appropriate sub-agent:

- **`cds-ui-author`** — has `compose-page`, `compose-app-surface`, `audit-against-system` in its toolset. Its system prompt mandates consulting the reference and self-auditing before declaring done. Inspect at `agents/cds-ui-author.md`.
- **`cds-code-companion`** — has `apply-design-system`, `audit-against-system`. Use when an agent is writing non-UI code that interacts with generated UI and you want the design-system vocabulary loaded into its context up front. Inspect at `agents/cds-code-companion.md`.

Spawning happens through Claude Code's standard sub-agent flow (Task tool with `subagent_type=cds-ui-author`).

**Important:** sub-agents are recommended, not enforcement gates. Every skill remains directly callable in three ways — its slash command (e.g., `/cds:compose-page`), its natural-language trigger (e.g., "mock a landing page"), or an explicit invocation from any orchestrator. A caller that bypasses the sub-agents bypasses the system-prompt mandates that come with them.

### When to spawn which

| Situation | Path |
|---|---|
| Sustained UI authoring (mocks + production surfaces, multiple invocations) | Spawn `cds-ui-author` |
| Sustained non-UI code authoring touching UI (handlers, fetchers, business logic, glue) | Spawn `cds-code-companion` |
| One-off `generate-stylesheets` after editing YAML | Call the skill directly |
| One-off `audit-against-system` against a single file | Call the skill directly |
| One-off mock for a quick share | Call `compose-page` directly |

---

## Iteration model

Mocks are deliverables, not state. To iterate, just call `compose-page` again with the change described in plain language. The skill:

1. Resolves the output path you supplied (or the default from `CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`).
2. Looks in its state directory for a prior run with that exact output path.
3. If it finds one, loads the prior brief + decisions and applies your change to them.
4. Writes the next mock to the same path (or a new path if you supplied one) + a new state record.

Matching uses strict `output_path` equality. If you want a fresh start, supply a new output path. If your request reads as a continuation but with a new filename, the skill asks.

The plugin assumes a single user; no file locking. Two simultaneous invocations against the same state directory produce undefined ordering.

---

## Updating brand inputs

Edit `customizable-design-elements.yaml`. Then:

> Regenerate the design-system CSS.

CDS recomputes the three CSS files and the manifest. Existing mocks become "stale" (the elements-YAML SHA-256 in their state records will not match the new manifest). On the next mock invocation, the skill prompts you to either regenerate or accept the stale stylesheet for that run.

---

## What CDS will not do

- It will not read your host-project code to figure out conventions. Everything it does comes from the reference tree, your elements YAML, or runtime input you give it.
- It will not emit theme controllers, mode resolvers, or routing code for in-app surfaces. Your host project owns those.
- It will not embed metadata inside the deliverable. Mocks and emitted code are clean.
- It will not fall back to "best guess" when the reference is missing something. It STOPs with a halt code and tells you what is missing. Halt codes include `SHAPE_RULES_PENDING:{page-type}` (composition rules for non-landing pages are explicitly deferred for beta-1), `MISSING_COMPONENT:{name}`, `STYLESHEETS_STALE`, `FRAMEWORK_UNSET`, and others.
- It will not extend itself. Adding new components, role definitions, or themes is your work in the elements YAML and the reference tree.

---

## Beta-1 limitations (explicit)

- **Non-landing page composition is not supported** in beta-1. `compose-page` halts with `SHAPE_RULES_PENDING:{page-type}` on requests for Editorial Detail, Resource Index, Documentation, Conversion/Authentication, or Application Shell page types. Landing-page composition is fully supported.
- **In-app section-level shape decisions are not supported**. `compose-app-surface` halts with `APP_SECTION_RULES_PENDING:{section-type}`. Shell-layout and page-shape composition from `app-shapes.md` IS supported.
- **The shipped setup file (`setup/customizable-design-elements.yaml`) carries the in-house working values** as a worked example. Treat it as a starter template you copy and replace — your real working file lives at the path your `CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` env var points to. Marketplace prep replaces these values with a generic placeholder.
- **No plugin tests** in beta-1. Verification is by spot-check and live use.
- **No hard enforcement** of design-system use. The sub-agents are the strong-default path; direct skill calls bypass the system-prompt mandates.

---

## Troubleshooting

**"The skill says my stylesheets are stale."** Run `generate-stylesheets` — your elements YAML has changed since the last generation.

**"The skill stopped with `SHAPE_RULES_PENDING:editorial-detail`."** Beta-1 only supports landing-page composition for new mocks. The editorial detail rules are deferred work.

**"The skill stopped with `MISSING_COMPONENT:approval-mode-tool-control`."** The component you asked for is not in `components.md` yet. Check `skills/compose-app-surface/reference/missing-components.md` — it likely names what is needed; that file is the input to the work of authoring it.

**"My sub-agent is generating UI code by hand instead of using `compose-page`."** The sub-agent's system prompt mandates use of the skills, but Claude can occasionally drift. Re-spawn the sub-agent, or explicitly remind it to invoke `compose-page` rather than emit markup directly.

**"`/cds:setup` overwrote a value I had hand-edited."** It should not — the merge semantics preserve unrelated keys and present current values as defaults. If a known value was changed, that is a bug; surface it.

**"How do I know which sub-agent to spawn?"** UI work (mocks, in-app surfaces) → `cds-ui-author`. Non-UI code that touches UI (handlers, fetchers, business logic) → `cds-code-companion`. Audit-only tasks → call `audit-against-system` directly.

---

## Where things live (cheat sheet)

| Looking for | Where |
|---|---|
| Your design choices (palettes, typefaces, themes) | `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` |
| The schema for your design choices | `validation/customizable-design-elements.schema.json` |
| Vocabulary — what counts as a Component vs. a Shape vs. a Use case | `reference/vocabulary.md` |
| Fixed design rules (spacing, motion, type scales) | `reference/foundations/*.md` |
| Component anatomy | `reference/components.md` |
| Per-page-type composition rules | `reference/page-types.md` |
| Landing-page section shape rules | `skills/compose-page/reference/landing-sections-shape-rules.md` |
| App shell layouts + page shapes | `skills/compose-app-surface/reference/app-shapes.md` |
| Components not yet covered | `skills/compose-app-surface/reference/missing-components.md` |
| Compliance rules | `reference/compliance.md` |
| Sub-agent system prompts | `agents/cds-ui-author.md`, `agents/cds-code-companion.md` |
| Slash commands | `commands/{setup,generate-stylesheets,compose-page,compose-app-surface,apply-design-system,audit-against-system}.md` |
| Your per-run skill state | `~/.claude/customizable-design-system/state/{skill}/` (global) or `<project>/.claude/customizable-design-system/state/{skill}/` (project) |
| The plugin manifest | `.claude-plugin/plugin.json` |
