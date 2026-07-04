#!/usr/bin/env python3
"""
residue-lint: find (and optionally strip) process-residue in a deliverable.

Process-residue is text that documents the *making* of a file instead of the
file's current state: change annotations, decision narration, TODOs, deferrals,
and parentheticals that explain what was removed, replaced, or rejected. It is
the "(no longer using X)" / "(do not display QR codes)" / "we decided to" noise
that leaks out of a conversation and contaminates the next reader's context.

Detection is split into two tiers, on purpose:

  STRIP  high-precision shapes that are residue almost every time (change-
         explaining parentheticals, directive parentheticals, TODO/FIXME lines,
         change-only "Note:" lines, whole strikethrough lines). Safe to delete
         mechanically.

  FLAG   words with legitimate uses ("previously", "instead of", "we decided")
         that need a judgment call. These are reported, never auto-deleted.

Two modes, two audiences:

  CLI     `residue_lint.py FILE...`         -> report (exit 1 if anything found)
          `residue_lint.py --fix FILE...`   -> delete STRIP hits, report FLAGs
          `--json`                          -> machine-readable findings
          For hand-offs, pre-commit, CI.

  HOOK    `residue_lint.py --hook`          -> reads Claude Code PostToolUse JSON
          on stdin, reports findings back to the model as plain factual context
          (never as a command). Set RESIDUE_LINT_FIX=1 to also strip STRIP hits.

Code fences and YAML frontmatter are skipped by default so the tool never
touches real code. Stdlib only.
"""

import argparse
import json
import os
import re
import sys

# --- extensions the hook will look at (CLI ignores this; it lints what you pass)
DEFAULT_EXTS = {".md", ".markdown", ".mdx", ".txt", ".rst"}
EXTS = {
    e if e.startswith(".") else "." + e
    for e in os.environ.get("RESIDUE_LINT_EXTS", "").split(",")
    if e.strip()
} or DEFAULT_EXTS

MAX_CONTEXT = 9000  # stay under Claude Code's 10k hook-output cap

# --- STRIP: delete the matched span (inline) or the whole line -----------------

# change-explaining parenthetical, kept as an inline aside: "... Y (no longer X) ..."
_PAREN_CHANGE = re.compile(
    r"\s*\((?:no longer|formerly|previously|used to|instead of|deprecated|"
    r"renamed|removed|dropped|superseded|to be (?:added|implemented|done)|"
    r"will be (?:added|implemented|removed)|todo|fixme|placeholder)\b[^()]*\)",
    re.IGNORECASE,
)
# directive parenthetical: "(do not display QR codes)", "(don't include the modal)"
_PAREN_DIRECTIVE = re.compile(
    r"\s*\((?:do not|don't|no need to|skip|omit)\s+[^()]*\)",
    re.IGNORECASE,
)
# whole-line task markers
_LINE_MARKER = re.compile(r"^\s*(?:TODO|FIXME|XXX|HACK)\b[:\-\s].*$", re.IGNORECASE)
# "Note:"-style line, but only when it's about a change
_LINE_CHANGE_NOTE = re.compile(
    r"^\s*(?:note|n\.?b\.?|caveat|editor'?s note|author'?s note)\s*[:\-]\s*.*\b"
    r"(?:no longer|previously|used to|instead|changed|replaced|removed|dropped|"
    r"decided|deprecated|originally|was going to)\b.*$",
    re.IGNORECASE,
)
# a line that is entirely struck-through
_LINE_STRIKE = re.compile(r"^\s*~~.*~~\s*$")

STRIP_LINE = [
    ("todo-marker", _LINE_MARKER),
    ("change-note", _LINE_CHANGE_NOTE),
    ("strikethrough", _LINE_STRIKE),
]
STRIP_SPAN = [
    ("change-aside", _PAREN_CHANGE),
    ("directive-aside", _PAREN_DIRECTIVE),
]

# --- FLAG: report only, needs a human/model judgment call ----------------------

FLAG = [
    ("change-history", re.compile(
        r"\b(?:no longer|previously|formerly|used to|instead of|rather than|"
        r"originally|superseded|deprecated|renamed|replaced with|changed (?:from|to)|"
        r"was (?:changed|removed|dropped)|has been (?:changed|removed|replaced))\b",
        re.IGNORECASE)),
    ("decision-narration", re.compile(
        r"\b(?:we decided|i decided|you decided|user decided|we chose|we opted|"
        r"decided to|opted to|as (?:discussed|requested|mentioned|noted|agreed)|"
        r"per your request|for now|going forward)\b",
        re.IGNORECASE)),
    ("negated-absent", re.compile(
        r"\b(?:do not include|don't include|not including|we removed|removed the|"
        r"excluded|omitting|dropped the|no longer include)\b",
        re.IGNORECASE)),
    ("deferral", re.compile(
        r"\b(?:to be (?:added|implemented|determined|decided|done)|will be implemented|"
        r"coming soon|not yet (?:implemented|added|done)|pending|placeholder)\b",
        re.IGNORECASE)),
    ("memory-migration", re.compile(
        r"\b(?:switched (?:from|to)|migrated (?:from|to)|moved (?:from|to)|"
        r"converted (?:from|to)|ported (?:from|to)|now (?:uses|stored|lives))\b",
        re.IGNORECASE)),
]

