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
import collections
import json
import math
import pathlib
import sys
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, assert_never

import wsjf_types
from typeguard import CollectionCheckStrategy, check_type, typechecked
from wsjf_types import (
    Estimate,
    Fault,
    Item,
    Level,
    LevelBase,
    OutsideRange,
    Payload,
    ReachResult,
    ReachRow,
    Reason,
    Rroe,
    Scales,
    ScoreData,
    ScoreResult,
    ScoreRow,
    Size,
    Unscored,
)

#: Per-level parameters. `rroeBands` are (reach ceiling, RR-OE rung) pairs, ascending.
_ARGUMENT_ERROR: str = "Arguments violate the wsjf input contract"


LEVELS: dict[str, LevelBase] = {
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
    """Return the current time as an ISO 8601 timestamp in UTC.

    Returns:
        The timestamp, to whole seconds, with a trailing `Z`.

    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def band(count: int, bands: tuple[tuple[int, int], ...], top: int) -> int:
    """Place a count on a band table, falling through to the top rung.

    Args:
        count: The count to place.
        bands: Ceiling/rung pairs in ascending ceiling order.
        top: The rung for anything above the last ceiling.

    Returns:
        The rung the count lands on.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    ceiling: int
    rung: int
    if not (isinstance(count, int)) or not (isinstance(bands, tuple)) or not (isinstance(top, int)):
        raise TypeError(_ARGUMENT_ERROR)
    for ceiling, rung in bands:
        if count <= ceiling:
            return rung
    return top


def fibonacci(count: int) -> list[int]:
    """Return the first rungs of the size scale.

    Args:
        count: How many rungs.

    Returns:
        1, 2, 3, 5, 8, ... — `count` of them.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(count, int)):
        raise TypeError(_ARGUMENT_ERROR)
    rungs: list[int] = [1, 2]
    while len(rungs) < count:
        rungs.append(rungs[-1] + rungs[-2])
    return rungs[:count]


def snap_size(value: float) -> int:
    """Put a judged size on the unbounded Fibonacci scale: the smallest rung at or above it.

    Args:
        value: The size the caller judged.

    Returns:
        The rung; 1 for any finite value at or below 1.

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: The size is not finite.

    """
    low: int
    high: int
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(_ARGUMENT_ERROR)
    if not -float("inf") < value < float("inf"):
        message: str = "WSJF size must be finite"
        raise ValueError(message)
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    edge: dict[str, str]
    source: str | None
    target: str | None
    if not (isinstance(edges, list)) or not (isinstance(ids, set)):
        raise TypeError(_ARGUMENT_ERROR)
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(start, str)) or not (isinstance(successors, dict)):
        raise TypeError(_ARGUMENT_ERROR)
    seen: set[str] = set()
    pending: collections.deque[str] = deque(successors.get(start, set()))
    while pending:
        node: str = pending.popleft()
        if node in seen or node == start:
            continue
        seen.add(node)
        pending.extend(successors.get(node, set()))
    return len(seen)


def _as_int(value: object) -> int | None:
    """Read a value as an integer, or None when it is absent or unusable.

    Args:
        value: The raw value.

    Returns:
        The integer, or None.

    """
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _as_number(value: object) -> int | float | None:
    """Read a value as a number, keeping a fraction, or None when it is absent or unusable.

    A judged size may fall between rungs, and snapping it up needs the fraction intact.

    Args:
        value: The raw value.

    Returns:
        The number, as an integer when it is whole, or None.

    """
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        number: float = float(value)
    except TypeError, ValueError:
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _resolve_level(payload: Payload, override: str | None) -> Level:
    """Pick the level parameters for this run.

    Args:
        payload: The parsed input document.
        override: The level named on the command line, if any.

    Returns:
        The level's parameter block, with its name under `level`.

    Raises:
        WsjfError: No level was named, or the name is not one this module defines.

    """
    name: str | None = override or payload.get("level")
    if name is None or name not in LEVELS:
        msg: str = f"level must be one of {sorted(LEVELS)}, got {name!r}"
        raise WsjfError(msg)
    return {"level": name, **LEVELS[name]}


def _estimate(item: Item) -> Estimate:
    """Return the judged size estimate an item carries, with its range and confidence.

    Args:
        item: The item being scored.

    Returns:
        `sizeEstimate`, `sizeLow`, `sizeHigh` and `sizeConfidence`, each only when given.

    """
    result: Estimate = {}
    estimate: int | float | None = _as_number(item.get("jobSize"))
    low: int | float | None = _as_number(item.get("sizeLow"))
    high: int | float | None = _as_number(item.get("sizeHigh"))
    confidence: int | None = _as_int(item.get("sizeConfidence"))
    if estimate is not None:
        result["sizeEstimate"] = estimate
    if low is not None:
        result["sizeLow"] = low
    if high is not None:
        result["sizeHigh"] = high
    if confidence is not None:
        result["sizeConfidence"] = confidence
    return result


def _sized_estimate(estimate: Estimate, size: int, source: str) -> Size:
    """Attach the judged range and confidence to a resolved size.

    Returns:
        A sized record preserving every supplied estimate field.

    """
    record: Size = {"jobSize": size, "sizeSource": source}
    if "sizeEstimate" in estimate:
        record["sizeEstimate"] = estimate["sizeEstimate"]
    if "sizeLow" in estimate:
        record["sizeLow"] = estimate["sizeLow"]
    if "sizeHigh" in estimate:
        record["sizeHigh"] = estimate["sizeHigh"]
    if "sizeConfidence" in estimate:
        record["sizeConfidence"] = estimate["sizeConfidence"]
    return record


def _resolve_size(item: Item, params: Level) -> Size | Reason:
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
    estimate: wsjf_types.Estimate = _estimate(item)
    children: list[int] = (
        [c for c in (_as_int(x) for x in item.get("childSizes") or []) if c and c > 0] if params["rollup"] else []
    )
    if children:
        total: int = sum(children)
        record: Size = _sized_estimate(estimate, total, "child-rollup")
        if "sizeLow" in estimate and "sizeHigh" in estimate:
            record["sizeOutsideRange"] = not (estimate["sizeLow"] <= total <= estimate["sizeHigh"])
        return record
    supplied: int | float | None = estimate.get("sizeEstimate")
    if supplied is None:
        return {"reason": "no jobSize supplied and no childSizes to roll up"}
    rung: int = snap_size(supplied)
    threshold: int | None = params["decompositionFaultAbove"]
    over: bool = threshold is not None and rung > threshold
    record = _sized_estimate(estimate, rung, "supplied")
    if over or rung != supplied:
        record["sizeFault"] = {"supplied": supplied, "rung": rung, "aboveScale": over}
    return record


def _resolve_rroe(
    item: Item,
    params: Level,
    successors: dict[str, set[str]],
    has_edges: bool,
) -> Rroe | Reason:
    """Settle one item's RR-OE, from a supplied value, a supplied count, or the graph.

    Args:
        item: The item being scored.
        params: The level's parameter block.
        successors: The forward edge index.
        has_edges: Whether the caller supplied an edge list, empty or not.

    Returns:
        A record carrying `riskReductionOpportunityEnablement` and `reaches`, or `reason`.

    """
    supplied: int | None = _as_int(item.get("riskReductionOpportunityEnablement"))
    reaches: int | None = _as_int(item.get("reaches"))
    if supplied is not None:
        return {
            "riskReductionOpportunityEnablement": supplied,
            "reaches": reaches,
            "rroeSource": "supplied",
        }
    if reaches is None:
        if not has_edges:
            return {
                "reason": "RR-OE needs a dependency graph: supply edges, reaches, or RR-OE",
            }
        reaches = reachable_count(str(item["id"]), successors)
        source: str = "graph"
    else:
        source = "supplied-count"
    return {
        "riskReductionOpportunityEnablement": band(
            reaches,
            params["rroeBands"],
            params["rroeTop"],
        ),
        "reaches": reaches,
        "rroeSource": source,
    }


def _confidence(item: Item) -> int | None:
    """Return the value confidence supplied with UBV and TC.

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


def _render(value: object) -> str:
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


def _metadata(record: ScoreData, params: Level) -> dict[str, str]:
    """Return the metadata a caller may store for one scored item.

    Args:
        record: The scored item.
        params: The level's parameter block.

    Returns:
        Keys to string values, carrying no character a shell would mis-split.

    """
    field: str
    key: str
    pairs: dict[str, str] = {
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
    fields: dict[str, object] = dict(record)
    for field, key in SIZE_KEYS.items():
        if fields.get(field) is not None:
            pairs[key] = _render(fields[field])
    if record.get("valueFrom"):
        pairs["wsjf_value_from"] = str(record["valueFrom"])
    if record.get("confidence") is not None:
        pairs["wsjf_confidence"] = str(record["confidence"])
    return pairs


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def score(payload: Payload, level: str | None = None) -> ScoreResult:
    """Score every item in one document.

    Args:
        payload: The input document.
        level: The level named on the command line, overriding the document's own.

    Returns:
        The scores, whatever could not be scored and why, any size faults, and `cycle`
        (always None).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    item: Item
    if not (isinstance(payload, dict)) or not (isinstance(level, str) or level is None):
        raise TypeError(_ARGUMENT_ERROR)
    params: wsjf_types.Level = _resolve_level(payload, level)
    items: list[wsjf_types.Item] = payload.get("items") or []
    successors: dict[str, set[str]] = build_successors(payload.get("edges") or [], {item["id"] for item in items})

    scores: list[ScoreRow] = []
    unscored: list[Unscored] = []
    faults: list[Fault] = []
    outside: list[OutsideRange] = []
    for item in items:
        item_id: str = str(item.get("id"))
        ubv: int | None = _as_int(item.get("userBusinessValue"))
        tc: int | None = _as_int(item.get("timeCriticality"))
        if ubv is None or tc is None:
            unscored.append(
                {"id": item_id, "reason": "no userBusinessValue or timeCriticality"},
            )
            continue
        rroe: wsjf_types.Rroe | wsjf_types.Reason = _resolve_rroe(
            item,
            params,
            successors,
            payload.get("edges") is not None,
        )
        if "reason" in rroe:
            unscored.append({"id": item_id, "reason": check_type(rroe, Reason)["reason"]})
            continue
        rroe = check_type(rroe, Rroe, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        size: wsjf_types.Size | wsjf_types.Reason = _resolve_size(item, params)
        if "reason" in size:
            unscored.append({"id": item_id, "reason": check_type(size, Reason)["reason"]})
            continue
        size = check_type(size, Size, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        fault: wsjf_types.SizeFault | None = size.pop("sizeFault", None)
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
                },
            )
        cod: int = ubv + tc + rroe["riskReductionOpportunityEnablement"]
        record: ScoreData = {
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
        scores.append({**record, "metadata": _metadata(record, params)})
    return {
        "ok": not unscored,
        "level": params["level"],
        "scores": scores,
        "unscored": unscored,
        "sizeFaults": faults,
        "outsideRange": outside,
        "cycle": None,
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def reach(payload: Payload, level: str | None = None) -> ReachResult:
    """Report the reachability count and RR-OE band for every item, and nothing else.

    Args:
        payload: The input document.
        level: The level named on the command line, overriding the document's own.

    Returns:
        One record per item, and `cycle` (always None).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    item_id: str
    if not (isinstance(payload, dict)) or not (isinstance(level, str) or level is None):
        raise TypeError(_ARGUMENT_ERROR)
    params: wsjf_types.Level = _resolve_level(payload, level)
    items: list[wsjf_types.Item] = payload.get("items") or []
    ids: set[str] = {str(i.get("id")) for i in items}
    successors: dict[str, set[str]] = build_successors(payload.get("edges") or [], ids)
    rows: list[ReachRow] = []
    for item_id in sorted(ids):
        count: int = reachable_count(item_id, successors)
        rows.append(
            {
                "id": item_id,
                "reaches": count,
                "riskReductionOpportunityEnablement": band(
                    count,
                    params["rroeBands"],
                    params["rroeTop"],
                ),
            },
        )
    return {"ok": True, "level": params["level"], "reaches": rows, "cycle": None}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def scales(level: str) -> Scales:
    """Report the computed tables for one level.

    Args:
        level: The level name.

    Returns:
        The RR-OE bands, the job-size scale and its decomposition-fault threshold, and
        the roll-up rule.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(level, str)):
        raise TypeError(_ARGUMENT_ERROR)
    params: wsjf_types.Level = _resolve_level({}, level)
    rungs: list[int] = fibonacci(LISTED_RUNGS)
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
        "childSizeRollup": ("the plain sum of the children's sizes" if params["rollup"] else None),
        "reachMetadataKey": params["reachKey"],
    }


def _read_payload(path: str | None) -> Payload:
    """Read the input document from a file or stdin.

    Args:
        path: The file to read, or None for stdin.

    Returns:
        The parsed document.

    Raises:
        WsjfError: The input is not valid JSON.

    """
    raw: str = sys.stdin.read() if path in {None, "-"} else pathlib.Path(path).read_text(encoding="utf-8")
    try:
        payload: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg: str = f"input is not valid JSON: {exc}"
        raise WsjfError(msg) from exc
    return check_type(payload, Payload, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


class _Subcommands(Protocol):
    def add_parser(self, name: str, *, help: str) -> argparse.ArgumentParser: ...  # ruff: ignore[builtin-argument-shadowing] - Exact argparse keyword contract.


def build_parser() -> argparse.ArgumentParser:
    """Assemble the command line.

    Returns:
        The parser.

    """
    name: str
    help_text: str
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="WSJF arithmetic over supplied inputs.",
    )
    sub: _Subcommands = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        (
            "score",
            "score every item, computing only what the item does not already carry",
        ),
        ("reach", "report the reachability count and RR-OE band, and nothing else"),
    ):
        cmd: argparse.ArgumentParser = sub.add_parser(name, help=help_text)
        cmd.add_argument("--level", choices=sorted(LEVELS), help="epic or task")
        cmd.add_argument("--input", help="a JSON file; omit for stdin")

    tables: argparse.ArgumentParser = sub.add_parser("scales", help="print the computed tables for one level")
    tables.add_argument("--level", choices=sorted(LEVELS), required=True)
    return parser


@dataclass(frozen=True)
class CommandOptions:
    """Hold one validated arithmetic CLI request."""

    command: Literal["score", "reach", "scales"]
    level: str | None
    input: str | None

    def __post_init__(self) -> None:
        """Reject invalid command values.

        Raises:
            TypeError: A field violates the CLI request contract.

        """
        if self.command not in {"score", "reach", "scales"}:
            raise TypeError(_ARGUMENT_ERROR)
        if self.level is not None and not isinstance(self.level, str):
            raise TypeError(_ARGUMENT_ERROR)
        if self.input is not None and not isinstance(self.input, str):
            raise TypeError(_ARGUMENT_ERROR)


def _command_options(argv: list[str] | None) -> CommandOptions:
    """Parse command-line values into their explicit immutable contract.

    Returns:
        Validated command options.

    Raises:
        TypeError: Parser output violates the command contract.

    """
    args: argparse.Namespace = build_parser().parse_args(argv)
    command: object = args.command
    level: object = args.level
    source: object = getattr(args, "input", None)
    if command not in {"score", "reach", "scales"}:
        message: str = "Unknown WSJF command"
        raise TypeError(message)
    if level is not None and not isinstance(level, str):
        message = "WSJF level must be a string"
        raise TypeError(message)
    if source is not None and not isinstance(source, str):
        message = "WSJF input must be a path string"
        raise TypeError(message)
    return CommandOptions(check_type(command, Literal["score", "reach", "scales"]), level, source)


def _execute_command(options: CommandOptions) -> ScoreResult | ReachResult | Scales:
    """Evaluate one parsed arithmetic command.

    Returns:
        The selected operation's exact result.

    Raises:
        ValueError: The scales command names no level.

    """
    if options.command == "score":
        return score(_read_payload(options.input), options.level)
    if options.command == "reach":
        return reach(_read_payload(options.input), options.level)
    if options.command == "scales":
        if options.level is None:
            message: str = "scales requires an explicit level"
            raise ValueError(message)
        return scales(options.level)
    assert_never(options.command)


def main(argv: list[str] | None = None) -> int:
    """Run one command.

    Args:
        argv: Argument vector, or None for sys.argv.

    Returns:
        The process exit status.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(argv, list) or argv is None):
        raise TypeError(_ARGUMENT_ERROR)
    options: CommandOptions = _command_options(argv)
    result: ScoreResult | ReachResult | Scales
    try:
        result = _execute_command(options)
    except (WsjfError, OSError) as exc:
        sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False) + "\n")
        return 2
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
