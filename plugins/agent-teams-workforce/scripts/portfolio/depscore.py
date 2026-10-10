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
    arch-revision        bind the architecture step's saved work to the arc42 views it read or
                         wrote: `check` records them, or sets aside saved work one of whose
                         views changed into a dated stale folder; `mark` records the step's own
                         integration (integrating, integrated); no `bd` call
    arch-resume          read the architecture step's saved work in its working directory and
                         print only the facts its control flow needs (finished steps, last
                         round, open findings by id, unreviewed claims per writer, the decision's
                         verdict, the integration's files); writes the full claim and finding
                         ledger to `ledger.json` there; a saved file that cannot be parsed is
                         set aside and named in `warnings`; no `bd` call
    arch-target          check an approved draft and write it to `target/<subject>/`, every view
                         `in-review`; refuses a draft with no view while design work is named,
                         a file in section 2, a survey with no assessment, or a subject with no
                         name left; the folder name is derived from the subject (lower-case,
                         hyphens, dates and the Epic, PRD and bead names taken out: `Company
                         Intelligence` is `company-intelligence`) and returned as
                         `subject`, the subject as given as `subjectName`; no `bd` call
    arch-delta           list a written target's build items: the elements its delta shows
                         (an entirely new target's views are its delta; no architecture
                         change has no delta), numbered D1, D2 ... in element-name order, then
                         the future set's implementation gaps, then one `prerequisite` item
                         per entry of the target's `closure.json`, every item with the ids it
                         `requires`; `--delta-dir` is the target's delta/ path, which exists
                         only for a partial change;
                         `--roots-only` leaves the closure out, `--save FILE` also writes the
                         listing to FILE; no `bd` call
    arch-closure         check the prerequisite closure the architecture step's Closure phase
                         saved (every element the delta's work rests on that is not built and
                         current) against the target's build items and the open beads, and
                         write it beside the target's baseline as `closure.json`; reads beads,
                         writes none
    arch-target-names    tell which names an approved target's files mention as whole words;
                         no `bd` call
    arch-target-remove   delete `target/<subject>/` and commit the removal in the repository
                         holding it; no `bd` call
    arch-built-remove    delete the `built/<subject>/` files the effective version now matches
                         and commit the removal in the repository holding them; no `bd` call
    arch-commit          commit the architecture files an integration changed, staging only
                         those paths, and push the branch; no `bd` call
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
    tasks-inputs         whether a Story's saved Tasks were decomposed from the inputs they
                         record, unchanged; no `bd` call
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
    arch-integration-files  measure the files an integration wrote since its saved
                         fingerprint, union them with the maintainer's report, write the lists
                         to a files file and relay their counts; no `bd` call
    arch-review-check    check a saved conformance review against the integration's files and
                         the approved coverage rows; relays counts; no `bd` call
    saved-target         the facts a resumed elaboration needs from an Epic's saved architecture
                         target and integration report; no `bd` call
    saved-span           the saved span ruling (`repo-scoping.json`) a resumed elaboration
                         replays; no `bd` call
    relay-read           print again the relay envelope of a result saved with `--relay FILE`,
                         re-running nothing; no `bd` call
    story-edges          derive and write the Story -> Story `blocks` edges from Epic order within
                         a repository and from Task edges between Stories in any repository;
                         a Story whose order is contradictory gets no edge written
                         `elaboration-finish` and a Task-level `apply-edges` run it after they write

Every command prints one JSON object. With `--out FILE` the full object is written to FILE
and stdout carries only its `summary`. With `--relay FILE` the full object is written to FILE
and stdout carries its relay view with a `relay` block (`file`, `checksum`, `chars`) a workflow
script checks the copy a runner session returns against; `relay-read --relay FILE` prints that
same envelope again from FILE without re-running the command. A leading
`--argv-sha256 HEX` refuses, with exit 3 and nothing run, a command line typed differently from
the one the workflow script built (see relay.py). `--dry-run`
computes, writes nothing, and returns the writes under `planned`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import beadgraph
import edgeset
import relay
import wsjf as rubric
from archclosure import write_closure
from archfiles import IntegrationOptions, files_from, integration_files, review_check
from archresume import ResumeError, ResumeOptions, resume_facts
from archrevision import check as revision_check
from archrevision import mark as revision_mark
from archstate import (
    TargetOptions,
    commit_integration,
    delta_items,
    remove_built,
    remove_target,
    restore_constraints,
    snapshot_constraints,
    snapshot_tree,
    target_names,
    tree_diff,
    write_target,
)
from archstate import promote as approve_arch
from archstate import states as arch_states
from assesscontext import assess_context, task_context
from beadgraph import Bead, Graph, GraphError, Writer, split_ids
from beadwrite import (
    add_corrective_tasks,
    closure_task_edges,
    plan_story_tasks,
    plan_task_edges,
    replace_tasks,
    tasks_inputs,
    write_all_task_edges,
    write_story,
    write_task,
    write_task_edges,
)
from cdsbundles import list_bundles, select_build
from contracts import JsonObject, JsonValue, json_object
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
from elaboration import LifecycleError, finish, release, start
from hierarchy import HierarchyError
from reconfacts import ReconError, recon_facts
from resumefacts import saved_span, saved_target
from scoring import ScoringError, judge_input, plan, record, score
from scoringcontracts import Plan
from specui import SpecUiError, spec_ui_append
from storyedges import story_edges
from typeguard import CollectionCheckStrategy, check_type

if TYPE_CHECKING:
    from collections.abc import Callable


ELAB_KEY = "elaboration_state"


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
        b for b in graph.of_kind(level) if not b.closed and not (level == "task" and b.metadata.get(ELAB_IDENTITY_KEY))
    ]
    cutoff = _instant(since) if since is not None else None
    prints = beadgraph.fingerprints(graph.records, beadgraph.SCOPE_JUDGING)

    def assessed(bead: Bead) -> bool:
        at: datetime | None
        if bead.metadata.get(SEEN_KEY) != prints.get(bead.id):
            return False
        if cutoff is None:
            return True
        at = _instant(bead.metadata.get(ASSESSED_AT_KEY) or "")
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


