---
name: cumulative-regression
description: Preserve current requirements across PRDs and map affected components to applicable tests and fresh execution evidence through the workflow's cumulative regression artifacts.
user-invocable: false
---

# Cumulative regression assurance

A passing command proves only what actually ran. It does not establish that the suite covers all current requirements of the changed component. New feature tests supplement the existing valid behavior; they do not replace it.

## Establish the affected requirements

**The scope rule.** This is the one statement of how far discovery reaches; the assessor writes to it and the reviewer checks against it.

1. Read the caller's actual Task, spec, PRD, architecture/contracts, repository instructions and existing tests, plus the prior `.agent-workforce/regression.json` in the assigned repository. Take the prior ledger as complete for what it records.
2. Beyond the ledger, follow the components the change edits, and the producers and consumers connected to them by a contract the change alters, to their current requirements in other PRDs and repositories. Use the supplied documentation locator and supported vault access where applicable.
3. Search past the prior ledger for what it already records only where the Task changes a universal or shared component: a shared library, layer, chassis or service other repositories or components consume.
4. Retain every unrelated prior requirement and mapping as not impacted, so no unnecessary fleet-wide rerun follows.

Discovery stops at demonstrated component and dependency impact. A search past this boundary is not required, its absence is no gap, and no speculative fleet-wide infrastructure is built. Regression impact links are evidence relationships, never permission to create or change Epic blocker edges. Epic Beads dependencies govern architecture development order; they do not define build, deploy or runtime order.

Record changed components with their actual files, and the sources searched with what they showed. A source reference identifies a real document and requirement or section, not a paraphrase. Do not assume that the newest PRD contains all obligations, that no ledger means greenfield, or that existing tests exhaust the requirements. Missing or inaccessible sources are explicit gaps.

Carry forward every still-valid prior requirement. Supersession requires an explicit accepted requirement or owner decision reference that authorizes the replaced behavior, with the old requirement ID and reason. Neither a new test, changed implementation, assessor preference nor failing old test authorizes supersession. Preserve unaffected tests and assertions. Renames, relocation or consolidation retain equivalent behavioral coverage and an explicit old-to-new test mapping; removal, weakening or newly skipping a test requires source-backed supersession or a demonstrated equivalent replacement.

## One shared artifact contract

The regression artifact has one contract: artifact-handoff's `schemas/regression-plan.schema.json`, whose descriptions define every member, what each layer and run format can express, and which members change after the scope is approved. Write the one candidate artifact the workflow assigns to it and return its reference under the artifact-handoff contract. The workflow checks the artifact against that file and with `scripts/portfolio/regression.py check`, returns the errors for one correction, fingerprints the bytes of every source file before reuse and binds approval to those bytes. Changed source evidence requires reassessment; a stable path or remembered review is not freshness evidence.

Preserve all still-valid prior requirements and mappings; mark which this change impacts with concrete reasons. Unaffected retained requirements do not trigger an unnecessary fleet-wide execution sweep. A real behavioral change cannot be waved through by marking every requirement unaffected. Assess unit, contract, integration and nonfunctional applicability explicitly: mark required layers and cite source-backed reasons for exclusions. Cross-service API/event/data interactions normally require contract and integration evidence; repository-local unit coverage alone does not establish these interactions. Do not invent a layer obligation with no applicable behavior.

Every required layer is planned to a run the gate can execute, whatever the layer. A requirement that the repository's lint, format or type checks pass is a nonfunctional requirement proved by a run of the repository's own check command whose exit status is its result; a test layer is proved by a run that writes a JUnit report naming the tests. What a run needs before it can run (installed dependencies, a built package, a token its install needs) is declared on the run as its setup, from the repository's own instructions (its `AGENTS.md`, `Taskfile.yml`, CI workflow), and the gate executes it before the run. A capability is a gap only when the repository supports no command for it.

