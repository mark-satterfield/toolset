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
| 9 | Write the Story document | script `spec_authoring.story_document`; first `design_gaps.hold_open` | `spec`, `data model`, `criteria`, `repository context` | when a document holds an open design gap below the round limit: `<arch-work>/design-gaps/open/<slug>.json`, and the repository's steps wait for one gap round (below); a row answered and held again, or every row at the limit, moved to the document's `## Decided at build` table and `<arch-work>/design-gaps/leftover/<slug>.json`, with a warning note; otherwise the section `## Architecture and design documents` at the end of each of the three spec documents; `story-<slug>.json` | file `story document`, value `decision ids` |
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
Story builds is the context's `buildScope`, read from who builds the entry and its verified flag
(`spec_authoring.entry_scope`), never from an architecture delta: `addition` when a Task of
another Epic builds the entry (the item's `builtBy`, carried on the row), so the spec states only
this Epic's addition to it and links the owner's spec (`builtBy[].specPaths`) for the rest, and
each spec document, the criteria included, lists under `usedAsBuilt` in its front matter the
`addition` entries it specifies no addition to (`document-front-matter.schema.json#/$defs/UsedAsBuilt`;
a document `spec_authoring.not_applicable` writes lists every one, and
`spec_authoring.document_check` refuses an id that is no `addition` entry), and the Story document
carries as `usedAsBuilt` the entries every document lists (`spec_authoring.story_used_as_built`,
`story-document.schema.json`); `delta` when the entry carries
the verified mark, so nothing it must be built as has changed since its last build and test, and
the spec covers this Epic's own work for it alone; `full` when the entry is not verified (a
change cleared the mark, or it was never built), and the spec covers all the work that brings the
build up to the entry's approved architecture. `componentDocuments` lists every
architecture and design document `atw-matrix documents` joins to the stacks and entries the
Story builds (`spec_authoring.component_documents`); step 9, after every correction, ends each
of the three spec documents with a link to each (`spec_authoring.link_documents`, which replaces
the section on a rerun) and lists them in the Story document, so whoever builds from the spec has
the full architecture of the component.

Before it writes anything, the context step checks that no other Epic came to own an entry the
span planned (or stopped owning one) since the span ran (`build_ownership.refuse_ownership_drift`);
on a change the span and every step after it run again, so no spec session works on a stale
snapshot.

The contracts and the data model must have the front matter of
`document-front-matter.schema.json#/$defs/SpecDocument`, whose `decisionIds` each resolve to a file
under the architecture root; the criteria must have the structure that "A criteria document's structure" in
the `acceptance-criteria` skill states (`criteria_document`). A document that fails its check
goes back to its session once, with the errors as an input. Accepting a document records the
document and nothing else: its citations stay in its `decisionIds` and reach the Story through
step 9, and nothing is written to the matrix, whose architecture side only arc42 (through
`sync-documents`) and the architect's recorded design write.

