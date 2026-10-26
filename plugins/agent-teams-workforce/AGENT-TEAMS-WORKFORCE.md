# Inside the Agentic SDLC Workforce

221 agents. Five task categories. Two pipelines, one upstream creation phase, one cross-cutting documentation team, and a governance tier that no one outranks. This is a complete software delivery lifecycle staffed entirely by bounded specialist agents — and the central design bet is that none of them is trusted very much.

The doctrine behind the system is simple to state: the agent is not the unit of trust; the workflow is. Every agent has a narrow purpose, explicit decision boundaries, least-privilege tools, and exactly one task category — *plan*, *orchestrate*, *execute*, *approve*, or *test*. An agent that plans never decides. An agent that builds never approves its own output. An agent that finds a flaw never fixes it. Work moves between agents through explicit artifacts. Where a composite gates a phase, the gate has three possible outcomes: pass, loop with structured feedback, or escalate upstream.

## The workflows

The system is a designed thing: two pipelines, a row of gates, a 221-agent doctrine of separated authorities. But doctrine is not what runs. What runs is deterministic code: `Workflow` scripts for the build pipeline, and a Python orchestrator for elaboration that runs the steps of a step journal. Both call agents as isolated sessions and route the next step from the facts each step returns. The agent is not the unit of trust; the script is. An agent produces work; it never decides whether its own work passed. The script reads the phase's reported facts (`greenConfirmed`, `deployedToDev`, `smokePassed`); the script alone owns what happens next.

The two pipelines are conceptual. Their realization is composable: small single-phase **minis** stitched into **composites**, with Documentation running as a parallel track. The doctrine below describes the shape; the status section says how much of that shape is wired.

```mermaid
graph TD
  subgraph GOV[Governance authorities]
    ENF[phase-gate-enforcer]
    EXH[exhausted-gate-ruler]
    CON[constitutional-agent]
    ADV[advantage-evaluator]
    CTX[context-curator]
  end

  GOV --> PIPE

  subgraph PIPE[Pipeline]
    P0[PRD Creation] --> PTS[PRD to Spec and Tasks]
    PTS --> STD[Spec to Deployment]
  end

  DOC[Documentation — cross-cutting] -.- PTS
  DOC -.- STD
```

### Governance — the separated authorities

Above both pipelines sits a small set of standalone specialists, each holding exactly one authority. No agent sequences the phases: the workflow scripts and the Python orchestrator do, and route each gate outcome. The `phase-gate-enforcer` referees the constitutive criteria at every gate that carries one: constitutive failures are hard stops; competitive criteria never reach it and are recorded as flags by the gate script. The `exhausted-gate-ruler` rules a gate whose loops are spent when `gate-enforce` runs in `exhaustion` mode: proceed with named residuals, or one directed revision. The `advantage-evaluator` rules commit or revert on work that proceeded under a competitive flag, and the `constitutional-agent` rules a conflict between two constitutive constraints; no workflow dispatches either. The `context-curator` assembles context indexes of pointers so that every constitutive constraint is carried by pointer and never summarized away. No agent holds more than one authority.

The realized substrate matches this separation. Orchestration is native `Workflow` scripts — no external state machine. Beads holds work state (which bead is ready, which is in progress, what was decided). Agent Mail holds file reservations and build slots so concurrent work does not collide. Where a gate runs, the script calls the gate agent separately from the producing agent, which makes segregation of duties a property of the code rather than a request to a model.

### Phase 0 — PRD Creation

Upstream of everything, `prd-creation` turns a raw stakeholder request into a structured intake, then one persona and one objective with its key results, then a draft PRD that `prd-alignment-verifier` checks against them; when the writer and the verifier do not converge, `review-dispute-decider` rules. `prd-validation` then checks a PRD with one specialist per lens. No pipeline picks a draft up: `prd-to-spec` starts only from a ready PRD.

### PRD to Spec and Tasks

`prd-to-spec` elaborates one ready Epic from a PRD that the run reads and never writes. One dispatch is one pass over the Epic's step journal: the journal lists the steps, the run starts at the first step that is not done, and nothing else decides where it begins. The outermost steps are Open the run, Architecture, TRD, Specs and Stories, Tasks, Task edges, Score the Tasks, Apply the done rule, Story edges and Mark the Epic elaborated. Opening the run brings the Epic's PRD row and the document rows in the matrix up to date and writes the architecture context file. In the Architecture step one agent, `aws-solutions-architect`, establishes the architecture the PRD needs and has the TRD written with it (see *The architecture step* below). The TRD step confirms the reviewed TRD: every source it cites resolves, and the Epic bead carries its path and digest. The TRD is the CARRIER: the single point at which architecture-imposed obligations enter the build chain, since the Specs, Stories and Tasks are built from it. Its requirements come from the PRD requirements that need a technical obligation, from the standing obligations of the approved architecture and section 2 that apply to an element this PRD involves, and from each shared capability the design uses, as one requirement of kind `reuse`; each has a checkable value, a source and the matrix element it applies to. It cites arc42 rather than restating it. A Story is one repository's share of what the Epic builds. The repository span is read from the architect's result: what the Stories build is the services, components, infrastructure and events it lists under `addedOrChangedElements`, and the existing elements it names under `unchangedWorkElements` as where Epic work that leaves their architecture unchanged lands (an Epic can have both, such as a new service and new wording on an existing page), each event with the service or component that publishes it (an event is a fact with a meaning, its name, its publisher and when it is triggered, and it is built as part of its publisher, never as a Story or Task of its own). The matrix is used only to find the stack the architecture side places each in and that stack's repository; everything else the Epic reaches is context, handed to the Tasks as what they depend on or use. A stack that names no repository is given the name the project's naming rules give it, and a repository the inventory lacks is created from the template its stacks' type names, only when a Story builds in it. Under Specs and Stories each repository of the span has its own container of steps: the repository context; for a frontend repository the UI bundle listing, the `ui-design-source-selector` session and its check against the bundles; the contracts session and the data-model session, which run together; the UI section; the acceptance-criteria session; for a repository whose stacks hold a DynamoDB store, a review of the data model by `dynamodb-schema-access-pattern-reviewer`; one review against the implementation criteria, whose findings go once to each author, with a disputed finding ruled on by `review-dispute-decider`; the Story document; and the Story bead write. Under Tasks each repository has the decomposition context, the `task-decomposer` session, the plan (coherent Tasks that each cover several of the things the Story builds, every thing cited by some Task, sized, in build order, with one correction session when a thing the Story builds is uncited or a Task is unsized), one step per Task bead write, the step that retires Task beads the plan no longer names, and the written record. An open Task of another Epic in the same repository that already plans the work is not duplicated: the Tasks that need it get a `blocks` edge onto it. Task edges derives the edges the elements' `requires` relations make between Stories, has `task-dependency-mapper` map further ones when the span has more than one repository, and writes them. Then the Tasks are scored, the done rule is applied, Story edges are written and the Epic is marked elaborated. Each step takes its inputs from the artifacts of the steps its `inputs` name and records its output in the journal right after writing it; the Story bead write and each Task bead write also create that bead's own journal. Every bead write is keyed by the durable elaboration key (`bead_metadata.KEY_ELAB_KEY`, defined in `skills/beads-contract/schemas/bead-metadata.schema.json`), so a step that runs again updates the Story or Task it finds and creates no second one.

