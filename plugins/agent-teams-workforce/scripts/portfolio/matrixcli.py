"""The sub-commands of ``atw-matrix`` that record a design, review it, and mark what was built.

``matrix.py`` holds the reads and the syncs; this module holds everything that writes a design
into the matrix or closes a step of it: ``put``, ``link``, ``claim``, ``settle``,
``note-sendback``, ``add-resource-type``, ``expertise``, ``unapproved``, ``approve``,
``mark-built``, ``mark-deployed``, ``mark-merged`` and ``check-reuse``. Each is one locked
read-modify-write of the matrix file, or a read.

The options of ``put`` are not listed here: one option exists per row field the schema lets a
put state, in the form the schema's type of that field calls for (:func:`field_options`).
"""

import argparse
import json
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
    APPROVAL_BASES,
    BASIS_REVIEWED,
    DISAGREEMENT_RULES,
    ELEMENT_KINDS,
    KIND_PRD,
    KINDS,
    LIFECYCLE_EFFECTIVE,
    LINK_TYPES,
    PUT_FIELDS,
    ApprovalBasis,
    Claim,
    DisagreementRule,
    JsonValue,
    Kind,
    Link,
    LinkType,
    Matrix,
    MatrixError,
    NodeId,
    ReviewScope,
    load_schema,
    validate_review_scope,
)
from matrixcall import Call, Outcome
from matrixcode import (
    COMMAND_BUILT,
    COMMAND_DEPLOYED,
    COMMAND_MERGED,
    COMMAND_STORY_BUILT,
    Built,
    CodeMarked,
    Deployed,
    Merged,
    record_built,
    record_deployed,
    record_merged,
    story_built,
)
from matrixexpertise import (
    SUBAGENT_START,
    Expertise,
    add_for_types,
    agent_skills,
    hook_output,
    refresh,
    skill_text,
)
from matrixquery import elements_of_repository, resolve
from matrixreuse import ReuseResult, changed_files, check_reuse, parse_task_elements, task_elements
from matrixreview import Approved, approve, open_review
from matrixstore import (
    CONTROL_REPO_FALLBACK_ENV,
    MatrixRefusedError,
    Stamp,
    as_node_id,
    make_id,
    read_matrix,
    role_of,
    timestamp,
    update_matrix,
    write_text,
)
from matrixsync import set_lifecycle, vault_root
from matrixwrite import (
    Actor,
    ClaimResult,
    LinkResult,
    Put,
    PutResult,
    ResourceTypeResult,
    SendBackResult,
    Settlement,
    SettleResult,
    add_resource_type,
    claim,
    link,
    note_sendback,
    put,
    settle,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

type FieldForm = Literal["text", "many", "flag", "parts", "json"]
"""How a row field is stated on the command line: one string, several strings, a flag, one string
per part of a small object, or JSON."""

FORM_TEXT: Final = "text"
FORM_MANY: Final = "many"
FORM_FLAG: Final = "flag"
FORM_PARTS: Final = "parts"
FORM_JSON: Final = "json"
REVIEW_STEP: Final = "review"
"""The journal step named on a claim the review opens when the caller names none."""
CONTROL_VARIABLES: Final[tuple[str, ...]] = (CONTROL_REPO_ENV, CONTROL_REPO_FALLBACK_ENV)
_CAMEL: Final[re.Pattern[str]] = re.compile(r"(?<=[a-z0-9])([A-Z])")


@dataclass(frozen=True, slots=True)
class FieldOption:
    """How one row field is stated on the ``put`` command line."""

    field: str
    form: FieldForm
    parts: tuple[str, ...]
    """The properties of a field stated one string per part; empty for every other form."""
    description: str


class PutOutput(TypedDict):
    """What ``put`` prints: what the put did, and the expertise it made newly relevant."""

    put: PutResult
    expertiseAdded: list[str]
    """The skills the row's resource type added to the Epic's expertise list."""
    expertiseText: str
    """The text of those skills, for the session that recorded the row to read now."""


def _resolved(spec: JsonValue, definitions: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Follow a schema node to the definition it references.

    Returns:
        The referenced definition, or the node itself when it references none.

    Raises:
        TypeError: The node is not an object.

    """
    if not isinstance(spec, dict):
        message: str = "the matrix schema holds a property that is not an object"
        raise TypeError(message)
    pointer: JsonValue = spec.get("$ref")
    target: JsonValue = definitions.get(pointer.rpartition("/")[2]) if isinstance(pointer, str) else None
    return target if isinstance(target, dict) else spec


def _is_text(spec: Mapping[str, JsonValue]) -> bool:
    """Tell whether a schema node describes one string.

    Returns:
        True for a vocabulary and for a type that is, or may be, a string.

    """
    kind: JsonValue = spec.get("type")
    return "enum" in spec or kind == "string" or (isinstance(kind, list) and "string" in kind)


def _field_option(field: str, spec: JsonValue, definitions: Mapping[str, JsonValue]) -> FieldOption:
    """Work out how one row field is stated, from the schema's type of it.

    Returns:
        Text for a string or a vocabulary, a flag and its ``--no-`` form for a boolean, several
        strings for a list of strings, one string per property for a closed object of strings,
        and JSON for the rest.

    """
    described: JsonValue = spec.get("description") if isinstance(spec, dict) else None
    resolved: dict[str, JsonValue] = _resolved(spec, definitions)
    description: str = described if isinstance(described, str) else f"the row's {field}"
    properties: JsonValue = resolved.get("properties")
    form: FieldForm = FORM_JSON
    parts: tuple[str, ...] = ()
    if _is_text(resolved):
        form = FORM_TEXT
    elif resolved.get("type") == "boolean":
        form = FORM_FLAG
    elif resolved.get("type") == "array" and _is_text(_resolved(resolved.get("items"), definitions)):
        form = FORM_MANY
    elif isinstance(properties, dict) and all(_is_text(_resolved(part, definitions)) for part in properties.values()):
        form, parts = FORM_PARTS, tuple(properties)
    return FieldOption(field, form, parts, description)


@lru_cache(maxsize=1)
def field_options() -> dict[str, FieldOption]:
    """List how each row field a put may state is given on the command line.

    Returns:
        One entry per field the schema's put table names for any kind, in schema order.

    Raises:
        TypeError: The schema does not define the row's properties.

    """
    definitions: JsonValue = load_schema().get("$defs")
    node: JsonValue = definitions.get("Node") if isinstance(definitions, dict) else None
    properties: JsonValue = node.get("properties") if isinstance(node, dict) else None
    if not isinstance(definitions, dict) or not isinstance(properties, dict):
        message: str = "the matrix schema does not define the properties of a row"
        raise TypeError(message)
    wanted: set[str] = {field for fields in PUT_FIELDS.values() for field in fields}
    return {field: _field_option(field, spec, definitions) for field, spec in properties.items() if field in wanted}


def option_name(field: str) -> str:
    """Name the command-line option of a row field.

    Returns:
        The field in lower case with a hyphen before each capital: ``resourceType`` gives
        ``resource-type``.

    """
    return _CAMEL.sub(r"-\1", field).lower()


def _destination(field: str) -> str:
    """Name the parsed argument of a row field's option.

    Returns:
        The option name with underscores.

    """
    return option_name(field).replace("-", "_")


def _stated_field(call: Call, option: FieldOption) -> JsonValue:
    """Read one row field from the command line.

    Returns:
        The value stated, or None when the field was not stated.

    Raises:
        MatrixRefusedError: Some parts of a field stated in parts are given and others are not.

    """
    name: str = _destination(option.field)
    if option.form == FORM_TEXT:
        return call.text(name)
    if option.form == FORM_FLAG:
        return call.choice(name)
    if option.form == FORM_MANY:
        many: list[JsonValue] = [*call.texts(name)]
        return many or None
    if option.form == FORM_JSON:
        return call.json(name)
    if option.form == FORM_PARTS:
        given: dict[str, JsonValue] = {part: call.text(f"{name}_{part}") for part in option.parts}
        if all(value is None for value in given.values()):
            return None
        if any(value is None for value in given.values()):
            wanted: str = ", ".join(f"--{option_name(option.field)}-{part}" for part in option.parts)
            message: str = f"give all of {wanted}"
            raise MatrixRefusedError(message)
        return given
    assert_never(option.form)


def _stated(call: Call) -> dict[str, JsonValue]:
    """Read every row field the command line states.

    Returns:
        Each stated field and its value.

    """
    stated: dict[str, JsonValue] = {}
    option: FieldOption
    for option in field_options().values():
        value: JsonValue = _stated_field(call, option)
        if value is not None:
            stated[option.field] = value
    return stated


def _member[T: str](stated: str, choices: tuple[T, ...], what: str) -> T:
    """Narrow a command-line value to one member of a vocabulary.

    Returns:
        The member.

    Raises:
        MatrixRefusedError: The value is not in the vocabulary.

    """
    choice: T
    for choice in choices:
        if choice == stated:
            return choice
    message: str = f"{stated!r} is not {what}: one of {', '.join(choices)}"
    raise MatrixRefusedError(message)


def _actor(call: Call) -> Actor:
    """Name who runs a write: the role, and the Epic and journal step given.

    Returns:
        The actor, at the present moment.

    """
    return Actor(role_of(call.environ), call.text("bead") or "", call.text("step") or "", timestamp())


def _row_id(call: Call, matrix: Matrix) -> NodeId | None:
    """Read the ``--id`` of a row.

    Returns:
        None when it was not given; the id of the row it refers to, by id, former id or a name
        only that row answers to; else the id itself, for a row that does not exist yet.

    """
    stated: str | None = call.text("id")
    if stated is None:
        return None
    try:
        return resolve(matrix, stated)
    except MatrixRefusedError:
        return as_node_id(stated)


def _run_put(call: Call) -> Outcome:
    """Run ``put``.

    Returns:
        What the put did, the skills the row's resource type made newly relevant to the Epic,
        and their text.

    """
    kind: Kind = _member(call.required("kind"), KINDS, "a row kind")
    stated: dict[str, JsonValue] = _stated(call)
    actor: Actor = _actor(call)
    resource_type: JsonValue = stated.get("resourceType")

    def change(matrix: Matrix) -> tuple[PutResult, list[str]]:
        done: PutResult = put(matrix, Put(kind, _row_id(call, matrix), stated), actor)
        relevant: bool = (
            kind in ELEMENT_KINDS
            and isinstance(resource_type, str)
            and bool(actor.bead)
            and make_id(KIND_PRD, actor.bead) in matrix["nodes"]
        )
        added: list[str] = (
            add_for_types(matrix, actor.bead, [resource_type], actor.stamp())
            if relevant and isinstance(resource_type, str)
            else []
        )
        return done, added

    done: PutResult
    added: list[str]
    done, added = update_matrix(call.matrix(), change, wait=call.lock_wait())
    output: PutOutput = {"put": done, "expertiseAdded": added, "expertiseText": skill_text(added, call.environ)}
    return Outcome(output)


def _run_link(call: Call) -> Outcome:
    """Run ``link``.

    Returns:
        The link as the source row now holds it, and whether it was added or removed.

    """
    link_type: LinkType = _member(call.required("type"), LINK_TYPES, "a link type")
    actor: Actor = _actor(call)
    heading: str | None = call.text("heading")
    relied: list[str] = call.texts("provides")

    def change(matrix: Matrix) -> LinkResult:
        wanted: Link = {"type": link_type, "to": resolve(matrix, call.required("to"))}
        if heading is not None:
            wanted["heading"] = heading
        if relied:
            wanted["provides"] = relied
        if call.flag("ambiguous"):
            wanted["ambiguous"] = True
        return link(matrix, resolve(matrix, call.required("source")), wanted, actor, remove=call.flag("remove"))

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_claim(call: Call) -> Outcome:
    """Run ``claim``.

    Returns:
        Whether the claim is the Epic's, the claim that stands, and the holder's unapproved rows.

    """
    actor: Actor = _actor(call)

    def change(matrix: Matrix) -> ClaimResult:
        target: NodeId = resolve(matrix, call.required("row"))
        return claim(matrix, target, call.text("heading"), actor, release=call.flag("release"))

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _statement_inputs(call: Call) -> list[Mapping[str, JsonValue]]:
    """Read the statements of a disagreement from ``--statements``.

    Returns:
        The statements; none when the option was not given.

    Raises:
        MatrixRefusedError: The option holds something other than a list of objects.

    """
    stated: JsonValue = call.json("statements")
    if stated is None:
        return []
    if not isinstance(stated, list):
        message: str = "--statements holds a JSON list of statements"
        raise MatrixRefusedError(message)
    statements: list[Mapping[str, JsonValue]] = []
    entry: JsonValue
    for entry in stated:
        if not isinstance(entry, dict):
            message = "each statement is a JSON object with its document, heading and text"
            raise MatrixRefusedError(message)
        statements.append(entry)
    return statements


def _run_settle(call: Call) -> Outcome:
    """Run ``settle``.

    Returns:
        The disagreement row as recorded, and whether each statement is in approved text.

    """
    rule: str | None = call.text("rule")
    actor: Actor = _actor(call)
    statements: list[Mapping[str, JsonValue]] = _statement_inputs(call)
    chosen: DisagreementRule | None = (
        None if rule is None else _member(rule, DISAGREEMENT_RULES, "a rule a disagreement is settled by")
    )

    def change(matrix: Matrix) -> SettleResult:
        fact: str | None = call.text("fact")
        reopens: str | None = call.text("reopens")
        settlement: Settlement = Settlement(
            name=call.text("name") or "",
            row=_row_id(call, matrix),
            statements=statements,
            rule=chosen,
            stands=call.number("stands"),
            reason=call.text("reason") or "",
            evidence=call.texts("evidence"),
            fact=None if fact is None else resolve(matrix, fact),
            reopens=None if reopens is None else resolve(matrix, reopens),
        )
        return settle(matrix, settlement, actor)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_note_sendback(call: Call) -> Outcome:
    """Run ``note-sendback``.

    Returns:
        The PRD row, the criterion and how many send-backs the row holds.

    """
    actor: Actor = _actor(call)

    def change(matrix: Matrix) -> SendBackResult:
        return note_sendback(matrix, call.required("criterion"), actor)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_add_resource_type(call: Call) -> Outcome:
    """Run ``add-resource-type``.

    Returns:
        The resource type and whether the controlled list gained it.

    """

    def change(matrix: Matrix) -> ResourceTypeResult:
        return add_resource_type(matrix, call.required("name"))

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _prd_text(call: Call, matrix: Matrix, bead: str) -> str:
    """Read the text of an Epic's PRD, for ``expertise --scan-prd``.

    Returns:
        The PRD file's text.

    Raises:
        MatrixRefusedError: The Epic has no PRD row.
        MatrixError: The PRD file cannot be read.

    """
    key: NodeId = make_id(KIND_PRD, bead)
    message: str
    if key not in matrix["nodes"] or "path" not in matrix["nodes"][key]:
        message = f"the matrix has no PRD row for {bead}; sync-prds writes it"
        raise MatrixRefusedError(message)
    file: Path = vault_root(call.required_folder("prd_dir", [PRD_DIR_ENV])) / matrix["nodes"][key]["path"]
    try:
        return file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        message = f"cannot read the PRD {file}: {error}"
        raise MatrixError(message) from error


def _run_expertise(call: Call) -> Outcome:
    """Run ``expertise``.

    Returns:
        The Epic's expertise list and the skills to hand the session asked about; with
        ``--emit-context``, the hook output that puts those skills' text in a started session.

    """
    bead: str = call.required("bead")
    stamp: Stamp = Stamp(timestamp(), bead)

    def change(matrix: Matrix) -> Expertise:
        return refresh(matrix, bead, _prd_text(call, matrix, bead) if call.flag("scan_prd") else "", stamp)

    result: Expertise = update_matrix(call.matrix(), change, wait=call.lock_wait())
    agent: str | None = call.text("for_agent")
    listed: set[str] = set() if agent is None else set(agent_skills(agent))
    result["skills"] = [name for name in result["expertise"] if name not in listed]
    if call.flag("emit_context"):
        text: str = skill_text(result["skills"], call.environ)
        return Outcome(hook_output(text, call.text("hook_event") or SUBAGENT_START))
    if call.flag("with_text"):
        result["text"] = skill_text(result["skills"], call.environ)
    return Outcome(result)


def _run_unapproved(call: Call) -> Outcome:
    """Run ``unapproved``.

    Returns:
        The review scope of the Epic, which is also written to ``--out`` when it is given.

    Raises:
        MatrixError: The folder of ``--out`` cannot be created.

    """
    bead: str = call.required("bead")
    at: str = timestamp()
    held: Claim = {"bead": bead, "step": call.text("step") or REVIEW_STEP, "at": at}
    stamp: Stamp = Stamp(at, f"{bead} {held['step']}")

    def change(matrix: Matrix) -> ReviewScope:
        return validate_review_scope(open_review(matrix, bead, held, stamp))

    scope: ReviewScope = update_matrix(call.matrix(), change, wait=call.lock_wait())
    out: str | None = call.text("out")
    if out is not None:
        target: Path = Path(out).expanduser()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            message: str = f"cannot create the folder of {target}: {error}"
            raise MatrixError(message) from error
        write_text(target, json.dumps(scope, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return Outcome(scope)


def _run_approve(call: Call) -> Outcome:
    """Run ``approve``.

    Returns:
        What was approved, what remains and why, the coverage and the documents made effective.

    """
    bead: str = call.required("bead")
    stated: str = call.text("basis") or BASIS_REVIEWED
    basis: ApprovalBasis = _member(stated, APPROVAL_BASES, "a basis of approval")
    stamp: Stamp = Stamp(timestamp(), f"{bead} approve")

    def change(matrix: Matrix) -> Approved:
        result: Approved = approve(matrix, bead, call.texts("steps"), basis, stamp)
        if result["promoted"]:
            vault: Path = vault_root(call.required_folder("arch", [ARCH_PATH_ENV]))
            path: str
            for path in result["promoted"]:
                set_lifecycle(vault, path, LIFECYCLE_EFFECTIVE)
        return result

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_mark_built(call: Call) -> Outcome:
    """Run ``mark-built``.

    Returns:
        The rows whose code marker changed.

    """
    built: Built = {
        "task": call.required("task"),
        "story": call.text("story") or "",
        "repository": call.required("repository"),
        "commit": call.required("commit"),
        "ref": call.required("ref"),
        "elements": call.texts("elements"),
    }
    marked: CodeMarked = record_built(call.matrix(), built, role_of(call.environ))
    return Outcome(marked)


def _run_mark_deployed(call: Call) -> Outcome:
    """Run ``mark-deployed``.

    Returns:
        The rows whose code marker changed, and the stack names that are no row.

    """
    deployed: Deployed = {
        "story": call.required("story"),
        "repository": call.text("repository") or "",
        "commit": call.required("commit"),
        "stacks": call.texts("stacks"),
    }
    marked: CodeMarked = record_deployed(call.matrix(), deployed, role_of(call.environ))
    return Outcome(marked)


def _run_mark_merged(call: Call) -> Outcome:
    """Run ``mark-merged``.

    Returns:
        The rows whose code marker changed.

    """
    merged: Merged = {"story": call.required("story"), "ref": call.required("ref")}
    pull_request: str | None = call.text("pr")
    if pull_request is not None:
        merged["pr"] = pull_request
    marked: CodeMarked = record_merged(call.matrix(), merged, role_of(call.environ))
    return Outcome(marked)


def _run_story_built(call: Call) -> Outcome:
    """Run ``story-built``.

    Returns:
        The rows whose trusted code the Story built, each with the headings that describe it.

    """
    return Outcome(story_built(read_matrix(call.matrix()), call.required("story")))


def elements_of_task(call: Call, task: str) -> list[str]:
    """Read the elements a Task builds, from a saved bead or from beads.

    Returns:
        The matrix ids the Task names: from the file ``--task-file`` names, which holds what
        ``bd show <task> --json`` printed, or else from ``bd`` in the control repository.

    Raises:
        MatrixError: The saved file cannot be read.

    """
    saved: str | None = call.text("task_file")
    if saved is None:
        return task_elements(call.required_folder("control", CONTROL_VARIABLES), task)
    try:
        return parse_task_elements(Path(saved).expanduser().read_text(encoding="utf-8"), task)
    except OSError as error:
        message: str = f"cannot read the Task file {saved}: {error}"
        raise MatrixError(message) from error


def _run_check_reuse(call: Call) -> Outcome:
    """Run ``check-reuse``.

    Returns:
        The reuse violations in the files the Task changed, and the definitions to rule on.

    """
    task: str = call.required("task")
    worktree: Path = Path(call.required("worktree")).expanduser()
    matrix: Matrix = read_matrix(call.matrix())
    named: list[str] = call.texts("elements") or elements_of_task(call, task)
    built: list[NodeId] = [resolve(matrix, name) for name in named]
    repository: str | None = call.text("repository")
    scope: list[NodeId] = built if repository is None else elements_of_repository(matrix, repository)
    result: ReuseResult = check_reuse(matrix, built, scope, worktree, call.texts("files") or changed_files(worktree))
    result["task"] = task
    return Outcome(result)


COMMANDS: Final[dict[str, Callable[[Call], Outcome]]] = {
    "put": _run_put,
    "link": _run_link,
    "claim": _run_claim,
    "settle": _run_settle,
    "note-sendback": _run_note_sendback,
    "add-resource-type": _run_add_resource_type,
    "expertise": _run_expertise,
    "unapproved": _run_unapproved,
    "approve": _run_approve,
    COMMAND_BUILT: _run_mark_built,
    COMMAND_DEPLOYED: _run_mark_deployed,
    COMMAND_MERGED: _run_mark_merged,
    COMMAND_STORY_BUILT: _run_story_built,
    "check-reuse": _run_check_reuse,
}
"""The sub-commands this module holds, by the name the schema's command table gives each."""


def _add_field(parser: argparse.ArgumentParser, option: FieldOption) -> None:
    """Add the option, or the options, of one row field to the ``put`` parser."""
    name: str = f"--{option_name(option.field)}"
    if option.form == FORM_TEXT:
        parser.add_argument(name, help=option.description)
    elif option.form == FORM_FLAG:
        parser.add_argument(name, action=argparse.BooleanOptionalAction, help=option.description)
    elif option.form == FORM_MANY:
        parser.add_argument(name, nargs="+", help=f"{option.description}; the values given are added")
    elif option.form == FORM_JSON:
        parser.add_argument(name, help=f"{option.description}, as JSON or as @file naming a file that holds it")
    elif option.form == FORM_PARTS:
        part: str
        for part in option.parts:
            parser.add_argument(f"{name}-{part}", help=f"the {part} of the row's {option.field}")
    else:
        assert_never(option.form)


def _design_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
    who: argparse.ArgumentParser,
) -> None:
    """Add the sub-commands a designing session runs: put, link, claim, settle and the two small ones."""
    row: argparse.ArgumentParser = commands.add_parser("put", parents=[where, who], help="add or change one row")
    row.add_argument("--kind", required=True, help=f"the kind of row: one of {', '.join(PUT_FIELDS)}")
    row.add_argument("--id", help="the row's id; default: built from the kind, the placement and the name")
    option: FieldOption
    for option in field_options().values():
        _add_field(row, option)
    joined: argparse.ArgumentParser = commands.add_parser("link", parents=[where, who], help="add or remove one link")
    joined.add_argument("--from", dest="source", required=True, help="the row the link starts from")
    joined.add_argument("--type", required=True, help=f"the link type: one of {', '.join(LINK_TYPES)}")
    joined.add_argument("--to", required=True, help="the row the link points at")
    joined.add_argument("--heading", help="for a describedBy link: the heading of the document")
    joined.add_argument("--provides", nargs="+", help="for a uses link: the ids of the provides entries relied on")
    joined.add_argument("--ambiguous", action="store_true", help="mark the link as one of several candidates")
    joined.add_argument("--remove", action="store_true", help="remove the link instead of adding it")
    held: argparse.ArgumentParser = commands.add_parser(
        "claim",
        parents=[where, who],
        help="mark a fact, a feature or a document heading as being changed by an Epic",
    )
    held.add_argument("row", help="the fact or feature row, or the document row whose heading is claimed")
    held.add_argument("--heading", help="the heading of a document row")
    held.add_argument("--release", action="store_true", help="give the Epic's own claim up")
    settled: argparse.ArgumentParser = commands.add_parser(
        "settle",
        parents=[where, who],
        help="record a disagreement between statements and its settlement",
    )
    settled.add_argument("--id", help="the id of the disagreement; default: built from the name")
    settled.add_argument("--name", help="what the disagreement is about")
    settled.add_argument("--statements", help="the statements, as a JSON list or @file: document, heading, text, line")
    rules: str = ", ".join(DISAGREEMENT_RULES)
    settled.add_argument("--rule", help=f"the rule that settles it, one of {rules}; none records it as open")
    settled.add_argument("--stands", type=int, help="the number, from 1, of the statement that stands")
    settled.add_argument("--reason", help="why that statement stands")
    settled.add_argument("--evidence", nargs="+", help="what the settlement rests on: a URL, a document, a requirement")
    settled.add_argument("--fact", help="the fact row that states what stands")
    settled.add_argument("--reopens", help="the earlier disagreement a new requirement reopens")
    sent: argparse.ArgumentParser = commands.add_parser(
        "note-sendback",
        parents=[where, who],
        help="record that a review sent a criterion back",
    )
    sent.add_argument("--criterion", required=True, help="the id of the criterion")
    typed: argparse.ArgumentParser = commands.add_parser(
        "add-resource-type",
        parents=[where],
        help="add a value to the controlled list of resource types",
    )
    typed.add_argument("name", help="the resource type, in lower case with hyphens")


def _review_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
    arch: argparse.ArgumentParser,
) -> None:
    """Add the sub-commands the script runs around a review: expertise, unapproved and approve."""
    skills: argparse.ArgumentParser = commands.add_parser(
        "expertise",
        parents=[where],
        help="the skills an Epic's domains need",
    )
    skills.add_argument("--bead", required=True, help="the Epic")
    skills.add_argument("--scan-prd", action="store_true", help="also match the PRD's text against the skills' terms")
    skills.add_argument("--prd-dir", help=f"a folder of the vault the PRD is in; default: {PRD_DIR_ENV}")
    skills.add_argument("--for-agent", help="leave out the skills this agent's own definition lists")
    skills.add_argument("--with-text", action="store_true", help="include the text of the skills")
    skills.add_argument("--emit-context", action="store_true", help="print the hook output that adds the text")
    skills.add_argument("--hook-event", help=f"the hook event the output answers; default: {SUBAGENT_START}")
    scope: argparse.ArgumentParser = commands.add_parser(
        "unapproved",
        parents=[where],
        help="list what is not approved for an Epic and mark it in review",
    )
    scope.add_argument("--bead", required=True, help="the Epic")
    scope.add_argument("--step", help="the journal step that opens the review")
    scope.add_argument("--out", help="a file to write the review scope to")
    passed: argparse.ArgumentParser = commands.add_parser(
        "approve",
        parents=[where, arch],
        help="mark approved what is in review for an Epic",
    )
    passed.add_argument("--bead", required=True, help="the Epic")
    passed.add_argument("--steps", nargs="+", required=True, help="the journal step ids of the reviews that passed")
    bases: str = ", ".join(APPROVAL_BASES)
    passed.add_argument("--basis", help=f"why it is approved, one of {bases}; default: {BASIS_REVIEWED}")


