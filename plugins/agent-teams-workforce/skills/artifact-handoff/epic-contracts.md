# Epic artifact contracts

This is the shared reading, writing and completion contract. Select your assigned artifact below;
read its linked schema, not a copy in a workflow brief. JSON Schema defines fields/types; the
completion rules define meaning. Producers and reviewers use exactly the same rules. Python
validates accepted files; human-readable summaries are navigation, never evidence substitutes.
A JSON schema must not be pasted into a brief. Input facts such as round number, own plan entry,
repository and validation errors travel in referenced files.

All architecture agents also read architecture-baseline/review-standard.md. The roster consists
of the nine proposers and three diagram authors in agent-contracts.md, its five architecture
reviewers and two cost reviewers. The coordinator routes; decider and maintainer are separate.

## survey

Schema: [survey.schema.json](schemas/survey.schema.json).

Fields and interpretation: The root fields are subject, subjectReason, capabilities, baseline, openTargets, businessConflicts, coverage and summary. Capability names equal baseline ids; requirement references agree. Every PRD capability is assessed, with evidence for applicable architecture/documentation actions and coverage. The embedded baseline is identical to architecture-baseline.schema.json for saved-survey compatibility. New code.state/implementationAction/disposition are unknown/unknown/undetermined; Python derives built-state work from matrix rows. These fields never prove implementation. Python renders readable survey.md from accepted JSON; the agent writes only its one JSON output.

## architecture-writer

Schema: [architecture-writer.schema.json](schemas/architecture-writer.schema.json).

Fields and interpretation: files lists actual authored draft-relative files, excluding baseline.json. Claims have stable claimId, claim, file, citation, supersedes and evidenceRefs. Answers map each assigned findingId to fixed/disputed with evidence; repairAnswers map assigned repairId to response. coverage uses stable ids and the common standard; businessConflicts only contains irreconcilable business requirements. Complete means assigned views exist, connected contracts agree, findings/repairs are addressed, coverage evidence is honest and the last writer reconciled the round.

## architecture-review

Schema: [architecture-review.schema.json](schemas/architecture-review.schema.json).

Fields and interpretation: findings name claimId, claim, file, verdict (verified/unsupported/wrong), evidence and owner. coverageChecks use row id, verdict and independent evidence; resolutions accept/reject author responses by findingId. repairChecks verify/revise the named repair with files/evidence; cost reviewers include estimates. Complete means every assigned claim, coverage row and repair is checked against the same authoring standard, including required absent views. No invented requirement or design edits.

## coordinator-plan

Schema: [coordinator-plan.schema.json](schemas/coordinator-plan.schema.json).

Fields and interpretation: readyForDecision and reason reflect ledger facts. dispatches name agentType, roster role, task, selectionReason, repairIds, files, answers, coverageIds, claimIds and claimFiles. overlaps gives files, claimIds, agentTypes and reason for necessary reviewer overlap. Complete means bounded file ownership, all outstanding work routed to capable roster members, writers before independent reviewers and no designOwner. The last listed writer reconciles.

## decision

Schema: [decision.schema.json](schemas/decision.schema.json).

Fields and interpretation: round is the absolute saved round (1..3). verdict is approve/return/owner-concern. diligence records check/present/where; choices record dispute/chosen/why; returnTo names agentType/missing; ownerConcerns kind is business-conflict or architecture-conflict with concern/evidence. Complete means every decision is grounded in existing independent evidence and every return is actionable. Python renders decision.md from the accepted JSON.

## maintain

Schema: [maintain.schema.json](schemas/maintain.schema.json).

Fields and interpretation: changedFiles, createdFiles and deletedFiles list actual canonical changes. viewsChecked maps element/view/action (updated/deleted/added/unaffected); constraintIssues and contradictions remain explicit. Complete means approved changes appear at every affected scope with references reconciled, no section 2 edits, and no unreported mutations. Python independently measures changes and controls promotion/commit.

## conformance

Schema: [conformance.schema.json](schemas/conformance.schema.json).

