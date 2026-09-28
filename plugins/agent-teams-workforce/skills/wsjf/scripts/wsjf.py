#!/usr/bin/env python3
"""wsjf.py — WSJF arithmetic over supplied inputs. Reads only the named input file; writes nothing.

Usage:
  wsjf.py score  --level epic|task [--input FILE]
  wsjf.py reach  --level epic|task [--input FILE]
  wsjf.py scales --level epic|task

`--input` names a JSON file and defaults to stdin. Input for `score` and `reach`:

  {
    "level": "epic",                              // optional; --level wins
    "edges": [{"from": "A", "to": "B"}],          // optional: A comes before B
    "items": [
      {
        "id": "A",
        "userBusinessValue": 13,
        "timeCriticality": 3,
        "valueFrom": "E1",                        // optional
        "riskReductionOpportunityEnablement": 8,  // optional: used as given
        "reaches": 12,                            // optional: used instead of the graph walk
        "jobSize": 8,                             // the judged size estimate
        "sizeLow": 5, "sizeHigh": 13,             // optional
        "sizeConfidence": 70,                     // optional, integer percent
        "childSizes": [3, 5, 2],                  // optional, Epic only: size = their sum
        "confidence": 88                          // optional, integer percent
      }
    ]
  }

Output for `score`: {ok, level, scores, unscored, sizeFaults, outsideRange, cycle}; `cycle` is
always null.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Any

#: Per-level parameters. `rroeBands` are (reach ceiling, RR-OE rung) pairs, ascending.
LEVELS: dict[str, dict[str, Any]] = {
    "epic": {
        "rubric": "epic-wsjf",
        "rroeBands": ((0, 1), (1, 3), (3, 5), (9, 8), (19, 13)),
        "rroeTop": 20,
        "decompositionFaultAbove": None,
        "rollup": True,
        "reachKey": "wsjf_reaches",
    },
    "task": {
        "rubric": "task-wsjf",
        "rroeBands": ((0, 1), (1, 3), (3, 5), (6, 8), (9, 13)),
        "rroeTop": 20,
        "decompositionFaultAbove": 13,
        "rollup": False,
        "reachKey": "wsjf_unblocks",
    },
}

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


def snap_size(value: float) -> int:
    """Put a judged size on the unbounded Fibonacci scale: the smallest rung at or above it.

    Args:
        value: The size the caller judged.

    Returns:
        The rung; 1 for any value at or below 1.
    """
    low, high = 1, 2
    if value <= low:
        return low
    while high < value:
        low, high = high, low + high
    return high


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
    """Settle one item's job size: the sum of its positive child sizes, or its judged estimate.

    At a level that rolls up, positive integer `childSizes` are summed and a sum outside the
    estimate's range is flagged. Otherwise the estimate is snapped onto the Fibonacci scale.

    Args:
        item: The item being scored.
        params: The level's parameter block.

    Returns:
        A record carrying `jobSize`, `sizeSource` and the estimate's fields, or `reason`
        when the size is missing.
    """
    estimate = _estimate(item)
    children = (
        [c for c in (_as_int(x) for x in item.get("childSizes") or []) if c and c > 0]
        if params["rollup"]
        else []
    )
    if children:
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
    rung = snap_size(supplied)
    threshold = params["decompositionFaultAbove"]
    over = threshold is not None and rung > threshold
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
    """The value confidence supplied with UBV and TC.

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
        The scores, whatever could not be scored and why, any size faults, and `cycle`
        (always None).

    Raises:
        WsjfError: The level is unusable.
    """
    params = _resolve_level(payload, level)
    items = payload.get("items") or []
    ids = {str(i.get("id")) for i in items}
    has_graph = payload.get("edges") is not None
    successors = build_successors(payload.get("edges") or [], ids)

    scores: list[dict[str, Any]] = []
    unscored: list[dict[str, Any]] = []
    faults: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get("id"))
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
        One record per item, and `cycle` (always None).

    Raises:
        WsjfError: The level is unusable.
    """
    params = _resolve_level(payload, level)
    items = payload.get("items") or []
    ids = {str(i.get("id")) for i in items}
    successors = build_successors(payload.get("edges") or [], ids)
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
        The RR-OE bands, the job-size scale and its decomposition-fault threshold, and
        the roll-up rule.

    Raises:
        WsjfError: The level is not one this module defines.
    """
    params = _resolve_level({}, level)
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
            "rungs": rungs,
            "continuesUpward": True,
            "decompositionFaultAbove": params["decompositionFaultAbove"],
        },
        "childSizeRollup": (
            "the plain sum of the children's sizes" if params["rollup"] else None
        ),
        "reachMetadataKey": params["reachKey"],
    }


def _read_payload(path: str | None) -> dict[str, Any]:
    """Read the input document from a file or stdin.

    Args:
        path: The file to read, or None for stdin.

    Returns:
        The parsed document.

    Raises:
        WsjfError: The input is not valid JSON.
    """
    raw = (
        sys.stdin.read() if path in (None, "-") else open(path, encoding="utf-8").read()
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"input is not valid JSON: {exc}"
        raise WsjfError(msg) from exc
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
        else:
            result = scales(args.level)
    except (WsjfError, OSError) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False)
        )
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
