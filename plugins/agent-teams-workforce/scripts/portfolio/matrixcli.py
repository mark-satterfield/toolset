"""The sub-commands of ``atw-matrix`` that change the matrix, bring it up to date, seed it and mark it.

``matrix.py`` holds the reads and the command line; this module holds everything else: ``put``,
``link``, ``unlink``, ``settle``, ``rename``, ``remove``, ``move-repository`` and ``commit``;
``sync-epics``, ``sync-documents`` and ``sync-events``; ``seed`` and its steps (``seed-stacks``,
``seed-packages``, ``seed-inputs``, ``seed-features``, ``seed-apply``); ``verify`` and the Task
script's ``built``, ``work`` and ``affected``; ``check-reuse``. Each change is
one locked read-modify-write of the matrix file.

The attribute options of ``put``, ``link`` and ``unlink`` are not listed here: one option exists
per attribute the kinds registry declares, in the form the registry's type of that attribute
calls for (:func:`attribute_options`).
"""

import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, TypedDict, assert_never

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from driver_surface_types import ARCH_PATH_ENV, CONTROL_REPO_ENV, PRD_DIR_ENV
from matrix_contract import (
    ENTRY_KINDS,
    KIND_EVENT,
    REL_PUBLISHES,
    RELATIONSHIP_KINDS,
    SIDE_ARCHITECTURE,
    SIDES,
    EntryId,
    EntryKind,
    JsonValue,
    RelationshipKind,
    Side,
    entry_kind,
    load_registry,
    relationship_kind,
)
from matrixcall import Call, Outcome
from matrixcode import COMMAND_VERIFY, record_verified
from matrixevents import CATALOG_PATH, CatalogEvent, EventsSynced, read_catalog, sync_events
from matrixquery import approval_view, impact_view
from matrixreuse import check_reuse
from matrixseed import (
    MERGE_FILE,
    PROPOSAL_FOLDER,
    READING_ALLOWANCE,
    RESULT_FOLDER,
    SEED_STEPS,
    STEP_FEATURES,
    Applied,
    PackagesSeeded,
    Repository,
    SeedStep,
    StacksSeeded,
    as_step,
    list_proposed,
    read_repositories,
    repository_types,
    seed,
    seed_apply,
    seed_directory,
    seed_inputs,
    seed_packages,
    seed_stacks,
)
from matrixstore import (
    Matrix,
    MatrixRefusedError,
    read_matrix,
    remove_entry,
    rename_entry,
    role_of,
    update_matrix,
)
from matrixsync import DocumentsSynced, EpicBead, EpicsSynced, read_epics, sync_documents, sync_epics, vault_root
from matrixtasks import COMMAND_AFFECTED, COMMAND_BUILT, COMMAND_WORK, TaskBead, affected, built, read_tasks, work
from matrixwrite import (
    LinkResult,
    MoveResult,
    PutResult,
    SettleResult,
    UnlinkResult,
    commit,
    link,
    move_repository,
    put,
    settle,
    unlink,
)

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable, Mapping

type AttributeForm = Literal["text", "number", "many", "parts", "json"]
"""How an attribute is stated on the command line: one string, one whole number, several strings,
one string per member of a small object, or JSON."""
type AttributeTable = Literal["entryKinds", "relationshipKinds"]
"""The table of the kinds registry an attribute is declared in."""

FORM_TEXT: Final = "text"
FORM_NUMBER: Final = "number"
FORM_MANY: Final = "many"
FORM_PARTS: Final = "parts"
FORM_JSON: Final = "json"
ENTRY_TABLE: Final[AttributeTable] = "entryKinds"
RELATIONSHIP_TABLE: Final[AttributeTable] = "relationshipKinds"
STANDS_PARTS: Final = 2
"""How many values ``settle --stands`` takes: the document and the heading."""
CONTROL_VARIABLES: Final[tuple[str, ...]] = (CONTROL_REPO_ENV,)
COMMAND_APPROVAL: Final = "approval"
"""The attributes no command line states: the step that promotes reviewed architecture sets them."""
_CAMEL: Final[re.Pattern[str]] = re.compile(r"(?<=[a-z0-9])([A-Z])")


@dataclass(frozen=True, slots=True)
class AttributeOption:
    """How one attribute of an entry or a relationship is stated on the command line."""

    attribute: str
    form: AttributeForm
    parts: tuple[str, ...]
    """The members of an attribute stated one string per member; empty for every other form."""
    description: str


