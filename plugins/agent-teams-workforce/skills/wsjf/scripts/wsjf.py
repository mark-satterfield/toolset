#!/usr/bin/env python3
"""wsjf.py — the WSJF arithmetic, over whatever the caller already knows.

This module owns the computed tables and rules: the RR-OE reachability bands, the
Fibonacci job-size scale with the Task ceiling, and the Epic roll-up, which is the plain
sum of its Tasks' sizes. Two levels parameterise them, `epic` and `task`.

It takes inputs and returns results. It reads no tracker, no repository and no file other
than the one named on the command line, and it writes nothing anywhere — the `metadata`
object on each score is what a caller may choose to store, not something stored here.

Usage:
  wsjf.py score  --level epic|task [--input FILE]
  wsjf.py reach  --level epic|task [--input FILE]
  wsjf.py scales --level epic|task
  wsjf.py selftest

`--input` names a JSON file, and defaults to stdin.

Input for `score` and `reach`:

  {
    "level": "epic",                         // optional; --level wins
    "edges": [{"from": "A", "to": "B"}],     // optional: A must come before B; an
                                             // empty list is a graph with no edges
    "items": [
      {
        "id": "A",
        "userBusinessValue": 13,             // judged, or inherited at task level
        "timeCriticality": 3,                // judged, or inherited at task level
        "valueFrom": "E1",                   // optional: where the two above came from
        "riskReductionOpportunityEnablement": 8,  // optional: skips the graph entirely
        "reaches": 12,                       // optional: skips the reachability walk
        "jobSize": 8,                        // the judged size estimate
        "sizeLow": 5,                        // optional: the estimate's plausible range
        "sizeHigh": 13,
        "sizeConfidence": 70,                // optional, integer percent, of the estimate
        "childSizes": [3, 5, 2],             // optional, Epic only: the size becomes
                                             // their sum; jobSize stays the estimate
        "confidence": 88                     // optional, integer percent: the value
                                             // confidence, judged or inherited
      }
    ]
  }

Anything an item already carries is used as given. Anything it omits is computed when the
inputs for computing it are present, and is reported as missing when they are not.

Output for `score`:

  {
    "ok": true,
    "level": "epic",
    "scores": [ { ...dimensions, "wsjf": 3.63, "metadata": {...} } ],
    "unscored": [ { "id": "C", "reason": "..." } ],
    "sizeFaults": [ { "id": "D", "supplied": 21, "rung": 13 } ],
    "outsideRange": [ { "id": "E", "size": 47, "low": 21, "high": 34 } ],
    "cycle": null
  }
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Any

#: Per-level parameters. Everything that differs between an Epic and a Task lives here.
#: Both levels size on the one Fibonacci scale; a Task above `sizeCeiling` should have
#: been split, and an Epic has no ceiling.
LEVELS: dict[str, dict[str, Any]] = {
    "epic": {
        "rubric": "epic-wsjf",
        # Reachability ceiling -> RR-OE rung, ascending; anything above takes rroeTop.
        "rroeBands": ((0, 1), (1, 3), (3, 5), (9, 8), (19, 13)),
        "rroeTop": 20,
        "sizeCeiling": None,
        "rollup": True,
        "reachKey": "wsjf_reaches",
    },
    "task": {
        "rubric": "task-wsjf",
        "rroeBands": ((0, 1), (1, 3), (3, 5), (6, 8), (9, 13)),
        "rroeTop": 20,
        "sizeCeiling": 13,
        "rollup": False,
        "reachKey": "wsjf_unblocks",
    },
}

#: The rungs `scales` lists. The scale itself continues upward without end.
LISTED_RUNGS = 11


class WsjfError(Exception):
    """An input this module cannot work from."""


def now_iso() -> str:
    """The current time as an ISO 8601 timestamp in UTC.

    Returns:
        The timestamp, to whole seconds, with a trailing `Z`.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def band(count: int, bands: tuple[tuple[int, int], ...], top: int) -> int:
    """Place a count on a band table, falling through to the top rung.

    Args:
        count: The count to place.
        bands: Ceiling/rung pairs in ascending ceiling order.
        top: The rung for anything above the last ceiling.

    Returns:
        The rung the count lands on.
    """
    for ceiling, rung in bands:
        if count <= ceiling:
            return rung
    return top


