---
name: artifact-handoff
description: Share authoritative documents, diagrams and JSON by artifact path, with format-specific validation and resumable checkpoints; never retype full payloads between agents.
---

Shared documents, Markdown, diagrams and other artifacts stay in their authoritative files. Pass paths and brief task context; recipients read the actual files. A summary is navigation, never a substitute source. Edit only explicitly assigned files; preserve accepted work. Do not retype an entire document into another agent's prompt or machine response. Use existing deterministic file operations for exact copies when a copy is explicitly required.

Keep the caller-specified checkpoint current after meaningful work: status, task, completed work, remaining work and artifact paths. On resume read the checkpoint and referenced artifacts, verify current state and complete remaining work. A checkpoint is progress evidence, never acceptance or permission to omit validation.

For JSON, write the caller's requested JSON object once to its exact candidate path. Use the supplied artifact schema; do not confuse it with the small return schema. Preserve existing completed work and inspect an existing candidate before continuing interrupted work. Return only the candidate path using the caller's structured return schema. Never copy the full artifact into StructuredOutput or prose.

The workflow's named command runner invokes `scripts/portfolio/jsonartifact.py` with the expected candidate, final path and schema. The script rejects duplicate keys, invalid JSON, schema violations and changes to already accepted results. It writes canonical JSON and an integrity receipt; downstream scripts verify the receipt. Candidates stay outside the accepted result directory. A failed candidate is never treated as a completed step.

The command runner runs only the exact checked command supplied by the workflow. Validation failure is reported explicitly; it does not authorize rewriting another producer's content or repeating a successful administrative command. Existing legacy artifacts are preserved.

For Markdown and diagrams, `jsonartifact.py --document PATH` verifies the actual nonempty UTF-8 file and returns its path, raw-byte SHA-256, length and format. It never copies or rewrites the document. This receipt identifies the reviewed version; it is not a semantic quality verdict and does not prohibit later authorized edits. Keep structured metadata separate and refer to the document path instead of embedding its contents.

Candidate completion checkpoints bind the exact candidate path, expected schema hash and caller revision. The workflow derives that revision from actual source-file/corpus byte fingerprints and assignment context; a path alone is not freshness evidence. Changed inputs require a new candidate revision. A saved complete result for the same revision is reused; it is never silently replaced. Fingerprints exclude the producer’s assigned output files to preserve interruption recovery.