class Renamed(TypedDict):
    """What ``rename`` prints."""

    old: EntryId
    new: EntryId


class Removed(TypedDict):
    """What ``remove`` prints."""

    id: EntryId
    removed: list[EntryId]
    """The ids of the entries removed, the one named included."""


def _resolved(spec: JsonValue, definitions: Mapping[str, JsonValue]) -> dict[str, JsonValue] | None:
    """Follow a registry node to the definition it references.

    Returns:
        The referenced definition, the node itself when it references none, or None when the
        definition it references is not one the registry holds.

    Raises:
        TypeError: The node is not an object.

    """
    if not isinstance(spec, dict):
        message: str = "the kinds registry holds an attribute that is not an object"
        raise TypeError(message)
    pointer: JsonValue = spec.get("$ref")
    if not isinstance(pointer, str):
        return spec
    target: JsonValue = definitions.get(pointer.rpartition("/")[2])
    return target if isinstance(target, dict) else None


def _is_text(spec: Mapping[str, JsonValue] | None) -> bool:
    """Tell whether a registry node describes one string.

    Returns:
        True for a vocabulary, for a string, and for a reference to a definition the registry
        does not hold itself (an entry id, which is a string).

    """
    return spec is None or "enum" in spec or spec.get("type") == "string"


def _attribute_option(attribute: str, spec: JsonValue, definitions: Mapping[str, JsonValue]) -> AttributeOption:
    """Work out how one attribute is stated, from the registry's type of it.

    Returns:
        Text for a string or a vocabulary, a number for an integer, several strings for a list of
        strings, one string per member for a closed object of strings, and JSON for the rest.

    """
    described: JsonValue = spec.get("description") if isinstance(spec, dict) else None
    resolved: dict[str, JsonValue] | None = _resolved(spec, definitions)
    description: str = described.rstrip(".") if isinstance(described, str) else f"the {attribute} attribute"
    form: AttributeForm = FORM_JSON
    parts: tuple[str, ...] = ()
    if resolved is None or _is_text(resolved):
        form = FORM_TEXT
    elif resolved.get("type") == "integer":
        form = FORM_NUMBER
    elif resolved.get("type") == "array" and _is_text(_resolved(resolved.get("items"), definitions)):
        form = FORM_MANY
    else:
        members: JsonValue = resolved.get("properties")
        if isinstance(members, dict) and all(_is_text(_resolved(part, definitions)) for part in members.values()):
            form, parts = FORM_PARTS, tuple(members)
    return AttributeOption(attribute, form, parts, description)


@lru_cache(maxsize=2)
def attribute_options(table: AttributeTable) -> dict[str, AttributeOption]:
    """List how each attribute the kinds registry declares is given on the command line.

    Args:
        table: The registry table: the entry kinds for ``put``, the relationship kinds for
            ``link`` and ``unlink``.

    Returns:
        One entry per attribute any kind of the table declares, in registry order, except the
        attributes only a script step sets. An attribute two kinds declare is listed once, as
        the first of them declares it.

    Raises:
        TypeError: The registry does not hold the table, or a kind of it is not an object.

    """
    registry: dict[str, JsonValue] = load_registry()
    kinds: JsonValue = registry.get(table)
    definitions: JsonValue = registry.get("$defs")
    message: str
    if not isinstance(kinds, dict) or not isinstance(definitions, dict):
        message = f"the kinds registry does not hold {table} and its definitions"
        raise TypeError(message)
    options: dict[str, AttributeOption] = {}
    kind: str
    declared: JsonValue
    for kind, declared in kinds.items():
        attributes: JsonValue = declared.get("attributes") if isinstance(declared, dict) else None
        if not isinstance(attributes, dict):
            message = f"the kinds registry declares no attributes object for {kind}"
            raise TypeError(message)
        options.update({
            attribute: _attribute_option(attribute, spec, definitions)
            for attribute, spec in attributes.items()
            if attribute not in options
        })
    return options


def option_name(attribute: str) -> str:
    """Name the command-line option of an attribute.

    Returns:
        The attribute in lower case with a hyphen before each capital: ``resourceType`` gives
        ``resource-type``.

    """
    return _CAMEL.sub(r"-\1", attribute).lower()


def _destination(attribute: str) -> str:
    """Name the parsed argument of an attribute's option.

    Returns:
        The option name with underscores.

    """
    return option_name(attribute).replace("-", "_")


