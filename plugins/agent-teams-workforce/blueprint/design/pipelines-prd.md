# The pipelines: PRD creation and PRD validation

Parent: [The pipelines: overview](pipelines.md)

PRD creation turns a raw stakeholder request into a PRD and the specification of the Epic bead
that is created with it; PRD validation inspects one PRD, whose Epic already exists, through seven
lenses and records in the matrix each technical rule the PRD states that no arc42 document
states. Each is one workflow script: `workflows/prd-creation.js` (phases Intake, Persona & OKR,
PRD Draft) and `workflows/prd-validation.js` (phase Validate). Neither is part of the Epic
pipeline: no step of an Epic's journal runs either one (`orchestrator/specs/epic/prd-validation.md`,
`orchestrator/specs/epic/INDEX.md` "Owner-run portfolio and PRD flows"), and an orchestrating
Claude Code session runs them (`workflows/ROUTING.md`, the driver table). Neither uses
`workflows/gate-enforce.js`. Their requirements live in the vault's `docs/sdlc/sdlc.md` (the PRD,
its Epic, where documents live and how they are handed on) and in
`blueprint/requirements/matrix.md` (the PRD-Epic pair, requirements and constraints in the
matrix); `blueprint/requirements/pipelines.md` names neither pipeline, so most of what follows is
as built only and is labelled so.

## Legend

| Notation | Meaning |
|---|---|
| `A ->> B` | A calls or dispatches B: A starts the work |
| `B -->> A` | The return of that call |
| `A -) Store` | A writes to a store, or sends a message, with no reply |
| `alt` / `opt` / `loop` / `par` | Alternative, optional, repeated and concurrent parts; each carries its condition, and each loop its exit |
| `box` | A group of participants: the run files, or a store |
| Stadium `([ ])` | Start or end of an activity |
| Diamond `{ }` | A decision; every outgoing edge carries its guard |
| "fork" / "join" | Concurrent work starts and ends |
| Cylinder `[( )]` | A store: "arc42 (vault)", "matrix", "beads", "vault", "git / GitHub", or the run's files |
| "differs from required" | A note where the code differs from the owner's written requirements |
| "assumption" | An element neither the requirements nor the code specifies |
| runner | A `workflow-command-runner` session (sonnet, effort low): the only way a workflow script runs a command or reads a file (the checked relay, `scripts/portfolio/relayrun.py`) |

Element names used throughout: the workflows `prd-creation.js` and `prd-validation.js`; the
agents `stakeholder-request-intake-writer`, `persona-profile-writer`, `okr-writer`, `prd-writer`,
`prd-alignment-verifier`, `spec-decider`, `prd-validation-analyst` and `workflow-command-runner`;
the caller (the orchestrating session that runs a workflow, `workflows/ROUTING.md`); the owner.

## 1. Where the two pipelines sit

**Subject:** the path from a stakeholder request to an Epic that elaboration may select.
**Scope:** both workflows, the caller's work between and after them, and the stores each touches.
**Purpose:** show the order of the pieces and the hand-offs between them before the detailed diagrams.
**Boundary:** elaboration (`prd-to-spec`) and the driver's selection of an Epic are outside; only the point where an Epic becomes selectable is shown.
**Basis:** as built: `workflows/prd-creation.js:815-843,1154-1171`, `workflows/prd-validation.js:673-680`,
`workflows/ROUTING.md` (driver table), `orchestrator/specs/epic/prd-validation.md`,
`ops/sdlc-automation/elabstate.py:160-210` (control repository). The caller's steps after
`prd-creation.js` returns are stated by the workflow's result (`epic`, `note`) and are not code;
the parts no source states are marked assumption.

```mermaid
flowchart TD
  S([Stakeholder request from the owner]) --> C1["caller runs prd-creation.js<br/>args request, workDir, pluginRoot, maxPasses"]
  C1 --> PC["prd-creation.js<br/>Intake, Persona and OKR, PRD Draft"]
  PC -->|writes| WD[("run files in workDir<br/>request, intake, persona, okrs,<br/>drafts, alignment, ruling")]
  PC --> R1{"result ok?"}
  R1 -->|"no: stage input, agent-dispatch-failed, prd-draft, or paused"| F1([Stops. The caller reads the files and the error])
  R1 -->|"yes: PRD aligned, or accepted by ruling"| C2["caller writes the PRD into the vault<br/>assumption: no code does it"]
  C2 -->|writes| V[("vault<br/>sdlc/mvp-1/prds/")]
  C2 --> C3["caller creates the Epic bead with bd<br/>title, description from the draft record epicScope"]
  C3 -->|writes| B[("beads<br/>Epic bead")]
  C3 --> C4["caller runs atw-matrix sync-epics<br/>--bead Epic id --prd PRD path, role script"]
  C4 -->|writes epic, requirement, hasRequirement| M[("matrix")]
  C4 --> D1{"validate the PRD?"}
  D1 -->|"yes: a person or session dispatches it"| PV["prd-validation.js<br/>args prd.path, artifacts.epicId, relay"]
  PV -->|reads find, node| M
  PV -->|"reads the heading the matrix names"| A42[("arc42 (vault)")]
  PV -->|"writes constraint, appliesTo"| M
  PV -->|writes| AD[("artifacts dir<br/>prd-validation.json")]
  PV --> R2{"verdict?"}
  R2 -->|"fail: a blocker finding, or a rule not recorded"| F2([Stops. The PRD is revised outside this diagram])
  R2 -->|pass| D2
  D1 -->|"no: nothing requires it"| D2{"the owner sets the Epic's elaboration state to ready?"}
  D2 -->|"no: state absent means PRD still being authored"| W([Epic not selectable by the driver])
  D2 -->|yes| E([Epic selectable by prd-to-spec, outside this document])
```

