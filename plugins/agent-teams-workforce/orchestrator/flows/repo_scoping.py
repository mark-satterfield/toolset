"""Read what the Epic's Stories build from the architect's result, and create a repository it needs and lacks.

What a Story builds is what the architect's result names, and nothing more: every
architecture-side element it lists under ``addedOrChangedElements``, which the Epic's
architecture adds or changes, and every existing element it names under
``unchangedWorkElements``, where the Epic has work that leaves the element's architecture as it
is, such as the wording of a page. Either list may be empty, and an Epic can have both. An
element is built in the stack the architecture side places it in
(``matrixtraverse.authority_holder``). An event has no home: it is built in each stack that
holds one of its producers, as one item per stack, and that item carries the event's
description and the producers in that stack as information, never as further work. The matrix
is used only to find those stacks, each stack's repository, the documents that describe each
element and the architecture-side dependencies between them. Everything else the Epic reaches
is context, never work. No session is started. A repository that a stack the Stories build in
lacks is named by the project's naming command, recorded on the stack, and created by the
``polyrepo`` tool, which takes its template from the name; a stack no Story builds in is never
touched.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple, TypedDict
from urllib.parse import urlparse

# The driver surface and the placement contract are defined once, in their skills.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "resource-naming" / "scripts"))
import hierarchy
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import (
    AUTHORITY_SIDE,
    FAMILY_DEPENDENCY,
    KIND_EVENT,
    KIND_STACK,
    LOCK_DIRECTORY,
    LOCK_SUFFIX,
    REL_DESCRIBED_BY,
    REL_MATCHES,
    REL_PUBLISHES,
    SIDE_REPOSITORY,
    Entry,
    EntryId,
    MatrixError,
    Relationship,
    RelationshipKind,
    family_kinds,
)
from matrixstore import Matrix, as_entry_id, matrix_path, read_matrix, update_matrix
from matrixtraverse import (
    ATTR_APP,
    ATTR_REPOSITORY,
    authority_holder,
    holder,
    stack_type,
)
from matrixwrite import commit, put
from naming_command import (
    NamingAnswer,
    NamingCommandError,
    check_repository,
    produced,
    require_naming_command,
    run_naming,
    violations_text,
)
from placement_contract import (
    KEY_ITEM_IDS,
    KEY_MISSING_REPOS,
    KEY_NAME,
    KEY_PLACEMENTS,
    KEY_PURPOSE,
    KEY_REPO_PATH,
    MissingRepo,
    Placement,
    PlacementRuling,
)
from target_contract import (
    KEY_MATRIX_ID,
    KIND_IMPLEMENTATION_GAP,
    DeltaItem,
    DeltaResult,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.handback import failure_for
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, NewStep, StepGroup, StepRun, file_artifact, value_artifact
from orchestrator.core.models import StepError
from orchestrator.core.tool_locks import file_lock, seconds
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.architecture_files import HUMAN_ACTION_STAGE, read_context, read_result
from orchestrator.flows.elaboration_files import (
    ARTIFACT_CREATION,
    ARTIFACT_ELEMENTS,
    ARTIFACT_MATRIX_COMMIT,
    ARTIFACT_REPOSITORIES,
    ARTIFACT_SPAN,
    SPEC_CONTEXT,
)
from orchestrator.flows.elaboration_support import REPO_SCOPING_PHASE, enter_phase
from orchestrator.flows.repo_placement import forbidden

if TYPE_CHECKING:
    from architecture_work_contract import ArchitectureResult
    from matrixwrite import CommitResult
    from step_journal_contract import Artifact, StepPlan

SPAN: Final = "atw-matrix epic --closure"
"""The script key of the span step."""
SPAN_DESCRIPTION: Final = "Read the repositories this Epic involves from the matrix"
SPAN_PURPOSE: Final = "The repository span and the entries each repository builds come from the matrix"
SPECS_PURPOSE: Final = "The repository has one reviewed spec set and one Story"
SPAN_FILE: Final = "repo-scoping.json"
ELEMENTS_FILE: Final = "span-elements.json"
"""The files the span step writes in the Epic's work directory: the placements and the items."""
CONTEXT_PURPOSE: Final = "The items this repository builds and the steps that specify them are known"
CREATION_STAGE: Final = "repo-creation"
CREATE_TIMEOUT_ENV: Final = "ATW_REPO_CREATE_TIMEOUT"
CREATE_TIMEOUT: Final = 3600.0
"""Seconds ``polyrepo create`` may take: its own environment setup alone may take 1800 and a synth 900."""
CREATE_LOCK_PREFIX: Final = "repo-create-"
"""The lock file of a repository's creation, beside the matrix's lock, is this prefix and the name."""
PRESENT_WHERE: Final[tuple[str, ...]] = ("disk", "github", "manifest")
"""Where a repository that exists is present: its clone, GitHub and the manifest."""
CREATE_PROBLEMS: Final[tuple[str, ...]] = (
    "environment_error",
    "format_error",
    "matrix_error",
    "ruleset_error",
    "beads_error",
    "gitnexus_error",
)
"""The steps of ``polyrepo create`` after the push to GitHub whose failure leaves the repository made."""
WEB_TYPE: Final = "web"
"""The stack type of a web front-end build, as the project's naming standard lists it."""
KEY_GITHUB: Final = "github"
KEY_URL: Final = "url"
"""An inventory record's GitHub listing, and the repository's URL in it."""
EVIDENCE_RESULT: Final = "architecture result"
"""The evidence of every item: the architect's result lists it under addedOrChangedElements or unchangedWorkElements."""
FIELD_ADDED_OR_CHANGED: Final = "addedOrChangedElements"
FIELD_UNCHANGED_WORK: Final = "unchangedWorkElements"
"""The fields of the architect's result that name what the Epic's Stories build."""
NO_BUILD_NEED: Final[frozenset[str]] = frozenset({REL_PUBLISHES, REL_MATCHES, "consumes", "routes"})
"""The dependency relationships that make no build need another: an event's producers, its rules and its targets."""
BUILD_DEPENDENCY_KINDS: Final[frozenset[RelationshipKind]] = frozenset(
    kind for kind in family_kinds(FAMILY_DEPENDENCY) if kind not in NO_BUILD_NEED
)
"""The dependency relationships that make one build need another.

Publishing an event and a rule matching an event make no build dependency; a rule's ``onBus``
and ``routesTo`` do.
"""
NAMING_REPOSITORY: Final = "repository"
NAMING_STACK: Final = "cdk-stack"
"""The naming command's kinds of a repository name and of the stack name it is converted from."""


