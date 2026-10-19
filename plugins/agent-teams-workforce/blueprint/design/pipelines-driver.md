# The pipelines: driver and routing

Parent: [The pipelines: overview](pipelines.md)

The driver is the process that runs every pipeline. It lives in the control repository at
`ops/sdlc-automation`: `keeper.py` keeps `supervisor.py` running, and the supervisor runs three
lanes, elaboration, build and deploy, each with its own pool of slots. Each lane reads beads,
selects the eligible work, ranks it, and dispatches one bead per free slot: an Epic to the Python
orchestrator (`orchestrator/run.py`, composite `prd-to-spec`), a Task to a headless Workflow
session running `workflows/task-to-deploy.js`, and a Story to its own Story deploy
(`storydeploy.py`, see [The pipelines: deploy](pipelines-deploy.md)). Every build and deploy
begins at the first step of the bead's step journal that is not done. Routing decides which
composite owns a bead: the driver routes with `routing.py`; a session routes one bead with
`commands/work-bead.md`, which calls `workflows/route-build.js` or
`workflows/route-elaboration.js` and dispatches nothing. Only the owner runs the driver. The
requirements are `blueprint/requirements/pipelines.md` (the three pipelines, Bugs, composites),
the vault's `docs/sdlc/sdlc.md` (the chain of documents and beads) and the owner's statements of
2026-10-19 quoted below; `orchestrator/specs/epic/driver-contract.md` describes the elaboration
boundary as built.

## Legend

| Notation | Meaning |
|---|---|
| `->>` (sequence) | a call or a dispatch: the caller starts the work |
| `-->>` (sequence) | the return of that call |
| `-)` (sequence) | an asynchronous message, or a write to a store with no reply |
| `([...])` (activity) | start or end |
| `{...?}` (activity) | a decision; each outgoing edge is labelled with its guard |
| `fork` / `join` nodes (activity) | concurrent work starts / ends |
| `[*]` (state machine) | initial or terminal state; transitions read "event [guard] / effect" |
| "arc42 (vault)", "matrix", "beads", "vault", "git / GitHub" | the stores, named the same everywhere |
| note "differs from required" | the as-built behaviour differs from the requirement named |
| "assumption" | an element neither the requirements nor the code specifies |

The owner's statements of 2026-10-19 this document draws as required:

- "I do prefer to spin up agents in headless claude sessions to do work, and then get out." and "I know a subagent can start a workflow with subagents, etc. There can be nested subagents."
- "i'm a huge fan of the contracs being deterministic in files and code, and for agents, a skill can contain both schemas and een the code to read and write and verify the schemas."
- "What I do not want is python code deciding which specialists to use, because pythin doesn't have the reasoning to make that determination." and "I also do not want a pipeline that blindly sends everything to ever agent, whether it applies or not".

## 1. The driver's processes

**Subject.** The processes and threads of the driver.
**Scope.** One owner-started run of `keeper.py`.
**Purpose.** Show who restarts whom, and where each lane hands off its work.
**Boundary.** Outside: the dashboard (`dashboard.py`), and the inside of each dispatch (section 4).
**Basis.** As built: `keeper.py` `Keeper._run_supervisors` (line 296), `_retry_decision`
(line 335), `_after_exit` (line 352); `supervisor.py` `SdlcSupervisor.run` (line 468), `_run_lane`
(line 506); `lane.py` `LaneRunner.loop` (line 358); `headless.py` `dispatch_one` (line 653).
Required: the three pipelines of `requirements/pipelines.md`; the owner's preference for
headless sessions.

