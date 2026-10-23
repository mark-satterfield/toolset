"""Render ``epicorder.py``'s analysis as the Markdown report the owner reads.

Epic titles lead everywhere; bead ids follow in parentheses only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from epicorder import Analysis, Check, Order, Pair, Unit

TOP: Final = 10
LISTED: Final = 3


def _name(analysis: Analysis, bead: str) -> str:
    return f"{analysis.epics[bead].title} ({bead})"


def _title(analysis: Analysis, bead: str) -> str:
    return analysis.epics[bead].title if bead in analysis.epics else bead


def _sizes(result: Order) -> list[int]:
    values: list[int] = list(result.levels.values())
    return [values.count(level) for level in range(1, max(values) + 1)]


def _starts(analysis: Analysis, result: Order) -> list[str]:
    return sorted((bead for bead, level in result.levels.items() if level == 1), key=lambda b: analysis.epics[b].title)


def _length(result: Order) -> int:
    return sum(len(step) for step in result.chain)


def _step(analysis: Analysis, step: tuple[str, ...]) -> str:
    if len(step) == 1:
        return _title(analysis, step[0])
    return "[cycle: " + ", ".join(_title(analysis, bead) for bead in step) + "]"


def _units(analysis: Analysis, units: tuple[Unit, ...]) -> str:
    named: list[str] = [analysis.decisions[unit].label for unit in units[:LISTED]]
    more: str = f" (+{len(units) - LISTED} more)" if len(units) > LISTED else ""
    return "; ".join(named) + more


def _edge_line(analysis: Analysis, pair: Pair, units: tuple[Unit, ...]) -> str:
    return f"- {_name(analysis, pair[1])} waits for {_name(analysis, pair[0])} — {_units(analysis, units)}"


def _shape(analysis: Analysis, result: Order) -> list[str]:
    sizes: list[int] = _sizes(result)
    return [
        f"- Edges after transitive reduction: {len(result.edges)} (before: {len(result.raw)}).",
        f"- Can start now: **{sizes[0]}** Epics.",
        f"- Levels: {len(sizes)}; maximum concurrency: **{max(sizes)}** Epics in one level.",
        f"- Epics per level: {', '.join(f'L{n}={size}' for n, size in enumerate(sizes, start=1))}.",
        f"- Longest chain ({_length(result)} Epics, {len(result.chain)} levels): "
        + " → ".join(_step(analysis, step) for step in result.chain)
        + ".",
    ]


def _top(analysis: Analysis, result: Order) -> list[str]:
    ranked: list[str] = sorted(analysis.epics, key=lambda b: (-result.unlocks[b], analysis.epics[b].title))[:TOP]
    return [f"{n}. {_name(analysis, bead)} — unlocks {result.unlocks[bead]}" for n, bead in enumerate(ranked, start=1)]


def _listed(analysis: Analysis, pairs: Iterable[Pair]) -> list[str]:
    return [f"  - {_name(analysis, b)} waits for {_name(analysis, a)}" for a, b in pairs]


def _details(summary: str, lines: list[str]) -> list[str]:
    return [f"<details><summary>{summary}</summary>", "", *lines, "", "</details>", ""]


def _closing(result: Order, hand: Iterable[Pair]) -> list[Pair]:
    successors: dict[str, set[str]] = {}
    for start, end in result.raw:
        successors.setdefault(start, set()).add(end)

    def reaches(start: str, goal: str) -> bool:
        seen: set[str] = set()
        todo: list[str] = [start]
        while todo:
            node: str = todo.pop()
            if node == goal:
                return True
            if node not in seen:
                seen.add(node)
                todo.extend(successors.get(node, ()))
        return False

    return sorted(pair for pair in hand if reaches(pair[1], pair[0]))


def _diff(analysis: Analysis, result: Order) -> list[str]:
    proposed: set[Pair] = set(result.edges)
    current: Mapping[Pair, bool] = analysis.current
    hand: set[Pair] = {pair for pair, owned in current.items() if not owned}
    owned: set[Pair] = set(current) - hand
    added: list[Pair] = sorted(proposed - set(current))
    closing: list[Pair] = _closing(result, hand)
    return [
        (
            f"Current `tracks` edges between open Epics: {len(current)} — {len(hand)} made by hand, "
            f"{len(owned)} owned by the pipeline. Proposed: {len(proposed)}."
        ),
        "",
        "Edges | Hand-made | Pipeline-owned",
        "--- | --- | ---",
        f"Also proposed (kept) | {len(hand & proposed)} | {len(owned & proposed)}",
        f"Not proposed | {len(hand - proposed)} | {len(owned - proposed)}",
        f"New (not in beads) | — | {len(added)}",
        "",
        "`--apply` replaces the pipeline-owned edges and never removes a hand-made edge.",
        "",
        (
            f"Hand-made edges that run against the proposed edges (the proposed edges lead from the waiting Epic "
            f"back to the one it waits for, so together they close a cycle): {len(closing)}."
        ),
        "",
        *_details("Hand-made edges that close a cycle with the proposed edges", _listed(analysis, closing)),
        *_details("Hand-made edges also proposed", _listed(analysis, sorted(hand & proposed))),
        *_details("Hand-made edges not proposed", _listed(analysis, sorted(hand - proposed))),
        *_details("Pipeline-owned edges also proposed", _listed(analysis, sorted(owned & proposed))),
        *_details("Pipeline-owned edges not proposed", _listed(analysis, sorted(owned - proposed))),
        *_details("New edges", _listed(analysis, added)),
    ]


def _cycles(analysis: Analysis, result: Order) -> list[str]:
    if not result.cycles:
        return ["No cycles: no two Epics define something the other uses."]
    lines: list[str] = [
        (
            "Each cycle is a set of Epics that, through the entries below, each define something another one "
            "uses. None is broken; the members share a level. The owner decides how each one is resolved."
        ),
        "",
    ]
    for n, cycle in enumerate(result.cycles, start=1):
        lines.extend([
            f"**Cycle {n}** ({len(cycle.members)} Epics, {len(cycle.edges)} edges inside).",
            "",
            "The entries that tie it together, by the number of edges inside the cycle each one makes:",
            "",
            "Entry | Evidence for its drivers | Drivers | Users | Edges inside",
            "--- | --- | --- | --- | ---",
            *_cycle_units(analysis, cycle.edges),
            "",
            *_details("Members", [f"- {_name(analysis, bead)}" for bead in cycle.members]),
            *_details(
                "Every edge inside the cycle",
                [_edge_line(analysis, pair, units) for pair, units in cycle.edges.items()],
            ),
        ])
    return lines


def _who(analysis: Analysis, beads: tuple[str, ...]) -> str:
    if len(beads) > LISTED:
        return f"{len(beads)} Epics"
    return ", ".join(_title(analysis, bead) for bead in beads)


def _cycle_units(analysis: Analysis, edges: Mapping[Pair, tuple[Unit, ...]]) -> list[str]:
    counts: dict[Unit, int] = {}
    for units in edges.values():
        for unit in units:
            counts[unit] = counts.get(unit, 0) + 1
    rows: list[str] = []
    for unit, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        decision = analysis.decisions[unit]
        rows.append(
            f"{decision.label} | {decision.rule} | {_who(analysis, decision.drivers)} | "
            f"{_who(analysis, decision.users)} | {count}",
        )
    return rows


def _check_line(analysis: Analysis, check: Check) -> str:
    who: str = f"{_title(analysis, check.waiter)} waits for {_title(analysis, check.driver)}"
    if not check.path:
        return f"- **No**: {who} is false; no chain of edges joins them."
    if check.direct:
        return f"- **Yes**: {who}, directly — {_units(analysis, check.direct)}."
    via: str = " → ".join(_title(analysis, bead) for bead in check.path)
    return f"- **Yes**: {who}, through {via}."


def _checks(analysis: Analysis, result: Order) -> list[str]:
    found: tuple[Check, ...] = analysis.checks[result.name]
    if not found:
        return []
    return ["### Spot-checks", "", *(_check_line(analysis, check) for check in found), ""]


def _scenario(analysis: Analysis, title: str, result: Order) -> list[str]:
    starts: list[str] = _starts(analysis, result)
    return [
        f"## {title}",
        "",
        *_shape(analysis, result),
        "",
        f"### Epics that can start now ({len(starts)})",
        "",
        *(f"- {_name(analysis, bead)}" for bead in starts),
        "",
        *_checks(analysis, result),
        "### Top 10 Epics by how many Epics they unlock (transitively)",
        "",
        *_top(analysis, result),
        "",
        "### Cycles",
        "",
        *_cycles(analysis, result),
        "",
        "### Diff against the current beads `tracks` edges",
        "",
        *_diff(analysis, result),
        f"### Every edge ({len(result.edges)})",
        "",
        "Each line names the entries the waiting Epic uses and the other Epic's requirements define.",
        "",
        *(_edge_line(analysis, pair, units) for pair, units in result.edges.items()),
        "",
    ]


def _summary(analysis: Analysis) -> str:
    a, b = analysis.orders
    a_sizes, b_sizes = _sizes(a), _sizes(b)
    sizes: str = ", ".join(str(len(cycle.members)) for cycle in a.cycles)
    cycles: str = (
        f"{len(a.cycles)} cycle(s) of Epics that each define something another uses remain (Epics in each: "
        f"{sizes}); they are not broken, count as one level each, and are listed as findings below"
        if a.cycles
        else "no cycles appear"
    )
    return (
        f"There are {len(analysis.epics)} open Epics. An edge now says only that one Epic uses an architecture "
        f"entry another Epic's own requirements define, so the user is elaborated after the definer; entries "
        f"no Epic defines (the VPC, the chassis library, the Cognito pool) make no edge, and no WSJF or other "
        f"ranking enters any edge. With nothing approved yet (scenario A), **{a_sizes[0]}** Epics can start now, "
        f"at most **{max(a_sizes)}** can be architected side by side in one level, and the longest chain is "
        f"**{_length(a)}** Epics across {len(a_sizes)} levels; {cycles}. If every `shared-*` entry were "
        f"already approved (scenario B), {b_sizes[0]} could start now, maximum concurrency would be "
        f"{max(b_sizes)}, and the longest chain {_length(b)} Epics. Nothing was written to beads."
    )


def _method(analysis: Analysis) -> list[str]:
    rules: dict[str, int] = {}
    for decision in analysis.decisions.values():
        rules[decision.rule] = rules.get(decision.rule, 0) + 1
    valid: str = "; ".join(f"{name}: {'no' if bad else 'yes'}" for name, bad in analysis.validation.items())
    lines: list[str] = [
        "## How the order was computed",
        "",
        "Relationships used, all architecture side:",
        "",
        (
            "- **Drives a feature.** An Epic drives a feature when it has a `drives` relationship to the feature, "
            "or to a document heading (or a whole document) that the feature's `describedBy` names. With no such "
            "Epic, the feature has a driver only when it serves the requirements of exactly one Epic "
            "(`hasRequirement` → `servedBy`) that does not only `restsOn` it; a feature serving several Epics with "
            "no `drives` has no driver and makes no edge (the first Epic elaborated approves it)."
        ),
        ("- **Uses a feature.** The other Epics the feature serves (`servedBy`), and the Epics with `restsOn` to it."),
        (
            "- **Drives a heading.** An Epic with a `drives` relationship to a document heading drives it. Its "
            "users are the Epics whose requirements that exact heading `covers`, and the Epics with `restsOn` "
            "to the heading or to an entry it describes."
        ),
        (
            "- **Not used to decide driving:** `covers` and `describedBy` through a heading no Epic `drives`; "
            "`realizedBy`, `homeIn` and dependency links. Services, stacks, infrastructure and libraries are "
            "never units of their own, so Epics adding different features to one service do not wait for each "
            "other, and an entry no Epic's requirements define makes no edge."
        ),
        "",
        (
            "Every driver of a unit gets an edge to every user of it. Co-drivers of one unit and users of one "
            "unit get no edge between them. A unit whose matrix `approved` flag is set makes no edge (none "
            "carries it today). Cycles are reported and never broken; each is one node in the transitive "
            "reduction and its members share a level."
        ),
        "",
        (
            f"- Units with at least one driver and one user: {len(analysis.decisions)} "
            f"({', '.join(f'{rule}: {count}' for rule, count in sorted(rules.items()))}, by the evidence that "
            "chose the drivers)."
        ),
        f"- `apply-edges` would accept each scenario's edges: {valid}.",
        *_refused(analysis),
    ]
    if analysis.missing:
        lines.append(
            "- Open Epics the matrix does not hold (no edges computed for them): "
            + ", ".join(_name(analysis, bead) for bead in analysis.missing)
            + ".",
        )
    return [*lines, ""]


def _refused(analysis: Analysis) -> list[str]:
    return [
        f"  - {name}: refused; with the edges `--apply` keeps, it would close: "
        + " → ".join(_title(analysis, bead) for bead in cycle)
        + "."
        for name, cycle in analysis.validation.items()
        if cycle
    ]


def render(analysis: Analysis) -> str:
    """Render the whole report.

    Returns:
        The Markdown text.

    """
    a, b = analysis.orders
    lines: list[str] = [
        "# Epic architecture order",
        "",
        _summary(analysis),
        "",
        *_method(analysis),
        *_scenario(analysis, "Scenario A: as things stand (nothing approved)", a),
        *_scenario(analysis, "Scenario B: every `shared-*` entry already approved", b),
    ]
    return "\n".join(lines).rstrip() + "\n"