def _build_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
) -> None:
    """Add the sub-commands the build and deploy pipelines run: the code marker and the reuse check."""
    built: argparse.ArgumentParser = commands.add_parser(COMMAND_BUILT, parents=[where], help="a Task's tests passed")
    built.add_argument("--task", required=True, help="the Task")
    built.add_argument("--story", help="the Task's Story")
    built.add_argument("--repository", required=True, help="the repository the Task built in")
    built.add_argument("--commit", required=True, help="the commit that holds the built code")
    built.add_argument("--ref", required=True, help="the branch that holds the commit")
    built.add_argument("--elements", nargs="+", help="the elements the Task built")
    deployed: argparse.ArgumentParser = commands.add_parser(
        COMMAND_DEPLOYED,
        parents=[where],
        help="a Story's deploy to AWS dev was verified",
    )
    deployed.add_argument("--story", required=True, help="the Story")
    deployed.add_argument("--repository", help="the Story's repository, which holds the stacks named")
    deployed.add_argument("--commit", required=True, help="the commit deployed")
    deployed.add_argument("--stacks", nargs="+", help="the names of the stacks verified")
    merged: argparse.ArgumentParser = commands.add_parser(
        COMMAND_MERGED,
        parents=[where],
        help="a Story's pull request merged",
    )
    merged.add_argument("--story", required=True, help="the Story")
    merged.add_argument("--ref", required=True, help="the default branch the code is on now")
    merged.add_argument("--pr", help="the pull request")
    trusted: argparse.ArgumentParser = commands.add_parser(
        COMMAND_STORY_BUILT,
        parents=[where],
        help="the rows whose trusted code a Story built, with the headings that describe them",
    )
    trusted.add_argument("--story", required=True, help="the Story")
    reuse: argparse.ArgumentParser = commands.add_parser(
        "check-reuse",
        parents=[where],
        help="check the files a Task changed against the shared capabilities it must use",
    )
    reuse.add_argument("--task", required=True, help="the Task")
    reuse.add_argument("--worktree", required=True, help="the worktree the Task changed")
    reuse.add_argument("--files", nargs="+", help="the changed files; default: what git reports changed")
    reuse.add_argument("--elements", nargs="+", help="the elements the Task builds; default: read from its bead")
    reuse.add_argument("--repository", help="also guard the capabilities of every element of this repository")
    reuse.add_argument("--task-file", help="a file holding what `bd show <task> --json` printed, read in place of bd")
    reuse.add_argument("--control", help=f"the control repository bd runs in; default: {CONTROL_REPO_ENV}")


def add_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
    arch: argparse.ArgumentParser,
    who: argparse.ArgumentParser,
) -> None:
    """Add this module's sub-commands to the command line.

    Args:
        commands: The sub-command group of the ``atw-matrix`` parser.
        where: The options that name the matrix file.
        arch: The option that names the architecture root.
        who: The options that name the Epic and journal step a change is made for.

    """
    _design_parsers(commands, where, who)
    _review_parsers(commands, where, arch)
    _build_parsers(commands, where)