```mermaid
flowchart TD
  OWN(["owner runs keeper.py"]) --> K["keeper.py<br/>launches supervisor.py as a child"]
  K --> SUP["supervisor.py<br/>control watcher plus one thread per lane"]
  SUP --> F{{"fork"}}
  F --> LE["elaboration lane<br/>--elaboration-concurrency slots"]
  F --> LB["build lane<br/>--build-concurrency slots"]
  F --> LD["deploy lane<br/>--deploy-concurrency slots"]
  LE --> OR["orchestrator/run.py prd-to-spec<br/>child process, starts bounded agent sessions"]
  LB --> HS["headless claude Workflow session<br/>task-to-deploy.js"]
  LD --> SD["storydeploy.run in the driver<br/>dispatches deploy-mechanism.js, story-deploy-fix.js, built-version.js as headless sessions"]
  LE --> J{{"join: every lane thread ended"}}
  LB --> J
  LD --> J
  J --> X{"supervisor exit code?"}
  X -->|"0"| END1(["keeper done"])
  X -->|"restart requested"| K
  X -->|"waiting, a quota pause"| PW["wait out the pause"] --> K
  X -->|"transient recorded cause"| BO["back off, doubling to a cap"] --> K
  X -->|"any other cause"| END2(["keeper stops, cause recorded, not relaunched"])
```

## 2. One turn of a lane

**Subject.** The loop each lane thread runs.
**Scope.** One lane, one turn.
**Purpose.** Show when a lane waits, selects, dispatches, and collects a finished dispatch.
**Boundary.** Outside: which beads are eligible (section 3) and what a dispatch runs (section 4).
**Basis.** As built: `lane.py` `_turn` (line 386), `_next_work` (line 490), `_launch_selected`
(line 466), `_await_after` (line 450), `_recover` (line 419), `_collect_outcome` (line 1277),
`_follow_up` (line 1347); `nextwork.py` `next_item` (line 257); `ordering.py` `rank` (line 122).

```mermaid
flowchart TD
  A(["turn starts"]) --> C["collect finished dispatches<br/>see section 5"]
  C --> L{"--max-rounds reached?"}
  L -->|"yes, none running"| E1(["lane stops"])
  L -->|"yes, some running"| A
  L -->|"no"| B{"every slot busy, or a quota hold with work running, or the lane held?"}
  B -->|"yes: wait one poll"| A
  B -->|"no"| R["bd export, fresh bead index"]
  R --> RQ{"beads readable?"}
  RQ -->|"no: wait and read again"| A
  RQ -->|"yes"| SEL["lane selection, section 3<br/>minus running, backing off, owner-held, unchanged holds"]
  SEL --> RK["rank: Epic WSJF, then item WSJF, in progress breaks ties"]
  RK --> OW{"highest-ranked item owned by a live execution?"}
  OW -->|"all owned"| W1["wait: every eligible item owned"] --> A
  OW -->|"none eligible"| W2["wait: nothing open"] --> IDLE{"idle limit reached?"}
  IDLE -->|"yes"| E2(["lane stops"])
  IDLE -->|"no"| A
  OW -->|"first unowned item"| Q{"quota held?"}
  Q -->|"yes, a probe allowed"| SUB
  Q -->|"yes, no probe"| A
  Q -->|"no"| SUB["submit to a slot, dispatch, section 4"]
  SUB --> A
```

A lane loop that raises a beads timeout restarts after a backoff, keeping in-flight work running;
any other error, or more crashes than the window allows, ends the lane, and the supervisor stops.

## 3. Selection in each lane

