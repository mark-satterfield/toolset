#!/usr/bin/env python3
"""The Epic portfolio — the deterministic half, over the tracker graph.

The `epic-summaries`, `dependency-assessment`, `wsjf-scoring` and `prd-to-spec` workflows
run these. Every judged step between them is an agent; everything here is code.

    summary-plan      the open Epics whose summary is missing or whose fingerprint no longer matches
    record-summaries  write summaries with the fingerprint they were written from
    portfolio         every open Epic with its summary and edges, as one document
    assess-plan       every open Epic's fingerprint, and those not assessed as they stand
                      (with `--since`, also those not assessed since that instant)
    assess-context    one Epic's assessment material: every open Epic's PRD as a file, an
                      index of them, and every edge standing between the Epic and another
                      open Epic with its recorded reason
    snapshot          the tracker as a graph
    validate          prove one Epic's edge proposal (`--edges` with `--epic`) is
                      applicable before anything is written: every edge touches the
                      Epic and carries a reason, and every owned edge standing on it is
                      kept or withdrawn with a reason
    apply-edges       apply one Epic's edge DIFF (`--edges` with `--epic`) through `bd dep`
                      as `tracks` edges, never touching a hand-made edge or an edge that
                      does not touch the Epic, converting any owned edge stored as another
                      type, recording each owned edge's reason and the Epic content the
                      assessment read. `--owned` proposes the owned edge set back, which
                      only adds and converts, and proposes no edge
    score-plan        what this scoring run judges, with the fingerprints that decide it
    judge-input       the items one level judges, with the PRD of each Epic to judge as a
                      file, and the sessions: one Epic each, or one Epic's Tasks each
    record            write judged values with the fingerprint they were judged from, from
                      every judgment file in `--epics-dir` and `--tasks-dir`
    score             recompute every Epic's and Task's WSJF and write what changed
    elaboration-start whether one Epic may be elaborated now: open, scored, every Epic it
                      depends on elaborated, and ready or in progress with no other
                      owner. When it may, mark it `in_progress` under an owner token
    elaboration-finish after an Epic's Tasks are written: fingerprint the Task sizes the run
                      judged, score the Epic and its Tasks, and with `--done` set its elaboration to `done`
    elaboration-release clear a run's owner token from an Epic it started and did not
                      finish; the Epic stays `in_progress`

Every command prints ONE JSON object on stdout and names the tracker source it read. With
`--out FILE` the full object is written to FILE and stdout carries only its `summary`.

`record-summaries`, `apply-edges`, `record`, `score` and the three `elaboration-` commands
take `--dry-run`: the command reads the tracker and
computes exactly as it otherwise would, writes nothing, and returns every write it would
have made, in order, under `planned`.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import beadgraph
from beadgraph import Bead, Graph, GraphError, Writer, split_ids
from assesscontext import assess_context
from edgeset import (
    ASSESSED_AT_KEY,
    SEEN_KEY,
    SequencingError,
    apply_edges,
    owned_edges,
    read_edges,
    read_withdrawn,
    validate,
)
from elaboration import LifecycleError, finish, release, start
from scoring import ScoringError, judge_input, plan, record, score
from summaries import (
    SummaryError,
    portfolio,
    record_summaries,
    summary_plan,
)

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
    """Every bead of the wanted kinds with its lineage, dependencies and elaboration state.

    `blockers` lists what each bead depends on, read from the edge type of its level:
    `tracks` edges for an Epic, `blocks` edges for a Task. A Story only groups Tasks and
    carries no dependency edge of its own.

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
            "blockers": list(bead.depends_on),
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


