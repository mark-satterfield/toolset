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

The architect starts each update inside its own session and records the request file it wrote on
the helper's step. A `trd-author` step left running when the architect's session stopped is
launched by the runner as its own session from that request file. The file already at the TRD's
path is kept for the session to update. When its answer is accepted the step records the request,
the file `TRD`, the answer, and the value `obligations with no source`.

## The confirm step

Outermost step "TRD", script `trd.confirm`, after the Architecture container. It starts no session.

1. It reads the TRD at the path the context file names.
2. It checks the document: it has YAML front matter; `decisionIds` is a list of strings; every
   entry, without its `#fragment`, names a file under the architecture root or under its `arc42`
   folder. A TRD that is missing or fails the check fails the step.
3. It records the TRD's path, relative to the project root, and the SHA-256 of its bytes in the
   Epic bead's metadata, unless the bead already holds both.
4. It records the file `TRD`, the value `TRD hash on the Epic bead`, and the value `TRD warnings`
   when `decisionIds` is empty.

The spec steps, and the first step of every Story's and Task's journal, are handed the TRD as the
artifact `TRD`. The build puts its path in the Task's build contract (`trdPath`), and the test
writers and the implementers are told to read it as a source of information for their decisions. The dispatch result reports the phase `trd` as passed once this step is done, and
the driver files the TRD in the vault at the path the dispatch argument `trdPath` names.
