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
whose name matches the frontend template.

| # | Description | Performed by | Reads (artifact) | Writes | Records (artifact) |
|---|---|---|---|---|---|
| 1 | Gather what the repository builds | script `spec_authoring.context` | `span`, `elements`; the dispatch arguments (PRD, design system) | `spec-<slug>.context.json` | value `repository`, file `repository context`, file `prd`; plans steps 2 to 11 |
| 2 | List the UI bundles (frontend) | script `cdsbundles.list_bundles` | the design system's packages directory | `spec-<slug>.bundles.json` | file `ui bundles` |
| 3 | Choose the UI design source of each UI item (frontend) | agent `api-specification-author` | `TRD`, `span`, `elements`, `prd`, `ui bundles`, `repository context` | `candidates/spec-<slug>.ui.json` | file `ui sources as authored` |
| 4 | Check the UI design sources against the bundles (frontend) | script `spec_authoring.normalize_ui` | `ui sources as authored`, `ui bundles`, `repository context` | `spec-<slug>.ui.json` | file `ui sources`, value `warnings` |
| 5 | Write the API, event and error contracts | agent `api-specification-author` | `TRD`, `span`, `elements`, `prd`, `ui sources` when there are any, `repository context` | `spec-<slug>.md` | file `spec` |
| 6 | Write the data model | agent `data-model-specification-author` | `TRD`, `span`, `elements`, `prd`, `repository context` | `spec-<slug>.data-model.md` | file `data model` |
| 7 | Add the UI design sources to the contracts (frontend) | script `specui.spec_ui_append` | `spec`, `ui sources` | the section `## UI design sources` of `spec-<slug>.md` | file `spec` |
| 8 | Write the acceptance criteria | agent `acceptance-criteria-writer` | `TRD`, `span`, `elements`, `prd`, `spec`, `data model`, `repository context` | `spec-<slug>.criteria.md` | file `criteria` |
| 9 | Review the specification documents | agent `openapi-contract-reviewer` | `spec`, `data model`, `criteria`, `TRD`, `repository context`, the criteria file | `spec-<slug>.review.json` | see "The review" |
| 10 | Write the Story document | script `spec_authoring.story_document` | `spec`, `data model`, `criteria`, `repository context` | `story-<slug>.json` | file `story document`, value `decision ids` |
| 11 | Write the Story bead | script `beadwrite.write_story` | `story document`, the three spec documents, `span`, `elements` | the Story bead; the Story's journal | value `story`, value `story write`, value `decision ids`; plans the repository's container under Tasks |

Steps 5 and 6 are consecutive agent steps whose inputs are done, so their sessions run together.

The repository context (`spec-<slug>.context.json`) holds the repository, the items of what the
Story builds (each event item with its `trigger` and `publishedBy`), the stacks the Story builds
in, what `atw-matrix story-scope` returns for each, the documents and headings to read, the shared
capabilities, the architect's `notesForSpecs`, and `dependsOn` from
`repo_scoping.build_context` (grouped by `storyKey`), as `task-decomposition.md` describes it.
`dependsOn` is context, never work.

The contracts and the data model must have YAML front matter whose `decisionIds` each resolve to a
file under the architecture root; the criteria must be non-empty. A document that fails its check
goes back to its session once, with the errors as an input. Accepting a document records the
document and nothing else: its citations stay in its `decisionIds` and reach the Story through
step 10, and nothing is written to the matrix, whose architecture side only arc42 (through
`sync-documents`) and the architect's recorded design write.

The Story document lists what the Story builds, one line per item: an event as
`E<n>: <name>, published by <publishers>: <trigger>`, any other item as
`E<n>: <name>: <purpose>`, the purpose being the matrix entry's.

## The review

One reviewer session per repository checks the three documents against the implementation-level
criteria of `skills/effective-architecture/review-criteria.json`. What follows is planned by the
step whose result calls for it, one step at a time, after that step:

| Step | Planned when | Performed by | Records |
|---|---|---|---|
| Review | always | `openapi-contract-reviewer` | file `spec review`; value `spec review findings` (the findings held against an implementation criterion); value `spec review findings dropped` (the others, which go no further) |
| Correct a document for the review's findings | the document has a finding, or is derived from a document that changed in this pass | the agent that wrote the document, continuing the session in which it wrote it | file `spec correction`, the document again, value `spec review document worked on` (whether it changed, which findings it disputed), value `warnings` |
| Rule on the disputed findings | an author disputed a finding of its own document | `spec-decider` | file `spec ruling`, value `spec review findings upheld`, value `warnings` |
| Revise a document to the ruling | the document has an upheld finding, or is derived from a document that changed in this pass | the agent that wrote the document | file `spec revision`, the document again, value `spec review document worked on`, value `warnings` |

Documents are worked on in the order they are written: contracts, data model, criteria. The
criteria are derived from the other two, so a change to either sends the criteria to their author
in the same pass. A finding goes to an author once. A finding disputed again after the ruling
stands as ruled. After each correction and revision the document must pass its own check again, or
the step fails.

## The Story bead and its journal

Step 11 finds the Story under the Epic by its elaboration key `story:<slug>`. A Story that exists
is updated where it differs and is open; a second Story is never created, so the step is safe to
run again after an invalidation. The Story's metadata records, for each spec document and the
Story document under the project root, its path and the SHA-256 of its bytes.

The same step creates the Story's journal (pipeline `deploy`) with its first step done and holding
the files `spec`, `data model`, `criteria`, `ui sources` when present, `TRD` and `story document`.
