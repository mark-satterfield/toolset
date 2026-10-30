# Spec authoring: one repository's specification documents and its Story

Code: `orchestrator/flows/spec_authoring.py`, `spec_review.py`, `spec_authoring_ui.py`,
`elaboration_files.py` (names and readers).

Under the outermost step "Specs and Stories" the span step plans one container per repository of
the span, named for the repository, with its first step. That first step plans the repository's
other steps. Every step below is one step of the Epic's journal. A step takes each file it reads
from the artifacts of the steps its `inputs` name, writes its output in the Epic's work directory
`<work>`, and records it as an artifact in the same journal change that marks it done.

## The steps of one repository

`<slug>` is the repository's artifact slug. "Frontend" marks a step planned only for a repository
whose name matches the frontend template and whose Story builds a UI item. Which sessions are
planned follows from the kinds of entry the Story builds (`spec_authoring.story_surfaces`): the
contracts session when it builds an entry of kind service, component, event, file, package or
layer, or infrastructure whose resource type carries an API or event contract (`rest-api`,
`websocket-api`, `api-gateway-`, `appsync-`, `eventbridge-`, `sqs-`, `sns-`,
`bedrock-agentcore-gateway`); the data-model session when it builds infrastructure whose
resource type is a data store (`dynamodb-`, `rds-`, `aurora-`, `neptune-`, `docdb-`,
`elasticache-`, `memorydb-`, `timestream-`, `opensearch-`, `keyspaces-`, `redshift-`); the UI
steps when the repository is a frontend repository and the Story builds a component that is no
AWS resource. An entry the matrix does not hold calls for every session. A document whose
session is not planned is written by step 1a instead.

| # | Description | Performed by | Reads (artifact) | Writes | Records (artifact) |
|---|---|---|---|---|---|
| 1 | Gather what the repository builds | script `spec_authoring.context` | `span`, `elements`, `TRD`; the dispatch arguments (PRD, design system) | `spec-<slug>.context.json`, `spec-<slug>.pack.json` | value `repository`, file `repository context`, file `spec pack`; plans steps 2 to 10 as the Story's entries call for, step 6a for a repository whose stacks hold a DynamoDB store and whose Story builds a data store |
| 1a | Record that the repository builds nothing a document specifies (contracts, data model) | script `spec_authoring.not_applicable` | `spec pack` | `spec-<slug>.md` or `spec-<slug>.data-model.md`, with no citation, listing what the Story builds | file `spec` or `data model` |
| 2 | List the UI bundles (frontend) | script `cdsbundles.list_bundles` | the design system's packages directory | `spec-<slug>.bundles.json` | file `ui bundles` |
| 3 | Choose the UI design source of each UI item (frontend) | agent `ui-design-source-selector` | `TRD`, `span`, `elements`, `ui bundles`, `repository context` | `candidates/spec-<slug>.ui.json` | file `ui sources as authored` |
| 4 | Write the data model | agent `data-model-specification-author` | `TRD`, `span`, `elements`, `repository context`, `spec pack` | `spec-<slug>.data-model.md` | file `data model` |
| 5 | Check the UI design sources against the bundles (frontend) | script `spec_authoring.normalize_ui` | `ui sources as authored`, `ui bundles`, `repository context` | `spec-<slug>.ui.json` | file `ui sources`, value `warnings` |
| 6 | Write the API, event and error contracts, when the Story needs them, then the acceptance criteria, in one session | agent `api-specification-author` | `TRD`, `span`, `elements`, `ui sources` when there are any, `data model`, `spec` when step 1a wrote it, `repository context`, `spec pack` | `spec-<slug>.md`, then `spec-<slug>.criteria.md` (the output; the request names both paths) | file `spec` when it wrote the contracts, file `criteria` |
| 6a | Review the DynamoDB access patterns of the data model (a repository whose stacks hold a DynamoDB store) | agent `dynamodb-schema-access-pattern-reviewer` | `data model`, `TRD`, `repository context` | `spec-<slug>.data-model-review.json` | file `data model review` |
| 7 | Add the UI design sources to the contracts (frontend) | script `specui.spec_ui_append` | `spec`, `ui sources` | the section `## UI design sources` of `spec-<slug>.md` | file `spec` |
| 8 | Review the specification documents | agent `spec-reviewer` | `spec`, `data model`, `criteria`, `TRD`, `repository context`, `spec pack` (and, recorded with the review, `data model review`) | `spec-<slug>.review.json` | see "The review" |
| 9 | Write the Story document | script `spec_authoring.story_document` | `spec`, `data model`, `criteria`, `repository context` | the section `## Architecture and design documents` at the end of each of the three spec documents; `story-<slug>.json` | file `story document`, value `decision ids` |
| 10 | Write the Story bead | script `beadwrite.write_story` | `story document`, the three spec documents, `span`, `elements` | the Story bead; the Story's journal | value `story`, value `story write`, value `decision ids`; plans the repository's container under Tasks |

Step 1a is planned first, before step 2. Steps 3 and 4 are consecutive agent steps whose inputs
are done, so their sessions run together; so are steps 6 and 6a. Step 6 starts once the data
model is written, because the criteria are derived from the contracts and the data model: one
`api-specification-author` session writes the contracts and then the criteria, so the criteria
cost no session of their own. A repository's stacks hold a DynamoDB store when the matrix holds an
infrastructure entry whose resource type starts with `dynamodb-` and whose home is one of the
stacks the Story builds in (`spec_authoring.holds_dynamodb`).

