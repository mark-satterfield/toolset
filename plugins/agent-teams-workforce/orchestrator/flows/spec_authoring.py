"""One repository's specification documents and its Story, as steps of the Epic's journal.

The span step plans one container per repository with its first step, the repository context.
That step gathers what the repository builds and plans the rest: for a frontend repository the UI
bundle listing, the UI sources session and its normalization; the contracts session and the
data-model session, which run together; the UI section; the acceptance-criteria session; the
review; the Story document; and the Story bead write. Each step takes the files it reads from the
artifacts of the steps its inputs name, and records what it writes right after writing it.

What a repository's Story is handed about the architecture is read from the matrix: the context
step writes what ``atw-matrix story-scope`` returns for each stack the Story builds in, and an
author is handed the documents and headings it names and no directory of the architecture.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
import beadgraph
import beadwrite
import cdsbundles
import hierarchy
import specui
from matrixquery import story_scope
from matrixstore import Matrix, as_entry_id, matrix_path, read_matrix
from recon_contract import KEY_MOCKS_DIR
from target_contract import KEY_ELEMENT, KEY_ID, KEY_MATRIX_ID, KEY_PUBLISHED_BY, KEY_TRIGGER
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_changes import create_child_journal
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import (
    UNDER_CONTAINER,
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import ARTIFACT_TRD, read_context, read_result
from orchestrator.flows.elaboration_files import (
    ARTIFACT_ELEMENTS,
    ARTIFACT_SPAN,
    AUTHOR_CONTRACTS,
    AUTHOR_CRITERIA,
    AUTHOR_DATA_MODEL,
    CONTEXT,
    CRITERIA,
    DATA_MODEL,
    PRD,
    REPOSITORY,
    REVIEWER,
    SPEC,
    SPEC_CONTEXT,
    STORY,
    STORY_DOCUMENT,
    STORY_DOCUMENT_STEP,
    STORY_WRITE,
    TASK_CONTEXT,
    TASKS_CONTAINER,
    UI_APPEND,
    UI_BUNDLE_LIST,
    UI_BUNDLES,
    UI_CANDIDATE,
    UI_NORMALIZE,
    UI_SOURCES,
    WARNINGS,
    WORK,
    Repository,
    control_repository,
    creating,
    handed_on,
    objects,
    project_root,
    repository,
    repository_of,
    span_files,
    story_files,
    strings,
)
from orchestrator.flows.elaboration_support import SPEC_AUTHORING_PHASE, enter_phase
from orchestrator.flows.repo_scoping import (
    BuildContext,
    build_context,
    item_stacks,
    shared_capabilities,
)
from orchestrator.flows.spec_authoring_ui import normalize_ui
from orchestrator.flows.trd_authoring import document

# isort: split
# The journal modules put the pipeline-contracts scripts directory on sys.path.
from step_journal_contract import BEAD_TYPE_STORY, BeadId

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from matrix_contract import Entry, EntryId
    from matrixquery import Described, StoryScope
    from step_journal_contract import Artifact, Step, StepPlan

    from orchestrator.core.models import OutputValidator

WORK_UI: Final = "ui-sources"
WORK_DOCUMENT: Final = "document"
"""What a step of an author agent, planned by the repository context step, does."""
DECISION_IDS: Final = "decision ids"
KEY_STACKS: Final = "stacks"
"""The member of the repository context that lists the ids of the stacks the Story builds in."""
STORY_SUMMARY: Final = "story write"
DOCUMENT_OF: Final[dict[str, str]] = {
    AUTHOR_CONTRACTS: SPEC,
    AUTHOR_DATA_MODEL: DATA_MODEL,
    AUTHOR_CRITERIA: CRITERIA,
}
"""The spec document each author writes, by artifact name."""
SUFFIX: Final[dict[str, str]] = {SPEC: ".md", DATA_MODEL: ".data-model.md", CRITERIA: ".criteria.md"}
CONTRACTS_OUTCOME: Final = "API, event and error contracts for what this repository's Story builds."
DATA_MODEL_OUTCOME: Final = "Data model specification for what this repository's Story builds."
CRITERIA_OUTCOME: Final = "Acceptance criteria and definition of done for the saved specifications."
UI_SCHEMA: Final = "skills/artifact-handoff/schemas/spec-ui.schema.json"
CONTEXT_PURPOSE: Final = "The items this repository builds and the steps that specify them are known"
TASKS_PURPOSE: Final = "The Story has Tasks that name what to build"
STORY_KEY_PREFIX: Final = "S"
"""The prefix of a Story's key: the span keys its Stories ``S<n>`` in the order it names their repositories."""


