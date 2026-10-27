# Architecture: the steps of the Architecture container

Code: `orchestrator/flows/prd_to_spec.py` (the open-run step), `architecture.py`,
`architecture_check.py`, `architecture_ruling.py`, `architecture_promotion.py`,
`architecture_earlier.py`, `architecture_files.py` (names, the context file and readers).

One agent, `aws-solutions-architect`, is responsible for the solution: it decides the architecture
a PRD needs, starting from the effective architecture (the effective arc42 before this Epic runs, which
is approved as of now and never complete), and reviews and approves it against the criteria of
`effective-architecture/review-standard.md`; nothing else reviews it. It always reads the PRD.
arc42 and the matrix are both input and output: a starting point that may be incomplete or wrong,
and for an Epic no earlier step has reached the matrix normally holds nothing beyond the
requirement headings synced from the PRD, which is normal. The order of operations is the owner's
(`blueprint/requirements/pipelines.md`, "Architecture, the PRD, arc42 and the matrix"): the
existing architecture is read and understood and compared to the PRD; every gap is designed and
approved; anything new or changed is updated in the matrix. The matrix never shows that the
architecture is complete, correct or good. Every conclusion it reaches,
`no-change-needed` included, goes through the check. The script starts sessions, records steps and carries results. It decides nothing
about who the architect asks, in what order or how often. Every step is one step of the Epic's
journal, and the journal alone decides where a run begins. The script names the agents of the
fixed steps by name (`aws-solutions-architect`, `trd-author`, `architecture-maintainer`,
`architecture-team-lead`, `architecture-decider`; `orchestrator/flows/architecture_files.py`). Every
other agent it starts is one the architect or the lead named; no code chooses it.

`<arch-work>` is `<work>/architecture/`.

## Open the run

Script `prd_to_spec.open_run`, the first outermost step. It fails when beads does not hold the
bead as an Epic. In one matrix change it brings the Epic's entry with its requirements
(`sync-epics --bead`) and the entries of the documents changed since the vault commit the last sync recorded (`sync-documents --paths`: committed since that commit, or uncommitted then or now; every document when there is no usable record, in `state/documents-synced.json` beside the matrix lock) up to date. It writes the context file `<arch-work>/context.json`, which
names every path of the Epic's architecture work: the PRD, the architecture root, the
architect's state and result files, the review log beside the result (`reviewLogPath`), the
TRD, and the folder for requests to helpers;
with the vault commit the document entries are synced to and the name of the matrix command. It
records the file `prd`, the value `matrix epic entry` and the file `context`, and plans, under the
Architecture container, the architecture pack, the TRD seed, the architect's step, and the index
and the check that follow it, and records each on itself, so a start at or before the open-run step
removes them and the open-run step plans them again as the lane plans them then. Those plans are also registered
as what the lane plans under the container, so a planned step whose key was renamed is replanned
to the current key when the run opens the journal.

A step that finds the context file does not satisfy the context contract (the contract changed
after the open-run step wrote it) is not failed: the open-run step and every step after it are set
back to planned, and the open-run step writes the file again (`prd-to-spec.md`, "Where a run
begins"). A helper whose saved request does not satisfy its contract does the same for the step
directly above it, which wrote the request.

Every later step of the container is handed the context file through the journal and derives no
path of its own.

## The TRD seed

Script `trd.seed` (`trd_steps.seed`), step "Seed the TRD from the constraints that bind the Epic",
after the pack and before the architect: the TRD is written as one of the very first steps, with no
session. In one matrix change it removes every constraint that points at a requirement of this
Epic's TRD (an earlier run's, `trd.epic` the Epic), and reads, for the Epic and the entries of the
pack's `reach`, each constraint with a rule (`statement`) that binds one of them
(`matrixtraverse.constraints_for`: an `appliesTo` relationship or a selector), and each constraint
of arc42 section 2 with a rule, no selector and no `appliesTo`. It writes the TRD at the context's
`trdPath`: under "Constraints that bind the Epic", one requirement per constraint, headed by the
constraint id, under a heading that names what it applies to (the reach entries its `appliesTo`
names, the selector, or the Epic as a whole), with its rule and each heading that states it as
`<path>#<heading>`; the front matter's `decisionIds` are those headings that resolve in the matrix.
Nothing of the seed is recorded in the matrix: its requirements are the matrix's own constraints.
It records the file `TRD`, the value `seeded requirements` and the value `earlier TRD constraints
removed`, and is an input of the architect's step, which is handed the TRD as `trd`.

