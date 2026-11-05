---
description: "Assess the Epic-to-Epic edges of one Epic"
argument-hint: "<epic-id> [--propose]"
allowed-tools: [Bash, Read, Write]
---

# Dependency assessment

The owner invokes this command for one Epic. Preserve the existing apply behavior: it writes
that Epic's assessed edges unless `--propose` is present, which returns the diff without writing.
The driver does not call it. Epic ordering follows the recorded shared-item judgments and does
not depend on architecture approval or verified marks.

Require exactly one Epic ID. Read `pipeline-contracts` and `epic-sequencing`. Resolve the current
repository with `git rev-parse --show-toplevel`, use `${CLAUDE_PLUGIN_ROOT}` as the plugin root,
and create a unique run directory under the repository's `.claude/workflow-runs/dependency-assessment/`.
Read the required project environment names from the generated driver-surface contract; preserve
the current environment, including the PRD/vault location used by the matrix context reader.

Write `args.json` in the run directory with these exact fields:

- `repoPath`: the absolute repository root.
- `pluginRoot`: the absolute installed plugin root.
- `workDir`: the unique absolute run directory.
- `epic`: the requested Epic ID.
- `apply`: false only for `--propose`; true otherwise.
- `archPath` and `projectRoot`: include the configured values when present.

Run the owner command once through Bash:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/atw-portfolio" dependency-assessment --args "<run>/args.json" --output "<run>/result.json"
```

`portfolio.py` runs the deterministic plan, context, validation and apply/diff commands directly.
Only the Epic dependency judgment starts a reasoning agent. It uses the shared edge-proposal
schema and validates the accepted proposal before any tracker mutation.

Read the result file and report the added, converted, removed and unchanged edges, whether they
were applied or proposed, the proposal path and any validation findings. A rejected proposal
leaves the tracker unchanged. Do not invoke a Workflow or a command-runner agent.