def nonempty(path: Path) -> None:
    """Require a nonempty authored document.

    Raises:
        ValueError: The document contains no text.

    """
    if not path.read_text(encoding="utf-8").strip():
        message: str = f"missing or empty document: {path}"
        raise ValueError(message)


def architecture_root(run: StepRun) -> Path:
    """Name the architecture root of the dispatch.

    Returns:
        The path the dispatch arguments give.

    """
    return Path(check_type(run.context.args[dispatch_arguments().KEY_ARCH_PATH], str)).resolve()


def design_system(run: StepRun) -> dict[str, JsonValue]:
    """Read the design system facts of the dispatch.

    Returns:
        The dispatch's design system argument; empty when it gives none.

    """
    return json_object(run.context.args.get(dispatch_arguments().KEY_DESIGN_SYSTEM) or {})


def document_file(run: StepRun, held: Repository, name: str) -> Path:
    """Name the file one spec document of a repository is written to.

    Returns:
        The file in the Epic's work directory.

    """
    return run.context.work / f"spec-{held.slug}{SUFFIX[name]}"


def document_check(run: StepRun, name: str) -> OutputValidator:
    """Give the check a spec document must pass each time its author has written it.

    Returns:
        The check: every architecture citation of the contracts and of the data model names a
        document and heading the matrix holds; the criteria are a nonempty document.

    """
    if name == CRITERIA:
        return nonempty
    matrix: Matrix = run.tools.portfolio(name, read_matrix, matrix_path(None, os.environ))
    return lambda path: document(path, matrix)


def author_files(run: StepRun, name: str) -> tuple[tuple[str, Path], ...]:
    """Name the files the author of one spec document reads.

    Returns:
        The TRD, the span, the elements and the PRD; the UI sources for the contracts of a
        frontend repository; the contracts and the data model for the criteria; then the
        repository context, which names the architecture documents and headings to read.

    """
    files: list[tuple[str, Path]] = [(label, run.inputs.file(label)) for label in (ARTIFACT_TRD, ARTIFACT_SPAN)]
    files.extend((label, run.inputs.file(label)) for label in (ARTIFACT_ELEMENTS, PRD))
    sources: Path | None = run.inputs.optional_file(UI_SOURCES)
    if name == SPEC and sources is not None:
        files.append((UI_SOURCES, sources))
    if name == CRITERIA:
        files.extend((label, run.inputs.file(label)) for label in (SPEC, DATA_MODEL))
    return (*files, (CONTEXT, run.inputs.file(CONTEXT)))


def author_dirs(run: StepRun, held: Repository) -> tuple[Path, ...]:
    """Name the directories an author session may read.

    Returns:
        The Epic's work directory, where the session writes, and the repository the Story builds
        in. The architecture documents and the PRD are handed as named files.

    """
    return (run.context.work, Path(held.path))


def _step(  # ruff: ignore[too-many-arguments] - One plan field each.
    ref: str,
    description: str,
    purpose: str,
    inputs: list[str],
    *,
    agent: str | None = None,
    script: str | None = None,
    work: str | None = None,
) -> NewStep:
    """Plan one step of a repository with the parameters that say what it does.

    Returns:
        The planned step; it is handed the planning step's artifacts with its parameters.

    """
    plan: StepPlan = {"ref": ref, "description": description, "purpose": purpose, "inputs": inputs}
    if agent is not None:
        plan["agent"] = agent
    if script is not None:
        plan["script"] = script
    params: dict[str, JsonValue] = {} if work is None else {WORK: work}
    return NewStep(plan, params)