DependsOn = TypedDict(
    "DependsOn",
    {
        "from": str,
        "kind": str,
        "to": str,
        "toKind": str,
        "side": str,
        "stack": str | None,
        "repository": str | None,
        "builtBy": str | None,
    },
)
"""One dependency of something a Story builds on something it does not build: context, never work.

``side`` is the side that states the relationship (a repository-side one is a hint read from
code); ``builtBy`` is the storyKey of another Story of the Epic whose items include ``to``.
"""


class BuildContext(TypedDict):
    """What a Story's Tasks depend on outside what the Story builds."""

    dependsOn: list[DependsOn]


@dataclass(frozen=True, slots=True)
class RepositoryStacks:
    """The stacks of the span that name one repository, with what the stacks say about it."""

    name: str
    stacks: tuple[EntryId, ...]
    apps: tuple[str, ...]
    """The ``app`` of each stack, without repeats."""
    types: tuple[str, ...]
    """The type of each stack, the last token of its name, without repeats: it marks a web front end."""
    purpose: str
    """The stacks' purposes, joined."""


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def inventory(tools: Tools, name: str | None = None) -> dict[str, JsonValue]:
    """Read the repository inventory and validate its row collection, without fetching any repository.

    Args:
        tools: The step's tools.
        name: The one repository to read (``polyrepo inventory --all --name``), wherever it is
            present; None reads every one on disk.

    Returns:
        The inventory object the ``polyrepo`` tool printed.

    """
    named: list[str] = ["--all", "--name", name] if name else []
    result = tools.polyrepo(["inventory", "--no-fetch", *named], stage=REPO_SCOPING_PHASE)
    value = json_object(json.loads(result.stdout))
    _objects(value["repos"])
    return value


def _naming_preflight(missing: Sequence[MissingRepo]) -> str | None:
    """Check, before any repository is created, that the naming command accepts every name to create.

    Returns:
        The owner fact that stops creation: each refused name with the naming command's violations;
        None when every name is accepted.

    """
    refused: list[str] = []
    for repo in missing:
        check = check_repository(repo[KEY_NAME])
        if not check.valid:
            refused.append(f"{check.name} ({check.problem})")
    if not refused:
        return None
    return (
        "The naming command refuses the repository names the matrix's stacks state: "
        + "; ".join(refused)
        + ". Correct each stack's repository attribute to a name the naming command gives."
    )


def _preflight(tools: Tools, owner: str) -> str | None:
    signed_in = tools.command(["gh", "auth", "status"], stage=CREATION_STAGE, check=False)
    if signed_in.exit:
        return "The GitHub CLI is not signed in on this machine; run gh auth login."
    membership = tools.command(
        ["gh", "api", f"user/memberships/orgs/{owner}", "--jq", ".state"],
        stage=CREATION_STAGE,
        check=False,
    )
    if membership.exit or membership.stdout.strip() != "active":
        return (
            f"The signed-in GitHub account is not an active member of {owner}; "
            "sign in with an active member account or arrange organisation membership."
        )
    return None


def _record_repository(stacks: Sequence[EntryId], created: str) -> None:
    """Record the repository that was created on each stack that named another.

    The fact is read from the repository that now exists, so it is stated from the repository
    side, which leaves each stack's own side, name and purpose as they are.
    """

    def change(matrix: Matrix) -> None:
        stack: EntryId
        for stack in stacks:
            put(matrix, KIND_STACK, SIDE_REPOSITORY, entry_id=stack, attributes={ATTR_REPOSITORY: created})

    update_matrix(matrix_path(None, os.environ), change)


def _create(missing: MissingRepo, tools: Tools, home: RepositoryStacks) -> dict[str, JsonValue]:
    """Create one repository with the ``polyrepo`` tool, in the app space its stacks name.

    The tool runs once, with no retry: a second attempt finds the repository it half made. Its
    success is judged from the JSON object it prints, not its exit status: the repository is made
    when the object names its absolute path and no ``error``, the error of a step that stops
    before or at the push to GitHub. A later step's failure (:data:`CREATE_PROBLEMS`) leaves the
    repository made and is kept in the outcome.

    A printed object that is not JSON, or names an ``error`` or no absolute path, fails the step.

    Returns:
        The path of the new clone, and the problems of the steps after the push.

    """
    name: str = missing[KEY_NAME]
    result = tools.polyrepo(
        ["create", name, "--space", home.apps[0]],
        stage=CREATION_STAGE,
        timeout=seconds(CREATE_TIMEOUT_ENV, CREATE_TIMEOUT),
        retry=False,
        check=False,
    )
    try:
        value = json_object(json.loads(result.stdout))
    except ValueError:
        raise tools.failure(CREATION_STAGE, OTHER_CAUSE, result.to_json()) from None
    path = check_type(value.get("path"), str | None)
    if value.get("error") or not path or not Path(path).is_absolute():
        raise tools.failure(CREATION_STAGE, OTHER_CAUSE, {**result.to_json(), "result": value})
    created = check_type(value.get("repo"), str | None)
    if created and created != name:
        tools.portfolio(CREATION_STAGE, _record_repository, home.stacks, created)
    problems: list[JsonValue] = [f"{key}: {value[key]}" for key in CREATE_PROBLEMS if value.get(key)]
    return {KEY_REPO_PATH: path, "existed": False, "problems": problems}


