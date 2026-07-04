<!-- residue-lint:ignore-file (documentation that quotes the residue vocabulary) -->

# memre

A Claude Code plugin for memory-and-deliverable hygiene. It keeps generated files
free of process-residue (the change annotations, decision narration, TODOs, and
"named only to be excluded" asides that leak out of a working session), audits
auto-memory for records that store a change instead of a current fact, and imports
file-based memories into beads.

## What it contains

- **Skill `canonical-output`** — a writing rule that applies when Claude writes or
  edits a deliverable, directing it to describe the current state only, for a
  reader who never saw the conversation.
- **PostToolUse hook** — after any `Write`, `Edit`, or `MultiEdit` on a document,
  it inspects the file for residue and hands the findings back to Claude as plain
  context, so Claude cleans them on its next turn.
- **Linter `scripts/residue_lint.py`** — the detector and fixer behind the hook,
  also runnable from the command line or CI, with a memory-audit mode.
- **Importer `scripts/md_to_beads.py`** — moves file-based auto-memory into beads,
  keeping the markdown verbatim.
- **Commands** — `/memre:scan`, `/memre:clean`, `/memre:audit-memory`, `/memre:to-beads`.

## Install

    /plugin marketplace add <your-marketplace>
    /plugin install memre@<your-marketplace>

To try it in place before publishing:

    claude --plugin-dir ./memre

## Commands

- `/memre:scan <file>` — report residue, change nothing.
- `/memre:clean <file>` — delete high-confidence residue in place and list the rest.
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
