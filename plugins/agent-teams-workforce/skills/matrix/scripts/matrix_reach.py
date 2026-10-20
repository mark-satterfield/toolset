"""Answer the three transitive questions of the matrix that one ``atw-matrix`` read does not.

``atw-matrix node`` and ``atw-matrix impact`` show only an entry's direct relationships, so an
Epic that reaches a service through requirement -> feature -> document -> service never appears
there. This script walks every Epic with the walk ``atw-matrix epic --closure`` makes
(``matrixtraverse.epic_reach``), in one process over one read of the file, and prints a compact
answer:

- ``epics-reaching <id>``: the Epics whose walk reaches the entry, with the features that lead
  to it.
- ``epic-needs <beads id>``: the services, components, infrastructure, stacks and repositories an
  Epic reaches, and its gaps: requirements with no feature, no covering document, no stack or no
  repository.
- ``unreached --kinds <kinds>``: the entries of those kinds (and ``repository``) no Epic reaches.

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
    KIND_COMPONENT,
    KIND_EPIC,
    KIND_INFRASTRUCTURE,
    KIND_SERVICE,
    KIND_STACK,
    REL_HOME_IN,
    Entry,
    EntryId,
    EntryKind,
    entry_kind,
)
from matrixquery import epic_view
from matrixstore import Matrix, matrix_path, read_matrix
from matrixtraverse import Dependency, EpicReach, epic_id, epic_reach

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

REPOSITORY: Final = "repository"
"""The pseudo-kind ``unreached`` accepts for the repositories stacks name."""
REALIZER_KINDS: Final[tuple[EntryKind, ...]] = (KIND_SERVICE, KIND_COMPONENT, KIND_INFRASTRUCTURE)
EPIC_PREFIX: Final = f"{KIND_EPIC}:"
DEPENDENCY: Final = "dependency"
"""How an Epic reaches an entry only through the dependencies of the stacks it reaches."""

type Walked = dict[EntryId, tuple[Dependency, ...]]
type Json = dict[str, Any]


def _bead(epic: EntryId) -> str:
    """Name the beads id an Epic entry id holds.

    Returns:
        The id without its ``epic:`` prefix.

    """
    return epic.removeprefix(EPIC_PREFIX)


def _reached(reach: EpicReach) -> set[EntryId]:
    """Collect every entry an Epic's walk reaches.

    Returns:
        The entries ``EpicReach.entries`` lists, the Epic's requirements and the documents that
        describe its features.

    """
    found: set[EntryId] = set(reach.entries())
    found.update(reach.served)
    found.update(relationship.end for held in reach.documents.values() for relationship in held)
    return found


def _stack_of(matrix: Matrix, entry: EntryId) -> EntryId | None:
    """Find the stack an entry has its home in.

    Returns:
        The stack (the entry itself when it is a stack), or None while it has no home.

    """
    if matrix.entry(entry).kind == KIND_STACK:
        return entry
    homes: list[EntryId] = [relationship.end for relationship in matrix.outgoing(entry, (REL_HOME_IN,))]
    return homes[0] if homes else None


def _repository(matrix: Matrix, stack: EntryId) -> str:
    """Read the repository a stack names.

    Returns:
        The repository, or an empty string while none holds the stack.

    """
    value: object = matrix.entry(stack).attributes.get(REPOSITORY)
    return value if isinstance(value, str) else ""


def _via(reach: EpicReach, target: EntryId) -> list[str]:
    """Name how a walk reaches an entry.

    Returns:
        The features that lead to it, else the kind of link that found it.

    """
    features: set[str] = {way.feature for way in reach.ways.get(target, ())}
    features.update(reach.stacks.get(target, frozenset()))
    if features:
        return sorted(features)
    if target in reach.served:
        return ["hasRequirement"]
    if target in reach.features:
        return ["servedBy"]
    if any(dependency.far == target for dependency in reach.dependencies):
        return [DEPENDENCY]
    return ["describedBy"]


def epics_reaching(matrix: Matrix, target: EntryId, *, features_only: bool = False) -> Json:
    """List the Epics whose walk reaches an entry.

    ``features_only`` leaves out the Epics that reach it only through a stack dependency (for
    example every Epic whose service calls a shared service that calls it).

    Returns:
        The entry and each Epic that reaches it, with how.

    """
    matrix.entry(target)
    walked: Walked = {}
    epics: list[Json] = []
    epic: Entry
    for epic in matrix.entries((KIND_EPIC,)):
        reach: EpicReach = epic_reach(matrix, epic.id, walked)
        if target not in _reached(reach):
            continue
        via: list[str] = _via(reach, target)
        if not (features_only and via == [DEPENDENCY]):
            epics.append({"epic": _bead(epic.id), "via": via})
    return {"id": target, "epics": epics}


def _requirement_gaps(matrix: Matrix, reach: EpicReach) -> tuple[list[EntryId], list[Json]]:
    """Find the requirements whose features reach no stack, or reach stacks no repository holds.

    Returns:
        The requirements with no stack, and each requirement with the stacks it reaches that name
        no repository.

    """
    no_stack: list[EntryId] = []
    no_repository: list[Json] = []
    requirement: EntryId
    features: tuple[EntryId, ...]
    for requirement, features in reach.served.items():
        if not features:
            continue
        stacks: set[EntryId] = {stack for stack, leading in reach.stacks.items() if leading.intersection(features)}
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
        The realizers, stacks and repositories the Epic reaches, and its gaps.

    """
    reach: EpicReach = epic_reach(matrix, epic_id(bead))
    view: Mapping[str, object] = epic_view(matrix, bead)
    reached: set[EntryId] = _reached(reach)
    realizers: dict[str, list[Json]] = {kind: [] for kind in REALIZER_KINDS}
    entry: EntryId
    for entry in sorted(reached):
        kind: EntryKind = matrix.entry(entry).kind
        if kind in realizers:
            stack: EntryId | None = _stack_of(matrix, entry)
            realizers[kind].append({"id": entry, "stack": stack or ""})
    stacks: list[Json] = [{"id": stack, "repository": _repository(matrix, stack)} for stack in sorted(reach.stacks)]
    no_stack, no_repository = _requirement_gaps(matrix, reach)
    return {
        "epic": bead,
        "prd": view["prd"],
        **{f"{kind}s": realizers[kind] for kind in REALIZER_KINDS},
        "stacks": stacks,
        "repositories": sorted({str(stack["repository"]) for stack in stacks} - {""}),
        "gaps": {
            "noFeature": view["noFeature"],
            "noDocument": view["noDocument"],
            "requirementsNoStack": no_stack,
            "requirementsNoRepository": no_repository,
            "entriesNoStack": list(reach.no_stack),
            "stacksNoRepository": list(reach.no_repository),
        },
    }


def unreached(matrix: Matrix, kinds: Sequence[str]) -> Json:
    """List the entries of some kinds, and the repositories, that no Epic reaches.

    Returns:
        For each kind asked for, the ids (or repository names) no Epic's walk reaches.

    """
    walked: Walked = {}
    reached: set[EntryId] = set()
    epic: Entry
    for epic in matrix.entries((KIND_EPIC,)):
        reached.update(_reached(epic_reach(matrix, epic.id, walked)))
    result: dict[str, list[str]] = {}
    kind: str
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
        yield f"{item['epic']}  via {', '.join(item['via'])}"


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
    reaching = sub.add_parser("epics-reaching", help="the Epics that reach an entry, transitively")
    reaching.add_argument("id")
    reaching.add_argument(
        "--features-only",
        action="store_true",
        help="leave out Epics that reach it only by dependency",
    )
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
        "epics-reaching": (
            lambda: epics_reaching(matrix, EntryId(args.id), features_only=args.features_only),
            _lines_reaching,
        ),
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
