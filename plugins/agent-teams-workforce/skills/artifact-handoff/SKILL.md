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

## Executable producer contract

Use the caller's canonical schema for both production and review; architecture uses [writer](schemas/architecture-writer.schema.json) and [reviewer](schemas/architecture-review.schema.json). Never maintain a second schema in prose. The [checkpoint schema](schemas/checkpoint.schema.json) is shared by producer status commands.

Resolve `scripts/portfolio/artifactcontract.py` from this plugin's root (two directories above this skill). The workflow supplies the candidate path, canonical schema and input revision. Pass exactly one of `--schema-file PATH` or `--schema-json JSON`; both use identical strict parsing, validation and canonical hashing. Prefer the schema file when the caller supplies one. Author a small progress JSON file with `task`, `completed`, `remaining`, and `artifacts`; add `reason` when blocked. Do not put binding hashes or completion flags in that file: the helper computes them.

```bash
python3 "$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py" checkpoint --candidate "$CANDIDATE" --schema-file "$SCHEMA" --revision "$REVISION" --progress-file "$PROGRESS" --status in-progress
python3 "$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py" complete --candidate "$CANDIDATE" --schema-file "$SCHEMA" --revision "$REVISION" --progress-file "$PROGRESS"
python3 "$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py" status --candidate "$CANDIDATE" --schema-file "$SCHEMA" --revision "$REVISION"
```

For a dependency you cannot satisfy, checkpoint with `--status blocked` and its exact `reason` and remaining work. Do not mark incomplete reasoning complete merely to satisfy the schema. `complete` requires no remaining work, validates strict JSON against the canonical schema, canonicalizes the candidate and writes its bound checkpoint. Return only the candidate reference after that command succeeds. `validate` performs schema validation without mutation. Invalid commands return exit 2 with an explicit error.

`complete-unaccepted` means structurally ready for the workflow's existing acceptance operation, not technically correct, approved, or shipped. Reviewers read the authoritative artifacts and independently judge evidence; mechanically valid metadata cannot establish their correctness. Status detects changed candidate bytes and changed input/schema bindings. Resume `in-progress`/`blocked` work from its actual artifacts; do not restart completed reasoning or silently retry an unchanged blocker.

The coordinator may use `scripts/portfolio/artifactpublish.py --record-argv-json JSON -- <jsonartifact acceptance arguments>` to validate/publish and record provenance in one deterministic invocation. The recorder receives argv, not shell text, and must name the accepted artifact. Pending or rejected candidates are never recorded; recorder failure reports failure and retains the accepted artifact for recovery. This replaces separate administrative agent calls without replacing specialist reasoning or independent review.

For the actual handoff use `submit` with the same arguments as `complete`: it validates and writes the checkpoint, then emits exactly the response object `{"artifactPath":"..."}`. Return that object unchanged. The schema describes the on-disk candidate; the response contains only its reference. A failed submission emits an error and never writes a new completion checkpoint. When the caller supplies `--files-root ROOT --files-field FIELD`, submission also verifies every path in that candidate field is relative to ROOT, stays inside it after symlink resolution, and names a nonempty regular file. These are declared authored outputs, not all assigned or future files. `--progress-artifacts-root ROOT` additionally checks explicitly declared progress artifact paths inside that root; use it only when the caller establishes that scope. These checks establish file existence and structure, not whether the reasoning is correct.