Fields and interpretation: conforms, reviewedFiles, findings (file/finding/evidence), coverageChecks and summary report independent semantic agreement with the approved target. Complete means all measured integration changes and required affected scopes are checked. conforms cannot be true with unresolved concrete defects; the reviewer never edits views.

## closure-walk

Schema: [closure-walk.schema.json](schemas/closure-walk.schema.json).

Fields and interpretation: rootEdges map item to prerequisite element names with evidence. elements lists reached non-root element, views, requiredBy, requires and evidence references. Complete means transitive prerequisite coverage of every root, consistent identities and no built-state judgments. Python classifies the walk using matrix satisfaction.

## closure

Schema: [closure.schema.json](schemas/closure.schema.json).

Fields and interpretation: Python writes prerequisites (walk fields plus state unknown and repository string/null), satisfied (element,state built/deployed,repository,task,commit), rootEdges and summary; publication can add version and roots. Complete means every reached element is classified from the snapshot; missing/unknown rows are prerequisites. A deployed or built row satisfies the element. No deployedBy/plannedBy fields or code search.

## placement

Schema: [placement.schema.json](schemas/placement.schema.json).

Fields and interpretation: placements contains repoPath (null for missing), repoName, itemIds, frontend and rationale. missingRepos names name/template/purpose/itemIds. noCode entries use itemId and reason; spanRationale explains boundaries. Complete means every build item is placed exactly once or legitimately external/configured elsewhere; no omitted work for existing code, missing repositories or other-Epic plans. The steward creates nothing; Python provisions named owners later.

## tasks

Schema: [tasks.schema.json](schemas/tasks.schema.json).

Fields and interpretation: tasks have title and task build contract fields; local keys are T1...; acceptanceCriteria and definitionOfDone cite stable ids in the criteria document, not copied requirement prose. requirementIds include placed work items and applicable TRD ids; decisionIds cite read architecture views, specPaths/specSections cite source docs, reuses names retained same-Story work and blockedByExternal names other-Epic blockers. Every placed item gets work. surfaces are api-contract,event-chain,auth,performance,web-ui,ios,android,cross-platform-mobile,ml,data-pipeline; [] means none, null unknown. testStrategy is the source pyramid/coverageThreshold/envMatrix/source or null. edges from prerequisite to dependent use local keys. scores provide key/jobSize/sizeLow/sizeHigh/sizeConfidence/rationale under wsjf; valid positive range contains jobSize and confidence is 0..100. Complete means every item cited, at least one Task and every Task sized; Python checks semantic completeness after schema validation.

## tasks-correction

Schema: [tasks-correction.schema.json](schemas/tasks-correction.schema.json).

Fields and interpretation: tasks use the same item fields, new keys N1...; edges only target new Tasks; scores cover new keys and exact saved keys reported unsized. Complete means the specific uncited work and unsized Tasks are repaired without rewriting retained Tasks. noWork is forbidden. Python merges and renumbers new keys then rechecks coverage and sizes.

## task-deps

Schema: [task-deps.schema.json](schemas/task-deps.schema.json).

Fields and interpretation: edges name from (prerequisite), to (dependent), kind data/contract/infrastructure/event-flow and reason; keys are S<i>-<local key>. acyclic and cycle describe the combined graph. Complete means justified cross-Story build relationships, no duplicate closure edges or invented repository dependencies; Python validates keys and prevents cycles.

## spec-ui

Schema: [spec-ui.schema.json](schemas/spec-ui.schema.json).

Fields and interpretation: uiItems use item (placed item id), designSource, reason, artifact (kind/slug), bundle, buildSpec and sections; optional mocksDir and warnings survive normalization. Source bundle must match the newest supplied kind/slug and its declared buildSpec/sections; cds designs with the configured design system; none changes no design. Complete means all relevant placed UI items are represented and citations agree. Python normalizes invalid sources/bundles, supplies missing artifact identities and drops unknown item ids with warnings, then appends the UI section. No schema-level enum blocks those specified normalizations.

## architecture-views

