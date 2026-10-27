# The TRD

Code: `orchestrator/flows/architecture.py` (the TRD author's sessions), `trd_authoring.py` (the
confirm step).

## Who writes it

`trd-author` writes the TRD at the path the context file names (`<work>/trd.md`): the
requirements not considered functional, the quality constraints and operational boundaries the
technical architecture must support. It is written, then updated, during the architecture, and the
architect reviews and approves it with the architecture, against the technical-requirement
criteria. The TRD is a source of information for the detailed design and for the build's
decisions.

1. The TRD initial write (mode `initial`) is the first step of the Architecture container, before
   the architect's step: the script writes its request from the context file
   (`architecture.md`, "The TRD initial write"). It adds the requirements already stated, many of
   them pre-written in arc42.
2. The TRD architecture update (mode `update`): once the higher-level architecture is in arc42,
   the architect has `trd-author` add the technical or architecture decisions that impact the
   detailed design, and the shared capabilities the design uses.
3. The detailed design reads the TRD; the architect has it updated in place (mode `update`) as the
   design adds technical requirements.

Every session of `trd-author` is handed the Epic's architecture pack (artifact `architecture
pack`), an index; the initial write is written from the pack and what it names alone: the PRD, the
constraints file, and the headings its reach rows name, read with `atw-matrix heading`. An update runs as its own step from the
request file its step is handed: one the architect's result requests, after the architect's
session, or the correction the confirm step plans. A `trd-author` step left running is launched
from the request file it holds. The file already at the TRD's path is kept for the session to
update. The answer's check fails, for the session's correction, when the TRD's front matter or a
citation does not resolve, or the TRD has no heading for a requirement the answer states or for
one a constraint of this TRD points at that the answer does not remove. When its answer is
accepted the step records the request, the file `TRD`, the answer, and the value `obligations
with no source`.

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
