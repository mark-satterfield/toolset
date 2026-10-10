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

import math
from pathlib import Path
from typing import TypedDict

import beadgraph
import scoringcontracts
import wsjf as rubric
import wsjf_types  # ruff: ignore[typing-only-third-party-import] - Typeguard checks local declarations at runtime.
from beadgraph import SCOPE_JUDGING, Bead, Graph, Writer, fingerprints
from contracts import JsonObject, JsonValue
from prds import write_prds
from scoringcontracts import (
    Applied,
    Group,
    JudgeEntry,
    JudgeInput,
    JudgeItem,
    JudgeSummary,
    LevelUnscored,
    Plan,
    PlanSummary,
    Recorded,
    ReferenceJob,
    ScoreResult,
)
from typeguard import CollectionCheckStrategy, typechecked
from wsjf_types import Item, Unscored  # ruff: ignore[typing-only-third-party-import] - Runtime imports preserve typeguard local-assignment validation.
from wsjf_types import ScoreResult as RubricResult  # ruff: ignore[typing-only-third-party-import] - Runtime import preserves typeguard local-assignment validation.

#: The metadata key holding the fingerprint of the content a judged value was judged from.
_ARGUMENT_ERROR: str = "Arguments violate the scoring input contract"


JUDGED_HASH_KEY = "wsjf_content_hash"

#: Metadata that changes on every write and so never, by itself, justifies one.
VOLATILE_KEYS = frozenset({"wsjf_calculated_at"})

#: The top rung of User-Business Value and Time Criticality in the `wsjf` rubric.
VALUE_TOP = 20

#: The judged size keys. `record` writes them; `score` reads them and never writes them.
ESTIMATE_KEY = "wsjf_size_estimate"
SIZE_JUDGED_KEYS = (
    ESTIMATE_KEY,
    "wsjf_size_low",
    "wsjf_size_high",
    "wsjf_size_confidence",
)


#: The Epic lifecycle key `prd-to-spec` writes, and the state at which elaboration is done.
ELABORATION_KEY = "elaboration_state"
ELABORATION_DONE = "done"


class SizeInputs(TypedDict, total=False):
    """Describe the size inputs wire record."""

    jobSize: int
    sizeLow: int
    sizeHigh: int
    sizeConfidence: int


class ScoringError(RuntimeError):
    """A judgment file the recorder cannot work from."""


def _int(value: JsonValue) -> int | None:
    """Parse a metadata integer, returning None when it is absent or unusable.

    Args:
        value: The raw metadata value.

    Returns:
        The integer, or None when there is not one.

    """
    try:
        return int(float(str(value).strip()))
    except TypeError, ValueError:
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
        return math.isclose(float(stored), float(fresh), rel_tol=0.0, abs_tol=0.0)
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
    changed: bool = any(not _same(bead.metadata.get(k), v) for k, v in pairs.items() if k not in VOLATILE_KEYS)
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


def _sized_from_tasks(
    graph: Graph,
    epic: Bead,
    rollup: frozenset[str] | set[str] = frozenset(),
) -> bool:
    """Whether an Epic's job size is the sum of its Tasks' sizes.

    Only an Epic whose elaboration is done rolls up. Until then its Tasks are being
    written one by one, so their sum is a partial count of the work, not its size; the
    Epic is sized by its judged estimate.

    Args:
        graph: The tracker graph.
        epic: The Epic.
        rollup: Epics to treat as done in this run: `elaboration-finish` scores the Epic
            before it writes `elaboration_state=done`.

    Returns:
        True when the Epic has Tasks and its elaboration is done.

    """
    done: bool = epic.metadata.get(ELABORATION_KEY) == ELABORATION_DONE or epic.id in rollup
    return done and bool(_tasks_of(graph, epic))


# ------------------------------------------------------------------------------------
# What needs judging
# ------------------------------------------------------------------------------------


