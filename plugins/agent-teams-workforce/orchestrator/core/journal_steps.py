"""What the code of one step journal step is given, and what it hands back.

The journal runner (``journal_run``) finds the code of a step in the registry
(``journal_registry``): a script step's ``script`` text is the key of a handler, and an agent
step's ``agent`` name is the key of a launch builder. Both receive a :class:`StepRun`: the step,
the journal, the run context, the tools, and the artifacts of the steps its ``inputs`` name
(:class:`StepInputs`). A handler never looks for an earlier output by a file name, a glob or a
derived path.

A script handler returns a :class:`Completion`; an agent builder returns an :class:`AgentLaunch`
whose ``accept`` function returns one when the session's output is accepted. The runner writes a
completion to the journal as one change (``journal_changes.apply_completion``): the step's
artifacts, every step the result plans, the record of each planned step, and the step's done mark.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from typeguard import CollectionCheckStrategy, typechecked

from . import step_journal
from .agents import AgentRunner
from .handback_contract import OTHER_CAUSE
from .models import OutputValidator, RunContext, StepError
from .tools import Tools

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import (
    KIND_DIRECTORY,
    KIND_FILE,
    KIND_VALUE,
    Artifact,
    BeadId,
    Journal,
    JsonValue,
    PathArtifact,
    Step,
    StepId,
    StepPlan,
    ValueArtifact,
)

type Where = Literal["after", "under-self", "under"]
AFTER_THIS: Final[Literal["after"]] = "after"
"""The planned steps follow the completing step, among its siblings."""
UNDER_THIS: Final[Literal["under-self"]] = "under-self"
"""The planned steps are child steps of the completing step, which stays running until they are done."""
UNDER_CONTAINER: Final[Literal["under"]] = "under"
"""The planned steps are the last child steps of a container step planned earlier."""
JOURNAL_LABEL: Final = "step journal"
"""The label of the journal file among the inputs of every agent step's brief."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def stage_of(step: Step) -> str:
    """Name a step in a failure, a session row and a stream file name.

    Returns:
        The step's script key, else its agent name, else its description.

    """
    return step.get("script") or step.get("agent") or step["description"]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def file_artifact(name: str, path: Path) -> PathArtifact:
    """Build the artifact that records a file a step wrote.

    Returns:
        The file artifact.

    """
    return {"name": name, "kind": KIND_FILE, "path": str(path)}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def directory_artifact(name: str, path: Path) -> PathArtifact:
    """Build the artifact that records a directory a step wrote.

    Returns:
        The directory artifact.

    """
    return {"name": name, "kind": KIND_DIRECTORY, "path": str(path)}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def value_artifact(name: str, value: JsonValue) -> ValueArtifact:
    """Build the artifact that records a result that is not a file.

    Returns:
        The value artifact.

    """
    return {"name": name, "kind": KIND_VALUE, "value": value}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class StepInputs:
    """Artifacts a step is handed, looked up by name.

    ``sources`` are in the order the step's ``inputs`` name them. When two of them hold an
    artifact of the same name, the single-artifact lookups return the later one and the list
    lookups return every one in order.
    """

    step: StepId
    description: str
    stage: str
    sources: tuple[tuple[Artifact, ...], ...]

    def _named(self, name: str) -> list[Artifact]:
        return [artifact for source in self.sources for artifact in source if artifact["name"] == name]

    def _evidence(self, name: str, problem: str) -> tuple[str, ...]:
        return (f"step {self.step} ({self.description}): {problem} {name!r}",)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def has(self, name: str) -> bool:
        """Tell whether an artifact of this name was handed over.

        Returns:
            True when at least one source holds it.

        """
        return bool(self._named(name))

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def files(self, name: str) -> list[Path]:
        """Read every file or directory artifact of this name.

        Returns:
            Their paths in source order; empty when there is none.

        """
        return [Path(artifact["path"]) for artifact in self._named(name) if artifact["kind"] != KIND_VALUE]

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def values(self, name: str) -> list[JsonValue]:
        """Read every value artifact of this name.

        Returns:
            Their values in source order; empty when there is none.

        """
        return [artifact["value"] for artifact in self._named(name) if artifact["kind"] == KIND_VALUE]

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def optional_file(self, name: str) -> Path | None:
        """Read the file or directory artifact of this name, when there is one.

        Returns:
            Its path, or None.

        """
        found: list[Path] = self.files(name)
        return found[-1] if found else None

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def file(self, name: str) -> Path:
        """Read the file or directory artifact of this name.

        Returns:
            Its path.

        Raises:
            StepError: No source holds a file or directory artifact of this name.

        """
        found: Path | None = self.optional_file(name)
        if found is None:
            raise StepError(self.stage, OTHER_CAUSE, self._evidence(name, "is handed no file artifact named"))
        return found

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def optional_value(self, name: str, default: JsonValue = None) -> JsonValue:
        """Read the value artifact of this name, when there is one.

        Returns:
            Its value, or ``default``.

        """
        found: list[JsonValue] = self.values(name)
        return found[-1] if self._has_value(name) else default

    def _has_value(self, name: str) -> bool:
        return any(artifact["kind"] == KIND_VALUE for artifact in self._named(name))

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def value(self, name: str) -> JsonValue:
        """Read the value artifact of this name.

        Returns:
            Its value.

        Raises:
            StepError: No source holds a value artifact of this name.

        """
        if not self._has_value(name):
            raise StepError(self.stage, OTHER_CAUSE, self._evidence(name, "is handed no value artifact named"))
        return self.values(name)[-1]

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def labelled_files(self) -> list[tuple[str, Path]]:
        """List every file and directory artifact with its name, for an agent's brief.

        Returns:
            Each distinct name and path pair, in source order.

        """
        pairs: list[tuple[str, Path]] = [
            (artifact["name"], Path(artifact["path"]))
            for source in self.sources
            for artifact in source
            if artifact["kind"] != KIND_VALUE
        ]
        return list(dict.fromkeys(pairs))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class StepRun:
    """Everything the code of one step is given.

    ``inputs`` are the artifacts of the steps the step's ``inputs`` name. ``saved`` are the
    artifacts the step itself held from an earlier, unfinished run of it (for example the request
    file of a helper another agent's session started), read before the step was started again.
    ``agents`` is the dispatch's session runner, for a step whose code runs sessions of its own
    and for the event sink of the dispatch.
    """

    step: Step
    bead: BeadId
    journal_path: Path
    context: RunContext
    tools: Tools
    agents: AgentRunner
    inputs: StepInputs
    saved: StepInputs

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def journal(self) -> Journal:
        """Read the journal as it stands now.

        A journal that cannot be read or does not conform raises ``StepJournalError``.

        Returns:
            The journal.

        """
        return step_journal.read_journal(self.journal_path)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def params(self) -> Mapping[str, JsonValue]:
        """Read the parameters the step that planned this step handed it.

        Returns:
            The value artifact ``for <this step id>`` among the inputs, or an empty mapping when
            no step planned this one with parameters.

        Raises:
            StepError: That artifact is not a JSON object.

        """
        name: str = step_journal.planned_for_name(self.step["id"])
        held: JsonValue = self.inputs.optional_value(name, {})
        if not isinstance(held, dict):
            raise StepError(
                self.inputs.stage,
                OTHER_CAUSE,
                (f"step {self.step['id']} ({self.step['description']}): the artifact {name!r} is not an object",),
            )
        return held

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def step_named(self, description: str) -> Step:
        """Find the one step of the journal with this description, for example a container.

        Returns:
            The step.

        Raises:
            StepError: No step, or more than one, has the description.

        """
        found: list[Step] = [
            step for step in step_journal.steps_in_order(self.journal()) if step["description"] == description
        ]
        if len(found) != 1:
            raise StepError(
                self.inputs.stage,
                OTHER_CAUSE,
                (f"step {self.step['id']}: {len(found)} steps of the journal are described {description!r}",),
            )
        return found[0]

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def earlier_sibling(self, agent: str) -> Step | None:
        """Find the nearest step before this one, in the same container, that an agent performed.

        Returns:
            The step, or None when ``agent`` performed no earlier sibling.

        """
        journal: Journal = self.journal()
        parent: Step | None = step_journal.parent_step(journal, self.step["id"])
        siblings: list[Step] = journal["steps"] if parent is None else parent["steps"]
        found: Step | None = None
        sibling: Step
        for sibling in siblings:
            if sibling["id"] == self.step["id"]:
                break
            if sibling.get("agent") == agent:
                found = sibling
        return found

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def session_holder(self, agent: str | None = None) -> Step | None:
        """Find the nearest earlier step of an agent that holds an agent session id.

        Args:
            agent: The agent; None means the agent of this step.

        Returns:
            The step, the nearest before this one in walk order, or None.

        """
        wanted: str | None = agent if agent is not None else self.step.get("agent")
        found: Step | None = None
        earlier: Step
        for earlier in step_journal.steps_in_order(self.journal()):
            if earlier["id"] == self.step["id"]:
                break
            if wanted is not None and earlier.get("agent") == wanted and "session" in earlier:
                found = earlier
        return found


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class NewStep:
    """One step a result plans.

    ``params`` are handed to the new step: the runner records them on the completing step as the
    value artifact ``for <new step id>`` and adds the completing step to the new step's
    ``inputs``. ``children`` are the new step's own child steps, for a container that is created
    with its first child; ``plan`` then holds no ``steps`` of its own.
    """

    plan: StepPlan
    params: Mapping[str, JsonValue] | None = None
    children: tuple[NewStep, ...] = ()

    def __post_init__(self) -> None:
        """Refuse child steps stated twice.

        Raises:
            ValueError: ``plan`` holds ``steps`` and ``children`` are given too.

        """
        if self.children and self.plan.get("steps"):
            message: str = f"the step {self.plan['description']!r} states its child steps twice"
            raise ValueError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class StepGroup:
    """Steps a result plans at one place of the journal, in the order they run.

    A ``ref`` of one plan can be named in the ``inputs`` of a later plan of the same group.
    ``follows`` places a group that goes after the completing step behind another sibling of it
    instead. ``unless_agent`` leaves the group out when a step at the place it goes already has
    that agent and is not done; the journal change decides it, so of several steps that complete
    at once only one adds the group.
    """

    steps: tuple[NewStep, ...]
    where: Where = AFTER_THIS
    container: StepId | None = None
    follows: StepId | None = None
    unless_agent: str | None = None

    def __post_init__(self) -> None:
        """Require a container exactly when the steps go under one.

        Raises:
            ValueError: The group is empty, ``container`` and ``where`` disagree, or ``follows``
                is given for a group that does not go after the completing step.

        """
        message: str
        if not self.steps:
            message = "a group of planned steps holds at least one step"
            raise ValueError(message)
        if self.follows is not None and self.where != AFTER_THIS:
            message = "a group names the sibling it follows only when it goes after the completing step"
            raise ValueError(message)
        if (self.where == UNDER_CONTAINER) != (self.container is not None):
            message = "a group names a container exactly when its steps go under a container planned earlier"
            raise ValueError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class Completion:
    """What one step's result records in the journal, written as one change.

    The step is marked done in that change, unless it plans child steps under itself: it then
    stays running, and the runner marks it done when those child steps are done.
    """

    artifacts: tuple[Artifact, ...] = ()
    add: tuple[StepGroup, ...] = ()

    @property
    def stays_running(self) -> bool:
        """Whether the step waits for child steps this result plans under it."""
        return any(group.where == UNDER_THIS for group in self.add)


type ScriptHandler = Callable[[StepRun], Completion]
type AcceptFunction = Callable[[StepRun, Path], Completion]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@dataclass(frozen=True)
class AgentLaunch:
    """What a launch builder decides about the session of one agent step.

    The runner adds the rest: the brief's inputs are the step's input artifacts by name, then
    ``files``, then the journal file; the request is ``request`` or the step's description; the
    session is the one the journal says to resume, else the one of ``resume_from``, else new.
    ``hand_inputs`` False keeps the step's input artifacts out of the brief, for an agent whose
    definition names its input labels: ``files`` then states every one of them.

    ``accept`` is called with the validated output path and returns what the step records. It is
    not called when the session marked the step done itself or left child steps under it.
    ``fresh_output`` False keeps a file already at ``output`` for a session that starts, for a
    document the agent updates in place.
    """

    output: Path
    validate: Path | OutputValidator
    outcome: str
    accept: AcceptFunction
    add_dirs: tuple[Path, ...] = ()
    files: tuple[tuple[str, Path], ...] = ()
    corrective: bool = True
    request: str | None = None
    resume_from: StepId | None = None
    fresh_output: bool = True
    hand_inputs: bool = True


type AgentBuilder = Callable[[StepRun], AgentLaunch]