**Subject.** Which beads each lane may dispatch.
**Scope.** The elaboration, build and deploy lanes.
**Purpose.** Show the eligibility rules that move a bead from one pipeline to the next.
**Boundary.** Outside: ranking (section 2) and routing (section 6).
**Basis.** As built: `selection.py` `_epic_candidate` (line 264), `build_candidates` (line 321),
`select_build` (line 408), `select_deploy` (line 433), `hold_for_person` (line 233);
`elabstate.py` `candidacy`, `unmet_blockers`; `storyorder.py` `gate` (line 184), `_take_holder`,
`_group_tasks`, `startable_without_tasks` (line 116), `_deploy` (line 149); `storydeploy.wait_of`
(line 1798); `workitems.py` `find_prd` (line 326, `atw-matrix epic`). Required: the Deploy row
("A Story whose Tasks are all built"), the Build row ("A Task with its build contract, on its
Story's branch") and the Elaboration row ("A ready Epic and its PRD") of
`requirements/pipelines.md`.

```mermaid
flowchart TD
  subgraph ELAB["Elaboration lane"]
    E1["every bead of type epic, open, not excluded"] --> E2{"every tracks or blocks prerequisite is an Epic with elaboration done?"}
    E2 -->|"no"| EX1["not selected"]
    E2 -->|"yes"| E3{"elaboration_state?"}
    E3 -->|"ready"| E4
    E3 -->|"in_progress, no live owner: reclaimed"| E4["workable"]
    E3 -->|"done, in_progress owned, authoring, held"| EX2["not selected"]
    E4 --> E5{"WSJF scored and a PRD resolves through atw-matrix epic?"}
    E5 -->|"yes"| E6["one Epic per PRD, composite prd-to-spec"]
    E5 -->|"no"| EX3["not selected"]
  end
  subgraph BUILD["Build lane"]
    B1["type task or an infrastructure type, WSJF scored, unblocked in beads, not closed, no human-action label"] --> B2{"repository, Story and elaboration key recorded?"}
    B2 -->|"no"| BX1["problem reported"]
    B2 -->|"yes"| B3{"its Epic's elaboration done?"}
    B3 -->|"no"| BX2["not selected"]
    B3 -->|"yes"| B4["group by Story, one Story per repository holds the repository:<br/>the started Story, else the highest ranked"]
    B4 --> B5["the holder's unfinished Tasks first, else its open Tasks, composite task-to-deploy"]
  end
  subgraph DEPLOY["Deploy lane"]
    D1{"open Story in_progress with every Task closed, or with no Task and its Epic done?"} -->|"yes"| D2{"its journal waits: SSM parameter missing or PR not merged?"}
    D1 -->|"no"| DX1["not selected"]
    D2 -->|"yes"| DX2["not selected until the probe clears"]
    D2 -->|"no"| D3["composite story-deploy"]
  end
```

Differences from the requirements:

- The Elaboration row takes in "A ready Epic"; as built an Epic in progress with no live owner is
  also selected (reclaimed). This continues a stopped run rather than starting one, so no
  requirement is broken; it is as built only.
- The build lane builds no Task of an Epic whose elaboration is not done, and only one Story per
  repository is worked at a time. No requirement covers either rule; as built only.

## 4. Dispatch

**Subject.** What one dispatch does, by composite.
**Scope.** `LaneRunner._work_in_scope` to the returned handback.
**Purpose.** Show the three dispatch paths, what each sends, and how the step journal is written.
**Boundary.** Outside: the steps of `prd-to-spec` and `task-to-deploy` (their own documents), and
the Story deploy's steps ([The pipelines: deploy](pipelines-deploy.md)).
**Basis.** As built: `lane.py` `_work_in_scope` (line 1192), `_claim_build` (line 1113),
`_with_step_journal` (line 1230); `workitems.py` `journal_args` (line 607), `composite_args`
(line 663); `headless.py` `dispatch_one` (line 653), `_dispatch_with_recovery`,
`_dispatch_session`, `_step_journal_reader`; `orchestrated.py`; `orchestrator/run.py` `main`;
`orchestrator/specs/epic/driver-contract.md` sections 3 and 4;
`orchestrator/core/journal_lines.py` `ChangeReader.feed`;
`skills/pipeline-contracts/SKILL.md` ("Journal changes a workflow script reports", driver
surface). Required: the owner's preference for headless sessions; deterministic contracts in
files and code.

```mermaid
sequenceDiagram
  autonumber
  participant LN as Lane runner lane.py
  participant HL as headless.py dispatch_one
  participant OR as orchestrator/run.py child process
  participant SD as storydeploy.run
  participant WS as headless claude Workflow session
  box rgb(235,240,245) Stores
    participant BDS as beads
    participant JRN as step journal
    participant LED as ledger state/ledger.jsonl
  end
  alt build lane, task-to-deploy
    LN-)BDS: bd update --claim Task, Story to in_progress
    LN->>JRN: open the Task's journal with the build plan, name a run
  else deploy lane, story-deploy
    LN-)BDS: Story to in_progress
  end
  LN-)LED: dispatched, composite, reason, arguments
  LN->>HL: dispatch_one bead, composite, arguments
  alt composite prd-to-spec, runner orchestrator
    HL->>OR: arguments.json, ATW_* environment, ATW_EXECUTION_ID
    OR->>BDS: claim the Epic, elaboration_state in_progress
    OR->>JRN: run the Epic's journal steps from the first not done
    OR-)LED: phase, verdict and session events
    OR-->>HL: handback file, validated by handback_contract
  else composite story-deploy, runner driver
    HL->>SD: run the Story's journal in the driver
    SD-->>HL: handback of the step that stopped, or the closed Story
  else composite task-to-deploy, runner workflow
    HL->>WS: claude headless, Workflow scriptPath, arguments with journal path and run, denied tools, model fallback keys
    loop while the session runs
      WS-)HL: STEP-JOURNAL lines on its log
      HL->>JRN: journal_lines.ChangeReader.feed applies each change once, in order of n
    end
    WS-->>HL: workflow result or handback sentinel line
  end
  HL-->>LN: Handback
  LN-)LED: handback event
```

Differences from the requirements: none found. The composites declared in
`skills/pipeline-contracts/schemas/composites.json` each have a runner (`prd-to-spec`
orchestrator; `task-to-deploy`, `story-deploy-fix`, `deploy-mechanism`, `built-version`
workflow; `story-deploy` driver), as "Composites" in `requirements/pipelines.md` requires. The
workflow `workflows/deploy.js` is declared as no composite and nothing dispatches it.

## 5. Collecting an outcome

**Subject.** What the lane does with a finished dispatch.
**Scope.** `LaneRunner._collect_outcome` and `_collect_error`.
**Purpose.** Show how a bead's beads state changes after a run, and when it is held, backed off
or excluded.
**Boundary.** Outside: the outcome classification inside `attempts.py`.
**Basis.** As built: `lane.py` `_collect_outcome` (line 1277), `_settle_build` (line 1155),
`_unlanded` (line 1130), `_elaboration_done` (line 799), `_file_artifacts` (line 994),
`_follow_up` (line 1347), `_collect_error` (line 1295);
`orchestrator/specs/epic/driver-contract.md` section 4.

```mermaid
flowchart TD
  A(["dispatch finished"]) --> RAISE{"the dispatch raised?"}
  RAISE -->|"yes"| ERR["failure and hard failure recorded, handback event, Task released, bead excluded for this invocation"] --> Z(["done"])
  RAISE -->|"no"| BL{"build lane, task-to-deploy?"}
  BL -->|"yes"| OKQ{"ok and the Story worktree clean?"}
  OKQ -->|"yes"| CLOSE["audit metadata, bd close Task"]
  OKQ -->|"no"| REL["build_state and stop metadata, Task back to open"]
  BL -->|"no"| EDQ
  CLOSE --> EDQ
  REL --> EDQ
  EDQ{"elaboration lane and beads now say elaboration_state done?"}
  EDQ -->|"yes"| FILE["file the TRD and Spec documents in the vault, write their paths on the Epic and Stories"]
  EDQ -->|"no"| FU
  FILE --> FU{"follow-up"}
  FU -->|"refusal"| HOLD1["hold until the Epic's beads facts change"]
  FU -->|"repeats"| BACK["back off the bead"]
  FU -->|"needs a person"| HOLD2["hold for a person, owner inbox entry, Epic to authoring with awaiting-human cause"]
  FU -->|"failed"| EXC["item failure recorded, excluded for this invocation"]
  FU -->|"ok"| Z
  HOLD1 --> Z
  BACK --> Z
  HOLD2 --> Z
  EXC --> Z
```

## 6. Routing

**Subject.** Which composite owns a bead.
**Scope.** The driver's router and the plugin's two routers.
**Purpose.** Show the rules, and where the two as-built routers disagree with each other and with
the policy document.
**Boundary.** Outside: selection, which comes after routing in the driver (section 3).
**Basis.** As built: `ops/sdlc-automation/routing.py` `route` (line 431), `route_build`
(line 340), `route_elaboration` (line 400); `workflows/route-build.js`;
`workflows/route-elaboration.js`; `commands/work-bead.md`; `workflows/ROUTING.md`. Required:
"Bugs" and "What the pipelines are" in `requirements/pipelines.md` ("Every unit of work the
pipelines do is an Epic, a Story or a Task"; "both routers skip a Bug and say why").

```mermaid
flowchart TD
  A(["a bead: type, labels, parent chain"]) --> T{"type epic, story or feature, or that label on an unknown type?"}
  T -->|"yes"| RE["route_elaboration"]
  T -->|"no"| RB["route_build"]
  RE --> RE1{"kind?"}
  RE1 -->|"epic"| PS["elaborate: prd-to-spec"]
  RE1 -->|"story"| PS2["elaborate: prd-to-spec through its parent Epic"]
  RE1 -->|"feature"| FS["driver: skip, a feature needs a PRD and an Epic<br/>route-elaboration.js: elaborate, prd-to-spec"]
  RB --> RB1{"kind?"}
  RB1 -->|"bug, or a bug label"| SB["skip: awaiting triage by a person"]
  RB1 -->|"label human, route-build.js only"| SH["skip: held for a person"]
  RB1 -->|"task, or an infrastructure type or label"| TD["work: task-to-deploy, with Infra Intent for infrastructure"]
  RB1 -->|"epic, story, feature"| SE["skip: route through route-elaboration"]
  RB1 -->|"chore, docs, research, spike, anything else"| SO["skip: out of the pipeline or unclassifiable"]
```

The `work-bead` command routes one bead the same way through the plugin routers, then prints the
next step of the bead's journal with `atw-step-journal next`; it dispatches nothing. The driver
does not call the plugin routers: each holds its own copy of the rules.

Differences from the requirements, and between the as-built routers:

- A feature: `requirements/pipelines.md` names Epics, Stories and Tasks as the only units of
  work. The driver's `route_elaboration` skips a feature; `route-elaboration.js` routes it to
  `prd-to-spec`. `route-elaboration.js` differs from the requirement and from the driver.
- The `human` label: `route-build.js` skips a bead labelled `human`; the driver's `route_build`
  does not, and the build and deploy lanes drop such beads at selection instead
  (`selection.hold_for_person`). The outcome matches; the rule lives in two places.
- `ROUTING.md` describes rules the routers do not implement: a `spec-ready` / `implementation`
  label rule (its rule 3), `task` among the skipped types (its rule 5), and an
  `ambiguity-detector` classification (its rule 6). Neither router has them. Both routers skip a
  Bug and say why, as required.

## 7. Bead states and how a bead moves between pipelines

### 7.1 An Epic

**Subject.** An Epic's `elaboration_state` and its beads status.
**Scope.** One Epic bead.
**Purpose.** Show who moves an Epic between states and which state makes it elaboration work.
**Boundary.** Outside: the Epic's WSJF score and edges (assessment workflows).
**Basis.** As built: `elabstate.py` (`AUTHORING`, `READY`, `IN_PROGRESS`, `DONE`, `candidacy`,
`hold_for_person`, `restore_command`); `orchestrator/specs/epic/driver-contract.md` section 2;
`depscore.py` `elaboration-start`, `elaboration-finish`; `elabmark.py`. Required: the
Elaboration row of `requirements/pipelines.md`; `sdlc.md` "The Chain" (a PRD and its Epic are
created together).

```mermaid
stateDiagram-v2
  [*] --> authoring : PRD and Epic created / no elaboration_state
  authoring --> ready : owner sets elaboration_state ready
  ready --> in_progress : prd-to-spec dispatch claims it / elaboration-start, owner token
  in_progress --> in_progress : run stopped, no live owner / reclaimed by the next dispatch
  in_progress --> authoring : run needs a person / driver hold, cause awaiting-human
  authoring --> in_progress : owner runs elabmark restore command
  in_progress --> done : journal step marks the Epic elaborated / Stories, Tasks, edges, scores written
  done --> ready : owner sets it explicitly
  done --> [*]
```

Nothing in the pipelines closes an Epic bead.

### 7.2 A Task and a Story

**Subject.** The beads status of a Task and of a Story.
**Scope.** One Task bead, one Story bead.
**Purpose.** Show which lane moves each status.
**Boundary.** Outside: the Task's build steps (its step journal, section 8).
**Basis.** As built: `lane.py` `_claim_build` (line 1113), `_settle_build` (line 1155);
`beadsio.py` `claim`, `start`, `release`, `close`; `storydeploy.py` `_close_step` (line 1508);
`supervisor.py` `_continue_unfinished` (line 743, stranded claims released at start).
Required: the Build and Deploy rows of `requirements/pipelines.md`.

```mermaid
stateDiagram-v2
  state "Task" as T {
    [*] --> t_open : written by elaboration
    t_open --> t_in_progress : build lane dispatch / bd update --claim
    t_in_progress --> t_closed : run ok [Story worktree clean] / bd close
    t_in_progress --> t_open : run failed or not landed / build_state recorded, released
    t_closed --> [*]
  }
  state "Story" as S {
    [*] --> s_open : written by elaboration
    s_open --> s_in_progress : its first Task dispatched, or a Story with no Task dispatched to deploy / bd update in_progress
    s_in_progress --> s_closed : deploy:close [PR merged, or branch holds no commit] / verified mark, bd close
    s_closed --> [*]
  }
```

### 7.3 How a bead moves between pipelines

**Subject.** The hand-offs from elaboration to build to deploy.
**Scope.** One Epic and the Stories and Tasks under it.
**Purpose.** Show the condition at each hand-off.
**Boundary.** Outside: Bugs, which no pipeline takes ("Bugs", `requirements/pipelines.md`).
**Basis.** Required: "What the pipelines are" and "Bugs" in `requirements/pipelines.md`; `sdlc.md`
"The Chain". As built: `selection.py`, `storyorder.py`, `lane.py`, `storydeploy.py`; the
verified mark per [The pipelines: deploy](pipelines-deploy.md) section 8.

```mermaid
stateDiagram-v2
  [*] --> Elaboration : Epic ready, prerequisites done, WSJF scored, PRD resolves
  Elaboration --> Build : Epic elaboration done / Stories and Tasks written, scored, ordered
  Build --> Build : next Task of the Story holding the repository [unblocked, scored]
  Build --> Deploy : every Task of the Story closed
  Deploy --> Build : Story closed / the repository's next Story may start
  Deploy --> Closed : Story merged and closed / verified mark per Story
  Closed --> [*]
  state Triage <<choice>>
  [*] --> Triage : a Bug bead
  Triage --> Elaboration : a person makes it an Epic
  Triage --> Build : a person makes it a Task
```

Differences from the requirements: the verified mark at `Closed` is per Story; the owner requires
it per Epic once all Tasks of all its Stories are built and tested (see
[The pipelines: deploy](pipelines-deploy.md), section 8.2).

## 8. A step of a step journal

**Subject.** The status of one step of a bead's step journal, for every pipeline.
**Scope.** Any step of an Epic's, Task's or Story's journal.
**Purpose.** Show the only thing that decides where a run begins.
**Boundary.** Outside: the deploy-specific waits and fix limit
([The pipelines: deploy](pipelines-deploy.md), section 9).
**Basis.** As built: `skills/pipeline-contracts/schemas/step-journal.schema.json`
(`stepStatus`, `changeOp` add, start, done, fail); `orchestrator/core/step_journal.py`
(`start_step`, `finish_step`, `fail_step`, `next_step`, `unclosed_steps`, `_settle_container`,
`_reset`); `orchestrator/core/journal_lines.py`; `skills/pipeline-contracts/SKILL.md` ("A run of
any pipeline begins at the first step of the bead's journal that is not done").

```mermaid
stateDiagram-v2
  state "step with an agent or a script" as P {
    [*] --> planned : plan, or add by a result or a workflow
    planned --> running : start [first step not done]
    running --> done : done / artifacts, steps the result adds
    running --> failed : fail / failure text
    failed --> running : start, the next dispatch runs it again from its beginning
    done --> planned : owner reset with elabmark --start-at
    failed --> planned : owner reset with elabmark --start-at
  }
  state "step that only contains child steps" as C {
    [*] --> c_planned : every child planned
    c_planned --> c_running : any child started
    c_running --> c_done : every child done
  }
```

A performed step whose child steps are all done waits for its own `done` (the driver's step for a
workflow it dispatched); `unclosed_steps` returns it first.

Differences from the requirements: none; no requirement states the journal's states. As built
only.
