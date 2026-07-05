---
name: validate-okf-bundle
description: >-
  Validate an Open Knowledge Format (OKF) bundle for v0.1 conformance and report
  warnings. Use when the user wants to check, validate, lint, or verify that a
  directory of markdown files conforms to OKF, or asks whether a bundle is
  OKF-conformant. Prefers the dedicated okflint linter when installed; falls back
  to the bundled conformance script.
allowed-tools: [Read, Grep, Glob, Bash]
---

# Validate an OKF bundle

Check conformance with the three OKF v0.1 rules and surface non-blocking
warnings. Conformance rules (spec §9):

1. Every non-reserved `.md` file has a parseable YAML frontmatter block. (`E1`)
2. Every frontmatter block has a non-empty `type` field. (`E2`)
3. Reserved files (`index.md`, `log.md`) follow their structure rules. (`E3`)

Everything else is soft guidance — **a bundle must never be rejected** for
missing optional fields, unknown `type` values, unknown frontmatter keys, broken
links, or missing `index.md` files.

## Preferred: okflint

If `okflint` is installed, use it — it has a broader rule set, profile
manifests, wikilink resolution, and JSON output.

```bash
command -v okflint
```

If **not** installed, offer to install it (`uv tool install okflint`, or
`pip install okflint`), and note the user can decline and use the bundled
script. If a profile manifest is present, pass it:

```bash
if [ -f okf-base.yaml ]; then
  okflint validate --manifest okf-base.yaml <bundle>
else
  okflint validate <bundle>
fi
```

Exit codes: `0` pass · `1` conformance failure · `2` bad manifest. See
`${CLAUDE_PLUGIN_ROOT}/references/serving-and-tooling.md`.

## Fallback: bundled script

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/validate-okf.sh" <bundle>
```

Exit `0` = conformant, `1` = conformance error(s), `2` = bad path. It reports
`E1`/`E2`/`E3` errors and `W1`/`W5` warnings.

## Reporting

Summarize clearly, e.g.:

```
PASS: 12/12 concept files have valid frontmatter with a type field
WARN: 3 files missing 'description' (recommended, non-blocking)
WARN: 2 broken cross-links (permitted — may be not-yet-written knowledge)
```

State the verdict (conformant or not), list errors with file paths, then
warnings. If it fails, point the user at `enrich-okf-concepts` (missing fields)
or `convert-to-okf` (files lacking frontmatter/`type`) to fix.
