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
    arch-approve         set `lifecycle_state: effective` on the architecture files an
                         integration changed or created that its conformance review covered;
                         a file the review does not name stays as it is; no `bd` call
    arch-state           read the `lifecycle_state` of the architecture files a step relies on;
                         no `bd` call
    arch-constraints     fingerprint section 2 (the owner's constraints): each file's hash and
                         the folder's git status; `--keep` also copies it aside and names the
                         copy in `kept`; no `bd` call
    arch-constraints-restore
                         put section 2 back from the copy `arch-constraints --keep` made;
                         no `bd` call
    arch-snapshot        fingerprint every file of `arc42/`, `target/` and `built/`, so a step
                         measures what its sessions wrote; `--save FILE` also writes the
                         result to FILE and `--against FILE` (repeatable) reports the files
                         created, changed and deleted since that saved fingerprint; with either,
                         the per-file hashes stay on disk and are not printed; no `bd` call
    arch-built-remove    delete the `built/<element>/` files the effective version now matches
                         and commit the removal in the repository holding them; no `bd` call
    spec-ui-append       write the `ui` items' design sources (bundle build spec and Section
                         IDs, cds, or none) as the `## UI design sources` section of a saved
                         spec document; no `bd` call
    cds-bundles          list the single-artifact cds bundles in a packages directory, the newest
                         per kind and slug (an absent or empty directory lists none); with
                         --design-source, also select the design source a web-ui Task builds
                         with now; no `bd` call
    recon-facts          check a repository's saved detailing (`recon-<slug>.json`) against the
                         delta items placed in it and print only the facts the workflows branch
                         on (usable or not and why, the ids that make work, each `ui` work
                         item's design source, whether dependencies are current);
                         a file that cannot be read or parsed is an error; no `bd` call
    write-story          write one repository's Story under an Epic from its saved document
    plan-tasks           one Story's saved Tasks in build order with their keys; no `bd` call
    add-tasks            merge a corrective pass into a Story's saved Tasks and detailing;
                         no `bd` call
    replace-tasks        delete a Story's unstarted Task beads before its Tasks are
                         decomposed again (an input upstream of them changed)
    write-task           write ONE Task of a Story and its edges to the Story's Tasks
    plan-task-edges      the saved Task edges between an Epic's Stories, checked; no `bd` call
    write-task-edges     write ONE Task's edges to Tasks in the Epic's other Stories
    write-all-task-edges write every Task's edges to Tasks in the Epic's other Stories
    closure-edges        the Task edges between Stories that the delta's `requires` relations
                         make (saved delta-items.json, recon-<slug>.json, tasks-<slug>.json),
                         and warnings where a required item has no Task, no open bead and is
                         not done; no `bd` call
    relay-read           print again the relay envelope of a result saved with `--relay FILE`,
                         re-running nothing; no `bd` call
    story-edges          derive and write the Story -> Story `blocks` edges from Epic order within
                         a repository and from Task edges between Stories in any repository;
                         a Story whose order is contradictory gets no edge written
                         `elaboration-finish` and a Task-level `apply-edges` run it after they write

Every command prints one JSON object. With `--out FILE` the full object is written to FILE
and stdout carries only its `summary`. With `--relay FILE` the full object is written to FILE
and stdout carries its relay envelope; `relay-read --relay FILE` prints that same envelope
again from FILE without re-running the command. The envelope, the relay file and the leading
command-line digest guard are relay.py's; this module imports them and restates none of them.
`--dry-run` computes, writes nothing, and returns the writes under `planned`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

import portfolio_path  # ruff: ignore[unused-import] - puts the beads-contract and artifact-handoff scripts on sys.path before the contract imports below.

# isort: split
import beadgraph
import edgeset
import relay
import wsjf as rubric
from architecture_artifacts import parse_conformance_result
from archstate import promote as approve_arch
from archstate import (
    remove_built,
    restore_constraints,
    snapshot_constraints,
    snapshot_tree,
    tree_diff,
)
from archstate import states as arch_states
from assesscontext import assess_context, task_context
from bead_metadata import (
    ELABORATION_DONE,
    KEY_ELAB_KEY,
    KEY_ELABORATION_STATE,
    KEY_SEQ_ASSESSED_AT,
    KEY_SEQ_CONTENT_HASH,
)
from beadgraph import Bead, Graph, GraphError, Writer, split_ids
from beadwrite import (
    add_corrective_tasks,
    closure_task_edges,
    plan_story_tasks,
    plan_task_edges,
    replace_tasks,
    write_all_task_edges,
    write_story,
    write_task,
    write_task_edges,
)
from cdsbundles import list_bundles, select_build
from contracts import JsonObject, JsonValue, json_object
from edgeset import (
    ApplyScope,
    Edge,
    SequencingError,
    apply_edges,
    owned_edges,
    read_edges,
    read_withdrawn,
    validate,
    withdraw_edge,
)
from elaboration import LifecycleError, finish, release, start
from hierarchy import HierarchyError, SpanFiles, SpanStories, StoryFiles, repo_slugs
from reconfacts import ReconError, recon_facts
from scoring import ScoringError, judge_input, plan, record, score
from scoringcontracts import Plan
from specui import SpecUiError, spec_ui_append
from storyedges import story_edges
from typeguard import CollectionCheckStrategy, check_type

if TYPE_CHECKING:
    from collections.abc import Callable


def snapshot(
    graph: Graph,
    *,
    kinds: tuple[str, ...],
    include_closed: bool,
    epics: list[str] | None,
) -> JsonObject:
    """Every bead of the wanted kinds with its lineage, dependencies and elaboration state.

    Args:
        graph: The tracker graph.
        kinds: The issue types to include.
        include_closed: True to include finished work.
        epics: Restrict to these Epics and what hangs beneath them, or None for all.

    Returns:
        The beads and a count per kind.

    Raises:
        TypeError: Arguments violate the declared input contract.

    """
    if (
        not isinstance(graph, Graph)
        or not isinstance(include_closed, bool)
        or not isinstance(kinds, tuple)
        or any(not isinstance(kind, str) for kind in kinds)
    ):
        message: str = "Invalid snapshot arguments"
        raise TypeError(message)
    if epics is not None and (not isinstance(epics, list) or any(not isinstance(epic, str) for epic in epics)):
        message = "Invalid snapshot epic selection"
        raise TypeError(message)
    wanted: set[str] | None
    beads: list[dict[str, JsonValue]]
    counts: dict[str, int]

    def epic_id(bead: Bead) -> str | None:
        epic: Bead | None
        if bead.kind == "epic":
            return bead.id
        epic = graph.epic_of(bead.id)
        return epic.id if epic else None

    def render(bead: Bead) -> JsonObject:
        return {
            "id": bead.id,
            "title": bead.title,
            "kind": bead.kind,
            "status": bead.status,
            "parent": bead.parent,
            "epic": epic_id(bead),
            "blockers": list(bead.depends_on),
            "ownedBlockers": list(bead.owned_blockers),
            "elaborationState": bead.metadata.get(KEY_ELABORATION_STATE),
            "description": bead.description or None,
        }

    wanted = set(epics) if epics else None
    beads = [
        render(b)
        for b in graph.of_kind(*kinds)
        if (include_closed or not b.closed) and (wanted is None or epic_id(b) in wanted)
    ]
    counts = {k: sum(1 for b in beads if b["kind"] == k) for k in kinds}
    return json_object({"beads": beads, "counts": counts, "summary": counts})


def _instant(text: str) -> datetime | None:
    """Parse an ISO 8601 instant, returning None for invalid text.

    Args:
        text: The text; a trailing `Z` means UTC, and an instant with no offset is UTC.

    Returns:
        The instant, timezone-aware.

    """
    value: datetime
    try:
        value = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def assess_plan(
    graph: Graph,
    *,
    epic: str | None,
    since: str | None = None,
    level: str = "epic",
    task: str | None = None,
) -> JsonObject:
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

    Raises:
        TypeError: Arguments violate the declared input contract.

    """
    if (
        not isinstance(graph, Graph)
        or not isinstance(level, str)
        or any(value is not None and not isinstance(value, str) for value in (epic, since, task))
    ):
        message: str = "Invalid assess_plan arguments"
        raise TypeError(message)
    item: str | None
    candidates: list[Bead]
    cutoff: datetime | None
    prints: dict[str, str]
    unassessed: list[str]
    item = epic if level == "epic" else task
    candidates = [
        b for b in graph.of_kind(level) if not b.closed and not (level == "task" and b.metadata.get(KEY_ELAB_KEY))
    ]
    cutoff = _instant(since) if since is not None else None
    prints = beadgraph.fingerprints(graph.records, beadgraph.SCOPE_JUDGING)

    def assessed(bead: Bead) -> bool:
        at: datetime | None
        if bead.metadata.get(KEY_SEQ_CONTENT_HASH) != prints.get(bead.id):
            return False
        if cutoff is None:
            return True
        at = _instant(bead.metadata.get(KEY_SEQ_ASSESSED_AT) or "")
        return at is not None and at >= cutoff

    unassessed = [c.id for c in candidates if not assessed(c)]
    summary: JsonObject = {"level": level, "scope": item or "all"}
    if level == "epic":
        summary["openEpics"] = len(candidates)
    else:
        summary["openTasks"] = sum(1 for b in graph.of_kind("task") if not b.closed)
        summary["candidates"] = len(candidates)
    summary["unassessed"] = len(unassessed)
    summary["unassessedIds"] = [str(item) for item in sorted(unassessed)]
    if since is not None:
        summary["since"] = since
    return {
        "level": level,
        "scope": item or "all",
        "since": since,
        "unassessed": [str(value) for value in unassessed],
        "fingerprints": {c.id: prints[c.id] for c in candidates if c.id in prints},
        "summary": summary,
    }


def _read_json(path: Path) -> JsonObject:
    """Read a JSON object from a file.

    Args:
        path: The file.

    Returns:
        The object.

    """
    return json_object(json.loads(path.read_text(encoding="utf-8")))


def _plan_fingerprints(path: Path) -> dict[str, str]:
    """Read the fingerprint map an `assess-plan` output records.

    Args:
        path: The plan file.

    Returns:
        Bead id -> the fingerprint the plan was made at; empty when the file has none.

    """
    return check_type(
        _read_json(path).get("fingerprints") or {},
        dict[str, str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


def _entries(path: Path | None, key: str) -> list[JsonObject]:
    """Read per-item records from a judging session's output file.

    Args:
        path: The output (`{key: [...]}`), or None when there is none.
        key: The list's key: `scores`.

    Returns:
        The records.

    """
    if path is None:
        return []
    entries: JsonValue = _read_json(path).get(key) or []
    return check_type(entries, list[JsonObject], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _dir_entries(
    directory: Path | None,
    key: str,
    unreadable: list[JsonObject],
) -> list[JsonObject]:
    """Read per-item records from every `*.json` file in a directory.

    Args:
        directory: The directory of session output files, or None when there is none.
        key: The list's key in each file.
        unreadable: Receives `{file, reason}` for each file that could not be read.

    Returns:
        The records, file by file in name order.

    """
    path: Path
    if directory is None:
        return []
    records: list[JsonObject] = []
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


class _Subcommands(Protocol):
    """The exact subcommand registration behavior used by this CLI."""

    # ruff: ignore[builtin-argument-shadowing] - argparse exposes this exact keyword.
    def add_parser(self, name: str, *, help: str, parents: list[argparse.ArgumentParser]) -> argparse.ArgumentParser:
        """Create a parser for one command."""
        ...


def _configure_command_2(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    sub.add_parser(
        "relay-read",
        help="print again the relay envelope of the result saved with --relay FILE; re-runs nothing; no `bd` call",
        parents=[common],
    )


def _configure_command_3(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    asp: argparse.ArgumentParser = sub.add_parser(
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


def _configure_command_4(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    acx: argparse.ArgumentParser = sub.add_parser(
        "assess-context",
        help="one Epic's or one Task's assessment material: corpus, index, standing edges",
        parents=[common],
    )
    acx.add_argument("--epic", default=None, help="the Epic to be assessed")
    acx.add_argument(
        "--task",
        default=None,
        help="the Task, created outside elaboration, to assess",
    )
    acx.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="write `prd/<id>.md` per open Epic (or `task/<id>.md` per open Task) and `index.md` here",
    )
    acx.add_argument(
        "--corpus-ready",
        action="store_true",
        help="`--epic` only: the PRD corpus and index in `--dir` were already written "
        "by this seeding; read them rather than writing them again",
    )


def _configure_command_5(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    snap: argparse.ArgumentParser = sub.add_parser("snapshot", help="the tracker as a graph", parents=[common])
    snap.add_argument("--kinds", default="epic,story,task")
    snap.add_argument("--with-description", action="store_true")
    snap.add_argument("--include-closed", action="store_true")
    snap.add_argument("--epics", default=None, help="restrict to these Epics")


def _configure_command_6(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    val: argparse.ArgumentParser = sub.add_parser(
        "validate",
        help="check one Epic's or one Task's edge proposal",
        parents=[common],
    )
    val.add_argument(
        "--edges",
        type=Path,
        required=True,
        help="edge file, or `-` for stdin",
    )
    val.add_argument("--epic", default=None, help="the one Epic the proposal covers")
    val.add_argument("--task", default=None, help="the one Task the proposal covers")


def _configure_command_7(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    source: argparse._MutuallyExclusiveGroup
    app: argparse.ArgumentParser = sub.add_parser(
        "apply-edges",
        help="apply an edge diff through `bd dep`: `tracks` between Epics, `blocks` between Tasks",
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


def _configure_command_8(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    wdr: argparse.ArgumentParser = sub.add_parser(
        "withdraw-edge",
        help="withdraw one standing owned edge, recording why",
        parents=[common],
    )
    wdr.add_argument("--from", dest="blocker", required=True, help="the `from` end")
    wdr.add_argument("--to", dest="blocked", required=True, help="the `to` end")
    wdr.add_argument(
        "--reason",
        required=True,
        help="why the edge does not exist; recorded",
    )
    wdr.add_argument(
        "--by",
        default="review",
        help="what withdrew it, recorded with the reason (default: review)",
    )
    wdr.add_argument(
        "--level",
        choices=("epic", "task"),
        default="epic",
        help="`epic` (default)",
    )
    _dry_run_flag(wdr)


def _configure_command_9(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    que: argparse.ArgumentParser = sub.add_parser(
        "score-plan",
        help="what this scoring run judges",
        parents=[common],
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


def _configure_command_10(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    jin: argparse.ArgumentParser = sub.add_parser(
        "judge-input",
        help="the items to judge at one level",
        parents=[common],
    )
    jin.add_argument("--plan", type=Path, required=True, help="the `score-plan` output")
    jin.add_argument("--level", choices=("epic", "task"), required=True)
    jin.add_argument(
        "--prd-dir",
        type=Path,
        default=None,
        help="write each Epic to judge's PRD here",
    )


def _configure_command_11(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    rec: argparse.ArgumentParser = sub.add_parser(
        "record",
        help="write judged values with their fingerprints",
        parents=[common],
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


def _configure_command_12(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    sco: argparse.ArgumentParser = sub.add_parser(
        "score",
        help="recompute every Epic and Task score and write what changed",
        parents=[common],
    )
    _dry_run_flag(sco)


def _configure_command_13(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    est: argparse.ArgumentParser = sub.add_parser(
        "elaboration-start",
        help="whether one Epic may be elaborated now; when it may, mark it in progress",
        parents=[common],
    )
    est.add_argument("--epic", required=True, help="the Epic to elaborate")
    est.add_argument(
        "--owner",
        default=None,
        help="the run's owner token; absent, a fresh one",
    )
    est.add_argument(
        "--reclaim",
        action="store_true",
        help="the run owning an in-progress Epic is established as not live",
    )
    _dry_run_flag(est)


def _configure_command_14(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    efi: argparse.ArgumentParser = sub.add_parser(
        "elaboration-finish",
        help="score the Epic and its Tasks; `--done` marks it done",
        parents=[common],
    )
    efi.add_argument("--epic", required=True, help="the Epic whose Tasks were written")
    efi.add_argument("--owner", default=None, help="the owner token the start returned")
    efi.add_argument(
        "--done",
        action="store_true",
        help=f"set the Epic's `{KEY_ELABORATION_STATE}` to `{ELABORATION_DONE}`",
    )
    _dry_run_flag(efi)


def _configure_command_15(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    wst: argparse.ArgumentParser = sub.add_parser(
        "write-story",
        help="write one repository's Story under an Epic from its saved story-<slug>.json",
        parents=[common],
    )
    wst.add_argument("--epic", required=True, help="the Epic")
    wst.add_argument(
        "--dir",
        required=True,
        type=Path,
        help="the Epic's working directory",
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


def _configure_command_16(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    task_parser: argparse.ArgumentParser
    pta: argparse.ArgumentParser = sub.add_parser(
        "plan-tasks",
        help="one Story's saved Tasks in build order with their keys; runs no `bd` command",
        parents=[common],
    )

    adt: argparse.ArgumentParser = sub.add_parser(
        "add-tasks",
        help="merge a corrective pass into a Story's saved Tasks and detailing; runs no `bd` command",
        parents=[common],
    )
    adt.add_argument(
        "--correction",
        required=True,
        type=Path,
        help="the accepted corrective pass, as the artifact-handoff skill's tasks-correction schema defines it",
    )

    wta: argparse.ArgumentParser = sub.add_parser(
        "write-task",
        help="write ONE Task of a Story from its saved tasks-<slug>.json",
        parents=[common],
    )
    wta.add_argument(
        "--epic",
        required=True,
        help="the Epic whose `story:<slug>` Story it sits under",
    )
    wta.add_argument(
        "--key",
        required=True,
        help="the Task's key, as plan-tasks lists it",
    )
    wta.add_argument(
        "--blocked-by-external",
        default="",
        help="Tasks of other Epics this Task is blocked by, comma-separated, beside the "
        "ones its saved blockedByExternal names",
    )

    rpt: argparse.ArgumentParser = sub.add_parser(
        "replace-tasks",
        help="delete a Story's unstarted Task beads before its Tasks are decomposed again",
        parents=[common],
    )
    rpt.add_argument(
        "--epic",
        required=True,
        help="the Epic whose `story:<slug>` Story the Tasks sit under",
    )
    rpt.add_argument(
        "--reason",
        required=True,
        help="which input upstream of the Tasks changed",
    )

    for task_parser in (pta, adt, wta, rpt):
        task_parser.add_argument(
            "--dir",
            required=True,
            type=Path,
            help="the Epic's working directory",
        )
        task_parser.add_argument(
            "--slug",
            required=True,
            help="the Story's repository slug",
        )
        task_parser.add_argument("--repo", required=True, help="the Story's repository")
        task_parser.add_argument(
            "--packages-dir",
            default=None,
            help="the packages directory every cds bundle a Task cites must sit in "
            "(default: the bundles the saved detailing cites, wherever they are)",
        )
        task_parser.add_argument(
            "--project-root",
            type=Path,
            default=None,
            help="the root spec references are recorded relative to",
        )
    _dry_run_flag(wta)
    _dry_run_flag(rpt)


def _configure_command_22(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    edge_parser: argparse.ArgumentParser
    pte: argparse.ArgumentParser = sub.add_parser(
        "plan-task-edges",
        help="the saved task-deps.json edges between an Epic's Stories, checked; runs no `bd` command",
        parents=[common],
    )

    wte: argparse.ArgumentParser = sub.add_parser(
        "write-task-edges",
        help="write ONE Task's saved task-deps.json edges to Tasks in other Stories",
        parents=[common],
    )
    wte.add_argument("--epic", required=True, help="the Epic")
    wte.add_argument("--task", required=True, help="the Task, as S<i>-<local key>")

    wae: argparse.ArgumentParser = sub.add_parser(
        "write-all-task-edges",
        help="write every Task's saved task-deps.json edges to Tasks in other Stories",
        parents=[common],
    )
    wae.add_argument("--epic", required=True, help="the Epic")
    wae.add_argument(
        "--also",
        default="",
        help="Tasks, as S<i>-<local key>, comma-separated, written even with no saved blocker",
    )

    cle: argparse.ArgumentParser = sub.add_parser(
        "closure-edges",
        help="the Task edges between Stories the delta's `requires` relations make, and "
        "warnings where a required item has no Task, no open bead and is not done; runs no "
        "`bd` command",
        parents=[common],
    )

    for edge_parser in (pte, wte, wae, cle):
        edge_parser.add_argument(
            "--dir",
            required=True,
            type=Path,
            help="the Epic's working directory",
        )
        edge_parser.add_argument(
            "--repos",
            required=True,
            help="the span, comma-separated, in its ruled order",
        )
    _dry_run_flag(wte)
    _dry_run_flag(wae)


def _configure_command_27(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    sed: argparse.ArgumentParser = sub.add_parser(
        "story-edges",
        help="derive and write the Story -> Story `blocks` edges",
        parents=[common],
    )
    _dry_run_flag(sed)


def _configure_command_28(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    erl: argparse.ArgumentParser = sub.add_parser(
        "elaboration-release",
        help="clear a run's owner token from an Epic it did not finish",
        parents=[common],
    )
    erl.add_argument("--epic", required=True, help="the Epic the run started")
    erl.add_argument(
        "--owner",
        required=True,
        help="the owner token the start returned",
    )
    _dry_run_flag(erl)


def _configure_command_29(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    aap: argparse.ArgumentParser = sub.add_parser(
        "arch-approve",
        help="set `lifecycle_state: effective` on the architecture files an approved "
        "architecture step covers; runs no `bd` command",
        parents=[common],
    )
    aap.add_argument(
        "--arch-files",
        required=True,
        help="the architecture files the integration changed or created, comma-separated",
    )
    aap.add_argument(
        "--reviewed-from",
        type=Path,
        default=None,
        help="instead of --reviewed-files: a saved integration conformance review (conformance schema), "
        "whose reviewed files are approved",
    )
    aap.add_argument(
        "--reviewed-files",
        default="",
        help="the files the conformance review checked and found conforming, comma-separated; only these are promoted",
    )
    aap.add_argument(
        "--arch-root",
        default=None,
        help="the architecture directory every `--arch-files` path must sit under",
    )
    _dry_run_flag(aap)


def _configure_command_30(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    acs: argparse.ArgumentParser = sub.add_parser(
        "arch-constraints",
        help="fingerprint section 2 of the effective architecture; writes nothing, runs no `bd` command",
        parents=[common],
    )
    acs.add_argument(
        "--arch-root",
        required=True,
        help="the architecture directory holding arc42/",
    )
    acs.add_argument(
        "--keep",
        action="store_true",
        help="copy section 2 to a new temporary directory, named in `kept`",
    )


def _configure_command_31(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    acr: argparse.ArgumentParser = sub.add_parser(
        "arch-constraints-restore",
        help="put section 2 back from the copy `arch-constraints --keep` made; runs no `bd` command",
        parents=[common],
    )
    acr.add_argument(
        "--arch-root",
        required=True,
        help="the architecture directory holding arc42/",
    )
    acr.add_argument(
        "--kept",
        required=True,
        help="the directory `arch-constraints --keep` named",
    )


def _configure_command_33(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    asn: argparse.ArgumentParser = sub.add_parser(
        "arch-snapshot",
        help="fingerprint every file of arc42/, target/ and built/; writes nothing but `--save`, runs no `bd` command",
        parents=[common],
    )
    asn.add_argument(
        "--arch-root",
        required=True,
        help="the architecture directory holding arc42/, target/ and built/",
    )
    asn.add_argument(
        "--save",
        type=Path,
        default=None,
        help="also write the full result to this file, for a resumed step",
    )
    asn.add_argument(
        "--against",
        type=Path,
        action="append",
        default=[],
        help="a fingerprint saved with --save; report the files created, changed and deleted since it (repeatable)",
    )
    asn.add_argument(
        "--counts",
        action="store_true",
        help="relay only the number of files created, changed and deleted per diff; the names stay in the relay file",
    )


def _configure_command_39(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    ast: argparse.ArgumentParser = sub.add_parser(
        "arch-state",
        help="read the `lifecycle_state` of architecture files; writes nothing, runs no `bd` command",
        parents=[common],
    )
    ast.add_argument(
        "--arch-files",
        required=True,
        help="the architecture files to read, comma-separated",
    )
    ast.add_argument(
        "--arch-root",
        default=None,
        help="the architecture directory every `--arch-files` path must sit under",
    )


def _configure_command_43(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    abr: argparse.ArgumentParser = sub.add_parser(
        "arch-built-remove",
        help="delete built/<element>/ files the effective version now matches and commit "
        "the removal; runs no `bd` command",
        parents=[common],
    )
    abr.add_argument(
        "--arch-root",
        required=True,
        help="the architecture directory holding built/",
    )
    abr.add_argument(
        "--files",
        required=True,
        help="the built files to remove, comma-separated",
    )
    abr.add_argument("--message", required=True, help="the commit message")


def _configure_command_45(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    sua: argparse.ArgumentParser = sub.add_parser(
        "spec-ui-append",
        help="write the ui items' design sources into a saved spec document; runs no `bd` command",
        parents=[common],
    )
    sua.add_argument("--doc", type=Path, required=True, help="the saved spec document")
    sua.add_argument(
        "--ui",
        type=Path,
        required=True,
        help="the saved UI design sources document (spec-<slug>.ui.json), whose `uiItems` are "
        "the artifact-handoff skill's recon schema `UiItem` rows",
    )


def _configure_command_46(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    cdb: argparse.ArgumentParser = sub.add_parser(
        "cds-bundles",
        help="the cds bundles a packages directory supplies; writes nothing, runs no `bd` command",
        parents=[common],
    )
    cdb.add_argument(
        "--packages-dir",
        default="",
        help="the packages directory; empty or absent supplies no bundle",
    )
    cdb.add_argument(
        "--design-source",
        default="",
        help="with --kind and --slug or --recorded-bundle: also select the design source a "
        "web-ui Task builds with now (bundle, cds or none, as its contract records it)",
    )
    cdb.add_argument("--kind", default="", help="the Task's artifact kind")
    cdb.add_argument("--slug", default="", help="the Task's artifact slug")
    cdb.add_argument(
        "--recorded-bundle",
        default="",
        help="the bundle the Task's contract records",
    )


def _configure_command_47(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    rcf: argparse.ArgumentParser = sub.add_parser(
        "recon-facts",
        help="the facts the workflows branch on from one repository's saved detailing; "
        "writes nothing, runs no `bd` command",
        parents=[common],
    )
    rcf.add_argument(
        "--file",
        type=Path,
        required=True,
        help="the saved detailing, recon-<slug>.json",
    )
    rcf.add_argument(
        "--items",
        required=True,
        help="the ids of the delta items placed in the repository, comma-separated",
    )


_COMMAND_CONFIGURATORS: tuple[Callable[[_Subcommands, argparse.ArgumentParser], None], ...] = (
    _configure_command_2,
    _configure_command_3,
    _configure_command_4,
    _configure_command_5,
    _configure_command_6,
    _configure_command_7,
    _configure_command_8,
    _configure_command_9,
    _configure_command_10,
    _configure_command_11,
    _configure_command_12,
    _configure_command_13,
    _configure_command_14,
    _configure_command_15,
    _configure_command_16,
    _configure_command_22,
    _configure_command_27,
    _configure_command_28,
    _configure_command_29,
    _configure_command_30,
    _configure_command_31,
    _configure_command_33,
    _configure_command_39,
    _configure_command_43,
    _configure_command_45,
    _configure_command_46,
    _configure_command_47,
)


def build_parser() -> argparse.ArgumentParser:
    """Build one subcommand per deterministic step.

    Returns:
        The parser.

    """
    common: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
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
    common.add_argument(
        "--relay",
        type=Path,
        default=argparse.SUPPRESS,
        help="write the full result here and print its relay view with a checksum",
    )
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    sub: _Subcommands = parser.add_subparsers(dest="command", required=True)

    configure: Callable[[_Subcommands, argparse.ArgumentParser], None]
    for configure in _COMMAND_CONFIGURATORS:
        configure(sub, common)
    return parser


def _required_text(value: str | Path | None) -> str:
    """Require the string variant of a command option.

    Returns:
        The supplied string.

    Raises:
        TypeError: The selected command did not supply text.

    """
    if not isinstance(value, str):
        message: str = "Required command option must be text"
        raise TypeError(message)
    return value


def _required_path(value: str | Path | None) -> Path:
    """Require the Path variant of a command option.

    Returns:
        The supplied path.

    Raises:
        TypeError: The selected command did not supply a path.

    """
    if not isinstance(value, Path):
        message: str = "Required command option must be a Path"
        raise TypeError(message)
    return value


@dataclass(frozen=True)
class _CommandOptions:
    """Immutable values parsed from the declared CLI actions."""

    command: str
    directory: Path | None
    out: Path | None
    relay: Path | None
    level: str | None
    epic: str | None
    task: str | None
    since: str | None
    dir: Path | None
    corpus_ready: bool
    kinds: str | None
    with_description: bool
    include_closed: bool
    epics: str | None
    edges: Path | None
    owned: bool
    plan: Path | None
    dry_run: bool
    blocker: str | None
    blocked: str | None
    reason: str | None
    by: str | None
    all: bool
    rejudge: bool
    only: str | None
    prd_dir: Path | None
    epics_dir: Path | None
    tasks_dir: Path | None
    owner: str | None
    reclaim: bool
    done: bool
    slug: str | None
    repo: str | None
    project_root: Path | None
    packages_dir: str | None
    correction: Path | None
    key: str | None
    blocked_by_external: str | None
    repos: str | None
    also: str | None
    arch_files: str | None
    reviewed_from: Path | None
    reviewed_files: str | None
    arch_root: str | None
    keep: bool
    kept: str | None
    save: Path | None
    against: list[Path]
    counts: bool
    files: Path | str | None
    message: str | None
    doc: Path | None
    ui: Path | None
    items: str | None
    design_source: str | None
    kind: str | None
    recorded_bundle: str | None
    file: Path | None


def _command_options(namespace: argparse.Namespace) -> _CommandOptions:
    """Validate argparse values at the CLI edge.

    Returns:
        The immutable options for the selected command.

    Raises:
        TypeError: An argument does not match its parser action type.

    """
    if not isinstance(namespace, argparse.Namespace):
        message: str = "Expected parsed CLI arguments"
        raise TypeError(message)
    return _CommandOptions(
        command=check_type(
            getattr(namespace, "command", None),
            str,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        directory=check_type(
            getattr(namespace, "directory", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        out=check_type(
            getattr(namespace, "out", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        relay=check_type(
            getattr(namespace, "relay", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        level=check_type(
            getattr(namespace, "level", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        epic=check_type(
            getattr(namespace, "epic", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        task=check_type(
            getattr(namespace, "task", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        since=check_type(
            getattr(namespace, "since", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        dir=check_type(
            getattr(namespace, "dir", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        corpus_ready=check_type(
            getattr(namespace, "corpus_ready", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        kinds=check_type(
            getattr(namespace, "kinds", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        with_description=check_type(
            getattr(namespace, "with_description", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        include_closed=check_type(
            getattr(namespace, "include_closed", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        epics=check_type(
            getattr(namespace, "epics", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        edges=check_type(
            getattr(namespace, "edges", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        owned=check_type(
            getattr(namespace, "owned", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        plan=check_type(
            getattr(namespace, "plan", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        dry_run=check_type(
            getattr(namespace, "dry_run", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        blocker=check_type(
            getattr(namespace, "blocker", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        blocked=check_type(
            getattr(namespace, "blocked", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        reason=check_type(
            getattr(namespace, "reason", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        by=check_type(
            getattr(namespace, "by", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        all=check_type(
            getattr(namespace, "all", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        rejudge=check_type(
            getattr(namespace, "rejudge", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        only=check_type(
            getattr(namespace, "only", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        prd_dir=check_type(
            getattr(namespace, "prd_dir", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        epics_dir=check_type(
            getattr(namespace, "epics_dir", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        tasks_dir=check_type(
            getattr(namespace, "tasks_dir", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        owner=check_type(
            getattr(namespace, "owner", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        reclaim=check_type(
            getattr(namespace, "reclaim", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        done=check_type(
            getattr(namespace, "done", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        slug=check_type(
            getattr(namespace, "slug", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        repo=check_type(
            getattr(namespace, "repo", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        project_root=check_type(
            getattr(namespace, "project_root", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        packages_dir=check_type(
            getattr(namespace, "packages_dir", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        correction=check_type(
            getattr(namespace, "correction", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        key=check_type(
            getattr(namespace, "key", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        blocked_by_external=check_type(
            getattr(namespace, "blocked_by_external", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        repos=check_type(
            getattr(namespace, "repos", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        also=check_type(
            getattr(namespace, "also", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        arch_files=check_type(
            getattr(namespace, "arch_files", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        reviewed_from=check_type(
            getattr(namespace, "reviewed_from", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        reviewed_files=check_type(
            getattr(namespace, "reviewed_files", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        arch_root=check_type(
            getattr(namespace, "arch_root", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        keep=check_type(
            getattr(namespace, "keep", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        kept=check_type(
            getattr(namespace, "kept", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        save=check_type(
            getattr(namespace, "save", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        against=check_type(
            getattr(namespace, "against", []),
            list[Path],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        counts=check_type(
            getattr(namespace, "counts", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        files=check_type(
            getattr(namespace, "files", None),
            Path | str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        message=check_type(
            getattr(namespace, "message", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        doc=check_type(
            getattr(namespace, "doc", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        ui=check_type(
            getattr(namespace, "ui", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        items=check_type(
            getattr(namespace, "items", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        design_source=check_type(
            getattr(namespace, "design_source", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        kind=check_type(
            getattr(namespace, "kind", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        recorded_bundle=check_type(
            getattr(namespace, "recorded_bundle", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        file=check_type(
            getattr(namespace, "file", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
    )


@dataclass(frozen=True)
class _GraphCommand:
    """One graph-backed CLI request after its shared prerequisites are loaded."""

    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    level: str
    item: str | None


SPAN_FILE: Final = "repo-scoping.json"
ELEMENTS_FILE: Final = "span-elements.json"
TASK_DEPS_FILE: Final = "task-deps.json"
"""The names a command given `--dir` reads the span's files and the mapper's edges under."""


def _story_files(directory: Path, slug: str, repo: str) -> StoryFiles:
    """Name the saved files of one Story for a command that is given a directory and a slug.

    A command line names a directory; the files are the ones an elaboration saves there under
    these names. Library callers hand each path themselves.

    Returns:
        The Story's files in ``directory``.

    """
    return StoryFiles(
        slug,
        repo,
        SpanFiles(directory / SPAN_FILE, directory / ELEMENTS_FILE),
        directory / f"story-{slug}.json",
        (
            directory / f"spec-{slug}.md",
            directory / f"spec-{slug}.data-model.md",
            directory / f"spec-{slug}.criteria.md",
        ),
        directory / f"tasks-{slug}.json",
    )


def _span_stories(directory: Path, repos: list[str]) -> SpanStories:
    """Name the saved files of every Story of a span for a command that is given a directory.

    Returns:
        The Stories in span order, with the mapper's edges file when the directory holds one.

    """
    deps: Path = directory / TASK_DEPS_FILE
    return SpanStories(
        SpanFiles(directory / SPAN_FILE, directory / ELEMENTS_FILE),
        tuple(_story_files(directory, slug, repo) for repo, slug in repo_slugs(repos).items()),
        deps if deps.is_file() else None,
    )


def _dispatch_plan_tasks(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the plan-tasks command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **plan_story_tasks(
            _story_files(_required_path(args.dir), _required_text(args.slug), _required_text(args.repo)),
            root=args.project_root,
            packages_dir=args.packages_dir,
        ),
    })


def _dispatch_add_tasks(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the add-tasks command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **add_corrective_tasks(
            _story_files(_required_path(args.dir), _required_text(args.slug), _required_text(args.repo)),
            correction=_required_path(args.correction),
        ),
    })


def _dispatch_plan_task_edges(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the plan-task-edges command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **plan_task_edges(_span_stories(_required_path(args.dir), split_ids(_required_text(args.repos)))),
    })


def _dispatch_arch_approve(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-approve command selected by the CLI.

    Returns:
        The selected command result.

    """
    files: list[str] = split_ids(_required_text(args.arch_files))
    if args.dry_run:
        return json_object({
            **head,
            "dryRun": True,
            "wouldApprove": files,
            "summary": {"dryRun": True, "files": len(files)},
        })
    return json_object({
        **head,
        **approve_arch(
            files,
            arch_root=args.arch_root,
            reviewed=parse_conformance_result(args.reviewed_from)["reviewedFiles"]
            if args.reviewed_from
            else split_ids(_required_text(args.reviewed_files)),
        ),
    })


def _dispatch_arch_constraints(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-constraints command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **snapshot_constraints(_required_text(args.arch_root), keep=args.keep)})


