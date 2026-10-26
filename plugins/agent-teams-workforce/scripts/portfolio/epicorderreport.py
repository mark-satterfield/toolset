"""Render ``epicorder.py``'s analysis, computed from the matrix alone, as the Markdown report the owner reads.

Epic titles lead everywhere; bead ids follow in parentheses only. Shared items are named by their
matrix name, with their id in parentheses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from epicorder import deciding, edges_made, label, unjudged

if TYPE_CHECKING:
    from collections.abc import Iterable

    from epicorder import Analysis, Check, Dropped, Pair
    from matrix_contract import EntryId
    from matrixshared import SharedItem

TOP: Final = 10
LISTED: Final = 3


def _name(analysis: Analysis, bead: str) -> str:
    if bead in analysis.epics:
        return f"{analysis.epics[bead].title} ({bead})"
    if bead in analysis.others:
        other = analysis.others[bead]
        return f"{other.title} ({bead}, release {other.release or 'none'})"
    return f"{bead} (an Epic the matrix does not hold)"


def _title(analysis: Analysis, bead: str) -> str:
    return analysis.epics[bead].title if bead in analysis.epics else bead


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _sizes(analysis: Analysis) -> list[int]:
    values: list[int] = list(analysis.order.levels.values())
    return [values.count(level) for level in range(1, max(values) + 1)]


def _starts(analysis: Analysis) -> list[str]:
    return sorted(
        (bead for bead, level in analysis.order.levels.items() if level == 1),
        key=lambda b: analysis.epics[b].title,
    )


def _items(analysis: Analysis, items: tuple[EntryId, ...]) -> str:
    named: list[str] = [label(analysis, item) for item in items[:LISTED]]
    more: str = f" (+{len(items) - LISTED} more)" if len(items) > LISTED else ""
    return "; ".join(named) + more


def _edge_line(analysis: Analysis, pair: Pair, items: tuple[EntryId, ...]) -> str:
    return f"- {_name(analysis, pair[1])} waits for {_name(analysis, pair[0])} — {_items(analysis, items)}"


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


def _other_releases(analysis: Analysis) -> list[str]:
    others: list[str] = sorted(analysis.others, key=lambda b: (analysis.others[b].release, analysis.others[b].title))
    touching: list[Pair] = sorted(
        (edge.blocker, edge.blocked)
        for edge in analysis.standing or ()
        if edge.blocker in analysis.others or edge.blocked in analysis.others
    )
    lines: list[str] = [
        f"## Epics of other releases ({len(others)})",
        "",
        (
            f"Only the Epics of release `{analysis.release}` are ordered. The Epics below take no part: what they "
            "need makes no item shared, and no edge is computed to or from them. `--apply` removes every standing "
            "edge to or from them and writes none."
        ),
        "",
        *(f"- {_name(analysis, bead)}" for bead in others),
        "",
    ]
    if analysis.standing is not None:
        lines += [
            f"Standing edges to or from them, which `--apply` removes: {len(touching)}.",
            "",
            *_listed(analysis, touching),
            "",
        ]
    lines += [
        (
            f"Shared items whose recorded driver is an Epic of another release, so they are unjudged for "
            f"`{analysis.release}`: {len(analysis.foreign)}."
        ),
        "",
        *(f"- {label(analysis, item)}" for item in analysis.foreign),
        "",
    ]
    return lines


def _dropped_line(analysis: Analysis, dropped: Dropped) -> str:
    waiter, driver = dropped.pair[1], dropped.pair[0]
    made: str = "only items judged `shared`" if dropped.shared_only else "at least one `owns` item"
    every: str = "; ".join(label(analysis, item) for item in dropped.items)
    return (
        f"- {_name(analysis, waiter)} no longer waits for {_name(analysis, driver)}: made by {made}, "
        f"{len(dropped.items)} item(s): {every}"
    )


def _dropped(analysis: Analysis) -> list[str]:
    if not analysis.order.dropped:
        return ["No edge closed a loop, so none was dropped.", ""]
    return [
        (
            "Each edge below lay inside a loop and was dropped, in this order: an edge that only items judged "
            "`shared` made goes before one an `owns` item made, and within each the edge made by the fewest "
            "items goes first, a tie to the lower bead id."
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
        return f"- **Yes**: {who}, directly — {_items(analysis, check.direct)}."
    via: str = " → ".join(_title(analysis, bead) for bead in check.path)
    return f"- **Yes**: {who}, through {via}."


def _checks(analysis: Analysis) -> list[str]:
    if not analysis.checks:
        return []
    return ["## Spot-checks", "", *(_check_line(analysis, check) for check in analysis.checks), ""]


def _driver_table(analysis: Analysis) -> list[str]:
    made: dict[EntryId, int] = edges_made(analysis)
    decided: list[SharedItem] = sorted(deciding(analysis.items.values()), key=lambda i: (-made.get(i.id, 0), i.id))
    rows: list[str] = []
    for item in decided:
        if item.decision is None:
            continue
        rows.append(
            f"{_cell(label(analysis, item.id))} | {item.kind} | {_name(analysis, item.decision.driver)} | "
            f"{item.decision.basis} | {item.decision.source} | {_cell(item.decision.reason)} | "
            f"{len(item.needs)} | {made.get(item.id, 0)}",
        )
    return [
        f"## Shared items with a driver ({len(rows)})",
        "",
        (
            "Each unapproved shared item a record decides: the Epic that goes first (the driver), the basis "
            "(`owns`: the driver builds and owns it and the others use it; `shared`: the Epics share it "
            "independently and the driver merely goes first), where the record is (`judged`: a `drives` with a "
            "basis to the item; `owner-stack`: the owner's `drives` to the stack it is realized or homed in), "
            "the reason, the Epics that need it, and the edges it makes after the loop break."
        ),
        "",
        "Item | Kind | Driver | Basis | Record | Reason | Epics that need it | Edges it makes",
        "--- | --- | --- | --- | --- | --- | --- | ---",
        *rows,
        "",
    ]


def _unjudged(analysis: Analysis) -> list[str]:
    open_items: list[SharedItem] = sorted(unjudged(analysis.items.values()), key=lambda i: (-len(i.needs), i.id))
    if not open_items:
        return ["## Unjudged shared items (0)", "", "Every unapproved shared item is decided.", ""]
    rows: list[str] = [
        f"{_cell(label(analysis, item.id))} | {item.kind} | {len(item.needs)} | "
        + ", ".join(_title(analysis, bead) for bead in item.needs)
        for item in open_items
    ]
    return [
        f"## Unjudged shared items ({len(open_items)})",
        "",
        (
            "Each unapproved shared item no record decides makes no edge until a judgment is recorded "
            "(`atw-matrix shared-items --batches`, then `atw-matrix record-judgments`)."
        ),
        "",
        *_details(
            "Unjudged items",
            ["Item | Kind | Epics | Epics that need it", "--- | --- | --- | ---", *rows],
        ),
    ]


def _summary(analysis: Analysis) -> str:
    sizes: list[int] = _sizes(analysis)
    shared: int = len(analysis.items)
    approved: int = sum(1 for item in analysis.items.values() if item.approved)
    in_advance: int = sum(1 for item in analysis.items.values() if not item.approved and item.in_advance)
    decided: int = len(deciding(analysis.items.values()))
    return (
        f"Release `{analysis.release}` has {len(analysis.epics)} Epics in the matrix ({len(analysis.others)} "
        f"Epics of other releases take no part) and {shared} shared items (features and architecture "
        f"entries two or more of its Epics need); {approved} have approved architecture, {in_advance} are realized or "
        f"homed in a stack deployed in advance, {decided} have a driver recorded in the matrix and "
        f"{len(unjudged(analysis.items.values()))} are unjudged. After the loop break {len(edges_made(analysis))} "
        f"items order Epics: every other Epic that needs one waits for its driver; nothing is inferred from "
        f"counts or names, and no WSJF or other ranking enters any edge. **{sizes[0]}** Epics can start now, at "
        f"most **{max(sizes)}** can be architected side by side in one level, and the longest chain is "
        f"**{len(analysis.order.chain)}** Epics across {len(sizes)} levels; {len(analysis.order.dropped)} edge(s) "
        "were dropped to break loops. The report writes nothing to beads."
    )


def _method() -> list[str]:
    return [
        "## How the order was computed",
        "",
        (
            "An Epic has requirements; requirements are served by features; features are realized by "
            "architecture entries (services, components, infrastructure, events, stacks, packages, layers), "
            "which depend on other entries. No Epic relates directly to another Epic. An edge exists so that an "
            "Epic waits for the Epic that builds and owns something it uses, and so that two Epics never work "
            "on the same unapproved shared item at the same time. The Epics and every record below are read "
            "from the matrix only."
        ),
        "",
        (
            "1. **A shared item** is a feature that serves a requirement of two or more Epics, or an "
            "architecture entry two or more Epics reach by the rule of reach (a serving feature's realizer, the "
            "stack it is or is homed in, or the far end of one dependency from either), whatever its repository "
            "or name."
        ),
        (
            "2. **Approved items make no edge.** A feature's architecture is approved when it is `realizedBy` at "
            "least one architecture-side entry and each carries the `approved` mark; an entry's, when it carries "
            "the mark."
        ),
        (
            "3. **A recorded judgment names the driver.** An architecture-side `drives` from Epic F to the item, "
            "with `basis` `owns` (F builds and owns it; the others use it) or `shared` (the Epics share it "
            "independently; F merely goes first) and a reason, made from the Epics' requirements. The owner's "
            "records stay in force: a `drives` with no basis from F to a stack makes F the owner of every "
            "shared item realized or homed in that stack, and `epicDriver: none` on a stack means its items "
            "make no edge, because the stack is deployed in advance."
        ),
        (
            "4. **Every other Epic that needs the item waits for the driver.** The edges several items make "
            "between one pair are one edge. An item with no record makes no edge and is listed as unjudged."
        ),
        (
            "5. **Loops are broken.** While the edges hold a loop, one edge inside a loop is dropped: first an "
            "edge that only `shared` items made, then one an `owns` item made, each time the edge made by the "
            "fewest items, a tie to the lower bead id; every dropped edge is listed below. The rest is "
            "transitively reduced."
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
        *_other_releases(analysis),
        *_driver_table(analysis),
        *_unjudged(analysis),
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
        "Each line names the shared items both Epics need whose driver is the Epic waited for.",
        "",
        *(_edge_line(analysis, pair, items) for pair, items in analysis.order.edges.items()),
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"
