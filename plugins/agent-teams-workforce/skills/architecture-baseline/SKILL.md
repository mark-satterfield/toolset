---
name: architecture-baseline
description: Assess the effective architecture in arc42 against one PRD, find what it does not yet serve or represent, build out the architecture from non-effective documents, existing repository code and the AWS MCP Server where it falls short, and keep arc42 updated with a delta for every change. Selects justified retention, change, replacement, addition or retirement without assuming a new design is required.
user-invocable: false
---

# Assessing the effective architecture for a PRD

## The architecture phase

The architecture is the current effective architecture in arc42: the canonical views whose `lifecycle_state` is `effective`. There is no separate baseline architecture. Every PRD builds on the effective architecture and leaves it updated, so it stays current as PRDs are processed. The architecture phase runs for every PRD and is never skipped; it is not architecture creation. It has three steps:

1. **Assess.** Using the PRD as the guide, find and analyze the effective architecture to judge whether it meets the PRD's needs, capability by capability.
2. **Build out.** Where the effective architecture does not completely serve the PRD, build it out from the non-effective architecture documents, with the code in the existing repositories on `main` as guidance and the AWS MCP Server as the authority on best practice (see below). Building out includes independent review and approval of the proposal.
3. **Update arc42.** Integrate the approved result into arc42 as the new effective architecture, with a delta that records the change.

## Authority and evidence

Read the caller's architecture MODEL, specifically `reference/architecture-documentation-model.md#Assessing existing architecture and implementation` beneath the supplied architecture root when that is the project's model layout. The project model owns its document versions, review states and maintenance obligations; this skill applies them to bounded workflow assignments without inventing a second authority policy.

The owner's explicit instructions and applicable requirements and constraints establish what the work must accomplish. Apply their stated scope. Existing code, CDK, tests, drafts and incidental implementation choices are evidence of the current state; their existence does not make them binding decisions or make retention the goal. The effective architecture is a reviewed starting point, not an immutable prohibition on better justified changes. Read an actual decision and its applicability before treating it as authoritative; do not infer an owner decision from a file, an old implementation or an agent-authored statement.

Compare the current system with the required target. Retain what is suitable; change, replace, add or retire what the evidence and requirements justify. Do not preserve stale design merely because it exists, and do not replace suitable work merely because a different design is possible. Explain the relevant requirement, defect, constraint or AWS guidance and the tradeoff behind a proposed change. A recommendation is evidence to assess in context, not an automatic requirement to redesign. Iteration is expected: preserve provenance and useful findings, revise the affected architecture and implementation work, and use normal Git history to make changes reviewable and reversible.

## Evolve the architecture one PRD at a time

An effective document is the approved architecture under the knowledge and requirements available when it was approved, not a permanent constraint on future work. Assess the current PRD against the relevant effective views, repository behavior and connected contracts. Expand that scope only where the impact evidence requires it; do not load or redesign all PRDs to approve one. A later PRD may justify superseding a previously sound decision. Explain the new requirement or evidence, update the affected canonical views and implementation handoff, and retain unrelated valid decisions and review evidence. Unknown future requirements are not present constraints or reasons to block approval.

## Assess the effective architecture before selecting work

Use the caller's authoritative PRD, repository code on `main`, CDK, interfaces, data and event schemas, tests, existing arc42 views, open targets and relevant AWS documentation. Repository code and CDK represent the intended deployed system; no separate live-account inventory or deployment-access gate is required by this contract.

Architecture includes responsibilities, business behavior, interfaces, data, interactions and runtime flows as well as infrastructure. A Lambda or table declaration in CDK does not establish what the application does. For a behavioral capability, inspect the relevant implementation, entrypoints, wiring, contracts and tests. Keep behavioral evidence separate from infrastructure evidence. A test file is evidence of a test, not evidence that it passed. Cite precise sources and distinguish established behavior, inference and uncertainty. Only a genuinely infrastructure-only or documentation-only obligation may use that narrower scope; explain its applicability.

Read each relevant document's actual `lifecycle_state`. `effective` and `in-review` are the existing review states; versions (`effective`, `target`, `delta`, `built`) describe the document's place in the architecture model. These dimensions are not interchangeable. An approved design need not have been implemented. Unreviewed documentation and existing code may be useful and correct, but still need validation. Missing documentation is not proof that code is absent; existing code is not proof that the required behavior is complete or suitable.

## Check what the effective architecture does not yet represent

Even when the effective views serve a capability, arc42 can hold content they do not yet reflect. For every capability the PRD needs, check it against:

- the owner's constraints in section 2 (`02-architecture-constraints/`), including constraints added or changed since the effective views were approved;
- canonical arc42 views still `in-review`, and other arc42 content not yet effective (for example section 4 strategy or section 8 concepts in review);
- open targets under `target/` and build records under `built/` that show the capability's elements.