def _dispatch_arch_constraints_restore(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-constraints-restore command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **restore_constraints(_required_text(args.arch_root), _required_text(args.kept))})


def _dispatch_arch_snapshot(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-snapshot command selected by the CLI.

    Returns:
        The selected command result.

    """
    result: JsonObject = json_object(head | snapshot_tree(_required_text(args.arch_root)))
    if "error" in result:
        return json_object(result)
    diffs: list[JsonObject] = [
        json_object({"against": str(p)} | tree_diff(json_object(json.loads(p.read_text(encoding="utf-8"))), result))
        for p in args.against
    ]
    if args.save is not None:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(result), encoding="utf-8")
        result["saved"] = str(args.save)
    if args.save is not None or args.against:
        result.pop("files", None)
        result["diffs"] = [json_object(item) for item in diffs]
    if args.counts:
        result["countsOnly"] = True
    return json_object(result)


def _dispatch_arch_state(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-state command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **arch_states(split_ids(_required_text(args.arch_files)), arch_root=args.arch_root)})


def _dispatch_closure_edges(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the closure-edges command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **closure_task_edges(_span_stories(_required_path(args.dir), split_ids(_required_text(args.repos)))),
    })


def _dispatch_arch_built_remove(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-built-remove command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **remove_built(
            _required_text(args.arch_root),
            split_ids(_required_text(args.files)),
            message=_required_text(args.message),
        ),
    })


def _dispatch_spec_ui_append(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the spec-ui-append command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **spec_ui_append(_required_path(args.doc), _required_path(args.ui))})


def _dispatch_recon_facts(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the recon-facts command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **recon_facts(_required_path(args.file), split_ids(_required_text(args.items)))})


def _dispatch_cds_bundles(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the cds-bundles command selected by the CLI.

    Returns:
        The selected command result.

    """
    listing: JsonObject = json_object(list_bundles(args.packages_dir))
    if args.design_source:
        listing["selection"] = json_object(
            select_build(
                args.packages_dir,
                args.design_source,
                {"kind": _required_text(args.kind), "slug": _required_text(args.slug)},
                args.recorded_bundle,
            ),
        )
    return json_object(head | listing | {"summary": {"bundles": len(check_type(listing["bundles"], list[JsonValue]))}})


def _dispatch_replace_tasks(args: _CommandOptions, head: JsonObject, writer: Writer) -> JsonObject:
    """Execute the replace-tasks command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **replace_tasks(
            writer,
            _required_text(args.epic),
            slug=_required_text(args.slug),
            reason=_required_text(args.reason),
        ),
    })


def _dispatch_write_task(args: _CommandOptions, head: JsonObject, writer: Writer) -> JsonObject:
    """Execute the write-task command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **write_task(
            writer,
            _required_text(args.epic),
            _story_files(_required_path(args.dir), _required_text(args.slug), _required_text(args.repo)),
            key=_required_text(args.key),
            root=args.project_root,
            external=split_ids(_required_text(args.blocked_by_external)),
            packages_dir=args.packages_dir,
        ),
    })


