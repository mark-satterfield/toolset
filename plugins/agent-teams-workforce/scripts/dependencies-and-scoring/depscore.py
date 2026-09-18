#!/usr/bin/env python3
"""Dependencies and scoring — the deterministic half, over the tracker graph.

The `dependencies-and-scoring` workflow runs these in order. Every judged step between
them is an agent; everything here is code.

    query         what this run must judge and whether the sequencer runs, with the
                  fingerprints that decide it
    judge-input   the whole portfolio at one level, as one judging session reads it
    snapshot      the tracker as a graph, which is what the sequencer reads
    validate      prove a proposed edge set is applicable before anything is written
    apply-edges   apply the edge DIFF through `bd dep`, never touching a hand-made edge,
                  and record which Epic content the sequencer read
    record        write judged values with the fingerprint they were judged from
    score         recompute every Epic's and Task's WSJF and write what changed

Every command prints ONE JSON object on stdout and names the tracker source it read. With
`--out FILE` the full object is written to FILE and stdout carries only its `summary`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import beadgraph
from beadgraph import Bead, Graph, GraphError, split_ids
from edgeset import SequencingError, apply_edges, read_edges, validate
from scoring import ScoringError, judge_input, plan, record, score

#: Set on an Epic by the elaboration pipeline. Carried in the snapshot because the
#: sequencer reads it.
ELAB_KEY = "elaboration_state"


def snapshot(
    graph: Graph,
    *,
    kinds: tuple[str, ...],
    include_closed: bool,
    epics: list[str] | None,
) -> dict:
    """Every bead of the wanted kinds with its lineage, blockers and elaboration state.

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
            "description": bead.description or None,
        }

    wanted = set(epics) if epics else None
    beads = [
        render(b)
        for b in graph.of_kind(*kinds)
        if (include_closed or not b.closed) and (wanted is None or epic_id(b) in wanted)
    ]
    counts = {k: sum(1 for b in beads if b["kind"] == k) for k in kinds}
    return {"beads": beads, "counts": counts, "summary": counts}


def _read_json(path: Path) -> dict:
    """Read a JSON object from a file.

    Args:
        path: The file.

    Returns:
        The object.

    Raises:
        ScoringError: The file does not hold a JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"{path} does not hold a JSON object"
        raise ScoringError(msg)
    return payload


def _judgments(path: Path | None) -> list[dict]:
    """The per-item scores from a judging session's output file.

    Args:
        path: The rubric-shaped output (`{"scores": [...]}`), or None when nothing was
            judged at that level.

    Returns:
        The score records.
    """
    if path is None:
        return []
    scores = _read_json(path).get("scores") or []
    return [s for s in scores if isinstance(s, dict)]


def build_parser() -> argparse.ArgumentParser:
    """The command line: one subcommand per deterministic step.

    Returns:
        The parser.
    """
    # `-C` and `--out` are accepted on either side of the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-C",
        "--directory",
        type=Path,
        default=argparse.SUPPRESS,
        help="run `bd` from this repository",
    )
    common.add_argument(
        "--out",
        type=Path,
        default=argparse.SUPPRESS,
        help="write the full result here and print only its summary",
    )
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    que = sub.add_parser(
        "query", help="what this run judges, and whether it sequences", parents=[common]
    )
    que.add_argument(
        "--all",
        action="store_true",
        help="judge every judged input and re-derive the edges, whatever the fingerprints say",
    )

    jin = sub.add_parser(
        "judge-input", help="the portfolio one judging session reads", parents=[common]
    )
    jin.add_argument("--plan", type=Path, required=True, help="the `query` output")
    jin.add_argument("--level", choices=("epic", "task"), required=True)

    snap = sub.add_parser(
        "snapshot", help="the tracker as a graph, for the sequencer", parents=[common]
    )
    snap.add_argument("--kinds", default="epic,story,task")
    snap.add_argument("--with-description", action="store_true")
    snap.add_argument("--include-closed", action="store_true")
    snap.add_argument("--epics", default=None, help="restrict to these Epics")

    val = sub.add_parser("validate", help="check a proposed edge set", parents=[common])
    val.add_argument(
        "--edges", type=Path, required=True, help="edge file, or `-` for stdin"
    )

    app = sub.add_parser(
        "apply-edges", help="apply an edge diff through `bd dep`", parents=[common]
    )
    app.add_argument(
        "--edges", type=Path, required=True, help="edge file, or `-` for stdin"
    )
    app.add_argument("--plan", type=Path, required=True, help="the `query` output")

    rec = sub.add_parser(
        "record", help="write judged values with their fingerprints", parents=[common]
    )
    rec.add_argument("--plan", type=Path, required=True, help="the `query` output")
    rec.add_argument("--epics", type=Path, default=None, help="the Epic judgments")
    rec.add_argument("--tasks", type=Path, default=None, help="the Task size judgments")

    sub.add_parser(
        "score",
        help="recompute every Epic and Task score and write what changed",
        parents=[common],
    )
    return parser


def run(args: argparse.Namespace) -> dict:
    """Dispatch one subcommand and return the object to print.

    Args:
        args: The parsed command line.

    Returns:
        The payload to print as JSON.
    """
    descriptions = args.command in ("query", "judge-input") or getattr(
        args, "with_description", False
    )
    graph = beadgraph.load(args.directory, with_description=descriptions)
    head = {"source": graph.source, "warnings": graph.warnings, "command": args.command}
    if args.command == "query":
        return head | plan(graph, everything=args.all)
    if args.command == "judge-input":
        return head | judge_input(graph, _read_json(args.plan), args.level)
    if args.command == "snapshot":
        epics = split_ids(args.epics) if args.epics else None
        return head | snapshot(
            graph,
            kinds=tuple(split_ids(args.kinds)),
            include_closed=args.include_closed,
            epics=epics,
        )
    if args.command == "validate":
        report = validate(graph, read_edges(args.edges))
        return (
            head
            | report
            | {"summary": {"ok": report["ok"], "edges": report["edgeCount"]}}
        )
    if args.command == "apply-edges":
        the_plan = _read_json(args.plan)
        result = apply_edges(
            graph, read_edges(args.edges), args.directory, the_plan["fingerprints"]
        )
        summary = {
            key: result.get(key)
            for key in ("applied", "added", "removed", "unchanged", "sequencedRecorded")
        }
        if not result["applied"]:
            summary["validation"] = result["validation"]
        return head | result | {"summary": summary}
    if args.command == "record":
        judgments = {"epic": _judgments(args.epics), "task": _judgments(args.tasks)}
        return head | record(graph, _read_json(args.plan), judgments, args.directory)
    return head | score(graph, args.directory)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Prints one JSON object; exit 2 means the command refused.

    Args:
        argv: The command line, or None for `sys.argv`.

    Returns:
        The process exit status.
    """
    args = build_parser().parse_args(argv)
    args.directory = getattr(args, "directory", None)
    out = getattr(args, "out", None)
    try:
        payload = run(args)
    except (
        SequencingError,
        ScoringError,
        GraphError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        print(json.dumps({"error": str(exc), "command": args.command}, indent=2))
        return 2
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        payload = {
            "command": args.command,
            "out": str(out),
            "warnings": payload.get("warnings", []),
            "summary": payload.get("summary", {}),
        }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
