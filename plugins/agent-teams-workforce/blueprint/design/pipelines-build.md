# The pipelines: build

Parent: [The pipelines: overview](pipelines.md)

The build pipeline runs once per Task. It takes in a Task with its build contract, on its
Story's branch, and produces the Task's code and tests committed to the Story's branch with the
repository's whole test suite passing (`blueprint/requirements/pipelines.md`, "What the pipelines
are"). The driver in `ops/sdlc-automation` routes the Task (`routing.py` `route_build`, the
executable twin of `workflows/route-build.js`), claims it, opens its step journal and dispatches
the composite `task-to-deploy` (`workflows/task-to-deploy.js`). That workflow runs the steps of
the journal (`skills/pipeline-contracts/schemas/pipeline-steps.json`, pipeline `build`) and, for
them, the workflows `workspace.js`, `infra-intent.js`, `suite-run.js`, `tdd-red.js`,
`tdd-green.js`, `tdd-refactor.js`, `documentation.js` and `settle.js`. The requirements live in
`blueprint/requirements/pipelines.md`, `blueprint/requirements/matrix.md` (R24 to R26, R39 to R42,
R46) and the Build table of section 4 of `blueprint/design/matrix.md`, which
`requirements/pipelines.md` makes the specification of the build lane's use of the matrix; the
owner's statements of 2026-10-19 that apply are quoted where they are used.

## Legend

| Notation | Meaning |
|---|---|
| `([...])` | Start or end of an activity diagram |
| `{...?}` | Decision; every outgoing edge carries its guard |
| `fork` / `join` | Concurrent work starts / ends |
| `merge` | Paths rejoin |
| `->>` | A call or a dispatch: the caller starts the work |
| `-->>` | The return of that call |
| `-)` | An asynchronous message, or a write to a store with no reply |
| `loop`, `alt`, `opt` | Repetition with its exit condition, alternatives, an optional part |
| `box` | A store: arc42 (vault), the matrix, beads, the vault, git / GitHub |
| "differs from required" | A note where the code does something other than what is required |
| "assumption" | An element neither source specifies |
| State `event [guard] / effect` | A state machine transition |

Store names used everywhere: **arc42 (vault)** (the architecture documents in the
`skillspoke-docs` vault), **vault** (the other vault documents, for example the Spec), **matrix**
(`atw-matrix`), **beads** (`bd`), **git / GitHub**. Two working files also appear: the **step
journal** (one file per bead, written by the driver) and the **relay directory** (the files every
deterministic command writes for this Task).

## 1. The build as required

**Subject:** what the build receives, what it reads, what it writes, and what it produces.
**Scope:** one Task, from ready to committed.
**Purpose:** the requirement every as-built diagram below is compared with.
**Boundary:** elaboration (which writes the Task) and the Story's deploy (which publishes, deploys,
corrects arc42 from what was built and sets the verified mark) are outside.
**Basis:** required. `requirements/pipelines.md` "What the pipelines are" and "Bugs" (a build that
finds a defect fixes it in that run) and "The matrix in the build and deploy lanes";
`requirements/matrix.md` R24, R25, R26, R39, R40, R41, R42, R46; `design/matrix.md` section 4,
Build table rows B1 to B7 and section 1.4; the owner's statements of 2026-10-19 in the conventions
(quoted in the notes). The order of B2 to B6 is as the Build table lists them (assumption: the
table names the steps, not their order, beyond B1 first and B7 last).

```mermaid
flowchart TD
    S(["Ready Task with its build contract, on its Story's branch"])
    T["The Task states in full what it builds - the matrix ids of its stack, components and shared capabilities (R41) - and carries the decisions made upstream, or pointers to them (Spec, arc42 views)"]
    B1["B1 Workspace - read the stack id the Task states, then matrix node stack for its repository"]
    D1{"Task states a stack?"}
    D2{"Infrastructure Task?"}
    B2["B2 Infrastructure intent - matrix node stack with what it holds, deps --of - provision what the matrix states"]
    B3["B3 Implementers and Green - shared capability ids the Task states, matrix node for each provider and its stack"]
    B4["B4 Regression - matrix impact --id for each entry the Task states"]
    B5["B5 Reuse audit - matrix check-reuse --ids --worktree"]
    B6["B6 Suite run - the stack's commands.test, a resolving session only when it is empty"]
    B7["B7 Commit to the Story's branch and close the Task - no matrix mark"]
    E(["Task's code and tests committed to the Story's branch, whole suite passing"])
    F(["Step fails"])
    S --> T --> B1 --> D1
    D1 -->|"no: fails the step"| F
    D1 -->|yes| D2
    D2 -->|"yes"| B2 --> B3
    D2 -->|"no"| B3
    B3 --> B4 --> B5 --> B6 --> B7 --> E
```

Notes on the required build:

