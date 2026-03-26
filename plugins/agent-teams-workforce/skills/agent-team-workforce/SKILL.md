---
name: agent-team-workforce
description: >
  Parallel execution framework for agents that need sub-agents. The calling
  agent becomes the orchestrator and spawns workers of its own type. Workers
  do their assigned work, prove it with tests, cross-review each other's
  results, and must reach peer consensus before anyone is done. Domain-agnostic.
user_invocable: true
category: orchestration
tier: advanced
dependencies: []
author: mark-satterfield
version: 2.0.0
---

# Agent Team Workforce

When an agent needs parallel work, it becomes the orchestrator and spawns
workers **of its own type**. Every worker has the full skill set of the
calling agent — they are peers, not specialists.

The framework is domain-agnostic. It knows nothing about what the workers
are building. All domain knowledge lives in the agent that invokes it.

---

## How It Works

1. The calling agent (e.g., `web-artisan`) decides it needs parallel work
2. It becomes the **orchestrator**
3. It spawns N **workers** — each one is the same agent type as itself
4. Each worker gets a different assignment but has the full capability set
5. Workers do their work and prove it (tests, artifacts, evidence)
6. Workers **cross-review each other** — Worker A reviews Worker B and vice versa
7. Workers must **agree with each other** that the work is done
8. The orchestrator reads the peer verdicts, spot-checks, and ratifies
9. Nobody exits until consensus is reached

---

## Roles

There are only two roles. The calling agent is the orchestrator. Everyone
it spawns is a worker.

| Role | Who | Responsibility |
|------|-----|---------------|
| `orchestrator` | The calling agent | Forms team, writes assignments, reads peer verdicts, ratifies consensus, handles integration |
| `worker` | Spawned instances of the same agent type | Does assigned work, produces proof, reviews other workers' output, participates in consensus |

Workers are both doers and reviewers. There is no separate reviewer role.
If the team has an odd number of workers or needs a dedicated verifier,
the orchestrator may spawn an additional worker whose only assignment is
cross-review — but it is still the same agent type.

---

## Integration

Add a block like this to any agent definition that needs parallel work:

```markdown
## Parallel Work

When this task requires parallel execution, invoke /agent-team-workforce.
You are the orchestrator. Spawn workers of your own type. Each worker has
all of your skills and capabilities — assign them different pieces of the
work, not different roles.
```

That's it. The framework handles the rest.

### Examples of agent integration

A **web designer agent** building a multi-screen site:
```
Workers: layout, content hierarchy, interactive states, token application
Each worker is a full web-designer instance assigned to one concern.
```

A **backend agent** building a new service:
```
Workers: API endpoints, data layer, integration tests
Each worker is a full backend instance assigned to one layer.
```

A **QA agent** running a comprehensive audit:
```
Workers: accessibility audit, performance audit, security audit
Each worker is a full QA instance assigned to one audit type.
```

---

## Execution Protocol

### Phase 1 — Team Formation (Orchestrator)

1. Write `roster.json` — team membership and cross-review assignments
2. Write one `assignments/{worker-id}.json` per worker
3. Create workspace directories (see Workspace Layout)
4. Set all `ralph-loop/{worker-id}.status` to `INCOMPLETE`
5. Build the **worker prompt payload**

   Claude Code's Agent tool spawns fresh subprocesses — they get only what
   is in the `prompt` parameter. Workers will not automatically inherit
   the orchestrator's skills, context, or agent definition. The
   orchestrator must assemble a prompt payload that includes:

   a. **Agent identity** — the full agent definition the orchestrator is
      running as (e.g., the entire web-artisan prompt). This makes the
      worker the same agent type in practice, not just in name.

   b. **Mandatory reads** — any files the agent definition requires
      reading before work begins. The orchestrator reads these files and
      embeds their content (or the critical sections) directly into the
      prompt. Workers cannot be trusted to read the right files unprompted.

   c. **Skill content** — any skills listed as mandatory in the agent
      definition. The orchestrator reads each SKILL.md and embeds the
      content. Workers do not have access to the Skill tool's invocation
      context.

   d. **The worker's assignment** — path to `assignments/{worker-id}.json`
      in the workspace, plus instructions to read it on startup.

   e. **The workspace protocol** — this skill's execution protocol
      (Phases 2–4), workspace layout, write permissions, proof schemas,
      and ralph-loop rules. Embed or reference the full SKILL.md.

   f. **Coordination state** — path to `roster.json` and the workspace
      root so the worker can orient itself.

   The orchestrator writes `orchestrator/worker-prompt-template.md` as the
   base payload, then customizes per worker by appending the assignment
   reference. This template is an auditable artifact — reviewers can verify
   that workers were properly equipped.

