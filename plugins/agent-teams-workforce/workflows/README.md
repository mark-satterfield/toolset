# agent-teams-workforce — workflow scripts

These are the **canonical source** for the agent-teams-workforce pipelines: the deterministic `Workflow` scripts that orchestrate the agents in `../agents/`. The agents declare *what* they do; these scripts decide *when* each runs, how work is routed, and where the deterministic control flow ends and agent judgment begins.

## Status: canonical here, deployed by hand (for now)

The Claude Code plugin framework does not deploy workflows natively, so these do not ship to a project automatically the way agents and skills do. Deployment will be **automated** — a `SessionStart` hook (modeled on `../scripts/init-update-project.sh`) will symlink this folder into a consuming project at `.claude/workflows/agent-teams-workforce-pipelines/` and refresh it when the plugin version changes.

Until that automation lands:

- **This folder is the single source of truth.** Edit workflows here, not in a consuming project.
- **Changes must be copied to consuming projects by hand.** A project that already links or copies these scripts will not see an update until you re-copy (or the symlink target is refreshed).

## Contents

- **Composites** — `prd-to-spec.js`, `spec-to-deploy.js`, `bug-fix.js`, `infra-change.js`: full pipelines stitched from the pieces below.
- **Front-ends & phases** — `prd-validation.js`, `architecture.js`, `trd-authoring.js`, `spec-authoring.js`, `task-decomposition.js`, `spec-freshness.js`, `tdd-red.js`, `tdd-green.js`, `tdd-refactor.js`, `integration.js`, `adversarial.js`, `deploy.js`, `documentation.js`, `infra-intent.js`.
- **Routing & gates** — `route-bead.js`, `bug-triage.js`, `gate-enforce.js`, `gate-constitutional.js`.
- **Docs** — `ROUTING.md` (how a bead is routed to a composite), `../AGENT-TEAMS-WORKFORCE.md` (the full workforce/pipeline reference).

Workflows are addressed **by name**, never by number.