def fibonacci(count: int) -> list[int]:
    """The first rungs of the size scale.

    Args:
        count: How many rungs.

    Returns:
        1, 2, 3, 5, 8, ... — `count` of them.
    """
    rungs = [1, 2]
    while len(rungs) < count:
        rungs.append(rungs[-1] + rungs[-2])
    return rungs[:count]


def snap_size(value: float, ceiling: int | None) -> tuple[int, bool]:
    """Put a judged size on the Fibonacci scale: the smallest rung at or above it.

    Args:
        value: The size the caller judged.
        ceiling: The level's largest allowed rung, or None when the scale is unbounded.

    Returns:
        The rung, and whether the value sat above the ceiling.

    Raises:
        WsjfError: The value is not a positive number.
    """
    if value <= 0:
        msg = f"jobSize must be greater than 0, got {value}"
        raise WsjfError(msg)
    if ceiling is not None and value > ceiling:
        return ceiling, True
    low, high = 1, 2
    if value <= low:
        return low, False
    while high < value:
        low, high = high, low + high
    return high, False


def build_successors(edges: list[dict[str, str]], ids: set[str]) -> dict[str, set[str]]:
    """Index the edges forward, restricted to the items in scope.

    Args:
        edges: Objects carrying `from` and `to`, meaning from must come before to.
        ids: The item ids being scored.

    Returns:
        Blocker id -> the ids it blocks.
    """
    successors: dict[str, set[str]] = {}
    for edge in edges:
        source, target = edge.get("from"), edge.get("to")
        if source in ids and target in ids and source != target:
            successors.setdefault(str(source), set()).add(str(target))
    return successors


def find_cycle(successors: dict[str, set[str]], ids: set[str]) -> list[str] | None:
    """Find one cycle in the edge graph, if there is one.

    Args:
        successors: Blocker id -> the ids it blocks.
        ids: Every id in scope.

    Returns:
        The cycle as a list of ids, or None when the graph is acyclic.
    """
    state: dict[str, int] = {}
    path: list[str] = []

    def walk(node: str) -> list[str] | None:
        state[node] = 1
        path.append(node)
        for nxt in sorted(successors.get(node, set())):
            if state.get(nxt) == 1:
                return path[path.index(nxt) :] + [nxt]
            if state.get(nxt, 0) == 0:
                found = walk(nxt)
                if found:
                    return found
        path.pop()
        state[node] = 2
        return None

    for node in sorted(ids):
        if state.get(node, 0) == 0:
            found = walk(node)
            if found:
                return found
    return None


def reachable_count(start: str, successors: dict[str, set[str]]) -> int:
    """How many distinct items are reachable forward from one item, excluding itself.

    Args:
        start: The item to walk from.
        successors: Blocker id -> the ids it blocks.

    Returns:
        The size of the forward reachable set.
    """
    seen: set[str] = set()
    pending = deque(successors.get(start, set()))
    while pending:
        node = pending.popleft()
        if node in seen or node == start:
            continue
        seen.add(node)
        pending.extend(successors.get(node, set()))
    return len(seen)


def _as_int(value: Any) -> int | None:
    """Read a value as an integer, or None when it is absent or unusable.

    Args:
        value: The raw value.

    Returns:
        The integer, or None.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_number(value: Any) -> int | float | None:
    """Read a value as a number, keeping a fraction, or None when it is absent or unusable.

    A judged size may fall between rungs, and snapping it up needs the fraction intact.

    Args:
        value: The raw value.

    Returns:
        The number, as an integer when it is whole, or None.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return int(number) if number.is_integer() else number