Differences from the requirements:

- `docs/sdlc/sdlc.md` ("The Chain"): "A PRD and its Epic are created together". As built,
  `prd-creation.js` writes neither: it returns the Epic's specification and the matrix command,
  and the caller writes the bead and runs the command (`prd-creation.js:1148-1171`). No command
  or code of the plugin performs the caller's part.
- `docs/sdlc/sdlc.md` ("Where Each Lives"): the PRD lives in `sdlc/mvp-1/prds/`. As built the
  PRD is written only to `workDir/drafts/pass-N.md`; moving it into the vault is unstated.
- `blueprint/requirements/matrix.md` R6 and section 3.1 ("Every Epic and its PRD is in the
  matrix"): as built the pair reaches the matrix only when the caller runs `sync-epics` by hand;
  until then the Epic exists in beads with no PRD in the matrix.

Assumptions: the caller writes the PRD into the vault before running `sync-epics` (that command
reads the PRD file under the vault, `scripts/portfolio/matrixsync.py:1109`).

## 2. What the owner requires of PRD creation and validation

**Subject:** the required outcome of creating and validating a PRD.
**Scope:** the PRD, its Epic, the matrix pair and how documents are handed on.
**Purpose:** give the yardstick the as-built diagrams are compared against.
**Boundary:** how the PRD is authored (agents, loops) is not required by any source and is not shown.
**Basis:** required: `docs/sdlc/sdlc.md` "The Chain", "Documents Are Written to Disk as They're
Produced", "Where Each Lives"; `blueprint/requirements/matrix.md` Q1, R3, R6, R10, R13, section 4
("Filled in and corrected"); the owner statement "i'm a huge fan of the contracs being
deterministic in files and code, and for agents, a skill can contain both schemas and een the
code to read and write and verify the schemas." No requirement covers PRD validation as a step;
the only requirement that bears on its findings is `sdlc.md` "A PRD states what: pure
requirements".

```mermaid
flowchart TD
  S([A PRD is wanted]) --> P["PRD states WHAT: pure requirements,<br/>blind to deployed state, no delta PRDs<br/>(sdlc.md, The Chain)"]
  P --> T["PRD and Epic created together:<br/>one Epic bead per PRD,<br/>its work may span repositories<br/>(sdlc.md, The Chain)"]
  T --> W1["each document written to disk by the agent that produces it,<br/>with a sibling metadata file of its hash and its inputs' hashes<br/>(sdlc.md, Documents Are Written to Disk)"]
  W1 --> W2["a rerun reuses every step whose recorded inputs are unchanged<br/>(sdlc.md)"]
  W2 --> H["documents handed between agents as paths<br/>recorded on the owning Beads issue, never as content<br/>(sdlc.md)"]
  H --> L["PRD lives in the vault at sdlc/mvp-1/prds/<br/>(sdlc.md, Where Each Lives)"]
  L --> M1["the matrix records the Epic by its beads id with its PRD,<br/>one Epic with one PRD (matrix R6, Q1)"]
  M1 --> M2["the matrix is the one location of the pair:<br/>no second record anywhere (matrix R3)"]
  M2 --> E([Epic and PRD exist as one pair])
```

## 3. The authoring step every file goes through

**Subject:** how one agent-authored file of either workflow is produced, checked and reused.
**Scope:** `author()` in `prd-creation.js` and the same calls in `prd-validation.js`
(`relayKit.artifactRevision`, `relayKit.authorArtifact`, `relayKit.acceptArtifact`).
**Purpose:** the main sequences below show this step as one line; this diagram is what that line does.
**Boundary:** what each maker writes is in sections 4, 5 and 8.
**Basis:** as built: `workflows/prd-creation.js:884-893` (`author`), the relay shared block
`prd-creation.js:207-757` (`exec` 482-534, `acceptArtifact` 700-718, `authorArtifact` 719-728,
`artifactRevision` 729-745), canonical source `scripts/shared-blocks/relay.js`;
`skills/artifact-handoff/schemas/checkpoint.schema.json`. The required counterpart is `sdlc.md`
"Documents Are Written to Disk" (hash and input hashes, reuse on rerun).

```mermaid
sequenceDiagram
  autonumber
  participant WF as workflow script
  participant RN as workflow-command-runner
  participant JA as jsonartifact.py and artifactpublish.py
  participant MK as maker agent
  box rgb(235,240,250) run files
    participant IN as input files
    participant CD as candidates dir
    participant FN as accepted file
  end
  WF->>RN: run relayrun.py, jsonartifact.py --source each input file
  RN->>JA: the command, checked by --argv-sha256
  JA->>IN: read and fingerprint
  JA-->>RN: one RELAY64v1 line, checksummed
  RN-->>WF: exit status and the line verbatim
  Note over WF: revision = sha256 of the input receipts and the context. A failed fingerprint binds the paths alone
  WF->>RN: probe - jsonartifact.py --candidate --final --contract --revision --probe
  RN->>JA: the probe command
  JA-->>WF: receipt via the runner
  alt accepted file exists for this revision
    Note over WF: reused - no maker session starts
  else candidate blocked
    Note over WF: ARTIFACT_BLOCKED, resumable - the step returns not ok
  else pending
    WF->>MK: brief with the input paths, the candidate path, the contract def, the revision, artifactcontract.py
    MK->>IN: read the inputs by path
    MK-)CD: write the candidate and its progress file
    MK->>JA: artifactcontract.py submit - validate and seal the checkpoint
    MK-->>WF: artifactPath only, never the content
    WF->>RN: accept - jsonartifact.py --candidate --final --contract --revision --keys --counts
    RN->>JA: the accept command
    JA->>CD: validate the candidate against its contract
    JA-)FN: publish the accepted file
    JA-->>WF: receipt with the requested facts and counts
  end
  opt the copy the runner returned fails its checksum
    WF->>RN: relayrun.py read --relay file --for-argv, at most 3 attempts
    RN-->>WF: the saved result, the command never runs twice
  end
```

Differences from the requirements:

- `sdlc.md` asks for "a sibling metadata file recording its content hash and the hashes of the
  inputs it was built from". As built the binding is the revision (one hash over the input
  receipts) held in the candidate's checkpoint sidecar and the relay file, not a per-document
  metadata file beside the accepted file.

