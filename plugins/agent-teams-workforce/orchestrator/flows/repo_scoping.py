"""Read what the Epic's Stories build from the architect's result, and create a repository it needs and lacks.

What a Story builds is what the Epic's architecture adds or changes: the services, components,
infrastructure and events the architect's result lists under ``addedOrChangedElements``. An event
is built as part of the service or component that publishes it, so its architecture-side
publishers are built with it. The matrix is used only to find the stack each is placed in on the
architecture side (``matrixtraverse.authority_holder``), that stack's repository, the documents
that describe it and the architecture-side dependencies between them. Everything else the Epic
reaches is context, never work. No session is started. A repository that a stack the Stories
build in lacks is named by the project's naming rules, recorded on the stack, and created from
the template named for the stack's type; a stack no Story builds in is never touched.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

# The driver surface and the placement contract are defined once, in their skills.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "resource-naming" / "scripts"))
import hierarchy
import naming
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import (
    AUTHORITY_SIDE,
    FAMILY_DEPENDENCY,
    KIND_COMPONENT,
    KIND_EVENT,
    KIND_INFRASTRUCTURE,
    KIND_SERVICE,
    KIND_STACK,
    REL_CONSUMES,
    REL_DESCRIBED_BY,
    SIDE_REPOSITORY,
    Entry,
    EntryId,
    EntryKind,
    MatrixError,
    Relationship,
    family_kinds,
)
from matrixquery import Capability, UsesResult, uses_view
from matrixstore import ATTR_EXTERNAL_SOURCE, Matrix, as_entry_id, matrix_path, read_matrix, update_matrix
from matrixtraverse import (
    ATTR_APP,
    ATTR_REPOSITORY,
    authority_holder,
    holder,
    stack_type,
)
from matrixwrite import put
from placement_contract import (
    KEY_ITEM_IDS,
    KEY_MISSING_REPOS,
    KEY_NAME,
    KEY_PLACEMENTS,
    KEY_PURPOSE,
    KEY_REPO_PATH,
    KEY_TEMPLATE,
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
from orchestrator.core.frontmatter import yaml_safe_load
from orchestrator.core.handback import failure_for
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, NewStep, StepGroup, StepRun, file_artifact, value_artifact
from orchestrator.core.models import StepError
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.architecture_files import HUMAN_ACTION_STAGE, read_context, read_result
from orchestrator.flows.elaboration_files import (
    ARTIFACT_CREATION,
    ARTIFACT_ELEMENTS,
    ARTIFACT_REPOSITORIES,
    ARTIFACT_SPAN,
    SPEC_CONTEXT,
)
from orchestrator.flows.elaboration_support import REPO_SCOPING_PHASE, enter_phase
from orchestrator.flows.repo_placement import forbidden

if TYPE_CHECKING:
    from step_journal_contract import StepPlan

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
WEB_TYPE: Final = "web"
"""The stack type of a web front-end build, as the project's naming standard lists it."""
MARKETING_APP: Final = "marketing"
"""The app whose repositories no pipeline step creates or changes."""
OWNER_KEY: Final = "github_owner"
BUILT_KINDS: Final[frozenset[EntryKind]] = frozenset({KIND_SERVICE, KIND_COMPONENT, KIND_INFRASTRUCTURE, KIND_EVENT})
"""The kinds of entry a Story builds: what the architecture adds or changes."""
EVIDENCE_RESULT: Final = "architecture result"
"""The evidence of every item: the architect's result lists it under addedOrChangedElements."""
NO_PUBLISHER_STACK: Final = ": no publisher of it is homed in a stack, or its publishers are in more than one stack"
NAMING_REPOSITORY: Final = "repository"
"""The naming rules' resource for the repository that holds a stack."""
NAMING_STACK_SEGMENT: Final = "stackName"
"""The segment that resource is named from: the stack's name."""


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


class ConsumedBy(TypedDict):
    """One consumer of an event a Story builds."""

    event: str
    consumer: str
    side: str
    stack: str | None
    repository: str | None


class BuildContext(TypedDict):
    """What a Story's Tasks depend on or use outside what the Story builds."""

    dependsOn: list[DependsOn]
    consumedBy: list[ConsumedBy]


