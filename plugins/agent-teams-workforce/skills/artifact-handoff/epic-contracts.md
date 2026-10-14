# Epic artifact contracts

This is the shared reading, writing and completion contract. Select your assigned artifact below;
read its linked schema, not a copy in a workflow brief. JSON Schema defines fields/types; the
completion rules define meaning. Producers and reviewers use exactly the same rules. Python
validates accepted files; human-readable summaries are navigation, never evidence substitutes.
A JSON schema must not be pasted into a brief. Input facts such as the
repository and validation errors travel in referenced files.

All architecture agents also read architecture-baseline/review-standard.md, which holds every
criterion a document is judged by. `aws-solutions-architect` is responsible for the architecture
an Epic needs; the files it and its team hand on are in the `architecture-work` section and the
sections after it.

## placement

Schema: [placement.schema.json](schemas/placement.schema.json).

Fields and interpretation: placements each name one repository with repoPath, repoName, the itemIds of what its Story builds, frontend and rationale; missingRepos names a repository the inventory lacks with name, template, purpose and itemIds. Python writes it from the architect's result: what the Stories build is the result's addedOrChangedElements with each event's architecture-side publishers, each in the repository of the stack the architecture side places it in (for an event, its publisher's stack); a stack that names no repository is given the name the project's naming rules give it, and a repository the inventory lacks is created from the template its stacks' type names before the file is written. Complete means every thing the Stories build is in exactly one placement and every placement has a repository path. No agent writes it.

## tasks

Schema: [tasks.schema.json](schemas/tasks.schema.json).

Fields and interpretation: tasks have title and task build contract fields; local keys are T1...; acceptanceCriteria and definitionOfDone cite stable ids in the criteria document, not copied requirement prose. requirementIds include the items of what the Story builds and applicable TRD ids; decisionIds cite read architecture views, specPaths/specSections cite source docs, reuses names retained same-Story work and blockedByExternal names other-Epic blockers. A Task is a coherent unit of build work: one Task covers several of the things the Story builds, every thing the Story builds is cited by some Task, and it is never one Task per thing; a Task that cites an event also cites a service or component that publishes it, and no Task covers events alone (the output check refuses a Task that covers one thing when the Story builds two or more, a Task that cites an event and none of its publishers, and a Task that covers only events). surfaces are api-contract,event-chain,auth,performance,web-ui,ios,android,cross-platform-mobile,ml,data-pipeline; [] means none, null unknown. testStrategy is the source pyramid/coverageThreshold/envMatrix/source or null. edges from prerequisite to dependent use local keys. scores provide key/jobSize/sizeLow/sizeHigh/sizeConfidence/rationale under wsjf; valid positive range contains jobSize and confidence is 0..100. Complete means every item cited, at least one Task and every Task sized; Python checks semantic completeness after schema validation.

## tasks-correction

Schema: [tasks-correction.schema.json](schemas/tasks-correction.schema.json).

Fields and interpretation: tasks use the same item fields, new keys N1...; edges only target new Tasks; scores cover new keys and exact saved keys reported unsized. Complete means the specific uncited work and unsized Tasks are repaired without rewriting retained Tasks. noWork is forbidden. Python merges and renumbers new keys then rechecks coverage and sizes.

## task-deps

Schema: [task-deps.schema.json](schemas/task-deps.schema.json).

Fields and interpretation: edges name from (prerequisite), to (dependent), kind data/contract/infrastructure/event-flow and reason; keys are S<i>-<local key>. acyclic and cycle describe the combined graph. Complete means justified cross-Story build relationships, no duplicate closure edges or invented repository dependencies; Python validates keys and prevents cycles.

## spec-ui

Schema: [spec-ui.schema.json](schemas/spec-ui.schema.json).

Fields and interpretation: uiItems use item (the id of an item the Story builds), designSource, reason, artifact (kind/slug), bundle, buildSpec and sections; optional mocksDir and warnings survive normalization. Source bundle must match the newest supplied kind/slug and its declared buildSpec/sections; cds designs with the configured design system; none changes no design. Complete means all relevant UI items the Story builds are represented and citations agree. Python normalizes invalid sources/bundles, supplies missing artifact identities and drops unknown item ids with warnings, then appends the UI section. No schema-level enum blocks those specified normalizations.

