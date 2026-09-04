---
name: elaborate-prd-epic
description: >-
  Run a PRD/Epic through the pipeline that produces the TRD, the Spec(s), and the
  Story and Task beads beneath it. Use after resolving a PRD/Epic pair from either
  end — a PRD document via /agent-teams-workforce:start-prd, or an Epic bead via
  /agent-teams-workforce:work-bead. Covers the repo span, the prd-to-spec dispatch,
  and checking what the run itself wrote into beads.
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

No worktree. This phase authors documents and writes beads from the MAIN repo
path; it writes no code, so there is no feature branch for it to land on — and
`.beads` is never written from a worktree.

Without `brd` the traceability audit has nothing to audit against and every
requirement reads as an orphan. Supply it when one exists; say so when it does not.

## 3. Check what the run wrote — do NOT write it yourself

**The composite writes the hierarchy into beads itself.** Its Emit Beads phase
creates the Epic, then the Stories under the Epic's real id, then each Story's
Tasks under their own Story's real id, then the dependency edges — parent before
child, ordered by the script, with a child of an unwritten parent never attempted.
Writing any of it again creates duplicates.

What comes back:

- `hierarchy: {epic, stories, tasks, storyDependencies}` — the same tree, with each
  node now carrying the real `id` it was written under.
- `emissionOk` — true only when every bead and every edge landed.
- `beadsEmitted` — how many beads this run actually created.
- `emission` — `{verdict, target, created, adopted, failed[], skipped[], links, heal}`.
  `verdict` is `complete`, `partial`, or `none`.
- `emission.heal` — the BACKFILL REPAIR, reported separately from the verdict.
  A Task that reached the build lane with no Story got a stand-in roll-up Story minted
  for it on the side. Once this run authors the Spec-backed Story that work belongs
  under, the stand-in is a Story under the same Epic saying nothing — so the run
  re-parents its Tasks onto a real Story and closes it. `{ran, reason, wrappers,
  reparented, closed, failed[]}`. It runs only for an Epic that already existed, and it
  can fail without changing `verdict` or `emissionOk`: retiring another run's stand-in
  is housekeeping, and a failed repair must never make a durable hierarchy report as
  partial. Report `closed` / `reparented` when they are non-zero, and every entry of
  `heal.failed` — a stand-in left open is a duplicate Story on the board.

Act on the verdict:

- **complete** — nothing to do. Report the ids.
- **partial** — some beads did not land, and `emission.failed` / `emission.skipped`
  name every one with its reason. The hierarchy is returned in full, so the
  remainder can be written with `bd` without re-running the pipeline: create each
  named node under the real parent id already recorded on the tree, parent before
  child. A `skipped` node was not attempted because its parent is missing — write
  the parent first or the child is an orphan the router refuses to work.
- **none** — the run comes back `ok: false` at stage `emit-beads`. Nothing is durable
  and nothing was lost: read `emission.reason`, fix the cause (usually the repository
  path or the tracker itself), and write the returned hierarchy or re-dispatch.

Report `emissionOk` and `beadsEmitted` exactly as the composite returned them. They
are measured by the step that did the writing; never compose them from your own
account of what you think landed.

## 4. Report

- Epic: adopted, or minted from the PRD
- PRD: located, or minted from the Epic
- Repo span: the repositories `repoSpan` names, and whether the run ruled them or a
  human pinned them
- Repositories still to create: every `newRepos` entry, with why no existing repo fits.
  Say plainly that their work is specified nowhere until they exist
- Stories: how many, and which repo each covers
- Tasks: how many, and the story-dependency edge count
- Emission: `emission.verdict`, `beadsEmitted`, and — when the verdict is not
  `complete` — every node in `emission.failed` and `emission.skipped` and what
  still has to be written
- Backfill repair: `emission.heal.closed` / `.reparented` when either is non-zero, and
  every `heal.failed` entry — each one is a stand-in roll-up Story still sitting on the
  board beside the real one
- Any gate that blocked — the composite's `headline` carries the phase, the reason and
  the first unmet criterion; the full gate feedback and every phase artifact are in the
  run journal at `detailPath`. The composite no longer returns its phase artifacts: a
  single run came back truncated and a campaign of them killed the dispatching session.
  A blocked run also names what it DID produce under `partialProduced` — read the journal
  before re-running, because a fresh run reproduces exactly that work.
- The exact next command: `/agent-teams-workforce:work-bead <first task id>`