## The architect and the agents it starts

Agent `aws-solutions-architect`, step "Decide what the architecture should be for this PRD".
Its brief (`agent-brief.schema.json`) names exactly the files its definition names: `prd`,
`trd` (the TRD at `trdPath`), `context`, `state` (its state file), and, in a later step, the
`findings` (check results), `answer` and `ruling` files that step is handed. No file
is written from the matrix for it: the architect reads the Epic live, with
`atw-matrix epic <id>`, `atw-matrix epic <id> --realizers` and `atw-matrix epic <id> --constraints`
(what each returns is defined in `blueprint/design/matrix.md`, queries Q2 and Q4, Q26 and Q5), and runs
`atw-matrix impact --id <id>` itself for an entry it means to change. The session is granted the
work folder and no folder of the architecture or of the PRDs. The architect records its own entries and links in the matrix (`atw-matrix put`, `link`)
before it writes its result. After its detailed design has determined the resources and
components, it decides the stack, and so the repository, of each element and records that
placement itself (`put stack`, `homeIn`, architecture side), leaving the repository out of a
stack whose repository does not exist yet; the `span` step names and creates that repository.
Its output is the architecture result at the path the context file names. The session's output
check validates the result against its schema, then runs `repo_scoping.story_build_problems` on the
result's `addedOrChangedElements` (the elements the design adds or changes) and on its
`unchangedWorkElements` (the existing elements the design leaves unchanged where the Epic has work),
each list on its own, since the Epic's Stories build both, and refuses a result in which both are empty: an id the matrix lacks, an entry
not on the architecture side, an event with no description, an entry built in no stack (for an
event, one none of whose producers is homed in a stack);
then it records the design in an in-memory copy of the matrix, which is never written, and compares
it with what `atw-matrix epic` returns from that copy: an entry the result names that the matrix does
not hold, a requirement the copy does not show as served by the feature the result names, a
requirement neither served by a feature nor listed under the result's `noFeature`. Each problem is
one sentence of the error the check raises, and goes to the architect as its correction (the
session's one corrective resume). The step that accepts the result then makes the write: it records
in the matrix what the result states of the Epic's features (`servedBy`, `realizedBy`,
`supportedBy`, and `covers` from each document heading that describes a feature), and fails only
when the matrix written does not hold it. It records the file `architecture result` and the values
`conclusion` and `requirements with no feature`. The output check also refuses a `requests` entry
naming an agent the `find-specialists` catalog (`skills/find-specialists/catalog.json`) does not
list.

Each entry of the result's `requests` is work the architect has an agent do outside its own
session. The accepting step writes each request beside its answer path
(`<answer stem>.request.json`) and plans, below its own step, one step per request whose answer
file is not yet a valid answer, performed by the agent the entry names and handed the request
file as the parameter `request`; then a step "Finish" of the architect whose inputs are those
steps, so it is handed each `answer`. The architect's step stays running until they are done.
A "Finish" whose result requests more work plans another "Finish" below it; the third "Finish"
in that chain that still requests work fails the step (`MAX_FINISH_GENERATIONS`), because the
architecture does not converge.

The same launch builder serves every step the architect performs: the first, its "Finish", a
correction after the mechanical check or after the lead's routing, and a competing design the lead plans.
The architect writes its result as the work goes (`architecture-result.schema.json`), and every
step keeps a result already at the result path, so a session that starts again continues from
the partial result. A step after the first updates the result file in place and continues the
architect's session: the "Finish" step continues the session of the step above it, and any other
later step continues the nearest earlier session the agent holds in the journal.

The architect starts the agents the PRD needs inside its own session, by the names it chose from
the `find-specialists` catalog, and the document maintainer. It records
each as a child step of its own step with `atw-step-journal`, with the request file it wrote, and
adds a last child step "Finish", by the protocol in `helper-steps.schema.json`. When its session
ends, the runner reads the journal again:

- every child step is done and the last is a "Finish" the architect closed in its own session: the
  runner checks the result and calls the launch's accept as if it had run "Finish" (the matrix
  links of the result, the steps its `requests` plan, the conclusion and the other artifacts), and
  records what it returns on the architect's step;