## 4. PRD creation: intake, persona and objective

**Subject:** the first two phases of `prd-creation.js`.
**Scope:** from the caller's dispatch to the persona and the objective being accepted.
**Purpose:** show who is started, what each receives and writes, and where the run stops.
**Boundary:** each "author" line is the step of section 3; the PRD Draft phase is section 5.
**Basis:** as built: `workflows/prd-creation.js:844-1016`;
`skills/artifact-handoff/schemas/prd-creation.schema.json` (`Request`, `Intake`, `Persona`,
`Okrs`); `agents/stakeholder-request-intake-writer.md`, `agents/persona-profile-writer.md`,
`agents/okr-writer.md` (each `model: sonnet`). No requirement covers these phases.

```mermaid
sequenceDiagram
  autonumber
  participant CL as caller
  participant WF as prd-creation.js
  participant RN as workflow-command-runner
  participant IW as stakeholder-request-intake-writer
  participant PW as persona-profile-writer
  participant OW as okr-writer
  box rgb(235,240,250) run files in workDir
    participant RQ as request.json
    participant IK as intake.json
    participant PS as persona.json
    participant OK as okrs.json
  end
  CL->>WF: args request with title or description, workDir, pluginRoot, maxPasses default 2
  alt no request title and no description
    WF-->>CL: ok false, stage input
  else workDir or pluginRoot not an absolute path
    WF-->>CL: ok false, stage input
  end
  Note over WF: phase Intake
  WF->>RN: relayrun.py check-file request.json against the request value
  opt the file is missing or differs
    WF->>RN: relayrun.py write-file, then check-file again
    RN-)RQ: request.json, contract Request
  end
  WF->>IW: author intake - brief names request.json and the Intake def, effort medium
  Note right of IW: reading budget - the request, at most 5 other files, no repository survey
  IW->>RQ: read
  IW-)IK: intake - scopeSummary, inScope, outOfScope, problem, audience, desiredOutcome, constraints, openQuestions
  IW-->>WF: artifactPath, then accepted with counts
  Note over WF: counts checked against 25 in and out of scope, 30 constraints, 25 open questions - logged, never trimmed
  alt intake not authored
    WF-->>CL: ok false, stage Intake or agent-dispatch-failed
  end
  Note over WF: phase Persona and OKR
  par persona
    WF->>PW: author persona - brief names intake.json and the Persona def, effort low
    PW->>IK: read
    PW-)PS: persona - name, summary, goals, frustrations, context
    PW-->>WF: artifactPath, accepted
  and objective and key results
    WF->>OW: author okrs - brief names intake.json and the Okrs def, effort low
    OW->>IK: read
    OW-)OK: okrs - objective, keyResults each metric and target
    OW-->>WF: artifactPath, accepted
  end
  alt persona or okrs not authored
    WF-->>CL: ok false, stage Persona and OKR or agent-dispatch-failed, files request and intake
  end
  Note over WF: counts checked against 15 goals, 15 frustrations, 8 key results
```

## 5. PRD creation: the draft, its check and the deadlock ruling

