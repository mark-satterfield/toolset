# Architecture: the steps of the Architecture container

Code: `orchestrator/flows/prd_to_spec.py` (the open-run step), `architecture.py`,
`architecture_check.py`, `architecture_review.py`, `architecture_promotion.py`,
`architecture_files.py` (names, the context file and readers). Checks:
`orchestrator/checks/check_architecture_flow.py`, `check_architecture_work.py`,
`check_architecture_artifacts.py`.

One agent, `aws-solutions-architect`, establishes the architecture a PRD needs until it is ready
for review. The script starts sessions, records steps and carries results. It decides nothing
about who the architect asks, in what order or how often. Every step is one step of the Epic's
journal, and the journal alone decides where a run begins.

## Open the run

Script `prd_to_spec.open_run`, the first outermost step. In one matrix change it brings the Epic's
PRD row, the document rows and the Epic's expertise list up to date. It writes the context file
`<work>/architecture/context.json`, which names every path of the Epic's architecture work: the
PRD, the architecture root, the constraints folder, the architect's state and result files, the
TRD, and the folder for requests to helpers. It records the file `prd`, the value `matrix prd row`
and the file `context`, and plans, under the Architecture container, the architect's step and the
check that follows it.

Every later step of the container is handed the context file through the journal and derives no
path of its own.

## The architect and the agents it starts

Agent `aws-solutions-architect`. Its brief names the PRD, the criteria file, the context file and
its state file; a correction also names the findings, answers and rulings its step is handed. Its
output is the architecture result at the path the context file names; a step after the first
updates that file in place and continues the architect's session.

The architect starts the agents a gap in the PRD needs inside its own session: design specialists,
diagram authors, the repository steward, the TRD author and the document maintainer. It records
each as a child step of its own step with `atw-step-journal`, with the request file it wrote, and
adds a last child step "Finish". When its session ends, the runner reads the journal again:

- every child step is done: the runner closes the architect's step;
- a helper was left running: the runner launches that agent as its own session from the request
  file the step holds, and records the request and the answer;
- "Finish" is not done: the runner launches the architect again, continuing its session.

The TRD is drafted early by `trd-author` at the architect's request and updated in place.

## The check

Script `atw-matrix check; atw-matrix unapproved`, after every step of the architect. It runs the
matrix check and lists what is not approved for the Epic, and records the check result and the
review scope. It then plans what follows by rule over the matrix, the criteria file and the
architect's result:

| What the check finds | What it plans |
|---|---|
| a mechanical defect | a correction step for the architect, handed the check result |
| a matter the architect could not settle | the step of `architecture-team-lead` |
| otherwise | one step for each reviewer the criteria file selects, and the promotion step after them |

It judges nothing.

## Review

Each reviewer is handed only the unapproved items its criteria apply to, as its own review scope
file. The reviewers' steps are consecutive agent steps whose inputs are done, so their sessions
run together. A finding outside a reviewer's scope is dropped and counted.

The first review that returns a finding, or asks for alternatives, plans one step for
`architecture-team-lead` after the last reviewer. The lead decides what each finding needs and adds
the steps for it under its own step. `architecture-decider` rules only where the lead sends a
matter to it.
The lead records whether every item is resolved.

## Promotion

Script `atw-matrix approve`. It runs when no review returned a finding, or the lead recorded that
every item is resolved; anything else fails the step with a structured cause. It marks the
reviewed rows and headings approved in the matrix, sets the reviewed documents effective in the
vault, commits and pushes the vault when a document changed, and commits the matrix file. It
records the approved items and the vault commit.

## After the container

The outermost step "TRD" (`trd.confirm`, `trd-authoring.md`) follows, then the repository span
(`repo-scoping.md`).