def _stated_attribute(call: Call, option: AttributeOption) -> JsonValue:
    """Read one attribute from the command line.

    Returns:
        The value stated, or None when the attribute was not stated. An attribute stated in
        parts holds the parts given.

    """
    name: str = _destination(option.attribute)
    if option.form == FORM_TEXT:
        return call.text(name)
    if option.form == FORM_NUMBER:
        return call.number(name)
    if option.form == FORM_MANY:
        many: list[JsonValue] = [*call.texts(name)]
        return many or None
    if option.form == FORM_JSON:
        return call.json(name)
    if option.form == FORM_PARTS:
        given: dict[str, JsonValue] = {}
        part: str
        for part in option.parts:
            value: str | None = call.text(f"{name}_{_destination(part)}")
            if value is not None:
                given[part] = value
        return given or None
    assert_never(option.form)


def _stated(call: Call, table: AttributeTable) -> dict[str, JsonValue]:
    """Read every attribute the command line states.

    Returns:
        Each stated attribute and its value.

    """
    stated: dict[str, JsonValue] = {}
    option: AttributeOption
    for option in attribute_options(table).values():
        value: JsonValue = _stated_attribute(call, option)
        if value is not None:
            stated[option.attribute] = value
    return stated


def _control(call: Call) -> Path:
    """Find the control repository a command cannot do without.

    A call that names none raises ``MatrixRefusedError`` from ``Call.required_folder``.

    Returns:
        The folder ``--control`` or the environment names.

    """
    return call.required_folder("control", CONTROL_VARIABLES)


def _run_put(call: Call) -> Outcome:
    """Run ``put``.

    Returns:
        The entry's id, whether it was created, what changed and the entry.

    An event the architecture side records names its publisher with ``--published-by``: the
    entry and its architecture-side ``publishes`` relationship are written in one change, so
    the event is never on the architecture side without the service or component that
    publishes it.

    Raises:
        MatrixRefusedError: ``--unset`` names an attribute the command line also states, or
            ``--published-by`` is given for another kind than an event or another side than
            the architecture side.

    """
    kind: EntryKind = entry_kind(call.required("kind"))
    side: Side = call.side()
    stated: dict[str, JsonValue] = _stated(call, ENTRY_TABLE)
    unset: list[str] = call.texts("unset")
    both: list[str] = sorted(set(unset) & set(stated))
    message: str
    if both:
        message = f"--unset names {', '.join(both)}, which the command line also states"
        raise MatrixRefusedError(message)
    published_by: EntryId | None = None if call.text("published_by") is None else call.entry("published_by")
    if published_by is not None and (kind != KIND_EVENT or side != SIDE_ARCHITECTURE):
        message = f"--published-by is stated only for an event the {SIDE_ARCHITECTURE} side records"
        raise MatrixRefusedError(message)
    attributes: dict[str, JsonValue] = {**stated, **dict.fromkeys(unset)}
    entry_id: EntryId | None = None if call.text("id") is None else call.entry("id")
    stack: EntryId | None = None if call.text("stack") is None else call.entry("stack")

    def change(matrix: Matrix) -> PutResult:
        result: PutResult = put(
            matrix,
            kind,
            side,
            entry_id=entry_id,
            name=call.text("name"),
            aliases=call.texts("aliases"),
            removed_aliases=call.texts("remove_aliases"),
            purpose=call.text("purpose"),
            attributes=attributes,
            stack=stack,
        )
        if published_by is not None:
            link(matrix, REL_PUBLISHES, published_by, result["id"], SIDE_ARCHITECTURE)
        return result

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_link(call: Call) -> Outcome:
    """Run ``link``.

    Returns:
        The relationship as the matrix now holds it, whether it was added and whether it changed.

    """
    kind: RelationshipKind = relationship_kind(call.required("kind"))
    start: EntryId = call.entry("source")
    end: EntryId = call.entry("to")
    side: Side = call.side()
    attributes: dict[str, JsonValue] = _stated(call, RELATIONSHIP_TABLE)

    def change(matrix: Matrix) -> LinkResult:
        return link(matrix, kind, start, end, side, attributes)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_unlink(call: Call) -> Outcome:
    """Run ``unlink``.

    Returns:
        The relationship removed, or the one asked about, and whether one was removed.

    """
    kind: RelationshipKind = relationship_kind(call.required("kind"))
    start: EntryId = call.entry("source")
    end: EntryId = call.entry("to")
    side: Side = call.side()
    attributes: dict[str, JsonValue] = _stated(call, RELATIONSHIP_TABLE)

    def change(matrix: Matrix) -> UnlinkResult:
        return unlink(matrix, kind, start, end, side, attributes)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_settle(call: Call) -> Outcome:
    """Run ``settle``.

    Returns:
        The disagreement's id, the statement that stands, the rule and the entry.

    Raises:
        MatrixRefusedError: ``--stands`` does not hold a document and a heading.

    """
    disagreement: EntryId = call.entry("id")
    stands: list[str] = call.texts("stands")
    if len(stands) != STANDS_PARTS:
        message: str = "--stands takes the document and the heading of the statement that stands"
        raise MatrixRefusedError(message)
    rule: str = call.required("rule")

    def change(matrix: Matrix) -> SettleResult:
        return settle(matrix, disagreement, stands[0], stands[1], rule, call.text("reason") or "")

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_rename(call: Call) -> Outcome:
    """Run ``rename``.

    Returns:
        The id the entry had and the id it has now.

    """
    renamed: Renamed = {"old": call.entry("source"), "new": call.entry("to")}
    rename_entry(call.matrix(), renamed["old"], renamed["new"], wait=call.lock_wait())
    return Outcome(renamed)


