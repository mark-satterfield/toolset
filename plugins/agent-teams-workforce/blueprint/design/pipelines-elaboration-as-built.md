# The pipelines: elaboration as built

Parent: [The pipelines: overview](pipelines.md)

Required counterpart: [The pipelines: elaboration](pipelines-elaboration.md)

This document draws the elaboration pipeline, the composite `prd-to-spec`, **as the code builds
it today**. Every diagram is "Basis: as built". One dispatch of `prd-to-spec`
(`orchestrator/flows/prd_to_spec.py`) takes one ready Epic and its PRD, claims the Epic in beads,
and runs the Epic's step journal from its first step that is not done: the Architecture container
(`architecture.py`, `architecture_check.py`, `architecture_review.py`, `architecture_promotion.py`,
`architecture_earlier.py`, `architecture_files.py`), the TRD confirm step (`trd_authoring.py`),
the repository span and one Specs and Stories container per repository (`repo_scoping.py`,
`repo_placement.py`, `spec_authoring.py`, `spec_authoring_ui.py`, `spec_review.py`), the Tasks
(`task_decomposition.py`), the Task edges (`task_edges.py`), and the finishing steps
(`elaboration_steps.py`, `elaboration_support.py`, `elaboration_result.py`). It produces the
architecture written in arc42 (vault) and recorded in the matrix, the TRD, one spec set and one
Story bead per repository, and scored Task beads with their edges. The step contracts are in
`orchestrator/specs/epic/` (`prd-to-spec.md`, `architecture.md`, `trd-authoring.md`,
`repo-scoping.md`, `spec-authoring.md`, `task-decomposition.md`). The workflows
`route-elaboration.js`, `dependency-assessment.js`, `task-dependency-assessment.js`,
`wsjf-scoring.js` and `gate-enforce.js` are not run by any step of the journal (section 1). The
owner's requirements for elaboration are in [requirements/pipelines.md](../requirements/pipelines.md),
[requirements/matrix.md](../requirements/matrix.md), and Part 1 of the elaboration plan (items 1.1
to 1.12, quoted in [The pipelines: elaboration](pipelines-elaboration.md)). Each diagram's
"Differences from the requirements" names the plan item an as-built step departs from.

## Legend

| Notation | Meaning |
|---|---|
| `A ->> B` (sequence) | A calls or starts B: B does work for A |
| `B -->> A` (sequence) | B returns its result to A |
| `A -) Store` (sequence) | A writes to a store; nothing is returned |
| `alt` / `opt` / `loop` / `par` (sequence) | Alternatives, an optional part, a repeated part labelled with its exit, concurrent parts |
| `note` "differs from required" | The as-built step departs from the owner's requirement named in the note |
| `([...])` (activity) | Start or end |
| `{...?}` (activity) | A decision; every outgoing edge is labelled with its guard |
| "fork" / "join" nodes (activity) | Work that runs concurrently, and the point where all of it has finished |
| "merge" node (activity) | Alternative paths coming back together; no waiting |
| `event [guard] / effect` (state) | What moves a durable state, under what condition, and what it writes |
| runner | The journal runner of one dispatch (`orchestrator/core/journal_run.py`), which runs a step's script handler or launches its agent's session |
| arc42 (vault) | The arc42 documents under the architecture root in the `skillspoke-docs` vault |
| vault | The `skillspoke-docs` vault as a git repository (commits and pushes) |
| matrix | The matrix file, read and written through `atw-matrix` and its Python modules (`matrixstore`, `matrixwrite`, `matrixsync`, `matrixquery`) |
| beads | The bead tracker (`bd`, `beadgraph`, `beadwrite`) |
| git / GitHub | Product repositories and their GitHub remotes (`polyrepo`) |
| journal | The Epic's step journal, `<control>/.claude/workflow-runs/step-journals/<epic>.step-journal.json` |

Two facts hold for every agent step below, so the diagrams do not repeat them:

- Every agent session's output is checked by its step's output check; an output that fails the
  check sends the session back once, with the errors, as its one corrective resume
  (`orchestrator/core/agents.py:462-517`). A second failure fails the step.