Fields and interpretation: Markdown catalog fields view_type, scope, subject, shows, lifecycle_state and repository; diagrams and prose match the shared architecture review standard. Effective/target/delta/built are versions, not interchangeable review states. Complete means required affected scopes and exact implementation contracts are present. Draft/target/baseline files are Python-owned except assigned view contents.

## architecture-baseline

Fields and interpretation: The array schema architecture-baseline.schema.json is unchanged for saved surveys; its id/requirements/subjects/documents/code/awsGuidance/actions/rationale/conflicts/current/target/disposition/suitabilityEvidenceRefs hold design assessment. code and implementation fields are legacy context only. Complete means every capability has a matched assessed row with source evidence.

## trd-document

Fields and interpretation: Nonempty UTF-8 Markdown, decisionIds YAML list of actual arc42-relative effective or architecture-relative target/delta view paths, optional #heading. Each requirement has stable id, source and appliesTo element. PRD technical elaboration and architecture-imposed obligations are both covered; architecture is cited rather than duplicated. Complete means all applicable obligations on placed elements are sourced, including crosscutting requirements, without invented elements or code-satisfaction judgments.

## spec-document

Fields and interpretation: Nonempty UTF-8 Markdown with decisionIds frontmatter. Describe every placed API/event/error/UI contract in this repository, exact fields and failure behavior, tracing PRD/TRD/views. No applicable surface gives a reasoned not-applicable document. Complete means every placed contract is specified or explicitly not applicable; Python checks all view paths resolve.

## data-model-document

Fields and interpretation: Nonempty UTF-8 Markdown with decisionIds; owned stores, access patterns, keys/indexes, retention/consistency and capacity assumptions traced to PRD/TRD/views. Derive access patterns from these sources. Complete means applicable data obligations are specified (or reasoned not-applicable), with resolvable citations.

## criteria-document

Fields and interpretation: Nonempty UTF-8 Markdown with stable acceptance criterion and DoD ids linked to PRD/TRD/spec sections. State observable pass conditions and preserve source testStrategy if present. Complete means applicable behavior/boundaries and non-unit-testable human checks are represented without invented scope. Tasks reference these ids.

## delta-items

Fields and interpretation: Python arch-delta report: ok/refusals, architectureChange/note, views and items with id,element,views,kind,state,requires and prerequisite context. Complete means every required element has a stable work id across the selected three-case model; no add/modify/remove/done/planned-elsewhere work statuses. Read ids exactly; placement/tasks cannot omit an item on built guesses.

## closure-edges

Fields and interpretation: Python-derived cross-Story prerequisite edges from delta requires relations and placement/task ids. These edges stand; task-dependency-mapper adds only nonduplicate justified edges. Complete means every resolved prerequisite relation is represented with qualified task keys.

## task-edges

Fields and interpretation: Python edge write report summary with blockers, added,removed,standing,rejected; complete means valid non-cycling resolved Task edges were written, not merely proposed.

## inventory

Fields and interpretation: Python repository inventory records name,path,role,lifecycle. Placement reads current inventory before proposing a missing owner; marketing and archived repositories are excluded from survey context. It conveys repository location/purpose, not built-state proof.

## matrix

Fields and interpretation: Tracked source and per-dispatch snapshot hold architecture element rows: repository, state unknown/built/deployed, task and commit with design/catalog metadata. Only seed/build Python writes it, seed always unknown. Missing rows mean unknown; built/deployed satisfy. Elaboration reads a snapshot and never writes built state. See DESIGN 10 for full writer/fingerprint contract.

## ledger

Fields and interpretation: Python-folded contractVersion 2: assignments,roundPlans,claims,findings,savedResults,repairRequests,coverage and coverageRevision. Complete means all accepted current result files are folded with stable ids, including omitted unresolved obligations. Agents read their plan/claim/coverage ids and never edit this derived ledger.

## revision

Fields and interpretation: Python revision record archRoot,revision,files,views,integrating,recordedAt. Files map relative paths to hashes; complete means recorded reviewed dependencies match actual bytes. Agents never manufacture revision evidence.

