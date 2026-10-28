---
description: "Route one bead and report where its pipeline stands: the next step of its step journal"
argument-hint: "<bead-id>"
allowed-tools: [Bash, Read, Workflow]
---

# Work a bead

Route `$ARGUMENTS` through the router that owns its kind, then report where its pipeline stands.
This command dispatches no pipeline. The pipeline's driver runs every build, deploy and
elaboration: it opens the bead's step journal, starts the run, and writes each step's result to
the journal while the run works. Do not implement anything yourself and do not hand-roll a step.

## 1. Resolve the bead

```bash
atw-bd show $ARGUMENTS --json || atw-bd show $ARGUMENTS
```

Pull out `id`, `title`, `description`, `type`, `labels`, and the parent chain.

## 2. Resolve the installed plugin root

```bash
echo "ROOT=${CLAUDE_PLUGIN_ROOT}"
```

Call the printed path `$ROOT`. Every dispatch below uses `scriptPath`, never a bare `name` —
name dispatch resolves against the session-start snapshot and is refused by the
workflow dispatch guard.

## 3. Route it

There are two routers, split by the kind of work. Pick by the bead's type — do not
guess, and do not send a bead to both.

**Task or Infra — DEVELOPMENT work:**

```
Workflow({scriptPath: "$ROOT/workflows/route-build.js",
  args: {bead: {id, type, labels, title, description,
                parentType, ancestorTypes},
         infraVocabulary}})
```

`infraVocabulary` is the JSON object printed by
`python3 $ROOT/skills/artifact-handoff/scripts/infra_vocabulary.py`, passed as it stands.

Supply `parentType` and `ancestorTypes` from the parent chain. A Task is routed to
`task-to-deploy` (which adds its infrastructure step for an infrastructure Task) with or without
them; they only change the router's `reason`.

**Epic, Story, or Feature — ELABORATION work:**

```
Workflow({scriptPath: "$ROOT/workflows/route-elaboration.js",
  args: {bead: {id, type, labels, title, description,
                parentType, parentId, ancestorTypes},
         infraVocabulary}})
```

`infraVocabulary` is the same object passed to `route-build.js`.

**Bug — neither.** A bug is a reporting mechanism, not work. It is TRIAGED by a
person into an Epic, a Task, or a closure. Both routers skip it, naming triage;
there is no triage composite to dispatch. Hand a bug to `route-build.js` and
report the skip.

Do **not** pass `childCount`. Neither router reads it.

The router returns `{action, composite, reason}`:

| action | What to do |
| --- | --- |
| `work` | **Go to step 4** with the Task. Nothing is dispatched from here: the pipeline's driver runs the build. |
| `elaborate` | **Go to step 4** with the Epic. Nothing is dispatched from here: the pipeline's driver runs elaboration. |
| `skip` | **Stop.** Report the id and the reason. |

A skip is an outcome, not an obstacle. Never relabel a bead to make it routable —
a skip's reason names what the bead needs, and a new label is never it.

## 4. Where the bead's pipeline stands

A Task is built by `task-to-deploy`, a workflow script the driver dispatches with the Task's
step journal. An Epic is elaborated by `prd-to-spec`, which runs in the Python orchestrator
(`$ROOT/orchestrator/run.py`) and which the driver starts. A Story is elaborated through its
parent Epic and deployed by the driver once its last Task is done: for a Story, report both its
own journal and its parent Epic's. A Story with no parent Epic, and a feature: report the
router's reason and stop.

One dispatch is one pass over the bead's step journal; it begins at the first step the journal
does not mark done. Print that step:

```bash
atw-step-journal next --dir "$ATW_CONTROL_REPO/.claude/workflow-runs/step-journals" --bead <bead id>
```

`ATW_CONTROL_REPO` is the `CONTROL_REPO_ENV` variable of the `pipeline-contracts` skill
(`$ROOT/skills/pipeline-contracts/schemas/driver-surface.schema.json`, `$defs.DriverEnvironment`);
if it is unset, report `ATW_CONTROL_REPO is unset` and stop. When the command reports that it
cannot read the journal file, the bead has no step journal yet: report that. A step whose
status is `failed` carries its cause in `failure`; report it verbatim.

For an Epic, read its elaboration state with
`python3 "$ROOT/skills/beads-contract/scripts/beads-contract.py" metadata get <epic id>`.

Write nothing: the run writes the journal, the Stories, the Tasks and their edges itself.

## 5. Report

One line each, no more:

- which composite owns the bead, and why the router chose it
- that the pipeline's driver runs it and this command dispatched nothing
- the step the bead's journal names next, with its status, and the cause of a failed step
- for an Epic, its elaboration state
- what you did NOT do
