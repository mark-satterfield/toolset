---
name: elaborate-prd-epic
description: >-
  Run a PRD/Epic through the pipeline that produces the TRD, the Spec(s), and the
  Story and Task beads beneath it. Use after resolving a PRD/Epic pair from either
  end — a PRD document via /agent-teams-workforce:start-prd, or an Epic bead via
  /agent-teams-workforce:work-bead. Covers the repo span, the prd-to-spec dispatch,
  and writing the returned hierarchy into beads with bd.
allowed-tools: [Read, Write, Bash, Glob, Workflow]
---

# Elaborate a PRD/Epic

A PRD and its Epic are **one work item in two representations** — the PRD is the
human-readable face, the Epic is the tracker face. They are created together.
Everything below is identical whichever face you walked in holding; the only thing
that differs is how you resolved the pair, and that happened before you got here.

Nothing here decomposes the Epic. The **file** side decomposes — PRD to TRD to
Spec — and the beads are what that chain deposits: one Story per Spec, Tasks per
Spec. The Epic is the container they land under.

## Precondition

You are here because a person invoked a pipeline. The existence of a PRD, an Epic,
or a paired both is **not** a request to build. Do not run this because you found
an Epic with no Stories.

You must arrive with:

- `prd` — `{id, title, body}`. If only the Epic existed, its PRD was minted first.
- `epic` — the Epic bead, adopted not re-minted. If only the PRD existed, its Epic
  was minted first.

If either is missing, stop. Mint the missing half and return here — minting
completes the representation, it does not authorize the build.

## 1. Do NOT determine the repo span

A PRD is a requirement. It is not scoped to a repository and it may span several. A
Spec and its Story are scoped to exactly one, and `prd-to-spec` runs spec authoring
once per repo — but **the span is decided inside the run, not by you.** Its
`repo-scoping` phase surveys the repositories that exist and rules the span from the
architecture decision the same run produced.

So: **pass no `repos`.** Pass `repoPath` — the repository you are standing in — as a
starting point, and let the run rule the rest.

Pass `repos` only when a human has named the span explicitly (`/start-prd`'s second
argument), and only for that run. It is an override, not a setting: nothing stores it,
and a later run without it is scoped afresh. Deriving a span yourself and passing it is
the failure this phase exists to remove — it pins the answer to what you could see
before the architecture decision existed, and a re-run after an adjustment then
inherits it.

Two results come back that you must not bury:

- `repoSpan` — the repositories that were ruled. Report it.
- `newRepos` / `requiredHumanActions` — repositories the work needs that the project
  does not have. The run created nothing, and the work in them is specified nowhere.
  Surface each one; the fix is to create the repository through the `polyrepo-steward`
  and re-run.

## 2. Dispatch

```bash
ls -d ~/.claude/plugins/cache/mark-satterfield/agent-teams-workforce/*/ | sort -V | tail -1
```

```
Workflow({scriptPath: "$ROOT/workflows/prd-to-spec.js", args: {
  prd:      {id, title, body, repoPath},
  epic:     <the Epic bead — always pass it, so it is adopted rather than re-minted>,
  repoPath: "/path/to/the/repo/you/are/standing/in",
  repos:    <OMIT — the run rules the span. Only when a human named it explicitly>,
  brd:      <BRD objectives text, when there is one>,
  sadPath:  <arc42 SAD location, when known>
}})
```

Use `scriptPath`, never a bare `name` — name dispatch resolves against the
session-start snapshot and the workflow dispatch guard refuses it.

No worktree. This phase authors documents and returns bead specifications; it
writes no code, so there is no feature branch for it to land on.

Without `brd` the traceability audit has nothing to audit against and every
requirement reads as an orphan. Supply it when one exists; say so when it does not.

## 3. Write the hierarchy into beads

The composite returns `hierarchy: {epic, stories, tasks, storyDependencies}` and
does **not** touch `.beads`. Links are by local key (`E1`, `S1`), not bead id, so
write top-down and record each real id as you go:

1. The Epic already exists — record its real id against `epic.key`.
2. `bd create` each Story in `buildOrderIndex` order, parent = the Epic's real id
   (mapped from `parentEpicKey`). Record each id against its key.
3. Add Story dependencies: each Story's `dependsOn` names keys that must land
   first — translate them to ids.
4. `bd create` each Task, parent = its Story's real id (from `parentStoryId`).

Get step 2 or 4 wrong and every Task is parentless, which the router refuses to
work — correctly, because a Task with no Story has no Spec to build against.

## 4. Report

- Epic: adopted, or minted from the PRD
- PRD: located, or minted from the Epic
- Repo span: the repositories `repoSpan` names, and whether the run ruled them or a
  human pinned them
- Repositories still to create: every `newRepos` entry, with why no existing repo fits.
  Say plainly that their work is specified nowhere until they exist
- Stories: how many, and which repo each covers
- Tasks: how many, and the story-dependency edge count
- Any gate that blocked — the composite's `headline` carries the phase, the reason and
  the first unmet criterion; the full gate feedback and every phase artifact are in the
  run journal at `detailPath`. The composite no longer returns its phase artifacts: a
  single run came back truncated and a campaign of them killed the dispatching session.
  A blocked run also names what it DID produce under `partialProduced` — read the journal
  before re-running, because a fresh run reproduces exactly that work.
- The exact next command: `/agent-teams-workforce:work-bead <first task id>`
