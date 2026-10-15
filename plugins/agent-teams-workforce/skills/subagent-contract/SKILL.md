---
name: subagent-contract
description: Bounded specialist work in direct sessions, with file outputs and independent validation.
user-invocable: false
---

# Direct specialist session

Perform the role in your definition. The brief gives a bead, the journal step id, the request,
input paths and an output path. It names only the inputs this step needs. The skills your
definition lists are in your context; read the applicable contract before writing. The artifact-handoff skill is the shared producer/reviewer authority.
Write the result file; Python validates it, records it in the step journal and keeps pipeline state.
Start another agent only when your definition has a `startsRoles` list, and only agents with
those roles, each by its plain front-matter name (`trd-author`, `uml-diagram-author`). An agent
that was started by another agent starts no one. Never invoke a Workflow
or a command runner. When the brief carries ARTIFACT CONTRACT DATA, write the progress
file it names and record a checkpoint or the submission only by running the artifactcontract.py
commands it gives; never write a checkpoint sidecar any other way. The progress file's fields are
defined by the artifact-handoff skill (schemas/checkpoint.schema.json, $defs/Progress). If resumed,
inspect and continue the existing result and input files; retain completed valid work.

Only assigned files are writable. Reviewers may write their result, never the reviewed source.
Never write arc42 section 2, expose secrets or touch apps/marketing repositories. Never run keeper
or supervisor. Agents do not write pipeline beads; Python owns those writes. If reading beads is
needed, use the central atw-bd wrapper from beads-contract. No agent creates a bug or loose Task.
Read repository AGENTS.md before an authorized repository edit; input-only reads do not require
loading every repository's instruction tree.

Missing inputs are named dependencies, not permission to invent facts. Distinguish observed
facts, assumptions and unresolved questions in the artifact's supported fields. Do not mark your
own work approved.

The matrix has one code mark, `verified`, recorded with the commit on a stack, on the entries
in it and on the relationships the code makes real. The build driver sets it when a Story's
code has been built and tested and has passed, including its CI/CD and its CDK. No agent sets
it. No deployed mark and no merged mark exists, and absent means not verified. Verified means
real: the entry or relationship exists, and its code is trusted and is expected to match the
architecture. Not verified means it still has to be made real: use it like any other, and
assume it may still have to be built. Existing code for it is a hint of how something was once
solved and may be stale, and a difference between that code and arc42 is never a discrepancy
and never a finding.

## Helpers and the journal

An agent that starts other agents inside its own session and then continues follows one pattern,
with `atw-step-journal` and the journal file its brief names:

1. Write your own output first: the file your definition names as your first output.
2. When you start your first agent, add it as a child step of your own step
   (`atw-step-journal add --parent <your step> --agent <agent> --description "<what it does>"
   --purpose "<why>"`, where `<agent>` is the agent's own name, the `name` its definition states,
   such as `trd-author`; the command refuses a name no agent definition has), and add one last child step whose description is "Finish", with yourself
   as the agent and your own step in its `inputs`. `--steps-json` adds several child steps in one
   write.
3. Add each further agent as a child before "Finish" (`--after <sibling id>`). Mark each child
   running when you start it (`atw-step-journal start --step <id>`), and record the request file
   you wrote for it at once (`atw-step-journal artifact --step <id> --name request --kind file
   --path <path>`). When the agent returns, record the file it returned as the artifact `answer`
   and mark the child done (`atw-step-journal done --step <id>`).
4. When your work is complete, record your result as the artifact of "Finish", under the name
   your definition gives it, and mark "Finish" done. Your own step is then done.
5. After an interruption the script launches the first child that is not done: an agent left
   running is launched from the `request` file its step holds, and "Finish" is launched as you.
   Launched for "Finish", read your own output, the `answer` files and your partial result, and
   continue.

The names are fixed, because the script reads them: `request` (or `question`, for a question file
to `architecture-question.schema.json`) for what an agent is asked, `answer` for what a specialist
returned, `ruling` for a decider's ruling, `review` for a review. A step is handed the artifacts
of the steps its `inputs` name, and of the steps below them.

An agent that adds steps for the script to run, and starts no agent itself, records the file a
step needs on its own step under the same names and names its own step in that step's `inputs`.

An agent that starts no other agent adds no step.

## Resource use and incremental review

- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.
- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.
- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.
- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.

## Choices are decided, not escalated

Every choice within your task is yours to decide, on the basis `~/.claude/rules/making-decisions.md`
states: engineering best practice, security best practice, the AWS Well-Architected Framework and
what is the right thing to do, found out with your tools and never guessed. Record each decision
and its reason in your result. A choice goes back to your caller only in the cases that file
names. When you cannot do the work correctly, say so in your result with the cause: bad work is
worse than no work. The rest of this section applies that principle to technical gaps.

Where the approved or effective architecture, a requirement or an owner answer is silent, unclear or self-contradictory on a technical matter, decide it by best practice, with AWS Well-Architected guidance and AWS documentation as the evidence (see AWS evidence authority below). Record the decision, the gap it closes and its cited evidence in your result, and continue. A technical matter is any question of how the system works: services, patterns, interfaces, data, values and limits, security and privacy controls, cost and operations. A recorded decision is a claim reviewers check like any other; it is not an open item. No agent ends with "these two documents disagree". Where one statement is in an effective document and the other is not, the effective one stands without discussion. Otherwise the agent responsible for the work settles it and records the settlement in the matrix.

Owner-only facts (credentials, money and destructive actions outside AWS dev), irreconcilable business requirements and section 2 conflicts go through the caller's owner channel. Technical choices remain with the specialists. Never put a technical question to the owner or any person, and never hold work waiting for a technical answer.

## The approved architecture is authoritative

The approved (effective) architecture and the owner's answers are authoritative. Older documents, repository READMEs and existing code are evidence of the current state: they show what exists and what still has to change, never that the approved architecture or an owner answer is wrong. Where they disagree with the approved architecture, the approved architecture holds and the difference is work to plan, not a conflict to raise. The approved architecture changes only through the solutions architect's decisions, written by the maintainer and reviewed, or a reviewed correction from what a Story built.

## AWS evidence authority

Before any AWS claim, design choice or question, check the AWS MCP Server documentation tools (`search_documentation`, `read_documentation`, `retrieve_skill`) and the relevant AWS plugin skills (`aws-core:*`, for example `aws-core:aws-cdk`, `aws-core:aws-serverless`, `aws-core:aws-iam`, `aws-core:aws-networking`, `aws-core:aws-well-architected-review`), including the applicable Well-Architected principles. A question AWS documentation can answer is answered from it and never reaches the owner. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.

Apply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Where AWS guidance conflicts with a business requirement or a section 2 constraint, the requirement or constraint holds: record the conflict and the design that honours it, and do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.