def _repository_steps(run: StepRun, held: Repository) -> StepGroup:
    """Plan every step of one repository that follows its context step.

    Returns:
        The steps in the order they run, after the context step.

    """
    name: str = Path(held.path).name
    upstream: list[str] = list(run.step.get("inputs", []))
    steps: list[NewStep] = []
    if held.frontend:
        steps.extend((
            _step(
                "bundles",
                f"List the UI bundles supplied for {name}",
                "The author knows the bundles",
                [],
                script=UI_BUNDLES,
            ),
            _step(
                "ui",
                f"Choose the UI design source of each UI item of {name}",
                "Every UI item has a design source",
                ["bundles", *upstream],
                agent=AUTHOR_CONTRACTS,
                work=WORK_UI,
            ),
            _step(
                "sources",
                f"Check the UI design sources of {name} against the supplied bundles",
                "Every design source can be built from",
                ["ui", "bundles"],
                script=UI_NORMALIZE,
            ),
        ))
    sources: list[str] = ["sources"] if held.frontend else []
    steps.extend((
        _step(
            "contracts",
            f"Write the API, event and error contracts of {name}",
            "The repository's contracts are specified",
            [*upstream, *sources],
            agent=AUTHOR_CONTRACTS,
            work=WORK_DOCUMENT,
        ),
        _step(
            "data-model",
            f"Write the data model of {name}",
            "The repository's data model is specified",
            upstream,
            agent=AUTHOR_DATA_MODEL,
            work=WORK_DOCUMENT,
        ),
    ))
    if held.frontend:
        steps.append(
            _step(
                "ui-section",
                f"Add the UI design sources to the contracts of {name}",
                "The contracts name the design source of each UI item",
                ["contracts", "sources"],
                script=UI_APPEND,
            ),
        )
    documents: list[str] = ["contracts", "data-model", "criteria"]
    steps.extend((
        _step(
            "criteria",
            f"Write the acceptance criteria of {name}",
            "The repository's work has criteria a test can be derived from",
            ["contracts", "data-model", *upstream],
            agent=AUTHOR_CRITERIA,
            work=WORK_DOCUMENT,
        ),
        _step(
            "review",
            f"Review the specification documents of {name}",
            "Every finding against the implementation criteria is settled",
            [*documents, *upstream],
            agent=REVIEWER,
        ),
        _step(
            "story",
            f"Write the Story document of {name}",
            "The Story names the repository, its items and its specifications",
            documents,
            script=STORY_DOCUMENT_STEP,
        ),
        _step(
            "story-bead",
            f"Write the Story bead of {name}",
            "The Epic has one Story for this repository",
            ["story", *documents, *upstream, *sources],
            script=STORY_WRITE,
        ),
    ))
    return StepGroup(tuple(steps))


def _scope_documents(arch: Path, scopes: Sequence[StoryScope]) -> list[JsonValue]:
    """List the architecture documents some story scopes name, each with the headings to read.

    Returns:
        One row per document, in id order: its entry id, its file under the architecture root,
        and the headings the scopes name in it (none when a scope names the document as a whole).

    """
    headings: dict[EntryId, dict[str, None]] = {}
    scope: StoryScope
    for scope in scopes:
        described: list[Described] = [
            *scope["documents"],
            *(found for built in scope["entries"] for found in built["documents"]),
            *(found for binding in scope["constraints"] for found in binding["statedIn"]),
        ]
        for found in described:
            named: dict[str, None] = headings.setdefault(found["document"], {})
            if found["heading"]:
                named[found["heading"]] = None
    rows: list[JsonValue] = []
    for identifier in sorted(headings):
        listed: list[JsonValue] = list(headings[identifier])
        rows.append({
            "document": identifier,
            "path": str(arch / identifier.partition(":")[2]),
            "headings": listed,
        })
    return rows


def items_by_story(every_build: Mapping[str, JsonValue]) -> dict[str, list[JsonValue]]:
    """Group what every Story of the Epic builds by the Story's key.

    The span plans one Story per repository, keyed ``S<n>`` in the order its placements name the
    repositories; the items of what the Stories build list the repositories in that order.

    Args:
        every_build: What every Story builds (``hierarchy.story_builds``), by item id.

    Returns:
        Each storyKey with the items of what its Story builds.

    """
    slugs: list[str] = list(dict.fromkeys(str(json_object(item)["slug"]) for item in every_build.values()))
    keys: dict[str, str] = {slug: f"{STORY_KEY_PREFIX}{index}" for index, slug in enumerate(slugs, 1)}
    grouped: dict[str, list[JsonValue]] = {key: [] for key in keys.values()}
    for item in every_build.values():
        grouped[keys[str(json_object(item)["slug"])]].append(item)
    return grouped


def story_context(matrix: Matrix, built: Sequence[JsonValue], every_build: Mapping[str, JsonValue]) -> BuildContext:
    """List what a Story depends on.

    Args:
        matrix: The matrix.
        built: The items of what this Story builds.
        every_build: What every Story of the Epic builds, by item id.

    Returns:
        ``repo_scoping.build_context`` for the Story.

    """
    return build_context(matrix, built, items_by_story(every_build))


