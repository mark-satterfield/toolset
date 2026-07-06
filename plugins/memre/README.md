<!-- residue-lint:ignore-file (documentation that quotes the residue vocabulary) -->

# memre

A Claude Code plugin for memory-and-deliverable hygiene. It keeps generated files
free of process-residue (the change annotations, decision narration, TODOs, and
"named only to be excluded" asides that leak out of a working session), audits
auto-memory for records that store a change instead of a current fact, imports
file-based memories into beads, and gives the making-of a home of its own so it
stops leaking into the work — a router that sends each recordable thing to one
durable sink, and a decision log behind it.

## What it contains

- **Skill `canonical-output`** — a writing rule that applies when Claude writes or
  edits a deliverable, directing it to describe the current state only, for a
  reader who never saw the conversation. At the moment Claude feels the pull to pour
  built-up reasoning and history into the file, it points that record at
  `record-observation` instead, so the deliverable stays state-only and the record
  still lands somewhere durable.
- **Skill `record-observation`** — the router. When Claude has something worth
  recording and no obvious place for it, this classifies the record into one sink —
  Issue, Decision, Memory, or Console — and hands it to the sink skill that owns it,
  so it stops getting stitched into the deliverable. It only classifies; each sink
  skill owns its own backend resolution and field enforcement.
- **Skill `record-decision`** — records a settled choice in the project's
  `decisions.md` (at the repo root). Claude drafts the seven fields and two rules;
  the bundled `record_decision.py` owns the identifiers, dates, and `Supersedes` /
  `Superseded By` back-pointers.
- **Skill `record-memory`** — writes one durable auto-memory. It resolves the store
  (beads-for-memory when context asks for it and beads is ready, else auto-memory
  markdown), enforces the schema — the `type` and the `Why`/`How to apply` lines
  feedback and project memories must carry — and its `record_memory.py` derives the
  filename and updates the `MEMORY.md` index.
- **Skill `record-issue`** — files a not-yet-done action to the right tracker. It
  resolves beads / GitHub / Linear / Jira by crossing SHOULD (what
  `AGENTS.md`/`CLAUDE.md` says to use) against CAN (what is installed), enforces the
  title/context/done triad, and creates the issue through the resolved backend.
- **Probe `scripts/probe_sinks.py`** — the CAN engine the record-issue and
  record-memory skills call: reports whether beads, GitHub, and Jira are usable here
  (Linear is resolved by MCP-tool presence, which a shell can't see). Silent on
  success, loud only on failure — a rule the record-* writer scripts share.
- **Linter `scripts/residue_lint.py`** — the mechanical backstop behind
  `/memre:scan` and `/memre:clean`, and runnable on its own from the command line or
  CI, with a memory-audit mode. It catches the purely literal residue shapes; the
  meaning-level judgment lives in the commands, which read the whole file.
- **Importer `scripts/md_to_beads.py`** — moves file-based auto-memory into beads,
  keeping the markdown verbatim.
- **Commands** — `/memre:scan`, `/memre:clean`, `/memre:audit-memory`, `/memre:to-beads`.

## Install

    /plugin marketplace add <your-marketplace>
    /plugin install memre@<your-marketplace>

To try it in place before publishing:

    claude --plugin-dir ./memre

## Commands

- `/memre:scan <file>` — read the whole file and report residue by meaning, change
  nothing. Judges each passage as a stranger would; the linter is only a backstop.
- `/memre:clean <file>` — remove residue in place by the same judgment, routing any
  real decision, history, or open action to `/record-observation` before deleting it,
  and listing the judgment calls for you.
- `/memre:audit-memory <file-or-dir>` — flag memory records that store a change
  ("user replaced X with Y") instead of a current fact. Report only.
- `/memre:to-beads <memory-dir>` — import file-based memories into beads (dry run
  by default).

## The linter on its own

    python3 scripts/residue_lint.py FILE...        # report; exits non-zero if found
    python3 scripts/residue_lint.py --fix FILE...   # strip high-confidence residue
    python3 scripts/residue_lint.py --json FILE...  # machine-readable findings
    python3 scripts/residue_lint.py --memory DIR    # audit auto-memory (report only)

High-confidence shapes (change-explaining parentheticals, directive parentheticals,
TODO/FIXME lines, change-only "Note:" lines, whole strikethrough lines) are safe to
delete. Ambiguous words with honest uses ("previously," "instead of," "we decided")
are reported for a judgment call, never deleted. Fenced code and YAML frontmatter
are left untouched.

## Importing memory into beads

    python3 scripts/md_to_beads.py <memory-dir> --project-dir <repo-root>   # dry run
    python3 scripts/md_to_beads.py <memory-dir> --project-dir <repo-root> --script
    python3 scripts/md_to_beads.py <memory-dir> --project-dir <repo-root> --apply

Each memory file becomes one beads entry: the key is the memory's `name` (the same
slug used in `[[wikilinks]]`), and the value is the file's full markdown, frontmatter
and body verbatim, so nothing is lost. The memory directory (under
`~/.claude/projects/`) and the beads project root (which holds `.beads/`) are
different places; `bd` runs in the project root. The dry run writes nothing; review
it, then use `--script` to emit a bash script to read first, or `--apply` to call
`bd remember`. Add `--delete-source` with `--apply` to delete each source file whose
import succeeded. The `MEMORY.md` index is skipped.

## Exempting a file or line

A file that legitimately discusses this vocabulary (a rule doc, a changelog that is
meant to be a history) will flag itself. Add `residue-lint:ignore-file` anywhere in
the file to skip it entirely, or `residue-lint:ignore` on a single line to skip just
that line. Both work inside a comment.

## Tuning

The word lists live near the top of `scripts/residue_lint.py`, in `STRIP_LINE`,
`STRIP_SPAN`, and `FLAG`. Add a phrase your projects tend to leak and it takes
effect on the next run.

## Setup notes

Set `author`, `homepage`, and `repository` in `.claude-plugin/plugin.json` to your
own values before publishing.
