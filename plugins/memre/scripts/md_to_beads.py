#!/usr/bin/env python3
"""
md_to_beads: import file-based auto-memory into beads, preserving the markdown.

Each memory file (~/.claude/projects/<project>/memory/<slug>.md) becomes one beads
entry. The key is the memory's `name` (the same slug used in [[wikilinks]]); the
value is the file's full markdown, frontmatter and body verbatim, so nothing is
lost and `bd memories <term>` still matches on the content.

The memory directory and the beads project are two different places: memory lives
under ~/.claude/projects/, while the beads DB lives in a `.beads/` directory in the
project's own root. Pass the memory dir as the argument and the project root as
--project-dir (default: current directory); `bd` runs there.

Default is a dry run that writes nothing. Review the plan, then:
  --apply           call `bd remember` for each entry (upsert; safe to re-run)
  --script          emit a runnable bash script to read before running
  --delete-source   with --apply, delete each source file whose import succeeded
The MEMORY.md index is skipped; it is an index, not a fact.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


def slug_from_filename(path):
    base = os.path.splitext(os.path.basename(path))[0]
    return base.replace("_", "-").strip().lower()


def parse_memory(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    name = mtype = desc = ""
    if m := _FRONTMATTER.match(text):
        fm = m.group(1)
        nm = re.search(r"(?im)^\s*name\s*:\s*(.+?)\s*$", fm)
        tm = re.search(r"(?im)^\s*type\s*:\s*([A-Za-z]+)", fm)
        dm = re.search(r"(?im)^\s*description\s*:\s*(.+?)\s*$", fm)
        name = nm[1].strip().strip("\"'") if nm else ""
        mtype = tm[1].strip().lower() if tm else ""
        desc = dm[1].strip().strip("\"'") if dm else ""
    key = name or slug_from_filename(path)
    return {
        "path": path,
        "key": key,
        "type": mtype or "(none)",
        "description": desc,
        "content": text,           # verbatim: frontmatter + body
        "links": _WIKILINK.findall(text),
        "had_name": bool(name),
    }


def collect(memory_dir, include_index):
    out = []
    for name in sorted(os.listdir(memory_dir)):
        if not name.endswith(".md"):
            continue
        if name == "MEMORY.md" and not include_index:
            continue
        out.append(parse_memory(os.path.join(memory_dir, name)))
    return out


def find_issues(memories):
    keys = {}
    for m in memories:
        keys.setdefault(m["key"], []).append(os.path.basename(m["path"]))
    known = set(keys)
    issues = []
    issues.extend(
        f"duplicate key '{k}' from: {', '.join(files)} (last import wins)"
        for k, files in keys.items()
        if len(files) > 1
    )
    for m in memories:
        if not m["had_name"]:
            issues.append(f"{os.path.basename(m['path'])}: no `name` in frontmatter; "
                          f"key derived from filename ('{m['key']}')")
        issues.extend(
            f"{os.path.basename(m['path'])}: [[{link}]] has no matching memory in this batch"
            for link in m["links"]
            if link not in known
        )
    return issues


def beads_ready(project_dir):
    bd = shutil.which("bd")
    if not bd:
        return False, "bd not on PATH"
    beads = shutil.which("beads")
    if not beads:
        return False, "beads not on PATH"
    if os.path.realpath(bd) != os.path.realpath(beads):
        return False, (f"bd and beads are different binaries "
                       f"({os.path.realpath(bd)} vs {os.path.realpath(beads)})")
    if not os.path.isdir(os.path.join(project_dir, ".beads")):
        return False, f"no .beads/ directory in {project_dir}"
    return True, "ready"


def bd_command(actor, key, content):
    cmd = ["bd"]
    if actor:
        cmd += ["--actor", actor]
    cmd += ["remember", "--key", key, content]
    return cmd


def print_plan(memories, issues, project_dir):
    print(f"Plan: import {len(memories)} memor{'y' if len(memories) == 1 else 'ies'} "
          f"into beads at {os.path.join(project_dir, '.beads')}\n")
    width = max((len(m["key"]) for m in memories), default=3)
    for m in memories:
        size = len(m["content"].encode("utf-8"))
        summary = m["description"] or m["content"].splitlines()[-1][:60] if m["content"] else ""
        print(f"  {m['key']:<{width}}  {m['type']:<9}  {size:>6}B  {summary}")
    if issues:
        print("\nIssues to note:")
        for it in issues:
            print(f"  - {it}")
    print("\nDry run: nothing was written. Re-run with --apply to write, "
          "or --script to emit a script first.")


def emit_script(memories, actor, project_dir):
    print("#!/usr/bin/env bash")
    print("set -euo pipefail")
    print(f"cd {shq(os.path.abspath(project_dir))}")
    for m in memories:
        actor_part = f"--actor {shq(actor)} " if actor else ""
        print(f"bd {actor_part}remember --key {shq(m['key'])} "
              f"\"$(cat {shq(os.path.abspath(m['path']))})\"")


def shq(s):
    return "'" + s.replace("'", "'\\''") + "'"


def apply(memories, actor, project_dir, delete_source):
    ok, fail = 0, 0
    for m in memories:
        try:
            r = subprocess.run(bd_command(actor, m["key"], m["content"]),
                               cwd=project_dir, capture_output=True, text=True)
        except OSError as e:
            print(f"  FAIL {m['key']}: {e}", file=sys.stderr)
            fail += 1
            continue
        if r.returncode == 0:
            print(f"  ok   {m['key']}")
            ok += 1
            if delete_source:
                try:
                    os.remove(m["path"])
                    print(f"       deleted {m['path']}")
                except OSError as e:
                    print(f"       could not delete {m['path']}: {e}", file=sys.stderr)
        else:
            print(f"  FAIL {m['key']}: {r.stderr.strip() or r.stdout.strip()}", file=sys.stderr)
            fail += 1
    print(f"\n{ok} imported, {fail} failed.")
    return 1 if fail else 0


def main():
    p = argparse.ArgumentParser(description="Import file-based auto-memory into beads.")
    p.add_argument("memory_dir", help="the .../memory directory to import from")
    p.add_argument("--project-dir", default=os.getcwd(),
                   help="project root containing .beads/ (default: current dir)")
    p.add_argument("--apply", action="store_true", help="write entries with bd remember")
    p.add_argument("--script", action="store_true", help="emit a runnable bash script instead")
    p.add_argument("--actor", default="", help="value for bd's --actor audit flag")
    p.add_argument("--delete-source", action="store_true",
                   help="with --apply, delete each source file whose import succeeded")
    p.add_argument("--include-index", action="store_true", help="also import MEMORY.md")
    args = p.parse_args()

    if not os.path.isdir(args.memory_dir):
        p.error(f"not a directory: {args.memory_dir}")
    memories = collect(args.memory_dir, args.include_index)
    if not memories:
        print(f"No memory files found in {args.memory_dir}")
        return 0
    issues = find_issues(memories)

    if args.script:
        emit_script(memories, args.actor, args.project_dir)
        return 0
    if args.apply:
        ready, why = beads_ready(args.project_dir)
        if not ready:
            print(f"beads not ready: {why}", file=sys.stderr)
            return 1
        return apply(memories, args.actor, args.project_dir, args.delete_source)

    print_plan(memories, issues, args.project_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
