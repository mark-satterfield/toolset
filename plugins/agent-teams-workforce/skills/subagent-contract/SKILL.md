---
name: subagent-contract
description: Bounded specialist work in direct sessions, with file outputs and independent validation.
user-invocable: false
---

# Direct specialist session

Perform the role in your definition. The brief gives a bead, input paths, output path and outcome;
it supplies no procedures or schema. Load the skills in your frontmatter and read the applicable
contract before writing. The artifact-handoff skill is the shared producer/reviewer authority.
Write the result file; Python handles validation, acceptance, fingerprints and pipeline state.
Do not invoke a Workflow, another agent, a command runner, a submission helper or StructuredOutput.
Do not create receipts, revision bindings or checkpoint sidecars. If resumed, inspect and continue
the existing result and input files; retain completed valid work.

Only assigned files are writable. Reviewers may write their result, never the reviewed source.
Never write arc42 section 2, expose secrets or touch apps/marketing repositories. Never run keeper
or supervisor. Agents do not write pipeline beads; Python owns those writes. If reading beads is
needed, use the central atw-bd wrapper from beads-contract. No agent creates a bug or loose Task.
Read repository AGENTS.md before an authorized repository edit; input-only reads do not require
loading every repository's instruction tree.

Missing inputs are named dependencies, not permission to invent facts. Distinguish observed
facts, assumptions and unresolved questions in the artifact's supported fields. Do not mark your
own work approved. In elaboration, repository code is evidence of current design detail only;
the matrix is the sole built-state record, and Python derives implementation work from it.

## Resource use and incremental review

- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.
- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.
- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.
- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.

## Technical gaps are decided, not escalated

Where the approved or effective architecture, a requirement or an owner answer is silent, unclear or self-contradictory on a technical matter, decide it by best practice, with AWS Well-Architected guidance and AWS documentation as the evidence (see AWS evidence authority below). Record the decision, the gap it closes and its cited evidence in your result, and continue. A technical matter is any question of how the system works: services, patterns, interfaces, data, values and limits, security and privacy controls, cost and operations. A recorded decision is a claim reviewers check like any other; it is not an open item.

Owner-only facts (credentials, money and destructive actions outside AWS dev), irreconcilable business requirements and section 2 conflicts go through the caller's owner channel. Technical choices remain with the specialists. Never put a technical question to the owner or any person, and never hold work waiting for a technical answer.

## The approved architecture is authoritative

The approved (effective) architecture and the owner's answers are authoritative. Older documents, repository READMEs and existing code are evidence of the current state: they show what exists and what still has to change, never that the approved architecture or an owner answer is wrong. Where they disagree with the approved architecture, the approved architecture holds and the difference is work to plan, not a conflict to raise. The approved architecture changes only through a reviewed target backed by requirements and evidence, or a reviewed correction from what a Story built.

## AWS evidence authority

Before any AWS claim, design choice or question, check the AWS MCP Server documentation tools (`search_documentation`, `read_documentation`, `retrieve_skill`) and the relevant AWS plugin skills (`aws-core:*`, for example `aws-core:aws-cdk`, `aws-core:aws-serverless`, `aws-core:aws-iam`, `aws-core:aws-networking`, `aws-core:aws-well-architected-review`), including the applicable Well-Architected principles. A question AWS documentation can answer is answered from it and never reaches the owner. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.

Apply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Where AWS guidance conflicts with a business requirement or a section 2 constraint, the requirement or constraint holds: record the conflict and the design that honours it, and do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.