Before Red, establish requirements and layer applicability, and declare the runs that already exist (the repository's checks and its suite) with their setup; mappings for tests still to be written may wait. After Red, finalize mappings to actual tests and declared commands without silently changing the approved requirement/component scope. A legitimate test rename or consolidation is a replacement; the mapping review verifies the old assertion semantics remain covered. Test replacement is distinct from requirement supersession. A mapping names a test by what its assertions cover, as the mapping review below checks.

## Test authoring and execution

A test writer adds to the existing test file that covers the module or behaviour, matching its imports, fixtures, naming and helpers, and creates a new file only when none covers the area. Where an existing test already encodes a criterion, keep it and do not write a second one. Tests synthesize, build or render the thing under test during the run; they never read a committed build output.

When given `regressionPlanPath`, read that artifact and the cited requirement sections before editing. Extend existing tests for the assigned layer, preserving valid assertions from earlier PRDs. Author the missing tests for the impacted requirements and layers of your own specialty in the repository you were given, along with the new feature tests. A test that belongs in another repository is reported in your result as a blocked dependency; you edit no other checkout. Keep existing test IDs stable and name each new test concretely so it can be mapped. Existing behavior tests normally remain green during Red; only genuinely new/unimplemented behavior must fail for its intended reason. Do not rewrite sound tests merely to manufacture Red.

Use repository-supported test commands and reporting configuration; do not narrow the whole-suite gate to only the new tests, omit failing tests, or rewrite expected behavior to match the implementation. Report unsupported or unavailable execution/reporting capabilities explicitly. The deterministic gate executes each declared run after its setup and checks its fresh result: every mapped test passing in a fresh JUnit report, or a check's zero exit status. An agent's claim, a stale report, a test run's exit code alone, a skipped/disabled test, or an unmapped green suite is insufficient. Cross-repository impacts need mapped execution evidence in the owning repository; inaccessible dependencies remain gaps rather than assumed passes.

## Independent review

The review's shape is artifact-handoff's `schemas/regression-review.schema.json`, whose descriptions define every member. Reviewers read source requirements, relevant code/contracts, the prior ledger, changed test assertions and current mappings, never the assessor's prose alone, and check omissions as well as listed entries. Report each finding with its source reference and a verifiable correction that the regression plan contract can express. Do not edit the producer's artifacts or approve your own assessment. The workflow retains the accepted cumulative ledger only after independent approval and deterministic execution evidence; unresolved gaps prevent completion.

### Plan review (before Red)

Check the scope as the regression plan contract states it before any test is written:

- the changed components and their actual files;
- discovery against the scope rule above, no further;
- every requirement the scope rule reaches, carried forward or new, with each of its four layers assessed from the sources;
- supersession, and any test removal, weakening or newly skipped test, backed by an accepted source;
- the runs the repository already supports, each with the setup its preconditions need, and the kept mappings of existing tests.

A plan review does not judge tests still to be written: not their design, not what they will assert, and not whether a mapping's assertions substantiate a requirement. Those belong to the mapping review.

### Mapping review (after Red)

- Every mapped test exists, and its assertions substantiate the mapped requirement. One test may substantiate several requirements only when its actual assertions cover each; a file name, a test count or a collection count is not evidence.
- Every replacement preserves the old requirement and assertion semantics.
- The run commands and report configuration are real and collect the mapped tests; a green subset is insufficient. `sourceFiles` covers the actual requirement documents.
- The approved scope is unchanged.

### Severity

A finding is blocking when the artifact as written would let the gate pass without evidence for a current obligation, or would record evidence that cannot exist: a requirement the scope rule reaches that is missing or dropped, a required layer of an impacted requirement with no run (in a mapping review, no mapping), an unsupported supersession or test removal, a run that cannot execute or collect its mapped tests, a run whose preconditions are not declared as setup, and in a mapping review a mapped test that is absent or whose assertions do not cover the requirement, or a changed approved scope. Every other finding is non-blocking: it loses no evidence (for example a flag or reason that misstates risk while the run still executes, a more precise source reference, or a search past the scope rule). The review is approved exactly when no finding is blocking; non-blocking findings are carried with it as notes.

### Re-review

When the brief names a previous review of the artifact, rule first on each of its findings: resolved or not, with the evidence. An unresolved blocking finding is raised again as a blocking finding. After that, raise a new finding only when it is blocking and concerns content the previous review could not judge: content that changed since the version it read (the brief names that version), or content the correction added. Content the previous review read and accepted or let pass, and that is unchanged since, is not reopened.
