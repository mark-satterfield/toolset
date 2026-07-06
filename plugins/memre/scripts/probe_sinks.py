#!/usr/bin/env python3
"""
probe-sinks: report which recording backends are USABLE here — the CAN axis.

record-observation decides where a recordable thing goes by combining two axes:

  SHOULD  does AGENTS.md / CLAUDE.md / a loaded rule or memory tell us to use a
          backend? Read from context by the agent — never by this script.
  CAN     is that backend actually available? For the command-line backends,
          that is what this script determines, deterministically.

Backends reported (JSON on stdout, keyed by name):

  beads   issues + optional memory. Usable when `bd` is on PATH, `bd` and
          `beads` resolve to the SAME binary (so bd really is beads), and a
          .beads/ directory exists at the project root.
  github  issues. Usable when `gh` is on PATH, authenticated, and the repo's
          origin remote points at github.com.
  jira    issues. Usable when a `jira` CLI (jira-cli) is on PATH. Config is not
          verified — presence is reported, not a live connection.
  linear  issues. No command-line client exists to probe; availability is the
          presence of Linear MCP tools, which only the agent can see. Reported
          as can=null so the agent fills it from its own toolset.

MCP servers (Linear, Jira, GitHub) are invisible to a shell probe. When a
backend's CLI is absent but its MCP tools ARE present in the agent's context,
that backend is still usable — the record-issue and record-memory skills tell the
agent to count MCP presence as CAN. This script reports only what a shell can prove.

Each backend entry is {"can": bool|null, "kind": "cli"|"mcp", "detail": str}.

  --text   print a human summary instead of JSON.
  --dir D  treat D as the project root (default: git root, else CWD).

Stdlib only. Never writes anything; exit code is always 0 (the report is the
product, not the exit status).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys


def _run(args):
    """Run a command, return (rc, stdout). rc is None if the binary is absent."""
    try:
        p = subprocess.run(args, capture_output=True, text=True)
        return p.returncode, p.stdout.strip()
    except FileNotFoundError:
        return None, ""


def project_root(cli_dir):
    if cli_dir:
        return os.path.abspath(cli_dir)
    rc, out = _run(["git", "rev-parse", "--show-toplevel"])
    if rc == 0 and out:
        return out
    return os.getcwd()


def probe_beads(root):
    bd = shutil.which("bd")
    beads = shutil.which("beads")
    if not bd:
        return {"can": False, "kind": "cli", "detail": "bd not on PATH"}
    if not beads:
        return {"can": False, "kind": "cli",
                "detail": "bd is on PATH but beads is not — cannot confirm bd is beads"}
    if os.path.realpath(bd) != os.path.realpath(beads):
        return {"can": False, "kind": "cli",
                "detail": f"bd and beads are different binaries "
                          f"(bd -> {os.path.realpath(bd)}, beads -> {os.path.realpath(beads)})"}
    if not os.path.isdir(os.path.join(root, ".beads")):
        return {"can": False, "kind": "cli",
                "detail": f"bd is beads, but no .beads/ at project root ({root}) — run `bd init`"}
    return {"can": True, "kind": "cli", "detail": "bd is beads; .beads/ present"}


def probe_github():
    if not shutil.which("gh"):
        rc, out = _run(["git", "remote", "get-url", "origin"])
        if rc == 0 and "github.com" in out:
            return {"can": False, "kind": "cli",
                    "detail": "origin is a GitHub remote but gh is not on PATH"}
        return {"can": False, "kind": "cli", "detail": "gh not on PATH"}
    rc, _ = _run(["gh", "auth", "status"])
    if rc != 0:
        return {"can": False, "kind": "cli",
                "detail": "gh is on PATH but not authenticated — run `gh auth login`"}
    rc, out = _run(["git", "remote", "get-url", "origin"])
    if rc != 0 or not out:
        return {"can": False, "kind": "cli",
                "detail": "gh is authenticated but the repo has no origin remote"}
    if "github.com" not in out and "github" not in out:
        return {"can": False, "kind": "cli",
                "detail": f"gh is authenticated but origin is not GitHub ({out})"}
    return {"can": True, "kind": "cli", "detail": f"gh authenticated; origin {out}"}


def probe_jira():
    if not shutil.which("jira"):
        return {"can": False, "kind": "cli",
                "detail": "jira CLI not on PATH (config, if any, unverified)"}
    return {"can": True, "kind": "cli",
            "detail": "jira CLI on PATH; connection/config not verified by this probe"}


def probe_linear():
    return {"can": None, "kind": "mcp",
            "detail": "no CLI to probe — usable only if Linear MCP tools are in the "
                      "agent's context, which the agent checks"}


def probe(root):
    return {
        "project_root": root,
        "beads": probe_beads(root),
        "github": probe_github(),
        "jira": probe_jira(),
        "linear": probe_linear(),
    }


def as_text(report):
    lines = [f"project root: {report['project_root']}"]
    for name in ("beads", "github", "jira", "linear"):
        e = report[name]
        mark = {True: "ready", False: "no", None: "ask-agent (MCP)"}[e["can"]]
        lines.append(f"  {name:7} {mark:16} {e['detail']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Report usable recording backends (CAN axis)")
    ap.add_argument("--dir", help="project root (default: git root, else CWD)")
    ap.add_argument("--text", action="store_true", help="human summary instead of JSON")
    args = ap.parse_args()

    report = probe(project_root(args.dir))
    if args.text:
        print(as_text(report))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