**Subject:** the PRD Draft phase: maker `prd-writer`, checker `prd-alignment-verifier`, decider `spec-decider`.
**Scope:** every pass of the bounded loop, the ruling, and the result returned to the caller.
**Purpose:** show the maker-checker-decider loop, its bound, its exits and what the result carries.
**Boundary:** the author lines are section 3; what the caller does with the result is section 7.
**Basis:** as built: `workflows/prd-creation.js:1017-1205`; `prd-creation.schema.json`
(`Draft`, `Alignment`, `DeadlockRuling`); `agents/prd-writer.md` (`model: opus`),
`agents/prd-alignment-verifier.md` (`model: sonnet`), `agents/spec-decider.md` "PRD deadlock
ruling" (`model: opus`); `skills/prd-writer/SKILL.md`. Required: `sdlc.md` "The Chain" for
WHAT-not-HOW and for one Epic per PRD.

```mermaid
sequenceDiagram
  autonumber
  participant CL as caller
  participant WF as prd-creation.js
  participant RN as workflow-command-runner
  participant PW as prd-writer
  participant AV as prd-alignment-verifier
  participant SD as spec-decider
  box rgb(235,240,250) run files in workDir
    participant IO as intake, persona, okrs
    participant DM as drafts pass-N.md, the PRD
    participant DJ as drafts pass-N.json, draft record
    participant AL as alignment pass-N.json
    participant RU as ruling.json
  end
  Note over WF: phase PRD Draft
  loop pass N from 1 to maxPasses, default 2 - exits on aligned, or on misaligned at the last pass or with nothing to act on
    WF->>PW: author draft N - inputs intake, persona, okrs, and from pass 2 the previous PRD and its verdict, effort medium
    PW->>IO: read
    opt pass 2 or later
      PW->>AL: read the verdict of pass N-1 and address feedback and every unsatisfied dimension
    end
    PW-)DM: the PRD in Markdown, no Epic line, at most 50 headings, P0 criteria only as given when then, at most 80
    PW-)DJ: draft record - title, epicScope
    PW-->>WF: artifactPath, accepted with title
    WF->>RN: jsonartifact.py --document pass-N.md - receipt of a non-empty text file
    alt draft or its PRD file missing
      WF-->>CL: ok false, stage PRD Draft or agent-dispatch-failed
    end
    WF->>AV: author alignment N - inputs intake, persona, okrs, draft record, PRD, effort low
    AV->>IO: read
    AV->>DM: read, never rewrite
    AV-)AL: verdict, exactly 4 dimensions intake persona okr template, feedback
    AV-->>WF: accepted with verdict, feedback, dimensions
    Note over WF: aligned only when the verdict is aligned AND no dimension is unsatisfied
    alt aligned
      Note over WF: break - the PRD of pass N is the result
    else misaligned at the last pass, or no feedback and no unsatisfied dimension
      Note over WF: deadlocked - break
    else misaligned and actionable
      Note over WF: retry - pass N+1 is handed this verdict
    end
  end
  opt deadlocked
    WF->>SD: author ruling - inputs intake, persona, okrs, the last draft record, PRD and verdict, effort high
    SD->>AL: read the objection
    SD->>IO: judge it against the same files
    SD-)RU: verdict accept or reject, rationale
    SD-->>WF: accepted with verdict
  end
  alt aligned, or ruled accept
    WF-->>CL: ok true, stage done, files, prd path, epic spec with matrixRecord, alignmentVerdict, decision, retries
  else ruled reject
    WF-->>CL: ok false, stage prd-draft
  else deadlocked and the ruling returned nothing
    WF-->>CL: ok false, stage agent-dispatch-failed, dispatchFailed
  end
  Note over WF,SD: epic spec - key E1, type epic, title, descriptionFrom the draft record epicScope, prdRef,<br/>matrixRecord - atw-matrix sync-epics with --bead and --prd placeholders, role script
```

Differences from the requirements:

- `sdlc.md` asks that documents be "handed between agents as paths recorded on the owning Beads
  issue". As built the paths are handed in each agent's brief, and nothing is recorded on a bead:
  the Epic bead does not exist yet while the workflow runs.

## 6. PRD creation: control flow and failure paths

**Subject:** every decision `prd-creation.js` takes and every result stage it can return.
**Scope:** the whole workflow, from argument checks to the returned result.
**Purpose:** show the failure paths the sequences abbreviate, including the dispatch interruption.
**Boundary:** the inside of each authoring step is section 3.
**Basis:** as built: `workflows/prd-creation.js:73-205` (bounded dispatch policy, `settleAgent`:
transient failures retried up to 3 attempts within 300 seconds of waiting; account quota or an
unavailable API interrupts and every later dispatch returns nothing), `:853-863`, `:894-899`
(`notAuthored`), `:1071-1145`, `:1174-1205`.