def _creation_lock(name: str) -> Path:
    """Name the lock file that one repository's creation holds, beside the matrix's lock.

    Returns:
        The lock file, named for the repository without case.

    """
    return matrix_path(None, os.environ).parent / LOCK_DIRECTORY / f"{CREATE_LOCK_PREFIX}{name.casefold()}{LOCK_SUFFIX}"


def _present(tools: Tools, name: str) -> dict[str, JsonValue] | None:
    """Read where a repository is present now, from a fresh inventory of that one name.

    Returns:
        Its path and where it is present (:data:`PRESENT_WHERE`); None when it is present nowhere.

    """
    folded: str = name.casefold()
    record = next(
        (r for r in _objects(inventory(tools, name)["repos"]) if check_type(r["name"], str).casefold() == folded),
        None,
    )
    if record is None:
        return None
    present = json_object(record["present"])
    where: dict[str, JsonValue] = {place: bool(present.get(place)) for place in PRESENT_WHERE}
    if not any(where.values()):
        return None
    return {**where, KEY_REPO_PATH: record.get("path")}


def _ensure_repository(
    missing: MissingRepo,
    tools: Tools,
    home: RepositoryStacks,
    owner: str,
    *,
    preflight_done: bool,
) -> tuple[dict[str, JsonValue], bool]:
    """Use the repository when it exists in full, or create it, under the lock of its creation.

    The inventory is read again under the lock, so a repository another Epic created while this
    one waited is used, not created twice. A repository is used only when it is cloned, on GitHub
    and in the manifest; one present in only some of them is an owner fact, since creating it
    again would fail on the part that exists.

    Returns:
        The outcome (the path, or the owner fact) and whether GitHub access was verified.

    """
    name: str = missing[KEY_NAME]
    with file_lock(_creation_lock(name), seconds(CREATE_TIMEOUT_ENV, CREATE_TIMEOUT) * 2):
        present = _present(tools, name)
        if present is not None:
            if all(present[place] for place in PRESENT_WHERE) and present[KEY_REPO_PATH]:
                return {KEY_REPO_PATH: present[KEY_REPO_PATH], "existed": True}, preflight_done
            lacking: str = ", ".join(place for place in PRESENT_WHERE if not present[place])
            fact: str = (
                f"The repository {name} was made only in part: it is not present on {lacking}. "
                "Complete it with the polyrepo-steward, or remove what was made, so it can be created again."
            )
            return {"error": fact, "ownerFact": True}, preflight_done
        if not preflight_done:
            need = _preflight(tools, owner)
            if need:
                return {"error": need, "ownerFact": True}, False
        return _create(missing, tools, home), True


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def create_repositories(
    ruling: PlacementRuling,
    tools: Tools,
    homes: Mapping[str, RepositoryStacks],
    owner: str,
    work: Path,
) -> dict[str, JsonValue]:
    """Create the repositories the span names and the inventory lacks, after verifying GitHub access.

    Args:
        ruling: The span, whose missing repositories are created.
        tools: The step's tools.
        homes: The stacks of the span by the repository each names (:func:`repository_stacks`).
        owner: The GitHub organisation the repositories are created in.
        work: The Epic's work directory, where the creation record is written.

    Returns:
        Measured creation results, or the owner fact that stopped creation: a repository name the
        naming command refuses (checked for every name before any is created) or missing GitHub access.

    Raises:
        StepError: A deterministic repository operation fails.
        ValueError: Repository output is invalid.
        OSError: A repository operation cannot access a required resource.
        KeyError: A required repository field is absent.

    """
    created: list[dict[str, JsonValue]] = []
    failures: list[dict[str, JsonValue]] = []
    refused: str | None = _naming_preflight(ruling[KEY_MISSING_REPOS])
    if refused:
        result_refused: dict[str, JsonValue] = json_object({
            "created": created,
            "failures": [{"error": refused, "ownerFact": True}],
        })
        write_json(work / "repo-creation.json", result_refused)
        return result_refused
    preflight_done = False
    for missing in ruling[KEY_MISSING_REPOS]:
        facts: dict[str, JsonValue] = {
            KEY_NAME: missing[KEY_NAME],
            KEY_ITEM_IDS: list(missing[KEY_ITEM_IDS]),
        }
        try:
            outcome, preflight_done = _ensure_repository(
                missing,
                tools,
                homes[missing[KEY_NAME]],
                owner,
                preflight_done=preflight_done,
            )
        except (StepError, ValueError, OSError, KeyError) as exc:
            failures.append(
                json_object({
                    **facts,
                    "error": list(exc.evidence) if isinstance(exc, StepError) else str(exc),
                    "ownerFact": False,
                    "failure": failure_for(CREATION_STAGE, exc, agent_started=False),
                }),
            )
            write_json(work / "repo-creation.json", {"created": created, "failures": failures})
            raise
        if outcome.get("ownerFact"):
            failures.append({**facts, **outcome})
            break
        created.append({**facts, **outcome})
    result = json_object({"created": created, "failures": failures})
    write_json(work / "repo-creation.json", result)
    return result


