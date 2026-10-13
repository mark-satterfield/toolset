"""Read the repository span of an Epic from the matrix, and create a repository it names and lacks.

The span is what ``atw-matrix epic <id> --closure`` reaches: the entries the Epic's features lead
to, the stack that is the home of each, and everything those stacks depend on. A stack reached
that holds an entry, or starts a relationship, with no verified mark may still have to be built,
so it and those entries are the items some repository's Story builds. The repository of an item
is the ``repository`` attribute of its stack. No session is started. A repository a stack names
and the inventory lacks is created from the template named for the stack's type.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

# The driver surface and the placement contract are defined once, in their skills.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
import hierarchy
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import (
    AUTHORITY_SIDE,
    BUILD_PROVED_KINDS,
    ENTRY_RULES,
    FAMILY_DEPENDENCY,
    KIND_STACK,
    REL_DESCRIBED_BY,
    SIDE_REPOSITORY,
    Entry,
    EntryId,
    family_kinds,
)
from matrixquery import Capability, UsesResult, uses_view
from matrixstore import Matrix, as_entry_id, matrix_path, read_matrix, update_matrix
from matrixtraverse import (
    ATTR_APP,
    ATTR_REPOSITORY,
    HOMED_KINDS,
    EpicReach,
    epic_id,
    epic_reach,
    held,
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
    KIND_PREREQUISITE,
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
from orchestrator.flows.architecture_files import HUMAN_ACTION_STAGE
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


def _proved(matrix: Matrix, entry_id: EntryId) -> bool:
    """Tell whether an entry, and every relationship a build proves that starts at it, is verified.

    Returns:
        True when the entry carries the verified mark, or is of a kind that carries none, and
        each such relationship carries it.

    """
    entry: Entry = matrix.entry(entry_id)
    marked: bool = entry.verified is not None or not ENTRY_RULES[entry.kind].verifiable
    return marked and all(
        relationship.verified is not None for relationship in matrix.outgoing(entry_id, BUILD_PROVED_KINDS)
    )


def _may_need_building(matrix: Matrix, entry: Entry) -> bool:
    """Tell whether an entry may still have to be built.

    Returns:
        True when the entry is not verified or starts a relationship that is not; for a stack,
        also when an entry the architecture side states it holds is not or starts one that is not.

    """
    members: list[EntryId] = [entry.id]
    if entry.kind == KIND_STACK:
        members.extend(inside for inside in held(matrix, entry.id) if matrix.entry(inside).side == AUTHORITY_SIDE)
    return not all(_proved(matrix, member) for member in members)


def _work_entries(matrix: Matrix, reach: EpicReach) -> tuple[list[Entry], set[EntryId]]:
    """Find the entries an Epic's Stories build, from what the Epic reaches.

    Verified decides nothing but what may still have to be built: every stack the Epic reaches is
    read, and a stack, or an architecture-side entry with a home in code, is an item while it or
    a relationship it starts carries no verified mark.

    Returns:
        The stacks the Epic reaches, the entries its features lead to and the far ends of their
        dependencies that may still have to be built, in id order; and the ids of those a
        feature leads to, with the stacks that hold them.

    """
    led: set[EntryId] = set(reach.ways)
    led.update(home for reached in reach.ways if (home := holder(matrix, reached)) is not None)
    candidates: set[EntryId] = {*reach.stacks, *reach.ways, *(dependency.far for dependency in reach.dependencies)}
    work: list[Entry] = []
    candidate: EntryId
    for candidate in sorted(candidates):
        entry: Entry = matrix.entry(candidate)
        built_in_code: bool = entry.kind == KIND_STACK or (entry.kind in HOMED_KINDS and entry.side == AUTHORITY_SIDE)
        if built_in_code and _may_need_building(matrix, entry):
            work.append(entry)
    return work, led


def _requires(matrix: Matrix, entry: Entry, ids: Mapping[EntryId, str]) -> list[str]:
    """List the items one item needs built first, from the dependency relationships it starts.

    A stack stands for itself and every entry it holds. A dependency whose far end is no item
    counts against the item of the stack that holds the far end.

    Returns:
        The item ids, in the order found and without repeats; never the item itself.

    """
    starts: list[EntryId] = [entry.id, *held(matrix, entry.id)] if entry.kind == KIND_STACK else [entry.id]
    own: EntryId | None = holder(matrix, entry.id)
    needed: dict[str, None] = {}
    start: EntryId
    for start in starts:
        for dependency in matrix.outgoing(start, family_kinds(FAMILY_DEPENDENCY)):
            home: EntryId | None = holder(matrix, dependency.end)
            if entry.kind == KIND_STACK and home == entry.id:
                continue
            target: str | None = ids.get(dependency.end)
            if target is None and home is not None and home != own:
                target = ids.get(home)
            if target is not None and target != ids[entry.id]:
                needed[target] = None
    return list(needed)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def span_items(matrix: Matrix, bead: str) -> list[DeltaItem]:
    """List the items an Epic's Stories build, in the shape the spec and Task steps read.

    An Epic the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        bead: The Epic.

    Returns:
        One item per stack and entry that may still have to be built: its id, the entry's name
        and matrix id, the documents that describe it, the repository its stack names, and the
        items it requires and is required by, from the dependency relationships between them.

    Raises:
        StepError: An architecture-side entry the Epic reaches has no stack, or a stack it
            reaches names no repository; the evidence names each.

    """
    reach: EpicReach = epic_reach(matrix, epic_id(bead))
    unplaced: list[str] = [
        *(f"the matrix records no stack (homeIn) for {entry_id}" for entry_id in reach.no_stack),
        *(f"the matrix records no repository for {stack}" for stack in reach.no_repository),
    ]
    if unplaced:
        raise StepError(SPAN, OTHER_CAUSE, tuple(unplaced))
    work, led = _work_entries(matrix, reach)
    ids: dict[EntryId, str] = {entry.id: f"E{index}" for index, entry in enumerate(work, 1)}
    items: list[DeltaItem] = []
    entry: Entry
    for entry in work:
        home: EntryId | None = holder(matrix, entry.id)
        named: JsonValue = None if home is None else matrix.entry(home).attributes.get(ATTR_REPOSITORY)
        item: DeltaItem = {
            "id": ids[entry.id],
            "element": entry.name,
            "matrixId": entry.id,
            "views": list(dict.fromkeys(stated.end for stated in matrix.outgoing(entry.id, (REL_DESCRIBED_BY,)))),
            "kind": KIND_IMPLEMENTATION_GAP if entry.id in led else KIND_PREREQUISITE,
            "repository": named if isinstance(named, str) else None,
            "requires": _requires(matrix, entry, ids),
            "requiredBy": [],
            "evidence": [entry.id],
        }
        items.append(item)
    by_id: dict[str, DeltaItem] = {item["id"]: item for item in items}
    for item in items:
        for needed in item.get("requires", []):
            by_id[needed].setdefault("requiredBy", []).append(item["id"])
    return items


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

    An id the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``.

    Args:
        matrix: The matrix.
        items: Items as the span step wrote them.

    Returns:
        Each stack, in id order, with the entries of the items it holds; a stack that is itself
        an item is among its own entries.

    Raises:
        ValueError: An item's entry has no stack.

    """
    grouped: dict[EntryId, list[EntryId]] = {}
    entry_id: EntryId
    for entry_id in item_ids(items):
        matrix.entry(entry_id)
        home: EntryId | None = holder(matrix, entry_id)
        if home is None:
            message: str = f"the matrix records no stack (homeIn) for {entry_id}"
            raise ValueError(message)
        grouped.setdefault(home, []).append(entry_id)
    return {stack: grouped[stack] for stack in sorted(grouped)}


