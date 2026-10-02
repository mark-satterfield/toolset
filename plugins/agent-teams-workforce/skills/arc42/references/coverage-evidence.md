# Coverage evidence for architecture work

The project's MODEL owns applicability, coverage results, navigation, review state and versions.
The MENU owns view selection and construction guidance. Read both from the resolved architecture
root; this procedure does not duplicate their project-specific families or thresholds.

## Establish the assessment boundary

Record the change or project-wide scope the caller commissioned and the sources that establish
its subjects: the design, relevant repository/service inventory, contracts, important flows and
shared mechanisms. The catalog finds existing coverage but is not the subject inventory. Apply
the MODEL's applicability conditions to each subject and reader question, including questions for
which no view exists. Record aliases and the files actually examined; no search hit is not proof
of non-applicability. A missing design answer is reported rather than invented.

A per-change assessment follows that change into system, domain, service, component and concept
views where applicable. It does not take responsibility for unrelated architecture or certify a
whole-project baseline. Record unrelated gaps as such for the caller. A separately commissioned
whole-project assessment uses the wider inventory and states what remains unassessed.

## Carry evidence through the assigned work

Use the artifact paths and structured schema supplied by the caller. In the architecture workflow,
coverage travels with the survey, round results and ledger; do not invent another coverage file or
store assessment records in living views. Keep stable obligation identifiers so routing, authored
views, independent review and integration refer to the same obligation. When content or its
applicability rationale changes, its earlier review does not establish the revised claim.

- **Survey/author:** identify the subject, reader question, applicable MODEL provision, inventory
  sources and rationale. Locate existing views and name needed coverage with no file. Use the
  MODEL's assessment results and keep them separate from `lifecycle_state`. The author maps
  assigned obligations to authored paths and evidence, with explicit unchecked work.
- **Coordinator:** assign missing/incomplete applicable coverage to an appropriate proposer or
  diagram author, with clear file ownership, then route the resulting evidence to an independent
  reviewer. Route design gaps to a designer; do not design or approve them yourself.
- **Diagram author:** draw the supplied design using MENU guidance and the assigned scope. An
  actual diagram must support its declaration; a catalog label, fence or prose index is not a
  diagram. Report rendering, visual readability and semantic self-checks separately, including
  unavailable checks. Self-checks do not replace independent review.
- **Reviewer:** check applicability and completeness against the independent inventory and MODEL,
  not only the author's chosen paths. Verify the current evidence for each obligation, including
  any exception/non-applicability rationale. Check content and adjacent views across the affected
  scopes; report named absences and unassessed evidence. Do not author missing designs or views.
- **Decider:** use the supplied independent evidence to decide; unresolved required coverage or
  missing due diligence is returned to its owner, not silently waived or authored here.
- **Maintainer:** apply only approved coverage and design, including approved new views absent from
  the old catalog. Report each obligation's disposition and actual integrated paths; update related
  navigation, prose and metadata together. An unapproved design gap goes back to the caller.
- **Conformance reviewer:** compare the integration with approved coverage as well as the target
  and delta. Confirm actual content, diagrams and required links, including views not found by the
  original catalog. Report findings without editing, promoting lifecycle or redesigning.

## Consumers of the caller-defined evidence

The caller owns the schema; do not add required fields or reports that it does not consume.

- **Consumed by: architecture-decision-workflow-coordinator** — uses survey/round coverage to
  assign missing work and independent review with exclusive file ownership.
- **Consumed by: architecture.js and arch-resume** — use the caller-defined coverage rows and
  current reviewer results in the saved survey/round ledger to determine whether due diligence
  permits the decision step; prior evidence does not silently approve a revised row.
- **Consumed by: architecture-decider** — uses independently reviewed coverage to approve or
  return the target without producing its own evidence.
- **Consumed by: architecture-maintainer** — uses approved obligations and paths to integrate
  the complete affected view set, including approved new views.
- **Consumed by: architecture-conformance-reviewer** — uses approved obligations, authored paths
  and integration dispositions to check actual fidelity, completeness and navigation.
- **Consumed by: architecture.js** — uses the conformance result to continue correction or proceed
  to lifecycle promotion; the maintainer cannot promote its own work.
- **Consumed by: the commissioning caller of arc42-verify** — uses the scoped findings to route
  corrections; a separately commissioned whole-project assessment is not a per-change gate.

## Evidence quality

Reference the paths and locations that support the result. Check diagram presence, type semantics,
renderability, visual readability, agreement with prose and consistency with adjacent views as
separate questions. A parser success does not establish readability or architectural correctness;
a missing tool or unchecked visual is a limitation, not success. Use the MODEL for prose-only
exceptions and honest type declarations, not a blanket exemption for missing diagrams.

Validate discovery against the actual file inventory so missing/invalid metadata cannot hide a
view. Validate missing coverage against the independently established subjects so nonexistent files
cannot hide obligations. Validate human navigation as the MODEL requires. Assessment sufficiency
is not architecture approval; only the calling review/approval process changes lifecycle state.