def _instant(text: str) -> datetime | None:
    """An ISO 8601 instant, or None when the text is not one.

    Args:
        text: The text; a trailing `Z` means UTC, and an instant with no offset is UTC.

    Returns:
        The instant, timezone-aware.
    """
    try:
        value = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def assess_plan(graph: Graph, *, epic: str | None, since: str | None = None) -> dict:
    """Every open Epic's fingerprint, and the Epics not assessed as they now stand.

    An Epic has been assessed as it stands when the `seq_content_hash` recorded on it
    matches its fingerprint. With `since`, an Epic whose `seq_assessed_at` is absent or
    earlier than that instant is unassessed too. The fingerprints are what
    `apply-edges --plan` records.

    Args:
        graph: The tracker graph, read with descriptions.
        epic: The one Epic to be assessed, or None for every open Epic.
        since: An ISO 8601 instant, or None.

    Returns:
        The fingerprints, the unassessed Epics, the scope, and a summary.

    Raises:
        SequencingError: `epic` is not an open Epic, or `since` is not an ISO 8601
            instant.
    """
    epics = [b for b in graph.of_kind("epic") if not b.closed]
    if epic is not None and epic not in {b.id for b in epics}:
        msg = f"{epic} is not an open Epic"
        raise SequencingError(msg)
    cutoff = _instant(since) if since is not None else None
    if since is not None and cutoff is None:
        msg = f"--since {since!r} is not an ISO 8601 instant"
        raise SequencingError(msg)
    prints = beadgraph.fingerprints(graph.records)

    def assessed(bead: Bead) -> bool:
        if bead.metadata.get(SEEN_KEY) != prints.get(bead.id):
            return False
        if cutoff is None:
            return True
        at = _instant(bead.metadata.get(ASSESSED_AT_KEY) or "")
        return at is not None and at >= cutoff

    unassessed = [e.id for e in epics if not assessed(e)]
    summary = {
        "scope": epic or "all",
        "openEpics": len(epics),
        "unassessed": len(unassessed),
        "unassessedIds": sorted(unassessed),
    }
    if since is not None:
        summary["since"] = since
    return {
        "scope": epic or "all",
        "since": since,
        "unassessed": unassessed,
        "fingerprints": {e.id: prints[e.id] for e in epics if e.id in prints},
        "summary": summary,
    }


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


def _entries(path: Path | None, key: str) -> list[dict]:
    """The per-item records from a judging or summarizing session's output file.

    Args:
        path: The output (`{key: [...]}`), or None when there is none.
        key: The list's key: `scores` or `summaries`.

    Returns:
        The records.
    """
    if path is None:
        return []
    entries = _read_json(path).get(key) or []
    return [e for e in entries if isinstance(e, dict)]


def _dir_entries(directory: Path | None, key: str) -> list[dict]:
    """The per-item records from every output file in a directory.

    Args:
        directory: The directory of session output files, or None when there is none.
        key: The list's key in each file.

    Returns:
        The records, file by file in name order.

    Raises:
        ScoringError: `directory` is not a directory.
    """
    if directory is None:
        return []
    if not directory.is_dir():
        msg = f"{directory} is not a directory"
        raise ScoringError(msg)
    return [e for path in sorted(directory.glob("*.json")) for e in _entries(path, key)]