def _judged_state(bead: Bead, required: tuple[str, ...], current: str) -> str:
    """Return the state of a bead's judged inputs.

    Args:
        bead: The bead.
        required: The judged metadata keys it must carry.
        current: Its content fingerprint now.

    Returns:
        `missing` when a judged value is absent, `changed` when the fingerprint recorded
        with the values no longer matches the bead, `unfingerprinted` when values are
        present with no fingerprint beside them, and `current` otherwise.

    """
    if any(bead.metadata.get(k) in {None, ""} for k in required):
        return "missing"
    stored: str | None = bead.metadata.get(JUDGED_HASH_KEY)
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
    """Return what this run does with an item's judged inputs.

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
    if state in {"missing", "changed"}:
        return "judge"
    if not include_all:
        return "keep"
    if rejudge:
        return "judge"
    return "adopt" if state == "unfingerprinted" else "keep"


def _required_judgments(graph: Graph, bead: Bead, level: str) -> tuple[str, ...]:
    if level != "epics":
        return SIZE_JUDGED_KEYS
    required: tuple[str, ...] = ("wsjf_ubv", "wsjf_tc", "wsjf_confidence")
    return required if _sized_from_tasks(graph, bead) else required + SIZE_JUDGED_KEYS


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def plan(
    graph: Graph,
    *,
    include_all: bool,
    rejudge: bool,
    only: list[str] | None = None,
) -> Plan:
    """Decide which judged inputs this run judges, and which stored ones it adopts.

    Args:
        graph: The tracker graph, read with descriptions.
        include_all: Include items that already have a value.
        rejudge: Judge again the existing values of the items included.
        only: Restrict what is judged and adopted to these open Epics and Tasks, or None
            for every one. The fingerprints still cover every open item, and the
            arithmetic is unaffected.

    Returns:
        The Epics and Tasks to judge with a reason each, the judged values to adopt,
        every open Epic's and Task's fingerprint, and a summary of counts. An id in
        `only` that is not an open Epic or Task is ignored.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    level: str
    beads: list[Bead]
    bead: Bead
    if (
        not (isinstance(graph, Graph))
        or not (isinstance(include_all, bool))
        or not (isinstance(rejudge, bool))
        or not (isinstance(only, list) or only is None)
    ):
        raise TypeError(_ARGUMENT_ERROR)
    prints: dict[str, str] = fingerprints(graph.records, SCOPE_JUDGING)
    epics: list[beadgraph.Bead] = _open(graph, "epic")
    tasks: list[beadgraph.Bead] = _open(graph, "task")
    ids: set[str] = {e.id for e in epics} | {t.id for t in tasks}
    wanted: set[str] | None = None if only is None else set(only) & ids
    adopt: list[str] = []
    states: dict[str, int] = {}
    judge: dict[str, list[JudgeEntry]] = {"epics": [], "tasks": []}
    for level, beads in (("epics", epics), ("tasks", tasks)):
        for bead in beads:
            if wanted is not None and bead.id not in wanted:
                continue
            required: tuple[str, ...] = _required_judgments(graph, bead, level)
            state: str = _judged_state(bead, required, prints.get(bead.id, ""))
            states[state] = states.get(state, 0) + 1
            action: str = _disposition(state, include_all=include_all, rejudge=rejudge)
            if action == "adopt":
                adopt.append(bead.id)
            elif action == "judge":
                entry: JudgeEntry = {"id": bead.id, "reason": JUDGE_REASONS[state]}
                if level == "tasks":
                    epic: beadgraph.Bead | None = graph.epic_of(bead.id)
                    entry["epic"] = epic.id if epic else None
                judge[level].append(entry)
    summary: PlanSummary = {
        "includeAll": include_all,
        "rejudge": rejudge,
        "openEpics": len(epics),
        "openTasks": len(tasks),
        "states": states,
        "epicsToJudge": len(judge["epics"]),
        "tasksToJudge": len(judge["tasks"]),
        "toAdopt": len(adopt),
    }
    if wanted is not None:
        summary["only"] = sorted(wanted)
    return {
        "judge": judge,
        "adopt": adopt,
        "fingerprints": {i: prints[i] for i in sorted(ids) if i in prints},
        "summary": summary,
    }


