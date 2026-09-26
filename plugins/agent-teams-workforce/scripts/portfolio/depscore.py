#!/usr/bin/env python3
"""The Epic portfolio — the deterministic half, over the tracker graph.

The `dependency-assessment`, `task-dependency-assessment`, `wsjf-scoring` and `prd-to-spec`
workflows run these. Every judged step between them is an agent; everything here is code.

Dependency assessment has two scopes, and each command that takes a proposal covers exactly
one item: ONE Epic (`--epic`, `tracks` edges between Epics), or ONE Task created outside
elaboration (`--task`, `blocks` edges between Tasks). A Task elaboration wrote carries
`elab_key`, and its edges are elaboration's.

    assess-plan       the fingerprint of every open item of a level (`--level epic`, the
                      default, or `--level task`: the open Tasks with no `elab_key`), and
                      those not assessed as they stand (with `--since`, also those not
                      assessed since that instant)
    assess-context    one item's assessment material. `--epic`: every open Epic's PRD as a
                      file and an index of them. `--task`: every open Task as a file and an
                      index of them. Either way, every edge standing between the item and
                      another open bead of its level, with its recorded reason
    snapshot          the tracker as a graph
    validate          prove one item's edge proposal (`--edges` with `--epic` or `--task`)
                      is applicable before anything is written: every edge joins two beads
                      of the level, touches the item and carries a reason, and every owned
                      edge standing on it is kept or withdrawn with a reason
    withdraw-edge     withdraw one standing owned edge, recording why, so no later
                      assessment sets it again without answering that reason
    apply-edges       apply one item's edge DIFF (`--edges` with `--epic` or `--task`)
                      through `bd dep` as the level's type, never touching a hand-made edge
                      or an edge that does not touch the item, converting any owned edge
                      stored as the other level's type, recording each owned edge's reason
                      and the item content the assessment read. `--owned` proposes the owned
                      Epic edge set back, which only adds and converts, and proposes no edge
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
    elaboration-complete write an Epic's Stories and Tasks into beads from the documents its
                      elaboration saved (`--dir`), updating by `elab_key` what an earlier run
                      wrote, then finish it as `elaboration-finish` does, `done` when every
                      part landed. `--require-complete` refuses, writing nothing, while a
                      step that needs an agent is missing from the Epic's STEPS.md

Every command prints ONE JSON object on stdout and names the tracker source it read. With
`--out FILE` the full object is written to FILE and stdout carries only its `summary`.

`apply-edges`, `record`, `score` and the four `elaboration-` commands take `--dry-run`:
the command reads the tracker and computes exactly as it otherwise would, writes nothing,
and returns every write it would have made, in order, under `planned`.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import beadgraph
from beadgraph import Bead, Graph, GraphError, Writer, split_ids
from assesscontext import assess_context
from assesscontext import task_context
from edgeset import (
    ASSESSED_AT_KEY,
    ELAB_IDENTITY_KEY,
    SEEN_KEY,
    SequencingError,
    apply_edges,
    owned_edges,
    read_edges,
    read_withdrawn,
    scope_defect,
    validate,
    withdraw_edge,
)
from elaboration import LifecycleError, finish, release, start
from emitter import complete as complete_elaboration
from hierarchy import HierarchyError
from hierarchy import build as build_hierarchy
from scoring import ScoringError, judge_input, plan, record, rubric, score

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


def assess_plan(
    graph: Graph,
    *,
    epic: str | None,
    since: str | None = None,
    level: str = "epic",
    task: str | None = None,
) -> dict:
    """Every candidate's fingerprint at a level, and those not assessed as they now stand.

    At Epic level the candidates are the open Epics; at Task level, the open Tasks with no
    `elab_key`, because a Task elaboration wrote has its edges from elaboration. An item
    has been assessed as it stands when the `seq_content_hash` recorded on it matches its
    fingerprint. With `since`, an item whose `seq_assessed_at` is absent or earlier than
    that instant is unassessed too. The fingerprints are what `apply-edges --plan`
    records.

    Args:
        graph: The tracker graph, read with descriptions.
        epic: The one Epic to be assessed, or None. Epic level only.
        since: An ISO 8601 instant, or None.
        level: `epic` or `task`.
        task: The one Task to be assessed, or None. Task level only.

    Returns:
        The level, the fingerprints, the unassessed items, the scope, and a summary.

    Raises:
        SequencingError: A scope was given for the other level, the scope is not a
            candidate of its level, or `since` is not an ISO 8601 instant.
    """
    if level == "epic" and task is not None:
        msg = "--task needs --level task"
        raise SequencingError(msg)
    if level == "task" and epic is not None:
        msg = "--epic needs --level epic"
        raise SequencingError(msg)
    item = epic if level == "epic" else task
    if item is not None:
        defect = scope_defect(graph, item, level)
        if defect:
            raise SequencingError(defect)
    candidates = [
        b
        for b in graph.of_kind(level)
        if not b.closed and not (level == "task" and b.metadata.get(ELAB_IDENTITY_KEY))
    ]
    cutoff = _instant(since) if since is not None else None
    if since is not None and cutoff is None:
        msg = f"--since {since!r} is not an ISO 8601 instant"
        raise SequencingError(msg)
    prints = beadgraph.fingerprints(graph.records, beadgraph.SCOPE_JUDGING)

    def assessed(bead: Bead) -> bool:
        if bead.metadata.get(SEEN_KEY) != prints.get(bead.id):
            return False
        if cutoff is None:
            return True
        at = _instant(bead.metadata.get(ASSESSED_AT_KEY) or "")
        return at is not None and at >= cutoff

    unassessed = [c.id for c in candidates if not assessed(c)]
    summary: dict = {"level": level, "scope": item or "all"}
    if level == "epic":
        summary["openEpics"] = len(candidates)
    else:
        summary["openTasks"] = sum(1 for b in graph.of_kind("task") if not b.closed)
        summary["candidates"] = len(candidates)
    summary["unassessed"] = len(unassessed)
    summary["unassessedIds"] = sorted(unassessed)
    if since is not None:
        summary["since"] = since
    return {
        "level": level,
        "scope": item or "all",
        "since": since,
        "unassessed": unassessed,
        "fingerprints": {c.id: prints[c.id] for c in candidates if c.id in prints},
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


def _plan_fingerprints(path: Path) -> dict:
    """The fingerprint map an `assess-plan` output records.

    A bare `["fingerprints"]` raised KeyError, which is outside the refusal tuple `main`
    catches, so a malformed plan exited 1 with a traceback instead of the documented
    exit-2 JSON refusal.

    Args:
        path: The plan file.

    Returns:
        Bead id -> the fingerprint the plan was made at.

    Raises:
        ScoringError: The file is not an `assess-plan` output.
    """
    payload = _read_json(path)
    seen = payload.get("fingerprints")
    if not isinstance(seen, dict):
        msg = (
            f"{path} is not an `assess-plan` output: it holds no `fingerprints` object"
        )
        raise ScoringError(msg)
    return seen


def _entries(path: Path | None, key: str) -> list[dict]:
    """The per-item records from a judging session's output file.

    Args:
        path: The output (`{key: [...]}`), or None when there is none.
        key: The list's key: `scores`.

    Returns:
        The records.

    Raises:
        ScoringError: The file holds no `key` list. A typo'd top-level key used to yield
            zero records, and the items then surfaced in `record`'s `missing` list — the
            effect visible, the cause not.
    """
    if path is None:
        return []
    payload = _read_json(path)
    if key not in payload:
        msg = f"{path} holds no {key!r} list; its top-level keys are {', '.join(sorted(payload)) or 'none'}"
        raise ScoringError(msg)
    entries = payload.get(key) or []
    return [e for e in entries if isinstance(e, dict)]


def _dir_entries(
    directory: Path | None, key: str, unreadable: list[dict]
) -> list[dict]:
    """The per-item records from every output file in a directory.

    Each file is one judging session's output. A file that is not JSON, or holds no
    `key` list, costs only that session's items: it is listed in `unreadable` with the
    reason, its items surface in `record`'s `missing`, and every other file is read.

    Args:
        directory: The directory of session output files, or None when there is none.
        key: The list's key in each file.
        unreadable: Receives `{file, reason}` for each file that could not be read.

    Returns:
        The records, file by file in name order.
    """
    if directory is None:
        return []
    if not directory.is_dir():
        unreadable.append({"file": str(directory), "reason": "not a directory"})
        return []
    records: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        try:
            records += _entries(path, key)
        except (ScoringError, json.JSONDecodeError, OSError) as exc:
            unreadable.append({"file": str(path), "reason": str(exc)})
    return records


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

    asp = sub.add_parser(
        "assess-plan",
        help="fingerprints, and the Epics or Tasks not assessed as they stand",
        parents=[common],
    )
    asp.add_argument(
        "--level",
        choices=("epic", "task"),
        default="epic",
        help="`epic` (default), or `task`: the open Tasks created outside elaboration",
    )
    asp.add_argument("--epic", default=None, help="the one Epic to be assessed")
    asp.add_argument("--task", default=None, help="the one Task to be assessed")
    asp.add_argument(
        "--since",
        default=None,
        help="ISO 8601; an item not assessed since this instant is also unassessed",
    )

    acx = sub.add_parser(
        "assess-context",
        help="one Epic's or one Task's assessment material: corpus, index, standing edges",
        parents=[common],
    )
    acx.add_argument("--epic", default=None, help="the Epic to be assessed")
    acx.add_argument(
        "--task", default=None, help="the Task, created outside elaboration, to assess"
    )
    acx.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="write `prd/<id>.md` per open Epic (or `task/<id>.md` per open Task) "
        "and `index.md` here",
    )
    acx.add_argument(
        "--corpus-ready",
        action="store_true",
        help="`--epic` only: the PRD corpus and index in `--dir` were already written "
        "by this seeding; read them rather than writing them again",
    )

    snap = sub.add_parser("snapshot", help="the tracker as a graph", parents=[common])
    snap.add_argument("--kinds", default="epic,story,task")
    snap.add_argument("--with-description", action="store_true")
    snap.add_argument("--include-closed", action="store_true")
    snap.add_argument("--epics", default=None, help="restrict to these Epics")

    val = sub.add_parser(
        "validate",
        help="check one Epic's or one Task's edge proposal",
        parents=[common],
    )
    val.add_argument(
        "--edges", type=Path, required=True, help="edge file, or `-` for stdin"
    )
    val.add_argument("--epic", default=None, help="the one Epic the proposal covers")
    val.add_argument("--task", default=None, help="the one Task the proposal covers")

    app = sub.add_parser(
        "apply-edges",
        help="apply an edge diff through `bd dep`: `tracks` between Epics, "
        "`blocks` between Tasks",
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
        help="the one Epic the proposal covers; `--edges` takes this or `--task`",
    )
    app.add_argument(
        "--task",
        default=None,
        help="the one Task the proposal covers; `--edges` takes this or `--epic`",
    )
    _dry_run_flag(app)

    wdr = sub.add_parser(
        "withdraw-edge",
        help="withdraw one standing owned edge, recording why",
        parents=[common],
    )
    wdr.add_argument("--from", dest="blocker", required=True, help="the `from` end")
    wdr.add_argument("--to", dest="blocked", required=True, help="the `to` end")
    wdr.add_argument(
        "--reason", required=True, help="why the edge does not exist; recorded"
    )
    wdr.add_argument(
        "--by",
        default="review",
        help="what withdrew it, recorded with the reason (default: review)",
    )
    wdr.add_argument(
        "--level", choices=("epic", "task"), default="epic", help="`epic` (default)"
    )
    _dry_run_flag(wdr)

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
    efi.add_argument(
        "--sad-files",
        default="",
        help=(
            "the SAD files this run's architecture phase changed, comma-separated. With "
            "`--done` they are promoted to `lifecycle_state: effective`; without it they "
            "are ignored, because only a completed elaboration vouches for a SAD entry"
        ),
    )
    efi.add_argument(
        "--sad-root",
        default=None,
        help="the SAD directory every `--sad-files` path must sit under",
    )
    _dry_run_flag(efi)

    eco = sub.add_parser(
        "elaboration-complete",
        help="write an Epic's hierarchy from its saved documents, then finish it",
        parents=[common],
    )
    eco.add_argument("--epic", required=True, help="the Epic")
    eco.add_argument(
        "--dir", required=True, type=Path, help="the Epic's working directory"
    )
    eco.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="the root spec references are recorded relative to",
    )
    eco.add_argument(
        "--repos",
        default="",
        help="the span, comma-separated; absent, the saved ruling's",
    )
    eco.add_argument(
        "--steps",
        default=None,
        help="the completed steps, comma-separated; absent, the Epic's STEPS.md",
    )
    eco.add_argument(
        "--extra",
        type=Path,
        default=None,
        help="a saved {tasks: [...]} added beside them",
    )
    eco.add_argument(
        "--hold",
        default="",
        help="reasons that hold the Epic short of done, comma-separated",
    )
    eco.add_argument("--owner", default=None, help="the owner token the start returned")
    eco.add_argument("--sad-root", default=None, help="the SAD directory")
    eco.add_argument(
        "--require-complete",
        action="store_true",
        help="refuse, writing nothing, while a step that needs an agent is missing",
    )
    _dry_run_flag(eco)

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
    if args.command == "elaboration-complete":
        return run_complete(args)
    descriptions = args.command in (
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
    if command == "assess-plan":
        return head | assess_plan(
            graph, epic=args.epic, since=args.since, level=args.level, task=args.task
        )
    if command == "assess-context":
        if (args.epic is None) == (args.task is None):
            msg = "assess-context covers exactly one Epic or one Task: pass --epic or --task"
            raise SequencingError(msg)
        if args.task is not None:
            return head | task_context(graph, args.task, args.dir)
        return head | assess_context(
            graph, args.epic, args.dir, corpus_ready=args.corpus_ready
        )
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
    if command in ("validate", "apply-edges") and args.edges:
        if bool(args.epic) == bool(args.task):
            msg = (
                "an edge proposal covers exactly one Epic or one Task: "
                "pass --epic or --task"
            )
            raise SequencingError(msg)
    if command == "apply-edges" and args.owned and args.task:
        msg = "--owned repairs the owned Epic edges; it takes no --task"
        raise SequencingError(msg)
    level = "task" if getattr(args, "task", None) else "epic"
    item = args.task if level == "task" else getattr(args, "epic", None)
    if command == "validate":
        report = validate(
            graph, read_edges(args.edges), item, read_withdrawn(args.edges), level
        )
        return (
            head
            | report
            | {"summary": {"ok": report["ok"], "edges": report["edgeCount"]}}
        )
    if command == "apply-edges":
        seen = _plan_fingerprints(args.plan) if args.plan else {}
        proposal = owned_edges(graph) if args.owned else read_edges(args.edges)
        withdrawn = [] if args.owned else read_withdrawn(args.edges)
        result = apply_edges(graph, proposal, writer, seen, item, withdrawn, level)
        summary = {
            key: result.get(key)
            for key in (
                "applied",
                "dryRun",
                "level",
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
    if command == "withdraw-edge":
        return head | withdraw_edge(
            graph,
            args.blocker,
            args.blocked,
            args.reason,
            writer,
            args.by,
            args.level,
        )
    if command == "record":
        unreadable: list[dict] = []
        judgments = {
            "epic": _dir_entries(args.epics_dir, "scores", unreadable),
            "task": _dir_entries(args.tasks_dir, "scores", unreadable),
        }
        result = record(graph, _read_json(args.plan), judgments, writer)
        result["unreadable"] = unreadable
        result["summary"]["unreadable"] = len(unreadable)
        return head | result
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
            # Paths, not bead ids, so they are split here rather than by `split_ids`.
            sad_files=[p.strip() for p in str(args.sad_files).split(",") if p.strip()],
            sad_root=args.sad_root,
        )
    if command == "elaboration-release":
        return head | release(graph, writer, args.epic, owner=args.owner)
    return head | score(graph, writer)


def run_complete(args: argparse.Namespace) -> dict:
    """Write an Epic's hierarchy from its saved documents, then finish its elaboration.

    The documents are read before the tracker, so an Epic whose agent steps are not all
    complete is refused without reading the tracker when `--require-complete` is set.

    Args:
        args: The parsed command line.

    Returns:
        The payload to print as JSON.
    """
    hier = build_hierarchy(
        args.dir,
        args.project_root,
        repos=split_ids(args.repos) if args.repos else None,
        steps=[s.strip() for s in args.steps.split(",") if s.strip()]
        if args.steps is not None
        else None,
        extra=args.extra,
        holds=[h.strip() for h in args.hold.split(",") if h.strip()],
    )
    head = {"command": args.command, "epic": args.epic}
    if args.require_complete and hier.missing_steps:
        return head | {
            "ok": False,
            "refusal": {
                "code": "steps-missing",
                "reason": "a step that needs an agent is not on the Epic's STEPS.md",
                "missing": hier.missing_steps,
            },
            "summary": {"ok": False, "refused": "steps-missing"},
        }
    graph = beadgraph.load(args.directory, with_description=True)
    if graph.warnings:
        msg = f"the tracker was not read through bd, so nothing is written: {graph.warnings}"
        raise GraphError(msg)
    writer = Writer(args.directory, dry_run=args.dry_run)
    result = complete_elaboration(
        graph,
        writer,
        args.epic,
        hier,
        args.project_root,
        owner=args.owner,
        sad_root=args.sad_root,
        reload=lambda: beadgraph.load(args.directory, with_description=True),
    )
    return {"source": graph.source, "warnings": graph.warnings} | head | result


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
        GraphError,
        HierarchyError,
        rubric.WsjfError,
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