@dataclass(frozen=True, slots=True)
class RepositoryStacks:
    """The stacks of the span that name one repository, with what the stacks say about it."""

    name: str
    stacks: tuple[EntryId, ...]
    apps: tuple[str, ...]
    """The ``app`` of each stack, without repeats."""
    types: tuple[str, ...]
    """The type of each stack, the last token of its name, without repeats."""
    purpose: str
    """The stacks' purposes, joined."""


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def inventory(tools: Tools, name: str | None = None) -> dict[str, JsonValue]:
    """Read the repository inventory and validate its row collection.

    Args:
        tools: The step's tools.
        name: The one repository to read (``polyrepo inventory --name``); None reads every one.

    Returns:
        The inventory object the ``polyrepo`` tool printed.

    """
    result = tools.polyrepo(["inventory", *(["--name", name] if name else [])], stage=REPO_SCOPING_PHASE)
    value = json_object(json.loads(result.stdout))
    _objects(value["repos"])
    return value


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


def _create(missing: MissingRepo, tools: Tools, home: RepositoryStacks) -> str:
    """Create one repository with the ``polyrepo`` tool, in the app space its stacks name.

    Returns:
        The path of the new clone. A result that names no absolute path fails the step.

    """
    name: str = missing[KEY_NAME]
    result = tools.polyrepo(
        [
            "create",
            name,
            "--space",
            home.apps[0],
            "--template",
            missing[KEY_TEMPLATE],
        ],
        stage=CREATION_STAGE,
    )
    value = json_object(json.loads(result.stdout))
    path = check_type(value.get("path"), str | None)
    if not path or not Path(path).is_absolute():
        raise tools.failure(CREATION_STAGE, OTHER_CAUSE, {"result": value})
    created = check_type(value.get("repo"), str | None)
    if created and created != name:
        tools.portfolio(CREATION_STAGE, _record_repository, home.stacks, created)
    return path


