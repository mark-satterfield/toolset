# agent-team-workforce

Parallel execution framework for agents that need sub-agents. The calling
agent becomes the orchestrator and spawns workers of its own type. Workers
cross-review each other and must reach peer consensus before anyone is done.

Domain-agnostic. No knowledge of what workers are building. All domain
knowledge lives in the agent that invokes it.

---

## Location

```
plugins/agent-teams-workforce/skills/agent-team-workforce/
  SKILL.md
  README.md
  
  schemas/
    roster.schema.json
    assignment.schema.json
    proof-of-work.schema.json
    proof-of-completeness.schema.json
    orchestrator-checkpoint.schema.json
  
  .agent-workspace-spec/
    README.md
```

---

## How to Use

Add this to any agent definition that needs parallel work:

```markdown
## Parallel Work

When this task requires parallel execution, invoke /agent-team-workforce.
You are the orchestrator. Spawn workers of your own type. Each worker has
all of your skills and capabilities — assign them different pieces of the
work, not different roles.
```

---

## Key Concepts

- **Homogeneous workers**: Workers are the same agent type as the caller
- **Cross-review**: Workers review each other's output — no separate reviewer role
- **Peer consensus**: Workers must agree the work is done before anyone exits
- **Orchestrator ratification**: The calling agent spot-checks and ratifies peer consensus
- **Proof of work**: Every worker produces evidence (tests, artifacts with hashes)
- **Ralph-loop**: Workers cannot exit until the orchestrator sets their status to `APPROVED`

---

## Runtime Workspace

Created by the orchestrator at team formation. Not committed to git.

```
.agent-workspace/{team-id}/
  roster.json
  assignments/
  work/
  proof/
  consensus/
  orchestrator/
  ralph-loop/
```

Add to `.gitignore`:

```
.agent-workspace/
```
