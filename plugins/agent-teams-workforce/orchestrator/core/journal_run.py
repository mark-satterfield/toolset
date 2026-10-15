"""The journal runner: one dispatch is a loop over the step journal of one bead.

The loop asks the journal for the next step, runs it, and repeats until no step is left or one
fails. There is no other cursor: a restart is the same loop on the same file, so it begins at the
first step without child steps that is not done. A step is marked running before its code or its
session starts; when its output is accepted, one journal change records its artifacts, the steps
its result plans and its done mark (``journal_steps.apply_completion``).

A step that raises is marked failed with a one-line structured cause and the exception continues
to the caller unchanged. A stop request (the stop file, an interrupt) leaves the step running.

Steps run in walk order. Consecutive sibling steps that each have an agent, have no child steps
and whose inputs are all done run as concurrent sessions under the dispatch's session slots.
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from functools import partial
from pathlib import Path
from uuid import uuid4

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.flows.elaboration_support import parallel

from . import step_journal
from .agents import AgentRunner, SessionNotResumedError
from .handback import failure_for, stop_stage
from .handback_contract import OTHER_CAUSE, Failure
from .journal_changes import apply_completion
from .journal_registry import REGISTRY, Registry
from .journal_steps import (
    JOURNAL_LABEL,
    AgentBuilder,
    AgentLaunch,
    Completion,
    ScriptHandler,
    StepInputs,
    StepRun,
    stage_of,
)
from .models import AgentStep, RunContext, StepError
from .tools import Tools

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import (
    STATUS_DONE,
    STATUS_PLANNED,
    STATUS_RUNNING,
    Artifact,
    BeadId,
    BeadType,
    Journal,
    JsonValue,
    Pipeline,
    Step,
    StepId,
    StepJournalError,
    StepPlan,
)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def concurrent_group(journal: Journal, first: StepId) -> list[StepId]:
    """Name the steps that run together with the next step.

    Args:
        journal: The journal.
        first: The next step, as ``step_journal.next_step`` returns it.

    Returns:
        ``first`` alone, or ``first`` and the siblings after it that run with it: each has an
        agent, no child steps, is not done and names only done steps in its inputs. The group
        ends at the first sibling after ``first`` that is not done and does not qualify; a done
        sibling is passed over. When ``first`` itself does not qualify it runs alone.

    """
    done: set[StepId] = {step["id"] for step in step_journal.steps_in_order(journal) if step["status"] == STATUS_DONE}

    def qualifies(step: Step) -> bool:
        return "agent" in step and not step["steps"] and all(named in done for named in step.get("inputs", []))

    parent: Step | None = step_journal.parent_step(journal, first)
    siblings: list[Step] = journal["steps"] if parent is None else parent["steps"]
    position: int = next(index for index, step in enumerate(siblings) if step["id"] == first)
    if not qualifies(siblings[position]):
        return [first]
    group: list[StepId] = [first]
    sibling: Step
    for sibling in siblings[position + 1 :]:
        if sibling["status"] == STATUS_DONE:
            continue
        if not qualifies(sibling):
            break
        group.append(sibling["id"])
    return group


def _inputs(journal: Journal, step: Step) -> StepInputs:
    """Resolve the artifacts a step is handed from the journal.

    An input that has child steps hands over their artifacts too: its result is on them (an
    agent that started helpers records its result on its last child step, and a step that only
    contains steps holds nothing itself).

    Returns:
        For each step its ``inputs`` name, in that order: that step's artifacts, then those of
        every step below it in walk order.

    """
    sources: list[tuple[Artifact, ...]] = []
    named: StepId
    for named in step.get("inputs", []):
        source: Step = step_journal.find_step(journal, named)
        sources.append(tuple(held for below in step_journal.steps_in_order_from(source) for held in below["artifacts"]))
    return StepInputs(step["id"], step["description"], stage_of(step), tuple(sources))


def _open_leaf(step: Step) -> Step | None:
    """Find the first step at or below a step that has no child steps and is not done.

    Returns:
        That step in walk order, or None when every such step is done.

    """
    if not step["steps"]:
        return None if step["status"] == STATUS_DONE else step
    child: Step
    for child in step["steps"]:
        found: Step | None = _open_leaf(child)
        if found is not None:
            return found
    return None


def _held_session(journal: Journal, step: Step, launch: AgentLaunch) -> str | None:
    """Find the agent session a step continues.

    Returns:
        The session the step itself holds from an earlier, unfinished run; else the session of
        the step the launch names; else the session of the step directly above it when the same
        agent performs both (its "Finish"); else None.

    """
    held: str | None = step.get("session")
    if held is None and launch.resume_from is not None:
        held = step_journal.step_session(journal, launch.resume_from)
    if held is None:
        parent: Step | None = step_journal.parent_step(journal, step["id"])
        if parent is not None and parent.get("agent") == step.get("agent"):
            held = parent.get("session")
    return held


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def unhandled_steps(journal: Journal, registry: Registry) -> list[Step]:
    """List the steps a run would reach that the registry holds no code for.

    Returns:
        In walk order, each step without child steps that is not done and names a script key or
        an agent the registry has no handler or launch builder for.

    """
    return [
        step
        for step in step_journal.steps_in_order(journal)
        if not step["steps"]
        and step["status"] != STATUS_DONE
        and ("script" in step or "agent" in step)
        and not registry.handles(step)
    ]


class UnregisteredStepError(LookupError):
    """Steps a run would reach name a script key or an agent the registry holds no code for."""

    def __init__(self, steps: Sequence[Step]) -> None:
        """Name every such step, its description and the key or agent it names.

        Args:
            steps: The steps without code, in walk order; at least one.

        Raises:
            ValueError: ``steps`` is empty.

        """
        if not steps:
            message: str = "UnregisteredStepError needs at least one step"
            raise ValueError(message)
        self.stage: str = stage_of(steps[0])
        self.evidence: tuple[str, ...] = tuple(
            f"step {step['id']} ({step['description']}): no code is registered for {stage_of(step)!r}" for step in steps
        )
        super().__init__("; ".join(self.evidence))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def require_handled(journal: Journal, registry: Registry) -> None:
    """Check that the registry holds code for every step a run would reach.

    Args:
        journal: The journal.
        registry: The code of the steps.

    Raises:
        UnregisteredStepError: A step that is not done names a script key or an agent the
            registry holds no code for; it names every such step.

    """
    unhandled: list[Step] = unhandled_steps(journal, registry)
    if unhandled:
        raise UnregisteredStepError(unhandled)


def _nested_plans(plans: Sequence[StepPlan]) -> dict[str, tuple[StepPlan, ...]]:
    """Index the child plans a lane states up front by the description of their container.

    Returns:
        For each plan, at any depth, that states child steps: its description and those plans.

    """
    found: dict[str, tuple[StepPlan, ...]] = {
        plan["description"]: tuple(plan["steps"]) for plan in plans if plan.get("steps")
    }
    children: tuple[StepPlan, ...]
    for children in list(found.values()):
        found = {**_nested_plans(children), **found}
    return found


def _plans_at(place: str | None, plans: Sequence[StepPlan], registry: Registry) -> tuple[StepPlan, ...]:
    """Name the lane's current plans at one place of the journal.

    Args:
        place: The description of the container, or None for the outermost steps.
        plans: The outermost plans of the lane, with the child plans it states up front.
        registry: The registry, which holds the plans a flow makes under a container as it runs.

    Returns:
        The outermost plans; else the container's child plans the lane states up front; else
        those a flow registered for the container; else none.

    """
    if place is None:
        return tuple(plans)
    return _nested_plans(plans).get(place) or registry.plans_under(place)


def _current_plan(journal: Journal, step: Step, plans: Sequence[StepPlan], registry: Registry) -> StepPlan | None:
    """Find the lane's current plan for the position a step holds.

    A step's position is its container and its place among the siblings of its kind: the n-th
    script step of a container is planned by the n-th script plan the lane makes there, and the
    n-th agent step by the n-th agent plan.

    Returns:
        That plan, or None when the lane makes no plan of the step's kind at that place.

    """
    parent: Step | None = step_journal.parent_step(journal, step["id"])
    siblings: list[Step] = journal["steps"] if parent is None else parent["steps"]
    kind: str = "script" if "script" in step else "agent"
    ordinal: int = [sibling["id"] for sibling in siblings if kind in sibling].index(step["id"])
    place: str | None = None if parent is None else parent["description"]
    candidates: list[StepPlan] = [plan for plan in _plans_at(place, plans, registry) if kind in plan]
    return candidates[ordinal] if ordinal < len(candidates) else None


def _take_plan(step: Step, plan: StepPlan) -> None:
    """Give a planned step the key or agent, the description and the purpose of a plan."""
    step["description"] = plan["description"]
    step["purpose"] = plan["purpose"]
    if "script" in plan:
        step["script"] = plan["script"]
        return
    if "agent" in plan:
        step["agent"] = plan["agent"]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def replan_unhandled(journal: Journal, plans: Sequence[StepPlan], registry: Registry) -> list[StepId]:
    """Replan each planned step the registry holds no code for from the lane's current plan.

    Only a step that has not started is changed: it takes the script key or agent, the
    description and the purpose of the plan the lane makes now at its position, when the
    registry holds the code of that plan. Its id, inputs and status stay. A step that has
    started or is done is never changed.

    Args:
        journal: The journal; changed in place.
        plans: The outermost plans of the lane, with the child plans it states up front.
        registry: The code of the steps and the plans flows make under containers.

    Returns:
        The ids of the steps replanned, in walk order.

    """
    stale: list[Step] = [step for step in unhandled_steps(journal, registry) if step["status"] == STATUS_PLANNED]
    found: list[tuple[Step, StepPlan | None]] = [
        (step, _current_plan(journal, step, plans, registry)) for step in stale
    ]
    usable: list[tuple[Step, StepPlan]] = [
        (step, plan) for step, plan in found if plan is not None and registry.handles(plan)
    ]
    step: Step
    plan: StepPlan
    for step, plan in usable:
        _take_plan(step, plan)
    return [step["id"] for step, _ in usable]


class JournalRunner:
    """Runs the steps of one bead's journal, in order, from the first that is not done."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self, path: Path, agents: AgentRunner, tools: Tools, registry: Registry = REGISTRY) -> None:
        """Bind the journal file, the session runner, the tools and the code of the steps.

        A journal that cannot be read or does not conform raises ``StepJournalError``.
        """
        self.path: Path = path
        self.agents: AgentRunner = agents
        self.tools: Tools = tools
        self.registry: Registry = registry
        self.bead: BeadId = step_journal.read_journal(path)["bead"]

    @property
    def context(self) -> RunContext:
        """The run context of the dispatch: the one the session runner holds."""
        return self.agents.context

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run(self) -> None:
        """Run every step that is not done, in order, until none is left.

        A step that fails raises what it raised, after the failure is recorded in the journal.

        Raises:
            StepError: Before any step runs, when a step that is not done names a script key or
                an agent the registry holds no code for; raised from the
                ``UnregisteredStepError`` that names every such step, whose text it carries.

        """
        try:
            require_handled(step_journal.read_journal(self.path), self.registry)
        except UnregisteredStepError as error:
            raise StepError(error.stage, OTHER_CAUSE, error.evidence) from error
        while self.run_next():
            pass

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run_next(self) -> bool:
        """Run the next step, or the next group of steps that run together.

        Returns:
            False when no step was left to run; True after a step or a group ran.

        """
        self._close_finished()
        journal: Journal = step_journal.read_journal(self.path)
        first: Step | None = step_journal.next_step(journal)
        if first is None:
            return False
        group: list[StepId] = concurrent_group(journal, first["id"])
        if len(group) == 1:
            self._run_step(group[0])
        else:
            parallel(self.context, [partial(self._run_step, step_id) for step_id in group])
        self._close_finished()
        return True

    def _close_finished(self) -> None:
        """Mark done every running step whose child steps are all done."""

        def waiting(journal: Journal) -> list[Step]:
            return [step for step in step_journal.unclosed_steps(journal) if step["status"] == STATUS_RUNNING]

        def close(journal: Journal) -> None:
            moment: str = step_journal.timestamp()
            while found := waiting(journal):
                step_journal.finish_step(journal, found[-1]["id"], moment)

        if waiting(step_journal.read_journal(self.path)):
            step_journal.update_journal(self.path, close)

    def _run_step(self, step_id: StepId) -> None:
        """Run one step and record its failure when it raises."""
        journal: Journal = step_journal.read_journal(self.path)
        step: Step = step_journal.find_step(journal, step_id)
        try:
            self._perform(journal, step)
        except Exception as exc:
            self._record_failure(step_id, stage_of(step), exc)
            raise

    def _perform(self, journal: Journal, step: Step) -> None:
        """Run a step with the code its script key or its agent name selects.

        Raises:
            StepError: The step has no agent, no script and no child steps, so nothing runs it.

        """
        if "script" in step:
            self._run_script(journal, step)
        elif "agent" in step:
            self._run_agent(journal, step)
        else:
            raise StepError(
                stage_of(step),
                OTHER_CAUSE,
                (f"step {step['id']} ({step['description']}) has no agent, no script and no child steps",),
            )

    def _record_failure(self, step_id: StepId, stage: str, exc: Exception) -> None:
        """Mark a step failed with its structured cause, unless the run was asked to stop.

        A step whose session left child steps under it cannot be marked itself; the failure is
        recorded on the first of those steps that is not done, where the next dispatch starts.
        """
        if stop_stage(exc) is not None:
            return
        started: bool = any(row.get("startedAt") is not None for row in self.context.sessions)
        failure: Failure = failure_for(stage, exc, agent_started=started)
        cause: dict[str, JsonValue] = {
            "stage": failure["stage"],
            "cause": failure["cause"],
            "classification": failure["classification"],
            "message": (str(exc).splitlines() or [type(exc).__name__])[0],
        }
        if isinstance(exc, StepError) and exc.evidence:
            cause["evidence"] = list(exc.evidence)
        text: str = json.dumps(cause, ensure_ascii=False)

        def change(journal: Journal) -> None:
            target: Step | None = _open_leaf(step_journal.find_step(journal, step_id))
            if target is not None:
                step_journal.fail_step(journal, target["id"], text, step_journal.timestamp())

        try:
            step_journal.update_journal(self.path, change)
        except StepJournalError as error:
            exc.add_note(f"The failure could not be recorded in the step journal {self.path}: {error}")

    def _step_run(self, step: Step, inputs: StepInputs, saved: tuple[Artifact, ...]) -> StepRun:
        """Assemble what the code of a step is given.

        Returns:
            The step with its inputs and the artifacts it held before it was started again.

        """
        return StepRun(
            step=step,
            bead=self.bead,
            journal_path=self.path,
            context=self.context,
            tools=self.tools,
            agents=self.agents,
            inputs=inputs,
            saved=StepInputs(step["id"], step["description"], stage_of(step), (saved,)),
        )

    def _start(self, step_id: StepId, session: str | None = None, keep: tuple[Artifact, ...] = ()) -> Step:
        """Mark a step running in the journal, holding ``keep``, as one change.

        Returns:
            The running step.

        """

        def change(journal: Journal) -> Step:
            running: Step = step_journal.start_step(journal, step_id, step_journal.timestamp(), session=session)
            artifact: Artifact
            for artifact in keep:
                running = step_journal.record_artifact(journal, step_id, artifact)
            return running

        return step_journal.update_journal(self.path, change)

    def _complete(self, step_id: StepId, completion: Completion) -> None:
        """Record a step's result in the journal as one change."""
        check_type(completion, Completion, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        step_journal.update_journal(
            self.path,
            lambda journal: apply_completion(journal, step_id, completion, step_journal.timestamp()),
        )

    def _run_script(self, journal: Journal, step: Step) -> None:
        """Run a script step: start it, call its handler, record what the handler returns."""
        handler: ScriptHandler = self.registry.script(step)
        inputs: StepInputs = _inputs(journal, step)
        saved: tuple[Artifact, ...] = tuple(step["artifacts"])
        running: Step = self._start(step["id"])
        with contextlib.redirect_stdout(sys.stderr):
            completion: Completion = handler(self._step_run(running, inputs, saved))
        self._complete(step["id"], completion)

    def _run_agent(self, journal: Journal, step: Step) -> None:
        """Run an agent step: build its launch, start it with its session, run the session, record.

        After the session the journal is read again. A step the session marked done, or left
        child steps under, is not completed here; an ordinary step is completed with what the
        launch's accept function returns.
        """
        builder: AgentBuilder = self.registry.agent(step)
        inputs: StepInputs = _inputs(journal, step)
        saved: tuple[Artifact, ...] = tuple(step["artifacts"])
        launch: AgentLaunch = check_type(builder(self._step_run(step, inputs, saved)), AgentLaunch)
        held: str | None = _held_session(journal, step, launch)
        session: str = held or str(uuid4())
        run: StepRun = self._step_run(self._start(step["id"], session, launch.keep), inputs, saved)
        handed: list[tuple[str, Path]] = inputs.labelled_files() if launch.hand_inputs else []
        labelled: list[tuple[str, Path]] = list(dict.fromkeys([*handed, *launch.files, (JOURNAL_LABEL, self.path)]))
        request: AgentStep = AgentStep(
            stage=stage_of(step),
            agent=step.get("agent", ""),
            inputs=tuple(str(path) for _, path in labelled),
            output=launch.output,
            outcome=launch.outcome,
            validate=launch.validate,
            add_dirs=launch.add_dirs,
            corrective=launch.corrective,
            request=launch.request or step["description"],
            journal_step=step["id"],
        )
        output: Path = self._session(request, labelled, session, launch, resume=held is not None)
        after: Step = step_journal.find_step(step_journal.read_journal(self.path), step["id"])
        if after["status"] != STATUS_DONE and not after["steps"]:
            self._complete(step["id"], launch.accept(replace(run, step=after), output))

    def _session(
        self,
        request: AgentStep,
        labelled: list[tuple[str, Path]],
        session: str,
        launch: AgentLaunch,
        *,
        resume: bool,
    ) -> Path:
        """Run the session of an agent step, starting a new one when its conversation is gone.

        Returns:
            The validated output path.

        """
        try:
            return self.agents.run_session(
                request,
                labelled,
                session=session,
                resume=resume,
                fresh_output=launch.fresh_output,
            )
        except SessionNotResumedError:
            fresh: str = str(uuid4())
            step_id: StepId = check_type(request.journal_step, StepId)
            step_journal.update_journal(
                self.path,
                lambda journal: step_journal.set_session(journal, step_id, fresh),
            )
            return self.agents.run_session(request, labelled, session=fresh, fresh_output=launch.fresh_output)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def open_journal(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] - One call names the journal and its services.
    directory: Path,
    bead: BeadId,
    bead_type: BeadType,
    pipeline: Pipeline,
    plans: list[StepPlan],
    agents: AgentRunner,
    tools: Tools,
    registry: Registry = REGISTRY,
) -> JournalRunner:
    """Create a bead's journal when its file does not exist, and return the runner for it.

    An existing journal alone says where the run begins. Of its steps, only a step that has not
    started and names a script key or agent the registry holds no code for is changed: it is
    replanned from the lane's current plan for its position (:func:`replan_unhandled`), so a
    journal written before a key was renamed runs the step as the lane plans it now. A journal
    that cannot be created, read or validated raises ``StepJournalError``.

    Args:
        directory: The directory that holds step journals (``step_journal.journals_directory``).
        bead: The bead id.
        bead_type: The kind of bead.
        pipeline: The pipeline whose steps the journal lists.
        plans: The outermost steps of a new journal, every one planned.
        agents: The session runner of this dispatch.
        tools: The deterministic tools of this dispatch.
        registry: The code of the steps.

    Returns:
        The runner of the bead's journal.

    """
    path: Path = step_journal.journal_path(directory, bead)
    if not path.is_file():
        step_journal.create_journal(path, step_journal.new_journal(bead, bead_type, pipeline, plans))
        return JournalRunner(path, agents, tools, registry)
    if replan_unhandled(step_journal.read_journal(path), plans, registry):
        step_journal.update_journal(path, lambda journal: replan_unhandled(journal, plans, registry))
    return JournalRunner(path, agents, tools, registry)