FENCE = re.compile(r"^\s*(?:```|~~~)")

# Escape hatches for files/lines that legitimately discuss residue vocabulary
# (rule docs, this plugin's own skill, changelogs that are meant to be histories).
IGNORE_LINE = "residue-lint:ignore"
IGNORE_FILE = "residue-lint:ignore-file"

# leading YAML frontmatter block, used by --memory to reach the description field
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _regions(lines, include_code):
    """Yield (idx, line, is_prose). is_prose False inside fences/frontmatter."""
    in_fence = False
    in_front = False
    # YAML frontmatter only if the very first line is '---'
    if lines and lines[0].strip() == "---":
        in_front = True
    for i, line in enumerate(lines):
        if in_front:
            yield i, line, False
            if i > 0 and line.strip() == "---":
                in_front = False
            continue
        if FENCE.match(line):
            in_fence = not in_fence
            yield i, line, False
            continue
        yield i, line, (not in_fence) or include_code


def _normalize(seg):
    """Tidy a prose line after an inline span was removed."""
    lead = re.match(r"^(\s*)", seg).group(1)
    body = seg[len(lead):]
    body = re.sub(r"\s+([.,;:!?])", r"\1", body)  # " ." -> "."
    body = re.sub(r"[ \t]{2,}", " ", body)         # collapse double spaces
    return (lead + body).rstrip() if body.strip() else ""


def scan(text, fix=False, include_code=False):
    """Return (new_text, findings). findings: list of (line_no, tier, cat, snippet)."""
    if IGNORE_FILE in text:
        return text, []

    lines = text.splitlines()
    findings = []
    out = []
    dropped = False

    for i, line, is_prose in _regions(lines, include_code):
        ln = i + 1
        if not is_prose or IGNORE_LINE in line:
            out.append(line)
            continue

        working = line
        removed_span = False

        # whole-line strips
        killed = False
        for cat, pat in STRIP_LINE:
            if pat.match(working):
                findings.append((ln, "strip", cat, working.strip()[:120]))
                killed = True
                break
        if killed:
            dropped = True
            if not fix:
                out.append(line)  # report mode keeps the line
            # fix mode: drop the line entirely
            continue

        # inline span strips
        for cat, pat in STRIP_SPAN:
            for m in pat.finditer(working):
                findings.append((ln, "strip", cat, m.group(0).strip()[:120]))
                removed_span = True
            if fix:
                working = pat.sub("", working)

        if removed_span and fix:
            working = _normalize(working)
            if working == "":
                dropped = True
                continue

        # flags (report only, on the post-strip text)
        for cat, pat in FLAG:
            m = pat.search(working)
            if m:
                findings.append((ln, "flag", cat, working.strip()[:120]))

        out.append(working)

    new_text = "\n".join(out)
    if text.endswith("\n"):
        new_text += "\n"
    if fix and dropped:
        new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    return new_text, findings


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# --- CLI -----------------------------------------------------------------------

def run_cli(args):
    total = 0
    payload = {}
    for path in args.files:
        try:
            text = _read(path)
        except OSError as e:
            print(f"residue-lint: cannot read {path}: {e}", file=sys.stderr)
            continue
        new_text, findings = scan(text, fix=args.fix, include_code=args.include_code)
        total += len(findings)
        payload[path] = [
            {"line": ln, "tier": tier, "category": cat, "text": snip}
            for ln, tier, cat, snip in findings
        ]
        if args.fix and new_text != text:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)

    if args.json:
        print(json.dumps(payload, indent=2))
        return 1 if total else 0

    for path, items in payload.items():
        if not items:
            print(f"{path}: clean")
            continue
        for it in items:
            mark = "strip" if it["tier"] == "strip" else "FLAG "
            verb = "removed" if (args.fix and it["tier"] == "strip") else "found"
            print(f'{path}:{it["line"]}: [{mark}] {it["category"]} {verb}: {it["text"]}')
    if total:
        stripped = sum(1 for p in payload.values() for it in p if it["tier"] == "strip")
        flagged = total - stripped
        tail = "removed" if args.fix else "to remove"
        print(f"\n{stripped} residue {tail}, {flagged} flagged for review.")
    return 1 if (total and not args.fix) else 0


# --- HOOK ----------------------------------------------------------------------