def _resolve_level(payload: dict[str, Any], override: str | None) -> dict[str, Any]:
    """Pick the level parameters for this run.

    Args:
        payload: The parsed input document.
        override: The level named on the command line, if any.

    Returns:
        The level's parameter block, with its name under `level`.

    Raises:
        WsjfError: No level was named, or the name is not one this module defines.
    """
    name = override or payload.get("level")
    if name not in LEVELS:
        msg = f"level must be one of {sorted(LEVELS)}, got {name!r}"
        raise WsjfError(msg)
    return {"level": name, **LEVELS[name]}


def _estimate(item: dict[str, Any]) -> dict[str, Any]:
    """The judged size estimate an item carries, with its range and confidence.

    Args:
        item: The item being scored.

    Returns:
        `sizeEstimate`, `sizeLow`, `sizeHigh` and `sizeConfidence`, each only when given.
    """
    fields = {
        "sizeEstimate": _as_number(item.get("jobSize")),
        "sizeLow": _as_number(item.get("sizeLow")),
        "sizeHigh": _as_number(item.get("sizeHigh")),
        "sizeConfidence": _as_int(item.get("sizeConfidence")),
    }
    return {key: value for key, value in fields.items() if value is not None}


def _resolve_size(item: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Settle one item's job size: the sum of its children, or its judged estimate.

    An Epic with children is sized as the plain sum of their sizes, which need not be a
    Fibonacci number. Its judged estimate is kept beside it, and a sum outside the
    estimate's plausible range is flagged. Without children, the estimate is placed on
    the Fibonacci scale.

    Args:
        item: The item being scored.
        params: The level's parameter block.

    Returns:
        A record carrying `jobSize`, `sizeSource` and the estimate's fields, or `reason`
        when the size is missing.

    Raises:
        WsjfError: A supplied size is not a positive number, or children were supplied at
            a level that does not roll up.
    """
    estimate = _estimate(item)
    children = [
        c for c in (_as_int(c) for c in item.get("childSizes") or []) if c is not None
    ]
    if children:
        if not params["rollup"]:
            msg = f"level {params['level']} does not roll child sizes up"
            raise WsjfError(msg)
        total = sum(children)
        record = {"jobSize": total, "sizeSource": "child-rollup", **estimate}
        if "sizeLow" in estimate and "sizeHigh" in estimate:
            record["sizeOutsideRange"] = not (
                estimate["sizeLow"] <= total <= estimate["sizeHigh"]
            )
        return record
    supplied = estimate.get("sizeEstimate")
    if supplied is None:
        return {"reason": "no jobSize supplied and no childSizes to roll up"}
    rung, over = snap_size(supplied, params["sizeCeiling"])
    record = {"jobSize": rung, "sizeSource": "supplied", **estimate}
    if over or rung != supplied:
        record["sizeFault"] = {"supplied": supplied, "rung": rung, "aboveScale": over}
    return record


def _resolve_rroe(
    item: dict[str, Any],
    params: dict[str, Any],
    successors: dict[str, set[str]],
    has_edges: bool,
) -> dict[str, Any]:
    """Settle one item's RR-OE, from a supplied value, a supplied count, or the graph.

    Args:
        item: The item being scored.
        params: The level's parameter block.
        successors: The forward edge index.
        has_edges: Whether the caller supplied an edge list, empty or not.

    Returns:
        A record carrying `riskReductionOpportunityEnablement` and `reaches`, or `reason`.
    """
    supplied = _as_int(item.get("riskReductionOpportunityEnablement"))
    reaches = _as_int(item.get("reaches"))
    if supplied is not None:
        return {
            "riskReductionOpportunityEnablement": supplied,
            "reaches": reaches,
            "rroeSource": "supplied",
        }
    if reaches is None:
        if not has_edges:
            return {
                "reason": "RR-OE needs a dependency graph: supply edges, reaches, or RR-OE"
            }
        reaches = reachable_count(str(item["id"]), successors)
        source = "graph"
    else:
        source = "supplied-count"
    return {
        "riskReductionOpportunityEnablement": band(
            reaches, params["rroeBands"], params["rroeTop"]
        ),
        "reaches": reaches,
        "rroeSource": source,
    }


def _confidence(item: dict[str, Any]) -> int | None:
    """The value confidence: the confidence judged with UBV and TC, or inherited with them.

    It is never combined with the size confidence, which stays with the estimate as
    `sizeConfidence`: a Task inherits its Epic's value confidence, and an Epic's size
    confidence says nothing about its value.

    Args:
        item: The item being scored.

    Returns:
        The integer percent, or None when none was supplied.
    """
    return _as_int(item.get("confidence"))


#: Size fields of a scored record -> the metadata keys they are stored under.
SIZE_KEYS = {
    "sizeEstimate": "wsjf_size_estimate",
    "sizeLow": "wsjf_size_low",
    "sizeHigh": "wsjf_size_high",
    "sizeConfidence": "wsjf_size_confidence",
    "sizeOutsideRange": "wsjf_size_outside_range",
}


def _render(value: Any) -> str:
    """Render one metadata value: booleans as `true`/`false`, numbers without a `.0`.

    Args:
        value: The value.

    Returns:
        Its stored form.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _metadata(record: dict[str, Any], params: dict[str, Any]) -> dict[str, str]:
    """The metadata a caller may store for one scored item.

    Args:
        record: The scored item.
        params: The level's parameter block.

    Returns:
        Keys to string values, carrying no character a shell would mis-split.
    """
    pairs = {
        "wsjf": f"{record['wsjf']:.2f}",
        "wsjf_calculated_at": now_iso(),
        "wsjf_rubric": params["rubric"],
        "wsjf_ubv": str(record["userBusinessValue"]),
        "wsjf_tc": str(record["timeCriticality"]),
        "wsjf_rroe": str(record["riskReductionOpportunityEnablement"]),
        "wsjf_cod": str(record["costOfDelay"]),
        "wsjf_size": str(record["jobSize"]),
        "wsjf_size_source": record["sizeSource"],
    }
    if record.get("reaches") is not None:
        pairs[params["reachKey"]] = str(record["reaches"])
    for field, key in SIZE_KEYS.items():
        if record.get(field) is not None:
            pairs[key] = _render(record[field])
    if record.get("valueFrom"):
        pairs["wsjf_value_from"] = str(record["valueFrom"])
    if record.get("confidence") is not None:
        pairs["wsjf_confidence"] = str(record["confidence"])
    return pairs


def score(payload: dict[str, Any], level: str | None = None) -> dict[str, Any]:
    """Score every item in one document.

    Args:
        payload: The input document.
        level: The level named on the command line, overriding the document's own.

    Returns:
        The scores, whatever could not be scored and why, any size faults, and the cycle
        when the edge graph has one.

    Raises:
        WsjfError: The level is unusable, or an item carries no id.
    """
    params = _resolve_level(payload, level)
    items = payload.get("items") or []
    for item in items:
        if not item.get("id"):
            msg = "every item needs an id"
            raise WsjfError(msg)
    ids = {str(i["id"]) for i in items}
    has_graph = payload.get("edges") is not None
    edges = payload.get("edges") or []
    successors = build_successors(edges, ids)
    cycle = find_cycle(successors, ids)
    if cycle:
        return {
            "ok": False,
            "level": params["level"],
            "scores": [],
            "unscored": [
                {"id": i, "reason": "the edge graph has a cycle"} for i in sorted(ids)
            ],
            "sizeFaults": [],
            "outsideRange": [],
            "cycle": cycle,
        }

    scores: list[dict[str, Any]] = []
    unscored: list[dict[str, Any]] = []
    faults: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item["id"])
        ubv = _as_int(item.get("userBusinessValue"))
        tc = _as_int(item.get("timeCriticality"))
        if ubv is None or tc is None:
            unscored.append(
                {"id": item_id, "reason": "no userBusinessValue or timeCriticality"}
            )
            continue
        rroe = _resolve_rroe(item, params, successors, has_graph)
        if "reason" in rroe:
            unscored.append({"id": item_id, "reason": rroe["reason"]})
            continue
        size = _resolve_size(item, params)
        if "reason" in size:
            unscored.append({"id": item_id, "reason": size["reason"]})
            continue
        fault = size.pop("sizeFault", None)
        if fault:
            faults.append({"id": item_id, **fault})
        if size.get("sizeOutsideRange"):
            outside.append(
                {
                    "id": item_id,
                    "size": size["jobSize"],
                    "estimate": size.get("sizeEstimate"),
                    "low": size["sizeLow"],
                    "high": size["sizeHigh"],
                }
            )
        cod = ubv + tc + rroe["riskReductionOpportunityEnablement"]
        record: dict[str, Any] = {
            "id": item_id,
            "userBusinessValue": ubv,
            "timeCriticality": tc,
            "valueFrom": item.get("valueFrom"),
            **rroe,
            **size,
            "costOfDelay": cod,
            "wsjf": round(cod / size["jobSize"], 2),
            "confidence": _confidence(item),
        }
        record["metadata"] = _metadata(record, params)
        scores.append(record)
    return {
        "ok": not unscored,
        "level": params["level"],
        "scores": scores,
        "unscored": unscored,
        "sizeFaults": faults,
        "outsideRange": outside,
        "cycle": None,
    }


