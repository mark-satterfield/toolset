# Unattended-mode routing policy

How `/loop` drains the ready queue: each tick claims the next ready bead, asks
[`route-bead`](route-bead.js) which composite owns it, runs that composite, reports,
and moves on. This file is the human-readable policy; `route-bead.js` is its
executable form. Keep them in sync — edit both when the policy changes.

## The four composites

| Composite | Front-end | For |
|---|---|---|
| `prd-to-spec` | prd-validation → architecture → spec-authoring → task-decomposition | a NEW feature with no implementation-ready contract yet |
| `spec-to-deploy` | spec-freshness → red → green → refactor → integration → adversarial → deploy | work whose spec/contract already exists and is implementation-ready |
| `bug-fix` | bug-triage → shared tail | a defect/regression in existing behavior |
| `infra-change` | infra-intent → shared tail (subset) | an infrastructure/provisioning change (CDK/IaC, AWS resources, deploy plumbing) |

## Type / label → composite

Routing is **deterministic first**: `route-bead` decides from `bead.type` and
`bead.labels` alone, with no agent in the loop. The **first matching rule wins**, so
the table is ordered. Labels can override the base type — an explicitly-labelled
bead is never mis-typed.

| # | Condition (type, or any label) | Composite |
|---|---|---|
| 1 | type `bug`; or label `bug` / `defect` / `regression` / `hotfix` | `bug-fix` |
| 2 | type `infra` / `infrastructure`; or label `infra` / `infrastructure` / `cdk` / `iac` / `provisioning` | `infra-change` |
| 3 | label `spec` / `spec-ready` / `implementation` / `implement` / `spec-to-deploy` | `spec-to-deploy` |
| 4 | type `feature` / `epic` / `story`; or label `feature` / `prd` / `requirement` / `prd-to-spec` | `prd-to-spec` |
| 5 | type `chore` / `docs` / `task` / `research` / `spike` | **SKIP** |
| 6 | anything else (unknown / unlabelled) | ambiguity classification, else **SKIP** |

Notes on order:

- **Bug and infra are checked before feature.** A bead can carry both a base
  `feature` type and a `bug`/`infra` label; the more specific kind wins.
- **Spec-ready (rule 3) is checked before feature (rule 4)** on purpose. A
  feature that *already* has an implementation-ready spec skips WF1 re-derivation
  and goes straight to the build-and-ship tail. Without a `spec*`/`implementation`
  label, a feature falls through to rule 4 and runs WF1 first.

### Ambiguity (rule 6)

When type and labels match nothing, the router does **not** guess. By policy it
SKIPs. Only when `allowAmbiguityAgent` is on (the default) does it ask the
read-only `ambiguity-detector` to classify from the title and description. That
agent authors nothing and never runs the composite — it only returns a pick and a
confidence. The router applies the verdict defensively:

- a **confident pick of one of the four composites** is dispatched;
- **`skip`, low confidence, or any unexpected value** is a reported SKIP.

Set `allowAmbiguityAgent: false` to force a deterministic-only pass — genuinely
ambiguous beads then SKIP without spawning an agent.

## What `/loop` skips — and that skips are reported, never force-fit

A SKIP is a `null` composite from `route-bead`, carrying a `reason`. `/loop`
**reports every skip** (bead id + reason) and moves to the next ready bead. It
does **not** force an unmatched bead into the nearest-looking composite — a
mis-route costs more than a skip. Beads are skipped when they are:

- an **out-of-pipeline kind** — `chore`, `docs`, `task`, `research`, `spike`
  (rule 5). These are real work, just not work this pipeline automates.
- **unclassifiable** — type/labels match nothing and the ambiguity agent could
  not confidently route them (rule 6).

A skipped bead is left in the ready queue (its status is untouched). The operator
sees the reported reason and decides: relabel it so it routes, handle it manually,
or leave it. Routing is **advisory triage**, not a state mutation — `route-bead`
reads a bead and returns a decision; it never closes, claims, or relabels.

To make a skipped bead route, give it a type/label from the table above — e.g.
add a `bug` label to a defect filed as a plain `task`, or a `spec-ready` label to
a feature whose contract already exists.

## How `/loop` self-paces — "until `bd ready` is empty"

`/loop` runs **self-paced** (no fixed interval): it works as fast as each
composite completes and stops on a queue condition, not a clock. One tick:

1. **Check the queue.** Run `bd ready`. If it is empty, **stop** — the loop is done.
2. **Claim the next bead.** Take the top ready bead and mark it in-progress
   (`bd update --status` / claim), so a second runner can't grab the same bead.
3. **Route it.** Call `route-bead` with `{ bead }`.
   - composite is non-null → run that composite on-demand
     (`Workflow({ name: <composite>, args: { bead } })`).
   - composite is null → **report the skip** (id + reason) and leave the bead's
     status as it was.
4. **Report the outcome** — composite result, or the skip reason.
5. **Loop.** Go back to step 1.

The terminating condition is **`bd ready` empty**, not a tick count. Skipped beads
do not block the loop (they're reported and stepped over), and they do not falsely
empty the queue (their status is untouched, so they remain visible to the
operator). The loop ends only when no claimable, routable work remains.

### Both run modes use the same composites

- **On-demand:** `Workflow({ name: 'bug-fix', args: { bead } })` (etc.) for a
  chosen bead — the operator picks the composite.
- **Unattended:** `/loop` self-paces over `bd ready`, using `route-bead` to pick
  the composite per bead. Same composites, same minis — only the selection differs.
