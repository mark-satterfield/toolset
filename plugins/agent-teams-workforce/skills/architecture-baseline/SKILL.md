---
name: architecture-baseline
description: Assess existing architecture and implementation against current requirements and evidence, selecting justified retention, change, replacement, addition or retirement without assuming a new design is required.
user-invocable: false
---

# Architecture baseline and justified change

## Authority and evidence

Read the caller's architecture MODEL, specifically `reference/architecture-documentation-model.md#Assessing existing architecture and implementation` beneath the supplied architecture root when that is the project's model layout. The project model owns its document versions, review states and maintenance obligations; this skill applies them to bounded workflow assignments without inventing a second authority policy.

The owner's explicit instructions and applicable requirements and constraints establish what the work must accomplish. Apply their stated scope. Existing code, CDK, tests, drafts and incidental implementation choices are evidence of the current state; their existence does not make them binding decisions or make retention the goal. Approved architecture establishes a reviewed starting point, not an immutable prohibition on better justified changes. Read an actual decision and its applicability before treating it as authoritative; do not infer an owner decision from a file, an old implementation or an agent-authored statement.

Compare the current system with the required target. Retain what is suitable; change, replace, add or retire what the evidence and requirements justify. Do not preserve stale design merely because it exists, and do not replace suitable work merely because a different design is possible. Explain the relevant requirement, defect, constraint or AWS guidance and the tradeoff behind a proposed change. A recommendation is evidence to assess in context, not an automatic requirement to redesign. Iteration is expected: preserve provenance and useful findings, revise the affected architecture and implementation work, and use normal Git history to make changes reviewable and reversible.

## Evolve the architecture one PRD at a time

An effective document is the approved architecture under the knowledge and requirements available when it was approved, not a permanent constraint on future work. Assess the current PRD against the relevant effective views, repository behavior and connected contracts. Expand that scope only where the impact evidence requires it; do not load or redesign all PRDs to approve one. A later PRD may justify superseding a previously sound decision. Explain the new requirement or evidence, update the affected canonical views and implementation handoff, and retain unrelated valid decisions and review evidence. Unknown future requirements are not present constraints or reasons to block approval.

## Establish the baseline before selecting work

Use the caller's authoritative PRD, repository code on `main`, CDK, interfaces, data and event schemas, tests, existing arc42 views, open targets and relevant AWS documentation. Repository code and CDK represent the intended deployed system; no separate live-account inventory or deployment-access gate is required by this contract.

Architecture includes responsibilities, business behavior, interfaces, data, interactions and runtime flows as well as infrastructure. A Lambda or table declaration in CDK does not establish what the application does. For a behavioral capability, inspect the relevant implementation, entrypoints, wiring, contracts and tests. Keep behavioral evidence separate from infrastructure evidence. A test file is evidence of a test, not evidence that it passed. Cite precise sources and distinguish established behavior, inference and uncertainty. Only a genuinely infrastructure-only or documentation-only obligation may use that narrower scope; explain its applicability.

Read each relevant document's actual `lifecycle_state`. `effective` and `in-review` are the existing review states; versions (`effective`, `target`, `delta`, `built`) describe the document's place in the architecture model. These dimensions are not interchangeable. An approved design need not have been implemented. Unreviewed documentation and existing code may be useful and correct, but still need validation. Missing documentation is not proof that code is absent; existing code is not proof that the required behavior is complete or suitable.

## Produce the canonical assessment

The caller supplies [the baseline schema](../artifact-handoff/schemas/architecture-baseline.schema.json) as `survey.baseline`. Each entry's `id` is exactly its surveyed capability name and its `requirements` match that capability's requirement references. Record the current state, required target, suitability evidence, rationale and unresolved conflicts. Do not use structural validity as a substitute for judging the evidence.

Keep design, documentation and implementation actions separate:

- A suitable approved design with missing implementation needs implementation work, not another design proposal.
- Suitable existing behavior with missing or incomplete architecture documentation needs documentation and its review, without invented replacement code.
- An existing unreviewed design may need validation and approval, or a bounded correction; it does not automatically need a competing proposal.
- An unsuitable existing implementation may need change, replacement or retirement, including when its older documentation was approved.
- A fully suitable, evidenced current capability can retain its design and implementation. Record that conclusion and evidence explicitly.
- Different capabilities and repositories in one PRD may take different actions. Preserve those distinctions in the target and implementation handoff.

`disposition` describes the implementation intent: retain, change, replace, add, retire or undetermined. It is not a document lifecycle state. Unknown evidence remains unknown; never convert it to absence, completion or permission to rebuild. The deterministic helper checks capability coverage, action consistency, required evidence categories and source freshness. It cannot establish that a cited handler implements the requirement: the appropriate independent reviewer must examine that meaning.

## Bounded authoring, review and maintenance

Select only the authors and reviewers needed for the assessed obligations and remaining gaps. No PRD automatically requires a database, API, integration, competing design or every specialty. Review relevant current claims and their affected dependencies; retain still-valid evidence when unrelated files change. Changes to cited behavior or connected contracts require targeted reassessment.

When design authoring is needed, the coordinator names one of the selected existing authors as accountable for the combined target's coherence. This is an assignment within the chosen work, not a new agent, a fixed lead specialty or an extra dispatch. Assign that author the integration views and order its final reconciliation after the contributing outputs it needs exist. Other authors own their bounded subject views; no author must certify a later author's unwritten output. A review-only or unchanged assessment has no design owner because it has no design-authoring assignment.

Keep maker, reviewer and approval responsibilities separate. A baseline assessment does not approve a design, and a machine-generated unchanged handoff does not replace independent review. After approval, update every affected architecture view and its connected documentation at the appropriate scopes. Carry implementation additions, modifications, replacements and retirements into the TRD, specifications and tasks even when no new architecture authoring is needed. A durable unchanged target may carry zero design changes while still carrying implementation work.

Approval leaves the covered canonical arc42 documentation correct and approved (`lifecycle_state: effective`); it does not claim implementation. Integrate reviewed target changes into the canonical views, correcting or removing superseded content at every affected scope. A target, delta or built document alone cannot satisfy canonical publication. Existing in-review canonical views may be approved in place after review; already correct and approved views need no gratuitous rewrite. Record the exact affected files so publication can be verified before completion.

Use the caller's executable artifact submission and checkpoint commands. Preserve accepted work and provenance; update the assessment when its relevant inputs change. Do not add private copies of this policy to workflow prompts: workflows supply paths, schemas, task scope and executable gates, while this skill owns the assessment principles.
