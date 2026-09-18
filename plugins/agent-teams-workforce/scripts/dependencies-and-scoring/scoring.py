#!/usr/bin/env python3
"""WSJF over the tracker graph: what needs judging, recording judgments, and the arithmetic.

A score has two kinds of input.

* JUDGED inputs come from a model applying the `agent-teams-workforce:wsjf` rubric: an
  Epic's User-Business Value, Time Criticality, confidence and — while it has no Tasks —
  its span Job Size, all judged from its PRD, which is the Epic's own description; and a
  Task's Job Size, judged from the Task's own content. Each judged value is stored with the
  content fingerprint of the bead it was judged from, under `wsjf_content_hash`. A judged
  input is judged again only when that fingerprint no longer matches the bead, when it was
  never judged, or when the caller asks for everything. A judged value that carries no
  fingerprint was judged by whoever wrote it from the content the bead holds, and is
  adopted: the current fingerprint is recorded beside it.
* COMPUTED inputs are arithmetic and are recomputed over the WHOLE portfolio on every run:
  Epic RR-OE from transitive reachability over the Epic edges, Epic Job Size from the sum
  of its Tasks' sizes once Tasks exist, Task RR-OE from reachability over the Task edges,
  a Task's inherited UBV, TC and confidence, and every WSJF. Recomputing all of it is what
  carries a change through upstream and downstream dependencies without anyone tracing it.

Epics and Tasks are scored in the same call, from the same read of the tracker, so an Epic
is never scored without its Tasks. The bands, the scales and the roll-up belong to the
rubric's `wsjf.py`, which this module calls. Only values that changed are written.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

from beadgraph import fingerprints

if TYPE_CHECKING:
    from beadgraph import Bead, Graph, Writer

#: The WSJF rubric's own implementation, loaded from the skill that owns it.
WSJF_PATH = (
    Path(__file__).resolve().parents[2] / "skills" / "wsjf" / "scripts" / "wsjf.py"
)

#: The metadata key holding the fingerprint of the content a judged value was judged from.
JUDGED_HASH_KEY = "wsjf_content_hash"

#: Metadata that changes on every write and so never, by itself, justifies one.
VOLATILE_KEYS = frozenset({"wsjf_calculated_at"})


class ScoringError(RuntimeError):
    """A judgment file the recorder cannot work from."""


def _load_wsjf():  # noqa: ANN202
    """Load the WSJF module from the skill that owns the arithmetic.

    Returns:
        The imported module.

    Raises:
        ImportError: The module could not be loaded from `WSJF_PATH`.
    """
    spec = importlib.util.spec_from_file_location("wsjf", WSJF_PATH)
    if spec is None or spec.loader is None:
        msg = f"cannot load the WSJF rubric from {WSJF_PATH}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rubric = _load_wsjf()


def _int(value: Any) -> int | None:
    """Parse a metadata integer, returning None when it is absent or unusable.

    Args:
        value: The raw metadata value.

    Returns:
        The integer, or None when there is not one.
    """
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _same(stored: str | None, fresh: str) -> bool:
    """Whether a stored metadata value already equals a recomputed one.

    `bd` hands numbers back as JSON numbers, so `3.00` returns as `3`; two values that
    parse to the same number are the same value.

    Args:
        stored: The value on the bead, or None.
        fresh: The recomputed value.

    Returns:
        True when writing `fresh` would change nothing.
    """
    if stored is None:
        return False
    if stored == fresh:
        return True
    try:
        return float(stored) == float(fresh)
    except ValueError:
        return False


def _write(bead: Bead, pairs: dict[str, str], writer: Writer) -> bool:
    """Write metadata onto a bead unless every non-volatile value is already there.

    Args:
        bead: The bead being written.
        pairs: The metadata to store.
        writer: The tracker writer; a dry-run writer records the write instead.

    Returns:
        True when the bead is written, or would be in a dry run.
    """
    changed = any(
        not _same(bead.metadata.get(k), v)
        for k, v in pairs.items()
        if k not in VOLATILE_KEYS
    )
    if changed:
        writer.metadata(bead.id, pairs)
    return changed


def _open(graph: Graph, kind: str) -> list[Bead]:
    """Every open bead of one kind, in id order.

    Args:
        graph: The tracker graph.
        kind: The issue type.

    Returns:
        The beads.
    """
    return [b for b in graph.of_kind(kind) if not b.closed]


def _tasks_of(graph: Graph, epic: Bead) -> list[Bead]:
    """Every Task beneath an Epic at any depth, closed ones included.

    Args:
        graph: The tracker graph.
        epic: The Epic.

    Returns:
        The Tasks. Closed Tasks count toward the roll-up: the cost is the whole job.
    """
    return [b for b in graph.descendants(epic.id) if b.kind == "task"]


# ------------------------------------------------------------------------------------
# What needs judging
# ------------------------------------------------------------------------------------


def _judge_reason(
    bead: Bead, required: tuple[str, ...], current: str, everything: bool
) -> str:
    """Why a bead's judged inputs must be judged in this run, or "" when they need not be.

    Args:
        bead: The bead.
        required: The judged metadata keys it must carry.
        current: Its content fingerprint now.
        everything: True when the caller asked for every judged input to be judged again.

    Returns:
        The reason, or "" when the stored judgment still stands.
    """
    if everything:
        return "--all re-judges every judged input"
    if any(bead.metadata.get(k) in (None, "") for k in required):
        return "not judged yet"
    stored = bead.metadata.get(JUDGED_HASH_KEY)
    if stored and stored != current:
        return "its content changed since it was judged"
    return ""


def plan(graph: Graph, *, everything: bool) -> dict:
    """Decide which judged inputs this run must judge, and whether the sequencer must run.

    Args:
        graph: The tracker graph, read with descriptions.
        everything: True to judge every judged input regardless of fingerprints.

    Returns:
        The Epics and Tasks to judge with a reason each, the judged values to adopt,
        whether the sequencer runs and why, every open Epic's and Task's fingerprint, and
        a summary of counts.
    """
    prints = fingerprints(graph.records)
    epics = _open(graph, "epic")
    adopt: list[str] = []
    judge_epics = []
    for epic in epics:
        required = ("wsjf_ubv", "wsjf_tc", "wsjf_confidence")
        if not _tasks_of(graph, epic):
            required += ("wsjf_size",)
        reason = _judge_reason(epic, required, prints.get(epic.id, ""), everything)
        if not reason and not epic.metadata.get(JUDGED_HASH_KEY):
            adopt.append(epic.id)
        if reason:
            judge_epics.append({"id": epic.id, "reason": reason})
    judge_tasks = []
    for task in _open(graph, "task"):
        reason = _judge_reason(
            task, ("wsjf_size",), prints.get(task.id, ""), everything
        )
        if not reason and not task.metadata.get(JUDGED_HASH_KEY):
            adopt.append(task.id)
        if reason:
            epic = graph.epic_of(task.id)
            judge_tasks.append(
                {"id": task.id, "epic": epic.id if epic else None, "reason": reason}
            )

    sequence_why: list[str] = []
    if everything:
        sequence_why.append("--all re-derives the edges")
    unseen = [
        e.id for e in epics if e.metadata.get("seq_content_hash") != prints.get(e.id)
    ]
    if unseen and not everything:
        sequence_why.append(
            f"{len(unseen)} open Epic(s) are new or changed since the sequencer last read them"
        )
    ids = {e.id for e in epics} | {t.id for t in _open(graph, "task")}
    return {
        "sequence": {"run": bool(sequence_why), "why": sequence_why, "epics": unseen},
        "judge": {"epics": judge_epics, "tasks": judge_tasks},
        "adopt": adopt,
        "fingerprints": {i: prints[i] for i in sorted(ids) if i in prints},
        "summary": {
            "sequence": bool(sequence_why),
            "sequenceWhy": sequence_why,
            "openEpics": len(epics),
            "epicsToJudge": len(judge_epics),
            "tasksToJudge": len(judge_tasks),
            "toAdopt": len(adopt),
        },
    }


def judge_input(graph: Graph, the_plan: dict, level: str) -> dict:
    """The material one judging session reads: the whole portfolio at one level.

    Every open item is included, whether or not it is judged in this run, because the
    rubric judges against descriptive rungs and a session can only place an item on them
    by comparing it with the rest. Items not being judged carry their current judged
    values as that comparison set; items being judged carry none, so the session judges
    them from their content. No computed value is included: RR-OE, reachability and
    WSJF are arithmetic over the graph and are not the session's to see or set.

    Args:
        graph: The tracker graph, read with descriptions.
        the_plan: The run's plan, from `plan`.
        level: `epic` or `task`.

    Returns:
        The items, each flagged `judge` with its reason when it is to be judged.
    """
    wanted = {j["id"]: j["reason"] for j in the_plan["judge"][f"{level}s"]}
    items = []
    for bead in _open(graph, level):
        entry: dict[str, Any] = {
            "id": bead.id,
            "title": bead.title,
            "description": bead.description,
            "judge": bead.id in wanted,
            "reason": wanted.get(bead.id),
        }
        if level == "epic":
            has_tasks = bool(_tasks_of(graph, bead))
            entry["hasTasks"] = has_tasks
            entry["current"] = (
                None
                if entry["judge"]
                else {
                    "userBusinessValue": _int(bead.metadata.get("wsjf_ubv")),
                    "timeCriticality": _int(bead.metadata.get("wsjf_tc")),
                    "jobSize": None
                    if has_tasks
                    else _int(bead.metadata.get("wsjf_size")),
                    "confidence": _int(bead.metadata.get("wsjf_confidence")),
                }
            )
        else:
            epic = graph.epic_of(bead.id)
            entry["epic"] = {"id": epic.id, "title": epic.title} if epic else None
            entry["current"] = (
                None
                if entry["judge"]
                else {"jobSize": _int(bead.metadata.get("wsjf_size"))}
            )
        items.append(entry)
    return {
        "level": level,
        "items": items,
        "summary": {"items": len(items), "toJudge": len(wanted)},
    }


# ------------------------------------------------------------------------------------
# Recording judgments
# ------------------------------------------------------------------------------------


def _positive(record: dict, key: str, bead_id: str) -> int:
    """Read one judged value as a positive integer.

    Args:
        record: The judgment for one item.
        key: The field.
        bead_id: The item, for the error message.

    Returns:
        The value.

    Raises:
        ScoringError: The value is missing or not a positive integer.
    """
    value = _int(record.get(key))
    if value is None or value <= 0:
        msg = f"{bead_id}: `{key}` must be a positive integer, got {record.get(key)!r}"
        raise ScoringError(msg)
    return value


def _judged_pairs(graph: Graph, level: str, bead: Bead, one: dict) -> dict[str, str]:
    """The metadata one judgment writes, with every judged value validated.

    Args:
        graph: The tracker graph.
        level: `epic` or `task`.
        bead: The judged bead.
        one: The judgment for it.

    Returns:
        The judged keys and their values, without the fingerprint.

    Raises:
        ScoringError: A judged value is missing or not a positive integer.
    """
    pairs: dict[str, str] = {}
    if level == "epic":
        pairs["wsjf_ubv"] = str(_positive(one, "userBusinessValue", bead.id))
        pairs["wsjf_tc"] = str(_positive(one, "timeCriticality", bead.id))
        pairs["wsjf_confidence"] = str(_positive(one, "confidence", bead.id))
        if not _tasks_of(graph, bead):
            pairs["wsjf_size"] = str(_positive(one, "jobSize", bead.id))
    else:
        pairs["wsjf_size"] = str(_positive(one, "jobSize", bead.id))
    return pairs


def record(
    graph: Graph, the_plan: dict, judgments: dict[str, list[dict]], writer: Writer
) -> dict:
    """Write judged values, each with the fingerprint of the content it was judged from.

    The plan's adopted values get their fingerprint recorded beside them. Only items the
    plan named for judging are written; a judgment for anything else is refused, because
    it was not asked for and carries no fingerprint from this run. Every judgment is
    validated before anything is written, so a bad value refuses the whole record.

    Args:
        graph: The tracker graph.
        the_plan: The run's plan, from `plan`.
        judgments: `epic` and `task` lists of the rubric's per-item scores.
        writer: The tracker writer; a dry-run writer records the writes instead.

    Returns:
        What was written, what the plan asked for and did not receive, a summary, and —
        in a dry run — every write in order.

    Raises:
        ScoringError: A judgment names an item outside the plan or carries a bad value.
    """
    prints = the_plan["fingerprints"]
    missing: list[str] = []
    pending: list[tuple[Bead, dict[str, str]]] = []
    for level in ("epic", "task"):
        asked = {j["id"] for j in the_plan["judge"][f"{level}s"]}
        got = {str(r.get("id")): r for r in judgments.get(level, [])}
        stray = sorted(set(got) - asked)
        if stray:
            msg = (
                f"{level} judgments for items the plan did not name: {', '.join(stray)}"
            )
            raise ScoringError(msg)
        missing += sorted(asked - set(got))
        for bead_id in sorted(asked & set(got)):
            bead = graph.beads.get(bead_id)
            if bead is None:
                missing.append(bead_id)
                continue
            pairs = {JUDGED_HASH_KEY: prints.get(bead_id, "")}
            pairs |= _judged_pairs(graph, level, bead, got[bead_id])
            pending.append((bead, pairs))
    written = [bead.id for bead, pairs in pending if _write(bead, pairs, writer)]
    adopted: list[str] = []
    for bead_id in the_plan.get("adopt", []):
        bead = graph.beads.get(bead_id)
        if bead is not None and prints.get(bead_id):
            writer.metadata(bead_id, {JUDGED_HASH_KEY: prints[bead_id]})
            adopted.append(bead_id)
    return {
        "dryRun": writer.dry_run,
        "written": written,
        "adopted": adopted,
        "missing": missing,
        "planned": writer.planned,
        "summary": {
            "dryRun": writer.dry_run,
            "written": len(written),
            "adopted": len(adopted),
            "missing": len(missing),
        },
    }


# ------------------------------------------------------------------------------------
# The arithmetic
# ------------------------------------------------------------------------------------


def _edges(beads: list[Bead]) -> list[dict[str, str]]:
    """The blocking edges among a set of beads, as the rubric takes them.

    Args:
        beads: The beads whose mutual edges are wanted.

    Returns:
        `from` must come before `to`.
    """
    ids = {b.id for b in beads}
    return [
        {"from": blocker, "to": b.id}
        for b in beads
        for blocker in b.blockers
        if blocker in ids
    ]


def _epic_items(graph: Graph, epics: list[Bead]) -> tuple[list[dict], list[dict]]:
    """The rubric input for every open Epic, and what is missing from it.

    Args:
        graph: The tracker graph.
        epics: The open Epics.

    Returns:
        The items, and the incomplete records.
    """
    items: list[dict] = []
    incomplete: list[dict] = []
    for epic in epics:
        item: dict[str, Any] = {
            "id": epic.id,
            "userBusinessValue": _int(epic.metadata.get("wsjf_ubv")),
            "timeCriticality": _int(epic.metadata.get("wsjf_tc")),
            "confidence": _int(epic.metadata.get("wsjf_confidence")),
        }
        tasks = _tasks_of(graph, epic)
        sizes = [_int(t.metadata.get("wsjf_size")) for t in tasks]
        if tasks and all(s is not None for s in sizes):
            item["childSizes"] = sizes
        else:
            item["jobSize"] = _int(epic.metadata.get("wsjf_size"))
            unsized = [t.id for t, s in zip(tasks, sizes, strict=True) if s is None]
            if unsized:
                incomplete.append(
                    {
                        "id": epic.id,
                        "reason": "Tasks carry no wsjf_size, so no roll-up: "
                        + ", ".join(unsized),
                    }
                )
        items.append(item)
    return items, incomplete


def _task_items(graph: Graph, tasks: list[Bead]) -> list[dict]:
    """The rubric input for every open Task, with value inherited from its Epic.

    Args:
        graph: The tracker graph.
        tasks: The open Tasks.

    Returns:
        The items. A Task with no Epic, or under an unjudged one, carries no value and
        comes back unscored from the rubric.
    """
    items = []
    for task in tasks:
        epic = graph.epic_of(task.id)
        meta = epic.metadata if epic else {}
        items.append(
            {
                "id": task.id,
                "userBusinessValue": _int(meta.get("wsjf_ubv")),
                "timeCriticality": _int(meta.get("wsjf_tc")),
                "confidence": _int(meta.get("wsjf_confidence")),
                "valueFrom": epic.id if epic else None,
                "jobSize": _int(task.metadata.get("wsjf_size")),
            }
        )
    return items


def _apply(graph: Graph, result: dict, writer: Writer) -> list[dict]:
    """Write every scored item whose values changed.

    Args:
        graph: The tracker graph.
        result: The rubric's `score` output.
        writer: The tracker writer; a dry-run writer records the writes instead.

    Returns:
        One record per scored item, marked with whether it is written.
    """
    rows = []
    for scored in result["scores"]:
        bead = graph.beads[scored["id"]]
        rows.append(
            {
                "id": bead.id,
                "wsjf": scored["wsjf"],
                "costOfDelay": scored["costOfDelay"],
                "rroe": scored["riskReductionOpportunityEnablement"],
                "reaches": scored["reaches"],
                "jobSize": scored["jobSize"],
                "sizeSource": scored["sizeSource"],
                "written": _write(bead, scored["metadata"], writer),
            }
        )
    return rows


def score(graph: Graph, writer: Writer) -> dict:
    """Recompute every open Epic's and every open Task's WSJF, and write what changed.

    The edge lists handed to the rubric are the whole graph at each level, so a level
    with no edges scores every item as reaching nothing.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the writes instead.

    Returns:
        The Epic and Task scores, everything that could not be scored and why, size
        faults, any cycle, a summary, and — in a dry run — every write in order.
    """
    epics = _open(graph, "epic")
    tasks = _open(graph, "task")
    epic_items, incomplete = _epic_items(graph, epics)
    epic_result = rubric.score({"edges": _edges(epics), "items": epic_items}, "epic")
    task_result = rubric.score(
        {"edges": _edges(tasks), "items": _task_items(graph, tasks)}, "task"
    )
    epic_rows = _apply(graph, epic_result, writer)
    task_rows = _apply(graph, task_result, writer)
    unscored = [{"level": "epic", **u} for u in epic_result["unscored"]] + [
        {"level": "task", **u} for u in task_result["unscored"]
    ]
    return {
        "epics": epic_rows,
        "tasks": task_rows,
        "unscored": unscored,
        "incomplete": incomplete,
        "sizeFaults": epic_result["sizeFaults"] + task_result["sizeFaults"],
        "cycles": {"epic": epic_result["cycle"], "task": task_result["cycle"]},
        "dryRun": writer.dry_run,
        "planned": writer.planned,
        "summary": {
            "dryRun": writer.dry_run,
            "epicsScored": len(epic_rows),
            "epicsWritten": sum(r["written"] for r in epic_rows),
            "tasksScored": len(task_rows),
            "tasksWritten": sum(r["written"] for r in task_rows),
            "unscored": len(unscored),
            "incomplete": len(incomplete),
            "epicCycle": epic_result["cycle"],
            "taskCycle": task_result["cycle"],
        },
    }