@script_step(SPEC_CONTEXT)
def context(run: StepRun) -> Completion:
    """Gather what one repository builds, and plan the steps that specify it.

    What the Story is handed about the architecture comes from the matrix: for each stack the
    Story builds in, what ``atw-matrix story-scope`` returns (the documents and headings that
    describe the stack and each entry, the constraints that bind them and the shared
    capabilities they must use); and from ``repo_scoping.build_context``, what the Story depends
    on outside what it builds, each with its stack and repository.

    Returns:
        The repository, its context file and the PRD as artifacts, with the repository's other
        steps planned after this one.

    Raises:
        StepError: The span places no item in the repository, the matrix cannot answer for its
            entries, or the solutions architect's result cannot be read.

    """
    held: Repository = repository_of(dict(run.params()), SPEC_CONTEXT)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, SPEC_CONTEXT, held.path)
    dispatch: DispatchArguments = dispatch_arguments()
    every_build: dict[str, JsonValue] = json_object(
        run.tools.portfolio(SPEC_CONTEXT, hierarchy.story_builds, span_files(run.inputs)),
    )
    items: list[JsonValue] = [item for item in every_build.values() if json_object(item)["slug"] == held.slug]
    if not items:
        raise StepError(SPEC_CONTEXT, OTHER_CAUSE, (f"the span places no item in {held.path}",))
    matrix: Matrix = run.tools.portfolio(SPEC_CONTEXT, read_matrix, matrix_path(None, os.environ))
    stacks: dict[EntryId, list[EntryId]] = run.tools.portfolio(SPEC_CONTEXT, item_stacks, matrix, items)
    scopes: list[StoryScope] = [
        run.tools.portfolio(SPEC_CONTEXT, story_scope, matrix, stack, built) for stack, built in stacks.items()
    ]
    depended: BuildContext = run.tools.portfolio(SPEC_CONTEXT, story_context, matrix, items, every_build)
    prd: Path = Path(check_type(json_object(run.context.args[dispatch.KEY_PRD])[dispatch.PRD_PATH], str)).resolve()
    path: Path = run.context.work / f"spec-{held.slug}.context.json"
    write_json(
        path,
        {
            "repoPath": held.path,
            "slug": held.slug,
            "frontend": held.frontend,
            "items": items,
            KEY_STACKS: list(stacks),
            "scopes": scopes,
            "documents": _scope_documents(architecture_root(run), scopes),
            "dependsOn": depended["dependsOn"],
            "sharedCapabilities": shared_capabilities(run, SPEC_CONTEXT, items),
            "notesForSpecs": read_result(run, read_context(run))["notesForSpecs"],
            dispatch.KEY_DESIGN_SYSTEM: design_system(run),
        },
    )
    return Completion(
        artifacts=(value_artifact(REPOSITORY, held.facts()), file_artifact(CONTEXT, path), file_artifact(PRD, prd)),
        add=(_repository_steps(run, held),),
    )


@script_step(UI_BUNDLES)
def bundles(run: StepRun) -> Completion:
    """List the UI bundles the owner supplied, for the author that chooses design sources.

    Returns:
        The listing file.

    """
    held: Repository = repository(run.inputs)
    dispatch: DispatchArguments = dispatch_arguments()
    packages: str | None = check_type(design_system(run).get(dispatch.DS_PACKAGES_DIR), str | None)
    listed: dict[str, JsonValue] = json_object(run.tools.portfolio(UI_BUNDLES, cdsbundles.list_bundles, packages))
    path: Path = run.context.work / f"spec-{held.slug}.bundles.json"
    write_json(path, listed)
    return Completion(artifacts=(file_artifact(UI_BUNDLE_LIST, path),))


def ui_sources(run: StepRun) -> AgentLaunch:
    """Build the session that chooses the design source of each UI item of a frontend repository.

    Returns:
        The launch: the choices as the author wrote them, checked against the spec-ui schema.

    """
    held: Repository = repository(run.inputs)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, WORK_UI, held.path)

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(UI_CANDIDATE, output),))

    return AgentLaunch(
        output=run.context.work / "candidates" / f"spec-{held.slug}.ui.json",
        validate=run.tools.plugin / UI_SCHEMA,
        outcome="UI design sources for what this repository's Story builds.",
        accept=accept,
        add_dirs=author_dirs(run, held),
        files=(
            *((label, run.inputs.file(label)) for label in (ARTIFACT_TRD, ARTIFACT_SPAN, ARTIFACT_ELEMENTS, PRD)),
            (UI_BUNDLE_LIST, run.inputs.file(UI_BUNDLE_LIST)),
            (CONTEXT, run.inputs.file(CONTEXT)),
        ),
        hand_inputs=False,
    )