def _stated_id(stated: str) -> EntryId | None:
    """Read one id the architect's result states.

    Returns:
        The id, or None when the text does not have the form of an entry id.

    """
    try:
        return as_entry_id(stated.strip())
    except MatrixError:
        return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_build_entries(added_or_changed: Sequence[str]) -> list[EntryId]:
    """List what the Epic's Stories build: what the architecture adds or changes, and where unchanged work lands.

    Only what the architect's result states is built. An event's producers are not added: the
    event is built in each stack that holds one of them (:func:`placements`), and its item names
    the producers in that stack as information (:func:`story_builds`).

    Args:
        added_or_changed: The ids the architect's result lists under ``addedOrChangedElements``
            and ``unchangedWorkElements``.

    Returns:
        The stated ids, each once, in id order. A text that is not an entry id is left out
        (:func:`story_build_problems` reports it).

    """
    return sorted({found for text in added_or_changed if (found := _stated_id(text)) is not None})


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def placements(matrix: Matrix, entry_id: EntryId) -> list[EntryId]:
    """Name the stacks an entry is built in.

    Args:
        matrix: The matrix.
        entry_id: The entry's id.

    Returns:
        For an event, each stack that holds one of its architecture-side producers
        (``Matrix.publisher_stacks``), in id order; for any other entry, the stack the
        architecture side places it in (:func:`matrixtraverse.authority_holder`). Empty when
        there is none or the matrix does not hold the entry.

    """
    entry: Entry | None = matrix.find(entry_id)
    if entry is None:
        return []
    if entry.kind == KIND_EVENT:
        return sorted(matrix.publisher_stacks(entry_id))
    stack: EntryId | None = authority_holder(matrix, entry_id)
    return [] if stack is None else [stack]


def _entry_problem(entry: Entry) -> str | None:
    """Check that an entry is something a Story builds.

    Returns:
        One sentence naming the first rule the entry breaks; None when it is an
        architecture-side element and, when an event, one with a description.

    """
    if entry.side != AUTHORITY_SIDE:
        return f"{entry.id} is on the {entry.side} side; what a Story builds is what the {AUTHORITY_SIDE} side states"
    if entry.kind == KIND_EVENT and not entry.purpose.strip():
        return f"{entry.id} is an event with no description; an event's purpose is its description"
    return None


def _stack_problem(matrix: Matrix, entry: Entry) -> str | None:
    """Check the stacks an entry is built in.

    Returns:
        One sentence when it is built in no stack; None otherwise.

    """
    stacks: list[EntryId] = placements(matrix, entry.id)
    if not stacks and entry.kind == KIND_EVENT:
        return f"the {AUTHORITY_SIDE} side states no producer of {entry.id} that is homed in a stack"
    if not stacks:
        return f"the {AUTHORITY_SIDE} side states no home for {entry.id}"
    return None


def _build_problem(matrix: Matrix, entry_id: EntryId) -> str | None:
    """Check one thing a Story is to build against what the architecture side states.

    Returns:
        One sentence naming the first rule the entry breaks; None when a Story can build it.

    """
    entry: Entry | None = matrix.find(entry_id)
    if entry is None:
        return f"{entry_id}: the matrix holds no such entry; record it with atw-matrix put"
    return _entry_problem(entry) or _stack_problem(matrix, entry)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_build_problems(
    matrix: Matrix,
    bead: str,
    added_or_changed: Sequence[str],
    field: str = FIELD_ADDED_OR_CHANGED,
) -> list[str]:
    """Check what the architecture says the Epic's Stories build.

    Args:
        matrix: The matrix.
        bead: The Epic, named in the sentences.
        added_or_changed: The ids the architect's result lists under ``field``.
        field: The field of the architect's result the ids come from, named in the sentences.

    Returns:
        One sentence per text that is not an entry id, and per entry of
        :func:`story_build_entries` that the matrix lacks, that is not on the architecture
        side, that is an event with no description, or that is built in no stack. Empty when the
        Stories can build every one.

    """
    unread: list[str] = [
        f"{bead}: {field} names {text!r}, which is not a matrix id"
        for text in added_or_changed
        if _stated_id(text) is None
    ]
    entries: list[EntryId] = story_build_entries(added_or_changed)
    found: list[str | None] = [_build_problem(matrix, entry_id) for entry_id in entries]
    return [*unread, *(problem for problem in found if problem is not None)]


def _requires(matrix: Matrix, entry_id: EntryId, own: str, ids: Mapping[EntryId, Sequence[str]]) -> list[str]:
    """List the build items one item needs built first.

    Only the dependency relationships the architecture side states count; a repository-side
    relationship never makes a ``requires``, and a dependency on something no Story of the Epic
    builds is context, not an item. Publishing an event and a rule matching an event make no
    need (:data:`BUILD_DEPENDENCY_KINDS`).

    Returns:
        The ids of the items that build what its architecture-side dependency relationships
        reach directly, in the order found and without repeats; never the item itself.

    """
    reached: list[str] = [
        needed
        for relationship in matrix.outgoing(entry_id, BUILD_DEPENDENCY_KINDS)
        if relationship.side == AUTHORITY_SIDE
        for needed in ids.get(relationship.end, ())
        if needed != own
    ]
    return list(dict.fromkeys(reached))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_name(matrix: Matrix, stack: EntryId) -> str:
    """Name the repository that holds a stack.

    Args:
        matrix: The matrix.
        stack: The stack's id.

    Returns:
        The stack's ``repository`` attribute; when it states none, the repository name the
        project's naming command converts the stack's name to (``name convert <stack> --from
        cdk-stack --to repository``). Never the raw stack name.

    Raises:
        ValueError: The stack states no repository and the naming command cannot name one.

    """
    entry: Entry = matrix.entry(stack)
    stated: JsonValue = entry.attributes.get(ATTR_REPOSITORY)
    if isinstance(stated, str) and stated:
        return stated
    message: str
    try:
        answer: NamingAnswer = run_naming([
            "name",
            "convert",
            entry.name,
            "--from",
            NAMING_STACK,
            "--to",
            NAMING_REPOSITORY,
        ])
    except NamingCommandError as error:
        message = f"{stack} names no repository and the naming command cannot name one: {error}"
        raise ValueError(message) from error
    name: str | None = produced(answer)
    if name is None:
        message = (
            f"{stack} names no repository and the naming command cannot name one: {violations_text(answer.document)}"
        )
        raise ValueError(message)
    return name