def _run_remove(call: Call) -> Outcome:
    """Run ``remove``.

    Returns:
        The id named and the ids of every entry removed.

    """
    entry_id: EntryId = call.entry("id")
    removed: Removed = {
        "id": entry_id,
        "removed": remove_entry(call.matrix(), entry_id, held=call.flag("held"), wait=call.lock_wait()),
    }
    return Outcome(removed)


def _run_move_repository(call: Call) -> Outcome:
    """Run ``move-repository``.

    Returns:
        Both repository names and the stacks whose repository changed.

    """
    old: str = call.required("source")
    new: str = call.required("to")

    def change(matrix: Matrix) -> MoveResult:
        return move_repository(matrix, old, new)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_commit(call: Call) -> Outcome:
    """Run ``commit``.

    Returns:
        Whether a commit was made, whether it was pushed, the commit and its message.

    """
    return Outcome(commit(call.matrix(), call.text("bead") or "", wait=call.lock_wait()))


def _run_sync_epics(call: Call) -> Outcome:
    """Run ``sync-epics``.

    Returns:
        The epic entries created and refreshed, what changed among the requirements, and the
        Epics with no PRD.

    """
    prd_dir: Path = call.required_folder("prd_dir", [PRD_DIR_ENV])
    epics: list[EpicBead] = read_epics(call.folder("control", CONTROL_VARIABLES), call.text("bead"))

    def change(matrix: Matrix) -> EpicsSynced:
        return sync_epics(matrix, epics, prd_dir, prd=call.text("prd"))

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_sync_documents(call: Call) -> Outcome:
    """Run ``sync-documents``.

    Returns:
        What reading the vault changed in the matrix.

    """
    arch: Path = call.required_folder("arch", [ARCH_PATH_ENV])
    paths: list[str] = call.texts("paths")

    def change(matrix: Matrix) -> DocumentsSynced:
        return sync_documents(matrix, arch, paths=paths or None)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_sync_events(call: Call) -> Outcome:
    """Run ``sync-events``: read the event catalog once, then load, change and save the matrix once.

    Returns:
        What the catalog changed among the events and rules, and the producer names that map to no entry.

    """
    stated: str | None = call.text("catalog")
    catalog_path: Path = (
        call.required_folder("arch", [ARCH_PATH_ENV]) / CATALOG_PATH if stated is None else Path(stated).expanduser()
    )
    catalog: list[CatalogEvent] = read_catalog(catalog_path)

    def change(matrix: Matrix) -> EventsSynced:
        return sync_events(matrix, catalog)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_seed(call: Call) -> Outcome:
    """Run ``seed``.

    Returns:
        What each seeding script step did.

    """
    control: Path = _control(call)
    return Outcome(
        seed(
            call.matrix(),
            control=control,
            arch=call.required_folder("arch", [ARCH_PATH_ENV]),
            prd_dir=call.required_folder("prd_dir", [PRD_DIR_ENV]),
            environ=call.environ,
            replace_existing=call.flag("replace"),
            wait=call.lock_wait(),
        ),
    )