```mermaid
flowchart TD
  S([caller dispatches prd-creation.js]) --> A1{"request has a title or a description?"}
  A1 -->|no| X1(["ok false, stage input"])
  A1 -->|yes| A2{"workDir and pluginRoot absolute?"}
  A2 -->|no| X1
  A2 -->|yes| Q1["save request.json through the relay"]
  Q1 --> Q2{"saved?"}
  Q2 -->|no| X2(["ok false, stage Intake or agent-dispatch-failed"])
  Q2 -->|yes| I1["author intake.json<br/>stakeholder-request-intake-writer"]
  I1 --> I2{"accepted?"}
  I2 -->|no| X2
  I2 -->|yes| FK["fork"]
  FK --> P1["author persona.json<br/>persona-profile-writer"]
  FK --> O1["author okrs.json<br/>okr-writer"]
  P1 --> JN["join"]
  O1 --> JN
  JN --> P2{"both accepted?"}
  P2 -->|no| X3(["ok false, stage Persona and OKR or agent-dispatch-failed"])
  P2 -->|yes| D1["pass N = 1"]
  D1 --> D2["author draft N<br/>prd-writer"]
  D2 --> D3{"draft record accepted and PRD file non-empty?"}
  D3 -->|no| X4(["ok false, stage PRD Draft or agent-dispatch-failed"])
  D3 -->|yes| C1["author alignment N<br/>prd-alignment-verifier"]
  C1 --> C2{"accepted?"}
  C2 -->|no| X4
  C2 -->|yes| C3{"verdict aligned and no dimension unsatisfied?"}
  C3 -->|"yes: aligned"| OK1(["ok true, stage done"])
  C3 -->|no| C4{"N equals maxPasses, or nothing actionable?"}
  C4 -->|"no: retry with this verdict"| C5["N = N + 1"]
  C5 --> D2
  C4 -->|"yes: deadlocked"| R1["author ruling.json<br/>spec-decider"]
  R1 --> R2{"ruling returned?"}
  R2 -->|no| X5(["ok false, stage agent-dispatch-failed"])
  R2 -->|"yes: accept"| OK2(["ok true, stage done, accepted by ruling"])
  R2 -->|"yes: reject"| X6(["ok false, stage prd-draft"])
  INT["any dispatch: account quota exhausted or API unavailable after bounded retries"] -.->|"every later dispatch returns nothing"| X7(["ok false, paused, resumable, stage account-quota-exhausted or api-unavailable"])
```

## 7. PRD creation: the draft pass as a state machine

**Subject:** the durable state of one PRD draft across passes, as the run files record it.
**Scope:** `drafts/pass-N.*`, `alignment/pass-N.json`, `ruling.json` in one workDir.
**Purpose:** show why a rerun with the same workDir resumes: an accepted file whose inputs are
unchanged is reused, so a stopped run continues from the first file not accepted.
**Boundary:** the files of the Intake and Persona and OKR phases follow the same rule and are not drawn.
**Basis:** as built: `workflows/prd-creation.js:884-893,1071-1145`, `authorArtifact`
`prd-creation.js:719-728`.

```mermaid
stateDiagram-v2
  [*] --> Drafting : pass N starts [draft N not accepted for this revision]
  [*] --> Drafted : pass N starts [draft N accepted, inputs unchanged] / reused, no session
  Drafting --> Drafted : prd-writer submits [candidate valid] / pass-N.json and pass-N.md published
  Drafting --> Failed : prd-writer returns nothing or candidate invalid / stage PRD Draft
  Drafted --> Checking : PRD file receipt [non-empty text]
  Checking --> Aligned : verifier verdict [aligned, no dimension unsatisfied]
  Checking --> Misaligned : verifier verdict [misaligned, or aligned with an unsatisfied dimension]
  Checking --> Failed : verifier returns nothing / stage PRD Draft
  Misaligned --> Drafting : retry [N less than maxPasses and actionable] / N plus 1, verdict handed on
  Misaligned --> Ruling : deadlock [N equals maxPasses or nothing actionable]
  Ruling --> Accepted : spec-decider [accept] / ruling.json
  Ruling --> Rejected : spec-decider [reject] / ruling.json
  Ruling --> Failed : spec-decider returns nothing / agent-dispatch-failed
  Aligned --> [*] : ok true
  Accepted --> [*] : ok true
  Rejected --> [*] : ok false, stage prd-draft
  Failed --> [*] : ok false
```

## 8. After PRD creation: the Epic bead, the vault and the matrix pair

**Subject:** what turns the workflow's result into an Epic and its PRD.
**Scope:** the caller's work after `prd-creation.js` returns ok, and the PRD-to-Epic sync the
`prd-writer` skill asks for.
**Purpose:** show where beads, the vault and the matrix are written for the pair, and the
conflict between the two ways the code records it.
**Boundary:** setting the Epic's elaboration state, and elaboration, are section 11 and beyond.
**Basis:** as built: `workflows/prd-creation.js:1148-1171,1202-1203` (the caller writes the bead
and runs `epic.matrixRecord.command`); `scripts/portfolio/matrixsync.py:1-20,1109-1180`
(`sync_epics`); `agents/prd-writer.md` "The PRD and Its Epic Are One Entity";
`skills/prd-writer/SKILL.md:35-83,148`; `ops/prd-epic-sync.py:1-40` in the control repository
(the command `ATW_PRD_EPIC_SYNC` names, `ops/sdlc-automation/atw.py:40-42,69-70`). Required:
`sdlc.md` "The Chain" and "Where Each Lives"; `matrix.md` Q1, R3, R6.

