"""Render ``epicorder.py``'s analysis, computed from the matrix alone, as the Markdown report the owner reads.

Epic titles lead everywhere; bead ids follow in parentheses only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from epicorder import Analysis, Check, Dropped, Order, Pair, Unit

TOP: Final = 10
LISTED: Final = 3


def _name(analysis: Analysis, bead: str) -> str:
    if bead not in analysis.epics:
        return f"{bead} (an Epic the matrix does not hold)"
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


def _diff(analysis: Analysis, result: Order) -> list[str]:
    if analysis.standing is None:
        return ["Beads was not read, so the standing Epic-to-Epic edges are not compared.", ""]
    proposed: set[Pair] = set(result.edges)
    standing: set[Pair] = {(edge.blocker, edge.blocked) for edge in analysis.standing}
    kinds: list[str] = sorted({edge.kind for edge in analysis.standing})
    return [
        (
            f"Standing Epic-to-Epic edges in beads: {len(standing)} ({', '.join(kinds) or 'none'}). "
            f"Computed: {len(proposed)}. `--apply` removes every standing edge, whoever made it, and writes "
            "each computed edge as a `tracks` edge."
        ),
        "",
        f"- Standing and computed (removed and written again): {len(standing & proposed)}.",
        f"- Standing and not computed (removed): {len(standing - proposed)}.",
        f"- Computed and not standing (new): {len(proposed - standing)}.",
        "",
        *_details("Standing edges not computed", _listed(analysis, sorted(standing - proposed))),
        *_details("New edges", _listed(analysis, sorted(proposed - standing))),
    ]


def _dropped_line(analysis: Analysis, dropped: Dropped) -> str:
    waiter, driver = dropped.pair[1], dropped.pair[0]
    return (
        f"- {_name(analysis, waiter)} no longer waits for {_name(analysis, driver)}: the driver has "
        f"{dropped.features} feature(s) in {_units(analysis, dropped.units)}"
    )


def _dropped(analysis: Analysis, result: Order) -> list[str]:
    if not result.dropped:
        return ["No edge closed a cycle, so none was dropped.", ""]
    return [
        (
            "Each edge below lay inside a cycle and was dropped, in this order: the edge whose driving Epic "
            "has the fewest features in the foundations that make it goes first, a tie to the lower bead id."
        ),
        "",
        *(_dropped_line(analysis, dropped) for dropped in result.dropped),
        "",
    ]


def _cycles(analysis: Analysis, result: Order) -> list[str]:
    if not result.cycles:
        return ["No cycle is left after the break."]
    lines: list[str] = [
        "Each cycle below is left after the break; `--apply` refuses to write any edge while one is.",
        "",
    ]
    for n, cycle in enumerate(result.cycles, start=1):
        lines.extend([
            f"**Cycle {n}** ({len(cycle.members)} Epics, {len(cycle.edges)} edges inside).",
            "",
            "Foundation | Driving Epic | Its features in the foundation | Users | Edges inside",
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
            f"{decision.label} | {_title(analysis, decision.driver)} | {decision.features} | "
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
        "### Edges dropped to break cycles",
        "",
        *_dropped(analysis, result),
        "### Cycles left",
        "",
        *_cycles(analysis, result),
        "",
        "### Diff against the standing Epic-to-Epic edges in beads",
        "",
        *_diff(analysis, result),
        f"### Every edge ({len(result.edges)})",
        "",
        "Each line names the foundations the waiting Epic realizes or uses and the other Epic drives.",
        "",
        *(_edge_line(analysis, pair, units) for pair, units in result.edges.items()),
        "",
    ]


def _summary(analysis: Analysis) -> str:
    a, b = analysis.orders
    a_sizes, b_sizes = _sizes(a), _sizes(b)
    driven: int = sum(1 for foundation in analysis.foundations.values() if foundation.driver is not None)
    left: str = f"{len(a.cycles)} cycle(s) are left, and `--apply` refuses them" if a.cycles else "no cycle is left"
    return (
        f"The matrix holds {len(analysis.epics)} Epics and {len(analysis.foundations)} shared foundations some "
        f"Epic touches; {driven} have a driving Epic. Only a foundation orders Epics: every Epic that realizes "
        f"part of it or uses one of its entries waits for its driving Epic, unless the matrix holds it "
        f"approved; no WSJF or other ranking enters any edge. As things stand (scenario A), "
        f"**{a_sizes[0]}** Epics can start now, at most **{max(a_sizes)}** can be architected side by side "
        f"in one level, and the longest chain is **{_length(a)}** Epics across {len(a_sizes)} levels; "
        f"{len(a.dropped)} edge(s) were dropped to break cycles and {left}. If every `shared-*` foundation "
        f"were already approved (scenario B), {b_sizes[0]} could start now, maximum concurrency would be "
        f"{max(b_sizes)}, and the longest chain {_length(b)} Epics. The report writes nothing to beads."
    )


def _foundation_row(analysis: Analysis, unit: Unit) -> str:
    foundation = analysis.foundations[unit]
    driver: str = "none" if foundation.driver is None else _title(analysis, foundation.driver)
    features: int | str = "" if foundation.driver is None else foundation.features.get(foundation.driver, 0)
    approved: str = "yes" if foundation.approved else "no"
    return f"{foundation.label} | {driver} | {foundation.rule} | {features} | {len(foundation.touching)} | {approved}"


def _foundations(analysis: Analysis) -> list[str]:
    return [
        "## Foundations and their drivers",
        "",
        "Foundation | Driving Epic | How it was decided | Driver's features in it | Epics touching it | Approved",
        "--- | --- | --- | --- | --- | ---",
        *(_foundation_row(analysis, unit) for unit in analysis.foundations),
        "",
    ]


def _method(analysis: Analysis) -> list[str]:
    lines: list[str] = [
        "## How the order was computed",
        "",
        (
            "An edge means that an architecture decision one Epic rests on should be designed from another "
            "Epic's requirements first, and the matrix does not hold that decision approved. The Epics and "
            "every relationship below are read from the matrix only."
        ),
        "",
        (
            "1. **Only shared foundations order Epics.** A foundation is a stack whose name starts with "
            "`shared-` or ends with `-lib` or `-infra`, with every entry homed in it (`homeIn`), and a layer "
            "or package homed in no such stack, on its own. Product services, components, events and app "
            "stacks make no Epic edge: who builds them first is build order, settled among Tasks."
        ),
        (
            "2. **Approved foundations make no edge.** A foundation is approved when its own entry and every "
            "architecture-side entry homed in it carry the matrix `approved` flag."
        ),
        (
            "3. **The owner's driver decisions come first.** A `drives` relationship on the architecture side "
            "from an Epic to the foundation's entry names its driving Epic; the stack attribute "
            "`epicDriver: none` says no Epic drives it. A foundation no Epic drives makes no edge: no Epic "
            "waits on it."
        ),
        (
            "4. **Otherwise, the most features.** The driving Epic is the one with strictly the most distinct "
            "features serving its requirements (`hasRequirement` → `servedBy`) that are `realizedBy` anything "
            "in the foundation. A tie for most means no Epic drives it, and it makes no edge."
        ),
        (
            "5. **Users wait for the driver.** Every other Epic that realizes part of the foundation, or "
            "reaches one of its entries as the far end of a dependency one hop away, waits for the driver; "
            "only entries some Epic realizes count. The edges several foundations make between one pair are "
            "one edge, and two Epics that only use a foundation get no edge between them."
        ),
        (
            "6. **Cycles are broken.** While the edges hold a cycle, the edge inside a cycle whose driving Epic "
            "has the fewest features in the foundations that make it is dropped, a tie to the lower bead id; "
            "every dropped edge is listed below. The rest is transitively reduced."
        ),
        "",
        f"- Foundations some Epic touches: {len(analysis.foundations)}.",
        f"- Foundations that make edges (a driving Epic and at least one user): {len(analysis.decisions)}.",
    ]
    return [*lines, ""]


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
        *_foundations(analysis),
        *_scenario(analysis, "Scenario A: as things stand (nothing approved)", a),
        *_scenario(analysis, "Scenario B: every `shared-*` foundation already approved", b),
    ]
    return "\n".join(lines).rstrip() + "\n"
