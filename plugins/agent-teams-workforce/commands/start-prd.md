---
description: "Resolve a PRD's Epic and report where its elaboration stands; the pipeline's driver runs elaboration"
argument-hint: "<prd-path-or-title>"
allowed-tools: [Bash, Read, Glob, Skill]
---

# Start a PRD

Take `$ARGUMENTS` from a PRD document to the Epic the pipeline elaborates, and report where
that Epic's elaboration stands.

The pipeline elaborates an Epic and reads the PRD linked to it. Elaboration, `prd-to-spec`,
runs in the Python orchestrator (`${CLAUDE_PLUGIN_ROOT}/orchestrator/run.py`), and the
pipeline's driver starts it for an Epic its elaboration lane selects. **This command dispatches
nothing**: there is no workflow script for elaboration, and a session does not start the
orchestrator or the driver. It starts from the PRD document, resolves the Epic linked to it, and
hands that Epic to the same procedure `/agent-teams-workforce:work-bead <epic-id>` uses.

## 1. Locate the PRD

The argument is a path or a title. If it is a title, search the PRD directory: the
directory in the PRD_DIR_ENV variable the `pipeline-contracts` skill names
(`${CLAUDE_PLUGIN_ROOT}/skills/pipeline-contracts/SKILL.md`, schema
`schemas/driver-surface.schema.json`, `$defs.DriverEnvironment`). Read the name from the skill's
generated module, never from memory; if the variable is unset, report that variable as unset and
stop:

```bash
CONTRACTS="${CLAUDE_PLUGIN_ROOT}/skills/pipeline-contracts/scripts"
{ read -r PRD_DIR_VAR; read -r PRD_DIR; } < <(PYTHONPATH="$CONTRACTS" python3 -c 'import os, driver_surface_types as d; print(d.PRD_DIR_ENV); print(os.environ.get(d.PRD_DIR_ENV, ""))')
echo "PRD_DIR_VAR=${PRD_DIR_VAR}"
echo "PRD_DIR=${PRD_DIR}"
```

When `PRD_DIR` printed empty, report `<PRD_DIR_VAR> is unset` and stop. Otherwise:

```bash
grep -ril -- "<title>" "<PRD_DIR>"
```

Read the PRD. Stop and report if you cannot find it —
do not invent a PRD from the title.

## 2. Resolve the Epic linked to the PRD

The PRD names its Epic on a `**Epic:** <id>` line, or an Epic carries the label
`prd:<prd file stem>`:

```bash
grep -m1 '^\*\*Epic:\*\*' "<prd path>"
atw-bd list --type epic --label "prd:<prd file stem>"
```

- Found → adopt it, with its `id`.
- Not found → stop and report that the PRD has no linked Epic. A PRD and its Epic are
  written together when the PRD is created; this command creates neither.

Whether the Epic is selected is the driver's decision: it selects an Epic that is open, scored,
with no unmet prerequisite, and whose elaboration state is ready, or in progress with no live
run owning it. This command changes none of that.

## 3. Hand off

Invoke the `elaborate-prd-epic` skill with the Epic's `id` and the PRD path. It reports the
Epic's elaboration state, where the Epic's step journal stands, and what earlier dispatches
wrote into beads. You report what it found; you write nothing.

**Do not work out the repo span.** The span is an output of the run: its span step reads it from
the matrix after the architecture is approved.

Do not re-implement any of that here. If it needs to change, change it there so
both doors change together.