```mermaid
sequenceDiagram
  autonumber
  participant CL as caller
  participant BD as bd
  participant MX as atw-matrix
  participant PES as prd-epic-sync.py
  box rgb(240,245,235) stores
    participant V as vault
    participant B as beads
    participant M as matrix
  end
  Note over CL: result ok - prd path in workDir, epic spec, matrixRecord command
  CL-)V: write the PRD to sdlc/mvp-1/prds - assumption, no code or command does it
  CL->>BD: create the Epic - type epic, title, description from the draft record epicScope
  BD-)B: Epic bead, no elaboration state
  BD-->>CL: the Epic id
  CL->>MX: sync-epics --bead Epic id --prd PRD path, ATW_MATRIX_ROLE script
  MX->>B: read the Epic through beadgraph
  MX->>V: read the PRD file, hash it, parse each heading under Requirements
  MX-)M: epic entry with PRD path and hash, one requirement entry per heading, hasRequirement from the Epic to each
  MX-->>CL: created, refreshed, requirements added, changed, removed, noPrd
  opt the prd-writer skill rule 3 and step 12 - sync the Epic half
    Note over PES: differs from required - writes a second record of the pair
    CL->>PES: --only slug --apply, through ATW_PRD_EPIC_SYNC
    PES->>V: read the PRD, write an Epic line under its title
    PES-)B: Epic title and description from the PRD, label prd slug, creates the Epic if absent
  end
```

Differences from the requirements:

- `matrix.md` R3: "No second record of them is kept anywhere". `ops/prd-epic-sync.py` records
  the pair on both sides, an `**Epic:**` line in the PRD and a `prd:` label on the bead, and the
  `prd-writer` skill tells the writer to run it (`SKILL.md` rule 3, step 12), while
  `agents/prd-writer.md` and the same skill also say to write neither pointer.
  `matrixsync.py` `sync_epics` falls back to the `prd:` labels when no PRD is given or recorded.
- Inside `prd-creation.js` the `prd-writer` writes only to `workDir`, and the Epic does not yet
  exist, so the sync the skill asks for has no vault PRD and no Epic to act on. Which of the two
  creates the Epic bead, the caller or `prd-epic-sync.py`, is not settled by the code.
- `sdlc.md` "A PRD and its Epic are created together": the bead, the vault file and the matrix
  pair are three separate later steps of the caller, with no code that runs them together.

Assumptions: the caller writes the PRD into the vault before `sync-epics`; the slug the sync
script takes is the PRD file name without `.md` (`prd-epic-sync.py` docstring).

## 9. PRD validation: the analysis and the matrix records

**Subject:** `prd-validation.js`: one `prd-validation-analyst` session, the recording of the
analysis, and the recording of each technical rule no document states.
**Scope:** from the caller's dispatch to the verdict.
**Purpose:** show what the analyst receives and writes, where the matrix and arc42 are read, and
where the matrix is written.
**Boundary:** the authoring step is section 3; consolidation and the verdict are section 10.
**Basis:** as built: `workflows/prd-validation.js:673-908`;
`skills/artifact-handoff/schemas/prd-validation-analysis.schema.json` (`Analysis`,
`TracedAnalysis`, `RequirementClass`, `Severity`); `agents/prd-validation-analyst.md`
(`model: sonnet`); `orchestrator/specs/epic/prd-validation.md`; `blueprint/design/matrix.md`
row A2. Required: none places validation in a pipeline; `matrix.md` R10 (constraints an Epic's
design must meet are recorded) and Q13 (links with nothing at the other end) bear on the
constraints it records.

