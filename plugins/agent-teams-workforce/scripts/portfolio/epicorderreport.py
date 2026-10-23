"""Render ``epicorder.py``'s analysis as the Markdown report the owner reads.

Epic titles lead everywhere; bead ids follow in parentheses only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from epicorder import Analysis, Order, Pair, Unit

TOP: Final = 10
LISTED: Final = 5


def _name(analysis: Analysis, bead: str) -> str:
    return f"{analysis.epics[bead].title} ({bead})"


def _sizes(result: Order) -> list[int]:
    values: list[int] = list(result.levels.values())
    return [values.count(level) for level in range(1, max(values) + 1)]


def _starts(analysis: Analysis, result: Order) -> list[str]:
    return sorted((bead for bead, level in result.levels.items() if level == 1), key=lambda b: analysis.epics[b].title)


def _edge_line(analysis: Analysis, pair: Pair, units: tuple[Unit, ...]) -> str:
    more: str = f" (+{len(units) - 1} more)" if len(units) > 1 else ""
    return f"- {_name(analysis, pair[1])} waits for {_name(analysis, pair[0])} — `{units[0]}`{more}"


def _shape(analysis: Analysis, result: Order) -> list[str]:
    sizes: list[int] = _sizes(result)
    starts: list[str] = _starts(analysis, result)
    lines: list[str] = [
        (
            f"- Edges after cycle breaking and transitive reduction: {len(result.edges)} "
            f"(before: {len(result.raw)}; entries excluded: {result.excluded})."
        ),
        f"- Can start immediately: **{len(starts)}** Epics.",
        f"- Levels: {len(sizes)}; maximum concurrency: **{max(sizes)}** Epics in one level.",
        f"- Epics per level: {', '.join(f'L{n}={size}' for n, size in enumerate(sizes, start=1))}.",
        f"- Longest chain ({len(result.chain)} Epics): "
        + " → ".join(analysis.epics[bead].title for bead in result.chain)
        + ".",
    ]
    return lines


def _top(analysis: Analysis, result: Order) -> list[str]:
    ranked: list[str] = sorted(analysis.epics, key=lambda b: (-result.unlocks[b], analysis.epics[b].title))[:TOP]
    return [f"{n}. {_name(analysis, bead)} — unlocks {result.unlocks[bead]}" for n, bead in enumerate(ranked, start=1)]


def _diff(analysis: Analysis, result: Order) -> list[str]:
    proposed: set[Pair] = set(result.edges)
    current: Mapping[Pair, bool] = analysis.current
    added: list[Pair] = sorted(proposed - set(current))
    removed: list[Pair] = sorted(set(current) - proposed)
    kept: list[Pair] = sorted(proposed & set(current))
    hand: int = sum(1 for pair in removed if not current[pair])

    def listed(pairs: Iterable[Pair]) -> list[str]:
        return [f"  - {_name(analysis, b)} waits for {_name(analysis, a)}" for a, b in pairs]

    return [
        (
            f"- Added: {len(added)}; removed: {len(removed)}; kept: {len(kept)} "
            f"(current `tracks` edges between open Epics: {len(current)})."
        ),
        f"- {hand} of the removed edges were made by hand (not owned by the pipeline); `--apply` keeps them.",
        "",
        "<details><summary>Added</summary>",
        "",
        *listed(added),
        "",
        "</details>",
        "",
        "<details><summary>Removed</summary>",
        "",
        *listed(removed),
        "",
        "</details>",
        "",
        "<details><summary>Kept</summary>",
        "",
        *listed(kept),
        "",
        "</details>",
    ]


def _cycles(analysis: Analysis, result: Order) -> list[str]:
    if not result.cycles:
        return ["No cycles."]
    lines: list[str] = []
    for n, cycle in enumerate(result.cycles, start=1):
        lines.append(f"**Cycle {n}** ({len(cycle.members)} Epics, {len(cycle.edges)} edges inside):")
        lines.extend(f"- member: {_name(analysis, bead)}" for bead in cycle.members)
        lines.extend(
            f"- broken: {_name(analysis, pair[1])} no longer waits for {_name(analysis, pair[0])} "
            f"(lower WSJF rank) — created by `{'`, `'.join(cycle.edges[pair][:LISTED])}`"
            + (f" (+{len(cycle.edges[pair]) - LISTED} more)" if len(cycle.edges[pair]) > LISTED else "")
            for pair in cycle.dropped
        )
        lines.append("")
    return lines


def _scenario(analysis: Analysis, title: str, result: Order, lean: Order) -> list[str]:
    starts: list[str] = _starts(analysis, result)
    return [
        f"## {title}",
        "",
        *_shape(analysis, result),
        "",
        "### Epics that can start now",
        "",
        *(f"- {_name(analysis, bead)}" for bead in starts),
        "",
        "### Without the over-broad entries",
        "",
        *_shape(analysis, lean),
        "",
        "<details><summary>Epics that can start now without the over-broad entries</summary>",
        "",
        *(f"- {_name(analysis, bead)}" for bead in _starts(analysis, lean)),
        "",
        "</details>",
        "",
        "### Top 10 Epics by how many Epics they unlock (transitively)",
        "",
        *_top(analysis, result),
        "",
        "### Cycles and breaks",
        "",
        *_cycles(analysis, result),
        "",
        "### Diff against the current beads `tracks` edges",
        "",
        *_diff(analysis, result),
        "",
        f"### Every edge ({len(result.edges)})",
        "",
        "Each line names one deciding entry; `(+N more)` counts the other entries that make the same edge.",
        "",
        *(_edge_line(analysis, pair, units) for pair, units in result.edges.items()),
        "",
    ]


def _summary(analysis: Analysis) -> str:
    a, a_lean, b, b_lean = analysis.orders
    a_sizes, b_sizes = _sizes(a), _sizes(b)
    tight: tuple[int, Order] = analysis.sensitivity[1]
    return (
        f"There are {len(analysis.epics)} open Epics. Computed deterministically from the matrix and beads "
        f"(no model calls), with no entry approved yet (scenario A), {a_sizes[0]} Epics can start "
        f"immediately, at most {max(a_sizes)} can be architected side by side in one level, and the longest "
        f"chain is {len(a.chain)} Epics long across {len(a_sizes)} levels. If everything in the `shared-*` "
        f"stacks (including the central event API and bus) were pre-architected and approved (scenario B), "
        f"{b_sizes[0]} Epics could start immediately, maximum concurrency would be {max(b_sizes)}, and the "
        f"longest chain {len(b.chain)} Epics. {len(analysis.broad)} entries are touched by more than "
        f"{analysis.broad_share:.0%} of the Epics and look like matrix-precision problems; without them, A "
        f"starts {_sizes(a_lean)[0]} Epics at once with a longest chain of {len(a_lean.chain)}, and B starts "
        f"{_sizes(b_lean)[0]} with a longest chain of {len(b_lean.chain)}. The chains are long because the "
        f"matrix ties {max((len(c.members) for c in a.cycles), default=0)} Epics into one cycle of mutual "
        f"waiting, and breaking it by WSJF leaves a near WSJF-sorted sequence; kept to entries touched by at "
        f"most {tight[0]} Epics, A starts {_sizes(tight[1])[0]} Epics at once with a longest chain of "
        f'{len(tight[1].chain)} (see "Why the chains are long"). Nothing has been written to beads; the '
        f"current beads `tracks` edges hold {len(analysis.current)} edges between open Epics."
    )


def _broad(analysis: Analysis) -> list[str]:
    rows: list[str] = [
        f"`{d.unit}` | {len(d.epics)} | {_name(analysis, d.driver)} ({d.rule})"
        for d in sorted(analysis.broad, key=lambda d: (-len(d.epics), d.unit))
    ]
    return [
        "## Over-broad entries",
        "",
        (
            f"Entries touched by more than {analysis.broad_share:.0%} of the open Epics. Each one makes its driver "
            "a gate for most of the portfolio, which usually means the matrix links it too widely (a broad document "
            "heading, a shared library every stack imports). They are not trusted silently: each scenario is shown "
            "with and without them."
        ),
        "",
        "Entry | Epics touching | Driver (rule)",
        "--- | --- | ---",
        *rows,
        "",
    ]


def _method(analysis: Analysis) -> list[str]:
    rules: dict[str, int] = {}
    for decision in analysis.decisions:
        rules[decision.rule] = rules.get(decision.rule, 0) + 1
    valid: str = "; ".join(f"{name}: {'no' if bad else 'yes'}" for name, bad in analysis.validation.items())
    lines: list[str] = [
        "## How the order was computed",
        "",
        (
            "- An Epic touches an architecture entry when the matrix's rule of reach reaches it (its features, "
            "the entries its covering document headings describe, their stacks, one dependency hop), when a "
            "document heading covers one of its requirements, or through its `drives` and `restsOn` relationships."
        ),
        (
            "- Each entry has ONE driver: an explicit `drives` relationship first, else an Epic whose requirements "
            "the entry's defining heading covers, else every touching Epic; ties go to the highest WSJF, then the "
            "bead id (the keeper's selection order). Every other touching Epic waits for the driver. Two users of "
            "one entry get no edge between them."
        ),
        "- An entry with the matrix `approved` flag makes no edge (none carries it today).",
        (
            "- Cycles are broken by the same rank: inside a cycle, an edge from a lower-ranked to a "
            "higher-ranked Epic is dropped. Then A → C is dropped wherever A → … → C exists."
        ),
        (
            f"- Entries judged: {len(analysis.decisions)} "
            f"({', '.join(f'{rule}: {count}' for rule, count in sorted(rules.items()))})."
        ),
        f"- `apply-edges` would accept each variant's edges: {valid}.",
    ]
    if analysis.missing:
        lines.append(
            "- Open Epics the matrix does not hold (no edges computed for them): "
            + ", ".join(_name(analysis, bead) for bead in analysis.missing)
            + ".",
        )
    return [*lines, ""]


def _refused(analysis: Analysis) -> list[str]:
    lines: list[str] = []
    for name, cycle in analysis.validation.items():
        if not cycle:
            continue
        path: str = " → ".join(analysis.epics[bead].title if bead in analysis.epics else bead for bead in cycle)
        lines.append(f"- {name}: refused; with the hand-made `tracks` edges `--apply` keeps, it would close: {path}.")
    return lines


def _why(analysis: Analysis) -> list[str]:
    a: Order = analysis.orders[0]
    by_unit = {d.unit: d for d in analysis.decisions}
    rules: dict[str, int] = {}
    for units in a.raw.values():
        rule: str = by_unit[units[0]].rule
        rules[rule] = rules.get(rule, 0) + 1

    def wsjf(bead: str) -> float:
        return analysis.epics[bead].wsjf or 0.0

    down: int = sum(1 for start, end in a.raw if wsjf(start) > wsjf(end))
    biggest: int = max((len(cycle.members) for cycle in a.cycles), default=0)
    links: dict[str, int] = {}
    for start, end in zip(a.chain, a.chain[1:], strict=False):
        rule = by_unit[a.edges[start, end][0]].rule
        links[rule] = links.get(rule, 0) + 1
    rows: list[str] = []
    for limit, result in analysis.sensitivity:
        sizes: list[int] = _sizes(result)
        biggest_cycle: int = max((len(cycle.members) for cycle in result.cycles), default=0)
        rows.append(
            f"{limit} | {len(result.edges)} | {sizes[0]} | {max(sizes)} | {len(result.chain)} | {biggest_cycle}",
        )
    return [
        "## Why the chains are long",
        "",
        (
            f"- Scenario A draws {len(a.raw)} driver → user edges before reduction "
            f"({', '.join(f'{rule}: {count}' for rule, count in sorted(rules.items()))}, by the rule that chose the "
            f"first deciding entry). {down} of them run from a higher-WSJF to a lower-WSJF Epic, because the "
            "tie-break among the Epics a heading covers is WSJF."
        ),
        (
            f"- Those edges tie {biggest} Epics into one cycle: each of them waits, through some chain, for each of "
            "the others. Breaking it by WSJF keeps every edge inside it that agrees with the WSJF order, so the "
            "cycle comes out close to a WSJF-sorted sequence. That is what makes the longest chain long, not a "
            "real need for each Epic to wait for the one before it."
        ),
        f"- The longest chain's links are decided by: {', '.join(f'{r}: {n}' for r, n in sorted(links.items()))}.",
        (
            "- `--apply` (the `apply-edges` path) would accept each variant's edges only if they close no cycle "
            "with the hand-made edges it never removes:"
        ),
        *_refused(analysis),
        "",
        "Scenario A kept to the entries touched by at most N Epics (precise entries only):",
        "",
        "N | Edges | Start now | Max concurrency | Longest chain | Largest cycle",
        "--- | --- | --- | --- | --- | ---",
        *rows,
        "",
    ]


def render(analysis: Analysis) -> str:
    """Render the whole report.

    Returns:
        The Markdown text.

    """
    a, a_lean, b, b_lean = analysis.orders
    lines: list[str] = [
        "# Epic architecture order",
        "",
        _summary(analysis),
        "",
        *_method(analysis),
        *_broad(analysis),
        *_why(analysis),
        *_scenario(analysis, "Scenario A: as things stand (no entry approved)", a, a_lean),
        *_scenario(analysis, "Scenario B: every `shared-*` entry pre-approved", b, b_lean),
    ]
    return "\n".join(lines).rstrip() + "\n"
