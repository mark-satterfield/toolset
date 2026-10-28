# Architecture: the steps of the Architecture container

Code: `orchestrator/flows/prd_to_spec.py` (the open-run step), `architecture.py`,
`architecture_rounds.py`, `architecture_check.py`, `architecture_ruling.py`, `architecture_promotion.py`,
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
Architecture container, the architecture pack, the TRD seed, the architect's Analyze step, and the
index and the check that follow it, and records each on itself, so a start at or before the open-run step
removes them and the open-run step plans them again as the lane plans them then. Those plans are also registered
as what the lane plans under the container, so a planned step whose key was renamed is replanned
to the current key when the run opens the journal.

A step that finds the context file does not satisfy the context contract (the contract changed
after the open-run step wrote it) is not failed: the open-run step and every step after it are set
back to planned, and the open-run step writes the file again (`prd-to-spec.md`, "Where a run
begins"). A helper whose saved request does not satisfy its contract does the same for the step
that planned it, whose output holds the request.

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
removed`, and is an input of the architect's Analyze step, which is handed the TRD as `trd`.

## The architect and the agents the script starts for it

Agent `aws-solutions-architect`. It starts no agent and holds no session across steps: every step
it performs is a fresh session that writes one file, and the step that accepts that file plans what
follows it, among its siblings, before the index and the check (`architecture_rounds`). Its brief
(`agent-brief.schema.json`) names exactly the files its definition names: `prd`, `trd` (the TRD at
`trdPath`), `context`, `state` (its state file) and an `example` of each file the step writes
(`skills/artifact-handoff/examples/`), which it is handed instead of the 45K-character schema; and,
on a later step, the `answers digest`, each `answer`, the `findings` (check results) and each
`ruling` that step is handed. No file is written from the matrix for it: it reads the Epic's pack
and runs `atw-matrix` reads itself. The session is granted the architecture work folder and no
folder of the architecture or of the PRDs.

| Step | Planned by | Output | What its acceptance plans after it |
|---|---|---|---|
| Analyze ("Analyze the PRD against the architecture and put the questions and draft reviews to the specialists") | the open-run step | the state file, then `<arch-work>/questions.json` (`specialist-round.schema.json`): one request per specialist | one step per request whose answer is not yet a valid answer, then a Decide step (round 1), handed every answer of the round: those the steps write, and as its parameter `answered` each that was already valid |
| Decide ("Decide the architecture with the specialists' answers") | the step whose output asked a round | the architecture result at the context's `resultPath`, updated in place | a further round and a Decide (round 2) when the result's `requests` holds an unanswered request; otherwise the document writes |
| A correction ("Correct what the mechanical check found"), or a step the lead adds | the check, or the lead | the architecture result, updated in place | as for Decide |

The output check of the Analyze step validates the round and the state file, and refuses a request
naming an agent the `find-specialists` catalog (`skills/find-specialists/catalog.json`) does not
list, a request naming `trd-author` or `architecture-maintainer`, which the script starts from the
result itself, and two requests naming one agent: a round holds one request per agent, all of its
questions and draft reviews together. An agent named with the plugin's prefix is the agent of that
name (`step_journal.agent_name`). The step records the file `specialist round` and the file
`state`.

The output check of a step that writes the result validates it against its schema, then applies the
architect's change file (`matrix-changes.json`, beside the context file) to a copy of the matrix
that is never written, reporting each failed operation by its index; then it runs
`repo_scoping.story_build_problems` on the result's `addedOrChangedElements` (the elements the
design adds or changes) and on its `unchangedWorkElements` (the existing elements the design leaves
unchanged where the Epic has work), each list on its own, since the Epic's Stories build both, and
refuses a result in which both are empty: an id the matrix lacks, an entry not on the architecture
side, an event with no description, an entry built in no stack (for an event, one none of whose
producers is homed in a stack); then it records the design in that copy and compares it with what
`atw-matrix epic` returns from it: an entry the result names that the matrix does not hold, a
requirement the copy does not show as served by the feature the result names, a requirement
neither served by a feature nor listed under the result's `noFeature`. It refuses an id a fact is
`about` that the copy does not hold, a fact whose home is a folder index (`matrixsync.folder_index`:
a Markdown file outside `arc42/` whose front matter states no catalog key, which the matrix never
holds), since listing a view in its folder's index is part of filing the view and no design fact,
and the request problems the Analyze step's check refuses.
When the result asks no further round, it also checks the review log
(`architecture_check.review_log_findings`, the same check the check step makes). Each problem is
one sentence of the error the check raises, and goes back to the same session as its one
correction. The step that accepts the result then makes the write: it applies the change file in
one locked update, records in the matrix what the result states of the Epic's features
(`servedBy`, `realizedBy`, `supportedBy`, and `covers` from each heading that already describes a
feature), and fails only when the matrix written does not hold it. It records the file
`architecture result` and the values `conclusion`, `requirements with no feature` and `specialist
recommendations`.

A round: the accepting step writes each request beside its answer path
(`<answer stem>.request.json`) and plans one step per request whose answer file is not yet a valid
answer, performed by the agent the request names and handed the request file as the parameter
`request`; then a Decide step whose inputs are those steps and the accepting step's own inputs, so
it is handed every answer of the chain and any findings and rulings, with the parameter `round`.
An architect step is handed as `answer` only the answers of the specialists' steps among its
inputs (`architecture_rounds.handed_answers`); the files of `trd-author` and
`architecture-maintainer` steps have their own contracts.
The specialist steps run at the same time. The Decide step's launch writes the digest of its answers
(`<helpersFolder>/digest-<step>.json`, `answers-digest.schema.json`: each answer's sentence,
assumptions, needs, decisions and diagram homes, with the agent and the answer file's path) and
hands it as `answers digest`. A result of round 2 (`MAX_ROUNDS`) that still requests work fails the
step, because the architecture does not converge.

The document writes: a result with no unanswered request is grouped into one write request per
group of arc42 sections (`architecture_rounds.write_requests`, `SECTION_GROUPS`): `structure`
(sections 1 to 5, the detailed architecture under `detailed/`, and any other document),
`runtime` (sections 6 and 7) and `concepts` (sections 8 to 12). A fact and a diagram go to the
request of their home's group, a restatement to the request of the group of the document it is
in, and a settlement to the request of each group holding a statement that lost, with only that
group's places. Each request is written to `<helpersFolder>/write-<group>-<hash>.request.json`,
named for its content (`architecture_rounds.write_name`), its result path beside it, so a later
write of a group never replaces the files of an earlier one. A group whose request was already
written with a valid result is not written again; every other gets one `architecture-maintainer` step, handed the
request as the parameter `request`, so a pass starts at most three maintainers and each reads a
neighbouring document once for every fact of its group. The maintainer steps run at the same
time, after the step that planned them and before the index.

A maintainer's output check renders, once, each Mermaid block of the documents its result and
request name (`architecture_files.written_paths`) that the vault's last commit does not hold,
with the `architecture-diagramming` skill's `scripts/render-check.sh`, into
`<helpersFolder>/diagrams/<step id>/` (`architecture_diagrams.syntax_problems`). A block that does
not render goes back to the same session as a problem to correct. The check is of syntax only:
the maintainer renders and looks at a diagram new to the documents, and an edited diagram is not
looked at.

The same launch builder serves every step the architect performs. The architect writes its result
as the work goes, and every step keeps a result already at the result path (`fresh_output` False),
so a session that starts again continues from the partial result, and a valid file there is never
taken as the step's finished output without the session (`reuse_output` False).

| Helper step | Request artifact | Output | Records |
|---|---|---|---|
| any agent the architect's round or the lead named (the launch builder registered for every catalog agent with no builder of its own, `journal_registry.any_agent_step`) | the step's parameter `request`, else `request` or `question` | the answer path the request names | the request, file `answer`. The repository steward places nothing: an entry the architect's result builds in no stack fails the architect's output check |
| `trd-author` (the TRD write after the check, and the `trd.confirm` correction) | `request`; for the TRD write, the request the launch builder writes | the answer path the request names; the TRD at the path the request names is kept and updated in place | the request, file `TRD`, file `TRD answer`, value `obligations with no source`, value `constraints recorded`. The step records one `constraint` for each requirement the answer lists under `requirements` (every requirement that write added or changed), as a pointer `trd` (the Epic and the requirement id, a heading of the TRD) with no copy of its text, with `statedIn` and `appliesTo`, removes the constraint of each id the answer lists under `removed`, and records one with no `statedIn` for each `noSource` obligation; it fails when the matrix refuses one |
| `architecture-maintainer` | the step's parameter `request`, else `write request` or `request` | the result path the request names | the request, file `what was written`, value `documents synced`. The session is granted the architecture root, where it writes; the step sets each document written that exists `in-review` in its front matter (`matrixsync.set_lifecycle`), so the check and the promotion of this run reach it, then runs `sync-documents --paths` on the documents written; then, in one matrix change, for each fact of the request the result does not list under `notApplied`, records `describedBy` from each entry the fact is `about` to its home heading, and `covers` from that heading to each requirement an entry among them serves as a feature, with that feature as `via`; a fact whose home is a folder index (`matrixsync.folder_index`) records nothing; it fails when the matrix refuses one, or a fact's home is a document of another class the matrix does not hold |

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
runs first, plans the pack, the TRD seed, the architect's Analyze step, and the index and the
check after it. The architect is not handed those files: they are unapproved copies and summaries from a
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

Script `atw-matrix check; atw-matrix review-scope`. It follows the architect's steps and the document
writes they plan, each correction of a mechanical defect, and the lead's step for a matter the architect could not
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
It sets the documents this Epic's maintainers wrote effective in their front matter, each folder
index they listed a view in included: the value `documents synced` each maintainer step recorded
(`architecture_files.written_documents`). It copies the review log
into the vault at `<architectureRoot>/review-logs/<epic id>.json`, mirrors the documents'
lifecycle in the matrix (`sync-documents --paths`; the matrix holds no folder index), links the log from the Epic's matrix entry
(attribute `reviewLog`: its path in the vault and its SHA-256), removes each disagreement settled
in this run whose losing statement a maintainer step corrected, commits and pushes those
documents and the log in the vault (each that exists or that git tracks), and commits and pushes the matrix file (`atw-matrix commit
--bead`). It writes `<arch-work>/promoted.json` and records it as the file `promoted documents`,
with the values `vault commit` and `matrix commit` when a commit was made. A document other than
a folder index whose matrix entry does not show it effective fails the step, naming each with the reason; anything else that fails ends
the step with a structured cause.

## After the container

The outermost step "TRD" (`trd.confirm`, `trd-authoring.md`) follows, then the repository span
(`repo-scoping.md`).
