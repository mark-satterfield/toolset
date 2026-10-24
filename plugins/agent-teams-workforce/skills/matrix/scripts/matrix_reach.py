"""Answer the three transitive questions of the matrix that one ``atw-matrix`` read does not.

``atw-matrix node`` and ``atw-matrix impact`` show only an entry's direct relationships, so an
Epic that reaches a service through requirement -> document heading -> service never appears
there. This script walks every Epic in one process over one read of the file and prints a compact
answer:

- ``epics-reaching <id>``: the Epics that reach the entry, with how.
- ``epic-needs <beads id>``: the services, components, infrastructure, stacks and repositories an
  Epic reaches, and its gaps.
- ``unreached --kinds <kinds>``: the entries of those kinds (and ``repository``) no Epic reaches.

The rule of reach is ``matrixtraverse.rule_reach``, the one walk the approval scope, the
architecture pack and the check use: an Epic reaches an entry when a feature serving one of its
requirements is ``realizedBy`` the entry. It reaches a stack when an entry so reached is the stack
or has its home in it (``homeIn``, the architecture side's, else the repository side's). It reaches
the direct far end of each dependency that starts at such an entry or stack, one hop. Document
headings and the dependency family beyond one hop are not followed: both make every Epic reach
every service.

It reads the matrix the same way ``atw-matrix`` does (``--matrix``, else ``ATW_MATRIX``, else
``ATW_CONTROL_REPO``) and changes nothing. ``--json`` prints one JSON object instead of text.
Run it through the ``matrix-reach`` wrapper beside it, which supplies the interpreter and the
packages the plugin's matrix modules import.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "portfolio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    AUTHORITY_SIDE,
    KIND_COMPONENT,
    KIND_EPIC,
    KIND_INFRASTRUCTURE,
    KIND_SERVICE,
    KIND_STACK,
    EntryId,
    EntryKind,
    entry_kind,
)
from matrixquery import epic_view
from matrixstore import Matrix, matrix_path, read_matrix
from matrixtraverse import RuleReach, epic_id, rule_reach, stacks_of

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

REPOSITORY: Final = "repository"
"""The pseudo-kind ``unreached`` accepts for the repositories stacks name."""
REALIZER_KINDS: Final[tuple[EntryKind, ...]] = (KIND_SERVICE, KIND_COMPONENT, KIND_INFRASTRUCTURE)
HOMED_KINDS: Final[frozenset[EntryKind]] = frozenset(REALIZER_KINDS)
EPIC_PREFIX: Final = f"{KIND_EPIC}:"

type Json = dict[str, Any]


def _bead(epic: EntryId) -> str:
    """Name the beads id an Epic entry id holds.

    Returns:
        The id without its ``epic:`` prefix.

    """
    return epic.removeprefix(EPIC_PREFIX)


def _text(value: object) -> str:
    """Read a string attribute.

    Returns:
        The value, or an empty string when it is not a string.

    """
    return value if isinstance(value, str) else ""


def _all_reaches(matrix: Matrix) -> dict[EntryId, RuleReach]:
    """Walk every Epic once by the rule of reach.

    Returns:
        Each Epic with what it reaches.

    """
    return {epic.id: rule_reach(matrix, epic.id) for epic in matrix.entries((KIND_EPIC,))}


def epics_reaching(matrix: Matrix, target: EntryId) -> Json:
    """List the Epics that reach an entry.

    Returns:
        The entry and each Epic that reaches it, with how: the features whose ``realizedBy`` reaches an
        entry, the reached entries that place a stack, or the dependencies that reach it one hop
        from a reached entry or stack.

    """
    matrix.entry(target)
    epics: list[Json] = []
    for epic, reach in _all_reaches(matrix).items():
        via: set[str] = (
            set(reach.entries.get(target, frozenset()))
            | set(reach.stacks.get(target, frozenset()))
            | set(reach.dependencies.get(target, frozenset()))
        )
        if via:
            epics.append({"epic": _bead(epic), "via": sorted(via)})
    return {"id": target, "epics": epics}


def _repository(matrix: Matrix, stack: EntryId) -> str:
    """Read the repository a stack names.

    Returns:
        The repository, or an empty string while none holds the stack.

    """
    return _text(matrix.entry(stack).attributes.get(REPOSITORY))


def _requirement_gaps(matrix: Matrix, reach: RuleReach) -> tuple[list[EntryId], list[Json]]:
    """Find the requirements that reach no stack, or reach stacks no repository holds.

    Returns:
        The requirements that reach entries but no stack, and each requirement with the stacks it
        reaches that name no repository.

    """
    no_stack: list[EntryId] = []
    no_repository: list[Json] = []
    for requirement, entries in sorted(reach.requirements.items()):
        if not entries:
            continue
        stacks: set[EntryId] = {stack for entry in entries for stack in stacks_of(matrix, entry)}
        if not stacks:
            no_stack.append(requirement)
            continue
        homeless: list[EntryId] = sorted(stack for stack in stacks if not _repository(matrix, stack))
        if homeless:
            no_repository.append({"requirement": requirement, "stacks": homeless})
    return no_stack, no_repository


def epic_needs(matrix: Matrix, bead: str) -> Json:
    """Report what an Epic reaches and where its chain breaks.

    Returns:
        The realizers, stacks and repositories the Epic reaches, the far ends of the dependencies
        it reaches one hop from them, and its gaps.

    """
    reach: RuleReach = rule_reach(matrix, epic_id(bead))
    view: Mapping[str, object] = epic_view(matrix, bead)
    realizers: dict[str, list[Json]] = {kind: [] for kind in REALIZER_KINDS}
    for entry in sorted(reach.entries):
        kind: EntryKind = matrix.entry(entry).kind
        if kind in realizers:
            stacks: list[EntryId] = sorted(stacks_of(matrix, entry))
            realizers[kind].append({"id": entry, "stack": ", ".join(stacks)})
    stacks_held: list[Json] = [
        {"id": stack, "repository": _repository(matrix, stack)} for stack in sorted(reach.stacks)
    ]
    no_stack, no_repository = _requirement_gaps(matrix, reach)
    return {
        "epic": bead,
        "prd": view["prd"],
        **{f"{kind}s": realizers[kind] for kind in REALIZER_KINDS},
        "stacks": stacks_held,
        "repositories": sorted({str(stack["repository"]) for stack in stacks_held} - {""}),
        "dependencies": [{"id": entry, "via": sorted(how)} for entry, how in sorted(reach.dependencies.items())],
        "gaps": {
            "noFeature": view["noFeature"],
            "noDocument": view["noDocument"],
            "requirementsReachNothing": sorted(
                requirement for requirement, found in reach.requirements.items() if not found
            ),
            "requirementsNoStack": no_stack,
            "requirementsNoRepository": no_repository,
            "entriesNoStack": sorted(
                entry
                for entry in reach.entries
                if matrix.entry(entry).kind in HOMED_KINDS
                and matrix.entry(entry).side == AUTHORITY_SIDE
                and not stacks_of(matrix, entry)
            ),
            "stacksNoRepository": [stack["id"] for stack in stacks_held if not stack["repository"]],
        },
    }


def unreached(matrix: Matrix, kinds: Sequence[str]) -> Json:
    """List the entries of some kinds, and the repositories, that no Epic reaches.

    Returns:
        For each kind asked for, the ids (or repository names) no Epic reaches.

    """
    reached: set[EntryId] = set()
    for reach in _all_reaches(matrix).values():
        reached.update(reach.ids())
    result: dict[str, list[str]] = {}
    for kind in kinds:
        if kind == REPOSITORY:
            held: set[str] = {_repository(matrix, stack.id) for stack in matrix.entries((KIND_STACK,))}
            used: set[str] = {_repository(matrix, entry) for entry in reached if matrix.entry(entry).kind == KIND_STACK}
            result[REPOSITORY] = sorted(held - used - {""})
            continue
        result[kind] = sorted(entry.id for entry in matrix.entries((entry_kind(kind),)) if entry.id not in reached)
    return {"unreached": result}


def _lines_reaching(result: Json) -> Iterable[str]:
    """Render ``epics-reaching`` as one line per Epic.

    Yields:
        A header line, then one line per Epic.

    """
    epics: list[Json] = result["epics"]
    yield f"{result['id']}: {len(epics)} Epic(s)"
    for item in epics:
        yield f"{item['epic']}  via {'; '.join(item['via'])}"


def _lines_needs(result: Json, *, full: bool = False) -> Iterable[str]:
    """Render ``epic-needs`` as short sections of ids.

    Yields:
        One line per heading and per id.

    """
    yield f"epic {result['epic']}  prd {result['prd']}"
    for key in ("services", "components", "infrastructures"):
        items: list[Json] = result[key]
        if key != "services" and not full:
            yield f"{key} ({len(items)}): --full or --json lists them"
            continue
        yield f"{key} ({len(items)}):"
        yield from (f"  {item['id']}  [{item['stack'] or 'NO STACK'}]" for item in items)
    stacks: list[Json] = result["stacks"]
    yield f"stacks ({len(stacks)}):"
    yield from (f"  {item['id']}  [{item['repository'] or 'NO REPOSITORY'}]" for item in stacks)
    yield f"repositories ({len(result['repositories'])}): {' '.join(result['repositories'])}"
    dependencies: list[Json] = result["dependencies"]
    if not full:
        yield f"dependencies ({len(dependencies)}): --full or --json lists them"
    else:
        yield f"dependencies ({len(dependencies)}):"
        yield from (f"  {item['id']}  via {'; '.join(item['via'])}" for item in dependencies)
    gaps: Mapping[str, list[Any]] = result["gaps"]
    for name, items in gaps.items():
        yield f"gap {name} ({len(items)}):"
        yield from (f"  {_gap(item)}" for item in items)


def _gap(item: object) -> str:
    """Render one gap as one line.

    Returns:
        The id, or the values of a gap object joined by spaces.

    """
    if not isinstance(item, dict):
        return str(item)
    return "  ".join(", ".join(value) if isinstance(value, list) else str(value) for value in item.values())


def _lines_unreached(result: Json) -> Iterable[str]:
    """Render ``unreached`` as one section per kind.

    Yields:
        One line per kind and per id.

    """
    found: Mapping[str, list[str]] = result["unreached"]
    for kind, ids in found.items():
        yield f"{kind} ({len(ids)}):"
        yield from (f"  {item}" for item in ids)


def _parser() -> argparse.ArgumentParser:
    """Build the command line.

    Returns:
        The parser.

    """
    parser = argparse.ArgumentParser(prog="matrix-reach", description=__doc__.splitlines()[0])
    parser.add_argument("--matrix", default=None, help="the matrix file; default: as atw-matrix decides")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of text")
    sub = parser.add_subparsers(dest="command", required=True)
    reaching = sub.add_parser("epics-reaching", help="the Epics that reach an entry by the rule of reach")
    reaching.add_argument("id")
    needs = sub.add_parser("epic-needs", help="what an Epic reaches, and its gaps")
    needs.add_argument("epic")
    needs.add_argument("--full", action="store_true", help="list the components and infrastructure too")
    unreached_parser = sub.add_parser("unreached", help="entries of some kinds no Epic reaches")
    unreached_parser.add_argument(
        "--kinds",
        default="service,stack,repository",
        help="kinds separated by commas; repository is the repositories stacks name; default: %(default)s",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one query and print its answer.

    Returns:
        The exit status.

    """
    args: argparse.Namespace = _parser().parse_args(argv)
    matrix: Matrix = read_matrix(matrix_path(args.matrix, os.environ))
    handlers: dict[str, tuple[Callable[[], Json], Callable[[Json], Iterable[str]]]] = {
        "epics-reaching": (lambda: epics_reaching(matrix, EntryId(args.id)), _lines_reaching),
        "epic-needs": (
            lambda: epic_needs(matrix, args.epic),
            lambda result: _lines_needs(result, full=args.full),
        ),
        "unreached": (
            lambda: unreached(matrix, [kind.strip() for kind in args.kinds.split(",") if kind.strip()]),
            _lines_unreached,
        ),
    }
    answer, render = handlers[args.command]
    result: Json = answer()
    text: str = json.dumps(result) if args.json else "\n".join(render(result))
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
