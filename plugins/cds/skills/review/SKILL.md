---
name: review
description: Opens ANY generated output — a Shell, a Page HTML, a View, an isolated Section, or an isolated Component — in a playground-style visual review harness so the user can SEE it, click regions, attach change comments, and copy out one natural-language change request to paste back — which then routes to the composer that owns the artifact. Trigger on "review the mock", "open it so I can comment", "let me mark up the design", "visual review", "comment on the mockup", "annotate the mock", "I want to give feedback on this". Do NOT trigger on composing or iterating (compose-page, compose-shell, compose-view — the pasted change request itself routes there), on auditing or compliance checks (audit-against-system), or on packaging an approved change (package-change).
allowed-tools: Read, Bash, Glob
---

## What this skill does

Builds a self-contained review harness beside any composed output by running `tools/build-review-harness.py`, opens it in the user's browser, and tells the user how to comment and copy the assembled change request back. The harness embeds the artifact in an iframe exactly as shipped (light/dark toggle intact), maps the wireframe sidecar's Section blocks onto the artifact's top-level structural regions so hovering shows each region's Building Blocks identity, lets the user pin numbered comments with quick tags, and assembles one natural-language change request grouped by region with a copy button. The pasted request routes back to the composer that owns the artifact — this skill is the human-review step of the compose → review → iterate loop, not a composer.

It opens every output kind: a **Page HTML** (`compose-page`), a **Shell** (`compose-shell`), a **View** (`compose-view`), or an **isolated Section / Component** render (`compose-page`).

## Vocabulary

Internal Building Blocks terms (`../../reference/model/entity-catalog.md`) govern the harness labels and the assembled change request: each labeled region is a **Section**; a lazily-assigned Section received its layout from a **Shape** at build time; in a View, the **Shell**'s Sections frame the **Page** in the vacant space. The harness reads each Section's identity (name, Section type, received Shape, ground) from the wireframe sidecar — it never re-derives it from the markup.

## Inputs

- **From caller (runtime):** the artifact path (argument or plain-language reference); optional sidecar path overrides; optional harness output path override.
- **From the sidecars beside the artifact** (pipeline contract, `../../reference/pipeline.md`): `<basename>.wireframe.txt` (Section identity blocks) and `<basename>.decisions.md` (shown in the harness as a collapsible decision log). Both optional — the harness falls back to "Region 1..N" labels without them.
- **From the composer state records** (at `~/.claude/customizable-design-system/state/{compose-page|compose-shell|compose-view}/` or the project-local equivalent, per `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`): the most recent `output_path`, used to resolve "the mock" / "it" when the caller names no file, and to identify which composer owns the artifact.
- **From `tools/build-review-harness.py`:** the deterministic, stdlib-only harness builder this skill runs via Bash.

## Discovery checklist

1. **Resolve the target artifact.** Explicit path argument first; else the most recent composer state record's `output_path` (across compose-page, compose-shell, and compose-view); else ask the user which output to open. Verify the file is readable → STOP `TARGET_UNREADABLE` if not.
2. **Identify the owning composer** from the matching state directory (compose-page, compose-shell, or compose-view) — the pasted change request routes there. A stored Shell with no state record still opens; its change requests route to `compose-shell` by name.
3. **Locate the sidecars.** Beside the artifact by basename (`<basename>.wireframe.txt`, `<basename>.decisions.md`). Missing sidecars are not a halt — the builder falls back to generic region labels; a caller-supplied sidecar path that cannot be read is a builder failure (surfaces as `REVIEW_HARNESS_FAILED`).
4. **Resolve the harness output path.** Caller override, else the builder default: `<basename>.review.html` beside the artifact.

## Pipeline

0. **Stylesheet freshness (silent).** Run the pipeline's freshness stage (`../../reference/pipeline.md`) before building the harness: compare the `cds_hash.py` fingerprints against `manifest.json`; on mismatch invoke `generate-css` and proceed. Never mention staleness or regeneration to the human; halt only `STYLESHEETS_REGEN_FAILED:{inner}` if the regeneration itself fails.
1. **Build the harness.** Run via Bash: `python3 "${CLAUDE_PLUGIN_ROOT}/tools/build-review-harness.py" <artifact.html> [--wireframe <path>] [--decisions <path>] [--out <path>]`. A non-zero exit → STOP `REVIEW_HARNESS_FAILED` with the script's stderr verbatim.
2. **Open it.** `open <basename>.review.html`.
3. **Tell the user how to review.** Hover a region to see its Section identity ("Section <id> - Shape <shape>"); click to pin a numbered marker and write a comment (quick tags: copy, layout, color, spacing, swap-shape, remove, add); the bottom panel assembles the change request live; press Copy and paste it back into the conversation. The "Review mode" toggle switches between commenting and browsing the artifact (links and the color-mode toggle active).
4. **Route the pasted change request.** When the user pastes the copied request, it is an iteration against the same output path, handled by the composer that owns the artifact — `compose-page` for a Page HTML or isolated render, `compose-shell` for a Shell, `compose-view` for a View — standard run-mode rules, `../../reference/pipeline.md` (Run-modes). This skill hands off; it does not compose.

## State

None. This skill is a sidecar-consumer, not a state writer: it writes nothing under the state directories — the only file it emits is `<basename>.review.html` beside the artifact. The `.review.html` is a **review artifact, not a deliverable** — `package-change` must not bundle it; only the artifact, its sidecars, and the pipeline outputs cross the hand-off boundary.

## Halt conditions

- `TARGET_UNREADABLE` — the artifact cannot be read (file missing, unreadable, or empty).
- `REVIEW_HARNESS_FAILED` — `tools/build-review-harness.py` exited non-zero (unreadable sidecar override, unwritable output path, or an internal builder error); surface its stderr verbatim.
- `STYLESHEETS_REGEN_FAILED:{inner-code}` — the silent freshness stage's auto-invoked `generate-css` halted; inner code surfaced verbatim.

Halt surface format:

```
STOP: review: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance gate

N/A — the harness is self-styled scaffolding around the unmodified artifact and is never audited against the system; the artifact inside it already passed its composer's compliance pass. Do not run `audit-against-system` on a `.review.html`.

## Boundary — does not

- Does not modify the artifact, its sidecars, or any state record — read-only except for the emitted `.review.html`.
- Does not compose, iterate, or apply the requested changes — the pasted change request routes to the owning composer.
- Does not audit (that is `audit-against-system`) and does not package (that is `package-change`; the `.review.html` is excluded from its bundles).
- Does not depend on the artifact's stylesheet for its own styling — the harness is self-styled (system font, light/dark via `prefers-color-scheme`) and makes no external requests.
- Does not re-derive Section identity from markup; identity comes from the wireframe sidecar or falls back to generic region labels.
