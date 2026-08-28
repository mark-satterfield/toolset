# agent-teams-workforce — workflow scripts

These are the **canonical source** for the agent-teams-workforce pipelines: the deterministic `Workflow` scripts that orchestrate the agents in `../agents/`. The agents declare *what* they do; these scripts decide *when* each runs, how work is routed, and where the deterministic control flow ends and agent judgment begins.

## Status: canonical here, deployed by hand (for now)

The Claude Code plugin framework does not deploy workflows natively, so these do not ship to a project automatically the way agents and skills do. Deployment will be **automated** — a `SessionStart` hook (modeled on `../scripts/init-update-project.sh`) will symlink this folder into a consuming project at `.claude/workflows/agent-teams-workforce-pipelines/` and refresh it when the plugin version changes.

Until that automation lands:

- **This folder is the single source of truth.** Edit workflows here, not in a consuming project.
- **Changes must be copied to consuming projects by hand.** A project that already links or copies these scripts will not see an update until you re-copy (or the symlink target is refreshed).

## Contents

- **Composites** — `prd-to-spec.js`, `task-to-deploy.js`, `bug-fix.js`, `infra-change.js`: full pipelines stitched from the pieces below.
- **Front-ends & phases** — `workspace.js`, `prd-reconciliation.js`, `prd-validation.js`, `architecture.js`, `repo-scoping.js`, `trd-authoring.js`, `spec-authoring.js`, `task-decomposition.js`, `spec-freshness.js`, `tdd-red.js`, `tdd-green.js`, `tdd-refactor.js`, `integration.js`, `adversarial.js`, `deploy.js`, `documentation.js`, `infra-intent.js`.
  - `repo-scoping.js` rules the REPO SPAN of a PRD — which repositories its remaining work lands in — after the architecture decision and before anything fans out per repo. The span is an output of the run, recomputed every time and stored nowhere, so a re-run after an adjustment is scoped against the adjustment. It can rule that a repository the project does not have is needed; that comes back as a required human action, never as a repository this pipeline creates.
  - `workspace.js` is the structural mirror of the settle step: settle LANDS the tree on every exit path, workspace ESTABLISHES it before the first write. Every code-writing composite dispatches it first, and its return value is the sole source of `contract.repoPath` — the caller supplies a repository, this step supplies the worktree.
- **Routing & gates** — `route-build.js`, `route-elaboration.js`, `bug-triage.js`, `gate-enforce.js`, `gate-constitutional.js`.
- **Docs** — `ROUTING.md` (how a bead is routed to a composite), `../AGENT-TEAMS-WORKFORCE.md` (the full workforce/pipeline reference).

Workflows are addressed **by name**, never by number.