def reach(payload: dict[str, Any], level: str | None = None) -> dict[str, Any]:
    """Report the reachability count and RR-OE band for every item, and nothing else.

    Args:
        payload: The input document.
        level: The level named on the command line, overriding the document's own.

    Returns:
        One record per item, and the cycle when the edge graph has one.

    Raises:
        WsjfError: The level is unusable.
    """
    params = _resolve_level(payload, level)
    items = payload.get("items") or []
    ids = {str(i["id"]) for i in items}
    successors = build_successors(payload.get("edges") or [], ids)
    cycle = find_cycle(successors, ids)
    if cycle:
        return {"ok": False, "level": params["level"], "reaches": [], "cycle": cycle}
    rows = []
    for item_id in sorted(ids):
        count = reachable_count(item_id, successors)
        rows.append(
            {
                "id": item_id,
                "reaches": count,
                "riskReductionOpportunityEnablement": band(
                    count, params["rroeBands"], params["rroeTop"]
                ),
            }
        )
    return {"ok": True, "level": params["level"], "reaches": rows, "cycle": None}


def scales(level: str) -> dict[str, Any]:
    """Report the computed tables for one level.

    Args:
        level: The level name.

    Returns:
        The RR-OE bands, the job-size scale and its ceiling, and the roll-up rule.

    Raises:
        WsjfError: The level is not one this module defines.
    """
    params = _resolve_level({}, level)
    ceiling = params["sizeCeiling"]
    rungs = fibonacci(LISTED_RUNGS)
    return {
        "level": params["level"],
        "rubric": params["rubric"],
        "rroe": {
            "bands": [{"upTo": c, "rroe": r} for c, r in params["rroeBands"]],
            "above": params["rroeTop"],
        },
        "jobSize": {
            "scale": "fibonacci",
            "rungs": [r for r in rungs if ceiling is None or r <= ceiling],
            "continuesUpward": ceiling is None,
            "max": ceiling,
        },
        "childSizeRollup": (
            "the plain sum of the children's sizes" if params["rollup"] else None
        ),
        "reachMetadataKey": params["reachKey"],
    }