def _run_seed_stacks(call: Call) -> Outcome:
    """Run ``seed-stacks``.

    Returns:
        The stacks created and changed, and the repositories that got none.

    """
    control: Path = _control(call)
    repositories: list[Repository] = read_repositories(control)
    types: dict[str, str] = repository_types(repositories, call.environ)

    def change(matrix: Matrix) -> StacksSeeded:
        return seed_stacks(matrix, repositories, types)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_seed_packages(call: Call) -> Outcome:
    """Run ``seed-packages``.

    Returns:
        The packages and the imports recorded, and the stacks whose repository states no project.

    """
    repositories: list[Repository] = read_repositories(_control(call))

    def change(matrix: Matrix) -> PackagesSeeded:
        return seed_packages(matrix, repositories)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _seed_folder(call: Call) -> Path:
    """Decide which folder holds the seeding files.

    Returns:
        The folder ``--directory`` names, else the seeding folder of the matrix file.

    """
    stated: str | None = call.text("directory")
    return seed_directory(call.matrix()) if stated is None else Path(stated).expanduser()


def _run_seed_inputs(call: Call) -> Outcome:
    """Run ``seed-inputs``.

    Returns:
        The batch files written for each seeding step.

    """
    arch: Path = call.required_folder("arch", [ARCH_PATH_ENV])
    allowance: int | None = call.number("allowance")
    return Outcome(
        seed_inputs(
            read_matrix(call.matrix()),
            arch=arch.expanduser(),
            vault=vault_root(call.required_folder("prd_dir", [PRD_DIR_ENV])),
            repositories=read_repositories(_control(call)),
            directory=_seed_folder(call),
            allowance=READING_ALLOWANCE if allowance is None else allowance,
        ),
    )


def _named_paths(call: Call, option: str, default: Path) -> list[Path]:
    """Read the files or folders an option names.

    Returns:
        The paths given, else the one default.

    """
    stated: list[str] = call.texts(option)
    return [Path(path).expanduser() for path in stated] if stated else [default]


def _run_seed_features(call: Call) -> Outcome:
    """Run ``seed-features``.

    Returns:
        Each proposed feature once with its purpose, and the requirements no proposal file lists.

    Raises:
        MatrixRefusedError: ``--list`` was not given.

    """
    if not call.flag("list"):
        message: str = "seed-features lists the proposed features: give --list"
        raise MatrixRefusedError(message)
    proposals: list[Path] = _named_paths(call, "proposals", _seed_folder(call) / PROPOSAL_FOLDER)
    return Outcome(list_proposed(proposals, read_matrix(call.matrix())))


def _run_seed_apply(call: Call) -> Outcome:
    """Run ``seed-apply``.

    Returns:
        The files read, what was recorded from them, and each write that could not be made.

    """
    step: SeedStep = as_step(call.required("step"))
    folder: Path = _seed_folder(call)
    features: bool = step == STEP_FEATURES
    results: list[Path] = _named_paths(call, "results", folder / (PROPOSAL_FOLDER if features else RESULT_FOLDER))
    stated: str | None = call.text("merge")
    merge: Path | None = Path(stated).expanduser() if stated is not None else None
    if merge is None and features:
        merge = folder / MERGE_FILE

    def change(matrix: Matrix) -> Applied:
        return seed_apply(matrix, step, results, merge)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_verify(call: Call) -> Outcome:
    """Run ``verify``.

    Returns:
        Whether the Story's merge completed its Epic and, when it did, the entries and
        relationships of the Epic that carry the verified flag at the commit.

    """
    return Outcome(
        record_verified(
            call.matrix(),
            call.required("story"),
            call.required("commit"),
            role_of(call.environ),
            call.folder("control", CONTROL_VARIABLES),
        ),
    )


def _run_built(call: Call) -> Outcome:
    """Run ``built``.

    Returns:
        The stacks and entries a Story built, from the ids its Tasks carry.

    """
    matrix: Matrix = read_matrix(call.matrix())
    return Outcome(built(matrix, read_tasks(call.folder("control", CONTROL_VARIABLES)), call.required("story")))


def _run_work(call: Call) -> Outcome:
    """Run ``work``.

    Returns:
        The open Tasks that name the entry or, for a stack, an entry the stack holds.

    """
    matrix: Matrix = read_matrix(call.matrix())
    tasks: list[TaskBead] = read_tasks(call.folder("control", CONTROL_VARIABLES))
    return Outcome(work(matrix, tasks, call.entry("id"), call.text("not_epic")))


