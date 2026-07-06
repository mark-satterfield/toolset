#!/usr/bin/env python3
"""
record-memory: write one auto-memory file and index it, enforcing the schema.

A memory is one file holding one fact. This script owns the mechanics so the
shape can't drift: it validates the frontmatter type, enforces that feedback and
project memories carry the **Why:** and **How to apply:** lines, derives the
filename from the type and name, writes the file, and adds the one-line pointer to
MEMORY.md. The agent supplies the content and the memory directory (which it
already holds in context — the `MEMORY.md` index path); it does not hand-format
the file or hand-edit the index.

Input is one JSON object on stdin:

  {
    "name":        "short-kebab-slug",              (required; the [[wikilink]] id)
    "description": "one-line relevance summary",     (required)
    "type":        "user|feedback|project|reference",(required)
    "title":       "Human Title",                    (required; MEMORY.md label)
    "hook":        "index one-liner after the em-dash", (required)
    "body":        "the fact, in full",              (required)
    "why":         "why this guidance exists",       (required for feedback/project)
    "how_to_apply":"how to act on it",               (required for feedback/project)
    "links":       ["other-memory-name", ...]        (optional; appended as [[..]])
  }

  --dir D    the auto-memory directory (required) — the one holding MEMORY.md.
  --update   overwrite an existing memory of the same name instead of refusing.

Filename is `<type>_<name-with-dashes-as-underscores>.md`. On success the script
is silent and exits 0. On any failure it prints one factual line to stderr and
exits non-zero, so the calling skill can surface the drafted memory rather than
lose it. Stdlib only.
"""

import argparse
import json
import os
import re
import sys
import tempfile

TYPES = ("user", "feedback", "project", "reference")
NEEDS_WHY = ("feedback", "project")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED = ("name", "description", "type", "title", "hook", "body")


def die(message):
    sys.stderr.write(f"record-memory: {message}\n")
    sys.exit(1)


def load_payload():
    raw = sys.stdin.read()
    if not raw.strip():
        die("no JSON on stdin (pipe the memory object in)")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"stdin is not valid JSON: {e}")
    if not isinstance(data, dict):
        die("JSON payload must be an object")
    missing = [f for f in REQUIRED if not str(data.get(f, "")).strip()]
    if missing:
        die("missing required field(s): " + ", ".join(missing))
    if data["type"] not in TYPES:
        die(f"type must be one of {', '.join(TYPES)}; got '{data['type']}'")
    if not NAME_RE.match(data["name"]):
        die(f"name must be a kebab-case slug (a-z, 0-9, dashes); got '{data['name']}'")
    if data["type"] in NEEDS_WHY:
        for f in ("why", "how_to_apply"):
            if not str(data.get(f, "")).strip():
                die(f"a '{data['type']}' memory requires '{f}'")
    return data


def render(data):
    lines = [
        "---",
        f"name: {data['name'].strip()}",
        f"description: {data['description'].strip()}",
        "metadata:",
        f"  type: {data['type']}",
        "---",
        "",
        data["body"].strip(),
    ]
    if data["type"] in NEEDS_WHY:
        lines += ["", f"**Why:** {data['why'].strip()}",
                  f"**How to apply:** {data['how_to_apply'].strip()}"]
    links = data.get("links")
    if isinstance(links, list) and links:
        refs = " ".join(f"[[{str(l).strip()}]]" for l in links if str(l).strip())
        if refs:
            lines += ["", f"Related: {refs}"]
    return "\n".join(lines) + "\n"


def atomic_write(path, text):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".memory.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def index_line(data, filename):
    return f"- [{data['title'].strip()}]({filename}) — {data['hook'].strip()}"


def update_index(mem_dir, filename, line):
    idx = os.path.join(mem_dir, "MEMORY.md")
    if os.path.exists(idx):
        text = open(idx).read()
        if f"({filename})" in text:
            return  # already indexed; leave the human's wording intact
        sep = "" if text.endswith("\n") else "\n"
        atomic_write(idx, text + sep + line + "\n")
    else:
        atomic_write(idx, "# Memory Index\n\n" + line + "\n")


def main():
    ap = argparse.ArgumentParser(description="Write one auto-memory file and index it")
    ap.add_argument("--dir", required=True, help="the auto-memory directory (holds MEMORY.md)")
    ap.add_argument("--update", action="store_true", help="overwrite an existing memory of the same name")
    args = ap.parse_args()

    mem_dir = os.path.abspath(args.dir)
    if not os.path.isdir(mem_dir):
        die(f"memory directory does not exist: {mem_dir}")

    data = load_payload()
    filename = f"{data['type']}_{data['name'].replace('-', '_')}.md"
    path = os.path.join(mem_dir, filename)
    if os.path.exists(path) and not args.update:
        die(f"memory {filename} already exists — edit it, or pass --update to replace it")

    try:
        atomic_write(path, render(data))
        update_index(mem_dir, filename, index_line(data, filename))
    except OSError as e:
        die(f"cannot write under {mem_dir}: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
