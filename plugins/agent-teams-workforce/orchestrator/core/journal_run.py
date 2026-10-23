"""The journal runner: one dispatch is a loop over the step journal of one bead.

The loop asks the journal for the next step, runs it, and repeats until no step is left or one
fails. There is no other cursor: a restart is the same loop on the same file, so it begins at the
first step without child steps that is not done. A step is marked running before its code or its
session starts; when its output is accepted, one journal change records its artifacts, the steps
its result plans and its done mark (``journal_steps.apply_completion``).

A step that raises is marked failed with a one-line structured cause and the exception continues
to the caller unchanged. A stop request (the stop file, an interrupt) leaves the step running. A
step that finds a file an earlier step wrote to a contract that has since changed
(``StaleInputError``) is not failed: the step that wrote the file and every step after it are set
back to planned, and the loop goes on from there; the same writer named twice in one dispatch
fails the step.

A session is continued only when its agent definition and contracts are unchanged since it
started (``AgentRunner.resumable``, by fingerprint); otherwise the step starts a new one.

Steps run in walk order. Consecutive sibling steps that each have an agent, have no child steps
and whose inputs are all done run as concurrent sessions under the dispatch's session slots.

Work that already succeeded is never redone: an agent step whose output file is valid and was
written since the step started is recorded from that file, and its agent is not started again
(``helper-steps.schema.json``). That covers a helper a lead agent ran in its own session and left
unrecorded, and a session that wrote its output and stopped before the step was recorded.

An agent step that has child steps is closed only through its "Finish", its last child step
(``helper-steps.schema.json``). A "Finish" the runner ran was accepted when it ran. A "Finish"
the agent closed in its own session holds no session id of its own; the accept of its launch is
called when its step closes, as if the runner had run it, and what it returns is recorded on the
agent's step. An agent step whose child steps are all done and whose last child is no done
"Finish" is not closed: a "Finish" is planned under it, and the agent continues its session there.
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Final
from uuid import uuid4

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.flows.elaboration_support import parallel

from . import step_journal
from .agents import CONTENT_FAILURES, AgentRunner, SessionNotResumedError, validate_output
from .handback import failure_for, stop_stage
from .handback_contract import OTHER_CAUSE, Failure
from .journal_changes import apply_completion
from .journal_registry import REGISTRY, Registry
from .journal_steps import (
    FINISH,
    JOURNAL_LABEL,
    AgentBuilder,
    AgentLaunch,
    Completion,
    ScriptHandler,
    StepInputs,
    StepRun,
    is_finish_of,
    stage_of,
)
from .models import AgentStep, RunContext, StaleInputError, StepError
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


def _done_finish(step: Step) -> Step | None:
    """Find the done "Finish" an agent step's child steps end with.

    Returns:
        The step's last child step when it is the step's "Finish" and is done; else None.

    """
    last: Step | None = step["steps"][-1] if step["steps"] else None
    if last is None or last["status"] != STATUS_DONE or not is_finish_of(step, last):
        return None
    return last


def _finish_plan(step: Step) -> StepPlan:
    """Plan the "Finish" of an agent step whose child steps are all done and that has none.

    Returns:
        A "Finish" step of the step's own agent, handed the step and every step below it.

    """
    return {
        "description": f"{FINISH} the step {step['description']!r} with what its helper steps recorded",
        "purpose": "Every helper step is done and the agent has not finished: it continues and records its result",
        "agent": step.get("agent", ""),
        "inputs": [step["id"]],
    }


def _planned_finish(journal: Journal, step_id: StepId, moment: str) -> Step | None:
    """Plan a "Finish" under a running agent step whose child steps are all done.

    Returns:
        The planned "Finish"; None when the step has no agent, no child steps, a child step that
        is not done, or is not running.

    """
    step: Step = step_journal.find_step(journal, step_id)
    ready: bool = (
        "agent" in step
        and step["status"] == STATUS_RUNNING
        and bool(step["steps"])
        and all(child["status"] == STATUS_DONE for child in step["steps"])
    )
    return step_journal.add_step(journal, _finish_plan(step), moment, parent=step_id) if ready else None


JSON_SUFFIX: Final = ".json"
"""The suffix of an output the runner may reuse."""


def _written_since_start(step: Step, output: Path) -> bool:
    """Tell whether a step's output file was written after the step last started.

    Returns:
        True when the step has a start time and the file exists with a modification time at or
        after it; the journal records whole seconds, so a file of the same second counts.

    """
    started: str | None = step.get("started")
    if started is None or not output.is_file():
        return False
    began: float = datetime.strptime(started, step_journal.TIMESTAMP_FORMAT).replace(tzinfo=UTC).timestamp()
    return output.stat().st_mtime >= began


def _finished_output(step: Step, launch: AgentLaunch) -> bool:
    """Tell whether an agent step's output is already its finished work.

    Only a JSON output is reused: an agent writes it whole, while a document may be part
    written when its session stops.

    Returns:
        True when the launch allows reuse and the JSON file at ``launch.output`` was written
        since the step started and passes the launch's check; an invalid file is the session's
        to redo. A contract that cannot be loaded raises ``PipelineDefectError`` from
        ``validate_output``.

    """
    if not launch.reuse_output or launch.output.suffix != JSON_SUFFIX or not _written_since_start(step, launch.output):
        return False
    request: AgentStep = AgentStep(
        stage=stage_of(step),
        agent=step.get("agent", ""),
        inputs=(),
        output=launch.output,
        outcome=launch.outcome,
        validate=launch.validate,
        journal_step=step["id"],
    )
    try:
        validate_output(request)
    except CONTENT_FAILURES:
        return False
    return True


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
        self.replanned: set[StepId] = set()
        """The steps planned again in this dispatch because a file they wrote was stale."""
        self.stale: list[StaleInputError] = []
        """The stale files found by the steps of the group that runs now."""

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
        self._replan_stale()
        self._close_finished()
        return True

    def _replan_stale(self) -> None:
        """Set the first step that wrote a stale file, and every step after it, back to planned.

        Every other writer comes after the first in walk order, so it is reset too. Runs after the
        whole group, so no session of the group is running when its step is reset.
        """
        writers: list[StepId] = list(dict.fromkeys(stale.writer for stale in self.stale))
        self.stale = []
        if not writers:
            return
        self.replanned.update(writers)

        def change(journal: Journal) -> None:
            order: list[StepId] = [step["id"] for step in step_journal.steps_in_order(journal)]
            first: StepId = min(writers, key=order.index)
            step_journal.invalidate_from(journal, first, step_journal.timestamp())

        step_journal.update_journal(self.path, change)

    def _close_finished(self) -> None:
        """Close every running step whose child steps are all done, the last in walk order first.

        A step with no agent is marked done. An agent step is closed through its "Finish": one
        the runner ran (it holds a session id) was accepted when it ran, so the step is marked
        done; one the agent closed in its own session is accepted now (:meth:`_accept_finish`).
        An agent step whose last child is no done "Finish" gets a planned "Finish" instead.
        Whatever accepting a "Finish" raises continues to the caller once the failure is recorded
        on a new "Finish" of the step (:meth:`_record_failure`).
        """
        while waiting := [
            step
            for step in step_journal.unclosed_steps(step_journal.read_journal(self.path))
            if step["status"] == STATUS_RUNNING
        ]:
            step: Step = waiting[-1]
            step_id: StepId = step["id"]
            finish: Step | None = _done_finish(step)
            if "agent" in step and finish is None:
                step_journal.update_journal(
                    self.path,
                    partial(_planned_finish, step_id=step_id, moment=step_journal.timestamp()),
                )
            elif "agent" in step and finish is not None and "session" not in finish:
                try:
                    self._accept_finish(step_id, finish["id"])
                except Exception as exc:
                    self._record_failure(step_id, stage_of(finish), exc)
                    raise
            else:
                step_journal.update_journal(
                    self.path,
                    partial(step_journal.finish_step, step_id=step_id, moment=step_journal.timestamp()),
                )

    def _accept_finish(self, step_id: StepId, finish_id: StepId) -> None:
        """Accept the "Finish" an agent closed in its own session, and record it on the agent's step.

        The launch is the one the runner builds for the "Finish" itself: its output is checked as
        a session's output is, its accept is called with the "Finish" as the accepted step, and
        what the accept returns is recorded on the agent's step, which is running: its artifacts,
        the steps it plans under the step, and the step's done mark unless it plans any.

        A launch that cannot be built, an output the check refuses and a refusing accept raise
        what they raise; nothing is recorded.
        """
        journal: Journal = step_journal.read_journal(self.path)
        finish: Step = step_journal.find_step(journal, finish_id)
        inputs: StepInputs = _inputs(journal, finish)
        run: StepRun = self._step_run(finish, inputs, tuple(finish["artifacts"]))
        launch: AgentLaunch = check_type(self.registry.agent(finish)(run), AgentLaunch)
        validate_output(
            AgentStep(
                stage=stage_of(finish),
                agent=finish.get("agent", ""),
                inputs=(),
                output=launch.output,
                outcome=launch.outcome,
                validate=launch.validate,
                journal_step=finish_id,
            ),
        )
        self._complete(step_id, launch.accept(run, launch.output))

    def _run_step(self, step_id: StepId) -> None:
        """Run one step and record its failure when it raises.

        A stale file the step finds is kept for :meth:`_replan_stale`, and the step is not failed,
        unless the step that wrote the file was planned again in this dispatch already.

        Raises:
            StaleInputError: The step that wrote the stale file was planned again in this dispatch already.

        """
        journal: Journal = step_journal.read_journal(self.path)
        step: Step = step_journal.find_step(journal, step_id)
        try:
            self._perform(journal, step)
        except StaleInputError as stale:
            if stale.writer in self.replanned:
                self._record_failure(step_id, stage_of(step), stale)
                raise
            self.stale.append(stale)
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
        When every one is done, the failure is recorded on a "Finish" planned under the agent's
        step (:func:`_planned_finish`), so the next dispatch continues the agent's session there
        instead of closing its step without a result.
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
            moment: str = step_journal.timestamp()
            target: Step | None = _open_leaf(step_journal.find_step(journal, step_id)) or _planned_finish(
                journal,
                step_id,
                moment,
            )
            if target is not None:
                step_journal.fail_step(journal, target["id"], text, moment)

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

        A step that holds no session of its own conversation and whose output is already its
        finished work (:func:`_finished_output`) is recorded from that file with what the
        launch's accept function returns, and no session starts. After a session the journal is
        read again. An ordinary step is completed with what the launch's accept function returns.
        A step whose child steps are all done and end with a "Finish" the session closed is
        completed through that "Finish" (:meth:`_accept_finish`), whatever session id the
        "Finish" holds. A step the session marked done, or left other child steps under, is not
        completed here.
        """
        builder: AgentBuilder = self.registry.agent(step)
        inputs: StepInputs = _inputs(journal, step)
        saved: tuple[Artifact, ...] = tuple(step["artifacts"])
        launch: AgentLaunch = check_type(builder(self._step_run(step, inputs, saved)), AgentLaunch)
        held: str | None = _held_session(journal, step, launch)
        if held is not None and not self.agents.resumable(held):
            held = None
        if held is None and _finished_output(step, launch):
            reused: StepRun = self._step_run(self._start(step["id"], None, launch.keep), inputs, saved)
            self._complete(step["id"], launch.accept(reused, launch.output))
            return
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
        output: Path = self._session(request, labelled, session, launch, resume=held is not None, before=step)
        after: Step = step_journal.find_step(step_journal.read_journal(self.path), step["id"])
        if after["status"] != STATUS_DONE and not after["steps"]:
            self._complete(step["id"], launch.accept(replace(run, step=after), output))
            return
        finish: Step | None = _done_finish(after)
        settled: bool = all(child["status"] == STATUS_DONE for child in after["steps"])
        if after["status"] == STATUS_RUNNING and settled and finish is not None:
            self._accept_finish(step["id"], finish["id"])

    def _session(  # ruff: ignore[too-many-arguments] - The session, its launch and the step before it restarted.
        self,
        request: AgentStep,
        labelled: list[tuple[str, Path]],
        session: str,
        launch: AgentLaunch,
        *,
        resume: bool,
        before: Step,
    ) -> Path:
        """Run the session of an agent step, starting a new one when its conversation is gone.

        When the conversation is gone and the session it held had already written its finished
        output (:func:`_finished_output`, judged against ``before``, the step as it stood before
        this run started it again), that output is the step's result and no new session starts.

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
            if _finished_output(before, launch):
                return launch.output
            step_id: StepId = check_type(request.journal_step, StepId)
            fresh: str = str(uuid4())
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