def _ensure_repository(
    missing: MissingRepo,
    tools: Tools,
    home: RepositoryStacks,
    owner: str,
    *,
    preflight_done: bool,
) -> tuple[dict[str, JsonValue], bool]:
    live = inventory(tools, missing[KEY_NAME])
    name: str = missing[KEY_NAME].casefold()
    existing = next(
        (r for r in _objects(live["repos"]) if check_type(r["name"], str).casefold() == name and r.get("path")),
        None,
    )
    if existing:
        return {KEY_REPO_PATH: existing["path"], "existed": True}, preflight_done
    if not preflight_done:
        need = _preflight(tools, owner)
        if need:
            return {"error": need, "ownerFact": True}, False
    return {KEY_REPO_PATH: _create(missing, tools, home), "existed": False}, True


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
        Measured creation results or an explicit owner authentication requirement.

    Raises:
        StepError: A deterministic repository operation fails.
        ValueError: Repository output is invalid.
        OSError: A repository operation cannot access a required resource.
        KeyError: A required repository field is absent.

    """
    created: list[dict[str, JsonValue]] = []
    failures: list[dict[str, JsonValue]] = []
    preflight_done = False
    for missing in ruling[KEY_MISSING_REPOS]:
        facts: dict[str, JsonValue] = {
            KEY_NAME: missing[KEY_NAME],
            KEY_TEMPLATE: missing[KEY_TEMPLATE],
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
def story_build_entries(matrix: Matrix, added_or_changed: Sequence[str]) -> list[EntryId]:
    """List what the Epic's Stories build: what the architecture adds or changes.

    An event is built as part of the service that publishes it, so each event among the ids
    brings its architecture-side publishers with it.

    Args:
        matrix: The matrix.
        added_or_changed: The ids the architect's result lists under ``addedOrChangedElements``.

    Returns:
        The ids, with the publishers of each event among them, each once, in id order. A text
        that is not an entry id is left out (:func:`story_build_problems` reports it).

    """
    stated: list[EntryId] = [found for text in added_or_changed if (found := _stated_id(text)) is not None]
    publishers: list[EntryId] = [
        publisher
        for entry_id in stated
        if (entry := matrix.find(entry_id)) is not None and entry.kind == KIND_EVENT
        for publisher in matrix.publishers(entry_id)
    ]
    return sorted({*stated, *publishers})


def _entry_problem(entry: Entry) -> str | None:
    """Check that an entry is something a Story builds.

    Returns:
        One sentence naming the first rule the entry breaks; None when it is an
        architecture-side service, component, piece of infrastructure or SkillSpoke event.

    """
    if entry.side != AUTHORITY_SIDE:
        return f"{entry.id} is on the {entry.side} side; what a Story builds is what the {AUTHORITY_SIDE} side states"
    if entry.kind not in BUILT_KINDS:
        return f"{entry.id} is a {entry.kind}; a Story builds services, components, infrastructure and events"
    if ATTR_EXTERNAL_SOURCE in entry.attributes:
        return f"{entry.id} is published outside SkillSpoke ({ATTR_EXTERNAL_SOURCE}); no Story builds it"
    return None


def _stack_problem(matrix: Matrix, entry: Entry) -> str | None:
    """Check the stack the architecture side places an entry in.

    Returns:
        One sentence when the architecture side places it in no stack, or in a stack of the
        marketing app; None otherwise.

    """
    stack: EntryId | None = authority_holder(matrix, entry.id)
    if stack is None:
        reason: str = NO_PUBLISHER_STACK if entry.kind == KIND_EVENT else ""
        return f"the {AUTHORITY_SIDE} side states no home for {entry.id}{reason}"
    if matrix.entry(stack).attributes.get(ATTR_APP) == MARKETING_APP:
        return f"{entry.id} is in {stack}, of the {MARKETING_APP} app, whose repositories no pipeline step changes"
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
def story_build_problems(matrix: Matrix, bead: str, added_or_changed: Sequence[str]) -> list[str]:
    """Check what the architecture says the Epic's Stories build.

    Args:
        matrix: The matrix.
        bead: The Epic, named in the sentences.
        added_or_changed: The ids the architect's result lists under ``addedOrChangedElements``.

    Returns:
        One sentence per text that is not an entry id, and per entry of
        :func:`story_build_entries` that the matrix lacks, that is not on the architecture
        side, that is not a service, component, piece of infrastructure or event, that is an
        event published outside SkillSpoke, that the architecture side places in no stack, or
        whose stack is of the marketing app. Empty when the Stories can build every one.

    """
    unread: list[str] = [
        f"{bead}: addedOrChangedElements names {text!r}, which is not a matrix id"
        for text in added_or_changed
        if _stated_id(text) is None
    ]
    entries: list[EntryId] = story_build_entries(matrix, added_or_changed)
    found: list[str | None] = [_build_problem(matrix, entry_id) for entry_id in entries]
    return [*unread, *(problem for problem in found if problem is not None)]


def _requires(matrix: Matrix, entry_id: EntryId, ids: Mapping[EntryId, str]) -> list[str]:
    """List the build items one item needs built first.

    Only the dependency relationships the architecture side states count; a repository-side
    relationship never makes a ``requires``, and a dependency on something no Story of the Epic
    builds is context, not an item.

    Returns:
        The item ids its architecture-side dependency relationships reach directly, in the order
        found and without repeats; never the item itself.

    """
    reached: list[str] = [
        ids[relationship.end]
        for relationship in matrix.outgoing(entry_id, family_kinds(FAMILY_DEPENDENCY))
        if relationship.side == AUTHORITY_SIDE and relationship.end in ids and relationship.end != entry_id
    ]
    return list(dict.fromkeys(reached))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_name(matrix: Matrix, stack: EntryId) -> str:
    """Name the repository that holds a stack.

    Args:
        matrix: The matrix.
        stack: The stack's id.

    Returns:
        The stack's ``repository`` attribute; when it states none, the name the project's
        naming rules (``atw-naming name repository --stack-name``) give the repository of a
        stack with the stack's name in the stack's app. Never the raw stack name.

    Raises:
        ValueError: The stack states no repository and the naming rules cannot name one.

    """
    entry: Entry = matrix.entry(stack)
    stated: JsonValue = entry.attributes.get(ATTR_REPOSITORY)
    if isinstance(stated, str) and stated:
        return stated
    app: JsonValue = entry.attributes.get(ATTR_APP)
    try:
        rules: naming.Rules = naming.load_rules(None)
        resource: naming.Resource = rules.resource(NAMING_REPOSITORY)
        return rules.build(resource, *rules.derive(resource, {NAMING_STACK_SEGMENT: entry.name}, _text_or_none(app)))
    except (naming.ConfigError, naming.NamingError) as error:
        message: str = f"{stack} names no repository and the naming rules cannot name one: {error}"
        raise ValueError(message) from error


def _text_or_none(value: JsonValue) -> str | None:
    """Read an attribute that is a non-empty string.

    Returns:
        The string, or None.

    """
    return value if isinstance(value, str) and value else None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_builds(matrix: Matrix, bead: str, added_or_changed: Sequence[str]) -> list[DeltaItem]:
    """List what the Epic's Stories build, in the shape the spec and Task steps read.

    Args:
        matrix: The matrix.
        bead: The Epic.
        added_or_changed: The ids the architect's result lists under ``addedOrChangedElements``.

    Returns:
        One item per entry of :func:`story_build_entries`: its id, the entry's name and matrix
        id, the documents that describe it, the repository of the stack the architecture side
        places it in (:func:`repository_name`), and the items it requires and is required by
        through the architecture-side dependency relationships between them.

    Raises:
        StepError: :func:`story_build_problems` reports a problem; the evidence names each.

    """
    problems: list[str] = story_build_problems(matrix, bead, added_or_changed)
    if problems:
        raise StepError(SPAN, OTHER_CAUSE, tuple(problems))
    entries: list[EntryId] = story_build_entries(matrix, added_or_changed)
    ids: dict[EntryId, str] = {entry_id: f"E{index}" for index, entry_id in enumerate(entries, 1)}
    items: list[DeltaItem] = [
        {
            "id": ids[entry_id],
            "element": matrix.entry(entry_id).name,
            "matrixId": entry_id,
            "views": list(dict.fromkeys(stated.end for stated in matrix.outgoing(entry_id, (REL_DESCRIBED_BY,)))),
            "kind": KIND_IMPLEMENTATION_GAP,
            "repository": repository_name(matrix, _placed_stack(matrix, entry_id)),
            "requires": _requires(matrix, entry_id, ids),
            "requiredBy": [],
            "evidence": [entry_id, EVIDENCE_RESULT],
        }
        for entry_id in entries
    ]
    by_id: dict[str, DeltaItem] = {item["id"]: item for item in items}
    for item in items:
        for needed in item.get("requires", []):
            by_id[needed].setdefault("requiredBy", []).append(item["id"])
    return items


def _placed_stack(matrix: Matrix, entry_id: EntryId) -> EntryId:
    """Name the stack the architecture side places an entry in.

    Returns:
        The stack (:func:`matrixtraverse.authority_holder`).

    Raises:
        ValueError: The architecture side places it in none.

    """
    stack: EntryId | None = authority_holder(matrix, entry_id)
    if stack is None:
        message: str = f"the {AUTHORITY_SIDE} side states no home for {entry_id}"
        raise ValueError(message)
    return stack


def _record_repository_names(items: Sequence[DeltaItem]) -> list[EntryId]:
    """Record on each stack that names no repository the name its Story's repository is given.

    The name comes from the naming rules (:func:`repository_name`), so the stack, the
    steward's manifest and the repository created for it carry one name. It is written on the
    architecture side, in one matrix change.

    Returns:
        The stacks that took a name.

    """

    def change(matrix: Matrix) -> list[EntryId]:
        stacks: set[EntryId] = {_placed_stack(matrix, as_entry_id(item.get("matrixId", ""))) for item in items}
        unnamed: list[EntryId] = sorted(
            stack for stack in stacks if _text_or_none(matrix.entry(stack).attributes.get(ATTR_REPOSITORY)) is None
        )
        named: dict[EntryId, str] = {stack: repository_name(matrix, stack) for stack in unnamed}
        for stack, name in named.items():
            put(matrix, KIND_STACK, AUTHORITY_SIDE, entry_id=stack, attributes={ATTR_REPOSITORY: name})
        return unnamed

    return update_matrix(matrix_path(None, os.environ), change)


def _stack_of(matrix: Matrix, entry_id: EntryId) -> tuple[EntryId | None, str | None]:
    """Name the stack of an entry a Story depends on or that consumes what it builds, and that stack's repository.

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


