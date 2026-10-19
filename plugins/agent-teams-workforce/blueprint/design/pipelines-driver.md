# The pipelines: driver

Parent: [The pipelines: overview](pipelines.md)

The driver is what runs every pipeline. The owner starts it, and only the owner: it begins where
the owner runs `keeper.py` and `supervisor.py` in the control repository's `ops/sdlc-automation`.
It takes in the beads that are ready for work and starts, for each, the pipeline that works it:
elaboration once per Epic, build once per Task, deploy once per Story. It produces no artifact of
its own; what it produces is pipeline runs that make real project progress, each done by agents in
headless Claude sessions that do the work and get out. This document draws the driver **as the
owner wants it**. The sources are the owner's messages of 2026-10-19 (quoted with their
qualifiers in Part 1 of the elaboration plan), the owner's statement "keeper is what knows to
deploy a story.", the SkillSpoke repository's root `AGENTS.md` ("Pipeline runs belong to the
owner", "Standing facts", "Code quality"), the vault's `docs/sdlc/sdlc.md`, and
[requirements/pipelines.md](../requirements/pipelines.md) where it agrees with the owner's words.
Where the owner has not said what is wanted, the step is drawn as an open question, listed at the
end with a recommendation. What each pipeline does inside is drawn in
[elaboration](pipelines-elaboration.md), [build](pipelines-build.md) and
[deploy](pipelines-deploy.md); the arc42 and matrix states in
[architecture and matrix states](pipelines-architecture-states.md).

## Legend

| Notation | Meaning |
|---|---|
| `A ->> B` (sequence) | A calls or starts B: B does work for A |
| `B -->> A` (sequence) | B returns its result to A |
| `A -) Store` (sequence) | A writes to a store; nothing is returned |
| `alt`, or a node, labelled "open - ..." | The owner has not decided this; every branch shown is an option, not a decision. The id names the entry under "Open questions" at the end |
| `opt` (sequence) | Steps that run only when the labelled condition holds |
| Q17 | A question new to these diagram documents; Q1 to Q16 are the owner's questions from the elaboration plan |
| `([...])` (activity) | Start or end |
| `{...?}` (activity) | A decision; every outgoing edge is labelled with its guard |
| "fork" / "join" nodes (activity) | Work that runs concurrently, and the point where all of it has finished |
| "merge" node (activity) | Alternative paths coming back together; no waiting |
| `[*]` and labelled transitions (state machine) | Initial or final state; the event or condition that moves the bead |
| headless session | A headless Claude session that does one piece of work and gets out |
| arc42 (vault), matrix, beads, vault, git / GitHub, AWS dev | The stores, named the same in every document |

## 1. The owner starts keeper and supervisor

**Subject:** the two programs the owner runs, and what each starts.
**Scope:** from the owner starting a run to the pipelines it starts.
**Purpose:** who starts the driver, what each program is for, and which pipeline each starts.
**Boundary:** how a bead is chosen is section 2; the inside of each pipeline is in its own
document.
**Sources:** `AGENTS.md`, "Pipeline runs belong to the owner": "Only the owner runs `keeper.py`
and `supervisor.py`; their real runs are the test of the pipeline." and "A pipeline run is long
and expensive, so a successful run must make real project progress." The owner: "keeper is what
knows to deploy a story." and "I do prefer to spin up agents in headless claude sessions to do
work, and then get out." and "There can be nested subagents."
[requirements/pipelines.md](../requirements/pipelines.md), "What the pipelines are": elaboration
runs once per Epic, build once per Task, deploy once per Story.

```mermaid
sequenceDiagram
    autonumber
    actor O as owner
    participant K as keeper.py
    participant S as supervisor.py
    participant EL as Elaboration, one Epic
    participant BU as Build, one Task
    participant DE as Deploy, one Story
    box Stores
        participant BD as beads
    end

    O->>K: runs keeper.py
    O->>S: runs supervisor.py
    Note over K,S: each runs on its own, started by the owner. Neither starts the other
    K->>BD: reads Stories
    BD-->>K: Stories whose Tasks are all built
    loop each such Story
        K->>DE: deploys the Story, in a headless session
        Note over DE: agents in headless sessions do the work and get out. There can be nested subagents
        DE-->>K: deployed and verified, or failed - section 5
    end
    alt open - Q17 - what supervisor.py starts
        S->>BD: reads ready Epics
        S->>EL: elaborates an Epic, in a headless session
        EL-->>S: Stories and Tasks written to beads
    else
        S->>BD: reads ready Tasks
        S->>BU: builds a Task, in a headless session
        BU-->>S: Task built and tested
    end
    K-->>O: what each run did, and why any stopped
    S-->>O: what each run did, and why any stopped
```

