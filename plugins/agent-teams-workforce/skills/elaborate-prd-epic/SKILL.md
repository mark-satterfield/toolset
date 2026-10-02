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

The pipeline elaborates an Epic and reads the PRD linked to it; the two are created
together. Everything below is identical whichever command you came from: both resolved
the Epic and its linked PRD before you got here.

Nothing here decomposes the Epic. The **file** side decomposes — PRD to TRD to
Spec — and the beads are what that chain deposits: one Story per Spec, Tasks per
Spec. The Epic is the container they land under.

## Precondition

You are here because a person invoked a pipeline. The existence of a PRD, an Epic,
or a paired both is **not** a request to build. Do not run this because you found
an Epic with no Stories.

You must arrive with:

- `prd` — `{id, title, body}`, the PRD linked to the Epic.
- `epic` — the Epic bead, with its `id`.

If either is missing, stop and report which one.

## The Epic lifecycle belongs to `prd-to-spec`

Do not check the Epic's readiness here. `prd-to-spec` owns the Epic's elaboration
lifecycle, and its first phase checks the Epic for every door into elaboration. It
refuses, with `stage: epic-lifecycle` and a `refusal` naming the code, when:

| Code | Meaning | What unblocks it |
| --- | --- | --- |
| `no-epic` | `epic.id` names no bead | Create the Epic, then assess and score it |
| `not-an-open-epic` | the id is not an open Epic | Pass the right Epic |
| `epic-unscored` | no `wsjf_ubv`, `wsjf_tc` or `wsjf` | Run the `dependency-assessment` and `wsjf-scoring` workflows for it |
| `upstream-not-elaborated` | an Epic it depends on is not `elaboration_state=done` | Elaborate that Epic first |
| `epic-authoring` | no `elaboration_state` | Set `elaboration_state=ready` when the PRD is finished |
| `epic-done` | already `done` | A person sets it to `in_progress` to elaborate again; the run resumes from its persisted artifacts |
| `epic-owned` | `in_progress` under another run's owner token | Pass `reclaim: true` only once that run is known not to be live |

Report a refusal verbatim and stop. Otherwise the run marks the Epic `in_progress`, and
when its Tasks are written it scores the Epic and its Tasks and sets the Epic's
`elaboration_state` to `done`. The Epic stays open until its work is released.

## 1. Do NOT determine the repo span

A PRD is a requirement. It is not scoped to a repository and it may span several. A
Spec and its Story are scoped to exactly one, and `prd-to-spec` runs spec authoring
once per repo — but **the span is decided inside the run, not by you.** Its
`repo-scoping` phase has the `polyrepo-steward` map the work onto the repositories that
exist, and create any repository the work needs that the project does not have.

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
- `createdRepos` — repositories the `polyrepo-steward` created for this work during the
  run. Report each one. When the shaper returns nothing, the steward returns no placement,
  or the placements name no repository, the run fails at `repo-scoping` with that reason.

## 2. Dispatch

```bash
echo "ROOT=${CLAUDE_PLUGIN_ROOT}"
```

```
Workflow({scriptPath: "$ROOT/workflows/prd-to-spec.js", args: {
  prd:      {id, title, body, repoPath},
  epic:     {id, title, description},   <the Epic bead; REQUIRED>
  repoPath: "/path/to/the/repo/you/are/standing/in",
  repos:    <OMIT — the run rules the span. Only when a human named it explicitly>,
  brd:      <OPTIONAL — BRD objectives text, only if one happens to exist>,
  archPath:       "$ATW_ARCH_PATH",
  projectRoot:    "$ATW_PROJECT_ROOT",
  artifactScript: "$ATW_ARTIFACT_SCRIPT",
  designSystem:   {packagesDir: "<host-configured packages directory>",
                   mocksDir:    "$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR",
                   shellsDir:   "$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR"}
}})
```