6. Spawn workers using the Agent tool. Each spawn call uses:
   - `prompt`: the worker prompt payload from step 5, with the
     worker-specific assignment appended
   - `subagent_type`: the same agent type as the orchestrator
   - `run_in_background: true`

   The orchestrator MUST NOT proceed to integration or other work after
   spawning. It waits for workers to reach consensus.

### Phase 2 — Parallel Work (Workers)

Each worker, independently and concurrently:

1. Read `roster.json` — confirm membership and review assignments
2. Read `assignments/{self-id}.json` — understand the task
3. Write `work/{self-id}/task-acknowledgment.md` — confirm understanding
4. Execute the task
5. Produce evidence that the work is done (tests, verification output)
6. Write `proof/{self-id}/pow.json` — what was produced, with hashes
7. Write `proof/{self-id}/poc.json` — how each requirement was satisfied
8. Set `ralph-loop/{self-id}.status` → `READY_FOR_REVIEW`
9. Wait for cross-review phase

### Phase 3 — Cross-Review (Workers review each other)

Once all workers reach `READY_FOR_REVIEW`, each worker reviews its
assigned peers:

1. Read the peer's `assignments/{peer-id}.json` — the original spec
2. Read every file in `work/{peer-id}/`
3. Run or inspect the peer's tests and evidence
4. Verify claims in `proof/{peer-id}/pow.json` — do the artifacts exist? do hashes match?
5. Verify claims in `proof/{peer-id}/poc.json` — does the work actually satisfy the requirements?
6. Write `proof/{peer-id}/peer-review/{self-id}.json` with verdict: `PASS`, `FAIL`, or `PASS_WITH_NOTES`
7. If `FAIL`: explain exactly what is wrong and what needs to change

### Phase 4 — Peer Consensus

Consensus is achieved when:
- Every worker has been reviewed by at least one other worker
- All peer reviews are `PASS` or `PASS_WITH_NOTES` — zero `FAIL` verdicts
- Workers who received `PASS_WITH_NOTES` acknowledge the notes

If any worker receives a `FAIL`:
- That worker reads the review, fixes the issues, re-submits proof
- The reviewing worker re-reviews
- This continues until the reviewer is satisfied

Write `consensus/round-{n}.json` after each review round.

### Phase 5 — Orchestrator Ratification

The orchestrator does NOT redo all the work. It:

1. Reads all peer review verdicts
2. Spot-checks a sample of artifacts and claims
3. Verifies that consensus was genuinely reached (not rubber-stamped)
4. Writes `orchestrator/checkpoint.json`
5. If satisfied: writes `orchestrator/final-approval.json`
6. Sets all `ralph-loop/{id}.status` → `APPROVED`

If the orchestrator disagrees with the peer consensus:
- Writes remediation instructions to the relevant `assignments/{id}.json`
- Sets `ralph-loop/{id}.status` → `IN_REMEDIATION`
- Workers iterate and re-submit

### Phase 6 — Integration

After all workers are `APPROVED`, the orchestrator assembles the final
output from the workers' artifacts. No separate integrator agent needed.

---

## Proof of Work

Every worker writes `proof/{self-id}/pow.json` before signaling readiness.

Required fields:
- `workerId`, `teamId`, `taskRef` — identity and linkage
- `completedAt`, `iterationCount` — timing and ralph-loop context
- `artifacts` — every file written, with path, description, and content hash
- `testResults` — tests run and their pass/fail status
- `externalRefs` — any external resource created or modified
- `toolCallSummary` — counts by category