```mermaid
sequenceDiagram
  autonumber
  participant CL as caller
  participant WF as prd-validation.js
  participant RN as workflow-command-runner
  participant AN as prd-validation-analyst
  participant MX as atw-matrix
  participant RS as artifacts.script record
  box rgb(240,245,235) stores
    participant V as vault PRD, BRD, notes
    participant A as arc42 (vault)
    participant M as matrix
  end
  box rgb(235,240,250) artifacts dir
    participant CF as candidates prd-validation.json
    participant PF as prd-validation.json
  end
  CL->>WF: args prd.path, brdPath, contextPath, archPath, artifacts dir epicId script phase inputs, relay or pluginRoot
  alt artifacts incomplete or no relay runner
    WF-->>CL: ok false, stage input
  else prd.path not absolute
    WF-->>CL: ok false, stage input
  end
  WF->>RN: fingerprint the PRD, BRD, notes, archPath and artifacts inputs - the revision
  WF->>AN: author the analysis - all lenses in one pass, contract Analysis or TracedAnalysis, effort low
  Note right of AN: reading budget - the PRD, the named BRD and notes, what Lens 0 asks the matrix, and only a heading the matrix names
  AN->>V: read the PRD in full, the BRD and the notes when named
  loop each requirement the PRD states
    Note over AN: Lens 0 - classify business or technical, with a reason
    opt technical
      AN->>MX: find --kinds constraint,document --text the rule and what it governs
      MX->>M: read
      MX-->>AN: matches
      AN->>MX: node id, for each match that bears on it
      MX-->>AN: constraint statement and statedIn, or document lifecycle and headings
      opt the entry alone does not settle it
        AN->>A: read the heading the matrix names, in that document only
      end
      Note over AN: archCoverage covered or absent, archRefs
    end
  end
  Note over AN: Lenses 1 to 6 - ambiguities, completenessGaps, conflicts, constraints, boundaryFindings, clarifications. Lens 7 BRD traceability, informational only, when a BRD is named
  AN-)CF: the candidate analysis
  AN-->>WF: artifactPath
  WF->>RN: accept against the contract
  RN-)PF: prd-validation.json
  alt not accepted
    WF-->>CL: ok false, stage Validate
  end
  WF->>RN: relayrun.py run python3 artifacts.script record prd-validation.json --epic --phase --inputs
  RN->>RS: record the analysis file
  RS-->>WF: sha256, bytes
  alt record failed
    WF-->>CL: ok false, stage Validate
  end
  opt technical requirements with archCoverage absent
    WF->>RN: one checked inline Python command, ATW_MATRIX_ROLE script
    loop each absent rule that states a rule
      RN->>MX: put constraint --side architecture --name Epic and requirement and subject --statement the rule
      MX-)M: constraint entry, no statedIn
      RN->>MX: link appliesTo --from the constraint --to epic Epic id --side architecture
      MX-)M: appliesTo relationship
    end
    RN-->>WF: recorded, failures
  end
  alt any rule not recorded, or an absent rule with no statement
    WF-->>CL: ok false, stage Validate, matrixConstraints
  end
```

Differences from the requirements:

- No requirement makes PRD validation a step of any pipeline, and nothing chains it to PRD
  creation, although `agents/prd-alignment-verifier.md` says "prd-validation runs after
  prd-creation". It runs only when dispatched.
- `matrix.md` section 4 names the elaboration pipeline as what fills in the matrix and the seeding
  work as what seeds it; it names no PRD validation step as a writer. As built this workflow
  writes `constraint` entries and `appliesTo` relationships (design row A2 records this).
- `matrix.md` R13: "The content of a design stays in its arc42 document". As built the rule's
  text is held as the constraint's `statement` in the matrix, because no document states it.
  Whether that is a "short statement that identifies a thing" is not settled by the requirement.

Assumptions: the matrix already holds the entry `epic:<Epic id>` (written by `sync-epics`,
section 8) when `link appliesTo` runs; nothing in the workflow checks this before the link.

## 10. PRD validation: control flow and the verdict

**Subject:** the decisions of `prd-validation.js` and how findings become a verdict.
**Scope:** argument checks, analysis, recording, constraint recording, consolidation.
**Purpose:** show every failure path and the rule that decides pass or fail.
**Boundary:** the analyst's reading is section 9.
**Basis:** as built: `workflows/prd-validation.js:69-94` (an account-quota or API failure
interrupts with no retry), `:739-744`, `:780-800`, `:838-857`, `:859-908`;
`prd-validation-analysis.schema.json` `Severity` (`blocker`, `major`, `minor`, `info`). Required:
`sdlc.md` "A PRD states what: pure requirements".

```mermaid
flowchart TD
  S([caller dispatches prd-validation.js]) --> A1{"artifacts has dir, script, epicId, phase, and a relay runner is known?"}
  A1 -->|no| X1(["ok false, stage input"])
  A1 -->|yes| A2{"prd.path absolute?"}
  A2 -->|no| X1
  A2 -->|yes| B1["fingerprint the inputs: the revision"]
  B1 --> B2{"fingerprint ran?"}
  B2 -->|no| X2(["ok false, stage Validate"])
  B2 -->|yes| C1["author prd-validation.json<br/>prd-validation-analyst, reused when inputs are unchanged"]
  C1 --> C2{"interrupted?"}
  C2 -->|"yes: quota or API"| X3(["ok false, paused, resumable"])
  C2 -->|no| C3{"accepted against the contract?"}
  C3 -->|no| X2
  C3 -->|yes| D1["record the file with artifacts.script record"]
  D1 --> D2{"exit 0?"}
  D2 -->|no| X2
  D2 -->|yes| E1{"any technical requirement with archCoverage absent?"}
  E1 -->|no| F1
  E1 -->|yes| E2{"each of them states a rule?"}
  E2 -->|"no: that requirement is a failure"| E4
  E2 -->|yes| E3["put constraint and link appliesTo to the Epic, in one checked command"]
  E3 --> E4{"every rule recorded?"}
  E4 -->|no| X4(["ok false, stage Validate, matrixConstraints"])
  E4 -->|yes| F1["consolidate findings:<br/>each technical requirement is a major finding,<br/>then ambiguity, completeness, conflict, domain boundary at their severity,<br/>each clarification at info"]
  F1 --> F2{"any blocker finding?"}
  F2 -->|"yes: fail"| X5(["ok false, validationVerdict fail"])
  F2 -->|"no: pass"| OK(["ok true, validationVerdict pass, findings sorted by severity"])
```