def _text_or_none(value: JsonValue) -> str | None:
    """Read an attribute that is a non-empty string.

    Returns:
        The string, or None.

    """
    return value if isinstance(value, str) and value else None


class Placed(NamedTuple):
    """One item of what a Story builds: an entry and the stack it is built in."""

    entry_id: EntryId
    stack: EntryId


def _build_item(matrix: Matrix, placed: Placed, item_id: str, ids: Mapping[EntryId, Sequence[str]]) -> DeltaItem:
    """Render one thing a Story builds in one stack as its item.

    Returns:
        The item: its id, the entry's name and matrix id, the documents that describe it, the
        stack's repository, the items it requires, ``state`` ``built`` when the entry is
        built and tested as the matrix records it (``hierarchy.STATE_VERIFIED``), and, for
        an event, its description and its producers in the stack.

    """
    item: DeltaItem = {
        "id": item_id,
        "element": matrix.entry(placed.entry_id).name,
        "matrixId": placed.entry_id,
        "views": list(dict.fromkeys(stated.end for stated in matrix.outgoing(placed.entry_id, (REL_DESCRIBED_BY,)))),
        "kind": KIND_IMPLEMENTATION_GAP,
        "repository": repository_name(matrix, placed.stack),
        "requires": _requires(matrix, placed.entry_id, item_id, ids),
        "requiredBy": [],
        "evidence": [placed.entry_id, EVIDENCE_RESULT],
    }
    if matrix.entry(placed.entry_id).verified is not None:
        item["state"] = hierarchy.STATE_VERIFIED
    if matrix.entry(placed.entry_id).kind != KIND_EVENT:
        return item
    return {**item, **_event_facts(matrix, placed, ids)}


class EventFacts(TypedDict):
    """What an event's item states about the event, as information, never as work."""

    trigger: str
    """The event's description: the event entry's purpose."""
    publishedBy: list[str]
    """Each producer in the item's stack: the id of the item that builds it, else its matrix id."""


