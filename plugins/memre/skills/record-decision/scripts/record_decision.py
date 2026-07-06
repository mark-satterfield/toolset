#!/usr/bin/env python3
"""
record-decision: append one decision to the project's decisions.md, wiring the
identifiers and supersession back-pointers the agent must not hand-forge.

The division of labor is deliberate. The agent writes the *content* of a
decision — the settled fact, the pressure that forced it, the roads not taken.
This script owns the *mechanics*: it assigns the next D-id, stamps today's date,
renders the entry in the canonical shape, inserts it newest-on-top, and — when
the decision supersedes an earlier one — flips that older entry to Superseded
and cross-links the two so the log never lies about which decision is live.

Input is one JSON object on stdin:

  {
    "title":   "Short decision title",              (required)
    "decision":"What was settled, present tense",   (required)
    "made_by": "Name · Role",                       (optional; blank if unknown)
    "context": "The pressure that forced a choice",  (required)
    "options": [                                     (required, >=1)
      {"option": "The winner"},                      exactly one has chosen:true
      {"option": "Loser B", "reason": "why it lost"}
    ],
    "chosen":  0,                                    index of winner, OR mark one
                                                     option object with "chosen": true
    "why_chosen":         "Why the winner won",      (required)
    "consequences":       "The price accepted",      (required)
    "revisit_conditions": "An observable trigger",   (required)
    "supersedes":         "D-003",                   (optional)
    "impacted_repositories": [                        (optional)
      {"name": "repo-or-dir", "target": "https://... or /path/"}
    ]
  }

On success the script is silent and exits 0. On any failure it prints a single
factual line to stderr and exits non-zero, so the calling skill can surface the
drafted record and the reason rather than losing it. The decisions.md file is
written to the git repository root (falling back to the current directory);
MEMRE_DECISIONS_FILE overrides the full path for tests.

Stdlib only.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

HEADER = """# Decision Log

<!-- Newest entries on top. Append-only: never edit or delete a past decision.
     When one changes, add a new entry and mark the old one Superseded. The
     record-decision skill and its script maintain this file; hand-edit with care. -->