@script_step(UI_NORMALIZE)
def normalize(run: StepRun) -> Completion:
    """Keep the UI choices of what the Story builds and replace a bundle that cannot be built from.

    Returns:
        The UI sources file, and the warnings the normalization raised.

    """
    held: Repository = repository(run.inputs)
    every_build: set[str] = {
        check_type(item[KEY_ID], str) for item in objects(strict_json(run.inputs.file(CONTEXT))["items"])
    }
    normalized: dict[str, JsonValue] = normalize_ui(
        strict_json(run.inputs.file(UI_CANDIDATE)),
        every_build,
        strict_json(run.inputs.file(UI_BUNDLE_LIST)),
        run.tools,
    )
    normalized[KEY_MOCKS_DIR] = design_system(run).get(dispatch_arguments().DS_MOCKS_DIR)
    path: Path = run.context.work / f"spec-{held.slug}.ui.json"
    write_json(path, normalized)
    return Completion(artifacts=(file_artifact(UI_SOURCES, path), value_artifact(WARNINGS, normalized["warnings"])))


def spec_document(run: StepRun) -> AgentLaunch:
    """Build the session that writes one spec document of a repository.

    The document's citations stay in the document and on the Story (``decisionIds``); nothing is
    recorded in the matrix, whose architecture side only arc42 and the architect write.

    Returns:
        The launch: the document at its file in the work directory, with its own check.

    """
    held: Repository = repository(run.inputs)
    name: str = DOCUMENT_OF[run.step.get("agent", "")]
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, name, held.path)

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(name, output),))

    return AgentLaunch(
        output=document_file(run, held, name),
        validate=document_check(run, name),
        outcome=CONTRACTS_OUTCOME if name == SPEC else DATA_MODEL_OUTCOME if name == DATA_MODEL else CRITERIA_OUTCOME,
        accept=accept,
        add_dirs=author_dirs(run, held),
        files=author_files(run, name),
        hand_inputs=False,
    )


@script_step(UI_APPEND)
def ui_section(run: StepRun) -> Completion:
    """Write the UI design sources section at the end of a frontend repository's contracts.

    Returns:
        The contracts document, which now names the design source of each UI item.

    """
    spec: Path = run.inputs.file(SPEC)
    run.tools.portfolio(UI_APPEND, specui.spec_ui_append, spec, run.inputs.file(UI_SOURCES))
    return Completion(artifacts=(file_artifact(SPEC, spec),))


def built_line(item: Mapping[str, JsonValue], names: Mapping[str, str], matrix: Matrix) -> str:
    """Render one thing a Story builds, as its Story document lists it.

    An event that names no publisher or no trigger raises ``ValueError`` from
    ``hierarchy.event_text``.

    Args:
        item: The item, as the repository context lists it.
        names: The name of each item of the Story, by item id.
        matrix: The matrix, which gives the purpose of an item that is not an event.

    Returns:
        For an event (an item with a ``trigger``), ``<id>: <name>, published by <publishers>
        when <trigger>``; for any other item, ``<id>: <name>: <purpose>``, or ``<id>: <name>``
        when the matrix gives it no purpose.

    """
    item_id: str = check_type(item[KEY_ID], str)
    name: str = check_type(item[KEY_ELEMENT], str)
    trigger: JsonValue = item.get(KEY_TRIGGER)
    if isinstance(trigger, str):
        published_by: list[str] = strings(item.get(KEY_PUBLISHED_BY) or [])
        return hierarchy.event_text(item_id, name, hierarchy.publisher_names(published_by, names), trigger)
    matrix_id: JsonValue = item.get(KEY_MATRIX_ID)
    found: Entry | None = matrix.find(as_entry_id(matrix_id)) if isinstance(matrix_id, str) else None
    purpose: str = "" if found is None else found.purpose.strip()
    return f"{item_id}: {name}: {purpose}" if purpose else f"{item_id}: {name}"


