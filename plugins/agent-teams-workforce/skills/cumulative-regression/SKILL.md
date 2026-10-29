---
name: cumulative-regression
description: Preserve current requirements across PRDs and map affected components to applicable tests and fresh execution evidence through the workflow's cumulative regression artifacts.
user-invocable: false
---

# Cumulative regression assurance

A passing command proves only what actually ran. It does not establish that the suite covers all current requirements of the changed component. New feature tests supplement the existing valid behavior; they do not replace it.

## Establish the affected requirements

Read the caller's actual Task, spec, PRD, architecture/contracts, repository instructions and existing tests, plus the prior `.agent-workforce/regression.json` in the assigned repository. Follow component and producer/consumer references to current requirements in other PRDs and affected repositories. Use the supplied documentation locator and supported vault access where applicable. Scope discovery to demonstrated component/dependency impact; do not construct speculative fleet-wide infrastructure. Regression impact links are evidence relationships, never permission to create or change Epic blocker edges. Epic Beads dependencies govern architecture development order; they do not define build, deploy or runtime order.

Record changed components with their actual files, and the sources searched with what they showed. A source reference identifies a real document and requirement or section, not a paraphrase. Do not assume that the newest PRD contains all obligations, that no ledger means greenfield, or that existing tests exhaust the requirements. Missing or inaccessible sources are explicit gaps.

Carry forward every still-valid prior requirement. Supersession requires an explicit accepted requirement or owner decision reference that authorizes the replaced behavior, with the old requirement ID and reason. Neither a new test, changed implementation, assessor preference nor failing old test authorizes supersession. Preserve unaffected tests and assertions. Renames, relocation or consolidation retain equivalent behavioral coverage and an explicit old-to-new test mapping; removal, weakening or newly skipping a test requires source-backed supersession or a demonstrated equivalent replacement.

## One shared artifact contract

The regression artifact has one contract: artifact-handoff's `schemas/regression-plan.schema.json`, whose descriptions define every member, what each layer and run format can express, and which members change after the scope is approved. Write the one candidate artifact the workflow assigns to it and return its reference under the artifact-handoff contract. The workflow checks the artifact against that file and with `scripts/portfolio/regression.py check`, returns the errors for one correction, fingerprints the bytes of every source file before reuse and binds approval to those bytes. Changed source evidence requires reassessment; a stable path or remembered review is not freshness evidence.

Preserve all still-valid prior requirements and mappings; mark which this change impacts with concrete reasons. Unaffected retained requirements do not trigger an unnecessary fleet-wide execution sweep. A real behavioral change cannot be waved through by marking every requirement unaffected. Assess unit, contract, integration and nonfunctional applicability explicitly: mark required layers and cite source-backed reasons for exclusions. Cross-service API/event/data interactions normally require contract and integration evidence; repository-local unit coverage alone does not establish these interactions. Do not invent a layer obligation with no applicable behavior.

Every required layer is planned to a run the gate can execute, whatever the layer. A requirement that the repository's lint, format or type checks pass is a nonfunctional requirement proved by a run of the repository's own check command whose exit status is its result; a test layer is proved by a run that writes a JUnit report naming the tests. What a run needs before it can run (installed dependencies, a built package, a token its install needs) is declared on the run as its setup, from the repository's own instructions (its `AGENTS.md`, `Taskfile.yml`, CI workflow), and the gate executes it before the run. A capability is a gap only when the repository supports no command for it.

Before Red, establish requirements and layer applicability, and declare the runs that already exist (the repository's checks and its suite) with their setup; mappings for tests still to be written may wait. After Red, finalize mappings to actual tests and declared commands without silently changing the approved requirement/component scope. A legitimate test rename or consolidation is a replacement; independent review verifies the old assertion semantics remain covered. Test replacement is distinct from requirement supersession. One test may substantiate several requirements only when its actual assertions cover each; file names or collection counts alone are not behavioral evidence.

## Test authoring and execution

A test writer adds to the existing test file that covers the module or behaviour, matching its imports, fixtures, naming and helpers, and creates a new file only when none covers the area. Where an existing test already encodes a criterion, keep it and do not write a second one. Tests synthesize, build or render the thing under test during the run; they never read a committed build output.

When given `regressionPlanPath`, read that artifact and the cited requirement sections before editing. Extend existing tests for the assigned layer, preserving valid assertions from earlier PRDs. Author the missing tests for the impacted requirements and layers of your own specialty in the repository you were given, along with the new feature tests. A test that belongs in another repository is reported in your result as a blocked dependency; you edit no other checkout. Keep existing test IDs stable and name each new test concretely so it can be mapped. Existing behavior tests normally remain green during Red; only genuinely new/unimplemented behavior must fail for its intended reason. Do not rewrite sound tests merely to manufacture Red.

Use repository-supported test commands and reporting configuration; do not narrow the whole-suite gate to only the new tests, omit failing tests, or rewrite expected behavior to match the implementation. Report unsupported or unavailable execution/reporting capabilities explicitly. The deterministic gate executes each declared run after its setup and checks its fresh result: every mapped test passing in a fresh JUnit report, or a check's zero exit status. An agent's claim, a stale report, a test run's exit code alone, a skipped/disabled test, or an unmapped green suite is insufficient. Cross-repository impacts need mapped execution evidence in the owning repository; inaccessible dependencies remain gaps rather than assumed passes.

## Independent review

Reviewers read source requirements, relevant code/contracts, the prior ledger, changed test assertions and current mappings. Check omissions as well as listed entries: changed components missing prior obligations, required layers missing mappings, mapped IDs absent from actual tests, runs whose preconditions are not declared as setup, unjustified test removal/weakening/skips and unsupported supersession. Report concrete findings with source references and a verifiable correction that the contract can express. Do not edit the producer's artifacts or approve your own assessment. The workflow retains the accepted cumulative ledger only after independent approval and deterministic execution evidence; unresolved gaps prevent completion.
