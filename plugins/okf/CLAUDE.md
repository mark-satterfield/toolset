# okf — Claude Code Instructions

@README.md

## Working in this plugin

- Skills own the OKF **knowledge**; agents are lean **workers**. Keep the rules
  in `references/` — do not restate them inside skills or agent prompts; link to
  them.
- The router skill (`skills/okf`) picks interactive-skill vs. delegate-to-agent
  by input size. Skills handle small/in-the-loop work; agents (`okf-auditor`,
  `okf-bundle-builder`, `okf-enricher`) handle bulk and read-only fan-out.
- Scripts are the deterministic surface: `scripts/validate-okf.sh` (conformance)
  and `scripts/gen-index.sh` (index generation). Skills and agents shell out to
  them rather than reimplementing the logic.
- Always address bundled files by `${CLAUDE_PLUGIN_ROOT}/references/…` and
  `${CLAUDE_PLUGIN_ROOT}/scripts/…`, from skills, commands, and agent prompts
  alike. Bare relative paths (`../../references/…`) are undefined after install —
  the plugin root is the only stable anchor.
- The one non-negotiable OKF rule to enforce everywhere: **never invent data**,
  and **`type` is the only hard requirement**.