def shared_capabilities(run: StepRun, step: str, items: Sequence[JsonValue]) -> list[Capability]:
    """List the shared capabilities the entries one repository builds must use.

    The entries are the ones the items name; the answer is what ``atw-matrix uses --ids`` prints
    for them. A matrix that cannot be read, or an item that names an entry the matrix lacks,
    fails the step.

    Args:
        run: The step that asks.
        step: The step's name, for a failure.
        items: The items placed in the repository.

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

    Args:
        matrix: The matrix.
        items: The items of the span (:func:`span_items`).

    Returns:
        Each repository name with the stacks of the span that name it, their apps, their types
        and their purposes.

    Raises:
        ValueError: An item's entry has no stack, or its stack names no repository.

    """
    stacks: dict[str, dict[EntryId, Entry]] = {}
    item: DeltaItem
    for item in items:
        home: EntryId | None = holder(matrix, as_entry_id(item.get("matrixId", "")))
        name: str | None = item.get("repository")
        if home is None or not name:
            message: str = f"the matrix places {item['element']} in no stack that names a repository"
            raise ValueError(message)
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


def _missing(home: RepositoryStacks, placed: list[str]) -> MissingRepo:
    """Describe a repository to create, from the stacks that name it.

    Returns:
        The repository's name, the template named for its stacks' one type, the stacks' purpose
        and the items placed in it.

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
        KEY_ITEM_IDS: placed,
    }


def _ruling(
    run: StepRun,
    items: list[DeltaItem],
    homes: Mapping[str, RepositoryStacks],
) -> PlacementRuling:
    """Group the items by the repository the matrix places each in.

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
    for name, placed in grouped.items():
        known: JsonValue = live.get(name.casefold(), {}).get("path")
        path: str | None = str(Path(known).resolve()) if isinstance(known, str) and known else None
        if path is not None and forbidden(Path(path), control, arch, env_path("SKILLSPOKE_ROOT") / "apps/marketing"):
            raise StepError(SPAN, OTHER_CAUSE, (f"{name} at {path} may hold no product entry",))
        placement: Placement = {
            KEY_REPO_PATH: path,
            "repoName": name,
            KEY_ITEM_IDS: placed,
            "frontend": WEB_TYPE in homes[name].types,
            "rationale": "The matrix records this repository on the stacks that hold these entries.",
        }
        ruling[KEY_PLACEMENTS].append(placement)
        if path is None:
            ruling[KEY_MISSING_REPOS].append(_missing(homes[name], placed))
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


@script_step(SPAN)
def span(run: StepRun) -> Completion:
    """Read the repository span from the matrix and plan one spec step per repository.

    Nothing is recorded in the matrix but the name of a repository that was created under another
    name than the one its stacks stated.

    Returns:
        The span file, the elements file, the repository paths, and the creation record when a
        repository had to be created; with the spec steps planned after this step.

    Raises:
        StepError: The Epic reaches nothing to build, an entry it reaches has no stack, a stack
            it reaches names no repository, or a repository can be created only after the owner
            acts.

    """
    enter_phase(run.context, run.agents.emit, REPO_SCOPING_PHASE, SPAN)
    matrix: Matrix = run.tools.portfolio(SPAN, read_matrix, matrix_path(None, os.environ))
    items: list[DeltaItem] = run.tools.portfolio(SPAN, span_items, matrix, run.bead)
    if not items:
        raise StepError(SPAN, OTHER_CAUSE, (f"the matrix records nothing to build for {run.bead}",))
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