def _dry_run_flag(parser: argparse.ArgumentParser) -> None:
    """Give a writing subcommand its `--dry-run` flag.

    Args:
        parser: The subcommand's parser.
    """
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write nothing; return every write this command would make under `planned`",
    )


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

    spl = sub.add_parser(
        "summary-plan",
        help="the open Epics whose summary is due",
        parents=[common],
    )
    spl.add_argument("--epics", default=None, help="restrict to these Epics")
    spl.add_argument(
        "--prd-dir", type=Path, default=None, help="write each due Epic's PRD here"
    )

    rsu = sub.add_parser(
        "record-summaries",
        help="write summaries with their fingerprints",
        parents=[common],
    )
    rsu.add_argument(
        "--plan", type=Path, required=True, help="the `summary-plan` output"
    )
    rsu.add_argument(
        "--summaries",
        type=Path,
        action="append",
        required=True,
        help="a summarizing session's output; repeatable",
    )
    _dry_run_flag(rsu)

    por = sub.add_parser(
        "portfolio",
        help="every open Epic with its summary, as one document",
        parents=[common],
    )
    por.add_argument(
        "--markdown", type=Path, required=True, help="the document to write"
    )
    por.add_argument(
        "--prd-dir", type=Path, default=None, help="write every open Epic's PRD here"
    )

    asp = sub.add_parser(
        "assess-plan",
        help="fingerprints, and the Epics not assessed as they stand",
        parents=[common],
    )
    asp.add_argument("--epic", default=None, help="the one Epic to be assessed")
    asp.add_argument(
        "--since",
        default=None,
        help="ISO 8601; an Epic not assessed since this instant is also unassessed",
    )

    acx = sub.add_parser(
        "assess-context",
        help="one Epic's assessment material: the PRD corpus, its index, standing edges",
        parents=[common],
    )
    acx.add_argument("--epic", required=True, help="the Epic to be assessed")
    acx.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="write `prd/<id>.md` per open Epic and `index.md` here",
    )

    snap = sub.add_parser("snapshot", help="the tracker as a graph", parents=[common])
    snap.add_argument("--kinds", default="epic,story,task")
    snap.add_argument("--with-description", action="store_true")
    snap.add_argument("--include-closed", action="store_true")
    snap.add_argument("--epics", default=None, help="restrict to these Epics")

    val = sub.add_parser(
        "validate", help="check one Epic's edge proposal", parents=[common]
    )
    val.add_argument(
        "--edges", type=Path, required=True, help="edge file, or `-` for stdin"
    )
    val.add_argument(
        "--epic", default=None, help="the one Epic the proposal covers (required)"
    )

    app = sub.add_parser(
        "apply-edges",
        help="apply an Epic edge diff through `bd dep` as `tracks` edges",
        parents=[common],
    )
    source = app.add_mutually_exclusive_group(required=True)
    source.add_argument("--edges", type=Path, help="edge file, or `-` for stdin")
    source.add_argument(
        "--owned",
        action="store_true",
        help="propose every owned edge back: adds absent ones, converts mistyped ones",
    )
    app.add_argument(
        "--plan",
        type=Path,
        default=None,
        help="the `assess-plan` output; its fingerprints record what the sequencer read",
    )
    app.add_argument(
        "--epic",
        default=None,
        help="the one Epic the proposal covers; required with `--edges`",
    )
    _dry_run_flag(app)

    que = sub.add_parser(
        "score-plan", help="what this scoring run judges", parents=[common]
    )
    que.add_argument(
        "--all",
        action="store_true",
        help="include items that already have a value",
    )
    que.add_argument(
        "--rejudge",
        action="store_true",
        help="judge again the existing values of the items included",
    )
    que.add_argument(
        "--only",
        default=None,
        help="judge only these open Epics and Tasks; the arithmetic is unaffected",
    )

    jin = sub.add_parser(
        "judge-input", help="the items to judge at one level", parents=[common]
    )
    jin.add_argument("--plan", type=Path, required=True, help="the `score-plan` output")
    jin.add_argument("--level", choices=("epic", "task"), required=True)
    jin.add_argument(
        "--prd-dir", type=Path, default=None, help="write each Epic to judge's PRD here"
    )

    rec = sub.add_parser(
        "record", help="write judged values with their fingerprints", parents=[common]
    )
    rec.add_argument("--plan", type=Path, required=True, help="the `score-plan` output")
    rec.add_argument(
        "--epics-dir",
        type=Path,
        default=None,
        help="a directory whose every `*.json` file holds Epic judgments",
    )
    rec.add_argument(
        "--tasks-dir",
        type=Path,
        default=None,
        help="a directory whose every `*.json` file holds Task size judgments",
    )
    _dry_run_flag(rec)

    sco = sub.add_parser(
        "score",
        help="recompute every Epic and Task score and write what changed",
        parents=[common],
    )
    _dry_run_flag(sco)

    est = sub.add_parser(
        "elaboration-start",
        help="whether one Epic may be elaborated now; when it may, mark it in progress",
        parents=[common],
    )
    est.add_argument("--epic", required=True, help="the Epic to elaborate")
    est.add_argument(
        "--owner", default=None, help="the run's owner token; absent, a fresh one"
    )
    est.add_argument(
        "--reclaim",
        action="store_true",
        help="the run owning an in-progress Epic is established as not live",
    )
    _dry_run_flag(est)

    efi = sub.add_parser(
        "elaboration-finish",
        help="fingerprint judged Task sizes, score the Epic and its Tasks, mark it done",
        parents=[common],
    )
    efi.add_argument("--epic", required=True, help="the Epic whose Tasks were written")
    efi.add_argument(
        "--judged",
        default="",
        help="the Tasks whose size this run judged from their current content",
    )
    efi.add_argument("--owner", default=None, help="the owner token the start returned")
    efi.add_argument(
        "--done",
        action="store_true",
        help="set the Epic's `elaboration_state` to `done`",
    )
    _dry_run_flag(efi)

    erl = sub.add_parser(
        "elaboration-release",
        help="clear a run's owner token from an Epic it did not finish",
        parents=[common],
    )
    erl.add_argument("--epic", required=True, help="the Epic the run started")
    erl.add_argument(
        "--owner", required=True, help="the owner token the start returned"
    )
    _dry_run_flag(erl)
    return parser