def _run_affected(call: Call) -> Outcome:
    """Run ``affected``.

    Returns:
        The open Tasks a change to the entry affects.

    """
    matrix: Matrix = read_matrix(call.matrix())
    entry_id: EntryId = call.entry("id")
    tasks: list[TaskBead] = read_tasks(call.folder("control", CONTROL_VARIABLES))
    return Outcome(affected(matrix, tasks, entry_id, impact_view(matrix, entry_id)["ids"]))


def _run_approval(call: Call) -> Outcome:
    """Run ``approval``.

    Returns:
        The matrix content the Epic reaches, split into what carries the approved flag and what
        does not.

    """
    return Outcome(approval_view(read_matrix(call.matrix()), call.required("epic")))


def _run_check_reuse(call: Call) -> Outcome:
    """Run ``check-reuse``.

    Returns:
        The reuse violations in the changed files of the worktree, and the findings to rule on.

    Raises:
        MatrixRefusedError: ``--ids`` names no entry.

    """
    ids: list[EntryId] = call.entries("ids")
    if not ids:
        message: str = "--ids is required: the shared capability ids the Task states"
        raise MatrixRefusedError(message)
    worktree: Path = Path(call.required("worktree")).expanduser()
    return Outcome(check_reuse(read_matrix(call.matrix()), ids, worktree, call.texts("files") or None))


COMMANDS: Final[dict[str, Callable[[Call], Outcome]]] = {
    "put": _run_put,
    "link": _run_link,
    "unlink": _run_unlink,
    "settle": _run_settle,
    "rename": _run_rename,
    "remove": _run_remove,
    "move-repository": _run_move_repository,
    "commit": _run_commit,
    "sync-epics": _run_sync_epics,
    "sync-documents": _run_sync_documents,
    "sync-events": _run_sync_events,
    "seed": _run_seed,
    "seed-stacks": _run_seed_stacks,
    "seed-packages": _run_seed_packages,
    "seed-inputs": _run_seed_inputs,
    "seed-features": _run_seed_features,
    "seed-apply": _run_seed_apply,
    COMMAND_VERIFY: _run_verify,
    COMMAND_BUILT: _run_built,
    COMMAND_WORK: _run_work,
    COMMAND_AFFECTED: _run_affected,
    COMMAND_APPROVAL: _run_approval,
    "check-reuse": _run_check_reuse,
}
"""The sub-commands this module holds, by the name the registry's command table gives each."""


def _add_attribute(parser: argparse.ArgumentParser, option: AttributeOption) -> None:
    """Add the option, or the options, of one attribute to a parser."""
    name: str = f"--{option_name(option.attribute)}"
    if option.form == FORM_TEXT:
        parser.add_argument(name, help=option.description)
    elif option.form == FORM_NUMBER:
        parser.add_argument(name, type=int, help=option.description)
    elif option.form == FORM_MANY:
        parser.add_argument(name, nargs="+", help=f"{option.description}; the values given are added")
    elif option.form == FORM_JSON:
        parser.add_argument(name, help=f"{option.description}, as JSON or as @file naming a file that holds it")
    elif option.form == FORM_PARTS:
        part: str
        for part in option.parts:
            parser.add_argument(f"{name}-{option_name(part)}", help=f"the {part} of the {option.attribute} attribute")
    else:
        assert_never(option.form)


def _add_relationship(parser: argparse.ArgumentParser) -> None:
    """Add the options that name one relationship: its kind, both ends, its side and its attributes."""
    parser.add_argument("kind", help=f"the relationship's kind: one of {', '.join(RELATIONSHIP_KINDS)}")
    parser.add_argument("--from", dest="source", required=True, help="the id of the entry the relationship starts from")
    parser.add_argument("--to", required=True, help="the id of the entry the relationship ends at")
    parser.add_argument("--side", required=True, help=f"the side that states it: one of {', '.join(SIDES)}")
    option: AttributeOption
    for option in attribute_options(RELATIONSHIP_TABLE).values():
        _add_attribute(parser, option)