def _case(name: str, expected: Any, got: Any) -> dict[str, Any]:
    """One selftest case, judged by equality.

    Args:
        name: What the case exercises.
        expected: The value the rubric must produce.
        got: The value it produced.

    Returns:
        The case with its verdict.
    """
    return {"case": name, "pass": expected == got, "expected": expected, "got": got}


def selftest() -> dict[str, Any]:
    """Exercise the bands, the scale, the roll-up, the graph walk and the missing inputs.

    Returns:
        Each case with its expectation, what it produced, and whether they match; `ok`
        is true only when every case passes.
    """
    cases: list[dict[str, Any]] = []

    graph = {
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "C"},
            {"from": "B", "to": "D"},
        ],
        "items": [
            {"id": "A", "userBusinessValue": 8, "timeCriticality": 3, "jobSize": 5},
            {"id": "B", "userBusinessValue": 8, "timeCriticality": 3, "jobSize": 3},
            {"id": "C", "userBusinessValue": 8, "timeCriticality": 3, "jobSize": 1},
            {"id": "D", "userBusinessValue": 8, "timeCriticality": 3, "jobSize": 1},
        ],
    }
    got = score(graph, "task")
    cases.append(
        _case(
            "transitive reach",
            {"A": 3, "B": 2, "C": 0, "D": 0},
            {s["id"]: s["reaches"] for s in got["scores"]},
        )
    )

    edgeless = score(
        {
            "edges": [],
            "items": [
                {"id": "X", "userBusinessValue": 5, "timeCriticality": 2, "jobSize": 3}
            ],
        },
        "task",
    )
    cases.append(
        _case(
            "an empty edge list counts 0",
            {"reaches": 0, "rroe": 1},
            {
                "reaches": edgeless["scores"][0]["reaches"],
                "rroe": edgeless["scores"][0]["riskReductionOpportunityEnablement"],
            },
        )
    )

    rollup_item = {
        "id": "E",
        "userBusinessValue": 13,
        "timeCriticality": 3,
        "riskReductionOpportunityEnablement": 13,
        "jobSize": 34,
        "sizeLow": 21,
        "sizeHigh": 55,
        "sizeConfidence": 60,
        "confidence": 80,
        "childSizes": [21, 21, 5],
    }
    rollup = score({"items": [rollup_item]}, "epic")["scores"][0]
    cases.append(
        _case(
            "roll-up is the plain sum, estimate kept, inside its range",
            {
                "jobSize": 47,
                "sizeSource": "child-rollup",
                "wsjf_size_estimate": "34",
                "wsjf_size_outside_range": "false",
                "confidence": 80,
            },
            {
                "jobSize": rollup["jobSize"],
                "sizeSource": rollup["sizeSource"],
                "wsjf_size_estimate": rollup["metadata"].get("wsjf_size_estimate"),
                "wsjf_size_outside_range": rollup["metadata"].get(
                    "wsjf_size_outside_range"
                ),
                "confidence": rollup["confidence"],
            },
        )
    )

    outside = score({"items": [{**rollup_item, "childSizes": [34, 34, 8]}]}, "epic")
    cases.append(
        _case(
            "roll-up outside the estimate's range is flagged, not refused",
            {
                "size": 76,
                "flagged": [
                    {"id": "E", "size": 76, "estimate": 34, "low": 21, "high": 55}
                ],
            },
            {
                "size": outside["scores"][0]["jobSize"],
                "flagged": outside["outsideRange"],
            },
        )
    )

    big = score(
        {
            "items": [
                {
                    "id": "P",
                    "userBusinessValue": 8,
                    "timeCriticality": 2,
                    "riskReductionOpportunityEnablement": 5,
                    "jobSize": 200,
                }
            ]
        },
        "epic",
    )
    cases.append(
        _case(
            "an Epic estimate snaps up the unbounded Fibonacci scale",
            {"jobSize": 233, "aboveScale": False},
            {
                "jobSize": big["scores"][0]["jobSize"],
                "aboveScale": big["sizeFaults"][0]["aboveScale"],
            },
        )
    )

    no_graph = score(
        {
            "items": [
                {"id": "X", "userBusinessValue": 5, "timeCriticality": 2, "jobSize": 3}
            ]
        },
        "task",
    )
    cases.append(
        _case(
            "no graph and no RR-OE",
            [
                {
                    "id": "X",
                    "reason": "RR-OE needs a dependency graph: supply edges, reaches, or RR-OE",
                }
            ],
            no_graph["unscored"],
        )
    )

    supplied = score(
        {
            "items": [
                {
                    "id": "X",
                    "userBusinessValue": 5,
                    "timeCriticality": 2,
                    "riskReductionOpportunityEnablement": 8,
                    "jobSize": 3,
                }
            ]
        },
        "task",
    )
    cases.append(
        _case("supplied RR-OE needs no graph", 5.0, supplied["scores"][0]["wsjf"])
    )

    cyclic = score(
        {
            "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "A"}],
            "items": [
                {"id": "A", "userBusinessValue": 5, "timeCriticality": 2, "jobSize": 3},
                {"id": "B", "userBusinessValue": 5, "timeCriticality": 2, "jobSize": 3},
            ],
        },
        "task",
    )
    cases.append(
        _case(
            "cycle",
            {"ok": False, "cycle": ["A", "B", "A"]},
            {"ok": cyclic["ok"], "cycle": cyclic["cycle"]},
        )
    )

    over = score(
        {
            "items": [
                {
                    "id": "T",
                    "userBusinessValue": 5,
                    "timeCriticality": 2,
                    "riskReductionOpportunityEnablement": 1,
                    "jobSize": 21,
                    "sizeConfidence": 50,
                }
            ]
        },
        "task",
    )
    cases.append(
        _case(
            "a Task above 13 is a decomposition fault",
            {"rung": 13, "aboveScale": True},
            {
                "rung": over["sizeFaults"][0]["rung"],
                "aboveScale": over["sizeFaults"][0]["aboveScale"],
            },
        )
    )

    separate = score(
        {
            "items": [
                {
                    "id": "V",
                    "userBusinessValue": 8,
                    "timeCriticality": 2,
                    "riskReductionOpportunityEnablement": 3,
                    "jobSize": 8,
                    "sizeLow": 5,
                    "sizeHigh": 21,
                    "sizeConfidence": 40,
                    "confidence": 85,
                }
            ]
        },
        "epic",
    )["scores"][0]
    cases.append(
        _case(
            "value confidence and size confidence stay separate",
            {"wsjf_confidence": "85", "wsjf_size_confidence": "40"},
            {
                "wsjf_confidence": separate["metadata"].get("wsjf_confidence"),
                "wsjf_size_confidence": separate["metadata"].get(
                    "wsjf_size_confidence"
                ),
            },
        )
    )

    return {"ok": all(c["pass"] for c in cases), "cases": cases}