Notes on the diagram:

- Only the deploy of a Story is drawn as started by `keeper.py`, because the owner said so. No
  other program starts a deploy.
- `keeper.py` and `supervisor.py` each run on their own, started by the owner, and neither starts
  the other, because independent processes fail independently and the owner starts each.
- What `supervisor.py` starts is an open question (Q17). Both branches are
  options; the owner's words name `supervisor.py` as a program the owner runs and nothing more.
- No session and no agent runs either program, and none rehearses a run (`AGENTS.md`). A run is
  the test of the pipeline, so each run is drawn as doing real work.

## 2. Choosing a bead and routing it to its pipeline

**Subject:** how the driver picks the next bead and decides which pipeline works it.
**Scope:** one pick of one bead.
**Purpose:** which kinds of bead are pipeline work, what each needs before it is started, and the
order among the ready ones.
**Boundary:** the readiness of an Epic's PRD is decided by PRD validation
([PRD creation and PRD validation](pipelines-prd.md)).
**Sources:** [requirements/pipelines.md](../requirements/pipelines.md): "A ready Epic and its PRD",
"A Task with its build contract, on its Story's branch", "A Story whose Tasks are all built", and
"Bugs": "A Bug bead is a report that something is wrong. It is not pipeline work" and "A person
triages a Bug into an Epic, a Task, or a closure." The owner: "keeper is what knows to deploy a
story." and "Ever agent needs to have a reason to be used." `docs/sdlc/sdlc.md`: "User stories in
the SkillSpoke SDLC are recorded ONLY as Beads issues".

```mermaid
flowchart TD
    s(["A free place to start work"]) --> read["Read beads: open beads not yet worked"]
    read --> kind{"What kind of bead?"}
    kind -->|"Bug"| bug["Not pipeline work. Left for a person to triage into an Epic, a Task or a closure"]
    kind -->|"Epic"| eReady{"Has its PRD passed validation, and has validation set the Epic ready in beads?"}
    kind -->|"Task"| tReady{"Are the Tasks it depends on, by beads dependency edges, closed?"}
    kind -->|"Story"| sReady{"Are all of the Story's Tasks built?"}
    kind -->|"any other kind"| other["Not routed to a pipeline. Skipped with the reason logged, left for a person"]
    eReady -->|"no"| skip["Not started this time"]
    eReady -->|"yes"| eDeps{"Are the Epics whose architecture decisions it rests on elaborated?"}
    eDeps -->|"no"| skip
    eDeps -->|"yes"| eOrder["Taken in WSJF order among the eligible Epics"]
    eOrder --> eRun(["Elaboration of the Epic - pipelines-elaboration.md"])
    tReady -->|"no"| skip
    tReady -->|"yes"| tOrder["Taken in WSJF order among the ready Tasks"]
    tOrder --> tRun(["Build of the Task - pipelines-build.md"])
    sReady -->|"no: a Task is not built"| skip
    sReady -->|"yes"| sRun(["keeper.py deploys the Story - pipelines-deploy.md"])
    bug --> m(("merge"))
    other --> m
    skip --> m
    m --> e(["Next pick"])
```

Notes on the diagram:

- A Bug is never started by the driver. The Epic or Task a person triages it into is then
  pipeline work like any other ([requirements/pipelines.md](../requirements/pipelines.md)).
- A Story is never elaborated or built by itself: it is created with its Spec in elaboration and
  deployed once its Tasks are built (`docs/sdlc/sdlc.md`,
  [requirements/pipelines.md](../requirements/pipelines.md)).
- An Epic is ready when its PRD has passed validation and validation set it ready in beads,
  because one setter and one condition keep one source of truth.
- Architecture dependencies between Epics decide which Epics may be elaborated: an Epic waits for
  the Epics whose architecture decisions it rests on, because an Epic designed before those
  decisions would be redesigned. WSJF orders the eligible Epics, because it puts the most value per
  effort first.
- A Task is ready when the Tasks it depends on (beads dependency edges) are closed, and ready Tasks
  are taken in WSJF order, because the edges carry build order and WSJF orders what is free to run.
- A bead of any kind not routed to a pipeline is skipped with the reason logged and left for a
  person, as a Bug is, and the routing table is data that accepts new kinds, because no closed list
  of today's kinds is kept and no pipeline runs work it was not designed for.
- No pipeline is started for a bead it does not apply to. The owner: "I also do not want a
  pipeline that blindly sends everything to ever agent, whether it applies or not".

