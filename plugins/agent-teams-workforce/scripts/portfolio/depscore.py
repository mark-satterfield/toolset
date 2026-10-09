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
from datetime import UTC, datetime
from pathlib import Path

import beadgraph
import relay
from archclosure import write_closure
from archfiles import files_from, integration_files, review_check
from archresume import ResumeError, resume_facts
from archrevision import check as revision_check
from archrevision import mark as revision_mark
from archstate import (
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
from scoring import ScoringError, judge_input, plan, record, rubric, score
from specui import SpecUiError, spec_ui_append
from storyedges import story_edges

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
    return value if value.tzinfo else value.replace(tzinfo=UTC)


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


def bead_status(bead_id: str, repo: Path | None) -> str | None:
    """Return a bead's status as `bd show` reports it, or None when it cannot be read.

    Args:
        bead_id: The bead.
        repo: The repository to run `bd` from, or None for the working directory.

    Returns:
        The status, or None.
    """
    try:
        shown = beadgraph._bd_json(["show", bead_id, "--json"], repo)
    except GraphError:
        return None
    record = shown[0] if isinstance(shown, list) and shown else shown
    status = record.get("status") if isinstance(record, dict) else None
    return str(status) if status else None


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
    common.add_argument(
        "--relay",
        type=Path,
        default=argparse.SUPPRESS,
        help="write the full result here and print its relay view with a checksum",
    )
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

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
        sv = sub.add_parser(name, help=f"{what}; no `bd` call", parents=[common])
        sv.add_argument(
            "--art-dir", type=Path, required=True, help="the Epic's artifacts directory"
        )

    sub.add_parser(
        "relay-read",
        help="print again the relay envelope of the result saved with --relay FILE; "
        "re-runs nothing; no `bd` call",
        parents=[common],
    )

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
    adt = sub.add_parser(
        "add-tasks",
        help="merge a corrective pass into a Story's saved Tasks and detailing; "
        "runs no `bd` command",
        parents=[common],
    )
    adt.add_argument(
        "--correction",
        required=True,
        type=Path,
        help="the accepted corrective pass: tasks, noWork, edges and scores",
    )
    wta = sub.add_parser(
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
        "--key", required=True, help="the Task's key, as plan-tasks lists it"
    )
    wta.add_argument(
        "--blocked-by-external",
        default="",
        help="Tasks of other Epics this Task is blocked by, comma-separated, beside the "
        "ones its saved blockedByExternal names",
    )
    tin = sub.add_parser(
        "tasks-inputs",
        help="whether a Story's saved Tasks were decomposed from the inputs they record, "
        "unchanged; runs no `bd` command",
        parents=[common],
    )
    rpt = sub.add_parser(
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
        "--reason", required=True, help="which input upstream of the Tasks changed"
    )
    for task_parser in (pta, adt, wta, tin, rpt):
        task_parser.add_argument(
            "--dir", required=True, type=Path, help="the Epic's working directory"
        )
        task_parser.add_argument(
            "--slug", required=True, help="the Story's repository slug"
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
    wae = sub.add_parser(
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
    cle = sub.add_parser(
        "closure-edges",
        help="the Task edges between Stories the delta's `requires` relations make, and "
        "warnings where a required item has no Task, no open bead and is not done; runs no "
        "`bd` command",
        parents=[common],
    )
    for edge_parser in (pte, wte, wae, cle):
        edge_parser.add_argument(
            "--dir", required=True, type=Path, help="the Epic's working directory"
        )
        edge_parser.add_argument(
            "--repos",
            required=True,
            help="the span, comma-separated, in its ruled order",
        )
    _dry_run_flag(wte)
    _dry_run_flag(wae)

    sed = sub.add_parser(
        "story-edges",
        help="derive and write the Story -> Story `blocks` edges",
        parents=[common],
    )
    _dry_run_flag(sed)

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

    aap = sub.add_parser(
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
        help="instead of --arch-files: the `touched` list of an arch-integration-files "
        "files file",
    )
    aap.add_argument(
        "--reviewed-from",
        type=Path,
        default=None,
        help="instead of --reviewed-files: the `reviewedFiles` list of a saved "
        "conformance review",
    )
    aap.add_argument(
        "--reviewed-files",
        default="",
        help="the files the conformance review checked and found conforming, "
        "comma-separated; only these are promoted",
    )
    aap.add_argument(
        "--arch-root",
        default=None,
        help="the architecture directory every `--arch-files` path must sit under",
    )
    _dry_run_flag(aap)

    acs = sub.add_parser(
        "arch-constraints",
        help="fingerprint section 2 of the effective architecture; writes nothing, runs no "
        "`bd` command",
        parents=[common],
    )
    acs.add_argument(
        "--arch-root", required=True, help="the architecture directory holding arc42/"
    )
    acs.add_argument(
        "--keep",
        action="store_true",
        help="copy section 2 to a new temporary directory, named in `kept`",
    )

    acr = sub.add_parser(
        "arch-constraints-restore",
        help="put section 2 back from the copy `arch-constraints --keep` made; runs no "
        "`bd` command",
        parents=[common],
    )
    acr.add_argument(
        "--arch-root", required=True, help="the architecture directory holding arc42/"
    )
    acr.add_argument(
        "--kept", required=True, help="the directory `arch-constraints --keep` named"
    )

    atn = sub.add_parser(
        "arch-target-names",
        help="tell which names an approved target's files mention; writes nothing, runs "
        "no `bd` command",
        parents=[common],
    )
    atn.add_argument("--target-dir", required=True, help="the target/<subject>/ folder")
    atn.add_argument("--names", required=True, help="the names, comma-separated")

    asn = sub.add_parser(
        "arch-snapshot",
        help="fingerprint every file of arc42/, target/ and built/; writes nothing but "
        "`--save`, runs no `bd` command",
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
        help="a fingerprint saved with --save; report the files created, changed and "
        "deleted since it (repeatable)",
    )
    asn.add_argument(
        "--counts",
        action="store_true",
        help="relay only the number of files created, changed and deleted per diff; the "
        "names stay in the relay file",
    )

    arv = sub.add_parser(
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
        "--work-dir", required=True, help="the architecture step's working directory"
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

    aif = sub.add_parser(
        "arch-integration-files",
        help="measure the files an integration wrote since its saved fingerprint, union them "
        "with the maintainer's report, and write the lists to a files file; relays counts; "
        "no `bd` call",
        parents=[common],
    )
    aif.add_argument("--arch-root", required=True, help="the architecture directory")
    aif.add_argument(
        "--before", type=Path, required=True, help="the fingerprint saved before"
    )
    aif.add_argument(
        "--report", type=Path, required=True, help="the maintainer's saved report"
    )
    aif.add_argument(
        "--files-out", type=Path, required=True, help="the files file to write"
    )
    aif.add_argument(
        "--last", type=Path, default=None, help="the previous measurement's fingerprint"
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

    arc = sub.add_parser(
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

    arz = sub.add_parser(
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
        "--round-plan", default="", help="validated durable round plan JSON"
    )

    atg = sub.add_parser(
        "arch-target",
        help="check an approved draft and write it to target/<subject>/ as in-review; "
        "runs no `bd` command",
        parents=[common],
    )
    atg.add_argument("--draft", required=True, help="the draft target directory")
    atg.add_argument(
        "--baseline",
        default="",
        help="validated survey JSON retaining baseline and implementation work",
    )
    atg.add_argument(
        "--arch-root", required=True, help="the architecture directory holding target/"
    )
    atg.add_argument(
        "--subject",
        required=True,
        help="the subject the target describes, as a display name or a folder name; "
        "the folder name is derived from it",
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

    ast = sub.add_parser(
        "arch-state",
        help="read the `lifecycle_state` of architecture files; writes nothing, runs no "
        "`bd` command",
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

    adl = sub.add_parser(
        "arch-delta",
        help="list the elements a target's delta shows, one item per element; writes "
        "nothing, runs no `bd` command",
        parents=[common],
    )
    adl.add_argument(
        "--delta-dir", required=True, help="the target/<subject>/delta/ directory"
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

    acl = sub.add_parser(
        "arch-closure",
        help="check a prerequisite closure against the delta and the open beads and write "
        "it beside the target's baseline as closure.json; reads beads, writes no bead",
        parents=[common],
    )
    acl.add_argument(
        "--closure", required=True, help="the closure the Closure phase saved"
    )
    acl.add_argument(
        "--delta-dir", required=True, help="the target/<subject>/delta/ directory"
    )
    _dry_run_flag(acl)

    atr = sub.add_parser(
        "arch-target-remove",
        help="delete target/<subject>/ and commit the removal; runs no `bd` command",
        parents=[common],
    )
    atr.add_argument(
        "--arch-root", required=True, help="the architecture directory holding target/"
    )
    atr.add_argument(
        "--target-dir", required=True, help="the target/<subject>/ folder to remove"
    )
    atr.add_argument("--message", required=True, help="the commit message")

    abr = sub.add_parser(
        "arch-built-remove",
        help="delete built/<subject>/ files the effective version now matches and commit "
        "the removal; runs no `bd` command",
        parents=[common],
    )
    abr.add_argument(
        "--arch-root", required=True, help="the architecture directory holding built/"
    )
    abr.add_argument(
        "--files", required=True, help="the built files to remove, comma-separated"
    )
    abr.add_argument("--message", required=True, help="the commit message")

    acm = sub.add_parser(
        "arch-commit",
        help="commit the architecture files an integration changed and push; runs no "
        "`bd` command",
        parents=[common],
    )
    acm.add_argument(
        "--arch-root",
        required=True,
        help="the architecture directory the files sit under",
    )
    acm.add_argument(
        "--files", default="", help="the integrated files to commit, comma-separated"
    )
    acm.add_argument(
        "--files-from",
        type=Path,
        default=None,
        help="instead of --files: the `all` list of an arch-integration-files files file",
    )
    acm.add_argument("--message", required=True, help="the commit message")

    sua = sub.add_parser(
        "spec-ui-append",
        help="write the ui items' design sources into a saved spec document; runs no `bd` "
        "command",
        parents=[common],
    )
    sua.add_argument("--doc", type=Path, required=True, help="the saved spec document")
    sua.add_argument(
        "--items",
        required=True,
        help="the repository's ui items as JSON: [{id, designSource?, buildSpec?, sections?}]",
    )

    cdb = sub.add_parser(
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
        "--recorded-bundle", default="", help="the bundle the Task's contract records"
    )

    rcf = sub.add_parser(
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
            args.dir,
            slug=args.slug,
            repo=args.repo,
            root=args.project_root,
            packages_dir=args.packages_dir,
        )
    if command == "tasks-inputs":
        return head | tasks_inputs(args.dir, slug=args.slug, root=args.project_root)
    if command == "add-tasks":
        return head | add_corrective_tasks(
            args.dir, slug=args.slug, correction=args.correction
        )
    if command == "plan-task-edges":
        return head | plan_task_edges(args.dir, split_ids(args.repos))
    if command == "arch-approve":
        files = (
            files_from(args.arch_files_from, "touched")
            if args.arch_files_from
            else split_ids(args.arch_files)
        )
        if args.dry_run:
            return head | {
                "dryRun": True,
                "wouldApprove": files,
                "summary": {"dryRun": True, "files": len(files)},
            }
        return head | approve_arch(
            files,
            arch_root=args.arch_root,
            reviewed=files_from(args.reviewed_from, "reviewedFiles")
            if args.reviewed_from
            else split_ids(args.reviewed_files),
        )
    if command == "arch-constraints":
        return head | snapshot_constraints(args.arch_root, keep=args.keep)
    if command == "arch-constraints-restore":
        return head | restore_constraints(args.arch_root, args.kept)
    if command == "arch-target-names":
        return head | target_names(args.target_dir, split_ids(args.names))
    if command == "arch-snapshot":
        result = head | snapshot_tree(args.arch_root)
        if "error" in result:
            return result
        diffs = [
            {"against": str(p)}
            | tree_diff(json.loads(p.read_text(encoding="utf-8")), result)
            for p in args.against
        ]
        if args.save is not None:
            args.save.parent.mkdir(parents=True, exist_ok=True)
            args.save.write_text(json.dumps(result), encoding="utf-8")
            result["saved"] = str(args.save)
        if args.save is not None or args.against:
            result.pop("files", None)
            result["diffs"] = diffs
        if args.counts:
            result["countsOnly"] = True
        return result
    if command == "arch-revision":
        if args.action == "mark":
            if not args.state:
                why = "arch-revision mark needs --state integrating or integrated"
                return head | {
                    "ok": False,
                    "error": why,
                    "summary": {"ok": False, "error": why},
                }
            return head | revision_mark(args.arch_root, args.work_dir, args.state)
        return head | revision_check(args.arch_root, args.work_dir, args.stale_root)
    if command == "saved-target":
        return head | saved_target(args.art_dir)
    if command == "saved-span":
        return head | saved_span(args.art_dir)
    if command == "arch-resume":
        return head | resume_facts(
            args.work_dir,
            roster=args.roster,
            assign=args.assign,
            team=args.proposal_team,
            plan=args.round_plan,
        )
    if command == "arch-target":
        return head | write_target(
            args.draft,
            arch_root=args.arch_root,
            subject=args.subject,
            forbid=split_ids(args.forbid),
            dry_run=args.dry_run,
            baseline=args.baseline,
            seed=args.seed,
        )
    if command == "arch-state":
        return head | arch_states(split_ids(args.arch_files), arch_root=args.arch_root)
    if command == "arch-delta":
        listing = head | delta_items(args.delta_dir, with_closure=not args.roots_only)
        if args.save is not None:
            args.save.parent.mkdir(parents=True, exist_ok=True)
            args.save.write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")
            listing["saved"] = str(args.save)
        return listing
    if command == "arch-closure":
        return head | write_closure(
            json.loads(Path(args.closure).read_text(encoding="utf-8")),
            args.delta_dir,
            dry_run=args.dry_run,
        )
    if command == "closure-edges":
        return head | closure_task_edges(args.dir, split_ids(args.repos))
    if command == "arch-target-remove":
        return head | remove_target(
            args.arch_root, args.target_dir, message=args.message
        )
    if command == "arch-built-remove":
        return head | remove_built(
            args.arch_root, split_ids(args.files), message=args.message
        )
    if command == "arch-commit":
        files = (
            files_from(args.files_from, "all")
            if args.files_from
            else split_ids(args.files)
        )
        return head | commit_integration(args.arch_root, files, message=args.message)
    if command == "arch-integration-files":
        return head | integration_files(
            args.arch_root,
            before=args.before,
            report=args.report,
            files_out=args.files_out,
            last=args.last,
            save_last=args.save_last,
            accumulate=args.accumulate,
        )
    if command == "arch-review-check":
        return head | review_check(
            args.review,
            files=args.files,
            coverage_from=args.coverage_from,
        )
    if command == "spec-ui-append":
        return head | spec_ui_append(args.doc, args.items)
    if command == "recon-facts":
        return head | recon_facts(args.file, split_ids(args.items))
    if command == "cds-bundles":
        listing = list_bundles(args.packages_dir)
        if args.design_source:
            listing["selection"] = select_build(
                args.packages_dir,
                args.design_source,
                {"kind": args.kind, "slug": args.slug},
                args.recorded_bundle,
            )
        return head | listing | {"summary": {"bundles": len(listing["bundles"])}}
    writer = Writer(args.directory, dry_run=getattr(args, "dry_run", False))
    if command == "replace-tasks":
        return head | replace_tasks(
            writer, args.epic, slug=args.slug, reason=args.reason
        )
    if command == "write-task":
        return head | write_task(
            writer,
            args.epic,
            args.dir,
            slug=args.slug,
            repo=args.repo,
            key=args.key,
            root=args.project_root,
            external=split_ids(args.blocked_by_external),
            packages_dir=args.packages_dir,
        )
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
    if command == "write-all-task-edges":
        return head | write_all_task_edges(
            graph,
            writer,
            args.epic,
            args.dir,
            split_ids(args.repos),
            split_ids(args.also) if args.also else [],
        )
    if command == "story-edges":
        return head | story_edges(graph, writer)
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
    if (
        command in ("validate", "apply-edges")
        and args.edges
        and bool(args.epic) == bool(args.task)
    ):
        msg = "an edge proposal covers exactly one Epic or one Task: pass --epic or --task"
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
        if level == "task" and result.get("applied") and not writer.dry_run:
            result["storyEdges"] = _story_edges_after(args.directory)
            summary["storyEdges"] = _story_edges_summary(result["storyEdges"])
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
        finished = finish(graph, writer, args.epic, owner=args.owner, done=args.done)
        if not writer.dry_run:
            finished["storyEdges"] = _story_edges_after(args.directory)
            finished.setdefault("summary", {})["storyEdges"] = _story_edges_summary(
                finished["storyEdges"]
            )
        return head | finished
    if command == "elaboration-release":
        return head | release(graph, writer, args.epic, owner=args.owner)
    return head | score(graph, writer)


def _story_edges_after(directory: Path | None) -> dict:
    """Run `story-edges` over the tracker as it stands after a command wrote Task edges.

    Args:
        directory: The repository to run `bd` from, or None for the working directory.

    Returns:
        The `story-edges` result, or `{ok: false, error}` when the tracker could not be read
        through `bd`.
    """
    try:
        graph = beadgraph.load(directory)
        return story_edges(graph, Writer(directory))
    except GraphError as exc:
        return {"ok": False, "error": str(exc)}


def _story_edges_summary(result: dict) -> dict:
    """The part of a `story-edges` result a caller's summary carries.

    Args:
        result: The `story-edges` result.

    Returns:
        Its summary, with the refusal's conflicts and cycles, or its error.
    """
    if result.get("error"):
        return {"ok": False, "error": result["error"]}
    out = dict(result.get("summary") or {})
    if result.get("refused"):
        out["conflicts"] = result.get("conflicts") or []
        out["cycles"] = result.get("cycles") or []
    return out


def main(argv: list[str] | None = None) -> int:
    """Entry point. Prints one JSON object; exit 2 means the command refused, exit 3 that the
    command line was not the one its `--argv-sha256` names (nothing ran).

    Args:
        argv: The command line, or None for `sys.argv`.

    Returns:
        The process exit status.
    """
    argv, typed_wrong = relay.argv_mismatch(
        list(sys.argv[1:] if argv is None else argv)
    )
    if typed_wrong:
        print(relay.line(relay.mismatch_envelope(typed_wrong)))
        return 3
    args = build_parser().parse_args(argv)
    args.directory = getattr(args, "directory", None)
    out = getattr(args, "out", None)
    relay_file = getattr(args, "relay", None)
    if args.command == "relay-read":
        if relay_file is None:
            print(json.dumps({"error": "relay-read needs --relay FILE"}, indent=2))
            return 2
        try:
            shown = relay.read(relay_file)
        except (relay.RelayError, json.JSONDecodeError, OSError) as exc:
            print(json.dumps({"error": str(exc), "command": args.command}, indent=2))
            return 2
        print(relay.line(shown))
        return shown["~exit"]
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
        cause = getattr(exc, "cause", beadgraph.OTHER_CAUSE)
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
            shown = relay.write(args.command, payload, relay_file, status)
        except (relay.RelayError, OSError) as exc:
            print(
                json.dumps(
                    {"error": f"--relay: {exc}", "command": args.command}, indent=2
                )
            )
            return 2
        print(relay.line(shown))
        return status
    print(json.dumps(payload, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
