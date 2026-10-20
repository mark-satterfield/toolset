"""The names the steps after the TRD share, and how a step reads what the journal hands it.

A step of the Specs and Stories, Tasks, Task edges and finish parts of an elaboration takes every
earlier output from the artifacts of the steps its ``inputs`` name. The artifact names are here,
with the script keys and agent names of those steps, and the readers that turn a step's inputs
into the file sets the portfolio functions take. No reader derives a path.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# The driver surface is defined once, in the pipeline-contracts skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
import hierarchy
import strictschema
from driver_surface_types import CONTROL_REPO_ENV
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, write_json
from orchestrator.core.journal_steps import StepInputs, StepRun, file_artifact, stage_of
from orchestrator.core.models import StepError
from orchestrator.core.tools import env_path
from orchestrator.flows.architecture_files import ARTIFACT_TRD

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import Artifact, Step, StepPlan

SPECS_CONTAINER: Final = "Specs and Stories"
TASKS_CONTAINER: Final = "Tasks"
EDGES_CONTAINER: Final = "Task edges"
"""The descriptions of the outermost steps that contain one step per repository, or the edge steps."""

SPEC_CONTEXT: Final = "spec_authoring.context"
UI_BUNDLES: Final = "cdsbundles.list_bundles"
UI_NORMALIZE: Final = "spec_authoring.normalize_ui"
UI_APPEND: Final = "specui.spec_ui_append"
STORY_DOCUMENT_STEP: Final = "spec_authoring.story_document"
STORY_WRITE: Final = "beadwrite.write_story"
TASK_CONTEXT: Final = "task_decomposition.context"
TASK_PLAN: Final = "beadwrite.plan_story_tasks"
TASK_WRITE: Final = "beadwrite.write_task"
TASK_RETIRE: Final = "beadwrite.retire_superseded_tasks"
TASK_RECORD: Final = "task_decomposition.record"
EDGE_CLOSURE: Final = "beadwrite.closure_task_edges"
EDGE_LISTING: Final = "task_edges.listing"
EDGE_WRITE: Final = "beadwrite.write_all_task_edges"
SCORE: Final = "elaboration.score"
DONE_RULE_STEP: Final = "elaboration.done_rule"
STORY_EDGES: Final = "storyedges.story_edges"
MARK_DONE: Final = "elaboration.finish"
"""The script keys of the steps after the TRD, as the journal shows them."""

AUTHOR_CONTRACTS: Final = "api-specification-author"
AUTHOR_DATA_MODEL: Final = "data-model-specification-author"
AUTHOR_CRITERIA: Final = "acceptance-criteria-writer"
REVIEWER: Final = "openapi-contract-reviewer"
DECIDER: Final = "spec-decider"
DECOMPOSER: Final = "task-decomposer"
MAPPER: Final = "task-dependency-mapper"
"""The agents that perform the agent steps after the TRD."""

ARTIFACT_SPAN: Final = "span"
ARTIFACT_ELEMENTS: Final = "elements"
ARTIFACT_REPOSITORIES: Final = "repositories"
ARTIFACT_CREATION: Final = "repository creation"
REPOSITORY: Final = "repository"
CONTEXT: Final = "repository context"
UI_BUNDLE_LIST: Final = "ui bundles"
UI_CANDIDATE: Final = "ui sources as authored"
UI_SOURCES: Final = "ui sources"
SPEC: Final = "spec"
DATA_MODEL: Final = "data model"
CRITERIA: Final = "criteria"
STORY_DOCUMENT: Final = "story document"
STORY: Final = "story"
TASK_CONTEXT_FILE: Final = "task context"
TASKS_FILE: Final = "tasks"
TASK_GAPS: Final = "task gaps"
TASK_CORRECTION: Final = "task correction"
TASK_PLAN_RECORD: Final = "task plan"
TASK: Final = "task"
TASK_KEY: Final = "task key"
TASK_EDGE_COUNTS: Final = "task edge counts"
TASKS_RESULT: Final = "tasks result"
CLOSURE_EDGES: Final = "closure edges"
EDGE_LIST: Final = "task dependency listing"
TASK_DEPS: Final = "task dependencies"
EDGES_RESULT: Final = "edges result"
UNSCORED: Final = "unscored tasks"
DONE_RULE: Final = "done rule"
STORY_EDGES_RESULT: Final = "story edges"
LIFECYCLE_DONE: Final = "lifecycle done"
WARNINGS: Final = "warnings"
"""The names of the artifacts the steps after the TRD record in the journal."""

SPEC_FILES: Final[tuple[str, ...]] = (SPEC, DATA_MODEL, CRITERIA)
"""The artifact names of one repository's three spec documents, in the order they are written."""
WORK: Final = "work"
"""The parameter that says which of an agent's kinds of step a planned step is."""
_SLUG: Final = re.compile(r"[A-Za-z0-9._-]+")

