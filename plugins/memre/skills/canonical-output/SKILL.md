---
name: canonical-output
description: Apply when writing or editing any deliverable that will be read as a source of truth — a document, spec, README, config, or code file. Keeps the file a description of the current state only, with no change history, decision narration, TODOs, or things named only to be excluded.
---

<!-- residue-lint:ignore-file (this rule quotes the residue vocabulary to define it) -->

# Writing canonical deliverables

A deliverable is the thing itself, not the story of how it was made. Write it as a
photograph of how things stand right now, for a reader who never saw the
conversation that produced it and who will treat the file as the only source of
truth.

State only what is true now. Describe the current state directly and in full.

Leave out history and process. Nothing about what was removed, replaced, renamed,
considered, rejected, deferred, or is still pending. No "previously," "no longer,"
"instead of," "used to," "we decided," "as requested," "changed," "TODO," or
"note:". No parenthetical whose job is to explain a choice or a change, such as
"(no longer using X)" or "(do not include Y)".

Never name something only to say it is absent. If a thing is not part of the
current design, it does not appear at all, not even to rule it out. Naming an
absent thing plants it for the next reader.

The check: read each sentence as a stranger would. If a phrase only makes sense to
someone who watched the file being built, or points at something not otherwise
here, cut it.

Reasoning, alternatives, decisions, and the audit trail of how the file came to be
are worth keeping — they are simply not part of the deliverable. The moment you feel
the pull to pour that built-up record into the file is the moment to give it its
real home instead: hand it to `record-observation`, the router that sends each piece
where it belongs — a settled choice to the decision log, an unfinished action to an
issue, a durable fact to memory, anything else to chat. Record it there, then keep
the deliverable itself state-only.