def _change_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
) -> None:
    """Add the sub-commands that change entries and relationships, and the commit."""
    entry: argparse.ArgumentParser = commands.add_parser("put", parents=[where], help="add or change one entry")
    entry.add_argument("kind", help=f"the entry's kind: one of {', '.join(ENTRY_KINDS)}")
    entry.add_argument("--side", required=True, help=f"the side the fact came from: one of {', '.join(SIDES)}")
    entry.add_argument("--id", help="the entry's id; default: built from the kind and the name")
    entry.add_argument("--name", help="the entry's name; needed for an entry that is new")
    entry.add_argument("--aliases", nargs="+", help="other names the entry is known by; the values given are added")
    entry.add_argument(
        "--remove-aliases",
        nargs="+",
        help="aliases to remove from the entry; one it does not hold is ignored",
    )
    entry.add_argument("--purpose", help="one or two sentences that identify the entry")
    entry.add_argument(
        "--stack",
        help="the id of the stack that holds a repository-side component, infrastructure or layer; it builds the id",
    )
    entry.add_argument(
        "--published-by",
        help="the id of the service or component that publishes an event the architecture side records; "
        "the publishes relationship is written with the event",
    )
    entry.add_argument("--unset", nargs="+", help="the names of the attributes to remove from the entry")
    option: AttributeOption
    for option in attribute_options(ENTRY_TABLE).values():
        _add_attribute(entry, option)
    _add_relationship(commands.add_parser("link", parents=[where], help="add or change one relationship"))
    _add_relationship(commands.add_parser("unlink", parents=[where], help="remove one relationship of one side"))
    settled: argparse.ArgumentParser = commands.add_parser(
        "settle",
        parents=[where],
        help="record which statement of a disagreement stands",
    )
    settled.add_argument("--id", required=True, help="the id of the disagreement")
    settled.add_argument(
        "--stands",
        nargs=STANDS_PARTS,
        required=True,
        metavar=("DOCUMENT", "HEADING"),
        help="the document (its id, or its path under the architecture root) and the heading of what stands",
    )
    settled.add_argument("--rule", required=True, help="the rule the ruling was made by")
    settled.add_argument("--reason", help="why, when the rule does not say it all")
    renamed: argparse.ArgumentParser = commands.add_parser(
        "rename",
        parents=[where],
        help="re-key an entry and both ends of its relationships",
    )
    renamed.add_argument("--from", dest="source", required=True, help="the entry's id now")
    renamed.add_argument("--to", required=True, help="the id it is to have, of the same kind")
    removed: argparse.ArgumentParser = commands.add_parser(
        "remove",
        parents=[where],
        help="remove an entry and its relationships",
    )
    removed.add_argument("id", help="the entry's id")
    removed.add_argument("--held", action="store_true", help="also remove every entry whose home or id names it")
    moved: argparse.ArgumentParser = commands.add_parser(
        "move-repository",
        parents=[where],
        help="give every stack of one repository another repository's name",
    )
    moved.add_argument("--from", dest="source", required=True, help="the repository's name as the stacks hold it")
    moved.add_argument("--to", required=True, help="the name they are to hold")
    committed: argparse.ArgumentParser = commands.add_parser(
        "commit",
        parents=[where],
        help="commit the matrix file alone and push it",
    )
    committed.add_argument("--bead", help="the Epic or Story the recorded changes belong to")


