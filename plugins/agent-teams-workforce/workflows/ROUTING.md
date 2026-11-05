# Pipeline routing

The control repository's Python routing classifies beads deterministically. A Task must have
its Story and Epic ancestry and repository context before the build dispatch. Infrastructure
Tasks use the same Python build and add concrete infrastructure intent. Bugs are reporting
records and are not directly implemented by a separate bug pipeline.

The owner starts keeper; keeper and supervisor dispatch Python composites through
`orchestrator/run.py`. Epic elaboration is `prd-to-spec`; Task build is `task-to-deploy`.
A Story's deploy is owned by the Python driver and uses the Python `deploy-mechanism`,
`story-deploy-fix` and `built-version` leaves within its existing journal.

Routing, subprocess execution, artifact acceptance, exit-code handling and arithmetic require
no model session. Real specialist reasoning remains agent work. The composite vocabulary and
phase names live in `skills/pipeline-contracts/schemas/composites.json`; step keys, ordering and
artifacts live in its `pipeline-steps.json`.

The supported owner commands `dependency-assessment` and `wsjf-scoring` use `bin/atw-portfolio`.
They are separate from keeper dispatch. The independent adversarial and gate judgment
workflows are not called by the Python build/deploy pipelines.
