---
name: review-mock
description: Opens a composed mock (any compose-page output — a page, a Shell, a Section, a Component) in a playground-style visual review harness so the user can SEE it, click regions, attach change comments, and copy out one natural-language change request to paste back — which then feeds compose-page's iteration model. Trigger on "review the mock", "open the mock so I can comment", "let me mark up the design", "visual review", "comment on the mockup", "annotate the mock", "I want to give feedback on this mock". Do NOT trigger on composing or iterating a mock (compose-page — the pasted change request itself routes there), on auditing or compliance checks (audit-against-system), or on packaging an approved change (package-change).
allowed-tools: Read, Bash, Glob
---

## What this skill does

Builds a self-contained review harness beside a composed mock by running `tools/build-review-harness.py`, opens it in the user's browser, and tells the user how to comment and copy the assembled change request back. The harness embeds the mock in an iframe exactly as shipped (light/dark toggle intact), maps the wireframe sidecar's Section blocks onto the mock's top-level structural regions so hovering shows each region's Building Blocks identity, lets the user pin numbered comments with quick tags, and assembles one natural-language change request grouped by region with a copy button. The pasted request routes to `compose-page` iteration against the same output path — this skill is the human-review step of the compose → review → iterate loop, not a composer.

## Vocabulary

Internal Building Blocks terms govern the harness labels and the assembled change request: each labeled region is a **Section**; a dynamic Section received its layout contract from a **Shape** at build time; the **Shell**'s persistent Sections (topbar, footer) frame the **Section Container** (alias: page type). The harness reads each Section's identity (name, Section type, received Shape, ground) from the wireframe sidecar — it never re-derives it from the markup. `../../reference/aliases.md` maps the user's words onto these terms when resolving the target.

## Inputs

- **From caller (runtime):** the mock path (argument or plain-language reference); optional sidecar path overrides; optional harness output path override.
- **From the sidecars beside the mock** (pipeline contract, `../../reference/pipeline.md`): `<basename>.wireframe.txt` (Section identity blocks) and `<basename>.decisions.md` (shown in the harness as a collapsible decision log). Both optional — the harness falls back to "Region 1..N" labels without them.
- **From the `compose-page` state records** (at `~/.claude/customizable-design-system/state/compose-page/` or `<project-root>/.claude/customizable-design-system/state/compose-page/` per `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`): the most recent `output_path`, used to resolve "the mock" when the caller names no file.
- **From `tools/build-review-harness.py`:** the deterministic, stdlib-only harness builder this skill runs via Bash.

## Discovery checklist

1. **Resolve the target mock.** Explicit path argument first; else the most recent `compose-page` state record's `output_path`; else ask the user which mock to open. Verify the file is readable → STOP `TARGET_UNREADABLE` if not.
2. **Locate the sidecars.** Beside the mock by basename (`<basename>.wireframe.txt`, `<basename>.decisions.md`). Missing sidecars are not a halt — the builder falls back to generic region labels; a caller-supplied sidecar path that cannot be read is a builder failure (surfaces as `REVIEW_HARNESS_FAILED`).
3. **Resolve the harness output path.** Caller override, else the builder default: `<basename>.review.html` beside the mock.

## Pipeline

1. **Build the harness.** Run via Bash: `python3 "${CLAUDE_PLUGIN_ROOT}/tools/build-review-harness.py" <mock.html> [--wireframe <path>] [--decisions <path>] [--out <path>]`. A non-zero exit → STOP `REVIEW_HARNESS_FAILED` with the script's stderr verbatim.
2. **Open it.** `open <basename>.review.html`.
3. **Tell the user how to review.** Hover a region to see its Section identity ("Section <id> - Shape <shape>"); click to pin a numbered marker and write a comment (quick tags: copy, layout, color, spacing, swap-shape, remove, add); the bottom panel assembles the change request live; press Copy and paste it back into the conversation. The "Review mode" toggle switches between commenting and browsing the mock (links and the color-mode toggle active).
4. **Route the pasted change request.** When the user pastes the copied request, it is a `compose-page` iteration against the same output path (the request names the mock's file path) — standard run-mode rules, `../../reference/pipeline.md` (Run-modes). This skill hands off; it does not compose.

## State

None. This skill is a sidecar-consumer, not a state writer: it writes nothing under the state directories — the only file it emits is `<basename>.review.html` beside the mock. The `.review.html` is a **review artifact, not a deliverable** — `package-change` must not bundle it; only the mock, its sidecars, and the pipeline artifacts cross the hand-off boundary.

## Halt conditions

- `TARGET_UNREADABLE` — the mock cannot be read (file missing, unreadable, or empty).
- `REVIEW_HARNESS_FAILED` — `tools/build-review-harness.py` exited non-zero (unreadable sidecar override, unwritable output path, or an internal builder error); surface its stderr verbatim.

Halt surface format:

```
STOP: review-mock: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance gate

N/A — the harness is self-styled scaffolding around the unmodified mock and is never audited against the system; the mock inside it already passed its composer's compliance pass. Do not run `audit-against-system` on a `.review.html`.

## Boundary — does not

- Does not modify the mock, its sidecars, or any state record — read-only except for the emitted `.review.html`.
- Does not compose, iterate, or apply the requested changes — the pasted change request routes to `compose-page`.
- Does not audit (that is `audit-against-system`) and does not package (that is `package-change`; the `.review.html` is excluded from its bundles).
- Does not depend on the mock's stylesheet for its own styling — the harness is self-styled (system font, light/dark via `prefers-color-scheme`) and makes no external requests.
- Does not re-derive Section identity from markup; identity comes from the wireframe sidecar or falls back to generic region labels.