def _sync_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
    sources: Mapping[str, argparse.ArgumentParser],
) -> None:
    """Add the sub-commands that bring the matrix up to date with beads and the vault, and that seed it."""
    control: argparse.ArgumentParser = sources["control"]
    arch: argparse.ArgumentParser = sources["arch"]
    prds: argparse.ArgumentParser = sources["prds"]
    epics: argparse.ArgumentParser = commands.add_parser(
        "sync-epics",
        parents=[where, control, prds],
        help="epic and requirement entries from beads and the PRDs",
    )
    epics.add_argument("--bead", help="the one Epic to give an entry; default: every open Epic")
    epics.add_argument("--prd", help="the PRD file of the one Epic given: absolute, or relative to the vault root")
    documents: argparse.ArgumentParser = commands.add_parser(
        "sync-documents",
        parents=[where, arch],
        help="document entries, their headings and lifecycle, and describedBy, from the vault",
    )
    documents.add_argument("--paths", nargs="+", help="the files to read; default: every architecture document")
    documents.add_argument("--bead", help="the Epic the documents were changed for; nothing recorded names it")
    events: argparse.ArgumentParser = commands.add_parser(
        "sync-events",
        parents=[where, arch],
        help="event entries, their purposes and publishers, from the event catalog in arc42 section 6",
    )
    events.add_argument("--catalog", help=f"the event catalog file; default: {CATALOG_PATH} under --arch")
    folder: argparse.ArgumentParser = sources["folder"]
    seeded: argparse.ArgumentParser = commands.add_parser(
        "seed",
        parents=[where, control, arch, prds],
        help="write an empty matrix and fill it from beads, the PRDs, arc42 and the repositories",
    )
    seeded.add_argument("--replace", action="store_true", help="replace the matrix file that is there")
    commands.add_parser("seed-stacks", parents=[where, control], help="one stack per repository")
    commands.add_parser("seed-packages", parents=[where, control], help="project packages and imports between stacks")
    inputs: argparse.ArgumentParser = commands.add_parser(
        "seed-inputs",
        parents=[where, control, arch, prds, folder],
        help="write the batch files the seeding sessions are handed",
    )
    inputs.add_argument("--allowance", type=int, help=f"the bytes one session reads; default: {READING_ALLOWANCE}")
    proposed: argparse.ArgumentParser = commands.add_parser(
        "seed-features",
        parents=[where, folder],
        help="list each proposed feature once, for the session that merges them so that one capability is one feature",
    )
    proposed.add_argument("--list", action="store_true", help="print one line's worth per proposed feature")
    proposed.add_argument("--proposals", nargs="+", help="the proposal files or folders; default: the seeding folder's")
    applied: argparse.ArgumentParser = commands.add_parser(
        "seed-apply",
        parents=[where, folder],
        help="record the result files the sessions of one seeding step wrote",
    )
    applied.add_argument("--step", required=True, help=f"the seeding step: one of {', '.join(SEED_STEPS)}")
    applied.add_argument("--results", nargs="+", help="the result or proposal files or folders; default: the step's")
    applied.add_argument("--merge", help="the merge file of the features step; default: the seeding folder's")


def _build_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
    sources: Mapping[str, argparse.ArgumentParser],
) -> None:
    """Add the verified flag, the Task script's reads, the approval lookup and the reuse check."""
    control: argparse.ArgumentParser = sources["control"]
    verified: argparse.ArgumentParser = commands.add_parser(
        COMMAND_VERIFY,
        parents=[where, control],
        help="set the verified flag on what an Epic's Stories built, once the merge of this Story completes the Epic",
    )
    verified.add_argument("--story", required=True, help="the Story's beads id")
    verified.add_argument("--commit", required=True, help="the merge commit of the Story's pull request")
    story: argparse.ArgumentParser = commands.add_parser(
        COMMAND_BUILT,
        parents=[where, control],
        help="the stacks and entries a Story built",
    )
    story.add_argument("--story", required=True, help="the Story's beads id")
    working: argparse.ArgumentParser = commands.add_parser(
        COMMAND_WORK,
        parents=[where, control],
        help="the open Tasks that name an entry",
    )
    working.add_argument("--id", required=True, help="the entry's id")
    working.add_argument("--not-epic", help="leave out the Tasks of this Epic")
    touched: argparse.ArgumentParser = commands.add_parser(
        COMMAND_AFFECTED,
        parents=[where, control],
        help="the open Tasks a change to an entry affects",
    )
    touched.add_argument("--id", required=True, help="the entry's id")
    approval: argparse.ArgumentParser = commands.add_parser(
        COMMAND_APPROVAL,
        parents=[where],
        help="the matrix content an Epic reaches, approved and not approved",
    )
    approval.add_argument("--epic", required=True, help="the Epic's beads id")
    reuse: argparse.ArgumentParser = commands.add_parser(
        "check-reuse",
        parents=[where],
        help="check the changed files of a worktree against the shared capabilities a Task states",
    )
    reuse.add_argument("--ids", nargs="+", required=True, help="the shared capability ids the Task states")
    reuse.add_argument("--worktree", required=True, help="the worktree the Task changed")
    reuse.add_argument("--files", nargs="+", help="the changed files; default: what git reports changed")


def add_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
    sources: Mapping[str, argparse.ArgumentParser],
) -> None:
    """Add this module's sub-commands to the command line.

    Args:
        commands: The sub-command group of the ``atw-matrix`` parser.
        where: The options that name the matrix file.
        sources: The option groups that name a source, by ``control`` (the control repository),
            ``arch`` (the architecture root), ``prds`` (the PRD folder) and ``folder`` (the
            seeding folder).

    """
    _change_parsers(commands, where)
    _sync_parsers(commands, where, sources)
    _build_parsers(commands, where, sources)