def run(args: argparse.Namespace) -> dict:
    """Dispatch one subcommand and return the object to print.

    Args:
        args: The parsed command line.

    Returns:
        The payload to print as JSON.
    """
    descriptions = args.command in (
        "summary-plan",
        "portfolio",
        "assess-plan",
        "assess-context",
        "score-plan",
        "judge-input",
        "elaboration-finish",
    ) or getattr(args, "with_description", False)
    graph = beadgraph.load(args.directory, with_description=descriptions)
    head = {"source": graph.source, "warnings": graph.warnings, "command": args.command}
    writer = Writer(args.directory, dry_run=getattr(args, "dry_run", False))
    command = args.command
    if command == "summary-plan":
        epics = split_ids(args.epics) if args.epics else None
        return head | summary_plan(graph, epics=epics, prd_dir=args.prd_dir)
    if command == "record-summaries":
        entries = [e for path in args.summaries for e in _entries(path, "summaries")]
        return head | record_summaries(graph, _read_json(args.plan), entries, writer)
    if command == "portfolio":
        return head | portfolio(graph, prd_dir=args.prd_dir, markdown=args.markdown)
    if command == "assess-plan":
        return head | assess_plan(graph, epic=args.epic, since=args.since)
    if command == "assess-context":
        return head | assess_context(graph, args.epic, args.dir)
    if command == "score-plan":
        only = split_ids(args.only) if args.only else None
        return head | plan(graph, include_all=args.all, rejudge=args.rejudge, only=only)
    if command == "judge-input":
        return head | judge_input(
            graph, _read_json(args.plan), args.level, prd_dir=args.prd_dir
        )
    if command == "snapshot":
        epics = split_ids(args.epics) if args.epics else None
        return head | snapshot(
            graph,
            kinds=tuple(split_ids(args.kinds)),
            include_closed=args.include_closed,
            epics=epics,
        )
    if command in ("validate", "apply-edges") and args.edges and not args.epic:
        msg = "an edge proposal covers exactly one Epic: pass --epic"
        raise SequencingError(msg)
    if command == "validate":
        report = validate(
            graph, read_edges(args.edges), args.epic, read_withdrawn(args.edges)
        )
        return (
            head
            | report
            | {"summary": {"ok": report["ok"], "edges": report["edgeCount"]}}
        )
    if command == "apply-edges":
        seen = _read_json(args.plan)["fingerprints"] if args.plan else {}
        proposal = owned_edges(graph) if args.owned else read_edges(args.edges)
        withdrawn = [] if args.owned else read_withdrawn(args.edges)
        result = apply_edges(graph, proposal, writer, seen, args.epic, withdrawn)
        summary = {
            key: result.get(key)
            for key in (
                "applied",
                "dryRun",
                "scope",
                "added",
                "converted",
                "removed",
                "unchanged",
                "sequencedRecorded",
                "reasonsRecorded",
            )
        }
        summary["withdrawn"] = len(result.get("withdrawn") or [])
        summary["plannedWrites"] = len(result.get("planned") or [])
        if not result["validation"]["ok"]:
            summary["validation"] = result["validation"]
        return head | result | {"summary": summary}
    if command == "record":
        judgments = {
            "epic": _dir_entries(args.epics_dir, "scores"),
            "task": _dir_entries(args.tasks_dir, "scores"),
        }
        return head | record(graph, _read_json(args.plan), judgments, writer)
    if command == "elaboration-start":
        return head | start(
            graph, writer, args.epic, owner=args.owner, reclaim=args.reclaim
        )
    if command == "elaboration-finish":
        return head | finish(
            graph,
            writer,
            args.epic,
            judged=split_ids(args.judged),
            owner=args.owner,
            done=args.done,
        )
    if command == "elaboration-release":
        return head | release(graph, writer, args.epic, owner=args.owner)
    return head | score(graph, writer)


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
        LifecycleError,
        SummaryError,
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
