---
description: "Start a PRD at the top of the pipeline — Epic, TRD, Spec+Story per repo, Tasks"
argument-hint: "<prd-path-or-title> [repo,repo,...]"
allowed-tools: [Bash, Read, Glob, Workflow]
---

# Start a PRD

Take `$ARGUMENTS` from a PRD document to an emitted Epic → Story → Task hierarchy.

This is the entry point the bead router cannot provide: a PRD is a **file**, so
`bd ready` never returns one and `route-bead` never sees it. Everything downstream
of here is bead-driven; this step is what creates the beads.

## 1. Locate the PRD

The first argument is a path or a title. If it is a title, search the product docs:

```bash
ls ~/projects/SkillSpoke/skillspoke-docs/docs/product/
```

Prefer `obsidian-cli` (vault `skillspoke-docs`) when Obsidian is running; if it is
not, do not wait — the vault is a plain git repo of markdown, so read it off disk.

Read the PRD. Extract `title` and `body`. Stop and report if you cannot find it —
do not invent a PRD from the title.

## 2. Decide the repo span

A Story is scoped to one repo, so `prd-to-spec` runs spec authoring once per repo
and the span has to be known before it starts.

- Second argument given → use it, comma-separated.
- Not given → derive candidates from the PRD: which services does it name? Check
  them against the actual repos on disk. State what you derived and what you are
  running with.
- Genuinely single-service → one repo. That is the common case; do not inflate it.

Getting this wrong is recoverable but wasteful: a missing repo means a Story that
never existed, and re-running costs the whole front-end.

## 3. Check for an existing Epic

```bash
bd list --type epic | grep -i "<prd title>"
```

- Found → pass it as `epic` so it is adopted rather than duplicated.
- Not found → pass nothing. `prd-to-spec` backfills one from the validated PRD.
  Most PRDs here predate the hierarchy, so backfill is the normal path.

## 4. Dispatch

```bash
ls -d ~/.claude/plugins/cache/mark-satterfield/agent-teams-workforce/*/ | sort -V | tail -1
```

```
Workflow({scriptPath: "$ROOT/workflows/prd-to-spec.js", args: {
  prd:      {id, title, body, repoPath},
  repos:    ["/path/to/repo-a", "/path/to/repo-b"],
  repoPath: "/path/to/repo-a",
  epic:     <only when step 3 found one>,
  brd:      <BRD objectives text, when there is one>,
  sadPath:  <arc42 SAD location, when known>
}})
```

`scriptPath`, never a bare `name` — name dispatch resolves against the
session-start snapshot and is refused by the workflow dispatch guard.

Without `brd` the traceability audit has nothing to audit against and every
requirement reads as an orphan. Supply it when one exists; note its absence when
it does not.

## 5. Write the hierarchy into beads

The composite returns `hierarchy: {epic, stories, tasks, storyDependencies}` and
does **not** touch `.beads`. Links are by local key (`E1`, `S1`), not bead id, so
write top-down and record each real id as you go:

1. `bd create` the Epic. Record its id against `epic.key`.
2. `bd create` each Story in `buildOrderIndex` order, parent = the Epic's real id
   (mapped from `parentEpicKey`). Record each id against its key.
3. Add Story dependencies: each Story's `dependsOn` lists keys that must land
   first — translate to ids.
4. `bd create` each Task, parent = its Story's real id (from `parentStoryId`).

Get step 2 or 4 wrong and every Task is parentless, which `route-bead` will refuse
to work — correctly, because a Task with no Story has no Spec to build against.

## 6. Report

- Epic: created or backfilled or adopted
- Stories: how many, and which repo each covers
- Tasks: how many, and the story-dependency edge count
- Any gate that blocked, with its feedback verbatim
- The exact next command: `/agent-teams-workforce:work-bead <first task id>`
