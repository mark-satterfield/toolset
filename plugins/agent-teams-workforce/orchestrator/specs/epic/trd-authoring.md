# The TRD

Code: `orchestrator/flows/architecture.py` (the TRD author's session), `trd_authoring.py` (the
confirm step).

## Who writes it

`trd-author` writes the TRD at the request of `aws-solutions-architect`, at the path the context
file names (`<work>/trd.md`). It is drafted early and updated in place as the architecture is
settled, and it is reviewed with the architecture: `trd-validator` is among the reviewers the
criteria file selects.

The architect starts `trd-author` inside its own session and records the request file it wrote on
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
artifact `TRD`. The dispatch result reports the phase `trd` as passed once this step is done, and
the driver files the TRD in the vault at the path the dispatch argument `trdPath` names.
