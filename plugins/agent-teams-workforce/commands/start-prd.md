---
description: "Start a PRD at the top of the pipeline — Epic, TRD, Spec+Story per repo, Tasks"
argument-hint: "<prd-path-or-title> [repo,repo,... — an override, rarely needed]"
allowed-tools: [Bash, Read, Glob, Skill, Workflow]
---

# Start a PRD

Take `$ARGUMENTS` from a PRD document to an emitted Epic → Story → Task hierarchy.

The pipeline elaborates an Epic and reads the PRD linked to it. This command starts
from the PRD document, resolves the Epic linked to it, and hands that Epic to the same
procedure `/agent-teams-workforce:work-bead <epic-id>` uses.

## 1. Locate the PRD

The first argument is a path or a title. If it is a title, search the PRD directory,
`$ATW_PRD_DIR`; if it is unset, report `ATW_PRD_DIR is unset` and stop:

```bash
grep -ril -- "<title>" "$ATW_PRD_DIR"
```

Read the PRD. Extract `title` and `body`. Stop and report if you cannot find it —
do not invent a PRD from the title.

## 2. Resolve the Epic linked to the PRD

The PRD names its Epic on a `**Epic:** <id>` line, or an Epic carries the label
`prd:<prd file stem>`:

```bash
grep -m1 '^\*\*Epic:\*\*' "<prd path>"
bd list --type epic --label "prd:<prd file stem>"
```

- Found → adopt it, with its `id`.
- Not found → stop and report that the PRD has no linked Epic. A PRD and its Epic are
  written together when the PRD is created; this command creates neither.

Every other condition — the Epic is scored, the Epics it depends on are elaborated, it
is not owned by another run — is checked by `prd-to-spec` at its start, which refuses
with a named reason. Report a refusal as it comes back.

## 3. Hand off

Invoke the `elaborate-prd-epic` skill with the resolved pair. Pass a BRD path only in the uncommon case that a BRD exists —
it is optional, and a PRD never has to reference one. It owns the `prd-to-spec` dispatch and the
report. The run writes the hierarchy into beads itself — you verify and report
what it wrote, you do not write it.

**Do not work out the repo span and do not pass one.** The span is an OUTPUT of
the run: `prd-to-spec` rules it after the architecture decision, from the design
that decision produced and from the repositories that actually exist. It cannot be
known before then — the span is a property of work no repository contains yet.

The second argument is an override for the case where a human has already decided
the span and wants this one run pinned to it. Pass it only when the invoker named
it. It is an argument, never a setting: nothing stores it, and the next run without
it is scoped afresh, which is what stops a re-run after an adjustment inheriting a
span computed before the adjustment.

Do not re-implement any of that here. If it needs to change, change it there so
both doors change together.