def run_hook():
    """PostToolUse: read stdin JSON, report residue to the model as plain context."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never break the session on bad input

    tool = data.get("tool_name", "")
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0
    tin = data.get("tool_input", {}) or {}
    path = tin.get("file_path") or tin.get("path") or ""
    if not path:
        return 0
    if os.path.splitext(path)[1].lower() not in EXTS:
        return 0

    cwd = data.get("cwd") or ""
    fpath = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        text = _read(fpath)
    except OSError:
        text = tin.get("content") or tin.get("new_string") or ""
        if not text:
            return 0

    fix = os.environ.get("RESIDUE_LINT_FIX", "") not in ("", "0", "false", "False")
    new_text, findings = scan(text, fix=fix, include_code=False)
    if fix and new_text != text:
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(new_text)
        except OSError:
            fix = False

    if not findings:
        return 0

    stripped = [f for f in findings if f[1] == "strip"]
    flagged = [f for f in findings if f[1] == "flag"]
    name = os.path.basename(fpath)

    # Plain, factual phrasing. Not an instruction. This is deliberate: hook text
    # framed as a command trips the model's prompt-injection defense.
    parts = [
        f"residue-lint checked {name}. The phrases below describe how the file "
        f"was made (history, decisions, deferrals, or things named only to be "
        f"excluded) rather than the current state, and don't belong in a "
        f"canonical deliverable."
    ]
    if fix and stripped:
        parts.append(f"{len(stripped)} high-confidence item(s) were removed automatically.")
    elif stripped:
        parts.append("High-confidence items to remove:")
        parts += [f"  line {ln}: {snip}" for ln, _, _, snip in stripped]
    if flagged:
        parts.append("Phrases to review and likely rewrite as plain present-tense state:")
        parts += [f"  line {ln} ({cat}): {snip}" for ln, _, cat, snip in flagged]

    context = "\n".join(parts)
    if len(context) > MAX_CONTEXT:
        context = context[:MAX_CONTEXT] + "\n(truncated)"

    n = len(findings)
    out = {
        "systemMessage": f"residue-lint: {name} — {n} process-residue item(s) "
                         f"{'cleaned/' if fix and stripped else ''}flagged.",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        },
    }
    print(json.dumps(out))
    return 0


# --- MEMORY audit --------------------------------------------------------------

def scan_memory(text):
    """Audit one memory record. Scans the frontmatter `description` and the body,
    since a memory's residue lives in the fact itself ("user replaced X with Y").
    Returns [(where, category, snippet)]. Report only; memory is never auto-edited."""
    if IGNORE_FILE in text:
        return []
    findings = []
    m = _FRONTMATTER.match(text)
    if m:
        body = text[m.end():]
        dm = re.search(r"(?im)^\s*description\s*:\s*(.+?)\s*$", m.group(1))
        if dm:
            desc = dm.group(1).strip().strip("\"'")
            _, df = scan(desc)
            for _, _, cat, snip in df:
                findings.append(("description", cat, snip))
    else:
        body = text
    _, bf = scan(body)
    for ln, _, cat, snip in bf:
        findings.append((f"body:{ln}", cat, snip))
    return findings


def run_memory(args):
    files = []
    for p in args.files:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in names if n.endswith(".md")]
        else:
            files.append(p)

    payload = {}
    dirty = 0
    for path in sorted(files):
        try:
            text = _read(path)
        except OSError as e:
            print(f"residue-lint: cannot read {path}: {e}", file=sys.stderr)
            continue
        f = scan_memory(text)
        payload[path] = f
        if f:
            dirty += 1

    if args.json:
        print(json.dumps(
            {p: [{"where": w, "category": c, "text": t} for w, c, t in f]
             for p, f in payload.items()}, indent=2))
        return 1 if dirty else 0

    for path, f in payload.items():
        if not f:
            print(f"{path}: end-state fact, clean")
            continue
        print(f"{path}: records a change or process, not just the current fact:")
        for where, cat, snip in f:
            print(f"  [{where}] {cat}: {snip}")
    if dirty:
        noun = "memory records" if dirty == 1 else "memories record"
        print(f"\n{dirty} {noun} a change rather than a fact. Overwrite each with the "
              f"current end-state fact, or prune it. (No files were modified.)")
    return 1 if dirty else 0


def main():
    p = argparse.ArgumentParser(description="Find/strip process-residue in deliverables.")
    p.add_argument("files", nargs="*", help="files to lint (CLI mode)")
    p.add_argument("--fix", action="store_true", help="delete high-confidence residue in place")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--include-code", action="store_true", help="also lint fenced code blocks")
    p.add_argument("--hook", action="store_true", help="Claude Code PostToolUse mode (stdin JSON)")
    p.add_argument("--memory", action="store_true",
                   help="audit auto-memory files/dirs: flag records that store a change "
                        "instead of a current fact (report only, never edits)")
    args = p.parse_args()

    if args.hook:
        sys.exit(run_hook())
    if args.memory:
        if not args.files:
            p.error("give a memory file or directory")
        sys.exit(run_memory(args))
    if not args.files:
        p.error("no files given (or use --hook)")
    sys.exit(run_cli(args))


if __name__ == "__main__":
    main()