- every child step is done and the last is no done "Finish" (the session stopped after its
  helpers): the runner plans a "Finish" and launches the architect there, continuing its session;
- a helper was left running: the runner launches that agent as its own session from the request
  file the step holds, and records the request and what the agent wrote;
- "Finish" is not done: the runner launches the architect again, continuing its session.

| Helper left running | Request artifact | Output | Records |
|---|---|---|---|
| any agent the architect or the lead named (the launch builder registered for every catalog agent with no builder of its own, `journal_registry.any_agent_step`) | the step's parameter `request`, else `request` or `question` | the answer path the request names | the request, file `answer`. The repository steward places nothing: an entry the architect's result builds in no stack fails the architect's output check |
| `trd-author` (the TRD write after the check, and the `trd.confirm` correction) | `request`; for the TRD write, the request the launch builder writes | the answer path the request names; the TRD at the path the request names is kept and updated in place | the request, file `TRD`, file `answer`, value `obligations with no source`, value `constraints recorded`. The step records one `constraint` for each requirement the answer lists under `requirements` (every requirement that write added or changed), as a pointer `trd` (the Epic and the requirement id, a heading of the TRD) with no copy of its text, with `statedIn` and `appliesTo`, removes the constraint of each id the answer lists under `removed`, and records one with no `statedIn` for each `noSource` obligation; it fails when the matrix refuses one |
| `architecture-maintainer` | `write request` or `request` | the result path the request names | the request, file `what was written`, value `documents synced`. The session is granted the architecture root, where it writes; the step sets each document written that exists `in-review` in its front matter (`matrixsync.set_lifecycle`), so the check and the promotion of this run reach it, then runs `sync-documents --paths` on the documents written |

The TRD is written, then updated, during the architecture: the seed is written before the
architect starts; the architect works from it, states in its result's `trdChanges` the technical
or architecture decisions that add, change or remove a requirement, and names `trdPath` and the
changes a subject depends on in each request for detailed design; once the check passes, one
`trd-author` session completes the TRD ("The TRD write").

## Earlier work on this PRD

A journal that `orchestrator/port_journal.py` builds for an Epic with saved run data holds, under
the Architecture container, a step "Earlier work on this PRD" (`architecture_earlier.carry`). It
contains one done step per piece of that work, each holding its files as artifacts named
`earlier work: <what the file is>`, so the journal records what was done. The open-run step, which
runs first, plans the pack, the TRD seed, the architect's step, and the index and the check after
it. The architect is not handed those files: they are unapproved copies and summaries from a
pipeline that no longer runs, and the matrix and the arc42 documents are the architect's sources.
Such a step has the script `architecture.earlier_work`, which records nothing when it runs: it runs only
after the owner asks for a start at or before it.

## The review log

The architect reviews and approves its own architecture, and records that review in the Epic's
review log at the context's `reviewLogPath` (`<arch-work>/review-log.json`), to the
`log-architecture-review` skill's `schemas/review-log.schema.json`, written with its
`scripts/review_log.py`: for each AWS resource the design adds or changes, the AWS tools, MCP
server tools, skills and specialists that reviewed it and the best practices and security best
practices it follows, each with where it is stated; the Well-Architected review of the design,
one assessment per pillar; and every decision between two or more options, with the options, the
choice and the reason.

## The index

Script `architecture.index` (`orchestrator/flows/architecture_index.py`). It runs before every
check, after every document of the pass is written, outside any agent session; no agent re-indexes.
It runs the command the driver names in `$ATW_DOCS_INDEX_COMMAND` (the project's re-index of its
graph index of the architecture documents) with no arguments, and nothing when the variable is
unset. It fingerprints every file under the architecture root (path, size, modification time); when
the fingerprint equals the one the latest done index step of the journal recorded, it runs nothing
and records the value `indexed documents` again. Otherwise it runs the command once, with a timeout
of 900 seconds, writes `<arch-work>/index/<step id>/index.json` (the command, its exit status and
output, or the cause and evidence of a run that did not finish) as the file `index run`, and, when
the command exits 0, records the fingerprint as the value `indexed documents`. A failed re-index
does not fail the step: the documents stand, and the next pass re-indexes them.

## The check