def _configure_command_1(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    name: str
    what: str
    for name, what in (
        (
            "saved-target",
            "the saved architecture target's facts a resumed elaboration needs",
        ),
        (
            "saved-span",
            "the saved span ruling (repo-scoping.json) a resumed elaboration replays",
        ),
    ):
        sv: argparse.ArgumentParser = sub.add_parser(name, help=f"{what}; no `bd` call", parents=[common])
        sv.add_argument(
            "--art-dir",
            type=Path,
            required=True,
            help="the Epic's artifacts directory",
        )


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
        help="set the Epic's `elaboration_state` to `done`",
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
        help="the accepted corrective pass: tasks, noWork, edges and scores",
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

    tin: argparse.ArgumentParser = sub.add_parser(
        "tasks-inputs",
        help="whether a Story's saved Tasks were decomposed from the inputs they record, "
        "unchanged; runs no `bd` command",
        parents=[common],
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

    for task_parser in (pta, adt, wta, tin, rpt):
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
        default="",
        help="the architecture files the integration changed or created, comma-separated",
    )
    aap.add_argument(
        "--arch-files-from",
        type=Path,
        default=None,
        help="instead of --arch-files: the `touched` list of an arch-integration-files files file",
    )
    aap.add_argument(
        "--reviewed-from",
        type=Path,
        default=None,
        help="instead of --reviewed-files: the `reviewedFiles` list of a saved conformance review",
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


def _configure_command_32(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    atn: argparse.ArgumentParser = sub.add_parser(
        "arch-target-names",
        help="tell which names an approved target's files mention; writes nothing, runs no `bd` command",
        parents=[common],
    )
    atn.add_argument("--target-dir", required=True, help="the target/<subject>/ folder")
    atn.add_argument("--names", required=True, help="the names, comma-separated")


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


def _configure_command_34(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    arv: argparse.ArgumentParser = sub.add_parser(
        "arch-revision",
        help="bind the architecture step's saved work to the arc42 views it read or wrote, "
        "setting it aside when one of them changed; no `bd` call",
        parents=[common],
    )
    arv.add_argument(
        "action",
        choices=("check", "mark"),
        help="check the binding, or mark the integration",
    )
    arv.add_argument(
        "--arch-root",
        required=True,
        help="the architecture directory holding arc42/",
    )
    arv.add_argument(
        "--work-dir",
        required=True,
        help="the architecture step's working directory",
    )
    arv.add_argument(
        "--stale-root",
        default=None,
        help="where `check` makes the dated stale folder (the Epic's artifacts directory)",
    )
    arv.add_argument(
        "--state",
        choices=("integrating", "integrated"),
        default=None,
        help="with `mark`: the integration began, or was approved",
    )


def _configure_command_35(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    aif: argparse.ArgumentParser = sub.add_parser(
        "arch-integration-files",
        help="measure the files an integration wrote since its saved fingerprint, union them "
        "with the maintainer's report, and write the lists to a files file; relays counts; "
        "no `bd` call",
        parents=[common],
    )
    aif.add_argument("--arch-root", required=True, help="the architecture directory")
    aif.add_argument(
        "--before",
        type=Path,
        required=True,
        help="the fingerprint saved before",
    )
    aif.add_argument(
        "--report",
        type=Path,
        required=True,
        help="the maintainer's saved report",
    )
    aif.add_argument(
        "--files-out",
        type=Path,
        required=True,
        help="the files file to write",
    )
    aif.add_argument(
        "--last",
        type=Path,
        default=None,
        help="the previous measurement's fingerprint",
    )
    aif.add_argument(
        "--save-last",
        type=Path,
        default=None,
        help="save this measurement's fingerprint",
    )
    aif.add_argument(
        "--accumulate",
        action="store_true",
        help="keep the reported lists already in the files file",
    )


def _configure_command_36(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    arc: argparse.ArgumentParser = sub.add_parser(
        "arch-review-check",
        help="check a saved conformance review against the integration's files and the "
        "approved coverage rows; relays counts; no `bd` call",
        parents=[common],
    )
    arc.add_argument("--review", type=Path, required=True, help="the saved review")
    arc.add_argument(
        "--files",
        type=Path,
        required=True,
        help="the arch-integration-files files file",
    )
    arc.add_argument(
        "--coverage-from",
        type=Path,
        required=True,
        help="the relay file of the arch-resume run holding the approved coverage rows",
    )


def _configure_command_37(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    arz: argparse.ArgumentParser = sub.add_parser(
        "arch-resume",
        help="the facts the architecture step's control flow needs from its saved work; "
        "writes ledger.json there, runs no `bd` command",
        parents=[common],
    )
    arz.add_argument(
        "--work-dir",
        required=True,
        help="the architecture working directory of one Epic",
    )
    arz.add_argument(
        "--roster",
        required=True,
        help="each role's agents, as role=a,b;role=c",
    )
    arz.add_argument(
        "--assign",
        default="",
        help="owners the coordinator assigned to findings, as F1.2.3=agent,...",
    )

    arz.add_argument(
        "--proposal-team",
        default="",
        help="deprecated compatibility input; coordinator dispatches select architecture specialists",
    )

    arz.add_argument(
        "--round-plan",
        default="",
        help="validated durable round plan JSON",
    )


def _configure_command_38(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    atg: argparse.ArgumentParser = sub.add_parser(
        "arch-target",
        help="check an approved draft and write it to target/<subject>/ as in-review; runs no `bd` command",
        parents=[common],
    )
    atg.add_argument("--draft", required=True, help="the draft target directory")
    atg.add_argument(
        "--baseline",
        default="",
        help="validated survey JSON retaining baseline and implementation work",
    )
    atg.add_argument(
        "--arch-root",
        required=True,
        help="the architecture directory holding target/",
    )
    atg.add_argument(
        "--subject",
        required=True,
        help="the subject the target describes, as a display name or a folder name; the folder name is derived from it",
    )
    atg.add_argument(
        "--forbid",
        default="",
        help="names a subject never carries (the Epic, the PRD), comma-separated",
    )
    atg.add_argument(
        "--seed",
        action="store_true",
        help="write only the baseline handoff (baseline.json, with the note naming the "
        "architecture change: none, new or partial) from --baseline into the draft, so "
        "every review has the documents it reviews",
    )
    _dry_run_flag(atg)


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


def _configure_command_40(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    adl: argparse.ArgumentParser = sub.add_parser(
        "arch-delta",
        help="list the elements a target's delta shows, one item per element; writes nothing, runs no `bd` command",
        parents=[common],
    )
    adl.add_argument(
        "--delta-dir",
        required=True,
        help="the target/<subject>/delta/ directory",
    )
    adl.add_argument(
        "--roots-only",
        action="store_true",
        help="list the root items alone, without the prerequisites closure.json adds",
    )
    adl.add_argument(
        "--save",
        type=Path,
        default=None,
        help="also write the full listing to this file (the Epic's delta-items.json)",
    )


def _configure_command_41(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    acl: argparse.ArgumentParser = sub.add_parser(
        "arch-closure",
        help="check a prerequisite closure against the delta and the open beads and write "
        "it beside the target's baseline as closure.json; reads beads, writes no bead",
        parents=[common],
    )
    acl.add_argument(
        "--closure",
        required=True,
        help="the closure the Closure phase saved",
    )
    acl.add_argument(
        "--delta-dir",
        required=True,
        help="the target/<subject>/delta/ directory",
    )
    _dry_run_flag(acl)


def _configure_command_42(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    atr: argparse.ArgumentParser = sub.add_parser(
        "arch-target-remove",
        help="delete target/<subject>/ and commit the removal; runs no `bd` command",
        parents=[common],
    )
    atr.add_argument(
        "--arch-root",
        required=True,
        help="the architecture directory holding target/",
    )
    atr.add_argument(
        "--target-dir",
        required=True,
        help="the target/<subject>/ folder to remove",
    )
    atr.add_argument("--message", required=True, help="the commit message")


def _configure_command_43(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    abr: argparse.ArgumentParser = sub.add_parser(
        "arch-built-remove",
        help="delete built/<subject>/ files the effective version now matches and commit "
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


def _configure_command_44(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    acm: argparse.ArgumentParser = sub.add_parser(
        "arch-commit",
        help="commit the architecture files an integration changed and push; runs no `bd` command",
        parents=[common],
    )
    acm.add_argument(
        "--arch-root",
        required=True,
        help="the architecture directory the files sit under",
    )
    acm.add_argument(
        "--files",
        default="",
        help="the integrated files to commit, comma-separated",
    )
    acm.add_argument(
        "--files-from",
        type=Path,
        default=None,
        help="instead of --files: the `all` list of an arch-integration-files files file",
    )
    acm.add_argument("--message", required=True, help="the commit message")


def _configure_command_45(sub: _Subcommands, common: argparse.ArgumentParser) -> None:
    """Register one command family and its arguments."""
    sua: argparse.ArgumentParser = sub.add_parser(
        "spec-ui-append",
        help="write the ui items' design sources into a saved spec document; runs no `bd` command",
        parents=[common],
    )
    sua.add_argument("--doc", type=Path, required=True, help="the saved spec document")
    sua.add_argument(
        "--items",
        required=True,
        help="the repository's ui items as JSON: [{id, designSource?, buildSpec?, sections?}]",
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
    _configure_command_1,
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
    _configure_command_32,
    _configure_command_33,
    _configure_command_34,
    _configure_command_35,
    _configure_command_36,
    _configure_command_37,
    _configure_command_38,
    _configure_command_39,
    _configure_command_40,
    _configure_command_41,
    _configure_command_42,
    _configure_command_43,
    _configure_command_44,
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


def _required[T](value: T | None) -> T:
    """Require a value present for the selected command.

    Returns:
        The supplied value.

    Raises:
        ValueError: A required command option is absent.

    """
    if value is None:
        message: str = "Required command option is absent"
        raise ValueError(message)
    return value


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
    art_dir: Path | None
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
    arch_files_from: Path | None
    reviewed_from: Path | None
    reviewed_files: str | None
    arch_root: str | None
    keep: bool
    kept: str | None
    target_dir: str | None
    names: str | None
    save: Path | None
    against: list[Path]
    counts: bool
    action: str | None
    work_dir: str | None
    stale_root: str | None
    state: str | None
    before: Path | None
    report: Path | None
    files_out: Path | None
    last: Path | None
    save_last: Path | None
    accumulate: bool
    review: Path | None
    files: Path | str | None
    coverage_from: Path | None
    roster: str | None
    assign: str | None
    proposal_team: str | None
    round_plan: str | None
    draft: str | None
    baseline: str | None
    subject: str | None
    forbid: str | None
    seed: bool
    delta_dir: str | None
    roots_only: bool
    closure: str | None
    message: str | None
    files_from: Path | None
    doc: Path | None
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
        art_dir=check_type(
            getattr(namespace, "art_dir", None),
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
        arch_files_from=check_type(
            getattr(namespace, "arch_files_from", None),
            Path | None,
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
        target_dir=check_type(
            getattr(namespace, "target_dir", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        names=check_type(
            getattr(namespace, "names", None),
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
        action=check_type(
            getattr(namespace, "action", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        work_dir=check_type(
            getattr(namespace, "work_dir", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        stale_root=check_type(
            getattr(namespace, "stale_root", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        state=check_type(
            getattr(namespace, "state", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        before=check_type(
            getattr(namespace, "before", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        report=check_type(
            getattr(namespace, "report", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        files_out=check_type(
            getattr(namespace, "files_out", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        last=check_type(
            getattr(namespace, "last", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        save_last=check_type(
            getattr(namespace, "save_last", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        accumulate=check_type(
            getattr(namespace, "accumulate", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        review=check_type(
            getattr(namespace, "review", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        files=check_type(
            getattr(namespace, "files", None),
            Path | str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        coverage_from=check_type(
            getattr(namespace, "coverage_from", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        roster=check_type(
            getattr(namespace, "roster", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        assign=check_type(
            getattr(namespace, "assign", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        proposal_team=check_type(
            getattr(namespace, "proposal_team", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        round_plan=check_type(
            getattr(namespace, "round_plan", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        draft=check_type(
            getattr(namespace, "draft", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        baseline=check_type(
            getattr(namespace, "baseline", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        subject=check_type(
            getattr(namespace, "subject", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        forbid=check_type(
            getattr(namespace, "forbid", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        seed=check_type(
            getattr(namespace, "seed", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        delta_dir=check_type(
            getattr(namespace, "delta_dir", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        roots_only=check_type(
            getattr(namespace, "roots_only", False),
            bool,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        closure=check_type(
            getattr(namespace, "closure", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        message=check_type(
            getattr(namespace, "message", None),
            str | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        files_from=check_type(
            getattr(namespace, "files_from", None),
            Path | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        doc=check_type(
            getattr(namespace, "doc", None),
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


def _dispatch_plan_tasks(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the plan-tasks command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **plan_story_tasks(
            _required_path(args.dir),
            slug=_required_text(args.slug),
            repo=_required_text(args.repo),
            root=args.project_root,
            packages_dir=args.packages_dir,
        ),
    })


def _dispatch_tasks_inputs(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the tasks-inputs command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **tasks_inputs(_required_path(args.dir), slug=_required_text(args.slug), root=args.project_root),
    })


def _dispatch_add_tasks(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the add-tasks command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **add_corrective_tasks(
            _required_path(args.dir),
            slug=_required_text(args.slug),
            correction=_required_path(args.correction),
        ),
    })


def _dispatch_plan_task_edges(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the plan-task-edges command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **plan_task_edges(_required_path(args.dir), split_ids(_required_text(args.repos)))})


def _dispatch_arch_approve(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-approve command selected by the CLI.

    Returns:
        The selected command result.

    """
    files: list[str]
    files = (
        files_from(args.arch_files_from, "touched")
        if args.arch_files_from
        else split_ids(_required_text(args.arch_files))
    )
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
            reviewed=files_from(args.reviewed_from, "reviewedFiles")
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


def _dispatch_arch_target_names(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-target-names command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **target_names(_required_text(args.target_dir), split_ids(_required_text(args.names)))})


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


def _dispatch_arch_revision(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-revision command selected by the CLI.

    Returns:
        The selected command result.

    """
    why: str
    if args.action == "mark":
        if not args.state:
            why = "arch-revision mark needs --state integrating or integrated"
            return json_object({
                **head,
                "ok": False,
                "error": why,
                "summary": json_object({"ok": False, "error": why}),
            })
        return json_object({**head, **revision_mark(_required(args.arch_root), _required(args.work_dir), args.state)})
    return json_object({**head, **revision_check(_required(args.arch_root), _required(args.work_dir), args.stale_root)})


def _dispatch_saved_target(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the saved-target command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **saved_target(_required_path(args.art_dir))})


def _dispatch_saved_span(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the saved-span command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **saved_span(_required_path(args.art_dir))})


def _dispatch_arch_resume(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-resume command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **resume_facts(
            _required_text(args.work_dir),
            ResumeOptions(
                roster=_required_text(args.roster),
                assign=_required_text(args.assign),
                team=_required_text(args.proposal_team),
                plan=_required_text(args.round_plan),
            ),
        ),
    })


def _dispatch_arch_target(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-target command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **write_target(
            _required_text(args.draft),
            TargetOptions(
                arch_root=_required_text(args.arch_root),
                subject=_required_text(args.subject),
                forbid=split_ids(_required_text(args.forbid)),
                dry_run=args.dry_run,
                baseline=_required_text(args.baseline),
                seed=args.seed,
            ),
        ),
    })


def _dispatch_arch_state(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-state command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **arch_states(split_ids(_required_text(args.arch_files)), arch_root=args.arch_root)})


def _dispatch_arch_delta(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-delta command selected by the CLI.

    Returns:
        The selected command result.

    """
    listing: JsonObject = json_object(
        head | delta_items(_required_text(args.delta_dir), with_closure=not args.roots_only),
    )
    if args.save is not None:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")
        listing["saved"] = str(args.save)
    return json_object(listing)


def _dispatch_arch_closure(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-closure command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **write_closure(
            json.loads(Path(_required(args.closure)).read_text(encoding="utf-8")),
            _required_text(args.delta_dir),
            dry_run=args.dry_run,
        ),
    })


def _dispatch_closure_edges(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the closure-edges command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **closure_task_edges(_required_path(args.dir), split_ids(_required_text(args.repos)))})


def _dispatch_arch_target_remove(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-target-remove command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **remove_target(
            _required_text(args.arch_root),
            _required_text(args.target_dir),
            message=_required_text(args.message),
        ),
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


def _dispatch_arch_commit(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-commit command selected by the CLI.

    Returns:
        The selected command result.

    """
    files: list[str]
    files = files_from(args.files_from, "all") if args.files_from else split_ids(_required_text(args.files))
    return json_object({
        **head,
        **commit_integration(_required_text(args.arch_root), files, message=_required_text(args.message)),
    })


def _dispatch_arch_integration_files(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-integration-files command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **integration_files(
            _required_text(args.arch_root),
            IntegrationOptions(
                before=_required_path(args.before),
                report=_required_path(args.report),
                files_out=_required_path(args.files_out),
                last=args.last,
                save_last=args.save_last,
                accumulate=args.accumulate,
            ),
        ),
    })


def _dispatch_arch_review_check(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the arch-review-check command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({
        **head,
        **review_check(
            _required_path(args.review),
            files=_required_path(args.files),
            coverage_from=_required_path(args.coverage_from),
        ),
    })


def _dispatch_spec_ui_append(args: _CommandOptions, head: JsonObject) -> JsonObject:
    """Execute the spec-ui-append command selected by the CLI.

    Returns:
        The selected command result.

    """
    return json_object({**head, **spec_ui_append(_required_path(args.doc), _required_text(args.items))})


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
            _required_path(args.dir),
            slug=_required_text(args.slug),
            repo=_required_text(args.repo),
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
            _required_path(args.dir),
            slug=_required_text(args.slug),
            repo=_required_text(args.repo),
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
            _required_path(args.dir),
            split_ids(_required_text(args.repos)),
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
            _required_path(args.dir),
            split_ids(_required_text(args.repos)),
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
    result: JsonObject = json_object(apply_edges(graph, proposal, writer, seen, item, withdrawn, level))
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
            _required_text(args.blocker),
            _required_text(args.blocked),
            _required_text(args.reason),
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
    "tasks-inputs": _dispatch_tasks_inputs,
    "add-tasks": _dispatch_add_tasks,
    "plan-task-edges": _dispatch_plan_task_edges,
    "arch-approve": _dispatch_arch_approve,
    "arch-constraints": _dispatch_arch_constraints,
    "arch-constraints-restore": _dispatch_arch_constraints_restore,
    "arch-target-names": _dispatch_arch_target_names,
    "arch-snapshot": _dispatch_arch_snapshot,
    "arch-revision": _dispatch_arch_revision,
    "saved-target": _dispatch_saved_target,
    "saved-span": _dispatch_saved_span,
    "arch-resume": _dispatch_arch_resume,
    "arch-target": _dispatch_arch_target,
    "arch-state": _dispatch_arch_state,
    "arch-delta": _dispatch_arch_delta,
    "arch-closure": _dispatch_arch_closure,
    "closure-edges": _dispatch_closure_edges,
    "arch-target-remove": _dispatch_arch_target_remove,
    "arch-built-remove": _dispatch_arch_built_remove,
    "arch-commit": _dispatch_arch_commit,
    "arch-integration-files": _dispatch_arch_integration_files,
    "arch-review-check": _dispatch_arch_review_check,
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
        ResumeError,
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