`designSystem.packagesDir` is the folder holding the mockups the owner supplied: zero or more single-artifact cds bundles, each a directory `<change-slug>-<timestamp>/` with its own `styles/`, `spec/build-spec.md`, `design/<kind>.html` and `bundle.json` (kind, slug, shell, created_at, build_spec). Of several bundles for the same kind and slug, the newest `created_at` is the supplied one. The detailing matches each `ui` item to a bundle or gives it no bundle. Each `ui` delta item, and each `web-ui` Task, takes one design source: `bundle` (a cds bundle the owner supplied packages the artifact it builds: the Spec cites the bundle's `spec/build-spec.md` and the build is audited against that bundle), `cds` (it changes design — layout, components, styles, visual states or a new screen — and no bundle is supplied: the implementing agent designs it with the CDS design system and the build is audited with `cds:audit-against-system` against the live design system) or `none` (it changes no design — copy, or data wired into an existing element: no cds design step and no cds audit).

`$ROOT` is the printed plugin root. The run resolves the root it runs its own scripts
under itself; pass none.

`archPath`, `projectRoot` and `artifactScript` are the project's configuration, read from the `ATW_*` environment (see
"Project configuration" in `AGENT-TEAMS-WORKFORCE.md`) and passed as expanded values; a
workflow script cannot read the environment itself. `ATW_ARCH_PATH` is required — the
architecture phase refuses without the architecture — so if it is unset, report
`ATW_ARCH_PATH is unset` and stop. Omit either of the other two when its variable is unset, and name it in
your report.

`designSystem` is optional. `packagesDir` is the host's packages directory; `mocksDir` and
`shellsDir` are the `CUSTOMIZABLE_DESIGN_SYSTEM_*` variables `cds:setup` defines, passed as
expanded values. Pass each one that has a value and omit the rest: an absent or empty packages
directory supplies no bundle, and every `ui` item then takes `cds` or `none`.

Use `scriptPath`, never a bare `name` — name dispatch resolves against the
session-start snapshot and the workflow dispatch guard refuses it.

No worktree. This phase authors documents and writes beads from the MAIN repo
path; it writes no code, so there is no feature branch for it to land on — and
`.beads` is never written from a worktree.

`brd` is entirely optional and most runs will not have one. Omitting it costs
nothing: it only skips an informational requirement-to-objective mapping. The PRD
is the top of the requirements chain — it never has to trace to, cite, or derive
from a BRD, and a run without one is in no way diminished.

## 3. Check what the run wrote — do NOT write it yourself

**The composite writes the hierarchy into beads itself**, each part in the step that
authors it: spec authoring writes each Story under the Epic, task decomposition writes
each Story's Tasks with their judged sizes and the `blocks` edges between them, and the
cross-Story step writes the `blocks` edges between Stories. Every write is keyed by the
durable `elab_key`, so a Story or Task that already exists is updated, never duplicated.
Writing any of it again yourself creates duplicates. The final step scores the Epic and
its Tasks and, when every part landed, sets the Epic's `elaboration_state` to `done`; the
Epic itself stays open.

What comes back:

- `hierarchy: {epic, stories, tasks}` — each Story and Task with the `id` and `elabKey`
  it was written under. A Task's `dependsOn` lists the Tasks it depends on.
- `crossStoryDependencies` — `{ran, reason, edges[], rejected[]}`: the Task edges that
  cross Stories, each typed and justified, and any proposed edge not applied.
- `lifecycle` — `{owner, start, finish, done}`: the start check, the scoring result for
  the Epic and its Tasks, and whether the Epic's elaboration is now `done`. When `done`
  is false the Epic's elaboration stays `in_progress` and the next run completes it.
- `beadsEmitted` — how many Stories and Tasks this run created or updated.

`depscore.py elaboration-finish` reads beads: when beads does not hold every Story, Task
and edge the span's saved documents name, it leaves the Epic `in_progress` and the run
returns `ok: false` at stage `hierarchy-not-persisted`, its `headline` naming what is
missing. Re-dispatch: the rerun replays every saved step, and each write updates what
landed and creates what did not.

Report `beadsEmitted` and `lifecycle.done` exactly as the composite returned them; never
compose them from your own account of what you think landed. `beadsEmitted` counts the
writes whose results were relayed; beads itself is what `lifecycle.done` was decided on.

## 4. Report

- Epic: its id, and whether `lifecycle.done` set its `elaboration_state` to `done`
- PRD: its path
- Repo span: the repositories `repoSpan` names, and whether the run ruled them or a
  human pinned them
- Repositories created: every `createdRepos` entry, with why no existing repo fits
- Stories: how many, and which repo each covers
- Tasks: how many, and how many dependency edges cross Stories
- Beads: `beadsEmitted`, and — when the run stopped at `hierarchy-not-persisted` —
  each missing Story, Task or edge the `headline` names
- A run that stopped — the composite's `headline` carries the phase and the reason; every
  phase artifact is in the run journal at `detailPath`, and the composite returns none of
  them. A stopped run names what it DID produce under `partialProduced` — read the journal
  before re-running, because a fresh run reproduces exactly that work.
- The exact next command: `/agent-teams-workforce:next-task`, which claims the
  highest-WSJF Task that is ready
