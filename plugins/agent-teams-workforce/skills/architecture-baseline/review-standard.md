# Shared architecture completion and review standard

## Authority and evidence

Applicable PRD business outcomes, settled owner decisions, section 2 constraints and the relevant
architecture documentation MODEL obligations are the acceptance basis. Read the MODEL and MENU
paths in the architecture root's reference directory; MODEL supplies obligations, MENU supplies
view types. PRD text describes what users get; implementation mechanisms are design inputs, not
business requirements. Technical gaps are decided by specialists with cited evidence. Only
irreconcilable business requirements or section 2 conflicts reach the architecture owner channel.
AWS documentation through the AWS MCP Server and applicable skills establishes AWS behavior;
state assumptions, tradeoffs and regional applicability. Never invent hypothetical scale.

Read effective views, relevant in-review canonical content, open targets and build records for
affected elements at every scope. Check section 2 and non-effective content not represented in
effective views, even for an unchanged capability. An open target's baseline revision may be
stale: validate it against current effective views before reuse. Code on main may supply current
design detail; it never proves built status. No AWS account inventory is required or permitted.
Cite views by absolute path and unique heading, code by repository, main revision and file:line,
external guidance by URL and retrieval/version reference. Unused evidenceRef fields are empty
strings. Reading test source never proves execution. Refresh only changed or insufficient evidence.

## Implementation detail that must be present

For each affected element the retained views identify its repository, stack, runtime/handler (or
chassis superclass/container), owned stores with keys/indexes/access patterns, routes with method,
path and authorizer, and events with envelope, publisher, consumers and delivery path. Show IAM
call boundaries, configuration and published SSM parameter names, timeouts, retries, dead letters,
idempotency keys, and log/metric/alarm names where applicable. A Task can name the repository,
stack, handler, table, route and event without inventing a design. A subject view's frontmatter
records repository (null when genuinely undecided); it also carries view_type, scope, subject,
shows and lifecycle_state. Exact contract fields and identifiers agree across producer/consumer
views; ownership, authorization, retention, failure behavior and cost unit math are explicit.

## Coverage and findings

Inventory relevant subjects from requirements and connected contracts independently of existing
catalog hits: missing views are obligations too. Each coverage row has a stable id, subject,
scope, MODEL obligation, sources, view paths (including absent paths), status, action, reason,
evidenceRefs, disposition and dispositionReason. Preserve IDs across rounds. After authoring,
Present and sufficient is appropriate only with evidence; Not yet applicable pairs with
not-applicable. Unknown obligations use unresolved. Unchanged and not-applicable need concrete
reasons. Mark unrelated-debt only with evidence it affects neither this change nor dependencies;
retain its honest status and summarize it. Independent verification makes it nonblocking.

Reviewers check assigned rows independently and return id/verdict/evidence for each, plus claim
findings and resolutions. A missing obligation can be a finding without a prior author claim.
Each defect cites the violated requirement, constraint or contract, observed evidence, responsible
author and bounded repair. Review only against this standard: no preferred redesign, invented
requirements or demand for unrelated new proposals. Later rounds recheck changed claims/views and
affected dependencies, retaining valid checks. Report new concrete defects even in retained work.

## Draft and three cases

Draft views use the arc42 section layout (03/04 only when affected, 05 building blocks, 06 runtime,
07 deployment, 08 crosscutting). Copy an effective view before editing it at the same relative
path. Extend sufficient shared views; create new ones only for uncovered reader questions.
Catalog every shown element. Name files for their subjects, never a bead, PRD id or date. No ADR,
history, rule or open-item document belongs in a view. Views are Markdown, with Mermaid when
required by their type; verify rendering/readability/semantics/links and report real limitations.

Partial change: future views plus delta/ of the change alone. Entirely new: future views are also
the delta, without a duplicated delta folder. No change: no authored view, one current/future set
and its note, no delta. Python writes baseline.json; agents read it but never edit/list it as an
authored file. Never write 02-architecture-constraints, even inside draft. Writers edit only draft;
only the maintainer integrates approved changes into canonical arc42. Python promotes and commits.

## Sequencing and reconciliation

Read your own entry in the supplied round plan by agentType. It supplies task, files, answers,
claimIds, claimFiles, coverageIds and repairIds. Writers run in plan order before any reviewer;
the last writer reconciles connected views across the round's owned files. There is no designOwner
field or permanent lead author. Resolve cross-view contract contradictions within that scope.
Return claims, coverage and explicit fixed/disputed answers with evidence. Reviewers run afterward
and never edit draft. The decider checks diligence from artifacts, not evidence it generates.
The Check review is round 1 and total review rounds cannot exceed 3, including resumed runs.