def _size(value: JsonValue) -> int | None:
    """Parse a stored size, returning None when it is absent, unusable or not positive.

    The rubric refuses a non-positive size by raising, which would abort the arithmetic
    for the whole portfolio over one bead's metadata. Read as absent, it leaves that one
    item unscored or its Epic incomplete, named in the report.

    Args:
        value: The raw metadata value.

    Returns:
        The positive integer, or None.

    """
    parsed: int | None = _int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _size_of(bead: Bead) -> dict[str, int | None]:
    """Return a bead's judged size estimate with its range and confidence.

    Args:
        bead: The bead.

    Returns:
        `jobSize`, `sizeLow`, `sizeHigh` and `sizeConfidence`, None where absent.

    """
    return {
        "jobSize": _size(bead.metadata.get(ESTIMATE_KEY)),
        "sizeLow": _size(bead.metadata.get("wsjf_size_low")),
        "sizeHigh": _size(bead.metadata.get("wsjf_size_high")),
        "sizeConfidence": _int(bead.metadata.get("wsjf_size_confidence")),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def reference_jobs(graph: Graph) -> list[ReferenceJob]:
    """Return the elaborated Epics: each one's original estimate beside its refined size.

    An Epic is a reference job once its elaboration is done and every one of its Tasks is
    sized. Its
    refined size is the sum of those sizes, so each reference job shows how an estimate
    made before the work was known compared with the work as decomposed.

    Args:
        graph: The tracker graph.

    Returns:
        One record per reference job, in id order.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    epic: Bead
    if not (isinstance(graph, Graph)):
        raise TypeError(_ARGUMENT_ERROR)
    jobs: list[ReferenceJob] = []
    for epic in graph.of_kind("epic"):
        if not _sized_from_tasks(graph, epic):
            continue
        tasks: list[beadgraph.Bead] = _tasks_of(graph, epic)
        sizes: list[int | None] = [_size(t.metadata.get("wsjf_size")) for t in tasks]
        if any(size is None for size in sizes):
            continue
        estimate: dict[str, int | None] = _size_of(epic)
        jobs.append(
            {
                "id": epic.id,
                "title": epic.title,
                "estimate": estimate["jobSize"],
                "low": estimate["sizeLow"],
                "high": estimate["sizeHigh"],
                "refinedSize": sum(s for s in sizes if s is not None),
                "tasks": len(tasks),
            },
        )
    return jobs


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def judge_input(
    graph: Graph,
    the_plan: Plan,
    level: str,
    prd_dir: Path | None = None,
) -> JudgeInput:
    """Return the material the judging sessions at one level read: the items to judge, and no other.

    Each Epic is judged in a session of its own, from its own full PRD, against the
    rubric's rungs and the reference jobs; each Epic's Tasks are sized together in a
    session per Epic, and every Task with no Epic in a session of its own. No item carries
    another item's judged values, and no Epic carries another Epic's PRD, so adding an item
    never moves another item's judgment. The reference jobs — elaborated Epics with their
    original estimate and refined size — are the size comparison at both levels. No
    computed value is included: RR-OE, reachability and WSJF are arithmetic over the graph
    and are not a session's to see or set.

    Args:
        graph: The tracker graph, read with descriptions.
        the_plan: The run's plan, from `plan`.
        level: `epic` or `task`.
        prd_dir: Where to write the PRD of each Epic to judge, or None.

    Returns:
        The items to judge, each with its reason; the reference jobs; and a summary naming
        the sessions: `ids`, one Epic per session, or `groups`, a session each, every
        group `{key, epic, tasks}` — an Epic's Tasks keyed by the Epic, or one Task with no
        Epic keyed by itself with `epic` null.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    bead: Bead
    if (
        not (isinstance(graph, Graph))
        or not (isinstance(the_plan, dict))
        or not (isinstance(level, str))
        or not (isinstance(prd_dir, Path) or prd_dir is None)
    ):
        raise TypeError(_ARGUMENT_ERROR)
    wanted: dict[str, str] = {j["id"]: j["reason"] for j in the_plan["judge"][f"{level}s"]}
    beads: list[beadgraph.Bead] = [b for b in _open(graph, level) if b.id in wanted]
    paths: dict[str, str] = write_prds(beads, prd_dir) if level == "epic" and prd_dir else {}
    items: list[JudgeItem] = []
    groups: dict[str, Group] = {}
    for bead in beads:
        entry: JudgeItem = {
            "id": bead.id,
            "title": bead.title,
            "reason": wanted[bead.id],
        }
        if level == "epic":
            entry["prdPath"] = paths.get(bead.id)
            entry["sizedFromTasks"] = _sized_from_tasks(graph, bead)
        else:
            entry["description"] = bead.description
            epic: beadgraph.Bead | None = graph.epic_of(bead.id)
            entry["epic"] = {"id": epic.id, "title": epic.title} if epic else None
            key: str = epic.id if epic else bead.id
            group: scoringcontracts.Group = groups.setdefault(
                key,
                {"key": key, "epic": epic.id if epic else None, "tasks": []},
            )
            group["tasks"].append(bead.id)
        items.append(entry)
    jobs: list[scoringcontracts.ReferenceJob] = reference_jobs(graph)
    summary: JudgeSummary = {
        "items": len(items),
        "toJudge": len(items),
        "referenceJobs": len(jobs),
    }
    if level == "epic":
        summary["ids"] = [item["id"] for item in items]
    else:
        summary["groups"] = list(groups.values())
    return {
        "level": level,
        "items": items,
        "referenceJobs": jobs,
        "summary": summary,
    }


# ------------------------------------------------------------------------------------
# Recording judgments
# ------------------------------------------------------------------------------------


def _positive(record: JsonObject, key: str, bead_id: str) -> int:
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
    value: int | None = _int(record.get(key))
    if value is None or value <= 0:
        msg: str = f"{bead_id}: `{key}` must be a positive integer, got {record.get(key)!r}"
        raise ScoringError(msg)
    return value


def _percent(record: JsonObject, key: str, bead_id: str) -> int:
    """Read one judged confidence as an integer percent, a value above 100 taken as 100.

    Args:
        record: The judgment for one item.
        key: The field.
        bead_id: The item, for the error message.

    Returns:
        The value.

    """
    return min(_positive(record, key, bead_id), 100)


def _size_pairs(one: JsonObject, bead_id: str) -> dict[str, str]:
    """Return the judged size estimate, its plausible range and its confidence, validated.

    Args:
        one: The judgment for one item.
        bead_id: The item, for the error message.

    Returns:
        The size keys and their values.

    """
    size: int = _positive(one, "jobSize", bead_id)
    low: int = min(_positive(one, "sizeLow", bead_id), size)
    high: int = max(_positive(one, "sizeHigh", bead_id), size)
    return {
        ESTIMATE_KEY: str(size),
        "wsjf_size_low": str(low),
        "wsjf_size_high": str(high),
        "wsjf_size_confidence": str(_percent(one, "sizeConfidence", bead_id)),
    }


def _value(record: JsonObject, key: str, bead_id: str) -> int:
    """Read one judged UBV or TC as an integer on the rubric's scale.

    Args:
        record: The judgment for one item.
        key: The field.
        bead_id: The item, for the error message.

    Returns:
        The value.

    """
    return min(_positive(record, key, bead_id), VALUE_TOP)


def _judged_pairs(graph: Graph, level: str, bead: Bead, one: JsonObject) -> dict[str, str]:
    """Return the metadata one judgment writes, with every judged value validated.

    Args:
        graph: The tracker graph.
        level: `epic` or `task`.
        bead: The judged bead.
        one: The judgment for it.

    Returns:
        The judged keys and their values, without the fingerprint.

    """
    pairs: dict[str, str] = {}
    if level == "epic":
        pairs["wsjf_ubv"] = str(_value(one, "userBusinessValue", bead.id))
        pairs["wsjf_tc"] = str(_value(one, "timeCriticality", bead.id))
        pairs["wsjf_confidence"] = str(_percent(one, "confidence", bead.id))
        if not _sized_from_tasks(graph, bead):
            pairs |= _size_pairs(one, bead.id)
    else:
        pairs |= _size_pairs(one, bead.id)
    return pairs


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record(
    graph: Graph,
    the_plan: Plan,
    judgments: dict[str, list[JsonObject]],
    writer: Writer,
) -> Recorded:
    """Write judged values, each with the fingerprint of the content it was judged from.

    The plan's adopted values get their fingerprint recorded beside them. Only items the
    plan named for judging are written. A judgment for an item the plan did not name is
    not written and is listed under `rejected`; an item judged twice takes its last
    judgment. Every judgment is validated
    before anything is written; one with a value off the rubric's scale is not written and
    is listed under `rejected` with its reason, and the others are written. One session's
    defect never costs another session's judgments.

    Args:
        graph: The tracker graph.
        the_plan: The run's plan, from `plan`.
        judgments: `epic` and `task` lists of the rubric's per-item scores.
        writer: The tracker writer; a dry-run writer records the writes instead.

    Returns:
        What was written, what was rejected and why, what the plan asked for and did not
        receive, a summary, and — in a dry run — every write in order.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    level: str | str
    one: JsonObject
    bead_id: str
    if (
        not (isinstance(graph, Graph))
        or not (isinstance(the_plan, dict))
        or not (isinstance(judgments, dict))
        or not (isinstance(writer, Writer))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    prints: dict[str, str] = the_plan["fingerprints"]
    missing: list[str] = []
    rejected: list[dict[str, str]] = []
    pending: list[tuple[Bead, dict[str, str]]] = []
    for level in ("epic", "task"):
        asked: set[str] = {j["id"] for j in the_plan["judge"][f"{level}s"]}
        got: dict[str, JsonObject] = {}
        for one in judgments.get(level, []):
            got[str(one.get("id"))] = one
        for bead_id in sorted(set(got) - asked):
            del got[bead_id]
            rejected.append(
                {
                    "id": bead_id,
                    "level": level,
                    "reason": "the plan did not name it for judging",
                },
            )
        missing += sorted(asked - set(got))
        for bead_id in sorted(asked & set(got)):
            bead: beadgraph.Bead | None = graph.beads.get(bead_id)
            if bead is None:
                missing.append(bead_id)
                continue
            try:
                judged: dict[str, str] = _judged_pairs(graph, level, bead, got[bead_id])
            except ScoringError as exc:
                rejected.append({"id": bead_id, "level": level, "reason": str(exc)})
                continue
            # An ABSENT fingerprint is not written as "". Writing one clobbers whatever
            # fingerprint the bead already carried with a value `_judged_state` reads as
            # `unfingerprinted` rather than `changed`, so the item is never re-judged
            # again without `--all --rejudge` — staleness masked permanently. The adopt
            # path below already skips on a falsy fingerprint; so does this one.
            stamp: str | None = prints.get(bead_id)
            pending.append(
                (bead, {JUDGED_HASH_KEY: stamp} | judged if stamp else judged),
            )
    written: list[str] = [bead.id for bead, pairs in pending if _write(bead, pairs, writer)]
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
        "rejected": rejected,
        "missing": missing,
        "planned": writer.planned,
        "summary": {
            "dryRun": writer.dry_run,
            "written": len(written),
            "adopted": len(adopted),
            "rejected": len(rejected),
            "missing": len(missing),
        },
    }


# ------------------------------------------------------------------------------------
# The arithmetic
# ------------------------------------------------------------------------------------


def _edges(beads: list[Bead]) -> list[dict[str, str]]:
    """Return the dependency edges among a set of beads, as the rubric takes them.

    Each bead's edges are read from the type its level is stored as: `tracks` between
    Epics, `blocks` between Tasks.

    Args:
        beads: The beads whose mutual edges are wanted.

    Returns:
        `from` must come before `to`.

    """
    ids: set[str] = {b.id for b in beads}
    return [{"from": upstream, "to": b.id} for b in beads for upstream in b.depends_on if upstream in ids]


def _scoring_size(bead: Bead, *, rolls_up: bool) -> SizeInputs:
    """Return the judged size inputs a bead hands the rubric.

    The estimate is `wsjf_size_estimate`. A bead with no stored estimate whose size does
    not roll up from Tasks is sized by the `wsjf_size` it carries.

    Args:
        bead: The bead.
        rolls_up: Whether its Tasks' sizes make its size.

    Returns:
        `jobSize`, `sizeLow`, `sizeHigh` and `sizeConfidence`, each only when present.

    """
    size: dict[str, int | None] = _size_of(bead)
    if size["jobSize"] is None and not rolls_up:
        size["jobSize"] = _size(bead.metadata.get("wsjf_size"))
    result: SizeInputs = {}
    for_key: int | None = size.get("jobSize")
    if for_key is not None:
        result["jobSize"] = for_key
    for_key = size.get("sizeLow")
    if for_key is not None:
        result["sizeLow"] = for_key
    for_key = size.get("sizeHigh")
    if for_key is not None:
        result["sizeHigh"] = for_key
    for_key = size.get("sizeConfidence")
    if for_key is not None:
        result["sizeConfidence"] = for_key
    return result


def _task_size(task: Bead) -> int | None:
    """Return the size a Task scores at in THIS run, not the one it was written with last run.

    `wsjf_size` is written by `_apply`, at the END of a run, so on the run that first
    judges a decomposed Epic's Tasks it is absent or holds the previous run's number. An
    Epic rolled up from it is therefore one run stale — and on first elaboration it falls
    back to the Epic's pre-decomposition estimate — while reporting nothing. So the Task's
    own judged estimate is preferred and snapped the same way `_resolve_size` snaps it for
    the Task itself, which is exactly the size this run will write.

    Args:
        task: The Task.

    Returns:
        The size, or None when the Task carries neither a judged estimate nor a size.

    """
    estimate: int | None = _size(task.metadata.get(ESTIMATE_KEY))
    if estimate is not None:
        return rubric.snap_size(estimate)
    return _size(task.metadata.get("wsjf_size"))


def _epic_items(
    graph: Graph,
    epics: list[Bead],
    rollup: frozenset[str] | set[str] = frozenset(),
) -> tuple[list[Item], list[Unscored]]:
    """Return the rubric input for every open Epic, and what is missing from it.

    Only an Epic whose elaboration is done hands the rubric its Tasks' sizes to sum; every
    other Epic is sized by its judged estimate.

    Args:
        graph: The tracker graph.
        epics: The open Epics.
        rollup: Epics to treat as done in this run.

    Returns:
        The items, and the incomplete records.

    """
    epic: Bead
    items: list[Item] = []
    incomplete: list[Unscored] = []
    for epic in epics:
        rolls_up: bool = _sized_from_tasks(graph, epic, rollup)
        tasks: list[beadgraph.Bead] = _tasks_of(graph, epic) if rolls_up else []
        item: Item = {
            "id": epic.id,
            "userBusinessValue": _int(epic.metadata.get("wsjf_ubv")),
            "timeCriticality": _int(epic.metadata.get("wsjf_tc")),
            "confidence": _int(epic.metadata.get("wsjf_confidence")),
        }
        size_inputs: SizeInputs = _scoring_size(epic, rolls_up=rolls_up)
        if "jobSize" in size_inputs:
            item["jobSize"] = size_inputs["jobSize"]
        if "sizeLow" in size_inputs:
            item["sizeLow"] = size_inputs["sizeLow"]
        if "sizeHigh" in size_inputs:
            item["sizeHigh"] = size_inputs["sizeHigh"]
        if "sizeConfidence" in size_inputs:
            item["sizeConfidence"] = size_inputs["sizeConfidence"]
        sizes: list[int | None] = [_task_size(t) for t in tasks]
        if tasks and all(s is not None for s in sizes):
            item["childSizes"] = list(sizes)
        else:
            unsized: list[str] = [t.id for t, s in zip(tasks, sizes, strict=True) if s is None]
            if unsized:
                incomplete.append(
                    {
                        "id": epic.id,
                        "reason": "Tasks carry neither a judged size estimate nor a "
                        "wsjf_size, so no roll-up: " + ", ".join(unsized),
                    },
                )
        items.append(item)
    return items, incomplete


def _task_items(graph: Graph, tasks: list[Bead]) -> list[Item]:
    """Return the rubric input for every open Task, with value inherited from its Epic.

    Args:
        graph: The tracker graph.
        tasks: The open Tasks.

    Returns:
        The items. A Task with no Epic, or under an unjudged one, carries no value and
        comes back unscored from the rubric.

    """
    task: Bead
    items: list[Item] = []
    for task in tasks:
        epic: beadgraph.Bead | None = graph.epic_of(task.id)
        meta: dict[str, str] = epic.metadata if epic else {}
        item: Item = {
            "id": task.id,
            "userBusinessValue": _int(meta.get("wsjf_ubv")),
            "timeCriticality": _int(meta.get("wsjf_tc")),
            "confidence": _int(meta.get("wsjf_confidence")),
            "valueFrom": epic.id if epic else None,
        }
        size_inputs: SizeInputs = _scoring_size(task, rolls_up=False)
        if "jobSize" in size_inputs:
            item["jobSize"] = size_inputs["jobSize"]
        if "sizeLow" in size_inputs:
            item["sizeLow"] = size_inputs["sizeLow"]
        if "sizeHigh" in size_inputs:
            item["sizeHigh"] = size_inputs["sizeHigh"]
        if "sizeConfidence" in size_inputs:
            item["sizeConfidence"] = size_inputs["sizeConfidence"]
        items.append(item)
    return items


def _apply(
    graph: Graph,
    result: RubricResult,
    writer: Writer,
    scope: set[str] | None,
) -> list[Applied]:
    """Write every scored item in scope whose values changed.

    Args:
        graph: The tracker graph.
        result: The rubric's `score` output.
        writer: The tracker writer; a dry-run writer records the writes instead.
        scope: The ids that may be written, or None for every scored item.

    Returns:
        One record per scored item in scope, marked with whether it is written.

    """
    scored: wsjf_types.ScoreRow
    rows: list[Applied] = []
    for scored in result["scores"]:
        if scope is not None and scored["id"] not in scope:
            continue
        bead: beadgraph.Bead = graph.beads[scored["id"]]
        computed: dict[str, str] = {
            key: value for key, value in scored["metadata"].items() if key not in SIZE_JUDGED_KEYS
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
            },
        )
    return rows


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def score(
    graph: Graph,
    writer: Writer,
    scope: set[str] | None = None,
    rollup: frozenset[str] | set[str] = frozenset(),
) -> ScoreResult:
    """Recompute every open Epic's and every open Task's WSJF, and write what changed.

    The edge lists handed to the rubric are the whole graph at each level, so a level
    with no edges scores every item as reaching nothing. The computation always covers the
    whole tracker, because RR-OE is reachability over the whole graph; `scope` limits only
    what is written and reported.

    Args:
        graph: The tracker graph.
        writer: The tracker writer; a dry-run writer records the writes instead.
        scope: The ids that may be written, or None for every open Epic and Task.
        rollup: Epics whose size rolls up from their Tasks although their
            `elaboration_state` is not yet `done`: the Epic `elaboration-finish` is about
            to mark done.

    Returns:
        The Epic and Task scores, everything that could not be scored and why, size
        faults, the Epics whose refined size falls outside their estimate's range, any
        cycle, a summary, and — in a dry run — every write in order.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    epic_items: list[Item]
    incomplete: list[Unscored]
    level: str
    outcome: RubricResult
    if (
        not (isinstance(graph, Graph))
        or not (isinstance(writer, Writer))
        or not (isinstance(scope, set) or scope is None)
    ):
        raise TypeError(_ARGUMENT_ERROR)
    epics: list[beadgraph.Bead] = _open(graph, "epic")
    tasks: list[beadgraph.Bead] = _open(graph, "task")
    epic_items, incomplete = _epic_items(graph, epics, rollup)
    epic_result: RubricResult = rubric.score({"edges": _edges(epics), "items": epic_items}, "epic")
    task_result: RubricResult = rubric.score(
        {"edges": _edges(tasks), "items": _task_items(graph, tasks)},
        "task",
    )
    epic_rows: list[scoringcontracts.Applied] = _apply(graph, epic_result, writer, scope)
    task_rows: list[scoringcontracts.Applied] = _apply(graph, task_result, writer, scope)

    def wanted(entry: Unscored) -> bool:
        return scope is None or entry["id"] in scope

    unscored: list[LevelUnscored] = []
    for level, outcome in (("epic", epic_result), ("task", task_result)):
        unscored.extend(
            LevelUnscored(level=level, id=entry["id"], reason=entry["reason"])
            for entry in outcome["unscored"]
            if wanted(entry)
        )
    incomplete = [i for i in incomplete if wanted(i)]
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
