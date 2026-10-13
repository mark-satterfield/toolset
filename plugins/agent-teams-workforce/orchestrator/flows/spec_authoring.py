"""One repository's specification documents and its Story, as steps of the Epic's journal.

The span step plans one container per repository with its first step, the repository context.
That step gathers what the repository builds and plans the rest: for a frontend repository the UI
bundle listing, the UI sources session and its normalization; the contracts session and the
data-model session, which run together; the UI section; the acceptance-criteria session; the
review; the Story document; and the Story bead write. Each step takes the files it reads from the
artifacts of the steps its inputs name, and records what it writes right after writing it.
"""

from __future__ import annotations

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
from recon_contract import KEY_MOCKS_DIR
from target_contract import KEY_ELEMENT, KEY_ID
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
from orchestrator.flows.architecture_files import ARTIFACT_TRD
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
from orchestrator.flows.spec_authoring_ui import normalize_ui
from orchestrator.flows.trd_authoring import document

# isort: split
# The journal modules put the pipeline-contracts scripts directory on sys.path.
from step_journal_contract import BEAD_TYPE_STORY, BeadId

if TYPE_CHECKING:
    from step_journal_contract import Artifact, Step, StepPlan

    from orchestrator.core.models import OutputValidator

WORK_UI: Final = "ui-sources"
WORK_DOCUMENT: Final = "document"
"""What a step of an author agent, planned by the repository context step, does."""
DECISION_IDS: Final = "decision ids"
STORY_SUMMARY: Final = "story write"
DOCUMENT_OF: Final[dict[str, str]] = {
    AUTHOR_CONTRACTS: SPEC,
    AUTHOR_DATA_MODEL: DATA_MODEL,
    AUTHOR_CRITERIA: CRITERIA,
}
"""The spec document each author writes, by artifact name."""
SUFFIX: Final[dict[str, str]] = {SPEC: ".md", DATA_MODEL: ".data-model.md", CRITERIA: ".criteria.md"}
CONTRACTS_OUTCOME: Final = "API, event and error contracts for this repository's placed items."
DATA_MODEL_OUTCOME: Final = "Data model specification for this repository's placed items."
CRITERIA_OUTCOME: Final = "Acceptance criteria and definition of done for the saved specifications."
UI_SCHEMA: Final = "skills/artifact-handoff/schemas/spec-ui.schema.json"
CONTEXT_PURPOSE: Final = "The items this repository builds and the steps that specify them are known"
TASKS_PURPOSE: Final = "The Story has Tasks that name what to build"


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
        The check: resolving architecture citations for the contracts and the data model, a
        nonempty document for the criteria.

    """
    arch: Path = architecture_root(run)
    return nonempty if name == CRITERIA else lambda path: document(path, arch)


def author_files(run: StepRun, name: str) -> tuple[tuple[str, Path], ...]:
    """Name the files the author of one spec document reads.

    Returns:
        The TRD, the span, the elements and the PRD; the UI sources for the contracts of a
        frontend repository; the contracts and the data model for the criteria; then the
        repository context.

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
        The Epic's work directory, the architecture root, the PRD's folder and the repository.

    """
    return (run.context.work, architecture_root(run), run.inputs.file(PRD).parent, Path(held.path))


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


@script_step(SPEC_CONTEXT)
def context(run: StepRun) -> Completion:
    """Gather what one repository builds, and plan the steps that specify it.

    Returns:
        The repository, its context file and the PRD as artifacts, with the repository's other
        steps planned after this one.

    Raises:
        StepError: The span places no item in the repository.

    """
    held: Repository = repository_of(dict(run.params()), SPEC_CONTEXT)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, SPEC_CONTEXT, held.path)
    dispatch: DispatchArguments = dispatch_arguments()
    placed: dict[str, JsonValue] = json_object(
        run.tools.portfolio(SPEC_CONTEXT, hierarchy.placed_items, span_files(run.inputs)),
    )
    items: list[JsonValue] = [item for item in placed.values() if json_object(item)["slug"] == held.slug]
    if not items:
        raise StepError(SPEC_CONTEXT, OTHER_CAUSE, (f"the span places no item in {held.path}",))
    prd: Path = Path(check_type(json_object(run.context.args[dispatch.KEY_PRD])[dispatch.PRD_PATH], str)).resolve()
    path: Path = run.context.work / f"spec-{held.slug}.context.json"
    write_json(
        path,
        {
            "repoPath": held.path,
            "slug": held.slug,
            "frontend": held.frontend,
            "items": items,
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
        outcome="UI design sources for this repository's placed items.",
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
    """Keep the UI choices of placed items and replace a bundle that cannot be built from.

    Returns:
        The UI sources file, and the warnings the normalization raised.

    """
    held: Repository = repository(run.inputs)
    placed: set[str] = {
        check_type(item[KEY_ID], str) for item in objects(strict_json(run.inputs.file(CONTEXT))["items"])
    }
    normalized: dict[str, JsonValue] = normalize_ui(
        strict_json(run.inputs.file(UI_CANDIDATE)),
        placed,
        strict_json(run.inputs.file(UI_BUNDLE_LIST)),
        run.tools,
    )
    normalized[KEY_MOCKS_DIR] = design_system(run).get(dispatch_arguments().DS_MOCKS_DIR)
    path: Path = run.context.work / f"spec-{held.slug}.ui.json"
    write_json(path, normalized)
    return Completion(artifacts=(file_artifact(UI_SOURCES, path), value_artifact(WARNINGS, normalized["warnings"])))


def spec_document(run: StepRun) -> AgentLaunch:
    """Build the session that writes one spec document of a repository.

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


@script_step(STORY_DOCUMENT_STEP)
def story_document(run: StepRun) -> Completion:
    """Write the Story document of one repository from its reviewed spec documents.

    Returns:
        The Story document and the architecture citations its Story carries.

    """
    held: Repository = repository(run.inputs)
    dispatch: DispatchArguments = dispatch_arguments()
    arch: Path = architecture_root(run)
    documents: list[Path] = [run.inputs.file(name) for name in (SPEC, DATA_MODEL, CRITERIA)]
    cited: list[str] = list(
        dict.fromkeys(value.strip() for path in documents[:2] for value in document(path, arch)[0] if value.strip()),
    )
    prd: dict[str, JsonValue] = json_object(run.context.args[dispatch.KEY_PRD])
    items: list[dict[str, JsonValue]] = objects(strict_json(run.inputs.file(CONTEXT))["items"])
    lines: list[str] = [
        f"Repository: {held.path}",
        "",
        "Placed items:",
        *(f"- {item[KEY_ID]}: {item[KEY_ELEMENT]}" for item in items),
        "",
        "Specifications:",
        *(f"- {path}" for path in documents),
    ]
    decisions: list[JsonValue] = list(cited)
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
    cited: list[JsonValue] = list(strings(bead["decisionIds"]))
    return Completion(
        artifacts=(
            value_artifact(STORY, story),
            value_artifact(STORY_SUMMARY, written["summary"]),
            value_artifact(DECISION_IDS, cited),
        ),
        add=(_task_steps(run, held),),
    )