`prd-to-spec` owns the Epic's elaboration lifecycle, and every door into elaboration passes through it. The pipeline's driver starts it, and selects an Epic only when it is open, carries a WSJF score, depends (through `tracks` edges, which record architecture dependencies: an architecture decision it rests on is established from that Epic's requirements first) on no Epic whose elaboration is not done, and is ready, or in progress with no live run owning it. The owner sets those `tracks` edges and the Epics' WSJF once, before `keeper.py` runs (`scripts/portfolio/epicorder.py` computes every Epic's edges from the matrix chain alone: only shared foundations (`shared-*`, `*-lib` and `*-infra` stacks with what is homed in them, and layers and packages) order Epics, each not approved has one driving Epic (the owner's `drives` decision, or strictly the most serving features `realizedBy` it; `epicDriver: none` or a tie means none, and no edge), every other Epic that realizes or uses it waits for that driver, and cycles are broken by dropping the edge whose driver has the fewest features; and, with `--apply`, replaces every Epic-to-Epic edge in beads with them; `wsjf-scoring` scores); the driver only reads them and never starts `dependency-assessment`, `task-dependency-assessment` or `wsjf-scoring`. At the start of a dispatch `elaboration.start` refuses, with a named reason, an Epic that is not open, whose elaboration is done, or that another run owns; otherwise it marks the Epic's elaboration as started under an owner token. The elaboration-state keys and their values are defined once, in `skills/beads-contract/schemas/bead-metadata.schema.json` (`bead_metadata.KEY_ELABORATION_STATE`, `ELABORATION_STATES`, `ELABORATION_CAUSES`). Each Task inherits the Epic's value and time criticality, carries its own judged size, and is written with every WSJF component. Until its elaboration is done the Epic is sized by its judged estimate, never by the Tasks written so far. Build dependencies are Task-to-Task `blocks` edges only — a Story only groups Tasks. Two business requirements the architecture decider finds no design can satisfy together, a design that only works against a section 2 constraint, or a GitHub sign-in or organisation membership the run needs before it can create a span repository holds the Epic for a person with one named command. The scoring step (`elaboration.finish`, with its scope limited to the Epic's Tasks) scores the Epic's Tasks with RR-OE counted across Stories and writes no WSJF value on the Epic; the last step sets the Epic's elaboration state to done (`bead_metadata.ELABORATION_DONE`) when every Task is scored; the Epic itself stays open until its work is released.

```mermaid
graph LR
  P[Ready PRD] --> L[elaboration-start]
  L --> O[Open the run]
  O --> A[Architecture: architect, check, review, promotion]
  A --> R[TRD confirmed]
  R --> RS[Repository span from the matrix]
  RS --> S[Spec Authoring, per repo]
  S --> T[Task Decomposition, per Story]
  T --> X[Cross-Story Task edges]
  X --> SC[Score the Tasks, done rule, Story edges]
  SC --> E[Mark the Epic elaborated]
  S -. write-story .-> B[(beads)]
  T -. write-task .-> B
  X -. write-all-task-edges .-> B
```

### The architecture step

The architecture lives in the architecture directory (the run's `archPath`, from `ATW_ARCH_PATH`; see *Project configuration*): the effective documents in `arc42/`, one folder per arc42 section, and in `detailed/`, the architecture below arc42's level (one component, one feature, components working together, the whole system); and, in `built/<element>/`, what a Story built that differs from them. The architecture documentation model in `reference/` defines both and what each section holds. Section 2 holds the owner's constraints: the pipeline reads them and never writes them. Each document's front matter (`view_type`, `scope`, `subject`, `shows`, `lifecycle_state`) is its catalog entry. `lifecycle_state` is per file: `effective` was reviewed and approved; `in-review` is input to check, never assumed vetted. The matrix, read and written through `atw-matrix`, records how repositories, stacks, elements, PRDs, features, design facts and documents relate, which content is approved and which code is trusted.

The Architecture step of the Epic's journal holds these steps:

1. **TRD initial write.** `trd-author` writes the TRD as one of the very first steps, before the architect starts: the requirements not considered functional (the quality constraints and operational boundaries the technical architecture must support), many of them pre-written in arc42. The architect works from it, and the detailed design and the build read it.
2. **Establish.** `aws-solutions-architect` has single responsibility for the architecture the PRD needs: it designs it, reviews it and approves it, and nothing else reviews it. It always reads the PRD, reads and understands the existing architecture in arc42 and the matrix (both input and output, a starting point that may be incomplete or wrong, and normally empty for an Epic no earlier step has reached) and compares it to the PRD, writes its state file, designs and has approved what fills every gap, and updates the matrix with everything new or changed. It decides which agents the Epic needs, choosing them from the catalog of the `find-specialists` skill; no code chooses them. Inside its own session it starts the agents it chose for a question or a quick bounded task, `trd-author` for the TRD architecture update once the higher-level architecture is in arc42 (the technical or architecture decisions that impact the detailed design, which follows and reads the TRD) and for each later update in place, `architecture-maintainer` to write its decisions into the arc42 documents, each fact in its one home. It places each element in a stack after the detailed design has determined the resources and components; the `span` step names and creates each repository that placement needs. It records each as a child step of its own step and ends with its result, which answers every architecture and technical-requirement criterion of `skills/effective-architecture/review-criteria.json`, and with the Epic's review log (the `log-architecture-review` skill): for each AWS resource the design defines, the AWS tools, MCP servers, skills and specialists that reviewed it and the best practices and security best practices it follows; the Well-Architected review of the design; and every decision between two or more options with the options and the reason. Work it has an agent do outside its session it lists in its result's `requests`, each naming the agent and stating the request; the script starts each named agent with its request, by name, and then the architect's `Finish` with the answers. An agent left running when a session stops is launched by the script from its saved request.
3. **Check.** A script checks what code can check (the matrix file, the documents it indexes, an answer for every criterion, and the review log: a decision with no options or reason, an AWS resource with no review entry, a design with AWS resources and no Well-Architected review) and lists what is not approved for the Epic. A defect goes back to the architect, at most 3 times.
4. **Route.** Only when the architect lists a matter as unsettled, `architecture-team-lead` decides what each matter needs: nothing, one correction by the architect, an opinion from one specialist it chooses from the `find-specialists` catalog, a competing design, or a ruling by `architecture-decider`, the last resort. It adds those steps to the journal and the script runs them. Only two business requirements that no design can satisfy together, or a conflict with section 2, hold the Epic for the owner.
5. **Promote.** A script marks the approved content approved in the matrix, sets the approved documents to `effective`, files the review log in the vault and links it from the Epic's matrix entry, and commits and pushes them in the vault.

`built-version` records what a Story built, after the Story's deploy to AWS dev verifies and before its pull request. A `built-architecture-comparer` session compares the code on the Story branch with the approved architecture and design headings that describe the stacks and entries the Story's Tasks state (`atw-matrix built --story`, then `atw-matrix story-scope` for each stack); a Story whose Tasks state nothing is not compared, and writes each difference as an `in-review` view in `built/<element>/`, citing `file:line`. When a difference exists, the `architecture-maintainer` corrects the effective version from the built views, the `architecture-conformance-reviewer` checks the correction (at most 2 correction passes), `depscore.py arch-approve` sets the corrected files to `effective`, and `depscore.py arch-built-remove` deletes the built views the effective version now matches — a built view the maintainer reports matched and the reviewer confirms — and commits the removal. `depscore.py arch-snapshot` measures what each session wrote: the comparison writes only under `built/<element>/`, and every file the correction wrote is reviewed, reported or not. A Story with no difference writes nothing. `built-version` runs as the child steps of the Story's `deploy:built-version` journal step (snapshot, compare, then correct, review, approve and remove when a difference exists) and reports each one to the Story's step journal, so a restarted run begins at the first child step that is not done; a review with findings adds a correction and another review.

### From artifact to Beads issue

Each artifact in the PRD-to-Spec pipeline answers a different question and lands in Beads as a different issue type. A single PRD's requirement stays alive across the whole chain as one Epic; everything downstream links back to it.

| Artifact | Answers | Built from | Beads issue type | Notes |
| --- | --- | --- | --- | --- |
| PRD | What | Stakeholder request / intake brief | `epic` | One Epic tracks the requirement end to end. |
| TRD | How | The PRD and the approved architecture | *(no standing issue — incidental coordination only)* | Coordinates whichever specialists the architecture calls for (persistence, integration, security, and so on). Each piece of incidental specialist work is tracked as a **Whisp**, not its own Epic or Story — it exists to get the TRD written, not to persist past it. |
| Spec | Specifics | The TRD and the elements the matrix places in one repository — one TRD may produce several Specs, each scoped to a single repository | `story` | Granular functionality, data flow, and testing criteria, ready for decomposition. |
| Task | — | Decomposing a Spec's Story | `task` | Individually implementable, WSJF-scored; its build dependencies are `blocks` edges onto other Tasks, in its own Story or another. |

**A Bug is not in this table, and that is the point.** A bug is a **reporting
mechanism**, not an artifact in the chain and not a unit of work. It is never
worked directly: every bug is **TRIAGED** — a judgment call requiring reason and
common sense, made by a person — and becomes an Epic, a Task, or a closure as a
non-defect. Bugs never have parents. Both routers SKIP a bug and name triage, and
the driver dispatches none. A build that finds a defect fixes it in that run.
See [A Bug is never routed](workflows/ROUTING.md#a-bug-is-never-routed).

**Beads types.** `bd`'s installed type enum is `bug|feature|task|epic|chore|decision`; `story` and `whisp` are not native types; a project registers them as custom types (`types.custom` in `.beads/config.yaml`). The routers and `ROUTING.md` route `story`, and the Task steps of `prd-to-spec` write only type `task`.

### Spec to Deployment

`task-to-deploy` builds a Task on its Story's branch. A Story is scoped to one repository and has one worktree and one branch, cut from the repository's `main` by `workspace` when its first Task starts and reused by each later Task, which starts from the branch as the previous Task left it. `task-to-deploy` runs the steps the Task's step journal lists: it reads the journal once, begins at the first step that is not done, hands each step the artifacts earlier steps recorded, and reports each step started, done with its artifacts and the steps its result adds, or failed with its cause, on its log, where the driver applies it to the journal file. A restarted build therefore continues on the tree as the stopped run left it, at exactly the next step. The step kinds, what each records and reads, which steps a result adds and the steps planned up front are defined once, in the `pipeline-contracts` skill (`schemas/pipeline-steps.json`). A Task with an infrastructure type or label (the infrastructure vocabulary the `artifact-handoff` skill defines in `schemas/infra-vocabulary.schema.json`; the caller runs the skill's `scripts/infra_vocabulary.py` and passes its output as `infraVocabulary`) first runs `infra-intent`, which authors the provisioning intent; its `cdk synth` assertion criterion joins the acceptance criteria and `cdk-stack-author` is its Green implementer.

Green is measured, not reported. `suite-run` runs the one test command the repository declares — in its `AGENTS.md` or `CLAUDE.md`, or as the `test` task in its Taskfile — and returns the exit code and the failing tests. The command is followed by an echo of its exit status on a `SUITE-EXIT` line, and the exit code is read from that line in the verbatim output; a run whose output lacks it counts as no result. Each failure is reported as a test that failed or a test file that could not be loaded, with its file and test name, whatever the test runner. A repository that declares none stops the Task at `baseline` with a required human action. The command is resolved once, at the baseline run before any change, and every later run in the Task uses it. No phase's own report decides anything: `greenConfirmed`, `noRegressions`, `redConfirmed` and `testsGreen` are information only.

- **Red**: Test Design writes failing tests from the Task's acceptance criteria — unit tests with the AWS services mocked and, for a criterion about the CDK stacks, `cdk synth` assertion tests in the language of the repository's CDK app — one test agent after another, each its own step, then a check step runs the suite. Red holds when a test in a file Red wrote or edited fails, no test file stops loading that loaded at the baseline, and no test that passed at the baseline fails. A check where Red does not hold adds the test agents' steps and another check; the fourth such check stops the Task with `red-unsatisfied`, and a check where the suite fails exactly as at the check before stops it with `no-progress`.
- **Green**: each selected implementer writes code in its own step, then a check step runs the suite; a check that is not green adds the implementers' steps and another check, until the whole suite exits 0, including tests that were already failing at the baseline. The eighth check since the implementers were selected stops the Task with `green`. Implementation writes the minimum code and does not change tests: Red's test files are fingerprinted at each check, and a change to one stops the Task with `green-modified-tests`. A test it names in `testIssues` (obsolete under the contract, defective, or missing configuration the contract now requires) goes to `tdd-unit-test-generator` in update mode, which updates, deletes or keeps each one, citing the contract. Something outside the Task that does not exist yet, named in `upstreamMissing`, stops the Task with `blocked-upstream`. A round that changes no file and leaves the suite failing exactly as the round before stops it with `no-progress`.
- **Refactor** ends green: when the suite fails after the refactor, the tree is restored to the snapshot the refactor recorded and the suite runs again.

Documentation follows, the suite runs a final time, and `settle` with `commitOnly` commits the Task to the Story branch only when that run exits 0. A Task deploys nothing and opens no pull request: the run succeeds when the repository's whole suite passes and its work is committed.

When a Story's last Task is done, the Story deploys. First `deploy-mechanism` asks the `polyrepo-steward` what the Story's repository publishes and deploys: a package to CodeArtifact (with the publish command the repository declares), a CDK deployment, or both. A Taskfile is a convenience and does not decide this. A repository that does neither — the control repository and the documentation vault among them — stops with stage `no-deploy-mechanism`. The remaining steps are the host's scripts, not agents: they publish the package when the repository publishes one, then, when it deploys with CDK, synthesize the Story branch, check that every SSM parameter the templates read exists in AWS dev (a missing one holds only the deploy, and the Story stays in progress), `cdk deploy` the repository's stacks to AWS dev, and verify that the deploy exited 0 and every stack reports `CREATE_COMPLETE` or `UPDATE_COMPLETE`. On a publish, synth, deploy or verification failure `story-deploy-fix` runs as the child steps of the Story's `deploy:fix` journal step — a `deploy-failure-fixer` diagnoses the failure and fixes it on the Story branch, the files it changed are read from git and the repository's synth assertion tests are run, and the fix is committed — and the Story tries again. A fix that changes no file stops the deploy with stage `no-change`, and a failure after three fixes stops it. Every step of the deploy is a step of the Story's step journal (`schemas/pipeline-steps.json`, pipeline `deploy`), so a restarted deploy begins at the first step that is not done. It never goes back to Green. Once the deploy verifies, `built-version` records what the Story built in the architecture's `built/<element>/` and corrects the effective version from it (see *The architecture step*). Then the Story opens ONE pull request with the project PR command. When every check on the pull request's head commit passes, the Story's test has passed and a script sets what the Story built verified in the matrix (`atw-matrix verify --story <id>`), before and apart from the merge; then a script waits for GitHub to report it `MERGED`, and on the merge the Story is closed and its worktree removed.

```mermaid
graph LR
  WS[Workspace] --> RED[Red] --> GRN[Green] --> REF[Refactor] --> DOC[Documentation] --> COM[Commit to the Story branch]
  COM -. last Task of the Story .-> DEP[Story deploy to AWS dev]
  DEP -. a step fails, at most three fixes .-> FIX[story-deploy-fix]
  FIX -.-> DEP
  DEP --> BV[built-version] --> PR[Pull request] --> MRG[Merged; Story closed]
```

### Cross-cutting — Documentation

The Documentation team runs alongside implementation and deployment rather than as a phase. Code is not done until its documentation is current: `documentation-currency-auditor` names the stale documents and the writer of each kind, each writer updates its documents in the worktree, `documentation-accuracy-reviewer` checks them against the shipped code with one correction when it finds a problem, and the commit lands them with the code.

### How the pipeline is built — composites, minis, and gates

The doctrine is realized as `Workflow` scripts of two kinds. A **leaf mini** is one phase: it calls `agent()` or `parallel()` and returns an artifact. It does no nesting — a mini that calls `workflow()` throws. A **composite** stitches minis together with `workflow('name', args)`, owns the loop and escalate control flow, and runs Documentation as a parallel track. Nesting is one level deep on purpose: composites stay flat, and a full feature run sequences composites from outside (a router, `/loop`, or an on-demand call), never by nesting one composite inside another.

The build-and-deploy work is a **shared tail** of minis — `tdd-red`, `tdd-green`, `tdd-refactor`, `adversarial`, `deploy`. `task-to-deploy` runs `tdd-red`, `tdd-green` and `tdd-refactor`, judged by `suite-run`. It builds from the build contract on the Task, with `infra-intent` in front for an infrastructure Task.

**Deploying and landing are different things.** `deploy` puts one repository's code in the AWS dev environment (`smoke-test-author` writes the smoke suite, `dev-deployer` deploys and runs it); it opens no pull request and requires none, and succeeds when `deployedToDev` and `smokePassed` are both true. Landing is git: `settle`, one `worktree-lander` session, commits a worktree through its hooks and, unless `commitOnly`, pushes the branch and opens the pull request with the project PR command. `task-to-deploy` runs it with `commitOnly` to commit each Task to its Story branch; a Story's pull request opens only after its deploy verifies. A pull request is never evidence that anything was deployed.

The gate is itself a reusable mini. `gate-enforce` takes a phase artifact, a list of pass criteria, deterministic checks, and a set of escalate targets, and returns one of three verdicts:

- **pass** — every criterion holds. Non-blocking quality concerns ride along as flags, and so does every `competitive` criterion: it is recorded as a flag and never adjudicated. Deterministic checks are measured against the artifact first, and only `constitutive` criteria go to the `phase-gate-enforcer`; a gate with none passes on its checks with no agent session.
- **loop** — a criterion failed and the cause is inside this phase. The gate returns feedback specific enough to retry without interpretation; the composite re-runs the phase, up to `maxLoops`. With `mode: 'exhaustion'`, `gate-enforce` asks the `exhausted-gate-ruler` to rule a gate whose loops are spent: proceed, or one directed revision.
- **escalate** — the failure originates upstream (the phase got bad inputs). The gate names which upstream phase it goes back to.

The gate is never the agent that produced the artifact under review.

| Script | Kind | Purpose |
| --- | --- | --- |
| `gate-enforce` | gate | Deterministic checks first; constitutive criteria to an independent judge, competitive ones recorded as flags; pass / loop / escalate; `exhaustion` mode asks the `exhausted-gate-ruler` to rule a spent gate. |
| `workspace` | mini | Reuses the worktree registered for the bead or cuts one on a feature branch; refuses a default branch or detached HEAD. |
| `settle` | mini | One `worktree-lander` session commits the worktree through its hooks, pushes the branch and opens the pull request with the project PR command; with `commitOnly` it commits on the branch and stops. |
| `suite-run` | mini | One session runs the repository's declared test command once and returns `exitCode`, `failing`, `tail` and `summary`; with no command given it resolves the one the repository declares, or returns `resolveError`. |
| `tdd-red` | shared-tail mini | Test writers derived from the contract surfaces (unit always), one after another, write failing tests that encode the acceptance criteria and confirm they fail. In update mode `tdd-unit-test-generator` rules on each test the implementer named: update, delete or keep. |
| `tdd-green` | shared-tail mini | Writes the minimum production code to pass the failing tests without changing tests; names contradicting tests in `testIssues` and missing things outside the Task in `upstreamMissing`. |
| `tdd-refactor` | shared-tail mini | One `code-refactoring-specialist` session refactors the changed code without changing behavior, keeps the suite green, and reverts the tree when it cannot; with `restoreTo` one session restores the tree to a recorded snapshot. |
| `adversarial` | shared-tail mini | Attack lanes in test environments only; one adjudicator rules each confirmed finding, and the script returns the count of open constitutive findings as `constitutiveOpen`. |
| `deploy` | shared-tail mini | `smoke-test-author` writes a smoke suite (or the one passed in is reused), then one `dev-deployer` session deploys the one repository to AWS dev and runs the smoke tests against the deployed endpoints. Never deploys to qa or prod. |
| `documentation` | cross-cutting mini | `documentation-currency-auditor` names the stale documents and assigns each to the writer of its kind (changelog, README, API reference, user guide, otherwise `developer-documentation-writer`; a specification file to none); the writers update them in the worktree, each followed by a `documentation-accuracy-reviewer` review with one correction on findings. |
| `task-to-deploy` | composite | Runs the steps of the Task's step journal (`schemas/pipeline-steps.json`, pipeline `build`), from the first that is not done: Workspace (the Story's branch), Infra Intent (an infrastructure Task), Regression Scope, Baseline, the test agents and a Red check that adds another round when Red does not hold, the implementers and a Green check that adds a test ruling or another round when the suite is not green (each implementer's brief opens with the shared capabilities the Task must use, read with `atw-matrix uses --ids` for the matrix ids the Task states), Reuse Audit (`atw-matrix check-reuse` over the changed files, with `shared-capability-reviewer` ruling each definition the command cannot rule on, a duplicate being a violation; violations sent back to the implementers once, and a violation that remains stops the Task with stage `reuse-violation`), Refactor, CDS Audit (a `web-ui` Task, by the design source selected before the build from the bundles supplied then; the design-source values are `bead_metadata.CDS_DESIGN_SOURCE_BUNDLE`, `CDS_DESIGN_SOURCE_CDS` and `CDS_DESIGN_SOURCE_NONE` from `skills/beads-contract/schemas/bead-metadata.schema.json` — a design-system Task whose artifact now has a bundle builds from it, a bundle Task builds from the newest bundle of its artifact and stops blocked-upstream when none remains: a bundle Task runs the cds plugin's `tools/audit-app.py` over the Task's changes against the supplied bundle, its report verified against the digest the script prints, with `cds:audit-against-system` on what the script cannot rule on; a design-system Task runs `cds:audit-against-system` against the live design system; a Task with no design change runs no audit; violations sent back to the implementers once, the verdict returned as `cdsAudit`), Documentation, then a final green `suite-run`, the regression mapping and its verification, and the commit to the Story branch. No deploy, no pull request. |
| `deploy-mechanism` | mini | The first agent step of a Story's deploy: one `polyrepo-steward` rules what the Story's repository publishes (a CodeArtifact package and its publish command) and deploys (CDK). Read-only. |
| `story-deploy-fix` | mini | The fix step of a Story's deploy, run as the child steps of the Story's `deploy:fix` journal step: one `deploy-failure-fixer` fixes a failed publish, synth, deploy or verification on the Story branch; the changed files are read from git and the synth assertion tests run; the fix is committed. A fix that changes no file returns `no-change`. Never deploys and never re-enters Green. |
### Run modes

A composite runs two ways. **On-demand**, a single call drives one unit of work: `/agent-teams-workforce:work-bead <bead id>` routes one bead to the composite that owns it and dispatches it. **Unattended**, a self-paced `/loop` runs until `bd ready` is empty — each tick claims the next ready bead, routes it to the composite that matches its type, and reports. A bead with no matching composite is skipped and reported, never force-fit into the wrong pipeline.

### Safety

`deploy` stops at dev. It authors smoke tests, deploys to the AWS dev environment and smoke-tests the deployed endpoints; deploying to dev is not human-gated. The pipeline does not run `cdk deploy` to qa or production. Outward-facing rollout is a separate, human-gated action triggered by a person, not by a composite. Adversarial agents operate in designated test environments only; the attack lanes are instructed never to touch production, and the composite ends with `deployedToProd: false`.

### Project configuration

The plugin knows nothing about the project it is installed in. Everything project-specific reaches it through these environment variables, which the project exports (in its shell profile, or in the environment of whatever launches its sessions). A workflow script has no process access, so the commands and skills that dispatch a workflow read these variables and pass their values as the named arguments; hooks and skill scripts read them directly. A required variable that is unset stops the step that needs it, by name.

The names of the `ATW_*` variables below that the plugin's code reads are defined in one place, the `pipeline-contracts` skill's `schemas/driver-surface.schema.json` (`$defs.DriverEnvironment`, one `x-constant` per variable, exported by the generated `scripts/driver_surface_types.py`, for example `ARCH_PATH_ENV`), and every command, skill and script reads the name through that constant. That schema defines names only: which variables a project must set, and what reads each, are this table's. A project's pipeline driver sets these variables for its child sessions from the same schema; there its `required` list describes the driver's child environment, not the project configuration below.

| Variable | Meaning | Required | Reaches |
|---|---|---|---|
| `ATW_PR_COMMAND` | Absolute path of an executable that, run inside a worktree as `<cmd> --title T --body B`, pushes the current branch and opens its pull request (a PR that already exists for the branch is success). Exit 0: PR open (URL on stdout); any other exit status: no PR | Yes, for any composite that lands work | the host opens a Story's pull request with it |
| `ATW_NAMING_COMMAND` | The command (an executable on `PATH`, or its absolute path) that implements the project's `resource-naming` command line: `<cmd> name build\|check\|convert\|swap\|identify\|check-repository\|repository-names ...` and `<cmd> token build\|check\|convert ...`, where `--json` prints one JSON document on stdout. Exit 0: the value was produced or the name is valid; 1: refused or invalid (the document lists the violations); 2: usage error; 70: internal error. The plugin holds no naming rule of its own: every name it builds, converts or checks comes from this command | Yes, for any step that names or checks a name; when the process environment lacks it, `naming_command.py` reads it from the user's login shell (`$SHELL -l`), which loads the profile the project exports it from; set in neither, the step reports that no naming command is configured and makes no name, and elaboration's `span` step stops on it before any other work | agents run it through the `resource-naming` skill (`printenv ATW_NAMING_COMMAND`); read by `skills/resource-naming/scripts/naming_command.py`, which `skills/polyrepo-repo/scripts/polyrepo.py`, `scripts/portfolio/matrixseed.py` and `orchestrator/flows/repo_scoping.py` use |
| `ATW_ARCH_PATH` (`ARCH_PATH_ENV`) | The architecture directory: the folder holding `reference/` (the architecture documentation model), the effective version in `arc42/` (one folder per section) and `detailed/`, and the `built/` version | Yes, for elaboration, dependency assessment and scoring | the dispatch argument `archPath` of `prd-to-spec`; `archPath` on `dependency-assessment` and `wsjf-scoring`, which `/dependency-assessment` and `/wsjf-scoring` refuse to dispatch without |
| `ATW_PRD_DIR` (`PRD_DIR_ENV`) | The directory PRDs live under | Yes, for elaborating an Epic and for the matrix's PRD rows | read by `orchestrator/flows/prd_to_spec.py`, `scripts/portfolio/matrix.py`, `scripts/portfolio/matrixcli.py` |
| `ATW_CONTROL_REPO` (`CONTROL_REPO_ENV`) | The root repository that holds the tracker — the central beads database every pipeline bead is read and written in; its beads `issue_prefix` is the project's issue prefix | Yes: `atw-bd` and `beads-contract.py` run `bd` against it from any repository or worktree (unset, they fall back to the working directory and warn) | read by `bin/atw-bd`, `skills/beads-contract/scripts/beads_contract.py`, `scripts/portfolio/beadgraph.py`, `skills/polyrepo-beads/scripts/*.sh`, `skills/polyrepo-repo/scripts/polyrepo.py` |
| `ATW_REPOS_ROOT` | The directory the project's repositories are cloned under; every git repository below it except `ATW_CONTROL_REPO` is a product repository | No — without it (or without `ATW_CONTROL_REPO`), the main-worktree guard allows the write and prints one warning line | read by `hooks/pre-tool-protect-main-worktree.cjs` |
| `ATW_PROJECT_ROOT` (`PROJECT_ROOT_ENV`) | The directory recorded artifact and spec paths are relative to | No — without it, no root-relative path is recorded on a bead | `projectRoot` on `prd-to-spec`, `dependency-assessment` and `wsjf-scoring` |
| `ATW_PRD_EPIC_SYNC` (`PRD_EPIC_SYNC_ENV`) | Command that brings a PRD's Epic into line with the document: `<cmd> --only <slug> --apply` | No — without it, the slug needing sync is reported | run, as the `prd-writer` skill directs, by the session that writes a PRD's vault file |
| `ATW_PRD_EPIC_VERIFY` (`PRD_EPIC_VERIFY_ENV`) | Command that checks one PRD against its Epic: `<cmd> <slug> [--apply]` | No | read by the `prd-writer` skill |
| `designSystem.packagesDir` | The folder of mockups the owner supplied: zero or more single-artifact cds bundles, each `<change-slug>-<timestamp>/` with its own `styles/`, `spec/build-spec.md`, `design/<kind>.html` and `bundle.json`; the newest `created_at` of a kind and slug is the supplied one | No; absent or empty supplies no bundle | the spec steps of `prd-to-spec` list the bundles (script step `cdsbundles.list_bundles`) and give each `ui` item its design source, one of `$defs.DesignSource` in the `artifact-handoff` skill's `schemas/recon.schema.json` (`bundle`, a supplied bundle; `cds`, the CDS design system; `none`, no design change); the Task steps hand the packages directory to the Task plan, so every bundle a Task cites sits in it; `task-to-deploy` reads it again before each build, so a mockup can arrive any time before its Task is built |
| `CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`, `CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` | Composed page mocks and Shells | No | `designSystem.mocksDir` and `designSystem.shellsDir`; intent references, not substitutes for an unresolved UI package |
| `ATW_BEADS_PORT` | The shared Dolt server port | No — `3308` | read by `skills/polyrepo-beads/scripts/*.sh` |

### Status

The shared tail, the `documentation` track, the `gate-enforce` gate, `workspace` and `settle` exist as scripts. Elaboration, `prd-to-spec`, runs in the Python orchestrator (`orchestrator/run.py`, with its steps in `orchestrator/flows/`) as a loop over the Epic's step journal, and is not a workflow script. `prd-validation`, `built-version`, and the build composite `task-to-deploy` (with `suite-run`, and `infra-intent` for an infrastructure Task) exist as workflow scripts. `prd-to-spec` does not dispatch `prd-validation`: validation runs on its own.

## The doctrine, principles, and rules

The narrative above describes the workforce as it is built. This section is the doctrine it implements and the rules every agent obeys. These rules bind every agent in the workforce; they supplement the workflow designs, and **where an agent definition and these rules conflict, these rules win.**

### Why the workforce is built this way

The goal is not to maximize individual agent autonomy. The goal is to maximize system-level delivery reliability. A large, broadly scoped agent introduces avoidable risk: it can silently blend requirement analysis, architecture, implementation, review, and approval into one coherent-looking response. Such an agent may:

- resolve ambiguity without surfacing it
- optimize for a local concern instead of the larger system
- choose familiar tools over appropriate patterns
- hallucinate missing facts
- drift from the original intent
- collapse trade-offs into unsupported conclusions
- review its own reasoning with the same flawed assumptions
- exceed its authority without making that visible

Specialized agents reduce these risks by limiting the scope of reasoning, context, tool access, and decision authority. A narrowly defined agent can still be wrong, but its failure is easier to detect, isolate, and correct. Agents are not trusted because they are broadly capable; they are useful because they are constrained.

### What every agent has

A project delivery agentic workforce is designed around bounded specialist agents, explicit handoff contracts, independent review, and read-only coordination. Each agent has:

- a narrow purpose
- a defined scope
- explicit responsibilities
- limited authority
- role-specific context
- role-specific skills
- least-privilege tool access
- required inputs
- required outputs
- defined review paths
- clear escalation triggers

### Design philosophy

The workforce is designed using the same principles that guide durable software architecture: separation of concerns, least privilege, bounded context, explicit interfaces, single responsibility, independent review, dependency control, artifact-driven collaboration, testability, auditability, and escalation over silent assumption. The system prefers explicit coordination over broad autonomy. The design makes it difficult for any single agent to silently become planner, implementer, reviewer, approver, and historian for the same work.

### Foundational principles

**Specialization by responsibility.** Agents are defined by responsibility, not by broad professional title. Broad titles such as *Architect*, *Engineer*, *Developer*, *Reviewer*, or *Analyst* are too vague unless further scoped. Preferred agent names describe the specific work performed:

| Broad role | Better specialized roles |
| --- | --- |
| Architect | Integration Pattern Architect |
| Architect | Domain Boundary Architect |
| Architect | Persistence Architecture Specialist |
| Developer | Lambda Implementation Specialist |
| Developer | CDK Construct Implementer |
| Reviewer | Security Controls Reviewer |
| Reviewer | Operational Readiness Reviewer |
| Writer | API Documentation Writer |

**Bounded authority.** Every agent has explicit decision boundaries. Each definition states what the agent may decide, may recommend, may create, may modify, may review, may *not* decide, and when it must escalate. Capability does not imply authority — an agent may be capable of a task and still be forbidden from doing it.

**Least context.** Agents receive only the context required for their role, distributed through role-specific context packets rather than a universal project dump. This reduces irrelevant anchoring, stale assumptions, conflicting instructions, scope creep, context-window pollution, and accidental authority expansion.

**Least tool access.** Agents have access only to the tools and MCP servers their purpose requires. Read-only is the default; write access is granted only when mutation is part of the agent's charter. Tool access is a form of authority: an agent with broad access can affect the delivery system even if its written role appears narrow.

**No self-approval.** No agent may approve its own work, and no agent may independently plan, execute, review, and approve the same deliverable — across architecture, code, infrastructure, documentation, tests, schemas, runbooks, deployment plans, and release decisions. Every agent must review its own work for correctness, completeness, and risk, but it may not approve it. Where an independent reviewer's verdict can change what gets built, that review is mandatory (Rule 4); where it cannot, the output is judged by the phase that consumes it, never approved by the agent that made it.

**Separation of intent, design, implementation, and review.** The workforce separates these concerns; no single agent owns the full chain:

| Concern | Responsibility |
| --- | --- |
| Intent | Understand what is being requested |
| Requirements | Define required outcomes and constraints |
| Domain framing | Establish business meaning and boundaries |
| Architecture | Select structural patterns |
| Platform mapping | Translate architecture into platform-specific implementation |
| Implementation | Produce concrete deliverables |
| Review | Challenge correctness, risk, and completeness |
| Decision recording | Capture rationale and trade-offs |
| Delivery readiness | Confirm release and operational fitness |

**Architecture before platform preference.** Platform implementation agents must respect upstream architectural decisions. An AWS Serverless Specialist may recommend the best AWS implementation for an approved architecture, but may not independently replace the approved pattern because another service appears cheaper, easier, or more familiar. If a platform agent believes an upstream decision is flawed, it must raise a formal exception — it may not silently override the architecture.

**Read-only coordination.** Team leaders coordinate work; they do not perform it. A team leader may route tasks, enforce workflow rules, verify required inputs, assign agents, track open questions, require reviews, detect missing artifacts, escalate unresolved conflicts, and assemble approved outputs. A team leader may not create architecture, write implementation code, modify deliverables, approve its own team's work, override specialist disagreement, or silently resolve trade-offs. Team leaders own process integrity, not subject-matter authority.

**Artifact-first collaboration.** Agents collaborate through explicit artifacts — intake brief, requirements brief, domain model, context map, architecture option analysis, architecture decision record, API contract, data schema, threat model, implementation plan, test plan, review report, release readiness checklist, handoff packet. Informal agent conversation is not enough; the durable record is the artifact.

**Explicit conflict handling.** Agent disagreement is expected and useful, and must be surfaced as a structured conflict rather than hidden inside compromise language:

| Conflict type | Example |
| --- | --- |
| Architecture conflict | Event-driven architecture vs workflow orchestration |
| Platform conflict | DynamoDB vs Aurora |
| Cost conflict | Lower cost vs greater operability |
| Security conflict | Developer convenience vs least privilege |
| Delivery conflict | Faster implementation vs long-term maintainability |
| Domain conflict | Technical model does not match business model |

When conflict exceeds predefined rules, it must be escalated.

### The five task categories

Every unit of work belongs to exactly one of five categories:

| Category | Meaning |
| --- | --- |
| plan | Produce analysis, options, designs, estimates, or recommendations |
| orchestrate | Delegate, route, sequence, and track work performed by other agents |
| execute | Build, write, or modify a project artifact (code, spec, doc, infra) |
| approve | Decide from collected evidence, adjudicate findings, or pass/fail a gate |
| test | Challenge, verify, validate, or attack another agent's output |

**For any single task, an agent may perform work in no more than ONE of these categories.** Supporting constraints:

- Every agent definition declares exactly one task category in its charter; the other four are forbidden to that agent.
- If completing a task would require work in a second category, the agent stops and reports the remaining work to its manager. It never performs or assigns that work itself.
- An orchestrating agent never produces, evaluates, or approves the artifacts it routes — it owns process integrity only.
- A planning agent never decides among the options it produced; deciding is approve-category work performed by a different agent.
- An executing agent never approves its own output and never writes the tests that gate its own output.
- A testing agent reports findings; it never fixes what it finds.
- An approving agent never generates the evidence it decides from.

**No self-tasking.** If an agent determines that work needs to be done, it reports that finding to its manager, who routes the work to an appropriate agent. The originating agent never performs or assigns the work it identified.

**Task atomicity is scoped.** A task is atomic for the receiving agent. A manager's atomic task may be "coordinate architecture analysis," which it decomposes by routing to workers; a worker's atomic task may be "analyze DynamoDB access patterns." The hierarchy handles decomposition.

**Separation of analysis and decision.** Providing analysis is one task; making a decision from that analysis is a separate task; the two are performed by different agents. No agent both analyzes options and decides among them. In the PRD-to-Spec pipeline the architecture step keeps it this way: the design specialists analyze and answer the questions `aws-solutions-architect` asks them, the architect decides and records each choice between options with its reason in the review log, and `architecture-decider` rules only on what the team could not settle. The effective architecture is a current-state description kept by an execute-category agent (`architecture-maintainer`), never a decision artifact; the `architecture-conformance-reviewer` checks each correction from built the `architecture-maintainer` makes.

**Iteration limits.** A step whose result calls for a correction adds the steps that make and confirm it, and declines to add another when its limit is reached, failing with the cause instead; the limits are stated per step kind in `schemas/pipeline-steps.json`. `task-to-deploy`: a Red check fails with `red-unsatisfied` at the fourth check that does not show Red, and a Green check with `green` at the eighth check since the implementers were selected or an audit sent violations back; either fails with `no-progress` when nothing changed and the suite fails exactly as at the check before. A Story's deploy: a failure after three fixes stops it. The architecture step: at most 3 corrections of mechanical defects before review; what a review's finding needs is the lead's routing. A spec document gets one correction for the review's findings and one revision after a ruling, and a Task plan with a gap gets one correction. `built-version`: a review fails the step when the correction does not conform after 2 corrections that answered findings. (The three gate outcomes — pass, loop, escalate — and the constitutive-versus-competitive distinction are described under *How the pipeline is built* above.)

### Workforce creation rules

**Rule 1 — every agent must have a charter.** An agent is defined by its front-matter fields (`name`, `description`, `tools`/`disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `color`, `initialPrompt`) and, in the body, at minimum: Team, Agent Type, Purpose, Primary Responsibility, Scope, Out of Scope, Allowed Decisions, Forbidden Decisions, Inputs Required, Outputs Produced, Escalation Triggers, Acceptance Criteria, Anti-Goals. If these cannot be completed clearly, the agent is not yet well-defined.

**Named dispatch and delivered contracts.** Every workflow agent call resolves through a registry generated from this plugin's agent definitions. Missing, generic and foreign identities fail before dispatch; MCP-enabled definitions use the plugin-owned user-level mirror described below. Each dispatch receives the canonical subagent and artifact-handoff contracts directly. Applicable domain skills must be explicitly loaded with Skill; a frontmatter name is not proof of delivery. Shared source documents remain authoritative at their file or vault references. Makers write only assigned artifacts, reviewers use the same completion criteria, and durable checkpoints preserve completed work without counting as accepted results. JSON artifact publication and acceptance use the deterministic handoff scripts; agents return references rather than duplicate the document payload.

**AWS architecture evidence.** For AWS choices, consult AWS MCP documentation and associated skills as the leading technical guidance, applying relevant Well-Architected principles to actual requirements and deployment constraints. Existing generated drafts are not owner approval. Cite the guidance and tradeoffs, surface conflicts, and report unavailable guidance explicitly. `aws-solutions-architect` decides from that evidence and asks a specialist when a gap needs one.

**MCP agents run from the user-level agents directory.** Claude Code ignores `mcpServers` on an agent defined in a plugin. Every agent whose frontmatter has an `mcpServers:` entry therefore runs from its copy in `~/.claude/agents/` (`$CLAUDE_CONFIG_DIR/agents`), which every session that loads user settings registers by its plain name, whatever repository it runs in. Claude Code registers a plugin agent only under the `agent-teams-workforce:` prefix. An agent is recorded by its plain front-matter name (`cdk-stack-author`) and started by the name the session registers: a workflow script names it plainly and its fable shared block dispatches an agent with no user-level copy as `agent-teams-workforce:<name>`; the orchestrator, whose sessions load only project settings, launches every agent as `agent-teams-workforce:<name>`; an agent starts another with the Agent tool as the `subagent-contract` skill says. Claude Code loads the definition and preloads the skills its front matter lists, and no code reads an agent's or a skill's text to start or configure it. The `hooks/sync-user-agents.cjs` hook copies those agents from the newest install of the plugin that `plugins/installed_plugins.json` records when a copy is missing or differs, removes a copy whose agent no longer declares `mcpServers`, and writes only the files named in `~/.claude/agents/.agent-teams-workforce-owned.json`. Claude Code has no hook event for a plugin install, update or reload, so the hook runs at SessionStart, which also has Claude Code watch `installed_plugins.json`, and again on FileChanged when an install or update rewrites that file. A copy it writes takes effect in the next session. `scripts/check-agent-types.mjs` fails a workflow agentType literal under the plugin prefix.

**Rule 2 — one primary responsibility.** Each agent has one primary responsibility; related responsibilities may exist only if they support it. An API documentation writer should not also redesign the API, approve the contract, define authentication, and generate SDKs.

**Rule 3 — a defined output.** Every worker agent produces a defined output (recommendation memo, architecture option analysis, OpenAPI fragment, documentation draft, schema proposal, implementation patch, review findings, test plan, risk register entry, handoff packet). If an agent produces no defined output, its role should be questioned.

**Rule 4 — independent review only where its verdict can change what gets built.** An output gets an independent reviewer when that reviewer's verdict can change what gets built — send the artifact back, stop the run, or change what the next phase receives. It never gets a second review of a question already decided: a property a deterministic check measures is decided by the check, and no agent re-judges it; a question an earlier reviewer ruled on is not reviewed again downstream. An output no verdict could change has no reviewer, and is still not approved by its author — it is judged where it is used. So the `trd-author` writes the TRD with no checker of its own, since the solutions architect reviews it with the architecture; `spec-reviewer` reviews each repository's spec documents once, because its findings go back to their authors; `documentation-accuracy-reviewer` reviews each writer's documents, because its findings send them back for one correction; `task-to-deploy` decides each phase from the exit code `suite-run` returns, with no gate agent; and `adversarial` counts the adjudicator's open constitutive findings rather than judging them again. The `architecture-conformance-reviewer` does review each integration of the architecture, because its findings send the integration back to the `architecture-maintainer` for correction. A review whose verdict nothing reads, or that repeats a decided question, does not exist (Rule 12).

**Rule 5 — agents must state assumptions.** Every substantive output includes Assumptions, Open Questions, Constraints Followed, Constraints at Risk, and Scope Exceptions. This protects against silent ambiguity resolution.

**Rule 6 — separate facts, assumptions, recommendations, and decisions.** Outputs distinguish provided facts, inferred facts, assumptions, recommendations, decisions, and unresolved questions, so recommendations are not mistaken for approved decisions.

**Rule 7 — escalate scope violations.** If a task requires authority outside the agent's charter, the agent stops and raises a scope exception rather than acting.

**Rule 8 — competitive review for high-risk judgment.** Competitive or adversarial agents are used when the task involves architectural trade-offs, security-sensitive design, persistence strategy, cost/performance decisions, data modeling, migration planning, release readiness, ambiguous requirements, or irreversible implementation choices. Competition is not used by default for routine mechanical work.

**Rule 9 — model diversity is targeted.** Different LLM models are used when independent failure modes matter — adversarial review, architecture validation, security review, ambiguous requirement analysis, final synthesis, unsupported-claim detection — not merely to make a workflow appear more sophisticated.

**Rule 10 — consolidation requires justification.** First-pass design favors granular specialization. Agents may be consolidated later only with clear benefit and without removing a required control boundary. Valid reasons: agents always require the same context; always produce the same artifact; review separation adds no value; handoff overhead exceeds risk reduction; skills and MCP access are effectively identical; responsibilities cannot realistically be separated. Invalid reasons: the names sound similar; a human would normally do both; the model is capable of both; the spreadsheet feels too large; the workflow diagram looks too busy.

**Rule 11 — consolidation must preserve control boundaries.** Agents must not be consolidated if doing so removes an independent review Rule 4 requires, separation of concerns, conflict visibility, authority boundaries, least-privilege tool access, or meaningful escalation points. It may be reasonable to consolidate API Documentation Writer and API Example Generator; it is not reasonable to consolidate API Contract Designer and API Contract Reviewer.

**Rule 12 — contracts are consumer-defined.** A consumer declares the schema it needs; a producer produces to that schema. A producer never invents a requirement and never decides unilaterally what must be produced. Every required field, section, or artifact must therefore **name the consumer that reads it**, in the form `Consumed by: <workflow/agent/script> — <what it does with it>`. If nothing downstream consumes it, **the requirement does not exist** — it is deleted, not softened to optional or advisory. Advisory ceremony still costs the reader's attention and still shows up as a finding, so demoting an unread requirement does not retire it. The same test governs gate criteria: a criterion asserts a property, and something downstream must depend on that property holding. A criterion no step reads, checks, or branches on is ceremony, not rigor.

### Team and specialist charters

**Agent team model.** Agents are organized into teams by delivery function. Each team has a read-only team leader and orchestrator, and may contain sub-orchestrators or sub-leaders depending on scope. The team leader coordinates the work but does not perform subject-matter production.

**Team leader charter.** Beyond what every agent requires, a team leader: delegates 100% of work to the team; is responsible for the quality and completion of all work the team produces; may not blame any team member for low quality, incompetence, or incomplete work; owns communication to, between, and from team members; ensures all rules, guidelines, and best practices are followed; and is honest and transparent above all else. A team leader is never allowed to perform work itself (including work that does not touch project artifacts) on behalf of the team, or to compensate for the team's inadequacies by doing their work or covering up their problems.

**Specialist agent charter.** Beyond what every agent requires, a specialist: always uses the skills and MCP servers provided over its own internal training; always provides an audit trail of decisions, including confidence level, reasoning, alternatives considered and dismissed, questions whose answers might have changed the outcome, and pros/cons and risks; and is honest and transparent above all else.

### Illustrative flows

**A potential architectural decision workflow.**

```text
1. Request Intake Analyst creates the intake brief.
2. Requirements Clarifier identifies required outcomes, constraints, ambiguities, and acceptance criteria.
3. Domain Boundary Architect defines domain ownership, business concepts, and bounded contexts.
4. Integration Pattern Architect recommends the appropriate integration pattern.
5. Competing Pattern Reviewer challenges the recommended pattern and identifies viable alternatives.
6. Architecture Trade-off Reviewer compares the recommendation against rejected alternatives.
7. Platform Implementation Specialist maps the approved architecture to platform-specific services.
8. Cost Reviewer challenges cost assumptions and scaling risks.
9. Security Reviewer challenges trust boundaries, permissions, and abuse cases.
10. Operational Readiness Reviewer challenges observability, failure handling, supportability, and recovery.
12. Architecture Team Leader verifies that all required workflow steps occurred and prepares the decision packet.
```

**An example handoff contract.** Every handoff has a contract (in practice, strict JSON to prevent ambiguity):

```text
Handoff: Integration Pattern Architect → AWS Serverless Implementation Specialist
Request: Map the approved event-driven architecture to AWS serverless services.
Upstream Decision: The solution must use event-driven decoupling between producer and consumer domains.
Constraints:
- Preserve producer/consumer decoupling.
- Preserve domain ownership boundaries.
- Do not replace the event-driven architecture with centralized workflow orchestration unless raising a formal architecture exception.
Allowed Decisions:
- Select AWS-native event routing services.
- Recommend retry and dead-letter handling.
- Recommend observability hooks.
- Recommend deployment considerations.
- Identify AWS-specific risks and trade-offs.
Forbidden Decisions:
- Change the approved integration pattern.
- Collapse producer and consumer boundaries.
- Redefine domain ownership.
- Select a non-event-driven architecture without escalation.
Required Output: AWS implementation recommendation with service choices, trade-offs, risks, assumptions, and operational considerations.
```

### Minimal guidance for creating an agent

Collecting these values gives enough structure to define both the agent and the governance model around it:

| Column | Purpose |
| --- | --- |
| Agent ID | Stable unique identifier |
| Agent Name | Human-readable role name |
| Team | Functional team assignment |
| Agent Type | Worker, reviewer, coordinator, decision-support, recorder |
| Purpose | Why the agent exists |
| Primary Responsibility | The agent's main responsibility |
| Scope | What the agent covers |
| Out of Scope | What the agent must not cover |
| Allowed Decisions | Decisions the agent may make |
| Forbidden Decisions | Decisions the agent may not make |
| Authority Level | Recommend, create, modify, review, approve, route |
| Mutation Rights | None, draft-only, patch, merge, deploy |
| Inputs Required | Required upstream artifacts |
| Outputs Produced | Required output artifacts |
| Required Skills | Attached Agent Skills |
| Required MCPs | Required tools or MCP servers |
| MCP Permissions | Read-only, comment-only, write, admin |
| Upstream Agents | Agents that feed this agent |
| Conflict Partners | Agents expected to challenge this agent |
| Escalation Triggers | Conditions requiring escalation |
| Acceptance Criteria | What good output means |
| Anti-Goals | Explicit behaviors to avoid |
| Consolidation Candidate | Yes, no, or later |
| Consolidation Rationale | Reason consolidation may be valid |
| Risk If Too Broad | Failure mode caused by excessive scope |
| Risk If Too Narrow | Failure mode caused by excessive fragmentation |
| Notes | Additional information |

### Final operating standard

The workforce is optimized for reliable project delivery, not individual agent autonomy. Agents are small by default. Authority is explicit. Context is limited. Tools are least-privilege. Review is independent. Coordination is read-only. Disagreement is surfaced. Decisions are recorded. Consolidation is earned. The system makes it difficult for any single agent to silently expand its role, collapse trade-offs, approve its own work, or substitute local optimization for project-level judgment.

## The taxonomy

Every agent is described by a role and one or more character types. Team membership is not stamped on the agent — a team is a composition its lead owns, and an agent may serve on more than one team.

### Roles

| Role | Authority |
| --- | --- |
| Manager | Has subordinates. Routes tasks to the right agent. Validates process outcomes (DoD met? redo?) |
| Worker | Performs a single atomic task. Returns result to Manager. |
| Specialist | No manager, no team. Performs assigned tasks on demand. |

### Character Types

An agent typically has multiple character types. These are behavioral constraints, not roles.

| Type | Behavior |
| --- | --- |
| Orchestrator | Manages agreement protocols, validates sub-task outputs. |
| Delegator | Cannot use execution tools. Emits task assignments only. |
| Executor | Receives delegated work, produces output. |
| Validator | Reviews, tests, asserts, evaluates another agent’s results. |
| Adversary | Validator with intentionally hostile intent — breaks, disproves, rejects, competes. |
| Advisor | Analyzes, optimizes, guides. Read-only — produces recommendations, not decisions. |
| Decider | Receives collected evidence from multiple agents. Produces a decision + rationale. Does not generate the evidence it decides from. |

### Team Types

| Concept | Definition |
| --- | --- |
| Execution Team | Contains Workers. The common case. |
| Supervisor Team | Contains only other Managers. Top-of-house coordination. |

Each delivery team below is an Execution Team: Workers, with a Manager lead where the team has one. No agent forms a Supervisor Team: the workflow scripts and the Python orchestrator sequence the phases, and none of them performs, evaluates or approves the work it routes. Governance agents, design specialists, architecture review specialists, workflow helpers and the polyrepo steward are Specialists: no manager, no team, invoked on demand.

## The teams — every agent, by team

### Governance — Standalone Specialists

Gate and conflict rulings, and context integrity. `gate-enforce` starts `phase-gate-enforcer` and, in its exhaustion mode, `exhausted-gate-ruler`; the others are available to a caller that chooses them. 5 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `phase-gate-enforcer` | Specialist | Validator, Decider (Referee) |
| `exhausted-gate-ruler` | Specialist | Decider |
| `advantage-evaluator` | Specialist | Validator, Decider |
| `constitutional-agent` | Specialist | Decider |
| `context-curator` | Specialist | Executor |

### PRD Creation — Execution Team

`prd-creation` starts each of these agents in turn and, when the writer and the verifier do not converge, `review-dispute-decider` (Spec Authoring). 5 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `stakeholder-request-intake-writer` | Worker | Executor |
| `feature-persona-writer` | Worker | Executor |
| `feature-objective-writer` | Worker | Executor |
| `prd-writer` | Worker | Executor |
| `prd-alignment-verifier` | Worker | Validator |

### PRD Validation — Execution Team

`prd-validation` starts one specialist per lens, and `brd-traceability-auditor` only when a BRD is named; it merges their results. `prd-to-spec` hands the PRD file to its agents as it stands and starts none of these. `nfr-analyst` and the lead are available to a caller that chooses them. 10 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `prd-validation-lead` | Manager | Delegator, Orchestrator |
| `requirement-classifier` | Worker | Validator |
| `ambiguity-detector` | Worker | Validator |
| `completeness-checker` | Worker | Validator |
| `requirements-conflict-detector` | Worker | Validator |
| `constraint-extractor` | Worker | Executor |
| `domain-boundary-validator` | Worker | Validator |
| `requirements-clarifier` | Worker | Advisor |
| `brd-traceability-auditor` | Worker | Validator |
| `nfr-analyst` | Worker | Advisor |

### Architecture — Execution Team

`aws-solutions-architect` has single responsibility for the architecture a PRD needs. It chooses the design specialists, review specialists and diagram authors a gap needs through the `find-specialists` catalog and asks each one question or one bounded task, starts `trd-author` for the TRD and `architecture-maintainer` to write its decisions into arc42, reviews and approves its own architecture and records the proof in the Epic's review log. `architecture-team-lead` routes what the architect could not settle, and `architecture-decider` rules on what the team could not settle. The remaining agents here are available to a caller that chooses them. 10 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `aws-solutions-architect` | Worker | Executor |
| `architecture-team-lead` | Worker | Orchestrator |
| `architecture-decider` | Worker | Decider |
| `architecture-maintainer` | Worker | Executor |
| `architecture-diagram-author` | Specialist | Executor |
| `c4-diagram-author` | Specialist | Executor |
| `uml-diagram-author` | Specialist | Executor |
| `architecture-impact-analyst` | Worker | Analyst |
| `architecture-fitness-function-author` | Worker | Executor |
| `ubiquitous-language-writer` | Worker | Executor |

### Design Specialists — Standalone Specialists

Each answers a question or does a bounded piece of design for the solutions architect in one domain, loads the `design-specialist-contract` skill and the skills of its domain, and is found by the architect through the `find-specialists` catalog. No workflow starts them by name; `infra-intent` also starts `cdk-infrastructure-designer` to turn a Task's recorded infrastructure into provisioning intent. `AGENT-ROSTER.md` groups them by domain and maps each to the AWS services it covers. 46 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `bounded-context-mapper` | Specialist | Advisor |
| `domain-event-modeler` | Specialist | Executor |
| `data-architect` | Specialist | Advisor |
| `persistence-architecture-specialist` | Specialist | Advisor |
| `integration-pattern-architect` | Specialist | Advisor |
| `security-architecture-designer` | Specialist | Advisor |
| `cdk-infrastructure-designer` | Specialist | Advisor |
| `lambda-function-designer` | Specialist | Advisor |
| `container-service-designer` | Specialist | Advisor |
| `kubernetes-cluster-designer` | Specialist | Advisor |
| `ec2-fleet-designer` | Specialist | Advisor |
| `batch-compute-designer` | Specialist | Advisor |
| `relational-database-designer` | Specialist | Advisor |
| `dynamodb-table-designer` | Specialist | Advisor |
| `cache-designer` | Specialist | Advisor |
| `graph-database-designer` | Specialist | Advisor |
| `document-database-designer` | Specialist | Advisor |
| `time-series-database-designer` | Specialist | Advisor |
| `object-storage-designer` | Specialist | Advisor |
| `block-and-file-storage-designer` | Specialist | Advisor |
| `vpc-network-designer` | Specialist | Advisor |
| `load-balancer-designer` | Specialist | Advisor |
| `dns-and-edge-designer` | Specialist | Advisor |
| `api-contract-designer` | Specialist | Executor |
| `graphql-api-designer` | Specialist | Executor |
| `event-routing-designer` | Specialist | Executor |
| `queue-and-topic-designer` | Specialist | Advisor |
| `workflow-orchestration-designer` | Specialist | Advisor |
| `stream-processing-designer` | Specialist | Advisor |
| `data-lake-designer` | Specialist | Advisor |
| `analytics-query-designer` | Specialist | Advisor |
| `data-warehouse-designer` | Specialist | Advisor |
| `iam-policy-designer` | Specialist | Advisor |
| `user-authentication-designer` | Specialist | Advisor |
| `encryption-and-secrets-designer` | Specialist | Advisor |
| `perimeter-protection-designer` | Specialist | Advisor |
| `foundation-model-designer` | Specialist | Advisor |
| `rag-architecture-designer` | Specialist | Advisor |
| `applied-ai-services-designer` | Specialist | Advisor |
| `ml-feature-pipeline-designer` | Specialist | Advisor |
| `ml-training-designer` | Specialist | Advisor |
| `ml-inference-designer` | Specialist | Advisor |
| `ai-agent-designer` | Specialist | Advisor |
| `generative-ai-pattern-designer` | Specialist | Advisor |
| `monitoring-and-tracing-designer` | Specialist | Advisor |
| `audit-and-compliance-designer` | Specialist | Advisor |

### Architecture Review Specialists — Standalone Specialists

Each reviews one aspect of an Epic's unapproved architecture and TRD when the solutions architect chooses it through the `find-specialists` catalog and asks it a review question. No workflow starts them. 7 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `architecture-boundary-guardian` | Specialist | Validator |
| `architecture-pattern-challenger` | Specialist | Adversary |
| `architecture-tradeoff-skeptic` | Specialist | Adversary |
| `failure-mode-analyst` | Specialist | Advisor |
| `operational-readiness-reviewer` | Specialist | Validator |
| `new-resource-cost-reviewer` | Specialist | Advisor |
| `changed-resource-cost-reviewer` | Specialist | Adversary |

### TRD — Execution Team

The solutions architect starts `trd-author`. The other two are available to a caller that chooses them. 3 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `trd-author` | Worker | Executor |
| `prd-trd-traceability-verifier` | Worker | Validator |
| `trd-decider` | Worker | Decider |

### Spec Authoring — Execution Team

Elaboration starts, per repository, `ui-design-source-selector` (frontend repositories), the two specification authors and `acceptance-criteria-writer`, `dynamodb-schema-access-pattern-reviewer` when a stack the Story builds in holds a DynamoDB store, `spec-reviewer`, and `review-dispute-decider` for each finding an author disputes. The other agents here are available to a caller that chooses them. 12 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `spec-authoring-lead` | Manager | Delegator, Orchestrator |
| `ui-design-source-selector` | Worker | Advisor |
| `api-specification-author` | Worker | Executor |
| `data-model-specification-author` | Worker | Executor |
| `acceptance-criteria-writer` | Worker | Executor |
| `definition-of-done-writer` | Worker | Executor |
| `dynamodb-schema-access-pattern-reviewer` | Worker | Validator |
| `spec-reviewer` | Worker | Validator |
| `acceptance-criteria-reviewer` | Worker | Validator |
| `event-schema-reviewer` | Worker | Validator |
| `graphql-schema-reviewer` | Worker | Validator |
| `review-dispute-decider` | Worker | Decider |

### Planning and Scoring — Execution Team

Elaboration starts `task-decomposer` and `task-dependency-mapper`; `task-dependency-assessment` also starts the mapper for a Task created outside elaboration, `dependency-assessment` starts `epic-dependency-assessor`, and `wsjf-scoring` starts `wsjf-scorer`. Elaboration writes Stories by script, so `story-bead-writer` serves a Story written outside it. The reviewers are available to a caller that chooses them. 8 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `task-decomposer` | Worker | Executor |
| `task-dependency-mapper` | Worker | Executor |
| `epic-dependency-assessor` | Worker | Advisor |
| `wsjf-scorer` | Worker | Executor |
| `wsjf-scoring-reviewer` | Worker | Validator |
| `story-bead-writer` | Worker | Executor |
| `user-story-reviewer` | Worker | Validator |
| `beads-format-validator` | Worker | Validator |

### Built Version — Execution Team

`built-version` starts the comparer and, when it records a difference, `architecture-maintainer` and the conformance reviewer, after a Story's deploy to AWS dev is verified. 2 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `built-architecture-comparer` | Worker | Validator |
| `architecture-conformance-reviewer` | Worker | Validator |

### Spec Freshness — Execution Team

No workflow starts these agents; they remain for a spec written well before its build. 3 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `spec-freshness-lead` | Manager | Delegator, Orchestrator |
| `spec-currency-validator` | Worker | Validator |
| `dependency-change-detector` | Worker | Validator |

### Test Design — Execution Team

`tdd-red` starts the writers its contract's surfaces call for (`tdd-unit-test-generator` always). The other agents here are available to a caller that chooses them. 16 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `test-design-lead` | Manager | Delegator, Orchestrator |
| `tdd-unit-test-generator` | Worker | Executor (test author) |
| `consumer-driven-contract-test-writer` | Worker | Executor (test author) |
| `security-test-case-designer` | Worker | Executor (test author) |
| `aws-integration-test-writer` | Worker | Executor (test author) |
| `playwright-e2e-web-test-writer` | Worker | Executor (test author) |
| `performance-benchmark-writer` | Worker | Executor (test author) |
| `xcuitest-writer` | Worker | Executor (test author) |
| `espresso-test-writer` | Worker | Executor (test author) |
| `mobile-e2e-test-writer` | Worker | Executor (test author) |
| `ml-evaluation-tester` | Worker | Executor (test author) |
| `data-pipeline-test-writer` | Worker | Executor (test author) |
| `acceptance-criteria-coverage-assessor` | Worker | Validator |
| `test-plan-strategy-reviewer` | Worker | Validator |
| `test-isolation-specialist` | Worker | Validator |
| `test-strategy-decider` | Worker | Decider |

### Implementation — Execution Team

`tdd-green` starts `implementation-lead` to select the implementers, then each selected implementer in turn. Every implementer loads the `implementer-contract` skill. `task-to-deploy` also starts `cdk-stack-author` for an infrastructure Task. 35 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `implementation-lead` | Manager | Delegator, Orchestrator |
| `chassis-extension-implementer` | Worker | Executor |
| `api-gateway-cdk-implementer` | Worker | Executor |
| `cdk-stack-author` | Worker | Executor |
| `event-api-client-implementer` | Worker | Executor |
| `event-driven-consumer-implementer` | Worker | Executor |
| `dynamodb-access-layer-implementer` | Worker | Executor |
| `postgresql-access-layer-implementer` | Worker | Executor |
| `power-tools-configuration-implementer` | Worker | Executor |
| `cognito-lambda-trigger-implementer` | Worker | Executor |
| `webauthn-implementer` | Worker | Executor |
| `cds-ui-implementer` | Worker | Executor |
| `nextjs-component-implementer` | Worker | Executor |
| `appsync-cdk-implementer` | Worker | Executor |
| `appsync-client-subscription-implementer` | Worker | Executor |
| `ios-swiftui-implementer` | Worker | Executor |
| `android-compose-implementer` | Worker | Executor |
| `react-native-implementer` | Worker | Executor |
| `bedrock-integration-implementer` | Worker | Executor |
| `llm-observability-implementer` | Worker | Executor |
| `sagemaker-implementer` | Worker | Executor |
| `applied-ai-services-implementer` | Worker | Executor |
| `agentcore-agent-implementer` | Worker | Executor |
| `vector-search-embeddings-implementer` | Worker | Executor |
| `matching-algorithm-implementer` | Worker | Executor |
| `recommendation-engine-implementer` | Worker | Executor |
| `behavioral-signals-implementer` | Worker | Executor |
| `mcp-server-implementer` | Worker | Executor |
| `glue-etl-implementer` | Worker | Executor |
| `kinesis-stream-implementer` | Worker | Executor |
| `dynamodb-streams-cdc-implementer` | Worker | Executor |
| `s3-data-lake-implementer` | Worker | Executor |
| `athena-redshift-analytics-implementer` | Worker | Executor |
| `payments-integration-implementer` | Worker | Executor |
| `email-notification-implementer` | Worker | Executor |

### Code Quality — Execution Team

`tdd-refactor` starts `code-refactoring-specialist`, which decides which refactorings the changed files need. The other agents here are available to a caller that chooses them. 9 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `code-quality-lead` | Manager | Delegator, Orchestrator |
| `complexity-analyzer` | Worker | Advisor |
| `code-refactoring-specialist` | Worker | Executor |
| `lint-finding-fixer` | Worker | Executor |
| `lambda-performance-optimizer` | Worker | Executor |
| `dynamodb-cost-optimizer` | Worker | Executor |
| `frontend-performance-optimizer` | Worker | Executor |
| `code-correctness-reviewer` | Worker | Validator |
| `accessibility-validator` | Worker | Validator |

### Integration Testing — Execution Team

No workflow starts these agents; each is available to a caller that chooses it. 9 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `integration-testing-lead` | Manager | Delegator, Orchestrator |
| `cross-repo-integration-test-coordinator` | Worker | Orchestrator |
| `test-environment-provisioner` | Worker | Executor |
| `aws-integration-test-runner` | Worker | Validator |
| `event-flow-tester` | Worker | Validator |
| `data-consistency-checker` | Worker | Validator |
| `cross-service-contract-tester` | Worker | Validator |
| `flaky-test-detector` | Worker | Validator |
| `root-cause-analyst` | Worker | Advisor |

### Adversarial Validation — Execution Team

`adversarial` starts the attackers its lanes call for against the designated test environment and test identities the caller names, then `adversarial-critique-adjudicator`. No build or deploy step runs it. 11 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `adversarial-review-loop-supervisor` | Manager | Delegator, Orchestrator |
| `injection-attack-tester` | Worker | Adversary |
| `auth-bypass-tester` | Worker | Adversary |
| `permission-escalation-tester` | Worker | Adversary |
| `race-condition-tester` | Worker | Adversary |
| `contract-violation-tester` | Worker | Adversary |
| `dependency-cve-auditor` | Worker | Validator |
| `dos-resilience-tester` | Worker | Adversary |
| `data-exposure-scanner` | Worker | Validator |
| `infrastructure-security-scanner` | Worker | Validator |
| `adversarial-critique-adjudicator` | Worker | Decider (Referee) |

### Deployment and Landing — Execution Team

The `deploy` workflow starts `smoke-test-author` and then `dev-deployer`. A Story's deploy pipeline publishes, synthesizes and deploys with no agent and, when one of those steps fails, runs `story-deploy-fix`, which starts `deploy-failure-fixer`. `settle` starts `worktree-lander`. Deploys go only to AWS dev; the other agents here are available to a caller that chooses them. 12 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `deployment-lead` | Manager | Delegator, Orchestrator |
| `smoke-test-author` | Worker | Executor (test author) |
| `dev-deployer` | Worker | Executor |
| `deploy-failure-fixer` | Worker | Executor |
| `worktree-lander` | Worker | Executor |
| `github-actions-pipeline-implementer` | Worker | Executor |
| `cdk-infrastructure-drift-detector` | Worker | Validator |
| `slo-error-budget-designer` | Worker | Advisor |
| `finops-analyst` | Worker | Advisor |
| `incident-response-runbook-designer` | Worker | Executor |
| `production-readiness-review-facilitator` | Worker | Orchestrator |
| `deployment-strategy-decider` | Worker | Decider |

### Documentation — Execution Team

`documentation` starts `documentation-currency-auditor`, then each writer it assigns stale documents to, each followed by `documentation-accuracy-reviewer`. `filing-clerk` files a fact in the documentation vault when a person or the steward asks. 9 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `documentation-lead` | Manager | Delegator, Orchestrator |
| `documentation-currency-auditor` | Worker | Validator |
| `api-documentation-writer` | Worker | Executor |
| `readme-writer` | Worker | Executor |
| `changelog-writer` | Worker | Executor |
| `user-guide-writer` | Worker | Executor |
| `developer-documentation-writer` | Worker | Executor |
| `documentation-accuracy-reviewer` | Worker | Validator |
| `filing-clerk` | Specialist | Executor |

### Cumulative Regression Assurance — Execution Team

`task-to-deploy` starts the assessor to write the regression scope and, after Green, the mapping of tests to requirements; the reviewer reviews each. 2 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `regression-impact-assessor` | Worker | Advisor |
| `regression-coverage-reviewer` | Worker | Validator |

### Workflow Helpers — Standalone Specialists

Sessions the named workflows start for one mechanical or judging step. 6 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `test-command-resolver` | Specialist | Advisor |
| `test-failure-parser` | Specialist | Executor |
| `cds-live-auditor` | Specialist | Validator |
| `cds-finding-reviewer` | Specialist | Validator |
| `shared-capability-reviewer` | Specialist | Validator |
| `workflow-command-runner` | Specialist | Executor |

### Standalone — Standalone Specialists

Reached through the `polyrepo-router` skill or the `/polyrepo-steward` command; `deploy-mechanism` also asks it what a repository publishes and deploys. 1 agent.

| Agent | Role | Character Types |
| --- | --- | --- |
| `polyrepo-steward` | Specialist | Executor |

## The full roster, in detail

Every agent, with the team it is rostered under, its role, character types, task category, responsibility, and the skills and tools it is granted (MCP tools are not listed).

| Agent | Team | Team Type | Role | Character Types | Category | Responsibility | Skills | Tools |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `phase-gate-enforcer` | Governance | Standalone Specialists | Specialist | Validator, Decider (Referee) | approve | Rules pass, loop or escalate on the constitutive criteria of one phase gate, from the criteria and the artifact the gate-enforce workflow quotes: loop when the cause of an unmet criterion is inside the phase, escalate when it is upstream, naming where it goes back to. Deterministic checks and competitive criteria are settled by the gate script and never reach it. | subagent-contract, validation-protocol | Read, Glob, Grep, Agent |
| `exhausted-gate-ruler` | Governance | Standalone Specialists | Specialist | Decider | approve | Rules how a run continues from a phase gate whose loops are spent: proceed, with the latest output standing and every unmet criterion carried on as a named residual with its mitigation, or one directed revision under a concrete, changed instruction. Started by the gate-enforce workflow in its exhaustion mode. | subagent-contract, validation-protocol | Read, Glob, Grep, Agent |
| `advantage-evaluator` | Governance | Standalone Specialists | Specialist | Validator, Decider | approve | Rules commit or revert on a competitive (non-constitutive) finding that work was allowed to proceed under: before the outcome exists it states the observation window and the evidence that will decide, then judges the observed outcome against it. Speculative execution with rollback, so a tradeable finding never halts a run. | subagent-contract, validation-protocol | Read, Glob, Grep, Write, Agent |
| `constitutional-agent` | Governance | Standalone Specialists | Specialist | Decider | approve | Rules on a conflict between two constitutive constraints that no gate can settle: establishes the constitutional layer the conflict falls under (the owner's section 2 constraints and settled decisions recorded in the matrix, the business outcomes of the PRD the work serves, and the review standard's acceptance basis), names which constraint prevails and under what conditions, and writes the ruling as a precedent record a later conflict can cite. | subagent-contract, validation-protocol, effective-architecture, matrix | Read, Glob, Grep, Write, Bash, Agent |
| `context-curator` | Governance | Standalone Specialists | Specialist | Executor | execute | Assembles a context index for one receiving agent and task: a file of pointers (paths, headings, matrix ids and atw-matrix commands) to exactly what the role needs, with every constitutive constraint that binds it carried by pointer to its one home, never copied or summarized, and keeps the constraint manifest those pointers come from current. | subagent-contract, validation-protocol, matrix | Read, Write, Edit, Glob, Grep, Agent |
| `stakeholder-request-intake-writer` | PRD Creation | Execution Team | Worker | Executor | execute | Turns one raw stakeholder request into the structured intake of a feature: the scope the request frames (what it asks for and what it leaves out), the problem, the audience, the desired outcome, the constraints it states and the open questions it leaves, WHAT the users need and never HOW to build it. | subagent-contract, validation-protocol, product-discovery | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `feature-persona-writer` | PRD Creation | Execution Team | Worker | Executor | execute | Writes the one target persona a feature serves, grounded in the audience, problem and outcome of the feature's intake: a proto-persona whose goals, frustrations and context are each stated, inferred or marked as an assumption, behavior over demographics. | subagent-contract, validation-protocol, persona-research | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `feature-objective-writer` | PRD Creation | Execution Team | Worker | Executor | execute | Writes the one objective a feature must move and the key results that prove it was met, grounded in the feature's intake: a qualitative, user-centered objective and measurable key results, each with its metric and target. | subagent-contract, validation-protocol, product-analytics | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `prd-writer` | PRD Creation | Execution Team | Worker | Executor | execute | Writes a template-conformant PRD, WHAT and never HOW, from a feature's intake, persona and objective, with acceptance criteria for its P0 requirements, and the one-paragraph scope of the Epic that pairs with it; on a revision, applies the alignment verdict on its previous draft. | subagent-contract, validation-protocol, prd-writer, matrix, acceptance-criteria | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `prd-alignment-verifier` | PRD Creation | Execution Team | Worker | Validator | test | Independently judges whether a draft PRD aligns with the intake brief, persona and objective it was written from, and is template-conformant and WHAT-not-HOW, on four dimensions (intake, persona, objective, template). | subagent-contract, validation-protocol, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `prd-validation-lead` | PRD Validation | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Manual-only coordinator for explicitly assigned PRD validation work. Selects bounded analysts and routes their findings without making solution or approval decisions. The active prd-validation mini dispatches its lens specialists itself and does not dispatch this lead. | subagent-contract, agent-orchestration, prd-writer | Read, Glob, Grep, Agent, SendMessage |
| `requirement-classifier` | PRD Validation | Execution Team | Worker | Validator | test | Classifies every requirement a PRD states as business or technical and, for each technical rule, asks the matrix whether the architecture already states it; never rewrites the PRD. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `ambiguity-detector` | PRD Validation | Execution Team | Worker | Validator | test | Finds the requirements of a PRD whose user-observable behavior is unclear, contradictory within itself or open to two incompatible readings (vague quantifiers, missing user-observable boundary conditions, unstated assumptions); reports each with a concrete clarification, never fixes. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `completeness-checker` | PRD Validation | Execution Team | Worker | Validator | test | Checks that each requirement of a PRD has an actor, a trigger or action, an observable user outcome and a behavioral acceptance criterion, and reports each missing or defective element; never supplies one. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `requirements-conflict-detector` | PRD Validation | Execution Team | Worker | Validator | test | Finds sets of requirements in a PRD whose WHAT cannot all hold, citing the requirements in tension; never resolves them. | subagent-contract, validation-protocol, artifact-handoff, prd-writer, acceptance-criteria | Read, Glob, Grep, Bash, Write, Agent |
| `constraint-extractor` | PRD Validation | Execution Team | Worker | Executor | execute | Extracts the explicit and implied constraints a PRD imposes (regulatory, business, platform, policy), each with its kind and where the PRD states or implies it; invents none. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `domain-boundary-validator` | PRD Validation | Execution Team | Worker | Validator | test | Checks that a PRD's requirements stay inside one bounded context, and reports each requirement that makes the feature own behavior another feature or service owns or that sits in more than one context. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `requirements-clarifier` | PRD Validation | Execution Team | Worker | Advisor | plan | Raises the open BUSINESS questions a PRD's author must answer before it can be specified, each tied to its requirement and unresolved; never answers them and never raises a technical gap. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `brd-traceability-auditor` | PRD Validation | Execution Team | Worker | Validator | test | Maps each PRD requirement to the objectives of a BRD the run names, for information only: a correspondence, never a verdict on the PRD. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `nfr-analyst` | PRD Validation | Execution Team | Worker | Advisor | plan | Lists the non-functional quality intents a PRD states or implies (performance, availability, security, privacy, accessibility, operability and the rest), each tied to the requirements that state or imply it, as input to a TRD; never quantifies them and never reports them as defects of the PRD. Available to a caller that chooses it; no workflow dispatches it. | subagent-contract, prd-writer | Read, Glob, Grep, Write, Agent |
| `aws-solutions-architect` | Architecture | Execution Team | Worker | Executor | execute | Holds single responsibility for the architecture a PRD needs, from the first read of the PRD until the architecture and the TRD are designed, reviewed and approved, with the review log that proves how. | effective-architecture, subagent-contract, find-specialists, senior-architect, aws-solution-architect, python-lambda-packaging, aws-serverless-eda, senior-security, graphrag-lookup, aws-core:aws-serverless, aws-core:aws-well-architected-review, aws-core:aws-security, aws-core:aws-billing-and-cost-management, log-architecture-review, aws-core:aws-database, matrix | Read, Glob, Grep, Bash, Write, Agent, SendMessage |
| `architecture-team-lead` | Architecture | Execution Team | Worker | Orchestrator | orchestrate | Routes what the solutions architect could not settle, so that the team settles it with the least further work. | effective-architecture, subagent-contract, find-specialists | Read, Glob, Grep, Bash, Write, Agent |
| `architecture-decider` | Architecture | Execution Team | Worker | Decider | approve | Rules between the positions on an architecture matter the solutions architect and the architecture team lead could not settle, from the evidence each position carries, and records the ruling in the matrix as the settlement of the disagreement. | effective-architecture, subagent-contract, validation-protocol, senior-architect, aws-solution-architect, python-lambda-packaging, matrix | Read, Glob, Grep, Write, Bash, Agent |
| `architecture-maintainer` | Architecture | Execution Team | Worker | Executor | execute | Writes the solutions architect's decisions into the architecture documents (arc42 and detailed/), each fact in its one home with links from every other document, and corrects the effective documents to match what a Story built. | effective-architecture, subagent-contract, arc42-maintain, c4-diagramming, uml-diagramming, matrix | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `architecture-diagram-author` | Architecture | Execution Team | Specialist | Executor | execute | Draws one architecture diagram of a design the solutions architect has settled, of any view type the documentation model lists (C4, UML, context map, data flow, deployment and the others), and returns it with its home, view type and the elements it shows. | subagent-contract, design-specialist-contract, architecture-diagramming, c4-diagramming, uml-diagramming, effective-architecture | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `c4-diagram-author` | Architecture | Execution Team | Specialist | Executor | execute | Draws one C4 diagram (system context, container, component or deployment) of a design the solutions architect has settled, and returns it with its home, view type and the elements it shows. | subagent-contract, design-specialist-contract, architecture-diagramming, c4-diagramming, effective-architecture | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `uml-diagram-author` | Architecture | Execution Team | Specialist | Executor | execute | Draws one UML diagram (sequence, state, activity, class, component or deployment) of a design the solutions architect has settled, and returns it with its home, view type and the elements it shows. | subagent-contract, design-specialist-contract, architecture-diagramming, uml-diagramming, effective-architecture | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `architecture-impact-analyst` | Architecture | Execution Team | Worker | Analyst | test | Judges what an architecture change reaches. Given the architecture views an integration changed, created or deleted, it takes from the matrix every Epic, open Task and entry those views reach (`atw-matrix impact`, `affected`), and rules on each one: unaffected, not yet elaborated, elaborated but unbuilt, or already built, with a knock-on Task proposed for each built item. It changes no bead and writes no code or document; it writes only its result file. | artifact-handoff, subagent-contract, beads-contract, validation-protocol, senior-architect, graphrag-lookup, matrix | Read, Glob, Grep, Bash, Write, Agent |
| `architecture-fitness-function-author` | Architecture | Execution Team | Worker | Executor | execute | Defines testable assertions from the owner's constraints and the architecture decisions, e.g. "every Lambda uses the configured logging library", "no service reads another service's table". | artifact-handoff, subagent-contract, validation-protocol, senior-architect, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `ubiquitous-language-writer` | Architecture | Execution Team | Worker | Executor | execute | Captures each bounded context's ubiquitous language — terms, definitions, usage rules — as a maintained glossary. | subagent-contract, validation-protocol, senior-architect | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `bounded-context-mapper` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on bounded contexts: their boundaries, domain responsibilities, which service owns each, the relationships between contexts and the published language each exposes. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-architect | Read, Write, Glob, Grep, Bash, Agent |
| `domain-event-modeler` | Design Specialists | Standalone Specialists | Specialist | Executor | plan | Answers a question or does a bounded piece of design for the solutions architect on domain events as facts: which fact each event states, the bounded context and aggregate that owns it, what triggers it, the causal flow it belongs to and the business meaning of the data it carries. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-architect | Read, Write, Glob, Grep, Bash, Agent |
| `data-architect` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on pure data architecture independent of any engine — conceptual and logical data models, entities and relationships, which domain owns each entity and its system of record, data flows and lineage, reference and master data, data classification and retention classes, operational versus analytical data, and data contracts between domains. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, data-architecture | Read, Write, Glob, Grep, Bash, Agent |
| `persistence-architecture-specialist` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on which store holds each data set (DynamoDB, Aurora or RDS, ElastiCache or MemoryDB, Neptune, DocumentDB, Timestream, S3, EBS, EFS or FSx), which block owns each store, the consistency each scenario needs, and the data lifecycle across stores. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, data-architecture, aws-core:aws-database, aws-core:aws-storage | Read, Write, Glob, Grep, Bash, Agent |
| `integration-pattern-architect` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on how building blocks interact: which interactions are synchronous calls and which are events, the delivery path each takes (direct call, EventBridge rule, SNS fan-out, SQS buffer, Step Functions), and its end- to-end delivery guarantee, ordering, idempotency and failure behaviour. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-serverless-eda, senior-architect, aws-core:aws-messaging-and-streaming | Read, Write, Glob, Grep, Bash, Agent |
| `security-architecture-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on trust boundaries, the threat model of a design and the mitigation of each threat across those boundaries: who may cross each boundary and what each runtime may reach. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-security | Read, Write, Glob, Grep, Bash, Agent |
| `cdk-infrastructure-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on which repository and which CDK stack hold each resource and building block, how stacks share values, which shared infrastructure must exist first, and construct and parameter names; and express the infrastructure the architecture records for a build Task as CDK provisioning intent. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-cdk-development, aws-core:aws-cdk, cdk-coding, resource-naming, matrix, python-lambda-packaging | Read, Write, Glob, Grep, Bash, Agent |
| `lambda-function-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS Lambda functions: runtime and architecture, memory, timeout and ephemeral storage, concurrency (reserved and provisioned), SnapStart, layers, invocation model and event source mappings, asynchronous invocation destinations, VPC attachment and cold-start behaviour. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, lambda, aws-core:aws-serverless, python-lambda-packaging | Read, Write, Glob, Grep, Bash, Agent |
| `container-service-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on containers on Amazon ECS: Fargate or ECS Managed Instances or EC2 capacity, task definitions (CPU, memory, containers, health checks), services and their deployment and scaling, Amazon ECR repositories and image lifecycle. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-containers | Read, Write, Glob, Grep, Bash, Agent |
| `kubernetes-cluster-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon EKS: cluster version and access, compute (managed node groups, Karpenter, Fargate profiles, EKS Auto Mode), pod networking, workload identity, add-ons and pod scaling. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-containers | Read, Write, Glob, Grep, Bash, Agent |
| `ec2-fleet-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon EC2 fleets: instance type selection, AMIs, launch templates, Auto Scaling groups and their scaling policies, Spot and mixed instances, IMDSv2 and fleet operations through Systems Manager. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-compute | Read, Write, Glob, Grep, Bash, Agent |
| `batch-compute-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS Batch: compute environments (Fargate, EC2, Spot), job queues and their priorities, job definitions, array and multi-node jobs, retries and timeouts, and scheduling policies. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-compute | Read, Write, Glob, Grep, Bash, Agent |
| `relational-database-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on relational databases on Amazon Aurora, Amazon RDS, Aurora DSQL and RDS Proxy — engine and cluster shape, capacity, access path, replicas, backups, and the relational schema (tables, keys, constraints, indexes, partitioning, migrations). | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aurora-postgresql, rds, design-postgres-tables, database-schema-designer, aws-core:aws-database | Read, Write, Glob, Grep, Bash, Agent |
| `dynamodb-table-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon DynamoDB and DAX — access-pattern-first single-table or multi-table design, partition and sort keys, GSIs and LSIs, capacity mode, TTL, streams, transactions, global tables, backups and cost. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, dynamodb, aws-core:aws-database | Read, Write, Glob, Grep, Bash, Agent |
| `cache-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on in-memory caching and in-memory data stores on Amazon ElastiCache (Valkey, Redis OSS, Memcached; serverless or node-based) and Amazon MemoryDB — caching pattern, key and TTL design, invalidation, eviction, topology, durability and multi-Region replication. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-database | Read, Write, Glob, Grep, Bash, Agent |
| `graph-database-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on graph data on Amazon Neptune Database and Neptune Analytics — engine and capacity choice, property graph or RDF, node and edge model, query language (openCypher, Gremlin, SPARQL), traversal and supernode design, loading, graph algorithms and vector search. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, amazon-neptune, aws-core:aws-database | Read, Write, Glob, Grep, Bash, Agent |
| `document-database-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on document data on Amazon DocumentDB (MongoDB compatible) — cluster type and capacity, document model (embedding or referencing), indexes, MongoDB API compatibility, change streams, transactions and read scaling. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-database | Read, Write, Glob, Grep, Bash, Agent |
| `time-series-database-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on time-series data on Amazon Timestream (Timestream for InfluxDB, and Timestream for LiveAnalytics for existing accounts) — engine choice, measurement, tag and field model, cardinality, retention and downsampling, ingestion and query. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-database | Read, Write, Glob, Grep, Bash, Agent |
| `object-storage-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on object storage on Amazon S3 and the S3 Glacier storage classes — buckets, key layout, storage classes and lifecycle, versioning and Object Lock, replication, access control and Block Public Access, presigned URLs, multipart upload and event notifications. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, s3, aws-core:aws-storage | Read, Write, Glob, Grep, Bash, Agent |
| `block-and-file-storage-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on block and file storage for EC2, containers and Lambda on Amazon EBS, Amazon EFS and Amazon FSx (Lustre, NetApp ONTAP, OpenZFS, Windows File Server) — volume and file system type, performance and throughput mode, availability, snapshots and backups, lifecycle tiering and access. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-storage | Read, Write, Glob, Grep, Bash, Agent |
| `vpc-network-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon VPC networking: CIDR plan, subnets and route tables, internet and NAT gateways, VPC endpoints (gateway and interface) and PrivateLink, security groups and network ACLs, Transit Gateway and peering, and VPC flow logs. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-networking | Read, Write, Glob, Grep, Bash, Agent |
| `load-balancer-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on Elastic Load Balancing: choosing an Application, Network or Gateway Load Balancer, listeners and TLS, routing rules, target groups and health checks, stickiness, deregistration and cross-zone behaviour. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup | Read, Write, Glob, Grep, Bash, Agent |
| `dns-and-edge-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon Route 53 and Amazon CloudFront: hosted zones, records and routing policies, health checks and failover, CloudFront distributions, origins and origin access control, cache and origin request policies, edge functions, and custom domains. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-networking | Read, Write, Glob, Grep, Bash, Agent |
| `api-contract-designer` | Design Specialists | Standalone Specialists | Specialist | Executor | plan | Answers a question or does a bounded piece of design for the solutions architect on REST APIs on Amazon API Gateway (REST API): which building block exposes each interface, its resources and methods, who may call it and how the caller is authorized, request validation, throttling and usage plans, errors, and how it stays compatible. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, api-gateway, api-design-reviewer, aws-core:aws-auth | Read, Write, Glob, Grep, Bash, Agent |
| `graphql-api-designer` | Design Specialists | Standalone Specialists | Specialist | Executor | plan | Answers a question or does a bounded piece of design for the solutions architect on GraphQL APIs on AWS AppSync: schema, operations and types, which block resolves each field from which owned data, resolvers and data sources, authorization modes, subscriptions, caching and compatibility. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, appsync-graphql, aws-core:aws-auth | Read, Write, Glob, Grep, Bash, Agent |
| `event-routing-designer` | Design Specialists | Standalone Specialists | Specialist | Executor | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon EventBridge: event type names and their registry entries, the payload schema of a new event type, buses, routing rules (event pattern, targets, owning stack), each rule target's retry policy and dead-letter queue, and EventBridge Scheduler schedules. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, eventbridge, aws-core:aws-serverless | Read, Write, Glob, Grep, Bash, Agent |
| `queue-and-topic-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon SQS queues and Amazon SNS topics: standard or FIFO, visibility timeout, retention, redrive policies and dead- letter queues, SNS subscriptions, filter policies and delivery retry, fan-out, and Amazon MQ where a broker protocol is required. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, sqs, sns, aws-core:aws-messaging-and-streaming | Read, Write, Glob, Grep, Bash, Agent |
| `workflow-orchestration-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS Step Functions: Standard or Express workflows, state machine structure in Amazon States Language, service integration patterns, retries and catches, sagas and compensation, Map and Parallel states, callbacks, and execution logging. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, step-functions, aws-core:aws-serverless | Read, Write, Glob, Grep, Bash, Agent |
| `stream-processing-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on real-time data streams on Amazon Kinesis Data Streams, Amazon Data Firehose, Amazon MSK and Amazon Managed Service for Apache Flink — stream and capacity mode, partition keys and ordering, retention, consumers and fan-out, delivery buffering, transformation and processing windows. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-messaging-and-streaming, senior-data-engineer | Read, Write, Glob, Grep, Bash, Agent |
| `data-lake-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on the data lake on AWS Glue, AWS Lake Formation and Amazon S3 Tables — zones and table layout, open table format (Apache Iceberg), partitioning, the Glue Data Catalog, ingestion and ETL jobs, connections to sources, data quality and Lake Formation permissions. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-data-analytics:creating-data-lake-table, aws-data-analytics:ingesting-into-data-lake, aws-data-analytics:exploring-data-catalog, aws-data-analytics:connecting-to-data-source, senior-data-engineer | Read, Write, Glob, Grep, Bash, Agent |
| `analytics-query-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on serverless SQL analytics with Amazon Athena over the data lake — workgroups and their limits, query result handling, data layout for scan cost, partition projection, federated and Iceberg queries, CTAS and UNLOAD, and capacity. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-data-analytics:querying-data-lake, aws-data-analytics:finding-data-lake-assets | Read, Write, Glob, Grep, Bash, Agent |
| `data-warehouse-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on data warehousing on Amazon Redshift (Serverless or provisioned RA3) — workgroup or cluster shape, table design (distribution, sort keys, encoding), loading with COPY and zero-ETL, materialized views, data sharing, Spectrum and workload management. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-data-analytics:redshift-guide | Read, Write, Glob, Grep, Bash, Agent |
| `iam-policy-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS IAM: roles and their trust policies, identity and resource policies with least privilege, condition keys and confused-deputy protection, permission boundaries, cross-account access, service-linked and service roles, and IAM Identity Center for human access. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, iam, aws-core:aws-iam | Read, Write, Glob, Grep, Bash, Agent |
| `user-authentication-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on end-user authentication with Amazon Cognito: user pools and app clients, sign-up and sign-in flows, MFA and passkeys, OAuth 2.0 and OIDC flows, social and SAML federation, tokens and their lifetimes, Lambda triggers, and identity pools. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, cognito, aws-core:aws-auth | Read, Write, Glob, Grep, Bash, Agent |
| `encryption-and-secrets-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS KMS keys and key policies, envelope encryption and key rotation, AWS Secrets Manager secrets and their rotation, and AWS Certificate Manager certificates. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, secrets-manager, aws-core:aws-secrets-manager | Read, Write, Glob, Grep, Bash, Agent |
| `perimeter-protection-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS WAF web ACLs and rules (managed rule groups, rate-based rules, bot control), AWS Shield Standard and Advanced for DDoS protection, Route 53 Resolver DNS Firewall, and Amazon GuardDuty threat detection. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-networking, aws-core:aws-security | Read, Write, Glob, Grep, Bash, Agent |
| `foundation-model-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon Bedrock foundation models - model and inference profile choice per task, Converse API calls, maxTokens and timeouts, quotas and throughput, prompt caching, attaching guardrails to a model call, and inference cost. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, bedrock, aws-core:amazon-bedrock | Read, Write, Glob, Grep, Bash, Agent |
| `rag-architecture-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on retrieval-augmented generation and semantic search - Bedrock Knowledge Bases, chunking, embeddings models, vector stores (Aurora pgvector, S3 Vectors, OpenSearch, Neptune Analytics), hybrid retrieval, re-ranking, metadata filtering and retrieval evaluation. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, rag-architect, pgvector-semantic-search, aurora-postgresql, recommendation-ranking, aws-data-analytics:storing-and-querying-vectors, aws-data-analytics:amazon-opensearch-service, aws-core:amazon-bedrock | Read, Write, Glob, Grep, Bash, Agent |
| `applied-ai-services-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on the AWS pre-trained AI services - Amazon Textract document extraction, Amazon Rekognition image and video analysis, and Amazon Comprehend text analysis and PII detection - their operations, synchronous or asynchronous paths, limits, confidence handling and cost. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup | Read, Write, Glob, Grep, Bash, Agent |
| `ml-feature-pipeline-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on machine learning features - feature definitions and engineering, batch or streaming computation, SageMaker Feature Store online and offline stores, SageMaker Data Wrangler data preparation, training-serving consistency and feature drift. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-data-scientist, senior-ml-engineer, senior-data-engineer | Read, Write, Glob, Grep, Bash, Agent |
| `ml-training-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on training and fine-tuning models on Amazon SageMaker AI - base model and technique (SFT, DPO, RLVR, RLAIF), training data, training jobs, managed Spot and checkpointing, hyperparameter tuning, evaluation and acceptance, experiment tracking and retraining. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-ai-ml, senior-data-scientist, senior-ml-engineer | Read, Write, Glob, Grep, Bash, Agent |
| `ml-inference-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on serving trained models on Amazon SageMaker AI - real-time, serverless and asynchronous endpoints, batch transform, multi-model and multi-container endpoints, scaling, deployment guardrails and shadow tests, and Model Monitor. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-ai-ml, senior-ml-engineer | Read, Write, Glob, Grep, Bash, Agent |
| `ai-agent-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on custom AI agents - Amazon Bedrock AgentCore Runtime and Harness, agent frameworks such as Strands, AgentCore Memory, tools through AgentCore Gateway and MCP, multi-agent and A2A, AgentCore Identity and Cedar policies, and agent bounds. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-agentic-ai, aws-agents:agents-get-started, aws-agents:agents-build, aws-agents:agents-connect, aws-agents:agents-harden, mcp-server-builder, aws-core:amazon-bedrock | Read, Write, Glob, Grep, Bash, Agent |
| `generative-ai-pattern-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on generative AI flow patterns - prompt chaining, routing, parallelisation, orchestrator and workers, evaluator-optimiser loops, prompt structure, structured output, chain of verification, LLM-as-judge evaluation, human in the loop and applying guardrails to a flow. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-prompt-engineer, cove-prompt-design, aws-core:amazon-bedrock | Read, Write, Glob, Grep, Bash, Agent |
| `monitoring-and-tracing-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on Amazon CloudWatch and AWS X-Ray: metrics and embedded metric format, log groups and retention, Logs Insights queries, alarms (metric, composite, anomaly detection) and their actions, dashboards, distributed tracing with X-Ray and ADOT, Application Signals, synthetics and SLO alarms. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-observability, cloudwatch, observability-designer | Read, Write, Glob, Grep, Bash, Agent |
| `audit-and-compliance-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answers a question or does a bounded piece of design for the solutions architect on AWS CloudTrail (trails, management and data events, CloudTrail Lake, log integrity and retention) and AWS Config (recording, managed and custom rules, conformance packs, remediation), and the Security Hub controls they feed. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-observability, aws-core:aws-security | Read, Write, Glob, Grep, Bash, Agent |
| `architecture-boundary-guardian` | Architecture Review Specialists | Standalone Specialists | Specialist | Validator | test | Reviews, for the solutions architect, the boundaries of a design: whether each building block's responsibilities and owned data stay inside its bounded context, whether every interface that crosses a boundary is explicit about who exposes it and who may call it, whether shared behaviour is taken from its shared home, and whether the design breaks a section 2 constraint or departs from an established pattern without a stated reason. | subagent-contract, design-specialist-contract, effective-architecture, senior-architect, graphrag-lookup, matrix | Read, Glob, Grep, Bash, Write, Agent |
| `architecture-pattern-challenger` | Architecture Review Specialists | Standalone Specialists | Specialist | Adversary | test | Reviews, for the solutions architect, the structure of a design for concrete weaknesses: a mechanism that does not do what the requirement needs, a structure more complex than the requirement, or an AWS pattern used against its documented best practice, each reported with the simpler sufficient repair. | subagent-contract, design-specialist-contract, effective-architecture, senior-architect, aws-solution-architect, python-lambda-packaging, aws-serverless-eda, aws-core:aws-well-architected-review | Read, Glob, Grep, Bash, Write, Agent |
| `architecture-tradeoff-skeptic` | Architecture Review Specialists | Standalone Specialists | Specialist | Adversary | test | Reviews, for the solutions architect, the trade-off claims of a design: whether each choice between options states the options and a reason the evidence supports, and whether the assumptions and estimates it rests on (latency, throughput, limits, effort) hold against the stated constraints and AWS documentation. | subagent-contract, design-specialist-contract, effective-architecture, senior-architect, aws-solution-architect, python-lambda-packaging, aws-core:aws-well-architected-review | Read, Glob, Grep, Bash, Write, Agent |
| `failure-mode-analyst` | Architecture Review Specialists | Standalone Specialists | Specialist | Advisor | test | Reviews, for the solutions architect, how a design fails and recovers: throttling, duplicate and out-of-order delivery, poison messages, downstream outages, timeouts, retries, dead-letter queues, idempotency and recovery paths across Lambda, SQS, SNS, EventBridge and the event path, as the runtime views and the TRD state them. | subagent-contract, design-specialist-contract, effective-architecture, aws-serverless-eda, lambda, sqs, eventbridge | Read, Glob, Grep, Bash, Write, Agent |
| `operational-readiness-reviewer` | Architecture Review Specialists | Standalone Specialists | Specialist | Validator | test | Reviews, for the solutions architect, whether a design can be operated: the logs, metrics, alarms and dashboards each block needs, the TRD's observability, availability and recovery obligations, how each failure is detected and who is told, and the operational burden at the stated usage. | subagent-contract, design-specialist-contract, effective-architecture, observability-designer, cloudwatch, aws-core:aws-observability | Read, Glob, Grep, Bash, Write, Agent |
| `new-resource-cost-reviewer` | Architecture Review Specialists | Standalone Specialists | Specialist | Advisor | test | Reviews, for the solutions architect, the cost of each billable AWS resource a design adds: its unit prices from the AWS Price List, the monthly unit math at the stated usage computed by script, its fixed monthly floor separated from its usage cost, and the total against the stated cost ceilings. | subagent-contract, design-specialist-contract, effective-architecture, aws-core:aws-billing-and-cost-management | Read, Glob, Grep, Bash, Write, Agent |
| `changed-resource-cost-reviewer` | Architecture Review Specialists | Standalone Specialists | Specialist | Adversary | test | Reviews, for the solutions architect, the cost effect of a design's changes to existing resources: changed billable limits, capacity modes, retention or usage, the cost assumptions each change rests on, a monthly floor it adds or moves, and any cost cliff (a pricing tier, free-tier limit, quota or capacity-mode boundary) the stated usage reaches. | subagent-contract, design-specialist-contract, effective-architecture, aws-core:aws-billing-and-cost-management, matrix | Read, Glob, Grep, Bash, Write, Agent |
| `trd-author` | TRD | Execution Team | Worker | Executor | execute | Writes the TRD as one of the very first steps of the architecture, the requirements not considered functional, many pre-written in arc42, and updates it as the architecture is decided. | subagent-contract, effective-architecture, matrix, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `prd-trd-traceability-verifier` | TRD | Execution Team | Worker | Validator | test | Builds and checks the TRD's SOURCE traceability matrix: every TRD requirement anchored to a PRD requirement OR to an architecture view, every PRD requirement needing technical elaboration answered, and genuine scope drift flagged. The relation is not 1:1 and an architecture-sourced requirement is not an orphan. | subagent-contract, validation-protocol, effective-architecture | Read, Glob, Grep, Bash, Write, Agent |
| `trd-decider` | TRD | Execution Team | Worker | Decider | approve | Rules on a dispute over a TRD from the evidence the sides wrote: a TRD maker-checker deadlock, competing TRD approaches, or checkers that contradict each other on one TRD section; generates no TRD content or analysis. For a caller that runs a TRD review loop; in elaboration TRD disputes go to architecture-decider through the architecture team. | subagent-contract, validation-protocol, effective-architecture | Read, Glob, Grep, Write, Agent |
| `spec-authoring-lead` | Spec Authoring | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes maker output to checkers and findings back to makers until checkers pass, then reports the spec packet; never evaluates spec quality, only pass/rework signals. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent, SendMessage |
| `ui-design-source-selector` | Spec Authoring | Execution Team | Worker | Advisor | plan | Chooses the design source of each UI item a frontend repository's Story builds, from the cds bundles the owner supplied and the configured Configurable Design System (cds) - a supplied bundle, the live design system, or no design change; designs nothing. | subagent-contract, artifact-handoff, cds:apply-design-system, cds:audit-against-system | Read, Write, Glob, Grep, Bash, Agent |
| `api-specification-author` | Spec Authoring | Execution Team | Worker | Executor | execute | Writes the spec of the API, event, error and UI contracts one repository's Story builds, from the recorded architecture and design; designs nothing. | subagent-contract, validation-protocol, api-design-reviewer, artifact-handoff, effective-architecture, graphrag-lookup, matrix, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `data-model-specification-author` | Spec Authoring | Execution Team | Worker | Executor | execute | Writes the spec of the data one repository's Story builds, from the recorded architecture and design; designs nothing. | subagent-contract, validation-protocol, dynamodb, database-schema-designer, artifact-handoff, effective-architecture, aurora-postgresql, design-postgres-tables, pgvector-semantic-search, graphrag-lookup, matrix, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `acceptance-criteria-writer` | Spec Authoring | Execution Team | Worker | Executor | execute | Derives traceable criteria and Definition of Done from the finished specification set. | subagent-contract, validation-protocol, artifact-handoff, effective-architecture, acceptance-criteria | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `definition-of-done-writer` | Spec Authoring | Execution Team | Worker | Executor | execute | Writes the Definition of Done of a given scope of work as independently verifiable true-or-false statements about the finished work, never checklist steps, each traced to the requirement or design decision it comes from. For a caller that needs a Definition of Done on its own; in elaboration the acceptance-criteria-writer writes it with the criteria. | subagent-contract, validation-protocol, effective-architecture | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dynamodb-schema-access-pattern-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Reviews the DynamoDB stores of one repository's data-model spec: whether each access pattern it states can be served by the keys and indexes it states, at the stated capacity, without a scan or client-side filtering, and whether each store has the key attributes, indexes, access patterns and expiry attribute the detailed design records. Returns findings the data-model author can correct without interpretation; changes nothing. | subagent-contract, artifact-handoff, effective-architecture, dynamodb | Read, Glob, Grep, Bash, Write, Agent |
| `spec-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Reviews one repository's three specification documents (the API, event and error contracts, the data model, and the acceptance criteria) against the specs-and-Tasks criteria I1 to I7 of the review standard, once, and returns findings a document's author can correct without interpretation; changes nothing. | subagent-contract, validation-protocol, api-design-reviewer, artifact-handoff, effective-architecture, dynamodb, aurora-postgresql, design-postgres-tables, python-lambda-packaging | Read, Glob, Grep, Write, Agent |
| `acceptance-criteria-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Reviews acceptance criteria and Definition of Done statements for testability, completeness and ambiguity: whether a test can be derived from each without interpretation, with boundary and failure cases covered; reports findings, never fixes. For a caller that wants criteria checked on their own; in elaboration spec-reviewer reviews the criteria document with the specs. | subagent-contract, validation-protocol, effective-architecture, acceptance-criteria | Read, Glob, Grep, Write, Agent |
| `event-schema-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Validates event contracts against the project's standard event and each event's payload schema — event type names, passed values, publishing conditions, consumer obligations, retry/DLQ behavior. | subagent-contract, validation-protocol, eventbridge, sqs | Read, Glob, Grep, Bash, Write, Agent |
| `graphql-schema-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Reviews the GraphQL contracts of a specification against the architecture and detailed design that record the API and against AppSync patterns: types, operations, resolver and data-source mappings, authorization modes and directives, error shapes, pagination and naming; reports findings, never fixes. For a caller that wants a spec's GraphQL contracts checked. | subagent-contract, validation-protocol, api-design-reviewer, effective-architecture, appsync-graphql | Read, Glob, Grep, Bash, Write, Agent |
| `review-dispute-decider` | Spec Authoring | Execution Team | Worker | Decider | approve | Rules on a review dispute between a maker and its reviewer, from the evidence the two sides wrote: each spec review finding a specification document's author disputes (the finding stands, with the directive the author applies, or the document stands), and a PRD draft the prd-writer and the prd-alignment-verifier could not converge on (accept or reject); writes no document content and no analysis of its own. | subagent-contract, validation-protocol, artifact-handoff, effective-architecture, prd-writer | Read, Glob, Grep, Write, Bash, Agent |
| `task-decomposer` | Planning and Scoring | Execution Team | Worker | Executor | execute | Decomposes what one Story builds into coherent, sized build Tasks in one repository. | subagent-contract, validation-protocol, beads-contract, graphrag-lookup, artifact-handoff, wsjf, matrix, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `task-dependency-mapper` | Planning and Scoring | Execution Team | Worker | Executor | execute | Maps the build dependencies between Tasks: an edge wherever one Task cannot be built until another is, because it consumes something the other provides. Proposes the cross-Story edges among the Tasks of one Epic's Stories, or every edge to or from one Task created outside elaboration; writes no edge itself. | subagent-contract, validation-protocol, beads-contract, artifact-handoff, graphrag-lookup, matrix | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `epic-dependency-assessor` | Planning and Scoring | Execution Team | Worker | Advisor | plan | Proposes and validates the architecture-dependency edges to and from ONE Epic, by the edge test of the epic-sequencing skill, and accounts for every owned edge standing on it; orders nothing, scores nothing and applies nothing. | subagent-contract, epic-sequencing, artifact-handoff, matrix | Read, Write, Bash, Glob, Grep, Agent |
| `wsjf-scorer` | Planning and Scoring | Execution Team | Worker | Executor | execute | Judges the WSJF inputs of work items under the wsjf skill's rubric: for an Epic its user-business value, time criticality and their confidence from its PRD, and its job size estimate while it is not sized from its Tasks; for the Tasks of an Epic their job sizes. Writes the judgments; computes no RR-OE and no WSJF, and writes nothing to a bead. | subagent-contract, validation-protocol, wsjf, beads-contract, artifact-handoff, matrix | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `wsjf-scoring-reviewer` | Planning and Scoring | Execution Team | Worker | Validator | test | Reviews the job sizes in a set of Task WSJF judgments for consistency, evidence and defensibility against the wsjf skill's rubric and recomputes the arithmetic; reports findings, never fixes. For a caller that wants a scoring run checked. | subagent-contract, validation-protocol, wsjf | Read, Glob, Grep, Bash, Write, Agent |
| `story-bead-writer` | Planning and Scoring | Execution Team | Worker | Executor | execute | Writes the title and description of ONE Story bead, a single-repository container paired with a spec set, and names the work outside the Story's repository that the Epic's closure in the matrix holds. For a caller that needs a Story written outside elaboration; elaboration writes its Stories by script. | subagent-contract, validation-protocol, matrix | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `user-story-reviewer` | Planning and Scoring | Execution Team | Worker | Validator | test | Reviews user stories (persona, goal, benefit and acceptance criteria) for completeness, testability and scope against the work each story covers and the spec it cites; reports findings, never fixes. For a caller that holds user stories, such as a PRD's or a person's backlog. | subagent-contract, validation-protocol, beads-contract | Read, Glob, Grep, Bash, Write, Agent |
| `beads-format-validator` | Planning and Scoring | Execution Team | Worker | Validator | test | Validates that Beads issues are structurally complete (title, acceptance criteria found where the beads contract looks, dependencies that resolve, spec links that resolve) and obey the hierarchy rule; reports defects, never fixes. For a caller that wants a set of issues checked before work starts. | subagent-contract, validation-protocol, beads-contract | Read, Glob, Grep, Bash, Write, Agent |
| `built-architecture-comparer` | Built Version | Execution Team | Worker | Validator | test | Compares the code one Story built with the approved architecture and design headings that describe the stacks and entries it built, and records each difference as an in-review view under built/<element>/, citing the code by file and line. | subagent-contract, effective-architecture, architecture-diagramming, graphrag-lookup, matrix | Read, Glob, Grep, Bash, Write, Agent |
| `architecture-conformance-reviewer` | Built Version | Execution Team | Worker | Validator | test | Checks, without modifying anything, that a correction of the effective architecture documents describes each element exactly as the built views of a Story record it, at every scope, with conforming front matter and placement and section 2 untouched. | artifact-handoff, subagent-contract, validation-protocol, arc42, architecture-diagramming, graphrag-lookup, effective-architecture, matrix, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `spec-freshness-lead` | Spec Freshness | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes spec freshness checks to validators and aggregates findings into one freshness packet. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent, SendMessage |
| `spec-currency-validator` | Spec Freshness | Execution Team | Worker | Validator | test | Checks, before implementation begins, that a specification still matches the project: every module, interface, contract, data model, file path and convention it references still exists and still matches, each claim classed current, drifted or unverifiable with evidence. For a caller that holds a spec written some time before its build. | subagent-contract, validation-protocol, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `dependency-change-detector` | Spec Freshness | Execution Team | Worker | Validator | test | Detects dependency version and contract changes since a specification was written, by diffing manifests and lockfiles against the spec-time reference and checking changed contracts, classing each as unchanged, reconciled in the spec, or needing reconciliation. For a caller that holds a spec written some time before its build. | subagent-contract, validation-protocol, dependency-auditor, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `test-design-lead` | Test Design | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes spec acceptance criteria to test writers, confirms Red (every new test fails), and assembles the Red readiness packet. | subagent-contract, agent-orchestration, python-lambda-packaging | Read, Glob, Grep, Agent, SendMessage |
| `tdd-unit-test-generator` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes failing unit tests, including cdk synth assertion tests of CDK stacks, from acceptance criteria before the implementation exists and confirms each fails for the intended reason; and, in update mode, rules on every existing test of any kind an implementer names (update, delete or keep, citing the contract) and applies the ruling. Python and TypeScript, back end, front end and CDK. | subagent-contract, validation-protocol, tdd-guide, cumulative-regression, python-coding, typescript-coding, web-frontend-coding, cdk-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `consumer-driven-contract-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes failing consumer-driven contract tests from the spec's API and event contracts. | subagent-contract, validation-protocol, contract-testing, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `security-test-case-designer` | Test Design | Execution Team | Worker | Executor (test author) | test | Designs failing security test cases from the threat model: abuse cases, negative paths, authorization matrices. | subagent-contract, validation-protocol, senior-security, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `aws-integration-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes failing integration tests covering the event delivery path the effective architecture describes, hop by hop. | subagent-contract, validation-protocol, aws-serverless-eda, cumulative-regression, python-coding, software-engineering, aws-core:aws-sdk-python-usage, aws-core:aws-serverless, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `playwright-e2e-web-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes failing Playwright E2E web tests for UI and API flows from spec acceptance criteria. | subagent-contract, validation-protocol, senior-qa, cumulative-regression, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `performance-benchmark-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes failing performance benchmarks with budgets from the spec's non-functional requirements. | subagent-contract, validation-protocol, senior-qa, load-testing, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `xcuitest-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes failing XCUITest suites for iOS features from spec acceptance criteria pre-implementation, confirming each fails for the intended reason. | subagent-contract, validation-protocol, ios-swiftui, tdd-guide, cumulative-regression, graphrag-lookup, software-engineering | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `espresso-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes failing Espresso suites for Android features from spec acceptance criteria, confirming each test fails for the intended reason. | subagent-contract, validation-protocol, android-compose, tdd-guide, cumulative-regression, graphrag-lookup, software-engineering | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `mobile-e2e-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes failing Detox and Maestro E2E tests for React Native and cross-platform mobile flows before implementation, confirming each fails for the intended reason. | subagent-contract, validation-protocol, cumulative-regression, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `ml-evaluation-tester` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and runs ML evaluation suites — matching quality, recommendation relevance, embedding drift — confirming each fails before the component exists. | subagent-contract, validation-protocol, senior-ml-engineer, senior-data-scientist, recommendation-ranking, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `data-pipeline-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes failing data pipeline tests — ETL correctness, CDC ordering, data quality, replay safety — confirming each fails for the intended reason. | subagent-contract, validation-protocol, senior-data-engineer, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `acceptance-criteria-coverage-assessor` | Test Design | Execution Team | Worker | Validator | test | Establishes, before any test is written, which acceptance criteria the repository's existing tests already encode and which are gaps, and — when every criterion is covered — runs only those tests and rules whether they are red, already-satisfied or not-encoded. Use before Red to avoid duplicate tests or a manufactured red for behaviour that already exists. Never writes or repairs a test. | subagent-contract, validation-protocol, senior-qa, cumulative-regression, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `test-plan-strategy-reviewer` | Test Design | Execution Team | Worker | Validator | test | Reviews a feature's test plan and authored suites at the strategy level — balance across unit, contract, integration, E2E, security and performance layers, test investment in the spec's highest risks, feasibility of the environments the tests need, duplication and contradiction between suites — and reports findings only. | subagent-contract, validation-protocol, senior-qa, cumulative-regression | Read, Glob, Grep, Bash, Write, Agent |
| `test-isolation-specialist` | Test Design | Execution Team | Worker | Validator | test | Validates that tests are independent — no shared mutable state, no order dependence, self-cleaning fixtures — by static inspection and by running the suites in shuffled order and repeatedly, and reports each isolation defect with a reproduction; never fixes. | subagent-contract, validation-protocol, tdd-guide, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `test-strategy-decider` | Test Design | Execution Team | Worker | Decider | approve | Decides a feature's test strategy — pyramid shape across test layers, environment matrix per platform, coverage thresholds — from strategy analyses and reviewer findings others produced, with a recorded rationale and rejected alternatives; generates no analysis of its own. | subagent-contract, validation-protocol, senior-qa | Read, Glob, Grep, Write, Agent |
| `implementation-lead` | Implementation | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Selects the implementer(s) whose specialties cover a Task, in build order, from the Task's build contract — its spec documents and the architecture views it was designed against. | subagent-contract, agent-orchestration, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Agent |
| `chassis-extension-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Lambda handlers as chassis superclass extensions for API endpoints and event consumers; writes minimum code to pass failing unit tests. | subagent-contract, implementer-contract, validation-protocol, aws-serverless-eda, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `api-gateway-cdk-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements API Gateway resources, methods, and authorizers in CDK; writes minimum code to pass failing unit tests. | subagent-contract, implementer-contract, validation-protocol, api-gateway, aws-cdk-development, graphrag-lookup, python-coding, software-engineering, aws-core:aws-cdk, aws-core:aws-serverless, aws-core:aws-auth, cdk-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `cdk-stack-author` | Implementation | Execution Team | Worker | Executor | execute | Writes AWS CDK stacks, constructs and app wiring in Python for an infrastructure Task, as the Task, its spec, the provisioning intent and the architecture give them, with the minimum change that makes the failing synth assertion tests pass. Never deploys. | subagent-contract, validation-protocol, aws-cdk-development, cloudformation, python-coding, software-engineering, aws-core:aws-cdk, graphrag-lookup, cdk-coding, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `event-api-client-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the calls a service makes to the project's central event API to publish the project's events. | subagent-contract, implementer-contract, validation-protocol, aws-serverless-eda, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `event-driven-consumer-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the handler code of a routing rule's target, for whatever target type the target's owner chose. | subagent-contract, implementer-contract, validation-protocol, sqs, aws-serverless-eda, sns, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dynamodb-access-layer-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements DynamoDB access patterns from the data model spec; writes minimum code to pass failing tests. | subagent-contract, implementer-contract, validation-protocol, dynamodb, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, aws-core:aws-database, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `postgresql-access-layer-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Aurora PostgreSQL access patterns through the RDS Data API from the data model spec, and the schema migrations they need; writes minimum code to pass failing tests. | subagent-contract, implementer-contract, validation-protocol, aurora-postgresql, design-postgres-tables, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, aws-core:aws-database, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `power-tools-configuration-implementer` | Implementation | Execution Team | Worker | Executor | execute | Configures Lambda Power Tools — structured logging, tracing, metrics, idempotency — on Lambdas built on the chassis; configures, never rebuilds. | subagent-contract, implementer-contract, validation-protocol, lambda, secrets-manager, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-observability, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `cognito-lambda-trigger-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Cognito Lambda triggers — sign-up, confirmation, token customization, custom auth challenges — on the chassis the architecture describes. | subagent-contract, implementer-contract, validation-protocol, cognito, lambda, graphrag-lookup, python-coding, software-engineering, aws-core:aws-auth, aws-core:aws-serverless, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `webauthn-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements WebAuthn passkey flows across web clients and the Cognito-backed auth stack: registration and authentication ceremonies with client-side handling. | subagent-contract, implementer-contract, validation-protocol, graphrag-lookup, software-engineering, aws-core:aws-auth, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `cds-ui-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements a Task's web UI components and pages in the application repository with the Configurable Design System (cds) applied by construction, from the supplied cds bundle or the live design system, and audits the changed UI against it before reporting; writes the minimum code that makes the failing tests pass. | subagent-contract, implementer-contract, cds:apply-design-system, cds:audit-against-system, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Bash, Glob, Grep, Agent |
| `nextjs-component-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the non-visual React/Next.js work — component state, data fetching, Next.js routing — writing minimum code to pass failing unit tests. Visual component and page work goes to cds-ui-implementer, which builds with the cds design system. | subagent-contract, implementer-contract, cds:apply-design-system, validation-protocol, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `appsync-cdk-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements AppSync GraphQL APIs in CDK: schema wiring, resolvers, data sources, authorization. | subagent-contract, implementer-contract, validation-protocol, aws-cdk-development, graphrag-lookup, python-coding, software-engineering, aws-core:aws-cdk, cdk-coding, appsync-graphql, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `appsync-client-subscription-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements AppSync client subscriptions for real-time web features. | subagent-contract, implementer-contract, validation-protocol, senior-frontend, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, appsync-graphql, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `ios-swiftui-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements iOS features in SwiftUI; writes minimum code to pass failing XCUITest suites. | subagent-contract, implementer-contract, ios-swiftui, validation-protocol, graphrag-lookup, software-engineering, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `android-compose-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Android features in Kotlin and Jetpack Compose; writes minimum code to pass failing Espresso suites. | subagent-contract, implementer-contract, android-compose, validation-protocol, graphrag-lookup, software-engineering, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `react-native-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements React Native cross-platform mobile features; writes minimum code to pass failing Detox and Maestro tests. | subagent-contract, implementer-contract, validation-protocol, senior-frontend, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `bedrock-integration-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the code that calls Amazon Bedrock foundation models - Converse and ConverseStream calls, prompt assembly from specified templates, guardrail and prompt-cache settings on the call, structured-output parsing, and inference error handling - writing minimum code to pass failing tests. Embeddings calls belong to vector-search-embeddings-implementer. | subagent-contract, validation-protocol, bedrock, graphrag-lookup, python-coding, software-engineering, aws-core:amazon-bedrock, aws-core:aws-sdk-python-usage, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `llm-observability-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements LLM observability — prompt/response logging, token and cost metrics, drift alerts — writing minimum code to pass failing tests. | subagent-contract, validation-protocol, senior-ml-engineer, graphrag-lookup, python-coding, software-engineering, aws-core:aws-observability, aws-core:amazon-bedrock, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `sagemaker-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the code that runs models on Amazon SageMaker AI as the ml-training-designer and ml-inference-designer designs record them - training job launch and training entry scripts, model registration, inference handler scripts, and the calls that invoke real-time, serverless and asynchronous endpoints or start batch transform - writing minimum code to pass failing tests. Endpoint and other resource provisioning in CDK belongs to cdk-stack-author. | subagent-contract, validation-protocol, graphrag-lookup, python-coding, software-engineering, aws-core:aws-ai-ml, aws-core:aws-sdk-python-usage, senior-ml-engineer, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `applied-ai-services-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the code that calls the AWS pre-trained AI services as the applied-ai-services-designer design records it - Amazon Textract document extraction, Amazon Rekognition image and video analysis, and Amazon Comprehend text analysis and PII detection - with their synchronous and asynchronous paths, result paging, confidence thresholds and error handling, writing minimum code to pass failing tests. Foundation-model extraction belongs to bedrock-integration-implementer. | subagent-contract, validation-protocol, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, aws-core:aws-serverless, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `agentcore-agent-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements custom AI agent code on Amazon Bedrock AgentCore as the ai-agent-designer design records it - the Strands (or other specified framework) agent and its AgentCore Runtime entrypoint, AgentCore Memory sessions, tool wiring through AgentCore Gateway and MCP, and outbound credentials through AgentCore Identity - writing minimum code to pass failing tests. MCP servers and Gateway targets belong to mcp-server-implementer; direct model calls to bedrock-integration-implementer. | subagent-contract, validation-protocol, aws-agentic-ai, graphrag-lookup, python-coding, software-engineering, aws-agents:agents-build, aws-agents:agents-connect, aws-agents:agents-harden, aws-core:amazon-bedrock, aws-core:aws-sdk-python-usage, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `vector-search-embeddings-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements vector search and embeddings for ML features — embedding generation, index read/write, similarity queries. | subagent-contract, validation-protocol, graphrag-lookup, python-coding, software-engineering, aws-core:amazon-bedrock, aws-core:aws-sdk-python-usage, aurora-postgresql, pgvector-semantic-search, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `matching-algorithm-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements matching algorithms - scoring functions, ranking and tie-breaking, candidate filtering, score normalisation and the composition of these stages into the specified matcher - writing minimum code to pass failing tests. | subagent-contract, validation-protocol, recommendation-ranking, graphrag-lookup, python-coding, software-engineering, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `recommendation-engine-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements recommendation engine components for ML features; writes minimum code to pass failing unit tests. | subagent-contract, validation-protocol, recommendation-ranking, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `behavioral-signals-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements behavioral signal capture and feature pipelines feeding matching and recommendation models; minimum code to pass failing tests. | subagent-contract, validation-protocol, senior-data-engineer, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `mcp-server-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements MCP servers on AWS, including AgentCore Gateway-fronted deployments — tool definitions and schemas, authorization, transport config, CDK deployment wiring. | subagent-contract, validation-protocol, mcp-server-builder, aws-agentic-ai, graphrag-lookup, python-coding, software-engineering, aws-core:amazon-bedrock, aws-core:aws-cdk, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `glue-etl-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Glue ETL jobs for batch data processing; writes minimum code to pass failing data-pipeline suites. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, graphrag-lookup, python-coding, software-engineering, aws-data-analytics:ingesting-into-data-lake, aws-data-analytics:connecting-to-data-source, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `kinesis-stream-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Kinesis stream producers and consumers — record serialization, partition keys, checkpointing — writing minimum code to pass failing data-pipeline tests. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, aws-serverless-eda, graphrag-lookup, python-coding, software-engineering, aws-core:aws-messaging-and-streaming, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dynamodb-streams-cdc-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements change data capture from DynamoDB Streams; writes minimum code to pass failing data-pipeline test suites. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, dynamodb, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `s3-data-lake-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements S3 data lake layout, partitioning, and lifecycle policies; writes minimum code to pass failing data-pipeline tests. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, s3, graphrag-lookup, python-coding, software-engineering, aws-core:aws-storage, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `athena-redshift-analytics-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Athena queries and Redshift analytics models over the data lake — tables, views, SQL — writing minimum code to pass failing data-pipeline tests. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, graphrag-lookup, python-coding, software-engineering, aws-data-analytics:redshift-guide, aws-data-analytics:querying-data-lake, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `payments-integration-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Stripe payment features: checkout sessions, webhook handlers built on the chassis, subscription lifecycle, refunds, and idempotent operations, with secrets in Secrets Manager. | subagent-contract, implementer-contract, validation-protocol, stripe-integration-expert, secrets-manager, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-secrets-manager, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `email-notification-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements transactional and notification email features: responsive templates, rendering pipelines, delivery through Amazon SES, and bounce/complaint handling. | subagent-contract, implementer-contract, validation-protocol, email-template-builder, graphrag-lookup, python-coding, typescript-coding, software-engineering, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `code-quality-lead` | Code Quality | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes refactor work to specialists, verifies tests stay green after every change, and assembles the refactor evidence packet. | subagent-contract, agent-orchestration, python-lambda-packaging | Read, Glob, Grep, Agent, SendMessage |
| `complexity-analyzer` | Code Quality | Execution Team | Worker | Advisor | plan | Analyzes complexity and duplication in a green-tested change set and returns a prioritized refactor recommendation memo, with the optimizer specialties (Lambda, DynamoDB cost, front-end performance, lint fixing) the change calls for; performs no refactoring. | subagent-contract, tech-debt-tracker, python-coding, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Write, Agent |
| `code-refactoring-specialist` | Code Quality | Execution Team | Worker | Executor | execute | Refactors the code a change touched for clarity, cohesion, less complexity and less duplication without changing behavior: decides which refactorings the changed files need (none is a valid answer), applies them through GitNexus (impact before each symbol, rename for every rename, detect_changes before finishing), and keeps the test suite green or gives up so the caller restores the tree. | subagent-contract, validation-protocol, code-reviewer, graphrag-lookup, python-coding, software-engineering, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `lint-finding-fixer` | Code Quality | Execution Team | Worker | Executor | execute | Fixes the lint, format and type-check findings of a check report on a change set with the smallest style-level change, keeping tests green; never suppresses or reconfigures a rule. | subagent-contract, validation-protocol, code-reviewer, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `lambda-performance-optimizer` | Code Quality | Execution Team | Worker | Executor | execute | Applies measured Lambda performance optimizations — cold start (init work, imports, bundle size), client and connection reuse, hot paths — to Lambda code whose tests are green, and recommends memory and timeout values with evidence, without changing behavior. | subagent-contract, validation-protocol, lambda, python-coding, software-engineering, aws-core:aws-serverless, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dynamodb-cost-optimizer` | Code Quality | Execution Team | Worker | Executor | execute | Reduces the DynamoDB cost of code whose tests are green within the approved data model — scans replaced by keyed queries, batching, projections, pagination, fewer round trips — and recommends capacity-mode and index changes with a stated cost basis, without changing behavior or data semantics. | subagent-contract, validation-protocol, dynamodb, aws-cost-operations, python-coding, software-engineering, aws-core:aws-database, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `frontend-performance-optimizer` | Code Quality | Execution Team | Worker | Executor | execute | Applies measured frontend performance optimizations — bundle trimming, code splitting and lazy loading, render-path fixes, Core Web Vitals (LCP, INP, CLS) — to React and Next.js code whose tests are green, without changing behavior, accessibility or visual output. | subagent-contract, validation-protocol, senior-frontend, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `code-correctness-reviewer` | Code Quality | Execution Team | Worker | Validator | test | Independently reviews a refactor or optimisation change set for correctness regressions and behavioral drift: re-runs the test suite itself, compares contracts, error and data semantics and side effects before and after, and flags modified, weakened or skipped tests and suppressed lint rules; reports findings, never fixes. | subagent-contract, validation-protocol, code-reviewer, python-coding, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `accessibility-validator` | Code Quality | Execution Team | Worker | Validator | test | Validates UI changes against WCAG 2.2 A/AA — contrast, keyboard navigation, ARIA, focus management, screen-reader flows — reporting violations with locations and remediations; never fixes. | subagent-contract, validation-protocol, a11y-audit, senior-frontend, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `integration-testing-lead` | Integration Testing | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Read-only selector a caller invokes to choose the integration suites for a change when it cannot derive them from declared contract surfaces. Chooses the fewest applicable suites and whether provisioning must precede them, returning suites, provisionEnv and rationale. Does not dispatch workers, run tests, aggregate results, classify failures or judge gates. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent |
| `cross-repo-integration-test-coordinator` | Integration Testing | Execution Team | Worker | Orchestrator | orchestrate | Sequences cross-repo integration test runs over the event chain, aligns environment state between repos, and routes consolidated results to its caller. Coordinates only — runs no tests. | subagent-contract, agent-orchestration | Read, Glob, Grep, SendMessage, Agent |
| `test-environment-provisioner` | Integration Testing | Execution Team | Worker | Executor | execute | Provisions and resets integration test environments — the event path, functions and data stores the suites depend on — confirming readiness. | subagent-contract, validation-protocol, senior-devops, aws-mcp-setup, aws-core:aws-cdk, aurora-postgresql, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `aws-integration-test-runner` | Integration Testing | Execution Team | Worker | Validator | test | Runs AWS integration test suites against the provisioned test environment, reporting structured pass/fail, coverage, and flakiness results. | subagent-contract, validation-protocol, cumulative-regression, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `event-flow-tester` | Integration Testing | Execution Team | Worker | Validator | test | Tests event flows end-to-end through the EventBridge-SQS-Lambda chain, verifying delivery, routing, retry, and dead-letter behavior per hop. | subagent-contract, validation-protocol, aws-serverless-eda, python-coding, software-engineering, aws-core:aws-messaging-and-streaming, aws-core:aws-sdk-python-usage, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `data-consistency-checker` | Integration Testing | Execution Team | Worker | Validator | test | Verifies data consistency across services and stores after integration and event-flow runs — partial writes, orphaned records, divergent state. | subagent-contract, validation-protocol, dynamodb, aurora-postgresql, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `cross-service-contract-tester` | Integration Testing | Execution Team | Worker | Validator | test | Runs contract tests across service and repo boundaries, verifying providers and consumers honor approved API and event contracts. | subagent-contract, validation-protocol, api-test-suite-builder, graphrag-lookup, contract-testing | Read, Glob, Grep, Bash, Write, Agent |
| `flaky-test-detector` | Integration Testing | Execution Team | Worker | Validator | test | Verifies intermittent test failures via repeated controlled reruns; reports verified-flaky tests as findings only — never edits or disables tests. | subagent-contract, validation-protocol, find-cause, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `root-cause-analyst` | Integration Testing | Execution Team | Worker | Advisor | plan | Diagnoses a bug bead read-only: the reproduction, the root cause, the distinct defects behind it, the files a fix must change, the blast radius, the surfaces the fix touches, and the repository it lives in; never fixes. | subagent-contract, find-cause, test-failure-mindset, graphrag-lookup, artifact-handoff, matrix | Read, Glob, Grep, Write, Agent |
| `adversarial-review-loop-supervisor` | Adversarial Validation | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Sequences the adversarial validation loop: testers attack project code in designated test environments only; the Adversarial Critique Adjudicator rules on findings, which route back until pass or loop-limit escalation. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent, SendMessage |
| `injection-attack-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Probes this project's endpoints in designated test environments only for SQL, NoSQL, command, and template injection; reports each confirmed path with a minimal reproduction. | subagent-contract, validation-protocol, senior-secops, aurora-postgresql, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `auth-bypass-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Attempts auth bypass — token forgery, session fixation, flow skipping — against the project's auth flows in designated test environments only, reporting each confirmed bypass. | subagent-contract, validation-protocol, senior-secops, cognito, aws-core:aws-auth, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `permission-escalation-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Attempts horizontal and vertical privilege escalation against this project's own IAM and authorization model in designated test environments only, reporting each confirmed escalation with a minimal reproduction. | subagent-contract, validation-protocol, senior-secops, iam, aws-core:aws-iam, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `race-condition-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Probes this project's concurrent flows in designated test environments only for race conditions and idempotency gaps — TOCTOU, double-spend, lost updates, replay duplication — reporting each defect with a minimal reproduction. | subagent-contract, validation-protocol, senior-secops, aws-serverless-eda, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `contract-violation-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Sends contract-violating inputs — malformed payloads, type/range violations, schema mismatches — across the project's service boundaries in designated test environments only. | subagent-contract, validation-protocol, api-test-suite-builder, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `dependency-cve-auditor` | Adversarial Validation | Execution Team | Worker | Validator | test | Audits the project's Python and Node dependencies for known CVEs, scoring severity and exploitable transitive paths. | subagent-contract, validation-protocol, dependency-auditor, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `dos-resilience-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Probes load and resource-exhaustion resilience in designated test environments only, reporting where throttling, backpressure, or quotas fail; findings are competitive, not gate-stopping. | subagent-contract, validation-protocol, senior-secops, graphrag-lookup, load-testing | Read, Glob, Grep, Bash, Write, Agent |
| `data-exposure-scanner` | Adversarial Validation | Execution Team | Worker | Validator | test | Scans the project's responses, logs, and storage in designated test environments only for data exposure — leaked secrets, PII, over-returned fields, unencrypted storage — reporting each confirmed exposure. | subagent-contract, validation-protocol, senior-secops, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `infrastructure-security-scanner` | Adversarial Validation | Execution Team | Worker | Validator | test | Scans project IaC and deployed test infrastructure, designated test environments only, for public exposure, over-broad IAM, missing encryption, and open security groups, reporting each with a minimal reproduction. | subagent-contract, validation-protocol, senior-secops, aws-cdk-development, aws-core:aws-iam, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `adversarial-critique-adjudicator` | Adversarial Validation | Execution Team | Worker | Decider (Referee) | approve | Rules on each adversarial finding whether it is real, its severity, and whether it is constitutive (a hard stop) or competitive (a tradeable concern), with a rationale per finding; the referee whose rulings implementers cannot downgrade. | subagent-contract, validation-protocol, senior-security | Read, Glob, Grep, Write, Agent |
| `deployment-lead` | Deployment and Landing | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes the feature deployment sequence, validates preconditions per step, and assembles the deployment evidence packet. | subagent-contract, agent-orchestration, python-lambda-packaging | Read, Glob, Grep, Agent, SendMessage |
| `smoke-test-author` | Deployment and Landing | Execution Team | Worker | Executor (test author) | test | Writes, before the deploy, the smoke tests that verify a change's critical paths against the endpoints of a deployment, parameterized by environment variables so the deploy session can run them against AWS dev once it has deployed. Never deploys and never runs them against a deployment. | subagent-contract, validation-protocol, api-test-suite-builder, python-coding, typescript-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dev-deployer` | Deployment and Landing | Execution Team | Worker | Executor | execute | Deploys one repository to AWS dev by the mechanism the repository deploys by (cdk deploy of the affected stacks, or the repository's own deploy path such as a static-site build, S3 sync and CloudFront invalidation), then runs its smoke tests or names the one command that runs them. Never deploys to any other environment and never writes code. | subagent-contract, validation-protocol, senior-devops, aws-cdk-development, aws-core:aws-cdk, cdk-coding, python-coding, python-lambda-packaging | Read, Glob, Grep, Bash, Agent |
| `deploy-failure-fixer` | Deployment and Landing | Execution Team | Worker | Executor | execute | Diagnoses a failed package publish, cdk synth, cdk deploy to AWS dev or stack verification from its output and the CloudFormation stack events, fixes the CDK (or whatever else the deploy needs) in the Story's worktree, runs the repository's synth assertion tests, corrects a test the fix proves wrong, and names the command that runs them. Never deploys, commits or publishes. | subagent-contract, validation-protocol, cdk-coding, aws-cdk-development, aws-core:aws-cdk, aws-core:aws-cloudformation, cloudformation, python-coding, software-engineering, test-failure-mindset, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `worktree-lander` | Deployment and Landing | Execution Team | Worker | Executor | execute | Lands the work in a git worktree: commits every change through the repository's hooks (fixing every finding they report, never bypassing them), and when asked pushes the branch and opens its pull request with the project's PR command. Never pushes to the default branch and never merges. | subagent-contract, validation-protocol, software-engineering, python-coding, typescript-coding, shell-coding, python-lambda-packaging | Read, Edit, Write, Glob, Grep, Bash, Agent |
| `github-actions-pipeline-implementer` | Deployment and Landing | Execution Team | Worker | Executor | execute | Writes and changes a repository's GitHub Actions workflows: OIDC authentication to AWS with no stored credentials, dependency and build caching, and the build, test, lint and deploy jobs the repository's own commands define. A specialist a caller chooses when a repository's CI/CD workflows must be created or changed. | subagent-contract, validation-protocol, senior-devops, software-engineering, shell-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `cdk-infrastructure-drift-detector` | Deployment and Landing | Execution Team | Worker | Validator | test | Detects drift between a repository's deployed CloudFormation stacks and its CDK app (cdk diff, CloudFormation drift detection, template comparison) and reports each divergence with evidence; read-only, never remediates. A specialist a caller chooses to check deployed infrastructure against its code. | subagent-contract, validation-protocol, aws-cdk-development, cloudformation, aws-core:aws-cdk, aws-core:aws-cloudformation, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `slo-error-budget-designer` | Deployment and Landing | Execution Team | Worker | Advisor | plan | Designs a deployed service's SLOs and error budgets: SLIs from the CloudWatch metrics it emits, targets and windows traced to its NFRs, error budget policy and multi-window burn-rate CloudWatch alarms; recommends, never adopts. A specialist a caller chooses when a service needs SLOs. | subagent-contract, observability-designer, cloudwatch, aws-core:aws-observability | Read, Glob, Grep, Write, Agent |
| `finops-analyst` | Deployment and Landing | Execution Team | Worker | Advisor | plan | Models what a feature costs to run on AWS before it ships — unit economics, scaling cost curves across load scenarios, budget impact, cost cliffs — and ranks cost recommendations; decides nothing. A specialist a caller chooses for a pre-deployment cost analysis. | subagent-contract, aws-core:aws-billing-and-cost-management | Read, Glob, Grep, Write, Agent |
| `incident-response-runbook-designer` | Deployment and Landing | Execution Team | Worker | Executor | execute | Writes a deployed feature's operational runbooks — incident response keyed to its alarms and SLIs, rollback steps that match its deployment strategy, and disaster recovery (backup, restore, failover) for its AWS resources — with every referenced command and resource verified. A specialist a caller chooses when a feature needs runbooks. | subagent-contract, validation-protocol, senior-devops, observability-designer, aws-core:aws-observability | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `production-readiness-review-facilitator` | Deployment and Landing | Execution Team | Worker | Orchestrator | orchestrate | Coordinates a production readiness review: checks the required artifacts exist (rollout result, smoke test results, drift report, SLO design, runbooks), routes each to the reviewer charged with it, and assembles the readiness packet with the reviewers' findings verbatim; never decides readiness. A coordinator a caller chooses before a production deployment. | subagent-contract, agent-orchestration | Read, Glob, Grep, SendMessage, Agent |
| `deployment-strategy-decider` | Deployment and Landing | Execution Team | Worker | Decider | approve | Decides one repository's deployment strategy (rollout mechanism such as Lambda alias traffic shifting, canary, blue-green or all-at-once; canary health criteria; rollback triggers) from analyses others produced (rollout options and risk, FinOps, SLO design, drift), with a recorded rationale; produces no analysis. A specialist a caller chooses when a rollout must be decided. | subagent-contract, validation-protocol, senior-devops, aws-core:aws-serverless, python-lambda-packaging | Read, Glob, Grep, Write, Agent |
| `documentation-lead` | Documentation | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes documentation work for shipped changes, tracks artifacts lacking current docs, and reports documentation currency. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent, SendMessage |
| `documentation-currency-auditor` | Documentation | Execution Team | Worker | Validator | test | Audits which documents a change leaves stale or missing, with cited evidence, and assigns each stale document to the documentation writer whose kind covers it (API reference, README, changelog, user guide, or internal and technical documents); names the specification files the change contradicts. Read-only. | subagent-contract, validation-protocol | Read, Glob, Grep, Bash, Write, Agent |
| `api-documentation-writer` | Documentation | Execution Team | Worker | Executor | execute | Updates the human-readable API reference documents of shipped APIs from their OpenAPI and GraphQL specifications: endpoint and operation guides, request, response and error examples, SDK snippets. Never edits a specification file. | subagent-contract, validation-protocol | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `readme-writer` | Documentation | Execution Team | Worker | Executor | execute | Writes and maintains README files — setup, usage, onboarding — derived from shipped code and pipelines. | subagent-contract, validation-protocol | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `changelog-writer` | Documentation | Execution Team | Worker | Executor | execute | Writes the changelog entries for a change before it merges, from the change and the conventional commits on its branch, in the project's changelog format, flagging breaking changes and recommending the semantic version increment. Never decides, sets or bumps a version. | subagent-contract, validation-protocol, changelog-generator | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `user-guide-writer` | Documentation | Execution Team | Worker | Executor | execute | Updates user-facing feature guides and walkthroughs, for the people who use the product, from the spec and the shipped behaviour. Not internal or technical documents, READMEs, changelogs or API reference documents. | subagent-contract, validation-protocol | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `developer-documentation-writer` | Documentation | Execution Team | Worker | Executor | execute | Updates a repository's internal and technical documents so they match the shipped code: developer guides, design and implementation notes, module and service documentation, configuration references and contributing guides. Not READMEs, changelogs, API reference documents, user guides or specification files. | subagent-contract, validation-protocol, software-engineering | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `documentation-accuracy-reviewer` | Documentation | Execution Team | Worker | Validator | test | Reviews the documents a documentation writer updated for a change against the behaviour the change ships, claim by claim, and reports each inaccurate claim and each uncovered behaviour with cited evidence. Read-only; never fixes. | subagent-contract, validation-protocol | Read, Glob, Grep, Bash, Write, Agent |
| `filing-clerk` | Documentation | Execution Team | Specialist | Executor | execute | The documentation filing clerk for the project's documentation vault. Hand it a fact, decision, definition, or note and it (1) searches the project's Obsidian vault — fast, from several angles — to see whether it is already documented, (2) hunts for any single-source-of-truth violation (an unmarked duplicate of something canonical), (3) if the fact is genuinely new, decides the one correct home and files it there with proper classification frontmatter, and (4) reports what it did and any conflicts for the owner to adjudicate. Use PROACTIVELY whenever the owner says things like "if we don't have it already, note that…", "file this", "document that…", "make sure it's written down somewhere", "capture this", "record that we decided…", "add … to arc42 / the glossary / the docs", or offloads a fact so the owner won't forget it. Examples: "note in arc42 somewhere that we use Amazon Bedrock AgentCore and the Strands Agents SDK for our agent" → clerk checks the SAD, files under §4 Solution Strategy if absent; "define 'aging authority' in the glossary if it isn't there" → clerk searches, adds a glossary term; "record that student verification uses SheerID" → clerk finds the right tech/spec doc and files it. | subagent-contract, obsidian:obsidian-cli, obsidian:obsidian-markdown, arc42 | Read, Write, Edit, Bash, Grep, Glob, Agent |
| `regression-impact-assessor` | Cumulative Regression Assurance | Execution Team | Worker | Advisor | plan | Maps the components a Task changes to every current requirement they can affect, across all PRDs and the repositories that consume them, and to the unit, contract, integration and nonfunctional test layers each requires — before Red as the regression scope, after Red as the final mapping to actual test IDs and JUnit-reporting run commands — retaining earlier requirements unless an accepted source supersedes them. | subagent-contract, artifact-handoff, cumulative-regression, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `regression-coverage-reviewer` | Cumulative Regression Assurance | Execution Team | Worker | Validator | test | Independently reviews a regression scope or final regression mapping against the actual requirement sources across PRDs, the changed code and the test assertions — completeness of discovered requirements and test layers, preservation of earlier requirements and tests, source-backed supersession, and, for a mapping, that the mapped tests exist, assert the obligations and are collected by the declared commands — and approves it or returns concrete findings. | subagent-contract, artifact-handoff, cumulative-regression, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `test-command-resolver` | Workflow Helpers | Standalone Specialists | Specialist | Advisor | execute | Finds the command a repository itself declares for running its whole test suite — from its AGENTS.md or CLAUDE.md, else the test task of its Taskfile — and returns it exactly as declared, or a resolution error naming the files read. Runs nothing and changes nothing. | subagent-contract | Read, Glob, Grep, Agent |
| `test-failure-parser` | Workflow Helpers | Standalone Specialists | Specialist | Executor | execute | Reads the saved output of one test-suite run and names every failure it reports — each failing test, and each test file the runner could not load — with the output line that names it and the runner's final summary, whatever the test runner. Never reruns the suite, fixes code or changes the log. | subagent-contract | Read, Agent |
| `cds-live-auditor` | Workflow Helpers | Standalone Specialists | Specialist | Validator | test | Audits the UI files a Task changed against the live Configurable Design System (cds) when no mockup or cds bundle was supplied, and rules each finding. | subagent-contract, validation-protocol, cds:apply-design-system, cds:audit-against-system, graphrag-lookup | Read, Glob, Grep, Bash, Agent |
| `cds-finding-reviewer` | Workflow Helpers | Standalone Specialists | Specialist | Validator | test | Rules on the findings a deterministic cds audit of a Task's changed UI could not rule on - each class name the supplied cds bundle's stylesheets do not name - as a violation, allowed, or a cds gap, against the bundle and the configured design system; changes no file. | subagent-contract, validation-protocol, cds:apply-design-system, cds:audit-against-system, graphrag-lookup | Read, Glob, Grep, Bash, Agent |
| `shared-capability-reviewer` | Workflow Helpers | Standalone Specialists | Specialist | Validator | test | Rules, for each definition a deterministic reuse check could not rule on, whether a function a Task added duplicates a behaviour a shared capability (a shared library, layer, chassis or service) provides to its consumers — duplicate or not-duplicate, with one sentence of reason. Reads only the named function and the provides entry; changes nothing. | subagent-contract, python-lambda-packaging | Read, Grep, Agent |
| `workflow-command-runner` | Workflow Helpers | Standalone Specialists | Specialist | Executor | execute | Executes one workflow-supplied checksum-guarded deterministic command and returns its exact compact machine receipt; never interprets or authors its payload. | artifact-handoff | Bash, Agent |
| `polyrepo-steward` | Standalone | Standalone Specialists | Specialist | Executor | execute | The fleet's caretaker and the place to ask about the project's repositories; ask it first whenever work involves more than one repository. Carries out the fleet's routine management and keeps its records true, but never authors or edits a repository's content; it says when its templates, master copies or tool need to change, and specialist agents write the changes. | subagent-contract, graphrag-lookup, polyrepo-repo, polyrepo-info, polyrepo-governance, polyrepo-beads, matrix | Bash, Read, Write, Edit, Glob, Grep, Agent |

## References

- [Agents directory](./AGENT-ROSTER.md)
