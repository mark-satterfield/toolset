#!/usr/bin/env python3
"""Work sequencing, deterministic half — the command line over the tracker graph.

Sequencing is a BATCH PASS over every Epic and every Task: it sets the dependency edges,
scores what the edges imply, and keeps both current as the tracker changes. The one part
that needs judgement — which Epic must be designed before which — happens in a reasoning
pass that emits an edge file. Everything here is set algebra and arithmetic over it.

    snapshot      the tracker as a graph, which is what the reasoning pass reads
    validate      prove a proposed edge set is applicable before anything is written
    apply-edges   apply the DIFF through `bd dep`, never touching a hand-made edge
    score-tasks   inherit Task value from its Epic and recompute Task WSJF
    rollup-epics  roll Epic job size up from its Tasks and recompute Epic WSJF
    eligibility   which Epics may be ELABORATED now, and why the rest may not
    material-changes  the declarations waiting for a pass, and the ledger that drains them

Every command prints ONE JSON object on stdout and names the tracker source it read.
Writes happen only with `--apply`; without it every command is a dry run reporting
exactly what it would do.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import beadgraph
from beadgraph import Bead, Graph, GraphError, split_ids
from edgeset import SequencingError, apply_edges, read_edges, validate
from materialchanges import QueueError, queue
from scoring import rollup_epics, score_tasks

#: Elaboration states an Epic may carry. A blocking Epic gates elaboration until `done`.
ELAB_READY = "ready"
ELAB_IN_PROGRESS = "in_progress"
ELAB_DONE = "done"
ELAB_KEY = "elaboration_state"


# ------------------------------------------------------------------------------------
# Eligibility — Epic edges gate ELABORATION, never building
# ------------------------------------------------------------------------------------


def epic_eligibility(graph: Graph) -> dict:
    """Which Epics may be elaborated now, and why the rest may not.

    A blocking Epic stays OPEN until its requirements are in production, so `bd ready`
    semantics are wrong here: the test is the blocker's `elaboration_state == done`.
    Ownership and leases are the provider's business, not this function's.
    """
    eligible: list[dict] = []
    held: list[dict] = []
    for epic in graph.of_kind("epic"):
        state = epic.metadata.get(ELAB_KEY, "")
        if epic.closed:
            continue
        if state not in (ELAB_READY, ELAB_IN_PROGRESS):
            held.append({"id": epic.id, "reason": f"elaboration_state={state or '(authoring)'}"})
            continue
        blocking = [
            b
            for b in epic.blockers
            if b in graph.beads and graph.beads[b].metadata.get(ELAB_KEY) != ELAB_DONE
        ]
        if blocking:
            held.append(
                {"id": epic.id, "reason": "blocking Epic not elaborated", "waitingOn": blocking}
            )
            continue
        eligible.append(
            {
                "id": epic.id,
                "elaborationState": state,
                "wsjf": epic.metadata.get("wsjf"),
                "title": epic.title,
            }
        )
    eligible.sort(key=lambda e: (-float(e["wsjf"] or 0), e["id"]))
    return {
        "eligible": eligible,
        "held": held,
        "unscored": [e["id"] for e in eligible if not e["wsjf"]],
        "taskEligibility": "Tasks use `bd ready` semantics; Epic edges never gate a Task",
    }


# ------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------


def snapshot(graph: Graph, *, kinds: tuple[str, ...], include_closed: bool) -> dict:
    """Every Epic, Story and Task with its lineage, blockers and scoring metadata."""

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

    beads = [render(b) for b in graph.of_kind(*kinds) if include_closed or not b.closed]
    return {"beads": beads, "counts": {k: sum(1 for b in beads if b["kind"] == k) for k in kinds}}


def build_parser() -> argparse.ArgumentParser:
    """The command line: one subcommand per deterministic step."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-C", "--directory", type=Path, default=None, help="run `bd` from this repository"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="the tracker as a graph, for the reasoning pass")
    snap.add_argument("--kinds", default="epic,story,task")
    snap.add_argument("--with-description", action="store_true")
    snap.add_argument("--include-closed", action="store_true")

    for name, helptext in (
        ("validate", "check a proposed edge set"),
        ("apply-edges", "apply an edge diff through `bd dep`"),
    ):
        cmd = sub.add_parser(name, help=helptext)
        cmd.add_argument("--edges", type=Path, required=True, help="edge file, or `-` for stdin")
        if name == "apply-edges":
            cmd.add_argument("--apply", action="store_true", help="write; omit for a dry run")

    for name, helptext in (
        ("score-tasks", "inherit Task value from its Epic and recompute Task WSJF"),
        ("rollup-epics", "roll Epic job size up from its Tasks and recompute Epic WSJF"),
    ):
        cmd = sub.add_parser(name, help=helptext)
        cmd.add_argument("--apply", action="store_true", help="write; omit for a dry run")

    sub.add_parser("eligibility", help="which Epics may be elaborated now, and why not")

    # A DECLARED change, never an inferred one. See `materialchanges` for why the queue is
    # a directory of files an agent wrote rather than anything derived from file state.
    mc = sub.add_parser(
        "material-changes", help="declarations waiting for a pass; --drain records them as acted on"
    )
    mc.add_argument(
        "--drain", action="store_true", help="record the pending declarations as acted on"
    )
    return parser


def run(args: argparse.Namespace) -> dict:
    """Dispatch one subcommand and return the object to print."""
    # The queue is read off disk and needs no tracker, so it answers before the graph is
    # built — a pass asks "is there anything to do" far more often than it does anything.
    if args.command == "material-changes":
        return {"command": args.command} | queue(args.directory, drain=args.drain)
    graph = beadgraph.load(
        args.directory, with_description=getattr(args, "with_description", False)
    )
    head = {"source": graph.source, "warnings": graph.warnings, "command": args.command}
    if args.command == "snapshot":
        return head | snapshot(
            graph, kinds=tuple(split_ids(args.kinds)), include_closed=args.include_closed
        )
    if args.command == "validate":
        return head | validate(graph, read_edges(args.edges))
    if args.command == "apply-edges":
        return head | apply_edges(graph, read_edges(args.edges), args.directory, apply=args.apply)
    if args.command == "score-tasks":
        return head | score_tasks(graph, args.directory, apply=args.apply)
    if args.command == "rollup-epics":
        return head | rollup_epics(graph, args.directory, apply=args.apply)
    return head | epic_eligibility(graph)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Prints one JSON object; exit 2 means the command refused."""
    args = build_parser().parse_args(argv)
    try:
        payload = run(args)
    except (SequencingError, GraphError, QueueError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"error": str(exc), "command": args.command}, indent=2))
        return 2
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