An open target is design input, not approved design. Its `baseline.json` records `arc42Revision`, the revision of the effective version it was designed against. When that revision is missing, or effective views of the same elements were approved after the target was written (their last commit in the vault is later than the target's), the survey and the Check judge the target possibly stale: validate each part against the current effective views before adopting it, and record in the assessment what was found superseded.

A constraint or document that applies to the capability and that its effective views do not represent is a cited gap: name the constraint or document (path and heading) and the effective view that does not represent it. Give that capability `designAction` `modify` when the design must change to honour it, or `documentationAction` `update` when only the documentation lags; either places the capability in design scope. Content that does not apply to the PRD's capabilities is not in scope; mention it in the summary. When nothing is unrepresented, say so for each capability, with the documents checked. This check is part of every assessment and of every independent review of a capability left unchanged, including a review-only Check.

## Build out from every available input

When the effective architecture does not completely serve the PRD, authors build the target from:

- the effective views, as the reviewed starting point;
- the non-effective architecture documents named above, as design input: validate them and adopt what suits this PRD, rather than only avoiding contradiction with them;
- the code in the existing repositories on `main`, as guidance: it may already be exactly the design the PRD needs, so reuse it when it is; it may also be stale and far out of date, so judge it against the PRD, the effective views and AWS best practice before following it, and never treat its existence as a reason to keep it;
- the AWS MCP Server's documentation and skills (with the `aws-core` skills and AWS Well-Architected guidance), as the authority on best practice: every AWS design choice follows them, and where code or an older document disagrees with them, the best practice wins unless a business requirement or a section 2 constraint says otherwise.

## Close over what the work rests on

A PRD names the capabilities it needs, not the foundations they run on. The work of the approved delta rests on other elements the effective architecture shows: a table on its database cluster, the cluster on its network, a handler on its event bus or user pool, a service on a shared library or on a repository that does not exist yet. The handoff to implementation is complete only when every element the delta's work transitively rests on is built and current on `main`, is planned by an open bead of any Epic, or is itself carried as implementation work. After integration, the architecture step's Closure phase walks the effective views from every delta item and records each element that is absent, stale against the effective views, or planned elsewhere, with the repository that deploys it or the repository to create. These become prerequisite items: placed in their own repository, detailed and specified like any delta item, built by their own Tasks, and ordered before the Tasks that need them. A prerequisite an open bead already plans gets no new Task; the Tasks that need it are blocked by that bead. Existing code is evidence of the built state and may be stale; AWS best practice decides what the element must be.

## Produce the canonical assessment

The caller supplies [the assessment schema](../artifact-handoff/schemas/architecture-baseline.schema.json) as `survey.baseline`. Each entry's `id` is exactly its surveyed capability name and its `requirements` match that capability's requirement references. Record the current state, required target, suitability evidence, rationale and unresolved conflicts. Do not use structural validity as a substitute for judging the evidence.

Keep design, documentation and implementation actions separate:

- A suitable approved design with missing implementation needs implementation work, not another design proposal.
- Suitable existing behavior with missing or incomplete architecture documentation needs documentation and its review, without invented replacement code.
- An existing unreviewed design may need validation and approval, or a bounded correction; it does not automatically need a competing proposal.
- An unsuitable existing implementation may need change, replacement or retirement, including when its older documentation was approved.
- A fully suitable, evidenced current capability can retain its design and implementation. Record that conclusion and evidence explicitly.
- Different capabilities and repositories in one PRD may take different actions. Preserve those distinctions in the target and implementation handoff.

`disposition` describes the implementation intent: retain, change, replace, add, retire or undetermined. It is not a document lifecycle state. Unknown evidence remains unknown; never convert it to absence, completion or permission to rebuild. The deterministic helper checks capability coverage, action consistency, required evidence categories and source freshness. It cannot establish that a cited handler implements the requirement: the appropriate independent reviewer must examine that meaning.

## Bounded authoring, review and maintenance

The default is check and approve: a PRD the effective architecture and the code already serve, with nothing in arc42 left unrepresented, is independently verified and approved without design authoring. A finding in that review that the effective architecture lacks design or documentation sends the assessment back for reassessment of the affected capabilities, which then enter design scope. Select only the authors and reviewers needed for the assessed obligations and remaining gaps. No PRD automatically requires a database, API, integration, competing design or every specialty. Review relevant current claims and their affected dependencies; retain still-valid evidence when unrelated files change. Changes to cited behavior or connected contracts require targeted reassessment.

When design authoring is needed, the coordinator names one of the selected existing authors as accountable for the combined target's coherence. This is an assignment within the chosen work, not a new agent, a fixed lead specialty or an extra dispatch. Assign that author the integration views and order its final reconciliation after the contributing outputs it needs exist. Other authors own their bounded subject views; no author must certify a later author's unwritten output. A review-only or unchanged assessment has no design owner because it has no design-authoring assignment.

Keep maker, reviewer and approval responsibilities separate. An assessment does not approve a design, and a machine-generated unchanged handoff does not replace independent review. After approval, update every affected architecture view and its connected documentation at the appropriate scopes. Carry implementation additions, modifications, replacements and retirements into the TRD, specifications and tasks even when no new architecture authoring is needed. A durable unchanged target may carry zero design changes while still carrying implementation work.

Every change to the effective architecture has a delta: authored design or documentation changes are delta views beside the target, and approving existing in-review views is recorded in the target's delta handoff. A PRD the effective architecture already serves still gets a delta handoff that says so, with its implementation work.

Approval leaves the covered canonical arc42 documentation correct and approved (`lifecycle_state: effective`); it does not claim implementation. Integrate reviewed target changes into the canonical views, correcting or removing superseded content at every affected scope. A target, delta or built document alone cannot satisfy canonical publication. Existing in-review canonical views may be approved in place after review; already correct and approved views need no gratuitous rewrite. Record the exact affected files so publication can be verified before completion.

Use the caller's executable artifact submission and checkpoint commands. Preserve accepted work and provenance; update the assessment when its relevant inputs change. Do not add private copies of this policy to workflow prompts: workflows supply paths, schemas, task scope and executable gates, while this skill owns the assessment principles.
