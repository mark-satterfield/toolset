"""The steps of the build and deploy pipelines, read from their one definition.

``skills/pipeline-contracts/schemas/pipeline-steps.json`` (under ``pipeline-steps.schema.json``)
names every kind of step the build pipeline runs for a Task and the deploy pipeline runs for a
Story, what each records and reads, which steps its result adds, and the steps planned up front.
A step of these pipelines carries its kind as the journal step's ``script`` text.

This module reads that file for the plugin and for the driver: :func:`plans` gives the up-front
steps as step plans, :func:`step_plan` the plan of one step a result adds, and
:func:`open_journal` makes a bead's journal hold its up-front steps, whether elaboration created
the journal, an earlier dispatch did, or no journal exists yet.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

from jsonschema import Draft7Validator
from typeguard import CollectionCheckStrategy, typechecked

from . import step_journal

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import (
    BEAD_TYPE_STORY,
    BEAD_TYPE_TASK,
    PIPELINE_BUILD,
    PIPELINE_DEPLOY,
    BeadId,
    BeadType,
    Journal,
    JsonValue,
    Pipeline,
    Step,
    StepJournalError,
    StepPlan,
    json_value,
)

SCHEMAS_DIRECTORY: Final[Path] = Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "schemas"
DEFINITION_PATH: Final[Path] = SCHEMAS_DIRECTORY / "pipeline-steps.json"
SCHEMA_PATH: Final[Path] = SCHEMAS_DIRECTORY / "pipeline-steps.schema.json"
PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{([A-Za-z][A-Za-z0-9]*)\}")

type StepPipeline = Literal["build", "deploy"]


class PipelineStepsError(StepJournalError):
    """The pipeline steps definition is unreadable, breaks its schema or names a kind it lacks."""


@dataclass(frozen=True, slots=True)
class Recorded:
    """One artifact a step of a kind records."""

    name: str
    kind: str
    holds: str


@dataclass(frozen=True, slots=True)
class Addition:
    """Steps the result of a step of a kind adds, and the result that calls for them."""

    kinds: tuple[str, ...]
    when: str


@dataclass(frozen=True, slots=True)
class StepKind:
    """One kind of step of a pipeline."""

    key: str
    description: str
    purpose: str
    run_by: str
    within: str | None
    params: tuple[str, ...]
    reads: tuple[str, ...]
    records: tuple[Recorded, ...]
    adds: tuple[Addition, ...]
    together: bool
    waits: str | None
    limit: str | None


@dataclass(frozen=True, slots=True)
class PipelineDefinition:
    """One pipeline: its up-front kinds, the child kinds planned when a step first runs, and every kind."""

    name: StepPipeline
    plan: tuple[str, ...]
    inner: Mapping[str, tuple[str, ...]]
    kinds: Mapping[str, StepKind]


def _object(value: JsonValue, where: str) -> dict[str, JsonValue]:
    """Narrow a JSON value to an object.

    Returns:
        The object.

    Raises:
        PipelineStepsError: The value is not a JSON object.

    """
    if not isinstance(value, dict):
        message: str = f"pipeline steps: {where} is not an object"
        raise PipelineStepsError(message)
    return value


def _texts(value: JsonValue, where: str) -> tuple[str, ...]:
    """Narrow a JSON value to a tuple of strings.

    Returns:
        The strings in order; empty when the value is absent.

    Raises:
        PipelineStepsError: The value is neither absent nor a list of strings.

    """
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        message: str = f"pipeline steps: {where} is not a list of strings"
        raise PipelineStepsError(message)
    return tuple(item for item in value if isinstance(item, str))


def _text(value: JsonValue, where: str) -> str:
    """Narrow a JSON value to a string.

    Returns:
        The string.

    Raises:
        PipelineStepsError: The value is not a string.

    """
    if not isinstance(value, str):
        message: str = f"pipeline steps: {where} is not a string"
        raise PipelineStepsError(message)
    return value


def _optional_text(value: JsonValue, where: str) -> str | None:
    """Narrow a JSON value to a string, or to None when it is absent.

    Returns:
        The string, or None.

    """
    return None if value is None else _text(value, where)


def _kind(key: str, raw: JsonValue) -> StepKind:
    """Read one kind of step.

    Returns:
        The kind.

    """
    where: str = f"kind {key}"
    entry: dict[str, JsonValue] = _object(raw, where)
    recorded: JsonValue = entry.get("records")
    added: JsonValue = entry.get("adds")
    return StepKind(
        key=key,
        description=_text(entry.get("description"), f"{where} description"),
        purpose=_text(entry.get("purpose"), f"{where} purpose"),
        run_by=_text(entry.get("runBy"), f"{where} runBy"),
        within=_optional_text(entry.get("within"), f"{where} within"),
        params=_texts(entry.get("params"), f"{where} params"),
        reads=_texts(entry.get("reads"), f"{where} reads"),
        records=tuple(
            Recorded(
                _text(_object(item, where).get("name"), f"{where} records name"),
                _text(_object(item, where).get("kind"), f"{where} records kind"),
                _text(_object(item, where).get("holds"), f"{where} records holds"),
            )
            for item in (recorded if isinstance(recorded, list) else [])
        ),
        adds=tuple(
            Addition(
                _texts(_object(item, where).get("kinds"), f"{where} adds kinds"),
                _text(_object(item, where).get("when"), f"{where} adds when"),
            )
            for item in (added if isinstance(added, list) else [])
        ),
        together=entry.get("together") is True,
        waits=_optional_text(entry.get("waits"), f"{where} waits"),
        limit=_optional_text(entry.get("limit"), f"{where} limit"),
    )


def _pipeline(name: StepPipeline, raw: JsonValue) -> PipelineDefinition:
    """Read one pipeline and check that every kind it names is defined.

    Returns:
        The pipeline.

    Raises:
        PipelineStepsError: The plan, a child plan, an addition or a ``within`` names a kind the
            pipeline does not define.

    """
    entry: dict[str, JsonValue] = _object(raw, f"pipeline {name}")
    kinds: dict[str, StepKind] = {
        key: _kind(key, value) for key, value in _object(entry.get("kinds"), f"{name} kinds").items()
    }
    plan: tuple[str, ...] = _texts(entry.get("plan"), f"{name} plan")
    inner: dict[str, tuple[str, ...]] = {
        key: _texts(value, f"{name} inner {key}") for key, value in _object(entry.get("inner"), f"{name} inner").items()
    }
    named: set[str] = {*plan, *inner, *(key for keys in inner.values() for key in keys)}
    kind: StepKind
    for kind in kinds.values():
        named.update(key for addition in kind.adds for key in addition.kinds)
        if kind.within is not None:
            named.add(kind.within)
    unknown: list[str] = sorted(named - set(kinds))
    if unknown:
        message: str = f"pipeline steps: {name} names kinds it does not define: {', '.join(unknown)}"
        raise PipelineStepsError(message)
    return PipelineDefinition(name=name, plan=plan, inner=inner, kinds=kinds)


def _read(path: Path) -> JsonValue:
    """Read one JSON file of the definition.

    Returns:
        The decoded document.

    Raises:
        PipelineStepsError: The file is missing, unreadable or not JSON.

    """
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        message: str = f"cannot read the pipeline steps file {path}: {error}"
        raise PipelineStepsError(message) from error
    return json_value(decoded)


@lru_cache(maxsize=1)
def _definitions() -> dict[StepPipeline, PipelineDefinition]:
    """Load and validate the definition once.

    Returns:
        The build and deploy pipelines.

    Raises:
        PipelineStepsError: The definition does not satisfy its schema.

    """
    document: JsonValue = _read(DEFINITION_PATH)
    schema: dict[str, JsonValue] = _object(_read(SCHEMA_PATH), "the schema")
    problems: list[str] = sorted(
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in Draft7Validator(schema).iter_errors(document)
    )
    if problems:
        message: str = f"{DEFINITION_PATH} does not satisfy {SCHEMA_PATH.name}: " + "; ".join(problems)
        raise PipelineStepsError(message)
    pipelines: dict[str, JsonValue] = _object(_object(document, "the document").get("pipelines"), "pipelines")
    return {
        PIPELINE_BUILD: _pipeline(PIPELINE_BUILD, pipelines.get(PIPELINE_BUILD)),
        PIPELINE_DEPLOY: _pipeline(PIPELINE_DEPLOY, pipelines.get(PIPELINE_DEPLOY)),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def definition(pipeline: Pipeline) -> PipelineDefinition:
    """Read the steps of the build or the deploy pipeline.

    A definition file that is unreadable or breaks its schema raises ``PipelineStepsError``.

    Args:
        pipeline: ``build`` or ``deploy``.

    Returns:
        The pipeline's up-front kinds, child plans and kinds.

    Raises:
        PipelineStepsError: The pipeline's steps are not defined here (elaboration plans its own).

    """
    if pipeline == PIPELINE_BUILD:
        return _definitions()[PIPELINE_BUILD]
    if pipeline == PIPELINE_DEPLOY:
        return _definitions()[PIPELINE_DEPLOY]
    message: str = f"the steps of the {pipeline} pipeline are not defined in {DEFINITION_PATH.name}"
    raise PipelineStepsError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def pipeline_of(bead_type: BeadType) -> StepPipeline:
    """Name the pipeline whose steps a Story's or a Task's journal lists.

    Args:
        bead_type: ``story`` or ``task``.

    Returns:
        ``deploy`` for a Story, ``build`` for a Task.

    Raises:
        PipelineStepsError: The bead is an Epic, whose journal lists elaboration steps.

    """
    if bead_type == BEAD_TYPE_STORY:
        return PIPELINE_DEPLOY
    if bead_type == BEAD_TYPE_TASK:
        return PIPELINE_BUILD
    message: str = f"a bead of type {bead_type} has no build or deploy pipeline"
    raise PipelineStepsError(message)


def _filled(text: str, params: Mapping[str, JsonValue], kind: str) -> str:
    """Replace each ``{name}`` of a description with the parameter of that name.

    Returns:
        The text with every placeholder replaced.

    Raises:
        PipelineStepsError: A placeholder names a parameter the step is not handed as text.

    """
    filled: str = text
    name: str
    for name in dict.fromkeys(PLACEHOLDER.findall(text)):
        held: JsonValue = params.get(name)
        if not isinstance(held, str) or not held:
            message: str = f"a step of kind {kind} needs the text parameter {name!r} for its description"
            raise PipelineStepsError(message)
        filled = filled.replace(f"{{{name}}}", held)
    return filled


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def step_plan(
    pipeline: Pipeline,
    kind: str,
    params: Mapping[str, JsonValue] | None = None,
    *,
    purpose: str | None = None,
    ref: str | None = None,
) -> StepPlan:
    """Build the plan of one step of a kind, as the journal takes it.

    Args:
        pipeline: ``build`` or ``deploy``.
        kind: The kind's key.
        params: The parameters the step is handed; they fill the description's placeholders.
        purpose: The finding that caused the step, in place of the kind's own purpose.
        ref: The name later plans of the same change use for this step.

    Returns:
        The plan: the description, the purpose and the kind as the ``script`` text.

    Raises:
        PipelineStepsError: The pipeline defines no such kind.

    """
    kinds: Mapping[str, StepKind] = definition(pipeline).kinds
    if kind not in kinds:
        message: str = f"the {pipeline} pipeline defines no step kind {kind!r}"
        raise PipelineStepsError(message)
    found: StepKind = kinds[kind]
    plan: StepPlan = {
        "description": _filled(found.description, params or {}, kind),
        "purpose": purpose if purpose is not None and purpose.strip() else found.purpose,
        "script": kind,
    }
    if ref is not None:
        plan["ref"] = ref
    return plan


def _ordered(pipeline: Pipeline, keys: tuple[str, ...]) -> list[StepPlan]:
    """Build the plans of kinds that run in order, each naming the earlier ones it reads.

    Returns:
        One plan per key. Its ref is the key, and its inputs are the refs of the earlier plans
        that record an artifact it reads.

    """
    kinds: Mapping[str, StepKind] = definition(pipeline).kinds
    built: list[StepPlan] = []
    position: int
    key: str
    for position, key in enumerate(keys):
        plan: StepPlan = step_plan(pipeline, key, ref=key)
        wanted: set[str] = set(kinds[key].reads)
        inputs: list[str] = [
            earlier for earlier in keys[:position] if wanted & {recorded.name for recorded in kinds[earlier].records}
        ]
        if inputs:
            plan["inputs"] = inputs
        built.append(plan)
    return built


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def plans(pipeline: Pipeline) -> list[StepPlan]:
    """Build the steps a pipeline plans up front, in the order they run.

    A pipeline this module does not define raises ``PipelineStepsError``.

    Args:
        pipeline: ``build`` or ``deploy``.

    Returns:
        One plan per up-front kind.

    """
    return _ordered(pipeline, definition(pipeline).plan)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def inner_plans(pipeline: Pipeline, parent_kind: str) -> list[StepPlan]:
    """Build the child steps a workflow script plans under a step when it first runs.

    Args:
        pipeline: ``build`` or ``deploy``.
        parent_kind: The kind of the step the workflow script performs.

    Returns:
        One plan per child kind, in the order they run.

    Raises:
        PipelineStepsError: The pipeline plans no child steps under that kind.

    """
    inner: Mapping[str, tuple[str, ...]] = definition(pipeline).inner
    if parent_kind not in inner:
        message: str = f"the {pipeline} pipeline plans no child steps under {parent_kind!r}"
        raise PipelineStepsError(message)
    return _ordered(pipeline, inner[parent_kind])


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def is_planned(journal: Journal) -> bool:
    """Tell whether a journal already holds a step of its pipeline's up-front plan.

    A journal of a pipeline this module does not define raises ``PipelineStepsError``.

    Args:
        journal: The journal of a Story or a Task.

    Returns:
        True when an outermost step carries an up-front kind as its ``script`` text.

    """
    planned: set[str] = set(definition(journal["pipeline"]).plan)
    return any(step.get("script") in planned for step in journal["steps"])


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def ensure_planned(journal: Journal, moment: str) -> list[Step]:
    """Add the up-front steps of a journal's pipeline after its last outermost step, once.

    A journal that already holds an up-front step is left as it is, so calling this again
    changes nothing.

    Args:
        journal: The journal of a Story or a Task; changed in place.
        moment: The present date-time, as ``step_journal.timestamp`` gives it.

    Returns:
        The steps added; empty when the journal already held its plan.

    """
    if is_planned(journal):
        return []
    return step_journal.add_steps(journal, plans(journal["pipeline"]), moment)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def open_journal(directory: Path, bead: BeadId, bead_type: BeadType) -> Path:
    """Make the journal of a Story or a Task hold its pipeline's up-front steps.

    A bead with no journal gets one whose steps are the up-front plan. A journal that holds only
    the step that created the bead gets the plan after that step. A journal that already holds
    the plan is not written. No step's status changes.

    Args:
        directory: The directory that holds step journals (``step_journal.journals_directory``).
        bead: The Story or Task bead id.
        bead_type: ``story`` or ``task``.

    Returns:
        The journal file.

    Raises:
        PipelineStepsError: The journal on disk lists another pipeline's steps.

    """
    pipeline: StepPipeline = pipeline_of(bead_type)
    path: Path = step_journal.journal_path(directory, bead)
    if not path.is_file():
        step_journal.create_journal(path, step_journal.new_journal(bead, bead_type, pipeline, plans(pipeline)))
        return path
    existing: Journal = step_journal.read_journal(path)
    if existing["pipeline"] != pipeline:
        message: str = f"the journal {path} lists {existing['pipeline']} steps, not {pipeline} steps"
        raise PipelineStepsError(message)
    if not is_planned(existing):
        step_journal.update_journal(path, lambda journal: ensure_planned(journal, step_journal.timestamp()))
    return path


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def runner_of(pipeline: Pipeline, kind: str) -> str:
    """Name what runs the steps of a kind.

    Args:
        pipeline: ``build`` or ``deploy``.
        kind: The kind's key.

    Returns:
        ``driver``, or the name of the workflow script.

    Raises:
        PipelineStepsError: The pipeline defines no such kind.

    """
    kinds: Mapping[str, StepKind] = definition(pipeline).kinds
    if kind not in kinds:
        message: str = f"the {pipeline} pipeline defines no step kind {kind!r}"
        raise PipelineStepsError(message)
    return kinds[kind].run_by