SCHEMAS: Final[Path] = Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "schemas"
"""The artifact-handoff skill's schema folder: the one home of every file contract a step writes for an agent."""
SPEC_CONTEXT_SCHEMA: Final = "spec-context.schema.json"
TASK_CONTEXT_SCHEMA: Final = "task-context.schema.json"
TASK_DEPS_SCHEMA: Final = "task-deps.schema.json"
STORY_DOCUMENT_SCHEMA: Final = "story-document.schema.json"
UI_BUNDLES_SCHEMA: Final = "ui-bundles.schema.json"
CLOSURE_EDGES_SCHEMA: Final = "closure-edges.schema.json"
LISTING_SCHEMA: Final = "task-dependency-listing.schema.json"
"""The contract files of the files the steps write for agents, by file name under :data:`SCHEMAS`."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_contract(path: Path, value: Mapping[str, JsonValue], schema: str) -> Path:
    """Write a file a step hands an agent, after checking it against its contract file.

    A value that fails its contract is a defect of the step that built it, so it raises
    ``jsonschema.ValidationError`` and nothing is written.

    Args:
        path: Where the file is written.
        value: The file's content.
        schema: The contract's file name under :data:`SCHEMAS`.

    Returns:
        ``path``.

    """
    contract: Path = SCHEMAS / schema
    strictschema.validate(dict(value), strict_json(contract), location=contract)
    write_json(path, value)
    return path


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def strings(value: JsonValue) -> list[str]:
    """Narrow a journal value to a list of strings.

    Returns:
        The list; a value that is not one raises ``TypeCheckError``.

    """
    return check_type(value, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def objects(value: JsonValue) -> list[dict[str, JsonValue]]:
    """Narrow a journal value to a list of JSON objects.

    Returns:
        The list; a value that is not one raises ``TypeCheckError``.

    """
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class Repository:
    """One repository of the span, as the step that plans its steps hands it on."""

    path: str
    slug: str
    story_key: str
    frontend: bool

    def facts(self) -> dict[str, JsonValue]:
        """Give the repository as the value a step records and hands on.

        Returns:
            The repository path, its slug, its Story key and whether it is a frontend repository.

        """
        return {"repoPath": self.path, "slug": self.slug, "storyKey": self.story_key, "frontend": self.frontend}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_of(value: JsonValue, stage: str) -> Repository:
    """Read a repository from the value a step was handed.

    Args:
        value: The parameters or the recorded ``repository`` value.
        stage: The step that reads it, named in a failure.

    Returns:
        The repository.

    Raises:
        StepError: The value is not a repository, or its slug cannot be part of a file name.

    """
    if not isinstance(value, dict):
        raise StepError(stage, OTHER_CAUSE, ("the step was handed no repository",))
    path: JsonValue = value.get("repoPath")
    slug: JsonValue = value.get("slug")
    key: JsonValue = value.get("storyKey")
    if not isinstance(path, str) or not path or not isinstance(slug, str) or not isinstance(key, str):
        raise StepError(stage, OTHER_CAUSE, (f"not a repository of the span: {value!r}",))
    if _SLUG.fullmatch(slug) is None or slug in {".", ".."}:
        raise StepError(stage, OTHER_CAUSE, (f"invalid repository slug {slug!r}",))
    return Repository(str(Path(path).resolve()), slug, key, value.get("frontend") is True)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository(inputs: StepInputs) -> Repository:
    """Read the repository a step works on from the artifacts it is handed.

    Returns:
        The repository the context step of its container recorded.

    """
    return repository_of(inputs.value(REPOSITORY), inputs.stage)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def span_files(inputs: StepInputs) -> hierarchy.SpanFiles:
    """Name the two files the span step wrote, from the artifacts a step is handed.

    Returns:
        The span file and the elements file.

    """
    return hierarchy.SpanFiles(inputs.file(ARTIFACT_SPAN), inputs.file(ARTIFACT_ELEMENTS))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_files(inputs: StepInputs, scope: hierarchy.SpanFiles | None = None) -> hierarchy.StoryFiles:
    """Name one repository's saved files, from the artifacts a step is handed.

    Args:
        inputs: The artifacts of one repository's steps.
        scope: The span's files, when ``inputs`` do not hold them.

    Returns:
        The Story document, the spec documents, and the Tasks file when one is handed.

    """
    held: Repository = repository(inputs)
    return hierarchy.StoryFiles(
        slug=held.slug,
        repo=held.path,
        scope=scope or span_files(inputs),
        story=inputs.file(STORY_DOCUMENT),
        specs=tuple(inputs.file(name) for name in SPEC_FILES),
        tasks=inputs.optional_file(TASKS_FILE),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def handed_on(inputs: StepInputs, *more: str) -> list[Artifact]:
    """List the files the later steps of a Story or a Task are handed.

    Args:
        inputs: The artifacts the creating step is handed.
        more: Further artifact names to hand on, after the spec documents, the UI sources, the
            TRD and the Story document.

    Returns:
        One file artifact per name the inputs hold, in that order.

    """
    names: tuple[str, ...] = (*SPEC_FILES, UI_SOURCES, ARTIFACT_TRD, STORY_DOCUMENT, *more)
    return [file_artifact(name, path) for name in names if (path := inputs.optional_file(name)) is not None]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def creating(run: StepRun) -> StepPlan:
    """Describe a step as the first step of the journal of a bead it creates.

    Returns:
        The step plan: this step's description, purpose and script.

    """
    return {"description": run.step["description"], "purpose": run.step["purpose"], "script": stage_of(run.step)}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repository_inputs(run: StepRun, description: str) -> list[StepInputs]:
    """Read what each repository's steps recorded under one container the step is handed.

    Args:
        run: The step that asks.
        description: The container, which the step's ``inputs`` name.

    Returns:
        One set of artifacts per repository container under it, in the order they run.

    Raises:
        StepError: The step's inputs do not name the container.

    """
    container: Step = run.step_named(description)
    if container["id"] not in run.step.get("inputs", []):
        evidence: str = f"step {run.step['id']} ({run.step['description']}) is not handed {description!r}"
        raise StepError(run.inputs.stage, OTHER_CAUSE, (evidence,))
    return [
        StepInputs(
            run.step["id"],
            run.step["description"],
            run.inputs.stage,
            (tuple(held for below in step_journal.steps_in_order_from(child) for held in below["artifacts"]),),
        )
        for child in container["steps"]
        if child["steps"]
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def span_stories(run: StepRun, task_deps: Path | None) -> hierarchy.SpanStories:
    """Name the saved files of every Story of the span, for a step that is handed both containers.

    Args:
        run: A step whose inputs name the Specs and Stories container and the Tasks container.
        task_deps: The mapper's edges file, or None when the mapper did not run.

    Returns:
        The Stories in span order, each with its Tasks file.

    Raises:
        StepError: A repository has no Tasks file on record.

    """
    scope: hierarchy.SpanFiles = span_files(run.inputs)
    decomposed: dict[str, StepInputs] = {
        repository(held).slug: held for held in repository_inputs(run, TASKS_CONTAINER)
    }
    stories: list[hierarchy.StoryFiles] = []
    for held in repository_inputs(run, SPECS_CONTAINER):
        files: hierarchy.StoryFiles = story_files(held, scope)
        tasks: StepInputs | None = decomposed.get(files.slug)
        if tasks is None:
            raise StepError(run.inputs.stage, OTHER_CAUSE, (f"the journal records no Tasks file for {files.repo}",))
        stories.append(
            hierarchy.StoryFiles(files.slug, files.repo, scope, files.story, files.specs, tasks.file(TASKS_FILE)),
        )
    return hierarchy.SpanStories(scope, tuple(stories), task_deps)


def control_repository() -> Path:
    """Name the control repository, where the bead tracker is.

    Returns:
        The path the driver surface's control repository variable holds.

    """
    return env_path(CONTROL_REPO_ENV)


def project_root() -> Path:
    """Name the project root bead metadata records file paths relative to.

    Returns:
        The path the ``SKILLSPOKE_ROOT`` variable holds.

    """
    return env_path("SKILLSPOKE_ROOT")
