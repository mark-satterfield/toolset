# The TRD

Code: `orchestrator/flows/trd_steps.py` (the seed and the request of the TRD write),
`architecture.py` (the TRD author's sessions), `trd_authoring.py` (the confirm step).

## Who writes it

The TRD is at the path the context file names (`<work>/trd.md`): the requirements not considered
functional, the quality constraints and operational boundaries the technical architecture must
support. It is written, then updated, during the architecture, and the architect reviews and
approves its changes with the architecture, against the technical-requirement criteria. The TRD
is a source of information for the detailed design and for the build's decisions.

1. The seed (script `trd.seed`, `architecture.md`, "The TRD seed") is written before the
   architect's step, with no session: one requirement for each constraint of the matrix with a
   rule that binds the Epic or an entry of its reach, and for each constraint of arc42 section 2
   that binds every Epic, headed by its constraint id. Nothing of it is recorded in the matrix.
2. The architect works from the seed, and states in its result's `trdChanges` each technical or
   architecture decision that adds, changes or removes a requirement; the detailed design reads
   the TRD with the changes its request states.
3. The TRD write (`trd-author`, mode `complete`, `architecture.md`, "The TRD write") runs once,
   when the architecture check passes and before the promotion: it adds the requirements the PRD
   implies that the TRD does not state, applies the architect's `trdChanges` and writes each shared
   capability of the result the TRD does not yet state.

Every session of `trd-author` is handed the Epic's architecture pack (artifact `architecture
pack`), an index, and runs from a request file: the TRD write's, which its launch builder writes
from the architect's result, or the correction the confirm step plans (mode `update`). A
`trd-author` step left running is launched from the request file it holds. The file already at
the TRD's path is kept for the session to update. The answer's check fails, for the session's
correction, when the TRD's front matter or a citation does not resolve, or the TRD has no heading
for a requirement the answer states or for one a constraint of this TRD points at that the answer
does not remove. When its answer is accepted the step records one constraint for each
requirement the answer added or changed, the request, the file `TRD`, the answer, and the value
`obligations with no source`.

## The confirm step

Outermost step "TRD", script `trd.confirm`, after the Architecture container. It starts no session.

1. It reads the TRD at the path the context file names. A TRD that is missing fails the step.
2. It checks the document: its front matter satisfies `TrdDocument`; every `decisionIds` entry
   names a document and heading the matrix holds; every constraint whose `trd` pointer names this
   Epic names a requirement heading of the TRD.
3. When a check fails, the step plans under itself one `trd-author` update (step "Correct the TRD
   where its confirmation found it does not resolve"), from a request of mode `update` whose
   `changes` state each problem, and then itself again ("Confirm the TRD after its correction"),
   and records the value `TRD corrections requested`. The second confirmation plans no
   correction: a check that still fails fails the step.
4. It records the TRD's path, relative to the project root, and the SHA-256 of its bytes in the
   Epic bead's metadata, unless the bead already holds both.
5. It emits one `verdict` event (phase `trd-authoring`, label `trd.confirm`): `passed` with the
   number of citations and the digest on the Epic bead, or `correction planned` with the number
   of problems sent to the TRD author.
6. It records the file `TRD`, the value `TRD hash on the Epic bead`, and the value `TRD warnings`
   when `decisionIds` is empty.

The spec steps, and the first step of every Story's and Task's journal, are handed the TRD as the
artifact `TRD`. The build puts its path in the Task's build contract (`trdPath`), and the test
writers and the implementers are told to read it as a source of information for their decisions. The dispatch result reports the phase `trd` as passed once this step is done, and
the driver files the TRD in the vault at the path the dispatch argument `trdPath` names.