def _dispatch_write_story(context: _GraphCommand) -> JsonObject:
    """Execute the write-story command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    args = context.args
    head = context.head
    writer = context.writer
    graph = context.graph
    return json_object({
        **head,
        **write_story(
            graph,
            writer,
            _required_text(args.epic),
            _story_files(_required_path(args.dir), _required_text(args.slug), _required_text(args.repo)),
            root=args.project_root,
        ),
    })


def _dispatch_write_task_edges(context: _GraphCommand) -> JsonObject:
    """Execute the write-task-edges command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    args = context.args
    head = context.head
    writer = context.writer
    graph = context.graph
    return json_object({
        **head,
        **write_task_edges(
            graph,
            writer,
            _required_text(args.epic),
            _span_stories(_required_path(args.dir), split_ids(_required_text(args.repos))),
            name=_required_text(args.task),
        ),
    })


def _dispatch_write_all_task_edges(context: _GraphCommand) -> JsonObject:
    """Execute the write-all-task-edges command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    args = context.args
    head = context.head
    writer = context.writer
    graph = context.graph
    return json_object({
        **head,
        **write_all_task_edges(
            graph,
            writer,
            _required_text(args.epic),
            _span_stories(_required_path(args.dir), split_ids(_required_text(args.repos))),
            also=split_ids(args.also) if args.also else [],
        ),
    })


def _dispatch_story_edges(context: _GraphCommand) -> JsonObject:
    """Execute the story-edges command selected by the CLI.

    Returns:
        The selected command result.

    """
    head: JsonObject
    writer: Writer
    graph: Graph
    head = context.head
    writer = context.writer
    graph = context.graph
    return json_object({**head, **story_edges(graph, writer)})


def _dispatch_assess_plan(context: _GraphCommand) -> JsonObject:
    """Execute the assess-plan command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    graph: Graph
    args = context.args
    head = context.head
    graph = context.graph
    return json_object({
        **head,
        **assess_plan(
            graph,
            epic=args.epic,
            since=args.since,
            level=_required_text(args.level),
            task=args.task,
        ),
    })


