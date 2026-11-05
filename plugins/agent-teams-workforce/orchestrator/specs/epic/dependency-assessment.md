# Manual dependency assessment

The owner invokes `bin/atw-portfolio dependency-assessment` through the supported plugin command. This manual portfolio operation is outside keeper Epic elaboration.

The implementation is `orchestrator/portfolio.py:assess`; external arguments follow `skills/pipeline-contracts/schemas/portfolio-command.schema.json`. Scope, repository and apply/propose flags are validated before tool calls.

Python directly calls depscore assess-plan and assess-context. One genuine epic-dependency-assessor session produces the shared epic-edge-proposal judgment. Python validates the accepted proposal, then calls apply-edges against the saved plan. Propose mode passes --dry-run. The existing edge validator and applier enforce scope, cycles, relations and current-graph checks.

Failed validation prevents apply. The result retains plan, accepted proposal path, validation and apply/diff evidence. No model session relays commands; this operation does not write architecture or matrix approval marks.