A worker that lists artifacts which do not exist or do not match the
claimed hash receives an automatic `FAIL` from any reviewer.

Full schema: `schemas/proof-of-work.schema.json`

---

## Proof of Completeness

Every worker writes `proof/{self-id}/poc.json` before signaling readiness.

Required fields:
- Every requirement from `assignments/{self-id}.json` — listed explicitly, none omitted
- `status` per requirement: `complete | partial | deferred | out-of-scope | blocked`
- `satisfiedBy` — artifact paths, test results, or external refs that satisfy each requirement
- `coverageSummary` — aggregate counts

Reviewers verify each claim against the original assignment and the
actual artifacts — not against the worker's self-assessment.

Full schema: `schemas/proof-of-completeness.schema.json`

---

## Workspace Layout

The orchestrator creates `.agent-workspace/{team-id}/` at team formation.

```
.agent-workspace/{team-id}/
  roster.json
  assignments/
    {worker-id}.json           ← written by orchestrator; updated on remediation
  work/
    {worker-id}/               ← worker writes here only
      task-acknowledgment.md
  proof/
    {worker-id}/
      pow.json                 ← proof of work
      poc.json                 ← proof of completeness
      peer-review/
        {reviewer-id}.json     ← written by reviewing worker
  consensus/
    round-{n}.json
  orchestrator/
    worker-prompt-template.md  ← base prompt payload for spawning workers
    checkpoint.json            ← orchestrator's ratification review
    final-approval.json        ← written last; unblocks all workers
  ralph-loop/
    {worker-id}.status         ← orchestrator controls; workers read only
```

### Write Permissions

| Path | Written by |
|------|-----------|
| `roster.json` | Orchestrator only |
| `assignments/{id}.json` | Orchestrator only |
| `work/{id}/` | That worker only |
| `proof/{id}/pow.json` | That worker only |
| `proof/{id}/poc.json` | That worker only |
| `proof/{id}/peer-review/{reviewer-id}.json` | The reviewing worker only |
| `consensus/round-{n}.json` | Orchestrator only |
| `orchestrator/` | Orchestrator only |
| `ralph-loop/{id}.status` | Orchestrator only |

No worker may write outside its own directory. No worker may approve its
own work. No worker may set its own ralph-loop status to `APPROVED`.

---

## Ralph-Loop Protocol

The ralph-loop prevents workers from exiting before the work is truly done.

### Status Values

| Value | Meaning |
|-------|---------|
| `INCOMPLETE` | Worker has not yet submitted proof |
| `READY_FOR_REVIEW` | Worker submitted PoW+PoC; awaiting cross-review |
| `IN_REVIEW` | Worker is reviewing peers |
| `IN_REMEDIATION` | Peer or orchestrator returned issues; worker is iterating |
| `APPROVED` | Orchestrator ratified; worker may exit |

### Rules

- A worker MUST NOT exit while its status is anything other than `APPROVED`
- Only the orchestrator sets `APPROVED`
- The orchestrator sets `APPROVED` only after writing `final-approval.json`
- If a worker attempts to exit without `APPROVED`, it re-enters the work loop

---

## Escalation

| Condition | Action |
|-----------|--------|
| Worker exceeds `maxIterations` without progress | Terminated; task reassigned to new worker |
| Same requirement fails 3 consecutive peer reviews | Escalate to user |
| Artifact listed in PoW does not exist | Automatic `FAIL` |
| PoC references nonexistent artifact | Automatic `FAIL` |
| Consensus not reached after 5 rounds | Block and escalate to user |

---

## Schema References

All schemas live in `schemas/` (relative to this skill directory):

```
schemas/roster.schema.json
schemas/assignment.schema.json
schemas/proof-of-work.schema.json
schemas/proof-of-completeness.schema.json
schemas/peer-review.schema.json
schemas/consensus-round.schema.json
schemas/orchestrator-checkpoint.schema.json
schemas/final-approval.schema.json
```
