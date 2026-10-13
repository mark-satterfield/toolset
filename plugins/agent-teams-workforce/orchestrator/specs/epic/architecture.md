# Architecture: the steps of the Architecture container

Code: `orchestrator/flows/prd_to_spec.py` (the open-run step), `architecture.py`,
`architecture_check.py`, `architecture_review.py`, `architecture_promotion.py`,
`architecture_earlier.py`, `architecture_files.py` (names, the context file and readers).

One agent, `aws-solutions-architect`, establishes the architecture a PRD needs until it is ready
for review. The script starts sessions, records steps and carries results. It decides nothing
about who the architect asks, in what order or how often. Every step is one step of the Epic's
journal, and the journal alone decides where a run begins. The script names agents by the `role`
their definitions state (`solutions-architect`, `design-specialist`, `diagram-author`,
`trd-author`, `document-maintainer`, `repository-steward`, `architecture-reviewer`,
`architecture-lead`, `decider`), never by name.

`<arch-work>` is `<work>/architecture/`.

## Open the run

Script `prd_to_spec.open_run`, the first outermost step. It fails when beads does not hold the
bead as an Epic. In one matrix change it brings the Epic's PRD row, the document rows and the
Epic's expertise list up to date. It writes the context file `<arch-work>/context.json`, which
names every path of the Epic's architecture work: the PRD, the architecture root, the constraints
folder, the architect's state and result files, the TRD, and the folder for requests to helpers;
with the vault commit the document rows are synced to and the name of the matrix command. It
records the file `prd`, the value `matrix prd row` and the file `context`, and plans, under the
Architecture container, the architect's step and the check that follows it.

Every later step of the container is handed the context file through the journal and derives no
path of its own.

## The architect and the agents it starts

Agent `aws-solutions-architect`, request "Establish the state of the architecture for this PRD."
Its brief names exactly the files its definition names: `prd`, `criteria` (the criteria file),
`context`, `state` (its state file), each file of earlier work on the PRD (below), and, in a later
step, the `findings` (reviews and check results), `answer` and `ruling` files that step is handed.
Its output is the architecture result at the path the context file names. When the result is
accepted the step records the file `architecture result` and the value `conclusion`.

The same launch builder serves every step the architect performs: the first, its "Finish", a
correction after the mechanical check or after findings, and a competing design the lead plans. A
step after the first updates the result file in place and continues the architect's session: the
"Finish" step continues the session of the step above it, and any other later step continues the
nearest earlier session the agent holds in the journal.

The architect starts the agents a gap in the PRD needs inside its own session: design specialists,
diagram authors, the repository steward, the TRD author and the document maintainer. It records
each as a child step of its own step with `atw-step-journal`, with the request file it wrote, and
adds a last child step "Finish". When its session ends, the runner reads the journal again:

- every child step is done: the runner closes the architect's step;
- a helper was left running: the runner launches that agent as its own session from the request
  file the step holds, and records the request and what the agent wrote;
- "Finish" is not done: the runner launches the architect again, continuing its session.

| Helper left running | Request artifact | Output | Records |
|---|---|---|---|
| a design specialist, a diagram author, the repository steward | `request` or `question` | the answer path the request names | the request, file `answer` |
| `trd-author` | `request` | the answer path the request names; the TRD at the path the request names is kept and updated in place | the request, file `TRD`, file `answer`, value `obligations with no source` |
| `architecture-maintainer` | `write request` or `request` | the result path the request names | the request, file `what was written` |

The TRD is drafted early by `trd-author` at the architect's request and updated in place.

## Earlier work on this PRD

A journal that `orchestrator/port_journal.py` builds for an Epic with saved run data holds, under
the Architecture container, a step "Earlier work on this PRD" (`architecture_earlier.carry`). It
contains one done step per piece of that work, each holding its files as artifacts named
`earlier work: <what the file is>`. The architect's step is planned after it with those steps
among its inputs, so its brief names every such file; the architect reads them as hints. Such a
step has the script `architecture.earlier_work`, which records nothing when it runs: it runs only
after the owner asks for a start at or before it.

