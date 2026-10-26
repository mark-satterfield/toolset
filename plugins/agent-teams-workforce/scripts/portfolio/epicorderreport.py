"""Render ``epicorder.py``'s analysis, computed from the matrix alone, as the Markdown report the owner reads.

Epic titles lead everywhere; bead ids follow in parentheses only. Features are named by their
matrix name, with their id in parentheses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from epicorder import edges_made

if TYPE_CHECKING:
    from collections.abc import Iterable

    from epicorder import Analysis, Check, Dropped, Pair
    from matrix_contract import EntryId

TOP: Final = 10
LISTED: Final = 3


def _name(analysis: Analysis, bead: str) -> str:
    if bead not in analysis.epics:
        return f"{bead} (an Epic the matrix does not hold)"
    return f"{analysis.epics[bead].title} ({bead})"


def _title(analysis: Analysis, bead: str) -> str:
    return analysis.epics[bead].title if bead in analysis.epics else bead


def _sizes(analysis: Analysis) -> list[int]:
    values: list[int] = list(analysis.order.levels.values())
    return [values.count(level) for level in range(1, max(values) + 1)]


def _starts(analysis: Analysis) -> list[str]:
    return sorted(
        (bead for bead, level in analysis.order.levels.items() if level == 1),
        key=lambda b: analysis.epics[b].title,
    )


def _features(analysis: Analysis, features: tuple[EntryId, ...]) -> str:
    named: list[str] = [analysis.decisions[feature].label for feature in features[:LISTED]]
    more: str = f" (+{len(features) - LISTED} more)" if len(features) > LISTED else ""
    return "; ".join(named) + more


def _edge_line(analysis: Analysis, pair: Pair, features: tuple[EntryId, ...]) -> str:
    return f"- {_name(analysis, pair[1])} waits for {_name(analysis, pair[0])} — {_features(analysis, features)}"


def _shape(analysis: Analysis) -> list[str]:
    result = analysis.order
    sizes: list[int] = _sizes(analysis)
    return [
        f"- Edges after transitive reduction: {len(result.edges)} (before: {len(result.raw)}).",
        f"- Can start now: **{sizes[0]}** Epics.",
        f"- Levels: {len(sizes)}; maximum concurrency: **{max(sizes)}** Epics in one level.",
        f"- Epics per level: {', '.join(f'L{n}={size}' for n, size in enumerate(sizes, start=1))}.",
        f"- Longest chain ({len(result.chain)} Epics): "
        + " → ".join(_title(analysis, bead) for bead in result.chain)
        + ".",
    ]


def _top(analysis: Analysis) -> list[str]:
    unlocks = analysis.order.unlocks
    ranked: list[str] = sorted(analysis.epics, key=lambda b: (-unlocks[b], analysis.epics[b].title))[:TOP]
    return [f"{n}. {_name(analysis, bead)} — unlocks {unlocks[bead]}" for n, bead in enumerate(ranked, start=1)]


def _listed(analysis: Analysis, pairs: Iterable[Pair]) -> list[str]:
    return [f"  - {_name(analysis, b)} waits for {_name(analysis, a)}" for a, b in pairs]


def _details(summary: str, lines: list[str]) -> list[str]:
    return [f"<details><summary>{summary}</summary>", "", *lines, "", "</details>", ""]


def _diff(analysis: Analysis) -> list[str]:
    if analysis.standing is None:
        return ["Beads was not read, so the standing Epic-to-Epic edges are not compared.", ""]
    proposed: set[Pair] = set(analysis.order.edges)
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
        f"{dropped.requirements} requirement(s) served by {_features(analysis, dropped.features)}"
    )


def _dropped(analysis: Analysis) -> list[str]:
    if not analysis.order.dropped:
        return ["No edge closed a loop, so none was dropped.", ""]
    return [
        (
            "Each edge below lay inside a loop and was dropped, in this order: the edge whose driving Epic "
            "has the fewest requirements served by the feature that made it goes first, a tie to the lower "
            "bead id."
        ),
        "",
        *(_dropped_line(analysis, dropped) for dropped in analysis.order.dropped),
        "",
    ]


def _check_line(analysis: Analysis, check: Check) -> str:
    who: str = f"{_title(analysis, check.waiter)} waits for {_title(analysis, check.driver)}"
    if not check.path:
        return f"- **No**: {who} is false; no chain of edges joins them."
    if check.direct:
        return f"- **Yes**: {who}, directly — {_features(analysis, check.direct)}."
    via: str = " → ".join(_title(analysis, bead) for bead in check.path)
    return f"- **Yes**: {who}, through {via}."


def _checks(analysis: Analysis) -> list[str]:
    if not analysis.checks:
        return []
    return ["## Spot-checks", "", *(_check_line(analysis, check) for check in analysis.checks), ""]


def _feature_table(analysis: Analysis) -> list[str]:
    made: dict[EntryId, int] = edges_made(analysis)
    ranked: list[EntryId] = sorted(made, key=lambda f: (-made[f], f))
    rows: list[str] = []
    for feature_id in ranked:
        decision = analysis.decisions[feature_id]
        feature = analysis.features[feature_id]
        rows.append(
            f"{decision.label} | {_name(analysis, decision.driver)} | {feature.rule} | {decision.requirements} | "
            f"{len(feature.needs)} | {made[feature_id]}",
        )
    return [
        f"## Features that make edges ({len(ranked)})",
        "",
        (
            "Feature | Driving Epic | How it was decided | Driver's requirements served by it | Epics it orders | "
            "Edges it makes"
        ),
        "--- | --- | --- | --- | --- | ---",
        *rows,
        "",
    ]


def _summary(analysis: Analysis) -> str:
    sizes: list[int] = _sizes(analysis)
    shared: int = len(analysis.features)
    approved: int = sum(1 for feature in analysis.features.values() if feature.approved)
    owner_none: int = sum(1 for feature in analysis.features.values() if feature.driver is None)
    return (
        f"The matrix holds {len(analysis.epics)} Epics and {analysis.needed} features that serve their "
        f"requirements; {shared} features are needed by two or more Epics, {approved} of them have approved "
        f"architecture, {owner_none} are realized only in a stack the owner says no Epic drives, and "
        f"{len(analysis.decisions)} have a driving Epic and unapproved architecture; after the loop break "
        f"{len(edges_made(analysis))} of them order Epics. Each of those features has one driving Epic, and "
        f"every other Epic that needs it waits for the driver; no WSJF or other ranking enters any edge. "
        f"**{sizes[0]}** Epics can start now, at most **{max(sizes)}** can be architected side by side in one "
        f"level, and the longest chain is **{len(analysis.order.chain)}** Epics across {len(sizes)} levels; "
        f"{len(analysis.order.dropped)} edge(s) were dropped to break loops. The report writes nothing to beads."
    )


def _method() -> list[str]:
    return [
        "## How the order was computed",
        "",
        (
            "An edge means that two Epics need the same feature, its architecture is not approved, and the "
            "Epic that drives the feature is elaborated first, so no two Epics work on that unapproved "
            "architecture at once. The Epics and every relationship below are read from the matrix only."
        ),
        "",
        (
            "1. **The Epics that need a feature** are the Epics with a requirement `servedBy` it "
            "(`hasRequirement` → `servedBy`)."
        ),
        (
            "2. **Approved features make no edge.** A feature's architecture is approved when the feature is "
            "`realizedBy` at least one architecture-side entry and every architecture-side entry it is "
            "`realizedBy` carries the `approved` mark. A feature realized by nothing is not approved."
        ),
        "3. **Only a feature two or more Epics need makes edges.** A feature one Epic needs orders nothing.",
        (
            "4. **The driver** is the Epic with the most of its requirements `servedBy` the feature, a tie to "
            "the lower bead id. The owner's decisions come first: an architecture-side `drives` relationship "
            "from an Epic to a stack makes it the driver of every feature whose realizers are all in that "
            "stack, and `epicDriver: none` on a stack means no feature whose realizers are all in it makes an "
            "edge, because the stack is deployed in advance."
        ),
        (
            "5. **Every other Epic that needs the feature waits for the driver.** The edges several features "
            "make between one pair are one edge."
        ),
        (
            "6. **Loops are broken.** While the edges hold a loop, the edge inside a loop whose driving Epic "
            "has the fewest requirements served by the feature that made it is dropped, a tie to the lower "
            "bead id; every dropped edge is listed below. The rest is transitively reduced."
        ),
        "",
    ]


def render(analysis: Analysis) -> str:
    """Render the whole report.

    Returns:
        The Markdown text.

    """
    starts: list[str] = _starts(analysis)
    lines: list[str] = [
        "# Epic architecture order",
        "",
        _summary(analysis),
        "",
        *_method(),
        *_feature_table(analysis),
        "## Edges dropped to break loops",
        "",
        *_dropped(analysis),
        "## Shape of the order",
        "",
        *_shape(analysis),
        "",
        f"## Epics that can start now ({len(starts)})",
        "",
        *(f"- {_name(analysis, bead)}" for bead in starts),
        "",
        *_checks(analysis),
        "## Top 10 Epics by how many Epics they unlock (transitively)",
        "",
        *_top(analysis),
        "",
        "## Diff against the standing Epic-to-Epic edges in beads",
        "",
        *_diff(analysis),
        f"## Every edge ({len(analysis.order.edges)})",
        "",
        "Each line names the features both Epics need and the other Epic drives.",
        "",
        *(_edge_line(analysis, pair, features) for pair, features in analysis.order.edges.items()),
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"