Script `atw-matrix check; atw-matrix review-scope`. It follows the architect's first step, each
correction of a mechanical defect, and the lead's step for a matter the architect could not
settle. It records nothing in the matrix. It checks what code can check: the matrix file, the
Epic's entry, an answer in the architect's result for every architecture and
technical-requirement criterion, and the review log (`review_log.problems`): a missing or
malformed log, a log for another Epic, a decision without two distinct options, a choice that is
not one of them or no reason, an AWS resource the design adds or changes (an
`addedOrChangedElements` entry whose matrix entry has a `resourceType`) with no review entry, and
a design with an AWS resource and no Well-Architected review covering each pillar once. It writes
`<arch-work>/checks/<step id>/check.json` (the folder is the check step's own, so a later check
never overwrites an earlier one) and records it as the file `check result`. It then plans what
follows by rule over the matrix, the criteria file, the architect's result and the review log:

| What the check finds | What it plans |
|---|---|
| a mechanical defect | a correction step for the architect, handed the check result, an index and a new check; after 3 corrections a defect fails the step |
| no defect, the result's conclusion is `unsettled`, and no lead has run in the container | the step of `architecture-team-lead`, an index and a new check |
| otherwise, whatever the conclusion | the TRD write, then the promotion step |

With no defect it reads what is in review for the Epic, the documents the Epic reaches that are
not effective with the headings reached (`atw-matrix review-scope --epic`), and writes
`review-scope.json` (file `review scope`) and `unlinked.json` (file `links with nothing recorded
at the other end`, from `atw-matrix epic <id> --unlinked`).

It judges nothing.

## Unsettled matters

`architecture-team-lead` (`flows/architecture_ruling.py`) is started only for a result whose
conclusion is `unsettled`. It is handed the `architecture result`; it reads the specialist it
asks for an opinion from the `find-specialists` catalog. It writes its routing
(`<arch-work>/routing-<step>.json`) and adds the steps its routing calls for under its own step,
with a last child step "Finish": a correction by the architect, a specialist's opinion, a
competing design, or a ruling. A routing that rejects every matter adds no step. When nothing
remains, the lead records the value `every item is resolved`, and the check runs again. A fourth
"Finish" of the lead, each below the one before, is not launched: the step fails.

`architecture-decider` rules only where the lead sends a matter to it. It is handed one question
file and writes one ruling (`<arch-work>/ruling-<step>.json`, file `ruling`, value `stands`), and
settles each disagreement the question's evidence cites with `atw-matrix settle`. The step that
accepts the ruling reads each of those disagreements back and fails when `stands` is unset; it
records the value `disagreements settled`. A send-back is in the step journal only. A ruling that
raises an owner concern fails the step at stage `requires-human-action`, with the concerns as its
evidence.

## The TRD write

Agent `trd-author`, step "Write the TRD from the architect's decisions", planned by a check that
found no defect, before the promotion; it runs once per pass through the architecture. The launch
builder (`architecture.trd_author`, with `trd_steps.write_request`) writes the request from the
context file and the architect's result: mode `complete`, the result's `trdChanges` as `changes`
and its `sharedCapabilities`, at `<helpersFolder>/trd.request.json` with the answer beside it
(`trd.answer.json`). The session adds the requirements the PRD implies that the TRD does not
state, applies the changes and writes each shared capability the TRD does not yet state as a
`reuse` requirement. The step records what a `trd-author` step records (the table above), so the
matrix holds each requirement it added or changed before the promotion commits the matrix.

## Promotion

Script `atw-matrix sync-documents; atw-matrix commit`. It follows the TRD write after a check that found no defect.
It sets the documents of the review scope effective in their front matter, copies the review log
into the vault at `<architectureRoot>/review-logs/<epic id>.json`, mirrors the documents'
lifecycle in the matrix (`sync-documents --paths`), links the log from the Epic's matrix entry
(attribute `reviewLog`: its path in the vault and its SHA-256), removes each disagreement settled
in this run whose losing statement a maintainer step corrected, commits and pushes those
documents and the log in the vault, and commits and pushes the matrix file (`atw-matrix commit
--bead`). It writes `<arch-work>/promoted.json` and records it as the file `promoted documents`,
with the values `vault commit` and `matrix commit` when a commit was made. A document that could
not be set effective fails the step, naming each with the reason; anything else that fails ends
the step with a structured cause.

## After the container

The outermost step "TRD" (`trd.confirm`, `trd-authoring.md`) follows, then the repository span
(`repo-scoping.md`).