def _dispatch_assess_context(context: _GraphCommand) -> JsonObject:
    """Execute the assess-context command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    graph: Graph
    args = context.args
    head = context.head
    graph = context.graph
    if args.task is not None:
        return json_object({**head, **task_context(graph, args.task, _required_path(args.dir))})
    return json_object({
        **head,
        **assess_context(
            graph,
            _required_text(args.epic),
            _required_path(args.dir),
            corpus_ready=args.corpus_ready,
        ),
    })


def _dispatch_score_plan(context: _GraphCommand) -> JsonObject:
    """Execute the score-plan command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    graph: Graph
    only: list[str] | None
    args = context.args
    head = context.head
    graph = context.graph
    only = split_ids(args.only) if args.only else None
    return json_object({**head, **plan(graph, include_all=args.all, rejudge=args.rejudge, only=only)})


def _dispatch_judge_input(context: _GraphCommand) -> JsonObject:
    """Execute the judge-input command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    graph: Graph
    args = context.args
    head = context.head
    graph = context.graph
    return json_object({
        **head,
        **judge_input(
            graph,
            check_type(
                _read_json(_required_path(args.plan)),
                Plan,
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            ),
            _required_text(args.level),
            prd_dir=args.prd_dir,
        ),
    })


def _dispatch_snapshot(context: _GraphCommand) -> JsonObject:
    """Execute the snapshot command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    graph: Graph
    epics: list[str] | None
    args = context.args
    head = context.head
    graph = context.graph
    epics = split_ids(args.epics) if args.epics else None
    return json_object({
        **head,
        **snapshot(
            graph,
            kinds=tuple(split_ids(_required_text(args.kinds))),
            include_closed=args.include_closed,
            epics=epics,
        ),
    })