## 3. The pipelines the driver runs, and how many at once

**Subject:** the three pipelines as places the driver starts work, and the concurrency of each.
**Scope:** one run of the driver.
**Purpose:** what each pipeline runs once per, who starts it, and what the sources say of running
several at once.
**Boundary:** the inside of each pipeline is in its own document.
**Sources:** [requirements/pipelines.md](../requirements/pipelines.md), "What the pipelines are".
The owner: "keeper is what knows to deploy a story.", "we can process 20 Epics through elaboration
with out building anything." and "I need a working pipeline ... and dosn't take 2 hours to run
through a single Epic". `docs/sdlc/sdlc.md`: one Spec and one Story per repository, all beneath
the single Epic.

```mermaid
flowchart TD
    s(["The owner starts a run"]) --> fork1(("fork"))
    fork1 --> el["Elaboration - once per Epic. Started by: open - Q17"]
    fork1 --> bu["Build - once per Task, on its Story's branch. Started by: open - Q17"]
    fork1 --> de["Deploy - once per Story whose Tasks are all built. Started by keeper.py"]
    el --> elN["Epics at once: up to the number in flight the owner sets"]
    bu --> buN["Tasks at once: different repositories in parallel, one at a time per repository and Story branch"]
    de --> deN["Stories at once: different repositories in parallel, one at a time per repository"]
    elN --> elOut["Stories and Tasks in beads. Needs no build: 20 Epics can be elaborated with nothing built"]
    buN --> buOut["Task built and tested on its Story's branch"]
    deN --> deOut["Story deployed to AWS dev and verified, one merged pull request"]
    elOut --> join1(("join: the run ends"))
    buOut --> join1
    deOut --> join1
    join1 --> e(["What the run did, reported to the owner"])
```

Notes on the diagram:

- Elaboration does not wait for the build. The owner: "we can process 20 Epics through
  elaboration with out building anything."
- The owner's time goal covers one Epic: a working pipeline that "dosn't take 2 hours to run
  through a single Epic".
- Runs on different repositories go in parallel, runs on the same repository (and the same Story
  branch) run one at a time, and the number in flight is a setting the owner can change, not a
  constant, because parallel work on different files is safe and fast and one writer per branch
  avoids conflicts.

## 4. An Epic, a Story and a Task, across the pipelines

**Subject:** the states of each kind of bead as the pipelines work it.
**Scope:** from the bead's creation to its closure.
**Purpose:** which pipeline moves each bead, and which states the sources name.
**Boundary:** the matrix's approved and verified flags and the arc42 `effective` and `in-review`
states are drawn in [architecture and matrix states](pipelines-architecture-states.md); they are
states of matrix content and documents, not of beads.
**Sources:** `docs/sdlc/sdlc.md`: "A PRD and its Epic are created together", "A Spec and its Story
are created together - one Story bead per Spec, scoped to exactly one repository", and user
stories are recorded only as Beads issues. `AGENTS.md`, "Standing facts": "A Task closes when it
completes, including passing all tests. A Story or Epic is never closed because its Tasks are
closed, and an open Epic is never a condition for other work." and "History is never changed:
closed or completed issues". [requirements/pipelines.md](../requirements/pipelines.md): "A ready
Epic and its PRD", "A Story whose Tasks are all built". The owner: "keeper is what knows to deploy
a story." and "Once all of the tasks for all of the stories for and Epic have been built and
tested (including CI (CDK), which means deployemen must also work), then all of the architecture
and rellationships for the Epic can be set to verified." The matrix holds no Story and no Task
(the owner: "The matrix does not include stories and tasks (it isn't a build tracker)").

### 4.1 An Epic

```mermaid
stateDiagram-v2
    state "Open, created with its PRD" as eOpen
    state "Ready, with its PRD" as eReady
    state "Being elaborated" as eElab
    state "Elaborated - Stories and Tasks in beads" as eDone
    state "Every Task of every Story built and tested, deployment working" as eBuilt
    state "Tested and signed off by a person" as eSigned
    [*] --> eOpen: PRD creation writes the PRD and the Epic together
    eOpen --> eReady: its PRD passes validation, and validation sets it ready
    eReady --> eElab: the driver starts its elaboration
    eElab --> eDone: elaboration writes the Stories and Tasks
    eElab --> eReady: the run fails or stops - section 5
    eDone --> eBuilt: the last Story of the Epic closes
    eBuilt --> eSigned: a person tests it and signs off
    eSigned --> [*]: the driver closes the Epic
```