## survey-seal

Fields and interpretation: Python survey seal revision,surveySha256,contextSha,inputs,repos and form adopted/v2 after migration. Complete means actual input and survey hashes bind current evidence; new forms omit repository tree and matrix bindings. Agents never write seals.

## target-report

Fields and interpretation: Python target report with targetDir,deltaDir,files,deltaFiles,architectureChange,note,designChanged,documentationChanged,implementationWork,approvalFiles,draftWritten or refusal fields. Complete means three-case paths and accepted documents correspond; failed checks are diagnostic, not approved architecture.

## tree-hashes

Fields and interpretation: Python mapping of architecture relative paths to hashes before/after integration. Complete means measured actual file bytes for the comparison; no agent-authored claims substitute.

## integration-files

Fields and interpretation: Python measured touched,deleted,all,unreported,section2,outside,changedSinceLast arrays. Complete means all filesystem changes are accounted; reviewers check measured files, not only maintainer claims.

## repo-creation

Fields and interpretation: Python created records name,repoPath,template,itemIds,existed plus failures name/template/itemIds/error/ownerFact. Complete means each missing owner has a actual checkout/remote or explicit failure; not an agent permission to create repositories.

## bundles

Fields and interpretation: Python list of supplied CDS bundles including identity kind/slug, newest createdAt, bundle path and buildSpec. Complete means usable supplied sources are enumerated; loose mocks are context, never a higher design authority than a matching bundle.

## story

Fields and interpretation: Python title,description,decisionIds: repository name plus PRD title, placed ids/elements and three spec paths. Complete means the repository container references the finished spec set; no agent Story narrative or outOfRepoFindings.

## task-items

Fields and interpretation: Python items array with id,element,views,requires,kind joined from placement and delta. Complete means all and only this Story repository work is represented, including prerequisites.

## task-context

Fields and interpretation: Python existingTasks/otherEpicTasks snapshot with keys,ids,titles,status,requirementIds and relevant descriptions/epic. Existing started/closed/deferred work is preserved; other-Epic overlap adds blockers, never suppresses Tasks.

## filed-documents

Fields and interpretation: Driver copies accepted UTF-8 spec documents to vault paths after elaboration done and records vault metadata. Complete means filed bytes represent accepted source artifacts; agents do not file them.

## run-manifest

Fields and interpretation: Python run record execution identity, sessions/phase/agent/model/effort/timing/result and failures. Complete means each started/resumed session is attributed once; see DESIGN 4 and runner contracts.

## handback

Fields and interpretation: Python driver-facing result carries ok/stage/failure/requiredHumanActions/sessions and artifact/repository facts defined by DESIGN 4. Complete means the process outcome and sessions are accurately returned; never an agent assertion of done.

## events

Fields and interpretation: Python JSON-line ledger events expose phase/verdict/session/process facts; driver translates existing callbacks. Complete means truthful observed transitions, no inferred running state.

## steps

Fields and interpretation: Python completed step ids in STEPS.md, dashboard navigation only. Complete means a validated recorded output exists; this list never determines reuse.

## retired

Fields and interpretation: Not produced by direct Epic sessions: survey-matrix.json is removed (DESIGN 3.6); Story draft is removed (11.5). Historical records are not active contracts.

## legacy

Fields and interpretation: Saved JavaScript receipts/candidates/tree-start and stale copies are historical evidence. Python adoption rules decide reuse; no agent regenerates legacy bindings.

## out-of-scope

Fields and interpretation: Owner-run portfolio readiness artifacts are indexed for historical accounting but not produced by Epic elaboration; their existing workflows remain until the plan removes them. No new Epic session or contract is inferred from those rows.


## round-results

Fields and interpretation: proposer/diagram files use architecture-writer.schema.json; reviewer/cost files use architecture-review.schema.json. The plan role decides which contract, never a producer-selected alternate. Complete means the assigned claim, coverage and repair set has an accepted result under its role contract. The ledger folds those result files; coordinator and decider read both.