def _consumed_by(matrix: Matrix, relationship: Relationship) -> ConsumedBy:
    """Render one consumer of an event a Story builds.

    Returns:
        The event, its consumer, the side that states it, and the consumer's stack and repository.

    """
    stack: EntryId | None
    repository: str | None
    stack, repository = _stack_of(matrix, relationship.start)
    return {
        "event": relationship.end,
        "consumer": relationship.start,
        "side": relationship.side,
        "stack": stack,
        "repository": repository,
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def build_context(
    matrix: Matrix,
    built: Sequence[JsonValue],
    all_items: Mapping[str, Sequence[JsonValue]],
) -> BuildContext:
    """List what a Story's Tasks depend on or use outside what the Story builds: context, never work.

    Args:
        matrix: The matrix.
        built: The items of what this Story builds.
        all_items: The items of every Story of the Epic, by the Story's storyKey.

    Returns:
        ``dependsOn``: each dependency-family relationship, on either side, that starts at an
        entry this Story builds and ends at one it does not build, with the side that states it,
        the far end's stack and repository, and the other Story that builds the far end.
        ``consumedBy``: each consumer of an event this Story builds, with its stack and
        repository.

    """
    own: set[EntryId] = set(item_ids(built))
    built_by: dict[EntryId, str] = {
        entry_id: story for story, items in all_items.items() for entry_id in item_ids(items) if entry_id not in own
    }
    dependencies: list[DependsOn] = [
        _depends_on(matrix, relationship, built_by)
        for entry_id in sorted(own)
        for relationship in matrix.outgoing(entry_id, family_kinds(FAMILY_DEPENDENCY))
        if relationship.end not in own
    ]
    consumers: list[ConsumedBy] = [
        _consumed_by(matrix, relationship)
        for entry_id in sorted(own)
        for relationship in matrix.incoming(entry_id, (REL_CONSUMES,))
    ]
    return {"dependsOn": dependencies, "consumedBy": consumers}


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
    the architecture side places in no stack raises ``ValueError``.

    Args:
        matrix: The matrix.
        items: Items as the span step wrote them.

    Returns:
        Each stack the architecture side places them in (for an event, its publisher's stack),
        in id order, with the entries of the items it holds.

    """
    grouped: dict[EntryId, list[EntryId]] = {}
    entry_id: EntryId
    for entry_id in item_ids(items):
        matrix.entry(entry_id)
        grouped.setdefault(_placed_stack(matrix, entry_id), []).append(entry_id)
    return {stack: grouped[stack] for stack in sorted(grouped)}


def shared_capabilities(run: StepRun, step: str, items: Sequence[JsonValue]) -> list[Capability]:
    """List the shared capabilities the entries one repository builds must use.

    The entries are the ones the items name; the answer is what ``atw-matrix uses --ids`` prints
    for them. A matrix that cannot be read, or an item that names an entry the matrix lacks,
    fails the step.

    Args:
        run: The step that asks.
        step: The step's name, for a failure.
        items: What the Story of the repository builds.

    Returns:
        Each supporting feature that applies to the entries, with what it provides, the
        ``provides`` items relied on, and the entries that provide it, each with its stack.

    """
    matrix: Matrix = run.tools.portfolio(step, read_matrix, matrix_path(None, os.environ))
    entries: list[EntryId] = run.tools.portfolio(step, item_ids, items)
    if not entries:
        return []
    used: UsesResult = run.tools.portfolio(step, uses_view, matrix, entries)
    return used["capabilities"]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_stacks(matrix: Matrix, items: Sequence[DeltaItem]) -> dict[str, RepositoryStacks]:
    """Group the stacks of some items by the repository each names.

    An entry the architecture side places in no stack raises ``ValueError``.

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
        home: EntryId = _placed_stack(matrix, as_entry_id(item.get("matrixId", "")))
        name: str = item.get("repository") or repository_name(matrix, home)
        stacks.setdefault(name, {})[home] = matrix.entry(home)
    grouped: dict[str, RepositoryStacks] = {}
    for name, found in stacks.items():
        ordered: list[Entry] = [found[stack] for stack in sorted(found)]
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
        The repository's name, the template named for its stacks' one type, the stacks' purpose
        and the items of what its Story builds.

    Raises:
        StepError: The stacks have more than one type or more than one app, name no app, or
            belong to the app whose repositories no pipeline step creates.

    """
    if len(home.types) != 1 or len(home.apps) != 1:
        evidence: str = (
            f"{home.name} does not exist, and its stacks {', '.join(home.stacks)} have the types "
            f"{', '.join(home.types) or 'none'} and the apps {', '.join(home.apps) or 'none'}: a repository is "
            "created from one template in one app space"
        )
        raise StepError(SPAN, OTHER_CAUSE, (evidence,))
    if home.apps[0] == MARKETING_APP:
        evidence = f"{home.name} does not exist, and no {MARKETING_APP} repository is created"
        raise StepError(SPAN, OTHER_CAUSE, (evidence,))
    return {
        KEY_NAME: home.name,
        KEY_TEMPLATE: home.types[0],
        KEY_PURPOSE: home.purpose,
        KEY_ITEM_IDS: built,
    }


def _ruling(
    run: StepRun,
    items: list[DeltaItem],
    homes: Mapping[str, RepositoryStacks],
) -> PlacementRuling:
    """Group what the Stories build by the repository of the stack the architecture side places each in.

    Returns:
        The span in the placement contract's shape: one placement per repository, with its path
        when the inventory has it, and one missing repository per name it lacks.

    Raises:
        StepError: A repository may hold no product entry, or a missing repository cannot be
            created from what its stacks state.

    """
    live: dict[str, dict[str, JsonValue]] = {
        check_type(repo["name"], str).casefold(): repo for repo in _objects(inventory(run.tools)["repos"])
    }
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
        if path is not None and forbidden(Path(path), control, arch, env_path("SKILLSPOKE_ROOT") / "apps/marketing"):
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


def _owner(control: Path) -> str:
    """Read the GitHub organisation repositories are created in, from the project's repository rules.

    Returns:
        The organisation's name.

    """
    config: dict[str, JsonValue] = json_object(
        yaml_safe_load((control / ".polyrepo/config.yaml").read_text(encoding="utf-8")),
    )
    return check_type(config[OWNER_KEY], str)


def _read_story_builds(run: StepRun) -> tuple[Matrix, list[DeltaItem]]:
    """Read what the Epic's Stories build, and name the repository of each stack that names none.

    Returns:
        The matrix as it is after the names are recorded, and the items (:func:`story_builds`).

    Raises:
        StepError: The architecture adds or changes nothing to build.

    """
    added: list[str] = read_result(run, read_context(run))["addedOrChangedElements"]
    matrix: Matrix = run.tools.portfolio(SPAN, read_matrix, matrix_path(None, os.environ))
    items: list[DeltaItem] = run.tools.portfolio(SPAN, story_builds, matrix, run.bead, added)
    if not items:
        raise StepError(SPAN, OTHER_CAUSE, (f"the architecture adds or changes nothing to build for {run.bead}",))
    run.tools.portfolio(SPAN, _record_repository_names, items)
    return run.tools.portfolio(SPAN, read_matrix, matrix_path(None, os.environ)), items


@script_step(SPAN)
def span(run: StepRun) -> Completion:
    """Read what the Epic's Stories build from the architect's result and plan one spec step per repository.

    What the Stories build is the architect's ``addedOrChangedElements`` with each event's
    publishers (:func:`story_builds`). Nothing is recorded in the matrix but the name of the
    repository of a stack the Stories build in that names none (from the naming rules), and the
    name of a repository that was created under another name than the one its stacks stated.

    Returns:
        The span file, the elements file, the repository paths, and the creation record when a
        repository had to be created; with the spec steps planned after this step.

    Raises:
        StepError: The architecture adds or changes nothing to build, what it lists cannot be
            built (:func:`story_build_problems`), or a repository can be created only after the
            owner acts.

    """
    enter_phase(run.context, run.agents.emit, REPO_SCOPING_PHASE, SPAN)
    matrix: Matrix
    items: list[DeltaItem]
    matrix, items = _read_story_builds(run)
    work: Path = run.context.work
    homes: dict[str, RepositoryStacks] = run.tools.portfolio(SPAN, repository_stacks, matrix, items)
    ruling: PlacementRuling = _ruling(run, items, homes)
    elements: DeltaResult = {
        "ok": True,
        "refusals": [],
        "summary": {"ok": True, "refusals": [], "items": len(items)},
        "items": items,
    }
    elements_path: Path = work / ELEMENTS_FILE
    write_json(elements_path, elements)
    artifacts = [file_artifact(ARTIFACT_ELEMENTS, elements_path)]
    if ruling[KEY_MISSING_REPOS]:
        owner: str = _owner(env_path(CONTROL_REPO_ENV))
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
    span_path: Path = work / SPAN_FILE
    write_json(span_path, ruling)
    repos: list[str] = list(dict.fromkeys(check_type(p[KEY_REPO_PATH], str) for p in ruling[KEY_PLACEMENTS]))
    kept: list[JsonValue] = list(repos)
    return Completion(
        artifacts=(file_artifact(ARTIFACT_SPAN, span_path), *artifacts, value_artifact(ARTIFACT_REPOSITORIES, kept)),
        add=_spec_steps(run, ruling, repos),
    )