---
"""

ENTRY_RE = re.compile(r"^### (D-(\d+)) ·", re.MULTILINE)
_STATUS_LINE = re.compile(r"^- \*\*Status:\*\* .*$")
_SUPERSEDED_BY_LINE = re.compile(r"^- \*\*Superseded By:\*\* .*$")

REQUIRED = ("title", "decision", "context", "why_chosen",
            "consequences", "revisit_conditions")


def die(message):
    sys.stderr.write(f"record-decision: {message}\n")
    sys.exit(1)


def project_root():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        top = out.stdout.strip()
        if top:
            return top
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return os.getcwd()


def resolve_path(cli_file):
    if cli_file:
        return os.path.abspath(cli_file)
    override = os.environ.get("MEMRE_DECISIONS_FILE")
    if override:
        return os.path.abspath(override)
    return os.path.join(project_root(), "decisions.md")


def load_payload():
    raw = sys.stdin.read()
    if not raw.strip():
        die("no JSON on stdin (pipe the decision object in)")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"stdin is not valid JSON: {e}")
    if not isinstance(data, dict):
        die("JSON payload must be an object")
    missing = [f for f in REQUIRED if not str(data.get(f, "")).strip()]
    if missing:
        die("missing required field(s): " + ", ".join(missing))
    return data


def resolve_options(data):
    options = data.get("options")
    if not isinstance(options, list) or not options:
        die("'options' must be a non-empty list")
    chosen_idx = data.get("chosen")
    marked = [i for i, o in enumerate(options)
              if isinstance(o, dict) and o.get("chosen")]
    if chosen_idx is not None:
        if not isinstance(chosen_idx, int) or not (0 <= chosen_idx < len(options)):
            die("'chosen' must be a valid index into 'options'")
        if marked and marked != [chosen_idx]:
            die("'chosen' index and an option's chosen:true disagree")
        winner = chosen_idx
    elif len(marked) == 1:
        winner = marked[0]
    elif not marked:
        die("no winning option (set 'chosen' index or mark one option chosen:true)")
    else:
        die("more than one option marked chosen — a decision has exactly one winner")
    for i, o in enumerate(options):
        text = (o.get("option") if isinstance(o, dict) else str(o)) or ""
        if not text.strip():
            die(f"option {i} has no text")
        if i != winner:
            reason = o.get("reason", "") if isinstance(o, dict) else ""
            if not str(reason).strip():
                die(f"losing option {i} ('{text.strip()}') needs a 'reason' it lost")
    return options, winner


def next_id(text):
    ids = [int(m.group(2)) for m in ENTRY_RE.finditer(text)]
    return max(ids) + 1 if ids else 1


def render_entry(data, new_id, date, options, winner, supersedes_ref):
    lines = [f"### {new_id} · {date} · {data['title'].strip()}"]
    lines.append("- **Status:** Active")
    lines.append(f"- **Decision:** {data['decision'].strip()}")
    made_by = str(data.get("made_by", "")).strip()
    lines.append(f"- **Made By:** {made_by}".rstrip())
    lines.append(f"- **Context:** {data['context'].strip()}")
    lines.append("- **Options Considered:**")
    for i, o in enumerate(options):
        text = (o.get("option") if isinstance(o, dict) else str(o)).strip()
        if i == winner:
            lines.append(f"  - {text} — chosen")
        else:
            lines.append(f"  - {text} — {str(o.get('reason', '')).strip()}")
    lines.append(f"- **Why Chosen:** {data['why_chosen'].strip()}")
    lines.append(f"- **Consequences:** {data['consequences'].strip()}")
    lines.append(f"- **Revisit Conditions:** {data['revisit_conditions'].strip()}")
    lines.append(f"- **Supersedes:** {supersedes_ref or '—'}")
    lines.append("- **Superseded By:** —")
    repos = data.get("impacted_repositories")
    if isinstance(repos, list) and repos:
        lines.append("- **Impacted Repositories:**")
        for r in repos:
            name = str(r.get("name", "")).strip()
            target = str(r.get("target", "")).strip()
            if name and target:
                lines.append(f"  - [{name}]({target})")
    return "\n".join(lines)


def entry_block_bounds(lines, dash_id):
    """Return (start, end) line indices of the block for D-id, or None."""
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"### {dash_id} ·"):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("### D-") or lines[j].strip() == "---":
            end = j
            break
    return start, end


def apply_supersession(text, old_dash_id, new_ref):
    """Flip the old entry to Superseded and point it at the new one.

    Returns (new_text, old_ref). Raises via die() if the id isn't present.
    """
    lines = text.split("\n")
    bounds = entry_block_bounds(lines, old_dash_id)
    if bounds is None:
        die(f"cannot supersede {old_dash_id}: no such entry in the log")
    start, end = bounds
    header = lines[start]
    m = re.match(r"### (D-\d+ · .+)$", header)
    old_ref = m.group(1) if m else old_dash_id
    saw_superseded_by = False
    for i in range(start, end):
        if _STATUS_LINE.match(lines[i]):
            lines[i] = "- **Status:** Superseded"
        elif _SUPERSEDED_BY_LINE.match(lines[i]):
            lines[i] = f"- **Superseded By:** {new_ref}"
            saw_superseded_by = True
    if not saw_superseded_by:
        lines.insert(end, f"- **Superseded By:** {new_ref}")
    return "\n".join(lines), old_ref


def insert_entry(text, entry):
    """Insert a rendered entry newest-on-top, right after the header rule."""
    marker = "\n---\n"
    idx = text.find(marker)
    if idx == -1:
        # malformed or headerless — rebuild a clean header in front of it
        return HEADER + "\n" + entry + "\n\n---\n" + ("\n" + text if text.strip() else "")
    cut = idx + len(marker)
    head, tail = text[:cut], text[cut:]
    tail = tail.lstrip("\n")
    body = entry + "\n\n---\n"
    if tail:
        body += "\n" + tail
    return head + "\n" + body


def atomic_write(path, text):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".decisions.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main():
    ap = argparse.ArgumentParser(description="Append one decision to decisions.md")
    ap.add_argument("--file", help="path to the decisions log (overrides project root)")
    args = ap.parse_args()

    data = load_payload()
    options, winner = resolve_options(data)

    path = resolve_path(args.file)
    try:
        text = open(path).read() if os.path.exists(path) else HEADER
    except OSError as e:
        die(f"cannot read {path}: {e}")

    date = datetime.date.today().isoformat()
    new_id = f"D-{next_id(text):03d}"

    supersedes_ref = None
    if str(data.get("supersedes", "")).strip():
        old_id = data["supersedes"].strip()
        if not re.fullmatch(r"D-\d+", old_id):
            die(f"'supersedes' must be a D-id like D-003, got '{old_id}'")
        new_ref = f"{new_id} · {date} · {data['title'].strip()}"
        text, supersedes_ref = apply_supersession(text, old_id, new_ref)

    entry = render_entry(data, new_id, date, options, winner, supersedes_ref)
    text = insert_entry(text, entry)

    try:
        atomic_write(path, text)
    except OSError as e:
        die(f"cannot write {path}: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