## architecture-views

Fields and interpretation: The arc42 documents of the effective architecture: Markdown with the catalog front matter view_type, scope, subject, shows and lifecycle_state, and Mermaid where the document's type needs a diagram. They meet the architecture-level criteria of architecture-baseline/review-standard.md; detail the standard places in the TRD or the specs stays out of them. `architecture-maintainer` writes them from the solutions architect's write request with lifecycle_state in-review; Python sets effective and commits after review. Section 2 is the owner's.

## trd-document

Fields and interpretation: Nonempty UTF-8 Markdown with a YAML front matter list decisionIds of the arc42 paths, with optional #heading, that its requirements cite. Each requirement has a stable id, a kind (obligation or reuse), a statement with its checkable value, a source and the matrix id of the element it applies to. `trd-author` writes it at the path the architecture context names, drafts it early and updates it in place. Complete means every obligation the PRD and the architecture impose on an element is sourced, and every shared capability the design uses has its reuse requirement. Python confirms that every decisionIds entry resolves and records the TRD on the Epic bead.

## spec-document

Fields and interpretation: Nonempty UTF-8 Markdown with decisionIds frontmatter. Describe every placed API/event/error/UI contract in this repository, exact fields and failure behavior, tracing PRD/TRD/views. No applicable surface gives a reasoned not-applicable document. Complete means every placed contract is specified or explicitly not applicable; Python checks all view paths resolve.

## data-model-document

Fields and interpretation: Nonempty UTF-8 Markdown with decisionIds; owned stores, access patterns, keys/indexes, retention/consistency and capacity assumptions traced to PRD/TRD/views. Derive access patterns from these sources. Complete means applicable data obligations are specified (or reasoned not-applicable), with resolvable citations.

## criteria-document

Fields and interpretation: Nonempty UTF-8 Markdown with stable acceptance criterion and DoD ids linked to PRD/TRD/spec sections. State observable pass conditions and preserve source testStrategy if present. Complete means applicable behavior/boundaries and non-unit-testable human checks are represented without invented scope. Tasks reference these ids.

## spec-review

Schema: [spec-review.schema.json](schemas/spec-review.schema.json).

Fields and interpretation: findings each name id, document (spec, data-model or criteria), criterion (an implementation-level id of architecture-baseline/review-criteria.json), location, observation, correction and doneWhen; summary says what was reviewed. The one reviewer reads the three specification documents, the TRD, the repository context and the criteria file. Complete means every item the Story builds was checked against every implementation-level criterion that applies to it; an empty findings list means the documents meet them. Python drops a finding whose criterion is not at the implementation level.

## spec-correction

Schema: [spec-correction.schema.json](schemas/spec-correction.schema.json).

Fields and interpretation: disputes name findingId, reason and evidence; summary says what changed. The author of a document writes it for its one correction: every finding on its document that it does not dispute is corrected in the document itself, at the document's path. Complete means each finding on the document is either corrected so that its doneWhen holds or disputed with a checkable reason, and a document derived from a corrected one agrees with it. The same contract carries the author's revision after a ruling, where the ruling's directives are applied and nothing is disputed.

## spec-ruling

Schema: [spec-ruling.schema.json](schemas/spec-ruling.schema.json).

Fields and interpretation: rulings name findingId, ruling (finding-stands or document-stands), reason and directive; summary says what was ruled. Complete means every disputed finding has exactly one ruling, grounded in the review, the author's reason and the criterion the finding names, with a directive for each finding that stands. A dispute with no ruling leaves the document as its author left it.

## closure-edges

Fields and interpretation: Python-derived prerequisite edges between Tasks of different Stories, from the requires relations of the span elements and the Task ids. These edges stand; task-dependency-mapper adds only nonduplicate justified edges. Complete means every resolved prerequisite relation is represented with qualified task keys.

## task-edges

Fields and interpretation: Python edge write report summary with blockers, added,removed,standing,rejected; complete means valid non-cycling resolved Task edges were written, not merely proposed.