A detail a Story needs that no approved document states has one of three kinds. A name the
project's naming standard produces (kind A) the author builds with the naming command and writes
in the spec. A detail local to the one repository (kind B) is a row of the table under the
document's `## Decided at build` heading, with the kind `B`: the build decides it and it blocks
nothing. A detail that crosses a boundary, contradicts another document or the TRD, or is invalid
as stated (kind C) is a design gap: its author records it as one row of the table under the
document's `## Design gaps` heading and does not settle it. The authors and `spec-reviewer` check
every element against every criterion, I1 to I7, in one pass, so every kind C gap is found in the
first round. `spec-reviewer` checks the classification (a kind C row filed as decided at build is
a finding that moves it to the gap table; a name filed as a gap or decided at build is a finding
that builds it) and holds every gap row to the approved documents, sending a row the documents do
settle to its author and leaving a real gap for the step below. Step 9 reads every gap row
(`design_gaps.open_gaps`) before anything else. A row left open stops the repository before its
Story and Tasks: the step files the repository's gaps at `<arch-work>/design-gaps/open/<slug>.json`
and raises `DesignGapError` (a `StaleInputError`) naming the repository's context step (step 1)
as the writer and the repository's container as its scope, however often it was set back in the
dispatch already. The other repositories' containers running at the same time are not stopped at
once: each that still holds its own step 9 not run goes on to it, and so does every sibling
container beyond the session cap, so its gaps are filed too
(`journal_run.JournalRunner._before_gap_check`, `_run_to_gap_checks`). Once every container has ended, the runner, in
one journal change, adds one gap round to the end of the Architecture container
(`design_gaps.gap_round`): the solutions architect's step "Answer the design gaps the spec stage
found", an index and a check; it plans the outermost step "TRD" (`trd.confirm`) again, so the TRD
is confirmed against the answered documents; and it sets back each repository that held a gap,
from its context step, within its own container. Nothing else is set back: the span, the
repositories without gaps and their Stories keep their state. The architect's step is handed every
repository's file as `design gaps` and decides what fills each gap; its result answers each row
under `gapAnswers` (the repository, the row exactly as filed, the decision and the ids of the
`facts` that state it), and the output check sends a row without an answer, or an answer naming a
fact the result does not hold, back to the same session (`design_gaps.unanswered`). The check
looks only at the rows handed to the step: answers an earlier round settled stay in the result,
which is updated in place, and are not checked again. Its accepted result (with no further round)
moves the files to `<arch-work>/design-gaps/settled/<step>/` and records, for each repository, one
more round and each row as answered in `<arch-work>/design-gaps/answers.json`
(`design_gaps.settle`); the architecture maintainer writes the decisions into the documents, the
check plans their promotion, with the TRD write before it only when the result's TRD changes
changed (`architecture.md`, "The check"), and the repositories that held gaps are specified again
against the settled design. No impact analysis runs in the round. When an answer changes the
elements the Stories build (the result's `addedOrChangedElements` and `unchangedWorkElements`
name other entries than the span's items), the repository's context step raises
`ScopeChangedError` naming the span step, so the span and every step after it run again
(`build_ownership.refuse_scope_drift`), counted with ownership changes. The Epic never fails on a design gap. A row the architect already answered that a repository's
documents hold again is carried to the build, and so is every open row of a repository whose gaps
have gone to the architect `design_gaps.MAX_ROUNDS` (2) times; a row never handed before, below
that limit, gets its own round. Carrying a row (`design_gaps.carry`) moves it from the document's
gap table to its `## Decided at build` table with the kind `C, left open after 2 architect
rounds`, adds it to `<arch-work>/design-gaps/leftover/<slug>.json`, removes the repository's open
file, and emits a warning note, "pipeline defect, design gaps after 2 rounds", naming the Epic,
the repository and the rows, which the supervisor's ledger and dashboard show. A repository at the
limit is never handed to the architect again (`design_gaps.handed`). The rounds are counted from
every record of them (`design_gaps.answers`): `answers.json` in either form it has had (a bare
count, or `rounds` with `rows`) and the settled folder, one round per settled step folder that
holds the repository's file, the larger count standing.

The Story document's description lists every decided-at-build row of its spec documents, so the
Story bead carries them; the decomposer gives each row to the Task that builds its element (its
`specSections` and description), the Task's implementer decides it, and the Story's architecture
comparison records the chosen value (`built_version`, `decidedAtBuild`). The Task dependency
mapper is handed the leftover files: a carried value two Stories' Tasks use orders the providing
Task before each using Task, and the edge write reports every carried row no edge orders
(`task_edges`).

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
stands as ruled. The output check of each correction and revision session is the account's schema
and every document of the round's own check, all reported together, so a document that no longer
passes is handed back in the session's one correction; a second failure fails the step.

## The Story bead and its journal

Step 10 finds the Story under the Epic by its elaboration key `story:<slug>`. A Story that exists
is updated where it differs and is open; a second Story is never created, so the step is safe to
run again after an invalidation. The Story's metadata records, for each spec document and the
Story document under the project root, its path and the SHA-256 of its bytes.

The same step creates the Story's journal (pipeline `deploy`) with its first step done and holding
the files `spec`, `data model`, `criteria`, `ui sources` when present, `TRD` and `story document`.
