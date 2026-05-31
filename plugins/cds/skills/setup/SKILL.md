---
name: setup
description: User-invoked only via the /cds:setup slash command — not triggered by natural language. Guides a step-by-step walkthrough to capture CUSTOMIZABLE_DESIGN_SYSTEM_* environment variable values (elements path, install mode, optional directories, framework target) and writes them to the env block of the appropriate settings.json (global ~/.claude/settings.json or project .claude/settings.local.json). Idempotent — safe to re-run to update existing values. Does not generate stylesheets, mocks, or component code.
allowed-tools: Read, Write, Edit, Bash, Glob
disable-model-invocation: true
---

# `/cds:setup`

A guided walkthrough that captures the `CUSTOMIZABLE_DESIGN_SYSTEM_*` env-var contract into the right `settings.json` `env` block so the other CDS skills find their defaults. User-invoked only — Claude does NOT auto-route to this skill.

This skill is never required. Users may set the env vars by hand per the plugin's `README.md` and never invoke `/cds:setup`. The README is a complete substitute.

---

## Inputs

- A user who has typed `/cds:setup` in Claude Code.
- Optional: an existing populated `customizable-design-elements.yaml` (path supplied by the user during the walkthrough).
- Optional: the shipped setup file at `../../setup/customizable-design-elements.yaml` (copied to the user's chosen location when they elect to bootstrap).
- Read access to the chosen settings file (or its parent directory, if the file does not yet exist).

## Discovery checklist

Ask in this order. Each step gathers exactly one decision.

1. "Do you already have a populated `customizable-design-elements.yaml`? (yes / no)"
2. If yes: "What is its absolute path?" — record as the value for `CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`.
3. If no: "Do you want CDS installed at the global level (one design system across all your projects) or project level (scoped to this project only)? (global / project)"
   - Global → copy `../../setup/customizable-design-elements.yaml` to `~/.claude/customizable-design-system/customizable-design-elements.yaml` (creating parent directories if needed).
   - Project → copy `../../setup/customizable-design-elements.yaml` to `<project-root>/.customizable-design-elements.yaml` (a hidden dot file at the project root).
   - Record the resulting path as the value for `CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` and the install mode as the value for `CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`.
4. For each of the optional env vars below, ask the user one at a time; accept "skip" to leave the variable unset:
   - `CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR` — directory for brand assets (SVGs, images, illustrations).
   - `CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR` — default output for `generate-stylesheets`.
   - `CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR` — default output for `compose-page` mocks.
   - `CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR` — default output for `compose-app-surface` framework-native code.
   - `CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK` — framework target for `compose-app-surface` (e.g., `react-tsx`, `vue-sfc`, `plain-html`).
5. Confirm the captured values back to the user before writing.

## Pipeline

1. Determine the settings file to write to (from step 3):
   - Global mode → `~/.claude/settings.json`.
   - Project mode → `<project-root>/.claude/settings.local.json` (gitignored layer — env vars often contain user-specific paths).
2. Read the existing settings file as JSON. If the file does not exist, treat as `{}`.
3. If the file is malformed JSON, STOP with `PRECONDITION_FAILED: settings.json is not valid JSON at <path>` — do not attempt repair.
4. Ensure the `env` key exists as an object; create if absent.
5. For each captured variable, set `env[VAR_NAME] = value`. Leave all other `env` keys (and unrelated top-level keys) untouched.
6. Write the result back with two-space indentation, trailing newline, and JSON key order preserved where the JSON library supports it.
7. Report the resulting `env` block to the user as confirmation.

## Halt conditions

- The settings file exists but is malformed JSON → STOP with `PRECONDITION_FAILED`.
- A copy of the shipped setup file is requested but the destination directory cannot be created (permissions, path collision with a file) → STOP and surface the path.
- The user declines to supply `CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` and provides no path to an existing YAML → STOP and report that no setup was written.

## Hard rules

- `/cds:setup` is NEVER required. The README documents the full env-var contract for users who choose to skip it.
- `/cds:setup` is idempotent. Running it twice on the same install reads the current values, presents them as defaults, and accepts edits without rewriting unrelated keys.
- `/cds:setup` writes ONLY to the `env` block of the chosen settings.json. It does not touch any other settings, file, or directory beyond copying the shipped setup file when the user chose to bootstrap from it.

## Boundary — does not

- Generate stylesheets, mocks, or component code (those are `generate-stylesheets`, `compose-page`, `compose-app-surface`).
- Edit `customizable-design-elements.yaml` content. It only copies the shipped template to the chosen path.
- Write to any settings file beyond the chosen one (no cross-scope writes).
- Touch the plugin's own files in `cds/`. Setup is project-side configuration, not plugin-tree mutation.