- A failed step ends the dispatch. The next dispatch starts at the first step with no child steps
  that is not done (`orchestrator/core/step_journal.py:729-746`), so the failed step runs again. An
  earlier start happens only when the owner asks for it (`atw-step-journal invalidate`, or the
  driver's `elabmark.py --start-at`), per `orchestrator/specs/epic/prd-to-spec.md`, "Where a run
  begins".

## 1. One dispatch, end to end

**Subject:** one dispatch of `prd-to-spec` for one Epic.
**Scope:** from the driver's selection of the Epic to the release of its claim, through the ten
outermost steps of the Epic's journal.
**Purpose:** the order of the steps, what decides where a dispatch begins, and how it ends.
**Boundary:** Epic dependency assessment and Epic WSJF scoring are outside (owner-run commands);
the build and deploy pipelines come after. Each outermost step is drawn in detail in the sections
that follow.
**Basis:** as built. `ops/sdlc-automation/selection.py:264-284` (`_epic_candidate`);
`orchestrator/flows/prd_to_spec.py:130-218` (`outermost_steps`), `:363-398` (claim and loop),
`:309-344` (release); `scripts/portfolio/elaboration.py` (`start`, `finish`, `release`);
`orchestrator/specs/epic/dependency-assessment.md` and `wsjf-scoring.md`, "Who calls it".

```mermaid
flowchart TD
    start(["Driver elaboration lane, started by the owner with keeper.py"]) --> pick{"Epic open, no unmet tracks blocker in beads, workable elaboration state, and a WSJF value on the bead?"}
    pick -->|"no"| skipped(["Not selected. The owner runs dependency-assessment and wsjf-scoring by hand"])
    pick -->|"yes"| args{"Epic id, beadsRepoPath and a readable PRD file?"}
    args -->|"no"| inputFail(["Dispatch fails at stage input"])
    args -->|"yes"| claim["Claim the Epic in beads - elaboration.start"]
    claim --> claimed{"Claim granted?"}
    claimed -->|"no: done, foreign owner, or unknown state"| refused(["Dispatch ends with the refusal"])
    claimed -->|"yes: state in_progress, owner token recorded"| journal["Open the Epic's journal. Created with the ten outermost steps planned when the file does not exist"]
    journal --> next{"A step with no child steps that is not done?"}
    next -->|"no"| result
    next -->|"yes"| runStep["Run the first such step - script handler or agent session"]
    runStep --> stepOk{"Step done?"}
    stepOk -->|"yes: artifacts recorded, planned steps added"| next
    stepOk -->|"no: step failed with a structured cause"| result
    result["Assemble the dispatch result from the journal - elaboration_result.py"] --> doneQ{"Last step marked the Epic elaborated?"}
    doneQ -->|"yes"| finish(["Handback. Epic elaboration state done"])
    doneQ -->|"no"| release["Release the claim - elaboration.release clears the owner token"]
    release --> partial(["Handback. Epic elaboration incomplete. The next dispatch starts at the first step not done"])
```

The ten outermost steps the loop runs, in order (`prd_to_spec.py:148-218`):

```mermaid
flowchart TD
    s1["1 Open the run - script prd_to_spec.open_run - section 2"] --> s2["2 Architecture - container - sections 3 to 6"]
    s2 --> s3["3 TRD - script trd.confirm - section 7"]
    s3 --> s4["4 Specs and Stories - container, created with the span step atw-matrix epic --closure - sections 8 and 9"]
    s4 --> s5["5 Tasks - container, one child container per Story bead write - section 10"]
    s5 --> s6["6 Task edges - container, created with beadwrite.closure_task_edges - section 11"]
    s6 --> s7["7 Score the Tasks - script elaboration.score - section 11"]
    s7 --> s8["8 Apply the done rule - script elaboration.done_rule - section 11"]
    s8 --> s9["9 Story edges - script storyedges.story_edges - section 11"]
    s9 --> s10["10 Mark the Epic elaborated - script elaboration.finish - section 11"]
```

Workflows the Epic's journal does not run, as built:

| Workflow | Who runs it today | Source |
|---|---|---|
| `route-elaboration.js` | `/work-bead` only; the driver routes with its own `routing.route_elaboration` | `orchestrator/specs/epic/route-elaboration.md`, "Entry" |
| `dependency-assessment.js` (`epic-sequencer`) | the owner, through the plugin command; the driver only reads the `tracks` edges it writes | `orchestrator/specs/epic/dependency-assessment.md`, "Who calls it" |
| `wsjf-scoring.js` (`wsjf-scorer`) | the owner, and `dependency-assessment.js` after it applies edges; elaboration runs only the WSJF arithmetic (`scoring.score`) | `orchestrator/specs/epic/wsjf-scoring.md`, "Who calls it"; `scripts/portfolio/elaboration.py:240-326` |
| `task-dependency-assessment.js` | nothing but the Workflow tool by name; marked for deletion | `orchestrator/specs/epic/task-dependency-assessment.md` |
| `gate-enforce.js` | no Epic step | `orchestrator/specs/epic/gate-enforce.md` |

**Differences from the requirements:**

- Plan item 1.10: step 4's span fails the dispatch when the architecture adds or changes nothing
  ("the architecture adds or changes nothing to build", `repo_scoping.py:1001-1002`), so an Epic
  with no architecture change gets no spec; the owner requires "there still needs to be a spec
  with instructions for the wording change".
- Plan item 1.8: the dispatch sets the matrix approved state only as `architectureApproved` on the
  Epic's requirements and features (section 6); verified is never set by elaboration, which
  matches the owner's "The verified flag remain false or unverified" after elaboration.

**Assumptions:** none.

## 2. Open the run

**Subject:** the first outermost step, script `prd_to_spec.open_run`.
**Scope:** from the dispatch's arguments to the architect's step planned under the Architecture
container.
**Purpose:** what the matrix and the context file hold before the architect starts.
**Boundary:** the architect's work is section 3.
**Basis:** as built. `orchestrator/flows/prd_to_spec.py:221-275` (`_sync_matrix`, `open_run`);
`orchestrator/flows/architecture_files.py:110-131` (`new_context`), `:294-314`
(`agents_with_role`); `orchestrator/flows/architecture.py:177-208` (`first_steps`, `plan_under`);
`orchestrator/flows/architecture_earlier.py` (`carry`).

```mermaid
sequenceDiagram
    autonumber
    participant R as runner
    participant O as open_run script
    box Stores
    participant B as beads
    participant V as vault
    participant M as matrix
    participant J as journal
    end
    R->>O: run step Open the run
    O->>B: read the Epic - matrixsync.read_epics
    B-->>O: the Epic bead, or none
    alt beads does not hold the bead as an Epic
        O-->>R: step fails
    end
    O->>V: git rev-parse HEAD
    V-->>O: the vault commit the documents are read at
    O-)M: one change - sync_epics (Epic entry, PRD path and hash, one requirement per PRD heading) and sync_documents (every arc42 document with its lifecycle and headings)
    O-)O: write architecture/context.json
    note right of O: PRD, architecture root, state and result paths, TRD path, helpers folder, vault commit, matrix command
    O->>O: agents_with_role solutions-architect
    note right of O: the agent file whose front matter role matches
    O-->>R: artifacts prd, matrix epic entry, context
    R-)J: plan under Architecture - the step of aws-solutions-architect, then the check
    note over J: A journal ported for an Epic with saved run data also holds Earlier work on this PRD, done steps whose files the architect is not handed - architecture_earlier.carry
```

**Differences from the requirements:**

- Plan item 1.4: the matrix is filled from the PRD here as one requirement per PRD heading, and
  the architect is then told the matrix holds the Epic's requirements (section 3). The owner:
  "This statement is not true, and was never true".
- Plan item 1.6: the agent for the architect's step is found by Python from the front matter
  field `role` (`architecture_files.py:294-314`); the plan replaces role-based seat filling with
  the way question 4 settles.

**Assumptions:** none.

## 3. The architect's session and the agents it starts

**Subject:** the step "Decide what the architecture should be for this PRD", agent
`aws-solutions-architect`, and the agents it starts inside its session.
**Scope:** from the launch of the architect's session to the accepted architecture result.
**Purpose:** what the architect reads, whom it starts and how each is chosen, what each returns,
and what is written to arc42 (vault) and the matrix.
**Boundary:** what the runner does with helpers left running when the session ends is section 4;
the check and review are sections 5 and 6.
**Basis:** as built. `orchestrator/flows/architecture.py:212-232` (`_handed_files`), `:300-438`
(recording and the output check), `:440-494` (`architect`); `agents/aws-solutions-architect.md`
"The first step" (`:100-132`), "Delegating to specialists" (`:220-275`), "The TRD" (`:331-346`),
"Having the documents written" (`:348-353`), "Before you finish" (`:355-370`); the agent files
whose front matter role is `design-specialist`, `diagram-author`, `trd-author`,
`document-maintainer` or `repository-steward`; schemas `agent-brief`, `architecture-state`,
`specialist-request`, `specialist-answer`, `trd-request`, `trd-answer`, `write-request`,
`write-result`, `architecture-result` in `skills/artifact-handoff/schemas/`.

```mermaid
sequenceDiagram
    autonumber
    participant R as runner
    participant SA as aws-solutions-architect
    participant SP as design specialists and diagram authors
    participant PS as polyrepo-steward
    participant TA as trd-author
    participant AM as architecture-maintainer
    box Stores
    participant A as arc42 (vault)
    participant M as matrix
    participant J as journal
    end
    R->>SA: launch - brief names prd, context, state, and on later steps findings, answer, ruling
    SA->>M: atw-matrix epic EPIC, epic EPIC --realizers, epic EPIC --constraints
    M-->>SA: requirements, features, realizers with stacks, constraints
    note over SA,M: differs from required, plan item 1.4 - told the matrix holds the requirements and to open the PRD only for what the matrix lacks
    opt something the matrix does not hold
        SA->>SA: read the PRD at the section the matrix names
    end
    SA-)SA: write the state file
    note right of SA: architecture-state.schema.json
    SA->>TA: trd-request mode draft, trdPath, approvedHeadings
    TA->>M: atw-matrix epic EPIC --constraints
    TA-)TA: write the TRD at trdPath and the trd-answer
    TA-->>SA: obligations it could not source, each a question for the architecture
    note right of SA: choose specialists - resourceType of each realizer matched by rg to agent front matter resourceTypes, or by specialty
    note over SA,SP: differs from required, plan item 1.6 - specialists chosen from a front matter resourceTypes list
    par one request per specialist, started together
        SA->>SP: Agent tool, specialist-request file in the helpers folder, concerns point to PRD sections and arc42 headings
        SP->>A: read the arc42 headings the concerns name
        SP->>M: atw-matrix find, node, deps
        SP-->>SA: specialist-answer file, needs names another specialty
    end
    SA-)J: atw-step-journal - one child step per helper with its request file
    loop until the design needs nothing more from a specialist
        SA->>SP: SendMessage follow-up, or a new request for a specialty an answer names
        SP-->>SA: answer file
    end
    SA-)M: atw-matrix put and link - entries and links the design adds or changes
    opt an entry the design places has no stack
        SA->>PS: request to place entries in stacks
        PS-)M: put stack, homeIn
        PS-->>SA: answer file
    end
    note over SA,PS: differs from required, plan item 1.4 - repositories and stacks may be decided before the detailed design is complete
    loop whenever the design adds a technical requirement
        SA->>TA: trd-request mode update, the changes, sharedCapabilities
        TA-)TA: update the TRD in place
        TA-->>SA: trd-answer - requirements added or changed, removed, noSource
    end
    SA->>AM: write-request - facts, diagrams, settlements, each with its home
    AM-)A: write the arc42 documents
    AM-->>SA: write-result - headings changed and created, links added, restatements removed, entries below architecture level
    note over SA,AM: differs from required, plan item 1.3 - an entry below architecture level is moved to the TRD or notesForSpecs
    SA-)M: atw-matrix sync-documents --paths, describedBy and covers for the headings written
    SA-)J: child step Finish
    SA-)SA: write the architecture result
    note right of SA: conclusion, features, noFeature, addedOrChangedElements, sharedCapabilities, facts, criteria answers, notesForSpecs, unsettled, reviewSignals, costEvidence
    R->>R: output check
    note right of R: schema, story_build_problems on addedOrChangedElements, design recorded in an in-memory matrix copy and compared with atw-matrix epic
    alt the check finds problems
        R->>SA: one corrective resume with each problem as one sentence
    end
    R-)M: accept - servedBy, realizedBy, supportedBy, covers from what the result states
    alt the matrix written does not hold what the result states
        R-->>R: step fails
    else
        R-)J: artifacts architecture result, conclusion, requirements with no feature
    end
```

Who each agent is and how it is chosen, as built:

| Agent | How it is chosen | Receives | Produces | Writes |
|---|---|---|---|---|
| `aws-solutions-architect` | Python, the one agent whose front matter `role` is `solutions-architect` (`architecture_files.py:294-314`) | `prd`, `context`, `state`; later `findings`, `answer`, `ruling` | state file, architecture result | matrix (`put`, `link`, `sync-documents`), journal child steps |
| design specialists: `api-contract-designer`, `bounded-context-mapper`, `cdk-infrastructure-designer`, `domain-event-modeler`, `event-schema-designer`, `graphql-schema-designer`, `integration-pattern-architect`, `persistence-architecture-specialist`, `security-architecture-designer` | the architect, from the realizers' `resourceType` and each specialist's front matter `resourceTypes`, or by specialty (`aws-solutions-architect.md:232-250`) | a `specialist-request` file | a `specialist-answer` file | nothing outside its answer |
| diagram authors: `architecture-diagram-author`, `c4-diagram-author`, `uml-diagram-author` | the architect | a `specialist-request` with `kind` `task` | an answer file | nothing outside its answer |
| `polyrepo-steward` | the architect, "for placing entries in stacks" (`aws-solutions-architect.md:229`) | a request file | an answer file | matrix stacks and `homeIn` |
| `trd-author` | the architect, as soon as the state file is written | `trd-request` (`draft`, then `update`) | the TRD at `trdPath`, a `trd-answer` | the TRD file |
| `architecture-maintainer` | the architect | `write-request` | arc42 documents, `write-result` | arc42 (vault) |

**Differences from the requirements:**

- Plan item 1.4: "The first step" tells the architect "The matrix holds the Epic's requirements,
  features, realizers and constraints, broken down from the PRD ... Open the PRD only for something
  specific the matrix does not hold" (`aws-solutions-architect.md:105-107`). The owner: "How would
  you know if the matrix had everything that needed to exist, if you didn't open the PRD?"
- Plan item 1.4: the architect may start `polyrepo-steward` to place entries in stacks during its
  work (`architecture.py:527-552`), and the span creates repositories after the TRD step (section
  8); the owner requires that "the detailed-desgnn has to be completed" before the repositories
  are known. Who decides where an element lives is question 9.
- Plan item 1.6: specialists are chosen from the front matter `resourceTypes` lists
  (`aws-solutions-architect.md:232-241`), and "A part the Epic reaches is asked about even when its
  documents are effective" (`:248-250`). The owner: "Every agent needs to have a reason to be used"
  and "I also do not want a pipeline that blindly sends everything to ever agent".
- Plan item 1.3: the design specialists' files defer detail to spec writers, the maintainer
  returns entries "below architecture level" that the architect moves "to the TRD or to
  `notesForSpecs`" (`aws-solutions-architect.md:351`), and `notesForSpecs` is a free-text field of
  the result. The owner requires high, medium and detailed architecture and design done during
  architecture and recorded in documents and the matrix.
- Plan item 1.7: the result carries `costEvidence`; nothing records, for each AWS resource, which
  AWS tools, MCP servers and skills reviewed it, that best practices and security best practices
  were followed, how each decision was made, or the Well-Architected review.
- Plan item 1.9: the TRD is drafted once the state file is written and updated whenever the design
  adds a technical requirement (`aws-solutions-architect.md:331-346`). The owner: "The TRD drives
  architecture, some information in the architecture (like standards and contraints) aslo drives
  the TRD." When it is first written and updated is question 13; `trd-author.md` and the flow are
  named for change.

**Assumptions:** the loop "until the design needs nothing more from a specialist" is the
architect's judgment; no code bounds it. The order of the specialist, steward, TRD and maintainer
exchanges is the architect's; the diagram shows one order.

## 4. When the architect's session ends

**Subject:** what the runner does with the architect's step and its child steps after the
architect's session ends.
**Scope:** the architect's step, its helper child steps and its "Finish" child step.
**Purpose:** how an interrupted session or a helper left running is continued without asking a
helper again.
**Boundary:** the helpers' work itself is section 3.
**Basis:** as built. `orchestrator/flows/architecture.py:440-494` (`architect`, `resume_from`,
`is_finish`), `:497-563` (`_saved_request`, `specialist`), `:677-730` (`trd_author`),
`:733-819` (`_sync`, `maintainer`); `orchestrator/specs/epic/architecture.md`, "The architect and
the agents it starts"; `skills/pipeline-contracts/schemas/helper-steps.schema.json`, the protocol named in
`aws-solutions-architect.md:270-275`.

```mermaid
flowchart TD
    start(["The architect's session ends"]) --> read["The runner reads the journal again"]
    read --> q1{"Every child step of the architect's step done?"}
    q1 -->|"yes"| close(["The architect's step is closed. The check runs next"])
    q1 -->|"no"| q2{"Is the next child step not done a helper's step?"}
    q2 -->|"yes: a design specialist, a diagram author or polyrepo-steward"| sp["Launch that agent as its own session from the request file the step holds - answer at the path the request names"]
    q2 -->|"yes: trd-author"| tr["Launch trd-author from its request file. Accept records one constraint per TRD requirement added or changed, removes those listed as removed, one constraint with no statedIn per noSource obligation"]
    q2 -->|"yes: architecture-maintainer"| am["Launch architecture-maintainer from its write request, granted the architecture root. Accept sets each document written in-review in its front matter and runs sync-documents --paths"]
    q2 -->|"no: Finish is not done"| fin["Launch the architect again, continuing its session - it reads the state file, its partial result and each answer"]
    sp --> stew{"Was it polyrepo-steward?"}
    stew -->|"yes"| nostack["Record the value entries with no stack - atw-matrix epic EPIC --unlinked"]
    stew -->|"no"| merge1(("merge"))
    nostack --> merge1
    tr --> merge1
    am --> merge1
    merge1 --> read
    fin --> read
```

Writes made when a helper's step is accepted, as built:

| Helper | Matrix | arc42 (vault) | Journal artifacts |
|---|---|---|---|
| design specialist, diagram author | none | none | `request` or `question`, `answer` |
| `polyrepo-steward` | stacks and `homeIn`, by the steward itself | none | `request`, `answer`, `entries with no stack` |
| `trd-author` | `constraint` entries with a `trd` pointer, `statedIn`, `appliesTo` (`architecture.py:615-674`) | none | `request`, `TRD`, `answer`, `obligations with no source`, `constraints recorded` |
| `architecture-maintainer` | `sync-documents --paths` for each document written (`architecture.py:760-781`) | each written document set `lifecycle: in-review` (`matrixsync.set_lifecycle`) | `write request`, `what was written`, `documents synced` |

**Differences from the requirements:** none named in the plan for this continuation.

**Assumptions:** none.

## 5. The check after the architect

**Subject:** the script step `atw-matrix check; atw-matrix review-scope`.
**Scope:** from an accepted architecture result to the planned reviewers, a correction, or the
lead's step.
**Purpose:** the mechanical gate, its loop bound, and how reviewers are selected.
**Boundary:** the reviews and what follows them are section 6.
**Basis:** as built. `orchestrator/flows/architecture_check.py:157-198` (`check_step`,
`_mechanical`), `:395-458` (`_review_steps`), `:461-487` (`_correction`, `MAX_CORRECTIONS` 3 at
`:90`), `:505-557` (`check`); `skills/effective-architecture/review-criteria.json` (`appliesWhen`).

```mermaid
flowchart TD
    start(["Architect's step, a correction, or the lead's routing step done"]) --> mech["Mechanical check - matrix file problems, the Epic's entry, an answer for every architecture and technical-requirement criterion"]
    mech --> w1["Write architecture/checks/STEP/check.json - artifact check result"]
    w1 --> valid{"Any problem?"}
    valid -->|"yes"| count{"Corrections so far below 3?"}
    count -->|"no"| fail(["Step fails, naming the problems"])
    count -->|"yes"| corr["Plan a correction step for aws-solutions-architect, handed the check result, and a new check with corrections plus 1"]
    corr --> start
    valid -->|"no"| scope["atw-matrix review-scope --epic - documents the Epic reaches that are not effective. Write review-scope.json and unlinked.json"]
    scope --> unsettled{"Conclusion unsettled and no architecture-team-lead step has run in the container?"}
    unsettled -->|"yes"| lead["Plan the step of architecture-team-lead - Route what the architect could not settle - and a new check"]
    lead --> start
    unsettled -->|"no: changes-designed, no-change-needed, or unsettled after the lead"| sel["Select reviewers by the appliesWhen rule of each reviewer group - kinds of content in review and the result's reviewSignals"]
    sel --> any{"Any reviewer selected?"}
    any -->|"no"| fail2(["Step fails - the criteria file selects no reviewer"])
    any -->|"yes"| plan["Write review-scope.REVIEWER.json per reviewer. Plan one step per reviewer and the promotion step after them"]
    plan --> done(["Section 6"])
```

The reviewers the criteria file can select are the agents whose front matter role is
`architecture-reviewer`: `architecture-boundary-guardian`, `architecture-pattern-challenger`,
`architecture-tradeoff-skeptic`, `cost-architecture-reviewer`, `cost-impact-reviewer`,
`failure-mode-analyst`, `operational-readiness-reviewer` and `trd-validator`. A result whose
conclusion is `no-change-needed` is reviewed too: each reviewer's narrowed scope also names the
effective documents and headings the result's criteria answers cite (`architecture_check.py:263-323`).

**Differences from the requirements:**

- Plan item 1.6: which reviewers run is decided by a rule in a JSON file over content kinds and
  signals, applied by Python; the plan names role-based seat filling
  (`architecture_files.py:294-312`) as Python choosing the agent.
- Plan item 1.3: the criteria the result must answer include rule A12 ("Every document stays at
  architecture level", `skills/effective-architecture/review-standard.md:59-61`), which the plan
  removes.

**Assumptions:** none.

## 6. Review, routing, ruling and promotion

**Subject:** the reviewers' steps, the steps of `architecture-team-lead` and
`architecture-decider`, and the promotion script `atw-matrix sync-documents; atw-matrix commit`.
**Scope:** from the planned reviewers to the documents set effective and the matrix committed.
**Purpose:** who reviews what, how findings loop back, who rules, and where `lifecycle` and
`architectureApproved` are written.
**Boundary:** the architect's corrections reuse section 3.
**Basis:** as built. `orchestrator/flows/architecture_review.py:195-305` (`_lead_group`,
`_accept_review`, `reviewer`), `:318-364` (`lead`), `:367-453` (`_disagreements`, `decider`);
`orchestrator/flows/architecture_promotion.py:88-145` (`_promote`), `:180-195`
(`_require_resolved`), `:267-321` (`promote`); `scripts/portfolio/matrixwrite.py:639-679`
(`approve`); `skills/artifact-handoff/scripts/architecture_work_contract.py:52-56` (routings).

```mermaid
sequenceDiagram
    autonumber
    participant R as runner
    participant RV as selected reviewers
    participant TL as architecture-team-lead
    participant SA as aws-solutions-architect
    participant AD as architecture-decider
    participant P as promotion script
    box Stores
    participant A as arc42 (vault)
    participant M as matrix
    participant V as vault
    participant J as journal
    end
    par consecutive reviewer steps whose inputs are done, at most ATW_ORCH_SESSIONS sessions
        R->>RV: review scope, architecture result, TRD when the group covers it, PRD when the scope names it
        RV->>A: read the headings the scope names
        RV-->>R: architecture/reviews/REVIEWER.json - findings, alternativesRequested
    end
    R-)J: artifacts review, findings, findings outside the scope - a finding outside the scope is dropped and counted
    alt some review holds a finding or asks for alternatives
        R-)J: plan the lead's step after the last reviewer, before the promotion
        R->>TL: findings from the reviews that raised something, architecture result
        TL-->>R: routing-STEP.json, one routing per item - reject, correct, opinion, competing-design, decider
        TL-)J: child steps for what remains, then Finish
        loop each child step the lead added, until the lead's Finish records every item is resolved
            alt correct
                R->>SA: correction with the findings, continuing its session
                SA-->>R: architecture result updated in place
                R->>RV: re-check by the reviewer that raised it, same narrowed scope, continuing its session
                RV-->>R: review
            else opinion
                R->>R: a design specialist answers the lead's question
            else competing-design
                R->>SA: design the position the request names
                SA-->>R: architecture result updated in place
            else decider
                R->>AD: one question file
                AD-)M: atw-matrix settle - stands on each disputed disagreement
                AD-->>R: ruling-STEP.json - stands, ownerConcerns
                alt the ruling raises an owner concern
                    R-->>R: step fails at stage requires-human-action
                else a disagreement the question is about has stands unset
                    R-->>R: step fails
                end
            end
            R->>TL: Finish - record every item is resolved, or add the steps that remain
        end
    end
    R->>P: run the promotion step
    alt a review raised something and no lead recorded every item is resolved
        P-->>R: step fails
    end
    P->>M: atw-matrix review-scope --epic with addedOrChangedElements
    P-)A: set lifecycle effective in each document's front matter
    P-)M: one change - sync-documents --paths, remove each settled disagreement a maintainer corrected, approve - architectureApproved on the Epic's requirements and the features that serve them
    note over P,M: differs from required, plan item 1.8 - approved set on requirements and features only, by a script
    P-)V: commit and push the changed documents to main
    P-)M: atw-matrix commit --bead - commit and push the matrix file
    alt a document is not shown effective in the matrix afterwards
        P-->>R: step fails, naming each document
    else
        P-)J: promoted.json - promoted documents, vault commit, matrix commit
    end
```

**Differences from the requirements:**

- Plan item 1.8: the arc42 `effective` lifecycle is set by the promotion script by rule
  (`architecture_promotion.py:116`; the architect's file: "A script marks content approved",
  `aws-solutions-architect.md:387`). The owner: `effective` "means ... the document has been
  approved by the architecture agent responsble for approving the architecture."
- Plan item 1.8: the approved state is the `architectureApproved` mark, set on the Epic's
  requirements and the features that serve them (`matrixwrite.py:667-679`); the owner requires an
  approved flag on the matrix content an Epic's elaboration reaches, set when the matrix and arc42
  are filled out or corrected. Whether `architectureApproved` is the approved flag is question 12.

**Assumptions:** the `opinion` branch is drawn as "a design specialist answers the lead's
question"; the lead's definition says it may ask the agents whose role is `design-specialist`
(`architecture_review.py:318-330`), and the step it adds runs through the `specialist` launch
builder (`architecture.py:527-563`).

## 7. The TRD confirm step

**Subject:** the outermost step "TRD", script `trd.confirm`.
**Scope:** from the TRD file `trd-author` wrote to the TRD recorded on the Epic bead.
**Purpose:** what is checked and recorded once the architecture is promoted.
**Boundary:** the writing of the TRD is sections 3 and 4.
**Basis:** as built. `orchestrator/flows/trd_authoring.py:164-302` (`document`,
`unresolved_requirements`, `_mark_trd`, `confirm`); `orchestrator/specs/epic/trd-authoring.md`.

```mermaid
sequenceDiagram
    autonumber
    participant R as runner
    participant C as trd.confirm script
    box Stores
    participant A as arc42 (vault)
    participant M as matrix
    participant B as beads
    end
    R->>C: run step TRD
    C->>C: read the TRD at the path the context file names
    C->>A: does every decisionIds entry name a file under the architecture root
    C->>M: does the matrix hold every cited document and heading, and does every constraint with a trd pointer name a heading the TRD has
    alt the TRD is missing, its front matter fails, or a citation does not resolve
        C-->>R: step fails
    else
        C-)B: Epic metadata - TRD path and SHA-256, unless both are already held
        C-->>R: artifacts TRD, TRD hash on the Epic bead, TRD warnings when decisionIds is empty
    end
```

**Differences from the requirements:** none named in the plan for this step.

**Assumptions:** none.

## 8. The repository span

**Subject:** the first step of "Specs and Stories", script `atw-matrix epic --closure`
(`repo_scoping.span`).
**Scope:** from the architect's `addedOrChangedElements` to one Specs and Stories container per
repository.
**Purpose:** what each Story builds, where repositories come from, and when a repository is
created.
**Boundary:** the spec steps of one repository are section 9.
**Basis:** as built. `orchestrator/flows/repo_scoping.py:354-371` (`story_build_entries`),
`:440-462` (`story_build_problems`), `:489-529` (`repository_name`), `:603-640` (`story_builds`),
`:227-337` (`create_repositories`), `:927-960` (`_spec_steps`), `:988-1062` (`span`);
`orchestrator/flows/repo_placement.py` (`forbidden`); `orchestrator/specs/epic/repo-scoping.md`.

```mermaid
sequenceDiagram
    autonumber
    participant R as runner
    participant S as span script
    participant N as naming command ATW_NAMING_COMMAND
    participant PT as polyrepo tool
    box Stores
    participant M as matrix
    participant G as git / GitHub
    participant J as journal
    end
    R->>S: run the span step
    S->>S: read addedOrChangedElements from architecture/result.json
    S->>M: placements, documents describing each entry, event producers, architecture-side dependencies
    M-->>S: one item per entry and stack - E1, E2 and so on, requires and requiredBy
    alt no item
        S-->>R: step fails - the architecture adds or changes nothing to build
    end
    note over S,M: differs from required, plan item 1.10 - an Epic with no architecture change gets no spec
    alt an item is not buildable - not an id, not on the architecture side, an event with no description, in no stack
        S-->>R: step fails with each problem
    end
    opt a stack the Stories build in names no repository
        S->>N: name convert STACK --from cdk-stack --to repository
        N-->>S: repository name
        S-)M: put stack --repository on the architecture side
    end
    S->>PT: polyrepo inventory
    PT-->>S: repositories known
    alt a repository is the control repository or the architecture folder
        S-->>R: step fails - may hold no product entry
    end
    opt a repository the inventory lacks
        S->>PT: polyrepo inventory - the one GitHub owner
        S->>PT: polyrepo create NAME --space APP
        PT-)G: create the repository from the template the name selects
        alt GitHub membership or creation fails
            S-->>R: step fails at stage requires-human-action
        end
        opt the created name differs
            S-)M: put stack --repository with the created name
        end
    end
    S-)S: write span-elements.json, repo-scoping.json, repo-creation.json when one was created
    S-->>R: artifacts elements, span, repository creation, repositories
    R-)J: plan one container per repository, named for it, first step spec_authoring.context with repoPath, slug, storyKey S1 and so on, frontend when its stacks are of type web
```

**Differences from the requirements:**

- Plan item 1.10: what each Story builds is the architect's `addedOrChangedElements` and nothing
  more (`repo_scoping.py:354-371`); the owner requires the spec's scope to come from the verified
  state of each element ("A spec's delta NEVER was supposed to come from an architecture delta").
- Plan item 1.10: the span fails when nothing is added or changed (`repo_scoping.py:1001-1002`);
  the owner requires a spec for an Epic with no architecture change.
- Plan item 1.4: repositories are determined from the stacks placed during the architect's
  session, before or alongside the detailed design (section 3); question 9.

**Assumptions:** none.

## 9. The specs and the Story of one repository

**Subject:** the steps of one repository's container under "Specs and Stories".
**Scope:** from `spec_authoring.context` to the Story bead and its journal.
**Purpose:** which agents write which documents from what, the review loop and its bound, and the
Story written to beads.
**Boundary:** the Tasks are section 10. Repositories run one after another.
**Basis:** as built. `orchestrator/flows/spec_authoring.py:254-351` (`_repository_steps`),
`:420-479` (`context`), `:550-576` (`spec_document`), `:620-725` (`story_document`,
`story_bead`); `orchestrator/flows/spec_review.py:204-458` (`following`, `reviewer`, `correction`,
`decider`, `author`); `orchestrator/flows/spec_authoring_ui.py`; `orchestrator/flows/elaboration_files.py:63-67`;
`orchestrator/specs/epic/spec-authoring.md`; schemas `spec-context`, `spec-ui`, `ui-bundles`,
`spec-review`, `spec-correction`, `spec-ruling`, `story-document`, `document-front-matter`
(`SpecDocument`).

```mermaid
sequenceDiagram
    autonumber
    participant R as runner
    participant X as spec_authoring.context
    participant API as api-specification-author
    participant DM as data-model-specification-author
    participant AC as acceptance-criteria-writer
    participant OR as openapi-contract-reviewer
    participant SD as spec-decider
    box Stores
    participant M as matrix
    participant A as arc42 (vault)
    participant B as beads
    participant J as journal
    end
    R->>X: repoPath, slug, storyKey, frontend, span, elements
    X->>M: item_stacks, atw-matrix story-scope per stack, build_context dependsOn
    X-)X: spec-SLUG.context.json
    note right of X: items, stacks with entries, documents and headings, dependsOn, PRD path, architecture result path, design system
    X-->>R: artifacts repository, repository context
    R-)J: plan the repository's steps
    opt frontend repository
        R->>R: cdsbundles.list_bundles - spec-SLUG.bundles.json
        R->>API: choose the UI design source of each UI item
        API-->>R: candidates/spec-SLUG.ui.json
        R->>R: spec_authoring.normalize_ui
        note right of R: spec-SLUG.ui.json, warnings
    end
    par contracts and data model, concurrent sessions
        R->>API: TRD, span, elements, ui sources, repository context
        API->>M: atw-matrix story-scope, uses
        API->>A: read the headings the context names
        API-->>R: spec-SLUG.md with SpecDocument front matter, decisionIds resolving under the architecture root
        R->>DM: TRD, span, elements, repository context
        DM->>M: atw-matrix story-scope, uses
        DM->>A: read the headings the context names
        DM-->>R: spec-SLUG.data-model.md
    end
    opt frontend repository
        R->>R: specui.spec_ui_append
        note right of R: section UI design sources in spec-SLUG.md
    end
    R->>AC: TRD, span, elements, spec, data model, repository context
    AC-->>R: spec-SLUG.criteria.md, non-empty
    R->>OR: spec, data model, criteria, TRD, repository context
    OR-->>R: spec-SLUG.review.json - findings, kept only when the criterion is an implementation-level id
    loop documents in order contracts, data model, criteria, one pass - each finding goes to its author once
        opt the document has a finding or derives from one that changed
            R->>API: correct, continuing the session that wrote it - or DM or AC for their documents
            API-->>R: spec correction, the document again, disputed findings
        end
    end
    opt an author disputed a finding
        R->>SD: the disputed findings
        SD-->>R: spec ruling - finding stands or document stands, directives
        loop documents in order, one pass
            opt the document has an upheld finding or derives from one that changed
                R->>API: revise to the ruling - or DM or AC
                API-->>R: spec revision, the document again
            end
        end
    end
    note over R,SD: a finding disputed again after the ruling stands as ruled. A document that fails its own check after a correction or revision fails the step
    R->>R: spec_authoring.story_document
    note right of R: story-SLUG.json, one line per item, decision ids
    R-)B: beadwrite.write_story - the Story under the Epic by elaboration key story:SLUG, metadata path and SHA-256 of each spec document
    R-)J: create the Story's journal, pipeline deploy, first step done holding spec, data model, criteria, ui sources, TRD, story document
    R-)J: plan the repository's container under Tasks
    note over R,B: nothing in this container writes the matrix
```

**Differences from the requirements:**

- Plan item 1.10: the spec's scope is the span's items, from the architecture delta; nothing
  reads the verified state of an element to choose between the work that brings the build up to
  the approved architecture and the delta alone.
- Plan item 1.3: the authors are handed the architect's result, whose `notesForSpecs` they start
  from (`architectureResult` in the context file, `spec_authoring.py:471`); the plan replaces
  that free-text channel with documents and the matrix.
- Plan item 1.10 and 1.12: the spec writers' files and names are to say they write specs and are
  not the detail-level designers.
- The Story bead is written by the script `beadwrite.write_story` from the Story document; the
  agent `user-story-writer` is not dispatched by any step (no flow or workflow names it). No plan
  item names this.

**Assumptions:** none.

## 10. The Tasks of one repository

**Subject:** the steps of one repository's container under "Tasks".
**Scope:** from `task_decomposition.context` to the Task beads written and recorded.
**Purpose:** what the decomposer receives, the gap check and its one correction, and what is
written to beads.
**Boundary:** edges between Tasks of different Stories are section 11.
**Basis:** as built. `orchestrator/flows/task_decomposition.py:240-260` (`task_grouping_check`),
`:265-317` (the decomposer's launch), `:319-345` (`_correction_steps`), `:380-420` (the plan
step); `scripts/portfolio/beadwrite.py` (`plan_story_tasks`, `write_task`,
`retire_superseded_tasks`); `orchestrator/specs/epic/task-decomposition.md`; schemas
`task-context`, `tasks`, `task-gaps`, `tasks-correction`.

```mermaid
sequenceDiagram
    autonumber
    participant R as runner
    participant TX as task_decomposition.context
    participant TD as task-decomposer
    participant BW as beadwrite scripts
    box Stores
    participant M as matrix
    participant B as beads
    participant J as journal
    end
    R->>TX: story, span, elements
    TX->>B: Tasks under the Story that are started or that elaboration did not write
    TX-)TX: tasks-SLUG.context.json
    note right of TX: existing Tasks, stacks with entries, dependsOn
    TX-->>R: artifacts repository, task context
    R->>TD: spec, data model, criteria, story document, span, elements, ui sources, repository context, task context
    TD->>M: atw-matrix work - open Tasks of other Epics in the same stacks
    TD->>M: atw-matrix uses - shared capabilities the Tasks must use
    TD-->>R: tasks-SLUG.json
    R->>R: task_grouping_check
    note right of R: schema, every Task cites more than one thing when the Story builds two or more
    R->>BW: plan_story_tasks
    alt no Task, an item cited by no Task, or a Task with no size
        BW-->>R: tasks-SLUG.gaps.json
        R->>TD: correct the gaps, continuing the decomposition session
        TD-->>R: tasks-SLUG.correction.json
        R->>BW: plan_story_tasks with the correction merged
        alt the plan still has a gap
            BW-->>R: step fails
        end
    end
    BW-->>R: task plan
    loop one step per Task, in build order
        R->>BW: write_task
        BW-)B: the Task bead under the Story by elaboration key, its blocks edges onto Tasks of the same Story, the build contract at the end of its description, size
        BW-)J: create the Task's journal, pipeline build, first step done holding spec, data model, criteria, ui sources, TRD, story document, tasks, task key
    end
    R->>BW: retire_superseded_tasks
    BW-)B: move blocks edges from Tasks of other Stories, delete Task beads elaboration wrote that the plan no longer names and nobody started
    R-)R: task_decomposition.record
    note right of R: tasks-SLUG.written.json, tasks result
```

**Differences from the requirements:** none named in the plan for these steps. Plan item 1.11
concerns what the build receives from the Tasks and specs and is drawn with the build pipeline.

**Assumptions:** none.

## 11. Task edges and the finish

**Subject:** the outermost steps "Task edges", "Score the Tasks", "Apply the done rule", "Story
edges" and "Mark the Epic elaborated".
**Scope:** from the Tasks of every Story to the Epic marked elaborated.
**Purpose:** where cross-Story edges come from, when the mapper runs, and the gates before the
Epic is done.
**Boundary:** WSJF judgment of Epics is outside elaboration (section 1).
**Basis:** as built. `orchestrator/flows/task_edges.py:70-120` (planning, `SEVERAL`), `:184-215`
(the mapper's launch); `scripts/portfolio/beadwrite.py` (`closure_task_edges`,
`write_all_task_edges`); `orchestrator/flows/elaboration_steps.py` (`score`, `apply_done_rule`,
`story_edges`, `mark_done`); `scripts/portfolio/elaboration.py:240-326` (`finish`);
`orchestrator/specs/epic/prd-to-spec.md`, "Task edges" and "Finish".

```mermaid
sequenceDiagram
    autonumber
    participant R as runner
    participant CE as beadwrite.closure_task_edges
    participant TM as task-dependency-mapper
    participant F as finishing scripts
    box Stores
    participant B as beads
    participant J as journal
    end
    R->>CE: every Story document, spec documents, Tasks file, span, elements
    CE->>CE: edges the items' requires make between Tasks of different Stories
    alt a required element has no Task that builds it
        CE-->>R: step fails
    end
    CE-->>R: closure edges
    R->>R: task_edges.listing
    note right of R: task dependency listing, pointing to each Story's Tasks file and the closure edges
    opt the span has two or more repositories
        R->>TM: Tasks files, closure edges, listing
        TM-->>R: task dependencies - checked against task-deps
    end
    R->>R: beadwrite.write_all_task_edges
    R-)B: blocks edges between Tasks of different Stories
    note over R,TM: the mapper's edges are written to beads only, never to the matrix
    R->>F: elaboration.score - scoring.score over the Epic's Tasks, WSJF arithmetic from the sizes write_task recorded
    F-)B: WSJF values of the Epic's Tasks
    F-->>R: unscored tasks
    R->>F: elaboration.done_rule
    alt a repository lacks its Story or Tasks, or a Task is unscored
        F-->>R: step fails
    end
    R->>F: storyedges.story_edges
    F-)B: blocks edges between the Epic's Stories
    R->>F: elaboration.finish with done
    F-)B: Epic elaboration state done, owner cleared
    alt the Epic could not be marked done
        F-->>R: step fails
    else
        F-)J: lifecycle done
    end
```

**Differences from the requirements:** none named in the plan for these steps.

**Assumptions:** none.

## 12. The Epic's elaboration state in beads

**Subject:** the bead metadata `KEY_ELABORATION_STATE` of one Epic and its owner token
(`KEY_ELABORATION_STATE_OWNER`).
**Scope:** every transition the driver selection and `prd-to-spec` make.
**Purpose:** when an Epic can be dispatched, claimed, resumed and finished.
**Boundary:** the Epic's `tracks` edges and WSJF value come from outside elaboration.
**Basis:** as built. `scripts/portfolio/elaboration.py:135-223` (`start`), `:240-326`
(`finish`), `:328-370` (`release`); `skills/beads-contract/scripts/bead_metadata.py:98-100`;
`ops/sdlc-automation/selection.py:264-284`.

```mermaid
stateDiagram-v2
    [*] --> ready
    ready --> in_progress : claim [selected by the driver] / owner token and time recorded
    in_progress --> in_progress : claim by the same owner, or reclaim / dispatch resumes the journal
    in_progress --> in_progress : release [dispatch ends before the last step] / owner token cleared
    in_progress --> done : elaboration.finish with done [every Task scored] / owner cleared, cause decomposed
    done --> done : claim / refused, its Tasks are the workable items
    done --> in_progress : a person sets the state in_progress / the Epic can be elaborated again
    done --> [*]
```

An absent elaboration state is taken as `ready`; an unknown one is taken as `ready` with a warning
(`elaboration.py:186-191`). A claim on an `in_progress` Epic held by another owner is refused
unless the dispatch asks to reclaim (`:192-200`).

**Differences from the requirements:** none named in the plan.

**Assumptions:** none.

## 13. A journal step

**Subject:** the status of one step of the Epic's journal.
**Scope:** every step, script or agent, at any depth.
**Purpose:** what a rerun reuses and what it runs again.
**Boundary:** the steps a step plans are added by its completion.
**Basis:** as built. `skills/pipeline-contracts/scripts/step_journal_contract.py:37-40`;
`orchestrator/core/step_journal.py:268-357` (container completion), `:569-692` (start, done,
fail), `:729-787` (`next_step`, journal done); `orchestrator/specs/epic/prd-to-spec.md`, "How a
step runs" and "Where a run begins".

```mermaid
stateDiagram-v2
    [*] --> planned : created with the journal, or added by a done step's completion
    planned --> running : runner starts its script or session
    running --> done : output accepted / artifacts recorded, planned steps added, parameters recorded as for STEP
    running --> failed : handler raised, or output invalid after the one corrective resume / structured cause recorded, dispatch ends
    failed --> running : next dispatch, first step not done
    running --> running : next dispatch after an interruption / agent session resumed where the step holds one
    done --> planned : owner asks for an earlier start, atw-step-journal invalidate / later steps reset, the steps they planned removed
    planned --> done : container [every child step done]
    done --> [*]
```

A container has no handler: it is done when every child step is done. Consecutive sibling steps
that each have an agent, have no child steps and whose inputs are done run as concurrent sessions,
at most `ATW_ORCH_SESSIONS` at a time (`orchestrator/core/journal_run.py:77`, `:427`).

**Differences from the requirements:** none named in the plan.

**Assumptions:** none.

## 14. arc42 lifecycle and the matrix marks, as elaboration writes them

**Subject:** the front matter `lifecycle` of an arc42 document and the matrix marks
`architectureApproved` and `verified`.
**Scope:** the writes elaboration makes, and the one write the driver makes after a Story merges.
**Purpose:** where the as-built states are set, for comparison with
[The pipelines: architecture and matrix states](pipelines-architecture-states.md).
**Boundary:** the seeding of the matrix and arc42 is outside.
**Basis:** as built. `orchestrator/flows/architecture.py:760-781` (`_sync`, in-review);
`orchestrator/flows/architecture_promotion.py:88-145` (effective, approve);
`scripts/portfolio/matrixwrite.py:639-679` (`approve`); `ops/sdlc-automation/matrixmarks.py:342`
(`verified`, `atw-matrix verify --story`).

An arc42 document:

```mermaid
stateDiagram-v2
    [*] --> effective : seeded, or promoted by an earlier Epic
    [*] --> in_review : created by architecture-maintainer / maintainer step sets in-review, sync-documents
    effective --> in_review : architecture-maintainer writes it for this Epic / maintainer step sets in-review, sync-documents
    in_review --> in_review : further writes in the same run
    in_review --> effective : promotion [no finding raised, or the lead recorded every item resolved] / set effective, sync-documents, vault commit and push
    effective --> [*]
```

A matrix requirement or feature of the Epic, and a stack or component:

```mermaid
stateDiagram-v2
    state "requirement or feature" as RF {
        [*] --> unmarked
        unmarked --> architectureApproved : promotion of this Epic / approve names the Epic
        architectureApproved --> architectureApproved : promotion again / left as it is when it already names the Epic
    }
    state "stack or component a Story built" as SC {
        [*] --> notVerified
        notVerified --> verified : driver, the Story's pull request merged / atw-matrix verify --story with the merge commit, commit and push
    }
```

**Differences from the requirements:**

- Plan item 1.8: `effective` is set by the promotion script, not by "the architecture agent
  responsble for approving the architecture".
- Plan item 1.8: the approved mark reaches only the Epic's requirements and features; the owner's
  approved flag covers the matrix content an Epic's elaboration reaches (nodes and linkages, "The
  linkage could have a verified flag. The node could have a verified flag."). Question 12.
- Plan item 1.8: `verified` is set per Story when its pull request merges; the owner: "Once all of
  the tasks for all of the stories for and Epic have been built and tested (including CI (CDK),
  which means deployemen must also work), then all of the architecture and rellationships for the
  Epic can be set to verified."

**Assumptions:** none.