## matrix

Schema: [matrix.schema.json](schemas/matrix.schema.json).

Fields and interpretation: One JSON file with three members, `version`, `entries` and `relationships`. The entries are Epics and their requirements, features, constraints, disagreements, arc42 documents, services, components, infrastructure, events, stacks, packages and layers; each entry and each relationship states its side, `architecture` or `repository`. What kinds exist is data, in `schemas/matrix-kinds.json`. It is read and written only through `atw-matrix`; Python reads its generated form, `scripts/matrix_contract.py`. The role of the session (`ATW_MATRIX_ROLE`) decides which commands it may run. The one code mark is `verified`, with the commit, which the build driver sets when a Story's code has merged; an entry without it may still have to be built.

## repo-creation

Fields and interpretation: Python created records name,repoPath,template,itemIds,existed plus failures name/template/itemIds/error/ownerFact. Complete means each missing owner has a actual checkout/remote or explicit failure; not an agent permission to create repositories.

## bundles

Fields and interpretation: Python list of supplied CDS bundles including identity kind/slug, newest createdAt, bundle path and buildSpec. Complete means usable supplied sources are enumerated; loose mocks are context, never a higher design authority than a matching bundle.

## story

Fields and interpretation: Python title,description,decisionIds: repository name plus PRD title, placed ids/elements and three spec paths. Complete means the repository container references the finished spec set; no agent Story narrative or outOfRepoFindings.

## task-items

Fields and interpretation: Python items array with id, element, views, requires and kind, joined from the placement and the span elements. Complete means all and only this Story repository's work is represented, including prerequisites.

## task-context

Fields and interpretation: Python snapshot. existingTasks holds the Story's started Tasks and those elaboration did not write, with keys,ids,titles,status and relevant descriptions. stacks holds the matrix ids of the stacks the Story builds in; stackWork holds, for each of them, what `atw-matrix work --id <stack id> --not-epic <epic id>` returns: the open Tasks of other Epics that name the stack or an entry it holds, each with its Story and Epic. sharedCapabilities holds what `atw-matrix uses --ids` returns for the entries the Tasks build. Existing started/closed/deferred work is preserved; other-Epic overlap adds blockers, never suppresses Tasks. A Task states the matrix ids of its stack, what it builds and the shared capabilities it uses, exactly as this file gives them.

## filed-documents

Fields and interpretation: Driver copies accepted UTF-8 spec documents to vault paths after elaboration done and records vault metadata. Complete means filed bytes represent accepted source artifacts; agents do not file them.

## run-manifest

Fields and interpretation: Python run record execution identity, sessions/phase/agent/model/effort/timing/result and failures. Complete means each started/resumed session is attributed once; see DESIGN 4 and runner contracts.

## handback

Not an agent artifact. `orchestrator/run.py` writes it and the driver reads it; no agent session produces or reads it. Its one definition is `orchestrator/core/handback_contract.py`.

## events

Fields and interpretation: Python JSON-line ledger events expose phase/verdict/session/process facts; driver translates existing callbacks. Complete means truthful observed transitions, no inferred running state.

## out-of-scope

Fields and interpretation: The artifacts of the owner-run portfolio workflows (WSJF scoring, dependency assessment, Task dependency assessment) are produced by those workflows, not by Epic elaboration. No Epic session or contract is inferred from those rows.

## architecture-work

The files of the architecture team that `aws-solutions-architect` leads. Every shape is defined once, in [architecture-result.schema.json](schemas/architecture-result.schema.json); each file below has its own schema file that refers to its definition there. Python reads them through `scripts/architecture_work_contract.py`, which is generated from that schema.

## architecture-state

Schema: [architecture-state.schema.json](schemas/architecture-state.schema.json).

Fields and interpretation: needs each name what the PRD needs, its PRD requirement headings, a state (approved, disagreement or missing), the statements judged and the judgment; conclusion is `baseline-meets-every-need` or `work-remains`, a starting point and never a result. `aws-solutions-architect` writes it before anything else. Complete means every thing the PRD needs of the architecture has one entry, and the conclusion follows from the states.

