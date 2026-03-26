# .agent-workspace-spec

Canonical template for the runtime workspace created by the orchestrator at
team formation. Domain-agnostic — used by any agent that invokes
/agent-team-workforce regardless of what it is building.

## Directory Map

```
.agent-workspace/{team-id}/
│
├── roster.json                        ← orchestrator writes at formation
│                                         schema: schemas/roster.schema.json
│
├── assignments/
│   └── {worker-id}.json              ← one per worker; orchestrator writes and updates
│                                         schema: schemas/assignment.schema.json
│
├── work/
│   └── {worker-id}/                  ← each worker's exclusive output directory
│       └── task-acknowledgment.md    ← worker writes on startup
│
├── proof/
│   └── {worker-id}/
│       ├── pow.json                  ← proof of work
│       │                                schema: schemas/proof-of-work.schema.json
│       ├── poc.json                  ← proof of completeness
│       │                                schema: schemas/proof-of-completeness.schema.json
│       └── peer-review/
│           └── {reviewer-id}.json   ← written by the reviewing worker
│
├── consensus/
│   └── round-{n}.json               ← orchestrator writes after each review round
│
├── orchestrator/
│   ├── checkpoint.json              ← orchestrator's ratification review
│   │                                    schema: schemas/orchestrator-checkpoint.schema.json
│   └── final-approval.json          ← written LAST; unblocks all workers
│
└── ralph-loop/
    └── {worker-id}.status           ← ORCHESTRATOR CONTROLS; workers READ ONLY
```

## Status File Values

```
INCOMPLETE          Worker has not submitted PoW+PoC
READY_FOR_REVIEW    Worker submitted proof; awaiting cross-review
IN_REVIEW           Worker is reviewing peers
IN_REMEDIATION      Peer or orchestrator returned issues; worker is iterating
APPROVED            Orchestrator ratified; worker may exit
```

## Write Permissions

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

## Initialization Script

```bash
TEAM_ID="$1"
shift
WORKSPACE=".agent-workspace/$TEAM_ID"

mkdir -p "$WORKSPACE"/{assignments,consensus,orchestrator,ralph-loop}

for WORKER_ID in "$@"; do
  mkdir -p "$WORKSPACE/work/$WORKER_ID"
  mkdir -p "$WORKSPACE/proof/$WORKER_ID/peer-review"
  echo "INCOMPLETE" > "$WORKSPACE/ralph-loop/$WORKER_ID.status"
done
```

## .gitignore

Add to project root `.gitignore`:

```
.agent-workspace/
```

The workspace is ephemeral audit trail, not source-controlled.
