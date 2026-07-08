#!/usr/bin/env python3
"""
record-journal: append one dated entry to a subject's journal file.

The division of labor matches the plugin's other record-* scripts: the agent
writes the *content* — the subject, the task, what happened or was noticed.
This script owns the *mechanics* — slugifying the subject into its file under
journal/, stamping today's date, and inserting the entry newest-on-top.

Input is one JSON object on stdin:

  {
    "subject":  "Hindsight planning",                (required)
    "task":     "Cleaning the requirements narrative", (required)
    "entry":    "Free-form prose or bullets.",         (required)
    "made_by":  "Claude"                               (optional)
  }

On success the script is silent and exits 0. On any failure it prints a single
factual line to stderr and exits non-zero, so the calling skill can surface the
drafted entry and the reason rather than losing it. The journal file is written
to <project-root>/journal/<slug-of-subject>.md; MEMRE_JOURNAL_DIR overrides the
journal directory, --dir overrides it per-call, and --file overrides the target
file outright.

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

HEADER_TEMPLATE = """# Journal — {title}

<!-- Newest entries on top. Append-only: a running log of tasks, steps, and
     thoughts for this subject — a moment's snapshot, not a fact to keep
     current. Never edit a past entry; add a new one instead. -->

---
"""

REQUIRED = ("subject", "task", "entry")


def die(message):
    sys.stderr.write(f"record-journal: {message}\n")
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


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "general"


def resolve_path(cli_file, cli_dir, subject):
    if cli_file:
        return os.path.abspath(cli_file)
    base = cli_dir or os.environ.get("MEMRE_JOURNAL_DIR")
    if not base:
        base = os.path.join(project_root(), "journal")
    return os.path.join(os.path.abspath(base), f"{slugify(subject)}.md")


def load_payload():
    raw = sys.stdin.read()
    if not raw.strip():
        die("no JSON on stdin (pipe the journal entry object in)")
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


def render_entry(data, date):
    lines = [f"### {date} · {data['task'].strip()}"]
    made_by = str(data.get("made_by", "")).strip()
    if made_by:
        lines.append(f"- **By:** {made_by}")
    lines.append(str(data["entry"]).strip())
    return "\n".join(lines)


def insert_entry(text, entry):
    marker = "\n---\n"
    idx = text.find(marker)
    if idx == -1:
        return entry + "\n\n---\n" + ("\n" + text if text.strip() else "")
    cut = idx + len(marker)
    head, tail = text[:cut], text[cut:]
    tail = tail.lstrip("\n")
    body = entry + "\n\n---\n"
    if tail:
        body += "\n" + tail
    return head + "\n" + body


def atomic_write(path, text):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".journal.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main():
    ap = argparse.ArgumentParser(description="Append one entry to a subject's journal file")
    ap.add_argument("--file", help="exact path to the journal file (overrides subject-based lookup)")
    ap.add_argument("--dir", help="journal directory (overrides the project-root default)")
    args = ap.parse_args()

    data = load_payload()
    subject = data["subject"].strip()

    path = resolve_path(args.file, args.dir, subject)
    try:
        if os.path.exists(path):
            text = open(path).read()
        else:
            text = HEADER_TEMPLATE.format(title=subject)
    except OSError as e:
        die(f"cannot read {path}: {e}")

    date = datetime.date.today().isoformat()
    entry = render_entry(data, date)
    text = insert_entry(text, entry)

    try:
        atomic_write(path, text)
    except OSError as e:
        die(f"cannot write {path}: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
