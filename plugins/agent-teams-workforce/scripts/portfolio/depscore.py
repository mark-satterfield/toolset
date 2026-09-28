#!/usr/bin/env python3
"""The deterministic Epic-portfolio commands over the beads graph.

    assess-plan          fingerprints of the open Epics (or Tasks with no `elab_key`) and
                         those not assessed as they stand, or not since `--since`
    assess-context       one Epic's or Task's corpus, index and standing edges
    snapshot             the tracker as a graph
    validate             check one Epic's or Task's edge proposal
    withdraw-edge        withdraw one owned edge, recording the reason
    apply-edges          apply one Epic's or Task's edge diff through `bd dep`
    score-plan           what a scoring run judges
    judge-input          the items one level judges, and its judging sessions
    record               write judged values with their fingerprints
    score                recompute every WSJF and write what changed
    elaboration-start    mark one Epic `in_progress` when it may be elaborated
    elaboration-finish   score an Epic and its Tasks; `--done` sets it done
    elaboration-release  clear a run's owner token from an Epic
    write-story          write one repository's Story under an Epic from its saved document
    plan-tasks           one Story's saved Tasks in build order with their keys; no `bd` call
    write-task           write ONE Task of a Story and its edges to the Story's Tasks
    plan-task-edges      the saved Task edges between an Epic's Stories, checked; no `bd` call
    write-task-edges     write ONE Task's edges to Tasks in the Epic's other Stories

Every command prints one JSON object. With `--out FILE` the full object is written to FILE
and stdout carries only its `summary`. `--dry-run` computes, writes nothing, and returns the
writes under `planned`.
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
    validate,
    withdraw_edge,
)
from beadwrite import (
    plan_story_tasks,
    plan_task_edges,
    write_story,
    write_task,
    write_task_edges,
)
from elaboration import LifecycleError, finish, release, start
from hierarchy import HierarchyError
from scoring import ScoringError, judge_input, plan, record, rubric, score

ELAB_KEY = "elaboration_state"


def snapshot(
    graph: Graph,
    *,
    kinds: tuple[str, ...],
    include_closed: bool,
    epics: list[str] | None,
) -> dict:
    """Every bead of the wanted kinds with its lineage, dependencies and elaboration state.

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

    Candidates are the open Epics, or the open Tasks with no `elab_key`. An item is
    unassessed when its `seq_content_hash` differs from its fingerprint or, with `since`,
    when its `seq_assessed_at` is absent or earlier than `since`.

    Args:
        graph: The tracker graph, read with descriptions.
        epic: The one Epic to be assessed, or None. Epic level only.
        since: An ISO 8601 instant, or None; an unparseable value is ignored.
        level: `epic` or `task`.
        task: The one Task to be assessed, or None. Task level only.

    Returns:
        The level, the fingerprints, the unassessed items, the scope, and a summary.
    """
    item = epic if level == "epic" else task
    candidates = [
        b
        for b in graph.of_kind(level)
        if not b.closed and not (level == "task" and b.metadata.get(ELAB_IDENTITY_KEY))
    ]
    cutoff = _instant(since) if since is not None else None
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
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _plan_fingerprints(path: Path) -> dict:
    """The fingerprint map an `assess-plan` output records.

    Args:
        path: The plan file.

    Returns:
        Bead id -> the fingerprint the plan was made at; empty when the file has none.
    """
    return _read_json(path).get("fingerprints") or {}


def _entries(path: Path | None, key: str) -> list[dict]:
    """The per-item records from a judging session's output file.

    Args:
        path: The output (`{key: [...]}`), or None when there is none.
        key: The list's key: `scores`.

    Returns:
        The records.
    """
    if path is None:
        return []
    entries = _read_json(path).get(key) or []
    return [e for e in entries if isinstance(e, dict)]


def _dir_entries(
    directory: Path | None, key: str, unreadable: list[dict]
) -> list[dict]:
    """The per-item records from every `*.json` file in a directory.

    Args:
        directory: The directory of session output files, or None when there is none.
        key: The list's key in each file.
        unreadable: Receives `{file, reason}` for each file that could not be read.

    Returns:
        The records, file by file in name order.
    """
    if directory is None:
        return []
    records: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        try:
            records += _entries(path, key)
        except (AttributeError, json.JSONDecodeError, OSError) as exc:
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
        help="score the Epic and its Tasks; `--done` marks it done",
        parents=[common],
    )
    efi.add_argument("--epic", required=True, help="the Epic whose Tasks were written")
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
            "the SAD files this run's architecture phase changed, comma-separated; with "
            "`--done` they are promoted to `lifecycle_state: effective`"
        ),
    )
    efi.add_argument(
        "--sad-root",
        default=None,
        help="the SAD directory every `--sad-files` path must sit under",
    )
    _dry_run_flag(efi)

    wst = sub.add_parser(
        "write-story",
        help="write one repository's Story under an Epic from its saved story-<slug>.json",
        parents=[common],
    )
    wst.add_argument("--epic", required=True, help="the Epic")
    wst.add_argument(
        "--dir", required=True, type=Path, help="the Epic's working directory"
    )
    wst.add_argument("--slug", required=True, help="the repository's artifact slug")
    wst.add_argument("--repo", required=True, help="the repository the Story covers")
    wst.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="the root artifact paths are recorded relative to",
    )
    _dry_run_flag(wst)

    pta = sub.add_parser(
        "plan-tasks",
        help="one Story's saved Tasks in build order with their keys; runs no `bd` command",
        parents=[common],
    )
    wta = sub.add_parser(
        "write-task",
        help="write ONE Task of a Story from its saved tasks-<slug>.json",
        parents=[common],
    )
    wta.add_argument("--story", required=True, help="the Story the Task sits under")
    wta.add_argument(
        "--key", required=True, help="the Task's key, as plan-tasks lists it"
    )
    for task_parser in (pta, wta):
        task_parser.add_argument(
            "--dir", required=True, type=Path, help="the Epic's working directory"
        )
        task_parser.add_argument(
            "--slug", required=True, help="the Story's repository slug"
        )
        task_parser.add_argument("--repo", required=True, help="the Story's repository")
        task_parser.add_argument(
            "--project-root",
            type=Path,
            default=None,
            help="the root spec references are recorded relative to",
        )
    _dry_run_flag(wta)

    pte = sub.add_parser(
        "plan-task-edges",
        help="the saved task-deps.json edges between an Epic's Stories, checked; "
        "runs no `bd` command",
        parents=[common],
    )
    wte = sub.add_parser(
        "write-task-edges",
        help="write ONE Task's saved task-deps.json edges to Tasks in other Stories",
        parents=[common],
    )
    wte.add_argument("--epic", required=True, help="the Epic")
    wte.add_argument("--task", required=True, help="the Task, as S<i>-<local key>")
    for edge_parser in (pte, wte):
        edge_parser.add_argument(
            "--dir", required=True, type=Path, help="the Epic's working directory"
        )
        edge_parser.add_argument(
            "--repos",
            required=True,
            help="the span, comma-separated, in its ruled order",
        )
    _dry_run_flag(wte)

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

    Raises:
        SequencingError: An edge proposal names neither or both of `--epic` and `--task`.
        GraphError: A write command's tracker was not read through `bd`.
    """
    command = args.command
    head = {"command": command}
    if command == "plan-tasks":
        return head | plan_story_tasks(
            args.dir, slug=args.slug, repo=args.repo, root=args.project_root
        )
    if command == "plan-task-edges":
        return head | plan_task_edges(args.dir, split_ids(args.repos))
    writer = Writer(args.directory, dry_run=getattr(args, "dry_run", False))
    if command == "write-task":
        return head | write_task(
            writer,
            args.story,
            args.dir,
            slug=args.slug,
            repo=args.repo,
            key=args.key,
            root=args.project_root,
        )
    writes = command in {"write-story", "write-task-edges"}
    descriptions = command in {
        "write-story",
        "assess-plan",
        "assess-context",
        "score-plan",
        "judge-input",
        "elaboration-finish",
    } or getattr(args, "with_description", False)
    graph = beadgraph.load(args.directory, with_description=descriptions)
    head = {"source": graph.source, "warnings": graph.warnings, "command": command}
    if writes and graph.warnings:
        msg = f"the tracker was not read through bd, so nothing is written: {graph.warnings}"
        raise GraphError(msg)
    if command == "write-story":
        return head | write_story(
            graph,
            writer,
            args.epic,
            args.dir,
            slug=args.slug,
            repo=args.repo,
            root=args.project_root,
        )
    if command == "write-task-edges":
        return head | write_task_edges(
            graph, writer, args.epic, args.dir, split_ids(args.repos), args.task
        )
    if command == "assess-plan":
        return head | assess_plan(
            graph, epic=args.epic, since=args.since, level=args.level, task=args.task
        )
    if command == "assess-context":
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
            owner=args.owner,
            done=args.done,
            sad_files=[p.strip() for p in str(args.sad_files).split(",") if p.strip()],
            sad_root=args.sad_root,
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