def _dispatch_validate(context: _GraphCommand) -> JsonObject:
    """Execute the validate command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    graph: Graph
    level: str
    item: str | None
    args = context.args
    head = context.head
    graph = context.graph
    level = context.level
    item = context.item
    report: JsonObject = json_object(
        validate(
            graph,
            read_edges(_required_path(args.edges)),
            item,
            read_withdrawn(_required_path(args.edges)),
            level,
        ),
    )
    return json_object(head | report | {"summary": {"ok": report["ok"], "edges": report["edgeCount"]}})


def _dispatch_apply_edges(context: _GraphCommand) -> JsonObject:
    """Execute the apply-edges command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    level: str
    item: str | None
    seen: dict[str, str]
    proposal: list[edgeset.Edge]
    withdrawn: list[edgeset.Edge]
    args = context.args
    head = context.head
    writer = context.writer
    graph = context.graph
    level = context.level
    item = context.item
    seen = _plan_fingerprints(args.plan) if args.plan else {}
    proposal = owned_edges(graph) if args.owned else read_edges(_required_path(args.edges))
    withdrawn = [] if args.owned else read_withdrawn(_required_path(args.edges))
    result: JsonObject = json_object(
        apply_edges(graph, proposal, writer, ApplyScope(seen, item, withdrawn, level)),
    )
    summary: JsonObject = {
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
    summary["withdrawn"] = len(check_type(result.get("withdrawn") or [], list[JsonValue]))
    summary["plannedWrites"] = len(check_type(result.get("planned") or [], list[JsonValue]))
    if not json_object(result["validation"])["ok"]:
        summary["validation"] = result["validation"]
    if level == "task" and result.get("applied") and not writer.dry_run:
        result["storyEdges"] = _story_edges_after(args.directory)
        summary["storyEdges"] = _story_edges_summary(json_object(result["storyEdges"]))
    return json_object(head | result | {"summary": summary})


def _dispatch_withdraw_edge(context: _GraphCommand) -> JsonObject:
    """Execute the withdraw-edge command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    args = context.args
    head = context.head
    writer = context.writer
    graph = context.graph
    return json_object({
        **head,
        **withdraw_edge(
            graph,
            Edge(_required_text(args.blocker), _required_text(args.blocked), _required_text(args.reason)),
            writer,
            _required_text(args.by),
            _required_text(args.level),
        ),
    })


def _dispatch_record(context: _GraphCommand) -> JsonObject:
    """Execute the record command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    judgments: dict[str, list[JsonObject]]
    args = context.args
    head = context.head
    writer = context.writer
    graph = context.graph
    unreadable: list[JsonObject] = []
    judgments = {
        "epic": _dir_entries(args.epics_dir, "scores", unreadable),
        "task": _dir_entries(args.tasks_dir, "scores", unreadable),
    }
    result: JsonObject = json_object(
        record(
            graph,
            check_type(
                _read_json(_required_path(args.plan)),
                Plan,
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            ),
            judgments,
            writer,
        ),
    )
    result["unreadable"] = [json_object(value) for value in unreadable]
    result_summary: JsonObject = json_object(result["summary"])
    result_summary["unreadable"] = len(unreadable)
    result["summary"] = result_summary
    return json_object({**head, **result})


def _dispatch_elaboration_start(context: _GraphCommand) -> JsonObject:
    """Execute the elaboration-start command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    args = context.args
    head = context.head
    writer = context.writer
    graph = context.graph
    return json_object({
        **head,
        **start(
            graph,
            writer,
            _required_text(args.epic),
            owner=args.owner,
            reclaim=args.reclaim,
        ),
    })


def _dispatch_elaboration_finish(context: _GraphCommand) -> JsonObject:
    """Execute the elaboration-finish command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    args = context.args
    head = context.head
    writer = context.writer
    graph = context.graph
    finished: JsonObject = json_object(
        finish(graph, writer, _required_text(args.epic), owner=args.owner, done=args.done),
    )
    if not writer.dry_run:
        finished["storyEdges"] = _story_edges_after(args.directory)
        finished_summary: JsonObject = json_object(finished.get("summary") or {})
        finished_summary["storyEdges"] = _story_edges_summary(json_object(finished["storyEdges"]))
        finished["summary"] = finished_summary
    return json_object({**head, **finished})


def _dispatch_elaboration_release(context: _GraphCommand) -> JsonObject:
    """Execute the elaboration-release command selected by the CLI.

    Returns:
        The selected command result.

    """
    args: _CommandOptions
    head: JsonObject
    writer: Writer
    graph: Graph
    args = context.args
    head = context.head
    writer = context.writer
    graph = context.graph
    return json_object({**head, **release(graph, writer, _required_text(args.epic), owner=_required_text(args.owner))})


_EARLY_COMMANDS: dict[str, Callable[[_CommandOptions, JsonObject], JsonObject]] = {
    "plan-tasks": _dispatch_plan_tasks,
    "add-tasks": _dispatch_add_tasks,
    "plan-task-edges": _dispatch_plan_task_edges,
    "arch-approve": _dispatch_arch_approve,
    "arch-constraints": _dispatch_arch_constraints,
    "arch-constraints-restore": _dispatch_arch_constraints_restore,
    "arch-snapshot": _dispatch_arch_snapshot,
    "arch-state": _dispatch_arch_state,
    "closure-edges": _dispatch_closure_edges,
    "arch-built-remove": _dispatch_arch_built_remove,
    "spec-ui-append": _dispatch_spec_ui_append,
    "recon-facts": _dispatch_recon_facts,
    "cds-bundles": _dispatch_cds_bundles,
}

_WRITE_COMMANDS: dict[str, Callable[[_CommandOptions, JsonObject, Writer], JsonObject]] = {
    "replace-tasks": _dispatch_replace_tasks,
    "write-task": _dispatch_write_task,
}

_GRAPH_COMMANDS: dict[str, Callable[[_GraphCommand], JsonObject]] = {
    "write-story": _dispatch_write_story,
    "write-task-edges": _dispatch_write_task_edges,
    "write-all-task-edges": _dispatch_write_all_task_edges,
    "story-edges": _dispatch_story_edges,
    "assess-plan": _dispatch_assess_plan,
    "assess-context": _dispatch_assess_context,
    "score-plan": _dispatch_score_plan,
    "judge-input": _dispatch_judge_input,
    "snapshot": _dispatch_snapshot,
    "validate": _dispatch_validate,
    "apply-edges": _dispatch_apply_edges,
    "withdraw-edge": _dispatch_withdraw_edge,
    "record": _dispatch_record,
    "elaboration-start": _dispatch_elaboration_start,
    "elaboration-finish": _dispatch_elaboration_finish,
    "elaboration-release": _dispatch_elaboration_release,
}


def run(args: _CommandOptions) -> JsonObject:
    """Dispatch one parsed command while loading only its required dependencies.

    Returns:
        The selected command's JSON result.

    Raises:
        TypeError: Arguments violate the declared input contract.
        SequencingError: An edge request has ambiguous ownership.

    """
    if not isinstance(args, _CommandOptions):
        message: str = "Invalid run arguments"
        raise TypeError(message)
    msg: str
    command: str = args.command
    head: JsonObject = {"command": command}
    if command in _EARLY_COMMANDS:
        return _EARLY_COMMANDS[command](args, head)
    writer: Writer = Writer(args.directory, dry_run=args.dry_run)
    if command in _WRITE_COMMANDS:
        return _WRITE_COMMANDS[command](args, head, writer)
    descriptions: bool = (
        command
        in {
            "write-story",
            "assess-plan",
            "assess-context",
            "score-plan",
            "judge-input",
            "elaboration-finish",
        }
        or args.with_description
    )
    graph: Graph = beadgraph.load(args.directory, with_description=descriptions)
    head = json_object({"source": graph.source, "warnings": graph.warnings, "command": command})
    if command in {"validate", "apply-edges"} and args.edges and bool(args.epic) == bool(args.task):
        msg = "an edge proposal covers exactly one Epic or one Task: pass --epic or --task"
        raise SequencingError(msg)
    level: str = "task" if args.task else "epic"
    item: str | None = args.task if level == "task" else args.epic
    if command in _GRAPH_COMMANDS:
        return _GRAPH_COMMANDS[command](_GraphCommand(args, head, writer, graph, level, item))
    return json_object(head | score(graph, writer))


def _story_edges_after(directory: Path | None) -> JsonObject:
    """Run `story-edges` over the tracker as it stands after a command wrote Task edges.

    Args:
        directory: The repository to run `bd` from, or None for the working directory.

    Returns:
        The `story-edges` result, or `{ok: false, error}` when the tracker could not be read
        through `bd`.

    """
    graph: Graph
    try:
        graph = beadgraph.load(directory)
        return json_object(story_edges(graph, Writer(directory)))
    except GraphError as exc:
        return {"ok": False, "error": str(exc)}


def _story_edges_summary(result: JsonObject) -> JsonObject:
    """Select the part of a `story-edges` result carried in its summary.

    Args:
        result: The `story-edges` result.

    Returns:
        Its summary, with the refusal's conflicts and cycles, or its error.

    """
    if result.get("error"):
        return {"ok": False, "error": result["error"]}
    out: JsonObject = json_object(result.get("summary") or {})
    if result.get("refused"):
        out["conflicts"] = result.get("conflicts") or []
        out["cycles"] = result.get("cycles") or []
    return out


def _read_relay(relay_file: Path | None) -> int:
    """Print the saved relay or its read error.

    Returns:
        The recorded exit status or two for an invalid relay.

    """
    if relay_file is None:
        sys.stdout.write(json.dumps({"error": "relay-read needs --relay FILE"}, indent=2) + "\n")
        return 2
    try:
        shown: JsonObject = json_object(relay.read(relay_file))
    except (relay.RelayError, json.JSONDecodeError, OSError) as exc:
        sys.stdout.write(json.dumps({"error": str(exc), "command": "relay-read"}, indent=2) + "\n")
        return 2
    sys.stdout.write(relay.line(shown) + "\n")
    return check_type(shown["~exit"], int)


def main(argv: list[str] | None = None) -> int:
    """Print one JSON result and return the command exit status.

    Exit 2 means the command refused, exit 3 that the
    command line was not the one its `--argv-sha256` names (nothing ran).

    Args:
        argv: The command line, or None for `sys.argv`.

    Returns:
        The process exit status.

    Raises:
        TypeError: Arguments violate the declared input contract.

    """
    if argv is not None and (not isinstance(argv, list) or any(not isinstance(value, str) for value in argv)):
        message: str = "Invalid main arguments"
        raise TypeError(message)
    typed_wrong: str
    status: int
    payload: dict[str, JsonValue]
    argv, typed_wrong = relay.argv_mismatch(
        list(sys.argv[1:] if argv is None else argv),
    )
    if typed_wrong:
        sys.stdout.write(relay.line(relay.mismatch_envelope(typed_wrong)) + "\n")
        return 3
    args: _CommandOptions = _command_options(build_parser().parse_args(argv))
    out: Path | None = args.out
    relay_file: Path | None = args.relay
    if args.command == "relay-read":
        return _read_relay(relay_file)
    status = 0
    try:
        payload = run(args)
    except (
        SequencingError,
        ScoringError,
        LifecycleError,
        GraphError,
        HierarchyError,
        SpecUiError,
        ReconError,
        relay.RelayError,
        rubric.WsjfError,
        ValueError,
        OSError,
    ) as exc:
        cause: str = check_type(getattr(exc, "cause", beadgraph.OTHER_CAUSE), str)
        payload, status = (
            {"error": str(exc), "cause": cause, "command": args.command},
            2,
        )
    if status == 0 and out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        payload = {
            "command": args.command,
            "out": str(out),
            "warnings": payload.get("warnings", []),
            "summary": payload.get("summary", {}),
        }
    if relay_file is not None:
        try:
            shown: JsonObject = json_object(relay.write(args.command, payload, relay_file, status))
        except (relay.RelayError, OSError) as exc:
            sys.stdout.write(
                json.dumps(
                    {"error": f"--relay: {exc}", "command": args.command},
                    indent=2,
                )
                + "\n",
            )
            return 2
        sys.stdout.write(relay.line(shown) + "\n")
        return status
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
