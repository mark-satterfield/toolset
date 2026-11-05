# Manual WSJF scoring

The owner invokes `bin/atw-portfolio wsjf-scoring` through the supported plugin command. This manual portfolio operation is outside keeper Epic elaboration.

The implementation is `orchestrator/portfolio.py`; external arguments follow `skills/pipeline-contracts/schemas/portfolio-command.schema.json`. Explicit boolean and scope validation precedes tool calls. Python directly runs existing score-plan, judge-input, record and score operations.

Each planned Epic or Task group receives one genuine wsjf-scorer session with only that job's items/group and common reference jobs. Concurrency uses the orchestrator's configured session limit. The shared judgment schema and exact coverage validation require exactly one score or unscored disposition per assigned ID, without duplicates or cross-group items.

Candidates are separate from accepted judgments. Only validated outputs enter the judgment directory passed to record. Ordinary individual session failures leave those IDs unjudged while successful groups can be recorded; account/shutdown failures stop the operation. Existing depscore planning and recording enforce partial results and scope checks.

Dry-run preserves proposal behavior; all/rejudge retain explicit command semantics. Results include recording/scoring evidence and failed job IDs. No model session relays commands or approves architecture.