The repository context (`spec-<slug>.context.json`) is written to `spec-context.schema.json`,
which says what each member holds. It holds facts and pointers: the items of what the Story
builds, and for the rest paths (the PRD and the architect's result). `dependsOn` is context, never
work. The spec pack (`spec-<slug>.pack.json`, `spec-pack.schema.json`, written by
`orchestrator/flows/spec_pack.py`) is what the spec sessions read instead of the vault and the
matrix: each stack and entry the Story builds with the Epic its approved flag names; the constraints and
shared capabilities `atw-matrix story-scope` gives for the stacks; the requirements of TRDs that
bind them (a constraint among those with a TRD pointer, and every requirement of this Epic's TRD
that names no entry), with the text of this Epic's; and the OpenAPI, AsyncAPI, GraphQL and JSON
Schema files the repository holds. It holds no heading text: a session reads the text of a
heading the context's `documents` name, only when its work turns on it, with `atw-matrix heading`,
which reads it with `git show HEAD:<path>` from the vault (after promotion, the approved
architecture), never from the working tree.

The authors write specs and design nothing: every detail a spec states (endpoints, payload and
data schemas, keys, parameter names) was decided during architecture and is in arc42, in the
detailed architecture under `detailed/` or in the matrix. What a spec covers for each entry the
Story builds is the context's `buildScope`, read from the entry's verified flag
(`spec_authoring.entry_scope`), never from an architecture delta: `delta` when the entry carries
the verified mark, so nothing it must be built as has changed since its last build and test, and
the spec covers this Epic's own work for it alone; `full` when the entry is not verified (a
change cleared the mark, or it was never built), and the spec covers all the work that brings the
build up to the entry's approved architecture. `componentDocuments` lists every
architecture and design document `atw-matrix documents` joins to the stacks and entries the
Story builds (`spec_authoring.component_documents`); step 9, after every correction, ends each
of the three spec documents with a link to each (`spec_authoring.link_documents`, which replaces
the section on a rerun) and lists them in the Story document, so whoever builds from the spec has
the full architecture of the component.

The contracts and the data model must have the front matter of
`document-front-matter.schema.json#/$defs/SpecDocument`, whose `decisionIds` each resolve to a file
under the architecture root; the criteria must have the structure that "A criteria document's structure" in
the `acceptance-criteria` skill states (`criteria_document`). A document that fails its check
goes back to its session once, with the errors as an input. Accepting a document records the
document and nothing else: its citations stay in its `decisionIds` and reach the Story through
step 9, and nothing is written to the matrix, whose architecture side only arc42 (through
`sync-documents`) and the architect's recorded design write.

The Story document lists what the Story builds, one line per item: an event as
`E<n>: <name>, published by <publishers>: <trigger>`, any other item as
`E<n>: <name>: <purpose>`, the purpose being the matrix entry's.

## The review

One reviewer session per repository checks the three documents against the specs-and-Tasks
criteria of `skills/effective-architecture/review-standard.md`; no criteria file is handed. For a
repository whose stacks hold a DynamoDB store, the data-model review (step 6a) is written to the
same contract with ids D1, D2 and so on, every finding on the data-model document; the review's
own ids are F1, F2 and so on, and its step adds the data-model review's findings to its own. The
correction and revision steps and the decider are handed the data-model review beside the review. The step
keeps a finding only when its criterion id is an id of the specs-and-Tasks level (`implementation`) of
`skills/effective-architecture/review-criteria.json`. What follows is planned by the
step whose result calls for it, in at most three rounds after the review; the author steps of
one round are consecutive agent steps with done inputs, so their sessions run together:

| Step | Planned when | Performed by | Records |
|---|---|---|---|
| Review | always | `spec-reviewer` | file `spec review`; value `spec review findings` (the findings of the review and of the data-model review, when there is one, held against an implementation criterion); value `spec review findings dropped` (the others, which go no further) |
| Correct the documents of one author for the review's findings (round 1, planned by the review) | one of its documents has a finding, or is derived from a document that has one | the agent that wrote the documents, in one session for all of them, continuing the session in which it wrote them | file `spec correction`, each document again, value `spec review document worked on` (its documents and which findings it disputed), value `warnings` |
| Decide whether a finding is disputed (after round 1) | round 1 has a step | script `spec_review.settle` | plans the decider when a record of round 1 names a disputed finding |
| Rule on the disputed findings (round 2) | an author disputed a finding of its own document | `review-dispute-decider` | file `spec ruling`, value `spec review findings upheld`, value `warnings` |
| Revise the documents of one author to the ruling (round 3, planned by the decider) | one of its documents has an upheld finding, or is derived from a document that has one | the agent that wrote the documents, in one session for all of them | file `spec revision`, each document again, value `spec review document worked on`, value `warnings` |

The criteria are derived from the other two documents, so a finding on either sends the criteria to
their author, `api-specification-author`, in the same round: it corrects the contracts and the
criteria in one session, handed the review (and the ruling), and brings the criteria into
agreement with what the findings direct, while the data-model author corrects the data model at
the same time. A finding goes to an author once. A finding disputed again after the ruling
stands as ruled. After each correction and revision the document must pass its own check again, or
the step fails.

## The Story bead and its journal

Step 10 finds the Story under the Epic by its elaboration key `story:<slug>`. A Story that exists
is updated where it differs and is open; a second Story is never created, so the step is safe to
run again after an invalidation. The Story's metadata records, for each spec document and the
Story document under the project root, its path and the SHA-256 of its bytes.

The same step creates the Story's journal (pipeline `deploy`) with its first step done and holding
the files `spec`, `data model`, `criteria`, `ui sources` when present, `TRD` and `story document`.