def _read_payload(path: str | None) -> dict[str, Any]:
    """Read the input document from a file or stdin.

    Args:
        path: The file to read, or None for stdin.

    Returns:
        The parsed document.

    Raises:
        WsjfError: The input is not a JSON object.
    """
    raw = (
        sys.stdin.read() if path in (None, "-") else open(path, encoding="utf-8").read()
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"input is not valid JSON: {exc}"
        raise WsjfError(msg) from exc
    if not isinstance(payload, dict):
        msg = "input must be a JSON object"
        raise WsjfError(msg)
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Assemble the command line.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        description="WSJF arithmetic over supplied inputs."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        (
            "score",
            "score every item, computing only what the item does not already carry",
        ),
        ("reach", "report the reachability count and RR-OE band, and nothing else"),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--level", choices=sorted(LEVELS), help="epic or task")
        cmd.add_argument("--input", help="a JSON file; omit for stdin")

    tables = sub.add_parser("scales", help="print the computed tables for one level")
    tables.add_argument("--level", choices=sorted(LEVELS), required=True)

    sub.add_parser(
        "selftest", help="exercise the bands, the scale, the roll-up and the graph walk"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one command.

    Args:
        argv: Argument vector, or None for sys.argv.

    Returns:
        The process exit status.
    """
    args = build_parser().parse_args(argv)
    try:
        if args.command == "score":
            result = score(_read_payload(args.input), args.level)
        elif args.command == "reach":
            result = reach(_read_payload(args.input), args.level)
        elif args.command == "scales":
            result = scales(args.level)
        else:
            result = selftest()
    except (WsjfError, OSError) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False)
        )
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if args.command != "selftest" or result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
