#!/usr/bin/env python3
"""WSJF over the tracker graph: what needs judging, recording judgments, and the arithmetic.

A score has two kinds of input.

* JUDGED inputs come from a model applying the `agent-teams-workforce:wsjf` rubric: an
  Epic's User-Business Value, Time Criticality, confidence and — while it has no Tasks —
  its Job Size estimate, all judged from its PRD, which is the Epic's own description; and
  a Task's Job Size estimate, judged from the Task's own content. Every size estimate
  carries a plausible range and a confidence. Each judged value is stored with the
  content fingerprint of the bead it was judged from, under `wsjf_content_hash`. A value
  that is missing, or whose fingerprint no longer matches the bead, is always judged. A
  value that is present — current, or carrying no fingerprint — is included only when the
  caller includes items that already have a value; an included value is judged again when
  the caller asks for re-judging, and otherwise kept, a value with no fingerprint gaining
  the fingerprint of the content it now describes.
* COMPUTED inputs are arithmetic and are recomputed over the WHOLE portfolio on every run:
  Epic RR-OE from transitive reachability over the Epic edges, Epic Job Size as the plain
  sum of its Tasks' sizes once Tasks exist — flagged when it falls outside the range of the
  Epic's own estimate — Task RR-OE from reachability over the Task edges,
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
from summaries import write_prds

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

#: The judged size keys. `record` writes them; `score` reads them and never writes them.
ESTIMATE_KEY = "wsjf_size_estimate"
SIZE_JUDGED_KEYS = (
    ESTIMATE_KEY,
    "wsjf_size_low",
    "wsjf_size_high",
    "wsjf_size_confidence",
)


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


def _judged_state(bead: Bead, required: tuple[str, ...], current: str) -> str:
    """The state of a bead's judged inputs.

    Args:
        bead: The bead.
        required: The judged metadata keys it must carry.
        current: Its content fingerprint now.

    Returns:
        `missing` when a judged value is absent, `changed` when the fingerprint recorded
        with the values no longer matches the bead, `unfingerprinted` when values are
        present with no fingerprint beside them, and `current` otherwise.
    """
    if any(bead.metadata.get(k) in (None, "") for k in required):
        return "missing"
    stored = bead.metadata.get(JUDGED_HASH_KEY)
    if not stored:
        return "unfingerprinted"
    if stored != current:
        return "changed"
    return "current"


#: Why an item in each state is judged.
JUDGE_REASONS = {
    "missing": "not judged yet",
    "changed": "its content changed since it was judged",
    "unfingerprinted": "--rejudge re-judges existing values",
    "current": "--rejudge re-judges existing values",
}


def _disposition(state: str, *, include_all: bool, rejudge: bool) -> str:
    """What this run does with an item's judged inputs.

    Missing and changed values are always judged. Values that are present and not known
    to be stale — unfingerprinted or current — are left alone unless `include_all`
    includes them; an included one is judged again under `rejudge`, and otherwise kept,
    an unfingerprinted one gaining the fingerprint of the content it now describes.

    Args:
        state: The item's state, from `_judged_state`.
        include_all: Whether items that already have a value are included.
        rejudge: Whether included existing values are judged again.

    Returns:
        `judge`, `adopt` or `keep`.
    """
    if state in ("missing", "changed"):
        return "judge"
    if not include_all:
        return "keep"
    if rejudge:
        return "judge"
    return "adopt" if state == "unfingerprinted" else "keep"


def plan(graph: Graph, *, include_all: bool, rejudge: bool) -> dict:
    """Decide which judged inputs this run judges, and which stored ones it adopts.

    Args:
        graph: The tracker graph, read with descriptions.
        include_all: Include items that already have a value.
        rejudge: Judge again the existing values of the items included.

    Returns:
        The Epics and Tasks to judge with a reason each, the judged values to adopt,
        every open Epic's and Task's fingerprint, and a summary of counts.
    """
    prints = fingerprints(graph.records)
    epics = _open(graph, "epic")
    tasks = _open(graph, "task")
    adopt: list[str] = []
    states: dict[str, int] = {}
    judge: dict[str, list[dict]] = {"epics": [], "tasks": []}
    for level, beads in (("epics", epics), ("tasks", tasks)):
        for bead in beads:
            if level == "epics":
                required = ("wsjf_ubv", "wsjf_tc", "wsjf_confidence")
                if not _tasks_of(graph, bead):
                    required += SIZE_JUDGED_KEYS
            else:
                required = SIZE_JUDGED_KEYS
            state = _judged_state(bead, required, prints.get(bead.id, ""))
            states[state] = states.get(state, 0) + 1
            action = _disposition(state, include_all=include_all, rejudge=rejudge)
            if action == "adopt":
                adopt.append(bead.id)
            elif action == "judge":
                entry = {"id": bead.id, "reason": JUDGE_REASONS[state]}
                if level == "tasks":
                    epic = graph.epic_of(bead.id)
                    entry["epic"] = epic.id if epic else None
                judge[level].append(entry)
    ids = {e.id for e in epics} | {t.id for t in tasks}
    return {
        "judge": judge,
        "adopt": adopt,
        "fingerprints": {i: prints[i] for i in sorted(ids) if i in prints},
        "summary": {
            "includeAll": include_all,
            "rejudge": rejudge,
            "openEpics": len(epics),
            "openTasks": len(tasks),
            "states": states,
            "epicsToJudge": len(judge["epics"]),
            "tasksToJudge": len(judge["tasks"]),
            "toAdopt": len(adopt),
        },
    }


def _size_of(bead: Bead) -> dict[str, int | None]:
    """A bead's judged size estimate with its range and confidence.

    Args:
        bead: The bead.

    Returns:
        `jobSize`, `sizeLow`, `sizeHigh` and `sizeConfidence`, None where absent.
    """
    return {
        "jobSize": _int(bead.metadata.get(ESTIMATE_KEY)),
        "sizeLow": _int(bead.metadata.get("wsjf_size_low")),
        "sizeHigh": _int(bead.metadata.get("wsjf_size_high")),
        "sizeConfidence": _int(bead.metadata.get("wsjf_size_confidence")),
    }


def reference_jobs(graph: Graph) -> list[dict]:
    """The elaborated Epics: each one's original estimate beside its refined size.

    An Epic is a reference job once it has Tasks and every one of them is sized. Its
    refined size is the sum of those sizes, so each reference job shows how an estimate
    made before the work was known compared with the work as decomposed.

    Args:
        graph: The tracker graph.

    Returns:
        One record per reference job, in id order.
    """
    jobs = []
    for epic in graph.of_kind("epic"):
        tasks = _tasks_of(graph, epic)
        sizes = [_int(t.metadata.get("wsjf_size")) for t in tasks]
        if not tasks or any(size is None for size in sizes):
            continue
        estimate = _size_of(epic)
        jobs.append(
            {
                "id": epic.id,
                "title": epic.title,
                "estimate": estimate["jobSize"],
                "low": estimate["sizeLow"],
                "high": estimate["sizeHigh"],
                "refinedSize": sum(s for s in sizes if s is not None),
                "tasks": len(tasks),
            }
        )
    return jobs


def judge_input(
    graph: Graph, the_plan: dict, level: str, prd_dir: Path | None = None
) -> dict:
    """The material one judging session reads: the whole portfolio at one level.

    Every open item is included, whether or not it is judged in this run, because the
    rubric judges against descriptive rungs and reference jobs, and a session can only
    place an item by comparing it with the rest. Items not being judged carry their
    current judged values as that comparison set; items being judged carry none, so the
    session judges them from their content. The reference jobs — elaborated Epics with
    their original estimate and refined size — are the size comparison at both levels.
    No computed value is included: RR-OE, reachability and WSJF are arithmetic over the
    graph and are not the session's to see or set.

    A Task carries its own description. An Epic carries no PRD text: the session reads the
    portfolio through the Epic summaries, and with `prd_dir` every Epic's PRD is written
    to a file the item names, for the session to read in full where it judges.

    Args:
        graph: The tracker graph, read with descriptions.
        the_plan: The run's plan, from `plan`.
        level: `epic` or `task`.
        prd_dir: Where to write each open Epic's PRD, or None.

    Returns:
        The items, each flagged `judge` with its reason when it is to be judged, and the
        reference jobs.
    """
    wanted = {j["id"]: j["reason"] for j in the_plan["judge"][f"{level}s"]}
    beads = _open(graph, level)
    paths = write_prds(beads, prd_dir) if level == "epic" and prd_dir else {}
    items = []
    for bead in beads:
        entry: dict[str, Any] = {
            "id": bead.id,
            "title": bead.title,
            "judge": bead.id in wanted,
            "reason": wanted.get(bead.id),
        }
        if level == "epic":
            entry["prdPath"] = paths.get(bead.id)
            has_tasks = bool(_tasks_of(graph, bead))
            entry["hasTasks"] = has_tasks
            entry["current"] = (
                None
                if entry["judge"]
                else {
                    "userBusinessValue": _int(bead.metadata.get("wsjf_ubv")),
                    "timeCriticality": _int(bead.metadata.get("wsjf_tc")),
                    "confidence": _int(bead.metadata.get("wsjf_confidence")),
                    **({} if has_tasks else _size_of(bead)),
                }
            )
        else:
            entry["description"] = bead.description
            epic = graph.epic_of(bead.id)
            entry["epic"] = {"id": epic.id, "title": epic.title} if epic else None
            entry["current"] = None if entry["judge"] else _size_of(bead)
        items.append(entry)
    jobs = reference_jobs(graph)
    return {
        "level": level,
        "items": items,
        "referenceJobs": jobs,
        "summary": {
            "items": len(items),
            "toJudge": len(wanted),
            "referenceJobs": len(jobs),
        },
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


def _percent(record: dict, key: str, bead_id: str) -> int:
    """Read one judged confidence as an integer percent from 1 to 100.

    Args:
        record: The judgment for one item.
        key: The field.
        bead_id: The item, for the error message.

    Returns:
        The value.

    Raises:
        ScoringError: The value is missing or outside 1-100.
    """
    value = _positive(record, key, bead_id)
    if value > 100:
        msg = f"{bead_id}: `{key}` is a percent, got {record.get(key)!r}"
        raise ScoringError(msg)
    return value


def _size_pairs(one: dict, bead_id: str) -> dict[str, str]:
    """The judged size estimate, its plausible range and its confidence, validated.

    Args:
        one: The judgment for one item.
        bead_id: The item, for the error message.

    Returns:
        The size keys and their values.

    Raises:
        ScoringError: A value is missing, not a positive integer, or the range does not
            contain the estimate.
    """
    size = _positive(one, "jobSize", bead_id)
    low = _positive(one, "sizeLow", bead_id)
    high = _positive(one, "sizeHigh", bead_id)
    if not low <= size <= high:
        msg = f"{bead_id}: the range {low}-{high} does not contain the estimate {size}"
        raise ScoringError(msg)
    return {
        ESTIMATE_KEY: str(size),
        "wsjf_size_low": str(low),
        "wsjf_size_high": str(high),
        "wsjf_size_confidence": str(_percent(one, "sizeConfidence", bead_id)),
    }


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
        pairs["wsjf_confidence"] = str(_percent(one, "confidence", bead.id))
        if not _tasks_of(graph, bead):
            pairs |= _size_pairs(one, bead.id)
    else:
        pairs |= _size_pairs(one, bead.id)
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
    """The dependency edges among a set of beads, as the rubric takes them.

    Each bead's edges are read from the type its level is stored as: `tracks` between
    Epics, `blocks` between Tasks.

    Args:
        beads: The beads whose mutual edges are wanted.

    Returns:
        `from` must come before `to`.
    """
    ids = {b.id for b in beads}
    return [
        {"from": upstream, "to": b.id}
        for b in beads
        for upstream in b.depends_on
        if upstream in ids
    ]


def _scoring_size(bead: Bead, *, has_tasks: bool) -> dict[str, int]:
    """The judged size inputs a bead hands the rubric.

    The estimate is `wsjf_size_estimate`. A bead with no stored estimate and no Tasks is
    sized by the `wsjf_size` it carries.

    Args:
        bead: The bead.
        has_tasks: Whether it has Tasks, whose sizes then make its size.

    Returns:
        `jobSize`, `sizeLow`, `sizeHigh` and `sizeConfidence`, each only when present.
    """
    size = _size_of(bead)
    if size["jobSize"] is None and not has_tasks:
        size["jobSize"] = _int(bead.metadata.get("wsjf_size"))
    return {key: value for key, value in size.items() if value is not None}


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
        tasks = _tasks_of(graph, epic)
        item: dict[str, Any] = {
            "id": epic.id,
            "userBusinessValue": _int(epic.metadata.get("wsjf_ubv")),
            "timeCriticality": _int(epic.metadata.get("wsjf_tc")),
            "confidence": _int(epic.metadata.get("wsjf_confidence")),
            **_scoring_size(epic, has_tasks=bool(tasks)),
        }
        sizes = [_int(t.metadata.get("wsjf_size")) for t in tasks]
        if tasks and all(s is not None for s in sizes):
            item["childSizes"] = sizes
        else:
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
                **_scoring_size(task, has_tasks=False),
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
        computed = {
            key: value
            for key, value in scored["metadata"].items()
            if key not in SIZE_JUDGED_KEYS
        }
        rows.append(
            {
                "id": bead.id,
                "wsjf": scored["wsjf"],
                "costOfDelay": scored["costOfDelay"],
                "rroe": scored["riskReductionOpportunityEnablement"],
                "reaches": scored["reaches"],
                "jobSize": scored["jobSize"],
                "sizeSource": scored["sizeSource"],
                "sizeOutsideRange": scored.get("sizeOutsideRange"),
                "written": _write(bead, computed, writer),
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
        faults, the Epics whose refined size falls outside their estimate's range, any
        cycle, a summary, and — in a dry run — every write in order.
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
        "outsideRange": epic_result["outsideRange"],
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
            "outsideRange": len(epic_result["outsideRange"]),
            "epicCycle": epic_result["cycle"],
            "taskCycle": task_result["cycle"],
        },
    }