When the last Story of the Epic closes, a deterministic step sets all of the Epic's architecture
and relationships in the matrix verified, because the condition is factual (the owner: "Once all
of the tasks for all of the stories for and Epic have been built and tested ... then all of the
architecture and rellationships for the Epic can be set to verified."). The Epic closes only after
a person has tested it and signed off, never because its Stories closed, because closure records
proof, not counting. An open Epic is never a condition for other work: its Stories and Tasks are
worked while it is open (`AGENTS.md`).

### 4.2 A Story

```mermaid
stateDiagram-v2
    state "Open, created with its Spec, one repository" as sOpen
    state "Its Tasks being built" as sBuild
    state "Every Task built" as sReady
    state "Being deployed by keeper.py" as sDeploy
    state "Deployed to AWS dev and verified, one merged pull request" as sDone
    [*] --> sOpen: elaboration writes the Spec and the Story together
    sOpen --> sBuild: the first of its Tasks is started
    sBuild --> sReady: its last Task closes
    sReady --> sDeploy: keeper.py deploys the Story
    sDeploy --> sReady: the deploy fails or stops - section 5
    sDeploy --> sDone: the deploy is verified
    sDone --> [*]: the driver closes the Story
```

A Story closes when its pull request has merged and its deploy is verified working, and never
because its Tasks are closed (`AGENTS.md`), because closure records proof, not counting.

### 4.3 A Task

```mermaid
stateDiagram-v2
    state "Open, created under its Story with its build contract" as tOpen
    state "Ready" as tReady
    state "Being built" as tBuild
    state "Closed - built and all tests passing" as tClosed
    [*] --> tOpen: elaboration writes the Task
    tOpen --> tReady: the Tasks it depends on are closed
    tReady --> tBuild: the driver starts its build
    tBuild --> tReady: the run fails or stops - section 5
    tBuild --> tClosed: it completes, including passing all tests, and the driver closes it
    tClosed --> [*]
```

The driver writes every bead state change, deterministically from each run's result; agents write
content, not states, because a state is a fact the run's contract reports, so code sets it the same
way every time. A closed bead is never reopened or changed: history is never changed
(`AGENTS.md`).

## 5. When a pipeline run fails or stops

**Subject:** what happens to a bead's work when its run fails or is stopped.
**Scope:** one run of one pipeline for one bead.
**Purpose:** that work already done is kept and reused, that a failed run is visible to the owner,
and that the next real run makes progress.
**Boundary:** how a failed deploy is fixed inside the deploy pipeline is in
[deploy](pipelines-deploy.md); a defect a build finds is fixed in that run
([requirements/pipelines.md](../requirements/pipelines.md): "A build that finds a defect fixes it
in that run.").
**Sources:** `docs/sdlc/sdlc.md`, "Documents Are Written to Disk as They're Produced": documents
are "written to disk by the agent that produces them", and "A rerun of an Epic reuses every phase
whose recorded inputs are unchanged instead of restarting from step 1." `AGENTS.md`: "A pipeline
run is long and expensive, so a successful run must make real project progress.", "Only the owner
runs `keeper.py` and `supervisor.py`", and of the tooling: "The owner verifies it by running the
pipeline: it works or it does not, and when it does not, adapt and correct." The owner: "Your
default is fault-intolerant. I need more fault-tolerance for the pipeline, and need more trust."
and "I can't afford to constantly refact the pipelines evey 2 weeks." Values known only at deploy
time: "We don't want to stop because of that. We need to make sure some of that is accommodated
and handled at run time (deploy time)."

```mermaid
flowchart TD
    s(["A pipeline run for one bead"]) --> work["Each step records its result before the next starts"]
    work --> res{"How did the run end?"}
    res -->|"completed"| done(["The bead moves on - section 4"])
    res -->|"failed"| kindF{"Is the cause transient: a rate limit, the network, a timed-out session?"}
    res -->|"stopped: by the owner, or the machine stopped"| kept
    kindF -->|"yes"| retry["Retried with exponential backoff and jitter, up to a bounded number of attempts"]
    kindF -->|"no: a failure of the work itself"| release["Not retried. The bead is released with its cause recorded and reported to the owner"]
    retry --> again{"Did a retry complete?"}
    again -->|"yes"| done
    again -->|"no: attempts spent"| release
    release --> others["Other beads keep running"]
    others --> kept["The steps already done stay recorded"]
    kept --> fixT{"Is the cause in the pipeline tooling?"}
    fixT -->|"yes"| adapt["The tooling is adapted and corrected"]
    fixT -->|"no"| m(("merge"))
    adapt --> m
    m --> owner["The owner runs keeper.py or supervisor.py again"]
    owner --> resume["The rerun starts at the first step not done and reuses every finished step whose inputs are unchanged"]
    resume --> s
```

Notes on the diagram:

- Transient failures (rate limits, network, a timed-out session) retry with exponential backoff
  and jitter up to a bounded number of attempts; a failure of the work itself is not retried
  blindly, the bead is released with its cause recorded, and other beads keep running, because the
  AWS Well-Architected reliability guidance calls for bounded retries and one failing bead must not
  stop the rest.
- Every step of every pipeline (elaboration, build and deploy) records its result before the next
  starts, and a rerun starts at the first step not done and reuses every finished step whose inputs
  are unchanged, because a halt never forces finished work to be redone (`docs/sdlc/sdlc.md`).
- Only the owner starts the next run. No session or agent restarts `keeper.py` or `supervisor.py`
  (`AGENTS.md`).
- A value known only at deploy time, such as the region or environment, is not a failure: it is
  handled at deploy time (the owner).

## 6. Where beads and the matrix are read

**Subject:** which store the driver and the pipelines it starts read and write.
**Scope:** one run of the driver.
**Purpose:** that the driver works from beads, that the pipelines read the matrix at their steps,
and that no Story or Task is written to the matrix.
**Boundary:** each pipeline's reads and writes are drawn in its own document.
**Sources:** `docs/sdlc/sdlc.md`: Stories and Tasks live only in beads, and "Documents are handed
between agents as paths recorded on the owning Beads issue (Epic or Story), never as content."
The owner: "The matrix does not include stories and tasks (it isn't a build tracker), and it
doesn't care about what has actually been deployed.", "Regarding the matrix: It's entire purpose is
to mintain a mapping (a matrix) between things to every step of every pipeline doesn't need to
research and scan or rediscover what pertains the task that step is performing.", "arc42 is both
input and out. The matrix is both input and output." and "Once all of the tasks for all of the
stories for and Epic have been built and tested ... then all of the architecture and
rellationships for the Epic can be set to verified."

```mermaid
sequenceDiagram
    autonumber
    participant K as keeper.py
    participant S as supervisor.py
    participant EL as Elaboration
    participant BU as Build
    participant DE as Deploy
    participant V as Verified step, deterministic
    box Stores
        participant BD as beads
        participant MX as matrix
        participant A42 as arc42 (vault)
    end

    S->>BD: reads beads ready for work - Q17
    S->>MX: the Epics each ready Epic rests on
    S->>EL: an Epic, with the paths on its bead
    EL->>MX: what is known for the Epic, at every step
    EL->>A42: effective documents
    EL-)MX: the Epic's entries and relationships, then approved
    EL-)BD: Stories and Tasks, with the paths of their documents
    S->>BU: a Task
    BU->>BD: the Task and its build contract
    BU->>MX: the ids the Task states
    BU-->>S: the Task built and all tests passing
    S-)BD: the Task closed
    K->>BD: Stories whose Tasks are all built
    K->>DE: a Story
    DE->>BD: the Story and its Tasks
    DE->>MX: the stacks and resources its Tasks state
    DE-->>K: deploy verified working, pull request merged
    K-)BD: the Story closed
    opt the closed Story is the last Story of its Epic
        V-)MX: all of the Epic's architecture and relationships set verified
    end
    Note over BD,MX: no Story, no Task and nothing about what is deployed is written to the matrix
```

Notes on the diagram:

- The driver chooses work from beads. The matrix is read by the pipelines' steps, because its
  purpose is that each step does not "research and scan or rediscover what pertains the task that
  step is performing" (the owner).
- The order of Epics reads, from the matrix, the Epics each ready Epic rests on, because an Epic
  waits for the Epics whose architecture decisions it rests on (section 2).
- The driver writes each bead state from the run's result, and the pipelines write content, because
  code sets a state the same way every time (section 4).
- A deterministic step that runs when the last Story of an Epic closes sets all of the Epic's
  architecture and relationships verified, because the condition is factual.

## Open questions

- **Q17. What does `supervisor.py` start: the elaboration of Epics, the build
  of Tasks, or both?** Appears in sections 1, 3 and 6. Recommendation: `supervisor.py` starts the
  elaboration of Epics and the build of Tasks, and `keeper.py` starts the deploy of Stories. Reason:
  the owner placed deploy with `keeper.py` ("keeper is what knows to deploy a story."), every
  pipeline needs a program that starts it, and one program per kind of start keeps each with one
  responsibility.