@script_step(STORY_DOCUMENT_STEP)
def story_document(run: StepRun) -> Completion:
    """Write the Story document of one repository from its reviewed spec documents.

    Returns:
        The Story document and the architecture citations its Story carries.

    """
    held: Repository = repository(run.inputs)
    dispatch: DispatchArguments = dispatch_arguments()
    matrix: Matrix = run.tools.portfolio(STORY_DOCUMENT_STEP, read_matrix, matrix_path(None, os.environ))
    documents: list[Path] = [run.inputs.file(name) for name in (SPEC, DATA_MODEL, CRITERIA)]
    citations: list[str] = list(
        dict.fromkeys(value.strip() for path in documents[:2] for value in document(path, matrix)[0] if value.strip()),
    )
    prd: dict[str, JsonValue] = json_object(run.context.args[dispatch.KEY_PRD])
    items: list[dict[str, JsonValue]] = objects(strict_json(run.inputs.file(CONTEXT))["items"])
    names: dict[str, str] = {check_type(item[KEY_ID], str): check_type(item[KEY_ELEMENT], str) for item in items}
    lines: list[str] = [
        f"Repository: {held.path}",
        "",
        "What the Story builds:",
        *(f"- {built_line(item, names, matrix)}" for item in items),
        "",
        "Specifications:",
        *(f"- {path}" for path in documents),
    ]
    decisions: list[JsonValue] = list(citations)
    path: Path = run.context.work / f"story-{held.slug}.json"
    write_json(
        path,
        {
            "title": f"{Path(held.path).name}: {prd.get(dispatch.PRD_TITLE) or run.bead}",
            "description": "\n".join(lines),
            "decisionIds": decisions,
        },
    )
    return Completion(artifacts=(file_artifact(STORY_DOCUMENT, path), value_artifact(DECISION_IDS, decisions)))


def _task_steps(run: StepRun, held: Repository) -> StepGroup:
    """Plan the Tasks container of one repository with its first step.

    Returns:
        The container, under the Tasks container, named for the repository; its context step is
        handed everything the repository's spec steps recorded.

    """
    name: str = Path(held.path).name
    specified: Step | None = step_journal.parent_step(run.journal(), run.step["id"])
    handed: list[str] = [] if specified is None else [specified["id"]]
    first: StepPlan = {
        "description": f"Gather what the Tasks of {name} are decomposed from",
        "purpose": "The decomposer knows the items, the Tasks that exist and the steps that follow",
        "script": TASK_CONTEXT,
        "inputs": [*handed, *run.step.get("inputs", [])],
    }
    container: StepPlan = {"description": name, "purpose": TASKS_PURPOSE}
    return StepGroup(
        (NewStep(container, children=(NewStep(first, held.facts()),)),),
        UNDER_CONTAINER,
        run.step_named(TASKS_CONTAINER)["id"],
    )


@script_step(STORY_WRITE)
def story_bead(run: StepRun) -> Completion:
    """Write the Story bead of one repository, create its journal, and plan its Tasks.

    The Story is found by its elaboration key under the Epic, so a second run of this step
    refreshes the Story it wrote and creates no other.

    Returns:
        The Story as the dispatch reports it and the write's summary; the repository's Tasks
        container is planned under the Tasks container.

    """
    held: Repository = repository(run.inputs)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, STORY_WRITE, held.path)
    files: hierarchy.StoryFiles = story_files(run.inputs)
    control: Path = control_repository()

    def attempt() -> dict[str, JsonValue]:
        graph: beadgraph.Graph = run.tools.portfolio(STORY_WRITE, beadgraph.load, control, with_description=True)
        writer: beadgraph.Writer = run.tools.portfolio(STORY_WRITE, beadgraph.Writer, control)
        return json_object(
            run.tools.portfolio(
                STORY_WRITE,
                beadwrite.write_story,
                graph,
                writer,
                run.bead,
                files,
                root=project_root(),
            ),
        )

    written: dict[str, JsonValue] = run.tools.operation(STORY_WRITE, attempt)
    bead: dict[str, JsonValue] = json_object(written["story"])
    identifier: str = check_type(bead["id"], str)
    story: dict[str, JsonValue] = {
        "key": held.story_key,
        "type": "story",
        "id": identifier,
        "elabKey": bead["elabKey"],
        "title": bead["title"],
        "descriptionPath": f"{files.story}#/description",
        "repoPath": held.path,
        "parentEpicKey": run.bead,
    }
    handed: list[Artifact] = handed_on(run.inputs)
    create_child_journal(run.journal_path.parent, BeadId(identifier), BEAD_TYPE_STORY, [creating(run)], handed)
    carried: list[JsonValue] = list(strings(bead["decisionIds"]))
    return Completion(
        artifacts=(
            value_artifact(STORY, story),
            value_artifact(STORY_SUMMARY, written["summary"]),
            value_artifact(DECISION_IDS, carried),
        ),
        add=(_task_steps(run, held),),
    )
