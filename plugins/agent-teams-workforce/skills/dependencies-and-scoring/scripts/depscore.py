#!/usr/bin/env python3
"""Dependencies and scoring — the deterministic half, over the tracker graph.

ONE operation: recalculate the dependency edges and the WSJF scores. Its SCOPE is the only
thing that varies, and the scope is read off the tracker and the material-change queue,
never off a flag somebody set:

* nothing carries a score yet -> the scope is everything, every Epic and every Task;
* something changed -> the scope is what that change reached, which is the Epics the
  declarations name plus anything that arrived unscored, and their Tasks with them.

An Epic in scope is recalculated together with its Tasks, always, in one loop. Nothing is
skipped because it already carries a score: a score is a function of a graph that moves,
and an in-scope item is recomputed and overwritten every time.

    scope         what this pass covers, and why each item is in it
    snapshot      the tracker as a graph, which is what the reasoning pass reads
    validate      prove a proposed edge set is applicable before anything is written
    apply-edges   apply the DIFF through `bd dep`, never touching a hand-made edge
    score         recalculate the Epics in scope and their Tasks together
    changes       the declarations waiting for a pass, and the ledger that drains them

Every command prints ONE JSON object on stdout and names the tracker source it read. The
commands write; there is no dry run, because a run costs the same either way.

These are the skill's internals. A person runs the command; the skill runs these.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import beadgraph
from beadgraph import Bead, Graph, GraphError, split_ids
from edgeset import SequencingError, apply_edges, read_edges, validate
from materialchanges import QueueError, queue
from scoring import score

#: Set on an Epic by the elaboration pipeline. Carried in the snapshot because the
#: reasoning pass reads it. Eligibility itself is NOT decided here: it is dependencies and
#: blockers, `ops/sdlc-automation/nextwork.py` is the one implementation, and a second copy
#: here would drift from it.
ELAB_KEY = "elaboration_state"


# ------------------------------------------------------------------------------------
# Scope — read off the tracker and the queue, never off a flag
# ------------------------------------------------------------------------------------


def _epic_for(graph: Graph, ident: str) -> Bead | None:
    """The Epic an id belongs to, whether the id is the Epic's own or one beneath it.

    Args:
        graph: The tracker graph.
        ident: A bead id named by a declaration.

    Returns:
        The Epic, or None when the id is not in the tracker.
    """
    bead = graph.beads.get(ident)
    if bead is None:
        return None
    return bead if bead.kind == "epic" else graph.epic_of(bead.id)


def resolve_scope(graph: Graph, directory: Path | None) -> dict:
    """Decide what this pass covers, and say why each Epic is in it.

    Args:
        graph: The tracker graph.
        directory: The repository holding the run artifacts, or None for the working dir.

    Returns:
        The scope kind (`everything`, `changed` or `none`), the Epic ids it covers with a
        reason each, and the decision ids the pending declarations named.
    """
    pending = queue(directory)["pending"]
    open_epics = [e for e in graph.of_kind("epic") if not e.closed]
    if not any(e.metadata.get("wsjf") for e in open_epics):
        return {
            "scope": "everything",
            "why": "no open Epic carries a score, so nothing has been calculated yet",
            "epics": [{"id": e.id, "reason": "nothing is scored yet"} for e in open_epics],
            "decisionIds": sorted({i for d in pending for i in d["decisionIds"]}),
        }

    reached: dict[str, set[str]] = {}
    for declaration in pending:
        anchor = declaration["epic"]
        if anchor in graph.beads:
            reached.setdefault(anchor, set()).add(
                f"a material change was declared by its run ({declaration['path']})"
            )
        for ident in declaration["suspectedImpact"]:
            epic = _epic_for(graph, ident)
            if epic is not None:
                reached.setdefault(epic.id, set()).add(f"a declaration named {ident} as impacted")
    for epic in open_epics:
        if not epic.metadata.get("wsjf"):
            reached.setdefault(epic.id, set()).add("the Epic carries no score")
    for task in graph.of_kind("task"):
        if task.closed or task.metadata.get("wsjf"):
            continue
        epic = graph.epic_of(task.id)
        if epic is not None and not epic.closed:
            reached.setdefault(epic.id, set()).add("a Task beneath it carries no score")

    epics = [{"id": i, "reason": "; ".join(sorted(reached[i]))} for i in sorted(reached)]
    return {
        "scope": "changed" if epics else "none",
        "why": "the declarations and the unscored items name these Epics"
        if epics
        else "everything is scored and nothing has declared a material change",
        "epics": epics,
        "decisionIds": sorted({i for d in pending for i in d["decisionIds"]}),
    }


def scope_ids(graph: Graph, directory: Path | None, chosen: str | None) -> list[str]:
    """The Epic ids a command acts on: the ones named, or the resolved scope.

    Args:
        graph: The tracker graph.
        directory: The repository holding the run artifacts.
        chosen: A comma-separated Epic id list from the caller, or None.

    Returns:
        The Epic ids in scope, in id order.
    """
    if chosen:
        return sorted(set(split_ids(chosen)))
    return [e["id"] for e in resolve_scope(graph, directory)["epics"]]


# ------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------


def snapshot(
    graph: Graph, *, kinds: tuple[str, ...], include_closed: bool, epics: list[str] | None
) -> dict:
    """Every bead of the wanted kinds with its lineage, blockers and scoring metadata.

    Args:
        graph: The tracker graph.
        kinds: The issue types to include.
        include_closed: True to include finished work.
        epics: Restrict to these Epics and what hangs beneath them, or None for all.

    Returns:
        The beads and a count per kind.
    """

    def epic_id(bead: Bead) -> str | None:
        if bead.kind == "epic":
            return bead.id
        epic = graph.epic_of(bead.id)
        return epic.id if epic else None

    def render(bead: Bead) -> dict:
        return {
            "id": bead.id,
            "title": bead.title,
            "kind": bead.kind,
            "status": bead.status,
            "parent": bead.parent,
            "epic": epic_id(bead),
            "blockers": list(bead.blockers),
            "ownedBlockers": list(bead.owned_blockers),
            "elaborationState": bead.metadata.get(ELAB_KEY),
            "wsjf": bead.metadata.get("wsjf"),
            "wsjfSize": bead.metadata.get("wsjf_size"),
            "wsjfUbv": bead.metadata.get("wsjf_ubv"),
            "wsjfTc": bead.metadata.get("wsjf_tc"),
            "description": bead.description or None,
        }

    wanted = set(epics) if epics else None
    beads = [
        render(b)
        for b in graph.of_kind(*kinds)
        if (include_closed or not b.closed) and (wanted is None or epic_id(b) in wanted)
    ]
    return {"beads": beads, "counts": {k: sum(1 for b in beads if b["kind"] == k) for k in kinds}}


def build_parser() -> argparse.ArgumentParser:
    """The command line: one subcommand per deterministic step.

    Returns:
        The parser.
    """
    # `-C` is accepted on either side of the subcommand: it is the argument most likely to
    # be typed in the wrong place, and refusing it there buys nothing.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-C",
        "--directory",
        type=Path,
        default=argparse.SUPPRESS,
        help="run `bd` from this repository",
    )
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scope", help="what this pass covers, and why", parents=[common])

    snap = sub.add_parser(
        "snapshot", help="the tracker as a graph, for the reasoning pass", parents=[common]
    )
    snap.add_argument("--kinds", default="epic,story,task")
    snap.add_argument("--with-description", action="store_true")
    snap.add_argument("--include-closed", action="store_true")
    snap.add_argument("--epics", default=None, help="restrict to these Epics; omit for the scope")

    val = sub.add_parser("validate", help="check a proposed edge set", parents=[common])
    val.add_argument("--edges", type=Path, required=True, help="edge file, or `-` for stdin")

    app = sub.add_parser(
        "apply-edges", help="apply an edge diff through `bd dep`", parents=[common]
    )
    app.add_argument("--edges", type=Path, required=True, help="edge file, or `-` for stdin")
    app.add_argument("--epics", default=None, help="the scope; omit for the whole portfolio")

    sco = sub.add_parser(
        "score", help="recalculate the Epics in scope and their Tasks", parents=[common]
    )
    sco.add_argument("--epics", default=None, help="the scope; omit for the resolved scope")

    # A DECLARED change, never an inferred one. See `materialchanges` for why the queue is
    # a directory of files an agent wrote rather than anything derived from file state.
    mc = sub.add_parser(
        "changes",
        help="declarations waiting for a pass; --drain records them as acted on",
        parents=[common],
    )
    mc.add_argument(
        "--drain", action="store_true", help="record the pending declarations as acted on"
    )
    return parser


def run(args: argparse.Namespace) -> dict:
    """Dispatch one subcommand and return the object to print.

    Args:
        args: The parsed command line.

    Returns:
        The payload to print as JSON.
    """
    # The queue is read off disk and needs no tracker, so it answers before the graph is
    # built — a pass asks "is there anything to do" far more often than it does anything.
    if args.command == "changes":
        return {"command": args.command} | queue(args.directory, drain=args.drain)
    graph = beadgraph.load(
        args.directory, with_description=getattr(args, "with_description", False)
    )
    head = {"source": graph.source, "warnings": graph.warnings, "command": args.command}
    if args.command == "scope":
        return head | resolve_scope(graph, args.directory)
    if args.command == "snapshot":
        epics = split_ids(args.epics) if args.epics else None
        return head | snapshot(
            graph,
            kinds=tuple(split_ids(args.kinds)),
            include_closed=args.include_closed,
            epics=epics,
        )
    if args.command == "validate":
        return head | validate(graph, read_edges(args.edges))
    if args.command == "apply-edges":
        scope = set(split_ids(args.epics)) if args.epics else None
        return head | apply_edges(graph, read_edges(args.edges), args.directory, scope)
    return head | score(graph, args.directory, scope_ids(graph, args.directory, args.epics))


def main(argv: list[str] | None = None) -> int:
    """Entry point. Prints one JSON object; exit 2 means the command refused.

    Args:
        argv: The command line, or None for `sys.argv`.

    Returns:
        The process exit status.
    """
    args = build_parser().parse_args(argv)
    args.directory = getattr(args, "directory", None)
    try:
        payload = run(args)
    except (SequencingError, GraphError, QueueError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"error": str(exc), "command": args.command}, indent=2))
        return 2
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