Differences from the requirements:

- `sdlc.md` "A PRD states what: pure requirements". As built a technical requirement is a
  `major` finding and never fails the PRD; only a `blocker` finding does, so a PRD that states
  technical requirements passes validation.
- `prd-writer`'s charter names "Gate 1" and `phase-gate-enforcer` as the independent review of a
  PRD; neither workflow runs `gate-enforce.js` or any gate. This is a difference inside the as-built
  code; no requirement names such a gate.

## 11. The Epic between creation and elaboration

**Subject:** the states an Epic passes through from the request to being selectable by elaboration.
**Scope:** the Epic bead, its matrix entry and its elaboration state.
**Purpose:** show what each pipeline changes and what only a person changes.
**Boundary:** `in_progress` and `done`, which elaboration sets, are outside.
**Basis:** as built: `workflows/prd-creation.js:1148-1171`; `scripts/portfolio/matrixsync.py`
`sync_epics`; `workflows/prd-validation.js:814-857`; `ops/sdlc-automation/elabstate.py:59-91,160-210`
(an Epic with no elaboration state is "PRD still being authored" and is skipped until a person
sets it ready); `skills/beads-contract/schemas/bead-metadata.schema.json` `ElaborationState`
(`ready`, `in_progress`, `done`, with `""` for authoring). Required: `matrix.md` R6.

```mermaid
stateDiagram-v2
  [*] --> Requested : stakeholder request
  Requested --> Drafted : prd-creation.js ok / PRD in workDir, Epic spec returned
  Requested --> [*] : prd-creation.js not ok / nothing written outside workDir
  Drafted --> Authoring : caller creates the Epic bead with bd / no elaboration state
  Authoring --> Paired : caller runs sync-epics / matrix epic, requirements, hasRequirement
  Paired --> Validated : prd-validation.js pass / constraints with appliesTo the Epic
  Paired --> NeedsRevision : prd-validation.js fail [blocker, or rule not recorded]
  NeedsRevision --> Paired : PRD revised, sync-epics run again / requirements refreshed
  Paired --> Ready : owner sets elaboration state ready
  Validated --> Ready : owner sets elaboration state ready
  Ready --> [*] : selectable by prd-to-spec
```

Differences from the requirements:

- `matrix.md` R6 and section 3.1 require every Epic to be in the matrix with its PRD. The state
  Authoring, an Epic bead with no matrix entry, exists until the caller runs `sync-epics`.
- `scripts/portfolio/elaboration.py:15,186-191` takes an absent elaboration state as `ready`,
  while the driver's `elabstate.py` takes it as authoring and skips the Epic. This is a difference
  inside the as-built code; elaboration is outside this document.

Assumptions: "NeedsRevision" and its return are drawn because a failed validation leaves the PRD
to be revised; no code revises it or re-runs `sync-epics` after a revision.

## 12. Where the stores are read and written

**Subject:** every read and write of beads, the vault, arc42, the matrix and the run files in both pipelines.
**Scope:** `prd-creation.js`, the caller's steps after it, `prd-validation.js`.
**Purpose:** one table to check a diagram against.
**Boundary:** git / GitHub is touched by neither workflow; `sync-epics` reads the vault as a git repository (`matrixsync.py`).
**Basis:** as built, from the files cited in sections 3 to 10; required counterparts as noted there.

| Step | Store | Read or write | What | Who |
|---|---|---|---|---|
| Intake to PRD Draft | run files in `workDir` | write | `request.json`, `intake.json`, `persona.json`, `okrs.json`, `drafts/pass-N.md` and `.json`, `alignment/pass-N.json`, `ruling.json`, each candidate under `candidates/`, relay files under `relay/` | the workflow (request), each maker and checker, the runner |
| Each authoring step | run files | read | the input files, fingerprinted for the revision | `jsonartifact.py` through the runner |
| After creation | vault | write | the PRD in `sdlc/mvp-1/prds/` (assumption) | the caller |
| After creation | beads | write | the Epic bead: type epic, title, description from `epicScope` | the caller with `bd`; or `prd-epic-sync.py` (differs from required) |
| After creation | matrix | write | `epic` entry with PRD path and hash, `requirement` entries, `hasRequirement` | `atw-matrix sync-epics`, role `script`, run by the caller |
| After creation | vault | read | the PRD file | `atw-matrix sync-epics` |
| Lens 0 | matrix | read | `find --kinds constraint,document --text`, `node` | `prd-validation-analyst` |
| Lens 0 | arc42 (vault) | read | only the heading the matrix names | `prd-validation-analyst` |
| Validate | vault | read | the PRD, the BRD and the notes when named | `prd-validation-analyst` |
| Validate | artifacts dir | write | `candidates/prd-validation.json`, `prd-validation.json`, its record | the analyst, `jsonartifact.py`, `artifacts.script record` |
| Validate | matrix | write | `constraint` (architecture side, no `statedIn`), `appliesTo` to `epic:<Epic id>` | the workflow's checked command, role `script` |
| Validate | beads | none | neither workflow writes to beads (`orchestrator/specs/epic/INDEX.md`) | |