## The check

Script `atw-matrix check; atw-matrix unapproved`. It follows the architect's first step, each
correction of a mechanical defect, and the lead's step for a matter the architect could not
settle. It checks what code can check: the matrix file, the documents the matrix indexes, a PRD
row for the Epic, and an answer in the architect's result for every architecture and
technical-requirement criterion. It writes `<arch-work>/check-<n>.json` (`<n>` is the number of
corrections before it) and records it as the file `check result`. It then plans what follows by
rule over the matrix, the criteria file and the architect's result:

| What the check finds | What it plans |
|---|---|
| a mechanical defect | a correction step for the architect, handed the check result, and a new check; after 3 corrections a defect fails the step |
| no defect, the result's conclusion is `unsettled`, and no lead has run in the container | the step of `architecture-team-lead` and a new check |
| otherwise | one step for each reviewer the criteria file selects, and the promotion step after them |

With no defect it lists what is not approved for the Epic, marks it in review in the matrix, and
writes `<arch-work>/review-scope.json` (file `review scope`). The reviewers are selected by the
`appliesWhen` rule of each reviewer group in the criteria file: the kinds of unapproved content
(a heading, a scenario fact, a TRD requirement; the TRD of an elaboration always counts) and the
review signals the architect's result lists. Each selected reviewer gets its own narrowed scope,
`<arch-work>/review-scope.<reviewer>.json`. The step records the value
`reviewers selected by rule`. A rule that selects no reviewer fails the step.

It judges nothing.

## Review

Each reviewer is handed only the unapproved items its criteria apply to. Its brief names `prd`,
`review scope` (its own narrowed scope), `architecture result`, `criteria`, and `trd` when its
group covers the TRD's requirements. The reviewers' steps are consecutive agent steps whose inputs
are done, so their sessions run together. Each writes `<arch-work>/reviews/<reviewer>.json` and
records it as the file `review`, with the value `findings`. A finding about an item outside the
reviewer's scope is taken out of the review file and counted (value
`findings outside the scope`); the review as returned is kept beside it as `.as-returned.json`.

The first review that returns a finding, or asks for alternatives, plans one step for
`architecture-team-lead` after the last reviewer and before the promotion step. The lead is handed
the reviews that raised something as `findings`, the `architecture result`, `criteria` and the
list of design specialists (`specialists`). It writes its routing
(`<arch-work>/routing-<step>.json`) and adds the steps its routing calls for under its own step,
with a last child step "Finish": a correction by the architect with a re-check by the reviewer
that raised the finding, a specialist's opinion, a competing design, or a ruling. A re-check is a
step of the reviewer that continues the reviewer's session with the same narrowed scope. A routing
that rejects every item adds no step. When nothing remains, the lead records the value
`every item is resolved`.

`architecture-decider` rules only where the lead sends a matter to it. It is handed one question
file and writes one ruling (`<arch-work>/ruling-<step>.json`, file `ruling`, value `stands`). A
ruling that raises an owner concern fails the step at stage `requires-human-action`, with the
concerns as its evidence.

## Promotion

Script `atw-matrix approve`. It runs when no review returned a finding or asked for alternatives,
or the lead recorded that every item is resolved; anything else fails the step with a structured
cause. It marks approved what is in review for the Epic in the matrix, sets the reviewed documents
effective in the vault, commits and pushes those documents in the vault, and commits the matrix
file in its repository. It writes `<arch-work>/approved.json` and records it as the file
`approved items`, with the values `vault commit` and `matrix commit` when a commit was made. An
item in review that could not be approved fails the step, naming each with the reason.

## After the container

The outermost step "TRD" (`trd.confirm`, `trd-authoring.md`) follows, then the repository span
(`repo-scoping.md`).