## architecture-result

Schema: [architecture-result.schema.json](schemas/architecture-result.schema.json).

Fields and interpretation: conclusion (`no-change-needed`, `changes-designed` or `unsettled`; every one goes through the check and the review); the features with the PRD requirements each serves; noFeature, every requirement no feature serves, with the reason; the new elements; each shared capability an element uses; the facts with their one home; the settled disagreements; one answer for every criterion whose level is architecture or technical-requirement; notesForSpecs; unsettled matters; reviewSignals; costEvidence. Complete means every such criterion is `satisfied` at a place that exists or `not-applicable` with its reason, every fact has one home, and `unsettled` is empty unless the conclusion is `unsettled`. Every feature and element the result names is an entry the architect already recorded in the matrix, and every requirement of the Epic is served by a feature or listed in noFeature: the step that accepts the result fails otherwise. A script selects the reviewers from reviewSignals by the `appliesWhen` rules of architecture-baseline/review-criteria.json, and reads from the matrix which documents are in review.

## specialist-request

Schema: [specialist-request.schema.json](schemas/specialist-request.schema.json).

Fields and interpretation: kind (`question` or `task`), the request, its bounds, the PRD sections and arc42 headings it concerns, the elements whose code is trusted, and the answer path. `aws-solutions-architect` writes one for each design specialist or diagram author it starts; `architecture-team-lead` writes one when it asks for an opinion. Complete means one gap of this PRD is stated so that it can be answered without reading anything the request does not name.

## specialist-answer

Schema: [specialist-answer.schema.json](schemas/specialist-answer.schema.json).

Fields and interpretation: the answer in one sentence; reasons, each with its source; assumptions; alternatives only when asked; needs (another specialty to ask); for a task, decisions as design facts with their arc42 section; for a diagram task, diagrams as Mermaid source with their home; notesForSpecs. Complete means the request is answered and nothing else is.

## trd-request

Schema: [trd-request.schema.json](schemas/trd-request.schema.json).

Fields and interpretation: mode (`draft` or `update`); the PRD, TRD and state paths; for a draft the approved headings and the shared capabilities used; for an update the changes by requirement id; the answer path. `aws-solutions-architect` writes it.

## trd-answer

Schema: [trd-answer.schema.json](schemas/trd-answer.schema.json).

Fields and interpretation: mode; the requirement ids written or changed; requirements, for mode `draft` every requirement the TRD states with its id, kind, statement, source and appliesTo (a matrix id, or an empty string for the Epic as a whole), which Python records as constraints, and empty for mode `update`; noSource, the obligations the PRD implies that neither the PRD nor the approved material gives a source for. Complete means the TRD at the request's path holds exactly what the request asked, and every unsourced obligation is in noSource and not in the TRD.

## write-request

Schema: [write-request.schema.json](schemas/write-request.schema.json).

Fields and interpretation: the facts, each with its statement, reason, one home and the documents that link to it; the restatements to replace with links; the settled disagreements to apply; the diagrams to place; the result path. `aws-solutions-architect` writes it for `architecture-maintainer`.

## write-result

Schema: [write-result.schema.json](schemas/write-result.schema.json).

Fields and interpretation: the headings changed and created, the links added, the restatements removed, belowArchitectureLevel (entries not written because they belong in the TRD or the specs) and notApplied with the reason. Complete means every entry of the request is written in its home, returned in belowArchitectureLevel or listed in notApplied.

## scope-review

Schema: [scope-review.schema.json](schemas/scope-review.schema.json).

Fields and interpretation: passed (the items that meet every criterion that applies to them); findings, each with its criterion id, item, observation, location, correction and doneWhen; dependsOnApproved; alternativesRequested. Complete means every item of the reviewer's scope (the `review-scope` section) is in passed or has a finding, a dependsOnApproved report or an alternative request. Python takes a finding whose item is outside the scope out of the file, keeps the review as returned beside it, and counts it.

## lead-routing

Schema: [lead-routing.schema.json](schemas/lead-routing.schema.json).