def _event_facts(matrix: Matrix, placed: Placed, ids: Mapping[EntryId, Sequence[str]]) -> EventFacts:
    """Read an event's description and its producers in one stack.

    Returns:
        The event entry's purpose, and each architecture-side producer homed in the stack, as
        the id of the item in the same item set that builds it, or as its matrix id when no
        item builds it.

    """
    return {
        "trigger": matrix.entry(placed.entry_id).purpose,
        "publishedBy": [
            next(iter(ids.get(producer, ())), producer)
            for producer in matrix.publishers(placed.entry_id)
            if matrix.home(producer) == placed.stack
        ],
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_builds(
    matrix: Matrix,
    bead: str,
    added_or_changed: Sequence[str],
    unchanged_work: Sequence[str],
) -> list[DeltaItem]:
    """List what the Epic's Stories build, in the shape the spec and Task steps read.

    Args:
        matrix: The matrix.
        bead: The Epic.
        added_or_changed: The ids the architect's result lists under ``addedOrChangedElements``.
        unchanged_work: The ids the architect's result lists under ``unchangedWorkElements``.

    Returns:
        One item per entry of :func:`story_build_entries` of both lists and stack it is built in
        (:func:`placements`): its id, the entry's name and matrix id, the documents that
        describe it, the stack's repository (:func:`repository_name`), and the items it
        requires and is required by through the architecture-side dependency relationships
        between them. An event's item also carries ``trigger``, the event's description, and
        ``publishedBy``, its producers in that stack (:func:`_event_facts`).

    Raises:
        StepError: :func:`story_build_problems` reports a problem in either list; the evidence
            names each.

    """
    problems: list[str] = [
        *story_build_problems(matrix, bead, added_or_changed, FIELD_ADDED_OR_CHANGED),
        *story_build_problems(matrix, bead, unchanged_work, FIELD_UNCHANGED_WORK),
    ]
    if problems:
        raise StepError(SPAN, OTHER_CAUSE, tuple(problems))
    placed: list[Placed] = [
        Placed(entry_id, stack)
        for entry_id in story_build_entries([*added_or_changed, *unchanged_work])
        for stack in placements(matrix, entry_id)
    ]
    item_ids_of: dict[Placed, str] = {built: f"E{index}" for index, built in enumerate(placed, 1)}
    ids: dict[EntryId, list[str]] = {}
    for built, item_id in item_ids_of.items():
        ids.setdefault(built.entry_id, []).append(item_id)
    items: list[DeltaItem] = [_build_item(matrix, built, item_id, ids) for built, item_id in item_ids_of.items()]
    by_id: dict[str, DeltaItem] = {item["id"]: item for item in items}
    for item in items:
        for needed in item.get("requires", []):
            by_id[needed].setdefault("requiredBy", []).append(item["id"])
    return items


def _item_stacks(matrix: Matrix, entry_id: EntryId, repository: str | None) -> list[EntryId]:
    """Name the stacks one item builds its entry in.

    Returns:
        The entry's stacks (:func:`placements`); for an event whose item names a repository,
        only the stacks that repository holds.

    Raises:
        ValueError: The entry is built in no stack, or in none the item's repository holds.

    """
    stacks: list[EntryId] = placements(matrix, entry_id)
    if repository is not None and matrix.entry(entry_id).kind == KIND_EVENT:
        stacks = [stack for stack in stacks if repository_name(matrix, stack).casefold() == repository.casefold()]
    if not stacks:
        message: str = f"the {AUTHORITY_SIDE} side places {entry_id} in no stack of {repository or 'any repository'}"
        raise ValueError(message)
    return stacks


def _record_repository_names(items: Sequence[DeltaItem]) -> list[EntryId]:
    """Record on each stack that names no repository the name its Story's repository is given.

    The name comes from the naming command (:func:`repository_name`), so the stack and the
    repository created for it carry one name. It is written on the architecture side, in one
    matrix change.

    Returns:
        The stacks that took a name.

    """

    def change(matrix: Matrix) -> list[EntryId]:
        stacks: set[EntryId] = {
            stack for item in items for stack in _item_stacks(matrix, as_entry_id(item.get("matrixId", "")), None)
        }
        unnamed: list[EntryId] = sorted(
            stack for stack in stacks if _text_or_none(matrix.entry(stack).attributes.get(ATTR_REPOSITORY)) is None
        )
        named: dict[EntryId, str] = {stack: repository_name(matrix, stack) for stack in unnamed}
        for stack, name in named.items():
            put(matrix, KIND_STACK, AUTHORITY_SIDE, entry_id=stack, attributes={ATTR_REPOSITORY: name})
        return unnamed

    return update_matrix(matrix_path(None, os.environ), change)


def _stack_of(matrix: Matrix, entry_id: EntryId) -> tuple[EntryId | None, str | None]:
    """Name the stack of an entry a Story depends on, and that stack's repository.

    Returns:
        The stack the architecture side places an architecture-side entry in, or the stack the
        repositories hold a repository-side entry in (a hint read from code); and the stack's
        ``repository``; None for either the matrix does not state.

    """
    entry: Entry | None = matrix.find(entry_id)
    if entry is None:
        return None, None
    stack: EntryId | None = (
        authority_holder(matrix, entry_id) if entry.side == AUTHORITY_SIDE else holder(matrix, entry_id)
    )
    found: Entry | None = None if stack is None else matrix.find(stack)
    return stack, None if found is None else _text_or_none(found.attributes.get(ATTR_REPOSITORY))


def _depends_on(matrix: Matrix, relationship: Relationship, built_by: Mapping[EntryId, str]) -> DependsOn:
    """Render one dependency of something a Story builds on something it does not build.

    Returns:
        The relationship's ends, kind and side, the far end's kind, stack and repository, and
        the other Story of the Epic that builds the far end, if one does.

    """
    stack: EntryId | None
    repository: str | None
    stack, repository = _stack_of(matrix, relationship.end)
    far: Entry | None = matrix.find(relationship.end)
    return {
        "from": relationship.start,
        "kind": relationship.kind,
        "to": relationship.end,
        "toKind": "" if far is None else far.kind,
        "side": relationship.side,
        "stack": stack,
        "repository": repository,
        "builtBy": built_by.get(relationship.end),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def build_context(
    matrix: Matrix,
    built: Sequence[JsonValue],
    all_items: Mapping[str, Sequence[JsonValue]],
) -> BuildContext:
    """List what a Story's Tasks depend on outside what the Story builds: context, never work.

    Args:
        matrix: The matrix.
        built: The items of what this Story builds.
        all_items: The items of every Story of the Epic, by the Story's storyKey.

    Returns:
        ``dependsOn``: each dependency relationship of :data:`BUILD_DEPENDENCY_KINDS`, on either
        side, that starts at an entry this Story builds and ends at one it does not build, with
        the side that states it, the far end's stack and repository, and the other Story that
        builds the far end.

    """
    own: set[EntryId] = set(item_ids(built))
    built_by: dict[EntryId, str] = {
        entry_id: story for story, items in all_items.items() for entry_id in item_ids(items) if entry_id not in own
    }
    dependencies: list[DependsOn] = [
        _depends_on(matrix, relationship, built_by)
        for entry_id in sorted(own)
        for relationship in matrix.outgoing(entry_id, BUILD_DEPENDENCY_KINDS)
        if relationship.end not in own
    ]
    return {"dependsOn": dependencies}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def item_ids(items: Sequence[JsonValue]) -> list[EntryId]:
    """Read the matrix ids of some items.

    An id that does not have the form of an entry id raises ``MatrixError`` from ``as_entry_id``.

    Args:
        items: Items as the span step wrote them.

    Returns:
        The id of the entry each item builds, in order and without repeats.

    """
    return list(
        dict.fromkeys(
            as_entry_id(check_type(json_object(item)[KEY_MATRIX_ID], str))
            for item in items
            if KEY_MATRIX_ID in json_object(item)
        ),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def item_stacks(matrix: Matrix, items: Sequence[JsonValue]) -> dict[EntryId, list[EntryId]]:
    """Group the entries some items build by the stack that holds each.

    An id the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``, and an entry
    built in no stack of its item's repository raises ``ValueError``.

    Args:
        matrix: The matrix.
        items: Items as the span step wrote them.

    Returns:
        Each stack the items build in (for an event, each stack of its item's repository that
        holds one of its producers), in id order, with the entries of the items it holds.

    """
    grouped: dict[EntryId, list[EntryId]] = {}
    placed: list[tuple[EntryId, EntryId]] = [
        (stack, entry_id)
        for item in items
        if KEY_MATRIX_ID in (fields := json_object(item))
        for entry_id in (as_entry_id(check_type(fields[KEY_MATRIX_ID], str)),)
        for stack in _item_stacks(matrix, entry_id, _text_or_none(fields.get("repository")))
    ]
    for stack, entry_id in placed:
        grouped.setdefault(stack, [])
        if entry_id not in grouped[stack]:
            grouped[stack].append(entry_id)
    return {stack: grouped[stack] for stack in sorted(grouped)}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_stacks(matrix: Matrix, items: Sequence[DeltaItem]) -> dict[str, RepositoryStacks]:
    """Group the stacks of some items by the repository each names.

    An entry built in no stack of its item's repository raises ``ValueError``.

    Args:
        matrix: The matrix.
        items: What the Epic's Stories build (:func:`story_builds`).

    Returns:
        Each repository name with the stacks the Stories build in that it holds, their apps,
        their types and their purposes.

    """
    stacks: dict[str, dict[EntryId, Entry]] = {}
    item: DeltaItem
    for item in items:
        repository: str | None = item.get("repository")
        homes: list[EntryId] = _item_stacks(matrix, as_entry_id(item.get("matrixId", "")), repository)
        found: dict[str, EntryId] = {repository or repository_name(matrix, home): home for home in homes}
        for name, home in found.items():
            stacks.setdefault(name, {})[home] = matrix.entry(home)
    grouped: dict[str, RepositoryStacks] = {}
    for name, held in stacks.items():
        ordered: list[Entry] = [held[stack] for stack in sorted(held)]
        apps: list[str] = [app for stack in ordered if isinstance(app := stack.attributes.get(ATTR_APP), str)]
        grouped[name] = RepositoryStacks(
            name=name,
            stacks=tuple(stack.id for stack in ordered),
            apps=tuple(dict.fromkeys(apps)),
            types=tuple(dict.fromkeys(stack_type(stack.name) for stack in ordered)),
            purpose=" ".join(dict.fromkeys(stack.purpose for stack in ordered if stack.purpose)),
        )
    return grouped


def _missing(home: RepositoryStacks, built: list[str]) -> MissingRepo:
    """Describe a repository to create, from the stacks that name it.

    Returns:
        The repository's name, the stacks' purpose and the items of what its Story builds.

    Raises:
        StepError: The stacks have more than one app or name none.

    """
    if len(home.apps) != 1:
        evidence: str = (
            f"{home.name} does not exist, and its stacks {', '.join(home.stacks)} have the apps "
            f"{', '.join(home.apps) or 'none'}: a repository is created in one app space"
        )
        raise StepError(SPAN, OTHER_CAUSE, (evidence,))
    return {
        KEY_NAME: home.name,
        KEY_PURPOSE: home.purpose,
        KEY_ITEM_IDS: built,
    }


def _ruling(
    run: StepRun,
    items: list[DeltaItem],
    homes: Mapping[str, RepositoryStacks],
    repositories: Sequence[dict[str, JsonValue]],
) -> PlacementRuling:
    """Group what the Stories build by the repository of the stack each item is built in.

    Returns:
        The span in the placement contract's shape: one placement per repository, with its path
        when the inventory has it, and one missing repository per name it lacks.

    Raises:
        StepError: A repository may hold no product entry, or a missing repository cannot be
            created from what its stacks and the polyrepo-steward's records state.

    """
    live: dict[str, dict[str, JsonValue]] = {check_type(repo["name"], str).casefold(): repo for repo in repositories}
    control: Path = env_path(CONTROL_REPO_ENV)
    arch: Path = Path(check_type(run.context.args[dispatch_arguments().KEY_ARCH_PATH], str)).resolve()
    grouped: dict[str, list[str]] = {}
    for item in items:
        grouped.setdefault(check_type(item.get("repository"), str), []).append(item["id"])
    ruling: PlacementRuling = {
        KEY_PLACEMENTS: [],
        KEY_MISSING_REPOS: [],
        "noCode": [],
        "spanRationale": "The repository of each entry's stack, as the matrix records it.",
    }
    for name, built in grouped.items():
        known: JsonValue = live.get(name.casefold(), {}).get("path")
        path: str | None = str(Path(known).resolve()) if isinstance(known, str) and known else None
        if path is not None and forbidden(Path(path), control, arch):
            raise StepError(SPAN, OTHER_CAUSE, (f"{name} at {path} may hold no product entry",))
        placement: Placement = {
            KEY_REPO_PATH: path,
            "repoName": name,
            KEY_ITEM_IDS: built,
            "frontend": WEB_TYPE in homes[name].types,
            "rationale": "The matrix records this repository on the stacks that hold these entries.",
        }
        ruling[KEY_PLACEMENTS].append(placement)
        if path is None:
            ruling[KEY_MISSING_REPOS].append(_missing(homes[name], built))
    return ruling


def _spec_steps(run: StepRun, ruling: PlacementRuling, repos: list[str]) -> tuple[StepGroup, ...]:
    """Plan one container per repository of the span, each with its first step, after the span step.

    Returns:
        The group, or nothing for an empty span. A container is named for its repository; its
        first step gathers what the repository builds and plans the repository's other steps.

    """
    slugs: dict[str, str] = check_type(
        run.tools.portfolio(SPAN, hierarchy.repo_slugs, repos),
        dict[str, str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    frontend: set[str] = {
        check_type(placement[KEY_REPO_PATH], str) for placement in ruling[KEY_PLACEMENTS] if placement["frontend"]
    }
    steps: list[NewStep] = []
    for index, (repo, slug) in enumerate(slugs.items(), 1):
        name: str = Path(repo).name
        first: StepPlan = {
            "description": f"Gather what {name} builds",
            "purpose": CONTEXT_PURPOSE,
            "script": SPEC_CONTEXT,
            "inputs": [run.step["id"], *run.step.get("inputs", [])],
        }
        params: dict[str, JsonValue] = {
            "repoPath": repo,
            "slug": slug,
            "storyKey": f"S{index}",
            "frontend": repo in frontend,
        }
        container: StepPlan = {"description": name, "purpose": SPECS_PURPOSE}
        steps.append(NewStep(container, children=(NewStep(first, params),)))
    return (StepGroup(tuple(steps)),) if steps else ()


def _owner(repositories: Sequence[dict[str, JsonValue]]) -> str:
    """Read the GitHub organisation repositories are created in: the owner of the inventory's repositories on GitHub.

    Returns:
        The organisation's name.

    Raises:
        StepError: The inventory's repositories on GitHub name no owner, or more than one.

    """
    owners: set[str] = set()
    for repo in repositories:
        github: JsonValue = repo.get(KEY_GITHUB)
        if isinstance(github, dict) and isinstance(github.get(KEY_URL), str):
            owners.add(urlparse(check_type(github[KEY_URL], str)).path.strip("/").split("/")[0])
    owners.discard("")
    if len(owners) != 1:
        message: str = (
            f"the repository inventory names {len(owners)} GitHub owners ({', '.join(sorted(owners)) or 'none'}), "
            "so the organisation a repository is created in is not known"
        )
        raise StepError(HUMAN_ACTION_STAGE, OTHER_CAUSE, (message,))
    return owners.pop()


def _read_story_builds(run: StepRun) -> tuple[Matrix, list[DeltaItem]]:
    """Read what the Epic's Stories build, and name the repository of each stack that names none.

    What the Stories build is what the architect's result adds or changes
    (``addedOrChangedElements``) and the existing elements it names as where the Epic's work
    that leaves them unchanged lands (``unchangedWorkElements``).

    Returns:
        The matrix as it is after the names are recorded, and the items (:func:`story_builds`).

    Raises:
        StepError: The architect's result names nothing a Story builds in.

    """
    result: ArchitectureResult = read_result(run, read_context(run))
    matrix: Matrix = run.tools.portfolio(SPAN, read_matrix, matrix_path(None, os.environ))
    items: list[DeltaItem] = run.tools.portfolio(
        SPAN,
        story_builds,
        matrix,
        run.bead,
        result[FIELD_ADDED_OR_CHANGED],
        result[FIELD_UNCHANGED_WORK],
    )
    if not items:
        message: str = (
            f"the architect's result for {run.bead} names nothing a Story builds in: "
            f"{FIELD_ADDED_OR_CHANGED} and {FIELD_UNCHANGED_WORK} are both empty"
        )
        raise StepError(SPAN, OTHER_CAUSE, (message,))
    run.tools.portfolio(SPAN, _record_repository_names, items)
    return run.tools.portfolio(SPAN, read_matrix, matrix_path(None, os.environ)), items


def _commit_matrix(run: StepRun) -> list[Artifact]:
    """Commit and push the matrix file, so what the span recorded in it is in the control repository.

    Returns:
        The matrix commit, when one was made or pushed; otherwise nothing.

    """
    recorded: CommitResult = run.tools.portfolio(SPAN, commit, matrix_path(None, os.environ), str(run.bead))
    if recorded["committed"] or recorded["pushed"]:
        return [value_artifact(ARTIFACT_MATRIX_COMMIT, recorded["head"])]
    return []


@script_step(SPAN)
def span(run: StepRun) -> Completion:
    """Read what the Epic's Stories build from the architect's result and plan one spec step per repository.

    What the Stories build is the architect's ``addedOrChangedElements`` and the existing elements
    the result names as where the Epic's work that leaves them unchanged lands
    (``unchangedWorkElements``), and nothing more (:func:`story_builds`). Nothing is recorded in the
    matrix but the name of the repository of a stack the Stories build in that names none (from the
    naming command), and the name of a repository that was created under another name than the one
    its stacks stated. The matrix file is then committed and pushed, so what the span recorded is
    in the control repository before any later step reads it.

    Returns:
        The span file, the elements file, the repository paths, the creation record when a
        repository had to be created, and the matrix commit when one was made or pushed; with the
        spec steps planned after this step.

    Raises:
        StepError: The naming command is not configured or cannot run (checked before any other
            work), the architecture adds or changes nothing to build, what it lists cannot be
            built (:func:`story_build_problems`), or a repository can be created only after the
            owner acts (a name the naming command refuses, or GitHub access).

    """
    enter_phase(run.context, run.agents.emit, REPO_SCOPING_PHASE, SPAN)
    try:
        require_naming_command()
    except NamingCommandError as error:
        raise StepError(HUMAN_ACTION_STAGE, OTHER_CAUSE, (str(error),)) from error
    matrix: Matrix
    items: list[DeltaItem]
    matrix, items = _read_story_builds(run)
    work: Path = run.context.work
    homes: dict[str, RepositoryStacks] = run.tools.portfolio(SPAN, repository_stacks, matrix, items)
    repositories: list[dict[str, JsonValue]] = _objects(inventory(run.tools)["repos"])
    ruling: PlacementRuling = _ruling(run, items, homes, repositories)
    elements: DeltaResult = {
        "ok": True,
        "refusals": [],
        "summary": {"ok": True, "refusals": [], "items": len(items)},
        "items": items,
    }
    write_json(work / ELEMENTS_FILE, elements)
    artifacts: list[Artifact] = [file_artifact(ARTIFACT_ELEMENTS, work / ELEMENTS_FILE)]
    if ruling[KEY_MISSING_REPOS]:
        owner: str = _owner(repositories)
        creation: dict[str, JsonValue] = create_repositories(ruling, run.tools, homes, owner, work)
        artifacts.append(file_artifact(ARTIFACT_CREATION, work / "repo-creation.json"))
        failures: list[dict[str, JsonValue]] = _objects(creation["failures"])
        if failures:
            raise StepError(HUMAN_ACTION_STAGE, OTHER_CAUSE, tuple(str(item["error"]) for item in failures))
        made: dict[str, str] = {
            check_type(repo[KEY_NAME], str).casefold(): check_type(repo[KEY_REPO_PATH], str)
            for repo in _objects(creation["created"])
        }
        for placement in ruling[KEY_PLACEMENTS]:
            placement[KEY_REPO_PATH] = placement[KEY_REPO_PATH] or made[placement["repoName"].casefold()]
    artifacts.extend(_commit_matrix(run))
    span_path: Path = work / SPAN_FILE
    write_json(span_path, ruling)
    repos: list[str] = list(dict.fromkeys(check_type(p[KEY_REPO_PATH], str) for p in ruling[KEY_PLACEMENTS]))
    kept: list[JsonValue] = list(repos)
    return Completion(
        artifacts=(file_artifact(ARTIFACT_SPAN, span_path), *artifacts, value_artifact(ARTIFACT_REPOSITORIES, kept)),
        add=_spec_steps(run, ruling, repos),
    )