- The matrix is read in every step that needs what it holds, and the build records nothing in it
  (R39, R46, `design/matrix.md` section 4 "the build and deploy steps read the matrix and record
  nothing in it except the verified mark at D8"). The verified mark is set by the driver when the
  Story's pull request merges (D8, `design/matrix.md` 1.4), outside the build of one Task.
- A build step that finds the code different from what the matrix states reports it in its
  result and the step journal, and changes nothing in the matrix (R29, section 4).
- The build trusts upstream: "the task should be detailed so that the build doesn't need to guess
  or interpret or decide on how to do anything that was already concluded upstream", with
  pointers (file paths, URLs) in place of copies; names come from the task or spec, and the
  `resource-naming` skill stays only "as a backuo" (owner, 2026-10-19).
- Values known only at deploy time do not stop the build: "there may be some information that
  just simply isn't known until deploy time, such as the region or environment ... We don't want
  to stop because of that", and "I don't want every subsequent step in a process constantly
  checking that upstream steps were done right" (owner, 2026-10-19).
- Every implementer has the full architecture of the component it works on, through the Spec's
  links to the architecture and design documents (owner, 2026-10-19).
- "Ever agent needs to have a reason to be used", and specialists are chosen by reasoning, not by
  code: "What I do not want is python code deciding which specialists to use" and "I also do not
  want a pipeline that blindly sends everything to ever agent" (owner, 2026-10-19).

## 2. The driver's build lane

**Subject:** how the driver turns a ready Task into a `task-to-deploy` dispatch and settles its
outcome in beads.
**Scope:** one dispatch of one Task.
**Purpose:** show where beads is read and written around the workflow.
**Boundary:** the workflow's own steps are in sections 3 to 5; the deploy lane is outside.
**Basis:** as built. `ops/sdlc-automation/routing.py` `route_build` (lines 340 to 441) and
`workflows/route-build.js` `decide()`; `ops/sdlc-automation/lane.py` `_claim_build` (1113),
`_with_step_journal` (1230), `_unlanded` (1130), `_settle_build` (1155);
`ops/sdlc-automation/buildinput.py` `contract()` (the build contract through the
`beads-contract` CLI, `skills/beads-contract/SKILL.md` "contract"); `journallines.py` (the
`STEP-JOURNAL` lines the workflow logs are applied to the journal file).

```mermaid
flowchart TD
    S(["Driver tick picks a ready bead"])
    R{"route_build - type and labels"}
    SK(["SKIP with a reason - bug, label human, Epic, Story, feature, unknown type"])
    C["Read the build contract - beads-contract contract, criteria from the Task or its Story or Epic"]
    CL["beads - claim the Task, start its Story"]
    J["Open the step journal - plan pipeline build when it has none"]
    DSP["Dispatch task-to-deploy with bead, journal path and run, relay, infraVocabulary, pluginRoot"]
    AP["Apply each STEP-JOURNAL line to the journal file as it is logged - start, done with artifacts and added steps, fail with cause"]
    O{"Outcome ok?"}
    U{"Story worktree clean?"}
    MD["beads - set audit metadata"]
    CLS["beads - close the Task"]
    NC["Record a build-write failure - built but not closed"]
    ST["beads - set build state and stop metadata"]
    REL["beads - release the Task"]
    E1(["Task closed"])
    E2(["Task released - a later dispatch starts at the first step not done"])
    S --> R
    R -->|"skip"| SK
    R -->|"work: a task, or a type or label in the infrastructure vocabulary"| C --> CL --> J --> DSP --> AP --> O
    O -->|"yes"| U
    U -->|"yes"| MD --> CLS --> E1
    U -->|"no: uncommitted changes or no Story branch"| NC --> ST
    O -->|"no"| ST
    ST --> REL --> E2
```

Notes:

- The router decides from type and labels alone; a Task missing its Story or Epic is still routed,
  and `task-to-deploy` refuses one with no Story at its workspace step (section 3).
- `workflows/ROUTING.md` "Type / label to composite" rule 5 lists type `task` as SKIP, while
  `route-build.js` and `routing.py` route a Task to `task-to-deploy`. The two as-built sources
  disagree; the code routes.

## 3. The step journal of a build: workspace to Red

**Subject:** the control flow of `task-to-deploy` from the dispatch to a Red that holds.
**Scope:** the steps `build:workspace`, `build:design-source`, `build:infra-intent`,
`build:regression-assess`, `build:regression-review`, `build:regression-validate`,
`build:baseline`, `build:red-write`, `build:red-check`.
**Purpose:** show every step, what adds the conditional steps, and each loop's exits. Part two is
section 4, part three section 5.
**Boundary:** what each step dispatches is in the sequence diagrams of sections 7 to 11.
**Basis:** as built. `skills/pipeline-contracts/schemas/pipeline-steps.json` `pipelines.build`
(`plan` and each kind's `adds` and `limit`); `workflows/task-to-deploy.js` `stepWorkspace` (1666),
`stepDesignSource` (1697), `stepInfraIntent` (1726), `regressionAssess` (1738),
`regressionReview` (1752), `stepRegressionValidate` (1765), `stepBaseline` (1786),
`stepRedWrite` (1807), `stepRedCheck` (1821), `MAX_RED_CHECKS` (1051).

```mermaid
flowchart TD
    S(["Dispatched with journal path and run"])
    RJ["Read the journal - atw-step-journal read"]
    DJ{"Journal read?"}
    NX["Begin at the first step not done"]
    W["build:workspace - workspace.js keyed by the Story"]
    DW{"repoPath and Story present, worktree established?"}
    AD{"web-ui Task with design source bundle or cds?"}
    DS["build:design-source - depscore.py cds-bundles"]
    AI{"type or label in the infrastructure vocabulary?"}
    II["build:infra-intent - infra-intent.js"]
    RA["build:regression-assess - regression-impact-assessor writes plan.json"]
    RR["build:regression-review - regression-coverage-reviewer writes plan-review.json"]
    RV["build:regression-validate - regression.py validate"]
    BL["build:baseline - suite-run.js resolves and runs the suite"]
    DB{"repository declares a test command?"}
    PL["tdd-red.js plan - names the test agents for the contract's surfaces"]
    RW["build:red-write - one step per test agent, one after another"]
    RC["build:red-check - suite-run.js, then judge Red"]
    DR{"Red holds - a new test fails in Red's files, no load failure, no new failure elsewhere?"}
    D4{"fourth Red check?"}
    DP{"suite fails exactly as at the check before?"}
    G(["Part two - build:select-implementers"])
    F(["Step fails - journal records the cause, run stops"])
    S --> RJ --> DJ
    DJ -->|"no: journal or input failure"| F
    DJ -->|"yes"| NX --> W --> DW
    DW -->|"no: input or workspace failure"| F
    DW -->|"yes"| AD
    AD -->|"yes: adds design-source"| DS --> AI
    AD -->|"no"| AI
    AI -->|"yes: adds infra-intent"| II --> RA
    AI -->|"no"| RA
    RA --> RR --> RV --> BL --> DB
    DB -->|"no: baseline failure, requiredHumanActions"| F
    DB -->|"yes"| PL --> RW --> RC --> DR
    DR -->|"yes: records redRun and testPrint"| G
    DR -->|"no"| D4
    D4 -->|"yes: red-unsatisfied"| F
    D4 -->|"no"| DP
    DP -->|"yes: no-progress"| F
    DP -->|"no: adds red-write per test agent and red-check"| RW
```

Differences from the requirements:

- B1: the workspace takes the repository from the Task's `repoPath`, not from the matrix
  (`node stack:<id>` for `repository`), and fails a Task with no `repoPath` or no Story with
  "re-elaborate the Task's Story", not a Task that states no stack
  (`task-to-deploy.js` 1668 to 1679).
- B4: no step reads `atw-matrix impact --id`. The regression-impact-assessor is told to "Discover
  affected requirements from actual sources" including prior PRDs (`regressionBrief`, 1350): the
  rediscovery by reading that R30 and R38 name as the failure the matrix removes.
- The regression scope is reviewed and validated before any test is written (regression-review,
  regression-validate), which re-checks requirement sources elaboration already bound to the
  Task; the owner does not want "every subsequent step ... constantly checking that upstream steps
  were done right".
- The test agents are named by a lookup table in code from the contract's surfaces
  (`tdd-red.js` `SURFACE_WRITERS`, 243), with `tdd-unit-test-generator` always included: code, not
  reasoning, decides which specialists run.

## 4. The step journal of a build: Green and the reuse audit

**Subject:** the control flow from the implementer selection to a green suite that passed the
reuse audit.
**Scope:** `build:select-implementers`, `build:implement`, `build:green-check`,
`build:test-ruling`, `build:reuse-audit`, and the rounds the audits add.
**Purpose:** show the Green loop, its exits, and how an audit sends work back once.
**Boundary:** the cds audit's own decision is in section 5; it sends work back into this same
loop.
**Basis:** as built. `pipeline-steps.json` kinds `build:select-implementers`, `build:implement`,
`build:green-check` (its `limit`), `build:test-ruling`, `build:reuse-audit` (its `limit`);
`task-to-deploy.js` `stepSelectImplementers` (1889), `stepImplement` (1912), `stepGreenCheck`
(1926), `stepTestRuling` (1983), `stepReuseAudit` (2149), `judgeReuse` (2124), `greenBoundary`
(1621), `MAX_GREEN_CHECKS` (1052).

```mermaid
flowchart TD
    S(["From part one - Red holds"])
    SI["build:select-implementers - atw-matrix uses --ids, then tdd-green.js select"]
    DI{"Task states matrix ids and a valid selection returned?"}
    IM["build:implement - one step per implementer, in order"]
    GC["build:green-check - fingerprint Red's test files, run the suite"]
    DT{"an implementer changed a Red test file with no ruling since?"}
    DG{"suite exits 0?"}
    DA{"answering an audit and upstreamMissing named?"}
    DU{"upstreamMissing named?"}
    DQ{"testIssues named?"}
    TR["build:test-ruling - tdd-red.js update mode, tdd-unit-test-generator"]
    DD{"one valid ruling per named test?"}
    DN{"no file changed and the same failures as the check before?"}
    D8{"eighth check since the round opened?"}
    WH{"which step opened this round?"}
    RU["build:reuse-audit - atw-matrix check-reuse, shared-capability-reviewer on what it cannot rule"]
    DV{"violations?"}
    DF{"first reuse audit?"}
    CA(["Part three - build:cds-audit, its second audit"])
    RS(["Part three - build:refactor-snapshot"])
    F(["Step fails - journal records the cause, run stops"])
    S --> SI --> DI
    DI -->|"no: green"| F
    DI -->|"yes: adds implement per implementer and green-check"| IM --> GC --> DT
    DT -->|"yes: green-modified-tests"| F
    DT -->|"no"| DG
    DG -->|"yes"| DA
    DA -->|"yes: blocked-upstream"| F
    DA -->|"no"| WH
    DG -->|"no"| DU
    DU -->|"yes: blocked-upstream"| F
    DU -->|"no"| DQ
    DQ -->|"yes: adds test-ruling and green-check"| TR --> DD
    DD -->|"no: red-decisions-incomplete"| F
    DD -->|"yes"| GC
    DQ -->|"no"| DN
    DN -->|"yes: no-progress"| F
    DN -->|"no"| D8
    D8 -->|"yes: green"| F
    D8 -->|"no: adds implement per implementer and green-check"| IM
    WH -->|"select-implementers"| RU
    WH -->|"reuse-audit - its second audit follows"| RU
    WH -->|"cds-audit - its second audit follows"| CA
    RU --> DV
    DV -->|"no"| RS
    DV -->|"yes"| DF
    DF -->|"yes: adds implement per implementer, green-check, reuse-audit"| IM
    DF -->|"no: reuse-violation"| F
```

Differences from the requirements:

- B3: an infrastructure Task's implementer is fixed in code as `cdk-stack-author` unless the caller
  names one (`task-to-deploy.js` 1901): code decides the specialist.
- B3: the implementers the build can run are told to name resources. `cdk-stack-author.md` lines
  50 and 65 and `api-gateway-cdk-implementer.md` lines 51 and 71 put naming in "Allowed
  Decisions" and say "Name every resource with the resource-naming skill"; the same instruction is
  in `appsync-cdk-implementer.md` 60, `chassis-extension-implementer.md` 64,
  `cognito-lambda-trigger-implementer.md` 59, `dynamodb-access-layer-implementer.md` 67,
  `event-driven-consumer-implementer.md` 65, `event-api-client-implementer.md` 59,
  `kinesis-stream-implementer.md` 57, `mcp-server-implementer.md` 62,
  `power-tools-configuration-implementer.md` 58, `postgresql-access-layer-implementer.md` 70 and
  `s3-data-lake-implementer.md` 57. The owner: names "should have already been provided in the
  task (or spec)" and the skill stays only as a backup.
- B3 reads `atw-matrix uses --ids` with the Task's ids and hands the providers' names, kinds and
  repositories on; it runs no separate `node` per provider (Q6). The `uses` result carries the
  provider's stack repository, so the facts the row names reach the implementers.
- A Task that states no matrix id fails `build:select-implementers` and `build:reuse-audit`. The
  requirement fails a Task that states no stack at B1; as built the check sits at B3 and B5.
- B5 matches: `check-reuse --ids <ids> --worktree <path>`, and the reviewer's rulings stay in the
  step's result (`reuseAudit`).

## 5. The step journal of a build: refactor to commit

**Subject:** the control flow from the refactor to the commit on the Story's branch.
**Scope:** `build:refactor-snapshot`, `build:refactor`, `build:refactor-check`,
`build:refactor-restore`, `build:cds-audit`, `build:docs-audit`, `build:docs-write`,
`build:final-suite`, `build:regression-map`, `build:regression-map-review`,
`build:regression-verify`, `build:commit`.
**Purpose:** show the undo path of the refactor, the cds audit's single send-back, and the gates
before the commit.
**Boundary:** the Task's close is the driver's (section 2).
**Basis:** as built. `pipeline-steps.json` kinds listed in the scope; `task-to-deploy.js`
`stepRefactorSnapshot` (2000), `stepRefactor` (2008), `stepRefactorCheck` (2022),
`stepRefactorRestore` (2042), `stepCdsAudit` (2053), `stepDocsAudit` (2179), `stepDocsWrite`
(2190), `stepFinalSuite` (2201), `stepRegressionVerify` (1774), `stepCommit` (2210); the step
journal's `together` (the `build:docs-write` steps run concurrently).

```mermaid
flowchart TD
    S(["From part two - green and the reuse audit clean"])
    SN["build:refactor-snapshot - gitutils.py snapshot"]
    RF["build:refactor - tdd-refactor.js, code-refactoring-specialist through GitNexus"]
    DGX{"refactor returned, no GitNexus blocker?"}
    RC["build:refactor-check - suite-run.js"]
    DG{"suite exits 0?"}
    DRS{"tree already restored?"}
    RR["build:refactor-restore - gitutils.py restore to the snapshot"]
    DUI{"web-ui Task with design source bundle or cds?"}
    CA["build:cds-audit - audit-app.py for a bundle, cds-live-auditor otherwise"]
    DV{"violations?"}
    DF{"first cds audit?"}
    DGP{"cds gaps?"}
    BACK(["Part two - implement per implementer and green-check, then cds-audit again"])
    DA["build:docs-audit - documentation-currency-auditor"]
    DS{"stale documents?"}
    FK["fork"]
    DW["build:docs-write - one step per documentation agent assigned"]
    JN["join"]
    FS["build:final-suite - suite-run.js"]
    DFS{"suite exits 0?"}
    RM["build:regression-map - regression-impact-assessor writes mapped.json"]
    RMR["build:regression-map-review - regression-coverage-reviewer"]
    RVF["build:regression-verify - regression.py verify runs the mapped tests"]
    DVF{"evidence verified?"}
    CM["build:commit - settle.js commitOnly"]
    DC{"committed on the Story branch?"}
    E(["Committed - handback ok, stage committed"])
    F(["Step fails - journal records the cause, run stops"])
    S --> SN --> RF --> DGX
    DGX -->|"no: refactor"| F
    DGX -->|"yes"| RC --> DG
    DG -->|"no"| DRS
    DRS -->|"yes: refactor"| F
    DRS -->|"no: adds refactor-restore and refactor-check"| RR --> RC
    DG -->|"yes"| DUI
    DUI -->|"yes: adds cds-audit"| CA --> DV
    DUI -->|"no"| DA
    DV -->|"yes"| DF
    DF -->|"yes: adds the implementers' round and cds-audit"| BACK
    DF -->|"no: cds-audit"| F
    DV -->|"no"| DGP
    DGP -->|"yes: blocked-upstream"| F
    DGP -->|"no"| DA
    DA --> DS
    DS -->|"yes: adds docs-write per agent"| FK --> DW --> JN --> FS
    DS -->|"no"| FS
    FS --> DFS
    DFS -->|"no: commit, nothing committed"| F
    DFS -->|"yes"| RM --> RMR --> RVF --> DVF
    DVF -->|"no: regression-coverage"| F
    DVF -->|"yes"| CM --> DC
    DC -->|"no"| F
    DC -->|"yes"| E
```

## 6. How a deterministic command runs

**Subject:** the checked relay every script step uses: `gitutils.py`, `atw-matrix`,
`regression.py`, `depscore.py`, `atw-step-journal` and the suite command.
**Scope:** one command.
**Purpose:** the sequence diagrams below draw each such call as one arrow; this is what the arrow
is.
**Boundary:** what each command does.
**Basis:** as built. `task-to-deploy.js` `relayKit` (159 to 673: `registeredCommand`, `exec`,
`run`), `gitutils` (1195), `matrixCommand` (1206, role `build-workflow`); `agents/workflow-command-runner.md`.

```mermaid
sequenceDiagram
    autonumber
    participant WF as task-to-deploy.js step
    participant WCR as workflow-command-runner (sonnet)
    participant RR as relayrun.py
    participant CMD as the command
    participant RD as relay directory
    WF->>WCR: run exactly this one command line, argv checksum-guarded
    WCR->>RR: python3 relayrun.py ... --argv-sha256 ...
    RR->>CMD: run the argv once in the tree
    CMD-->>RR: exit status and output
    RR-)RD: write the relay file for the step
    RR-->>WCR: one RELAY64v1 line, checksum, exit status
    WCR-->>WF: the line copied as opaque text
    alt copy hashes to the checksum
        WF->>WF: use the keys asked for
    else damaged copy or unknown outcome
        WF->>RD: read the relay file bound to that command line
        Note over WF,RD: the command never runs twice
    end
```

## 7. Workspace, design source and provisioning intent

**Subject:** the first steps: the Story's worktree, the design source of a web-ui Task, the
provisioning intent of an infrastructure Task.
**Scope:** `build:workspace`, `build:design-source`, `build:infra-intent`.
**Purpose:** what each agent receives and produces, and where git and the matrix are touched.
**Boundary:** the routing and claim before it (section 2).
**Basis:** as built. `task-to-deploy.js` `stepWorkspace`, `selectDesign` (1533),
`stepDesignSource`, `stepInfraIntent`; `workflows/workspace.js` (provision 805, independent
verification 817); `workflows/infra-intent.js` (prompt and schema, 172 to 232).

```mermaid
sequenceDiagram
    autonumber
    participant TTD as task-to-deploy.js
    participant WS as workspace.js
    participant II as infra-intent.js
    participant CID as cdk-infrastructure-designer
    box beads
    participant BD as Task bead
    end
    box git / GitHub
    participant GIT as repository and worktree
    end
    box matrix
    participant MX as atw-matrix
    end
    Note over TTD,BD: the bead argument is the build contract the driver read from beads
    TTD->>TTD: repoPath and Story present?
    Note right of TTD: differs from required - B1 reads the repository from matrix node stack
    TTD->>WS: repoPath, beadId the Story, branchPrefix story
    WS->>GIT: gitutils.py provision - reuse the Story's tree or cut repo/.worktrees/story-...
    GIT-->>WS: tree, branch, defaultBranch
    WS->>GIT: gitutils.py facts - separate run verifies a linked worktree on that branch
    GIT-->>WS: facts
    WS-->>TTD: ok, repoPath the worktree, branch, defaultBranch
    TTD-)TTD: record worktree, branch, defaultBranch
    opt web-ui Task with design source bundle or cds
        TTD->>TTD: depscore.py cds-bundles - newest bundle supplied for the Task's artifact
        TTD-)TTD: record design - designSource, bundle, buildSpecs
    end
    opt type or label in the infrastructure vocabulary
        TTD->>II: change - id, title, description, worktree
        II->>CID: produce CDK-expressible provisioning intent, name every stack and resource with resource-naming
        Note right of CID: differs from required - B2 reads node stack and deps --of and provisions what the matrix states, the build names nothing upstream named
        CID-->>II: resources, stacks, crossStackRefs, affectedStacks, rationale
        II-->>TTD: provisioningIntent, affectedStacks
        TTD-)TTD: record provisioning
    end
    Note over MX: no matrix call in these steps
```

## 8. Regression scope, mapping and verification

**Subject:** the cumulative regression artifacts written before Red and finished before the
commit.
**Scope:** `build:regression-assess`, `-review`, `-validate`, and later `build:regression-map`,
`-map-review`, `-verify`.
**Purpose:** what the assessor and the reviewer receive and write, and what the script checks.
**Boundary:** the tests themselves are written in Red.
**Basis:** as built. `task-to-deploy.js` `REGRESSION_FILES` (1321), `regressionInvoke` (1329),
`author` (1340), `regressionBrief` (1348), `regressionReviewBrief` (1352), `regressionAssess`,
`regressionReview`, `stepRegressionValidate`, `stepRegressionVerify`; `scripts/portfolio/regression.py`
modes `prepare`, `validate`, `verify`.

```mermaid
sequenceDiagram
    autonumber
    participant TTD as task-to-deploy.js
    participant REG as regression.py
    participant RIA as regression-impact-assessor
    participant RCR as regression-coverage-reviewer
    participant RD as relay directory regression
    box vault
    participant VS as Spec and PRDs
    end
    box git / GitHub
    participant WT as worktree
    end
    TTD->>REG: prepare --plan plan.json --ledger worktree/.agent-workforce/regression.json --source each Spec path
    REG-)RD: previous.json - requirements and mappings recorded before this Task
    TTD->>RIA: contract, previous.json, produce the impact scope before Red
    RIA->>VS: read the Spec, prior PRDs, connected contracts
    RIA->>WT: read code and existing tests
    Note right of RIA: differs from required - B4 reads matrix impact --id for each entry the Task states
    RIA-)RD: plan.json candidate, accepted against REGRESSION_SCHEMA
    TTD->>RCR: review plan.json against sources, code, tests and previous.json
    RCR-)RD: plan-review.json - approved, findings, evidence
    TTD->>REG: validate --plan plan.json --review plan-review.json
    REG-->>TTD: ok, requiredKinds
    alt not ok
        TTD-)TTD: fail regression-plan
    end
    Note over TTD,WT: Red, Green, refactor, audits, docs and the final suite run here
    TTD->>REG: prepare --approved-plan plan.json
    TTD->>RIA: keep the scope unchanged, finalize mappings and runs from the saved tests
    RIA-)RD: mapped.json
    TTD->>RCR: check each mapping and replacement keeps the old assertions
    RCR-)RD: mapped-review.json
    TTD->>REG: verify --plan mapped.json --review mapped-review.json --approved-plan plan.json
    REG->>WT: run each mapped command, read its JUnit report
    REG-->>TTD: ok and the evidence
    TTD-)TTD: record regressionEvidence, or fail regression-coverage
```

## 9. Baseline and Red

**Subject:** resolving the suite command, the baseline run, and the Red loop.
**Scope:** `build:baseline`, `build:red-write`, `build:red-check`, and the ruling on named tests
(`build:test-ruling`), which uses the same workflow.
**Purpose:** how test writers are chosen, what they receive, and how Red is judged by the run,
not by the agents' reports.
**Boundary:** Green (section 10).
**Basis:** as built. `task-to-deploy.js` `suite` (1309), `stepBaseline`, `stepRedWrite`,
`stepRedCheck`, `stepTestRuling`, `contractAt` (1247); `workflows/suite-run.js` (`resolvePrompt`
821, `test-command-resolver` 851, the run 880, `test-failure-parser` 906); `workflows/tdd-red.js`
(`SURFACE_WRITERS` 243, `plan` 263, `authorPrompt`, `updatePrompt`, writers in sequence 351).

```mermaid
sequenceDiagram
    autonumber
    participant TTD as task-to-deploy.js
    participant SR as suite-run.js
    participant TCR as test-command-resolver
    participant TFP as test-failure-parser
    participant RED as tdd-red.js
    participant TW as test writer
    box git / GitHub
    participant WT as worktree
    end
    box vault
    participant VS as Spec
    end
    box arc42 (vault)
    participant AV as architecture views
    end
    TTD->>SR: repoPath the worktree, no command yet
    SR->>TCR: find the test command in AGENTS.md, CLAUDE.md or Taskfile test
    Note right of TCR: differs from required - B6 reads the stack's commands.test, a session only when it is empty
    TCR-->>SR: command, or none
    SR->>WT: run the command once through relayrun.py
    opt exit is not 0
        SR->>TFP: read the relay file, name the failures
        TFP-->>SR: failing - kind test or load, file, test, line
    end
    SR-->>TTD: exitCode, summary, failing, tail, command
    TTD-)TTD: record suiteCommand and baseline
    TTD->>RED: contract, plan true
    RED-->>TTD: testAgents - tdd-unit-test-generator plus one per surface from SURFACE_WRITERS
    Note right of RED: differs from required - code, not reasoning, picks the test specialists
    loop until Red holds, at most four checks, or a check repeats the one before
        loop each test agent, one after another
            TTD->>RED: contract, testAgent, feedback from the last check, prior test files
            RED->>TW: write failing tests for the acceptance criteria, test code only
            TW->>VS: read the Spec sections named
            TW->>AV: read the architecture views the Task is designed against
            TW->>WT: add tests, run them narrowed
            TW-->>RED: testFiles, redConfirmed, evidence
            RED-->>TTD: testFiles, redConfirmed
        end
        TTD->>SR: the recorded command
        SR->>WT: run the whole suite
        SR-->>TTD: the run
        TTD->>TTD: judge Red against the baseline failures
        TTD->>WT: gitutils.py hash-files - fingerprint Red's test files when Red holds
    end
```

## 10. Green: implementer selection, implementation and the test ruling

**Subject:** how implementers are chosen and run, how the suite judges them, and how a test an
implementer disputes is ruled on.
**Scope:** `build:select-implementers`, `build:implement`, `build:green-check`,
`build:test-ruling`.
**Purpose:** what each implementer receives (contract, shared capabilities, Spec and arc42
pointers, feedback) and produces, and where the matrix is read.
**Boundary:** the audits (section 11).
**Basis:** as built. `task-to-deploy.js` `stepSelectImplementers`, `capabilityBrief` (1868),
`greenFeedbackAt` (1632), `baselineNoteAt` (1625), `stepImplement`, `stepGreenCheck`,
`stepTestRuling`, `checkTestDecisions` (1131); `workflows/tdd-green.js` (`IMPLEMENTER_ROSTER`,
the `implementation-lead` selection, `reuseBlock`, `GREEN_SCHEMA`); `agents/implementation-lead.md`.

```mermaid
sequenceDiagram
    autonumber
    participant TTD as task-to-deploy.js
    participant GR as tdd-green.js
    participant IL as implementation-lead
    participant IMP as implementer
    participant RED as tdd-red.js
    participant UTG as tdd-unit-test-generator
    participant SR as suite-run.js
    box matrix
    participant MX as atw-matrix
    end
    box vault
    participant VS as Spec
    end
    box arc42 (vault)
    participant AV as architecture views
    end
    box git / GitHub
    participant WT as worktree
    end
    TTD->>MX: uses --ids the Task's matrix_elements, role build-workflow
    MX-->>TTD: capabilities - feature, provides, providers with stack repository
    TTD->>GR: contract with sharedCapabilities, red, select true, implementer cdk-stack-author for an infrastructure Task
    alt no implementer named
        GR->>IL: select the fewest implementers from the roster, in build order
        IL->>VS: read the Spec documents
        IL->>AV: read the architecture views
        IL-->>GR: implementers, rationale
    end
    GR-->>TTD: implementers
    TTD-)TTD: record implementers and sharedCapabilities
    loop until the suite exits 0, at most eight checks per round
        loop each implementer, in order
            TTD->>GR: contract, red, implementers, only this one, feedback
            GR->>IMP: SHARED CAPABILITIES THIS TASK MUST USE, Task, Spec and arc42 pointers, Red evidence, baseline repair scope, make the failing tests pass, do not change tests
            IMP->>VS: read the Spec sections
            IMP->>AV: read the architecture views
            IMP->>WT: change production code, run the suite
            IMP-->>GR: changedFiles, testIssues, upstreamMissing, evidence
            GR-->>TTD: changedFiles, testIssues, upstreamMissing
        end
        TTD->>WT: gitutils.py hash-files - did a Red test file change?
        TTD->>SR: the recorded command
        SR->>WT: run the whole suite
        SR-->>TTD: the run
        opt not green and testIssues named
            TTD->>RED: contract, testIssues, test files, the last run
            RED->>UTG: rule on each named test - update, delete or keep, citing the contract
            UTG->>WT: change test code only
            UTG-->>RED: decisions, testFiles
            RED-->>TTD: decisions
            TTD->>TTD: one valid ruling per named test, else fail red-decisions-incomplete
        end
    end
    Note over TTD,MX: the build records nothing in the matrix - upstreamMissing stays in the step journal
```

## 11. Audits: reuse, refactor and cds

**Subject:** the checks that follow Green and may send work back once.
**Scope:** `build:reuse-audit`, `build:refactor-snapshot`, `build:refactor`,
`build:refactor-check`, `build:refactor-restore`, `build:cds-audit`.
**Purpose:** the matrix read of B5, the GitNexus-only refactor and its undo, and the cds audit
for a web-ui Task.
**Boundary:** the rounds they add re-enter section 10.
**Basis:** as built. `task-to-deploy.js` `stepReuseAudit`, `judgeReuse`, `REUSE_JUDGMENT_SCHEMA`,
`stepRefactorSnapshot`, `stepRefactor`, `stepRefactorCheck`, `stepRefactorRestore`,
`stepCdsAudit`, `auditCds` (1453, `RUN_CDS_AUDIT_PY`), `auditCdsLive` (1590);
`workflows/tdd-refactor.js` (snapshot 834, the specialist's prompt 849 to 900, blocker and revert
handling, `gitutils.py changed` 957).

```mermaid
sequenceDiagram
    autonumber
    participant TTD as task-to-deploy.js
    participant SCR as shared-capability-reviewer
    participant RFW as tdd-refactor.js
    participant CRS as code-refactoring-specialist
    participant CLA as cds-live-auditor
    participant SR as suite-run.js
    box matrix
    participant MX as atw-matrix
    end
    box git / GitHub
    participant WT as worktree
    end
    TTD->>MX: check-reuse --ids the Task's ids --worktree
    MX-->>TTD: violations, judgment, unchecked, clean
    opt definitions the check cannot rule on
        TTD->>SCR: each definition with the capability and provides entry
        SCR->>WT: read the definitions
        SCR-->>TTD: duplicate or not-duplicate, with a reason
    end
    TTD-)TTD: record reuseAudit - violations go back to the implementers once
    TTD->>WT: gitutils.py snapshot - record the tree id
    TTD->>RFW: contract, changedFiles, snapshotTree
    RFW->>CRS: refactor the changed files without changing behavior, GitNexus impact, rename, detect_changes
    CRS->>WT: refactor, run the suite
    CRS-->>RFW: testsGreen, reverted, evidence, blastRadius, detectChanges, gitnexusBlocker
    alt GitNexus blocker or reverted
        RFW->>WT: gitutils.py restore to the snapshot
    else refactored
        RFW->>WT: gitutils.py changed since the snapshot
    end
    RFW-->>TTD: changedFiles, restored
    TTD->>SR: run the whole suite
    SR-->>TTD: the run
    alt red after the refactor
        TTD->>RFW: restoreTo the snapshot
        RFW->>WT: gitutils.py restore
        TTD->>SR: run the whole suite again
    end
    opt web-ui Task with design source bundle or cds
        alt a cds bundle
            TTD->>WT: audit-app.py --repo --bundle, digest checked
        else no bundle
            TTD->>CLA: audit the changed UI files against the live design system
            CLA-->>TTD: findings ruled violation, allowed or cds-gap
        end
        TTD-)TTD: record cdsAudit - violations back to the implementers once, a gap fails blocked-upstream
    end
```

## 12. Documentation, the final suite and the commit

**Subject:** the documentation audit and updates, the final suite run, and the commit on the
Story's branch; then the driver's close.
**Scope:** `build:docs-audit`, `build:docs-write`, `build:final-suite`, `build:commit`, and the
driver's `_settle_build`.
**Purpose:** who is chosen to write documents and how, and where git and beads are written.
**Boundary:** the regression mapping between the final suite and the commit (section 8).
**Basis:** as built. `task-to-deploy.js` `stepDocsAudit`, `stepDocsWrite`, `allChangedAt` (2177),
`stepFinalSuite`, `stepCommit`, `handback` (2270); `workflows/documentation.js` (`WRITERS`,
the auditor's prompt, `writerForPath`, `assignment` mode); `workflows/settle.js` `commitRun`
(commit agent `github-actions-pipeline-implementer`); `ops/sdlc-automation/lane.py`
`_settle_build`.

```mermaid
sequenceDiagram
    autonumber
    participant DRV as driver lane.py
    participant TTD as task-to-deploy.js
    participant DOC as documentation.js
    participant DCA as documentation-currency-auditor
    participant DWR as documentation writer
    participant SR as suite-run.js
    participant ST as settle.js
    participant GAP as github-actions-pipeline-implementer
    box git / GitHub
    participant WT as worktree and Story branch
    end
    box beads
    participant BD as Task bead
    end
    TTD->>DOC: contract, every file the implementers and the refactor changed, auditOnly
    alt only tests and fixtures changed
        DOC-->>TTD: no stale documents
    else
        DOC->>DCA: which READMEs, API docs, changelog, user guides are stale, assign each to a writer of the roster
        DCA->>WT: read the documents and the change
        DCA-->>DOC: staleDocs, assignments
        DOC->>DOC: a stale document left unassigned goes to a writer by its path
        Note right of DOC: differs from required - code picks the writer for an unassigned document
        DOC-->>TTD: staleDocs, assignments
    end
    par one per documentation agent assigned
        TTD->>DOC: assignment - agent and its documents
        DOC->>DWR: update these documents to match the change
        DWR->>WT: edit the documents
        DWR-->>DOC: updatedDocs
        DOC-->>TTD: updatedDocs
    end
    TTD->>SR: run the whole suite a final time
    SR-->>TTD: the run - nothing is committed unless it exits 0
    TTD->>ST: worktree, commitOnly, branch, defaultBranch, message the Task id and title
    ST->>WT: gitutils.py facts before
    ST->>GAP: commit every change, type(scope) message, no --no-verify, fix hook findings or report blocked
    GAP->>WT: git add -A and commit on the Story branch
    GAP-->>ST: blocked
    ST->>WT: gitutils.py facts after - HEAD moved, same branch
    ST-->>TTD: status reported, commit
    TTD-->>DRV: ok, stage committed, commit, suite command and summary
    DRV->>WT: git status of the Story worktree - clean?
    DRV-)BD: set audit metadata, close the Task
    Note over DRV,BD: no push and no pull request here - the Story's deploy opens one
```

## 13. A step of the step journal

**Subject:** the states one journal step passes through, in the workflow's copy and in the file.
**Scope:** any step of pipeline `build`.
**Purpose:** show restart: a run begins at the first step that is not done, and a step that ran
before starts again from its beginning.
**Boundary:** the order of the steps (sections 3 to 5).
**Basis:** as built. `skills/pipeline-contracts/schemas/step-journal.schema.json`
`definitions/stepStatus` (planned, running, done, failed); the `step-journal` shared block in
`task-to-deploy.js` (674 to 948: `next`, `start`, `done`, `fail`, `run`, `together`);
`ops/sdlc-automation/journalstart.py` `start_at` (`invalidate_from`).

```mermaid
stateDiagram-v2
    [*] --> planned: in the up-front plan / or added by an earlier step's result
    planned --> running: next() picks it [first step not done] / start - artifacts cleared, STEP-JOURNAL start
    running --> done: step function returns artifacts and add / STEP-JOURNAL done, added steps placed right after it
    running --> failed: step function returns fail, throws, or the run is interrupted / STEP-JOURNAL fail with stage and message
    failed --> running: a later dispatch [it is the first step not done] / start again from its beginning
    running --> running: a later dispatch after a stopped run [status still running] / start again, artifacts of the unfinished run dropped
    done --> planned: start_at named this step or an earlier one / invalidate_from resets it and every step after it
    done --> [*]: the run reaches the end of the journal
```

## Agents the build dispatches, and how each is chosen

Basis: as built (the files cited in sections 6 to 12).

| Agent | Step | Chosen by |
|---|---|---|
| `workflow-command-runner` | every script step | always, for each command (section 6) |
| `cdk-infrastructure-designer` | `build:infra-intent` | code: an infrastructure type or label |
| `regression-impact-assessor`, `regression-coverage-reviewer` | the six regression steps | always |
| `test-command-resolver`, `test-failure-parser` | every suite run | the resolver when no command is recorded, the parser when the suite exits non-zero |
| `tdd-unit-test-generator` and the surface test writers | `build:red-write`, `build:test-ruling` | code: `SURFACE_WRITERS` from the contract's surfaces, the unit writer always |
| `implementation-lead` | `build:select-implementers` | always, unless the caller or code names the implementer |
| the implementers of `IMPLEMENTER_ROSTER` | `build:implement` | `implementation-lead`, or `cdk-stack-author` fixed for an infrastructure Task |
| `shared-capability-reviewer` | `build:reuse-audit` | definitions `atw-matrix check-reuse` cannot rule on |
| `code-refactoring-specialist` | `build:refactor` | always |
| `cds-live-auditor` | `build:cds-audit` | a web-ui Task with design source cds and no bundle |
| `documentation-currency-auditor` | `build:docs-audit` | unless only tests and fixtures changed |
| `api-documentation-writer`, `readme-writer`, `changelog-writer`, `user-guide-writer` | `build:docs-write` | the auditor, or `writerForPath` for a document it left unassigned |
| `github-actions-pipeline-implementer` | `build:commit` | always, when the tree has changes |

Not dispatched by the build as built: `workflows/adversarial.js` (its testers and
`adversarial-critique-adjudicator`) and `workflows/gate-enforce.js` (`phase-gate-enforcer`); no
workflow in the build lane names either. `agents/test-coverage-gap-reviewer.md` says the
`tdd-red` workflow dispatches it, and `workflows/tdd-red.js` does not.

## Stores read and written by the build

Basis: as built, compared with required (`design/matrix.md` section 4, Build table).

| Store | Read | Written |
|---|---|---|
| beads | the build contract (driver, `beads-contract contract`) | the driver claims the Task, starts the Story, closes or releases the Task and sets build metadata |
| matrix | `uses --ids` (B3) and `check-reuse` (B5), role `build-workflow` | nothing, as required |
| arc42 (vault) | the architecture views the Task's `decisionIds` name, by the test writers, `implementation-lead` and the implementers | nothing |
| vault | the Spec documents and sections, and prior PRDs by the regression agents | nothing |
| git / GitHub | the worktree, through `gitutils.py` and the agents | the Story's worktree and branch (created or reused), the code, tests and documents, one commit per Task; no push |

## Differences from the requirements, in one list

1. B1: repository from `repoPath`, not `atw-matrix node stack:<id>`; the refusal names a missing
   `repoPath` or Story, not a missing stack (sections 3 and 7).
2. B2: `infra-intent.js` reads no matrix and has `cdk-infrastructure-designer` design resources and
   stacks again and name them with the `resource-naming` skill, re-deciding what upstream decided
   (section 7).
3. B3: thirteen implementer definitions tell the implementer to name resources, two of them with
   naming among their "Allowed Decisions" (section 4).
4. B4: the regression scope is rediscovered from sources, not read with `impact --id` (sections 3
   and 8).
5. B6: the suite command is resolved from `AGENTS.md`, `CLAUDE.md` or the Taskfile by a session,
   not read from the stack's `commands.test` (section 9).
6. Specialists chosen by code: the test writers (`SURFACE_WRITERS`), the implementer of an
   infrastructure Task (`cdk-stack-author`), and the writer of an unassigned document
   (`writerForPath`) (sections 3, 4 and 12).
7. Re-checks of upstream: the regression scope review and validation re-check the requirement
   sources elaboration bound to the Task, and the missing-id refusals sit at B3 and B5 rather than
   at B1 (sections 3 and 4).

## Assumptions

- Section 1: the order of B2 to B6 is the order the Build table lists them.