Fields and interpretation: one entry for each finding, alternative request or unsettled matter: who raised it, the routing (`reject`, `correct`, `opinion`, `competing-design` or `decider`), one sentence of reason, and the journal steps added for it. `architecture-team-lead` writes it before it adds a step.

## architecture-question

Schema: [architecture-question.schema.json](schemas/architecture-question.schema.json).

Fields and interpretation: the matter, its kind, and the two or more positions, each with its statement, evidence and cost. `architecture-team-lead` writes it for `architecture-decider`; it is the shape of an `unsettled` entry of the architecture result.

## architecture-ruling

Schema: [architecture-ruling.schema.json](schemas/architecture-ruling.schema.json).

Fields and interpretation: the matter, the position that stands, the reason, what the losing position must change, and owner concerns (a business conflict or a section 2 conflict only). Complete means the ruling rests on the evidence the two positions gave. It is recorded in the matrix as the settlement of the matter.

## built-comparison

Schema: [built-comparison.schema.json](schemas/built-comparison.schema.json).

Fields and interpretation: differences, each with the element, the code location, the approved heading, the difference and the built-difference document written for it; filesWritten. `built-architecture-comparer` writes it for one Story. An empty differences list means the code the Story built matches the approved architecture.

## span-elements

Schema: [target-report.schema.json](schemas/target-report.schema.json) `$defs/DeltaResult`.

Fields and interpretation: Python writes it from the matrix when it reads the repository span: one item for each element the PRD's features are realized by, and for each element those depend on, whose code no pipeline has built. An item has an id, the element's name, the documents that describe it, its repository, its kind and the items it requires and is required by. The spec authors and task-decomposer read the items of their repository; ids are read exactly as written.

## step-journal

Not an agent artifact file format. One journal per bead lists the steps a pipeline runs for it; it alone decides where a run begins. Its one definition is `skills/pipeline-contracts/schemas/step-journal.schema.json`, generated into `skills/pipeline-contracts/scripts/step_journal_contract.py`. An agent changes it only through `atw-step-journal`, as the subagent-contract skill describes.

## architecture-context

Schema: [architecture-context.schema.json](schemas/architecture-context.schema.json).

Fields and interpretation: Python writes it when the run is opened: the Epic, the PRD path, the architecture root, the section 2 folder, the vault commit the matrix is synced to, the matrix command, the paths of the state file, the result file and the TRD, and the folder for request and answer files. `aws-solutions-architect` is handed it as `context`.

## check-result

Schema: [check-result.schema.json](schemas/check-result.schema.json).

Fields and interpretation: valid, problems (one sentence each), unansweredCriteria and corrections. Python writes one before each review: the problems of the matrix file, a missing Epic entry, and each architecture or technical-requirement criterion the architecture result leaves unanswered. When it is not valid, `aws-solutions-architect` is handed it as `findings`.

## review-scope

Definition: `ReviewScope` in `scripts/portfolio/matrixreview.py` (what `atw-matrix review-scope --epic` prints) and `ReviewerScope` in `orchestrator/flows/architecture_check.py`.

Fields and interpretation: Python reads from the matrix the documents the Epic reaches that are not effective, and records nothing. The review scope holds `epic`, `requirements`, `features` and `documents`; each document has its `id`, `kind`, `name`, `side`, `lifecycle`, the `headings` reached and, under `reachedBy`, what leads the Epic to it. For each reviewer the criteria file selects, Python writes a ReviewerScope: `bead`, `epic`, `reviewer`, its `groups` and their `criteria`, `documents` (the documents in review, empty when no group of the reviewer covers documents), `trd` (the TRD path when a group covers its requirements, else null) and `signals` (the lists of the architect's result that selected it). A reviewer is handed its own file as `review scope`.

## specialists

Schema: [specialists.schema.json](schemas/specialists.schema.json).

Fields and interpretation: Python lists the agents whose role is design-specialist, each with the description its definition gives. `architecture-team-lead` is handed it as `specialists`.

## promoted-documents

Not an agent artifact. The promotion step writes the documents it set effective, the disagreements it removed and what it could not set effective with the reason; `orchestrator/flows/architecture_promotion.py` writes it as `promoted.json`.
