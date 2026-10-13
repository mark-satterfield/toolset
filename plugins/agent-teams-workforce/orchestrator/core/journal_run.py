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

    Returns:
        The artifacts of the steps its ``inputs`` name, in that order.

    """
    return StepInputs(
        step["id"],
        step["description"],
        stage_of(step),
        tuple(tuple(source["artifacts"]) for source in step_journal.resolve_inputs(journal, step["id"])),
    )


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
        """
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
            inputs=inputs,
            saved=StepInputs(step["id"], step["description"], stage_of(step), (saved,)),
        )

    def _start(self, step_id: StepId, session: str | None = None) -> Step:
        """Mark a step running in the journal.

        Returns:
            The running step.

        """
        return step_journal.update_journal(
            self.path,
            lambda journal: step_journal.start_step(journal, step_id, step_journal.timestamp(), session=session),
        )

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
        run: StepRun = self._step_run(self._start(step["id"], session), inputs, saved)
        labelled: list[tuple[str, Path]] = list(
            dict.fromkeys([*inputs.labelled_files(), *launch.files, (JOURNAL_LABEL, self.path)]),
        )
        request: AgentStep = AgentStep(
            stage=stage_of(step),
            agent=step.get("agent", ""),
            inputs=tuple(str(path) for _, path in labelled),
            output=launch.output,
            outcome=launch.outcome,
            validate=launch.validate,
            final=None,
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

    An existing journal is left exactly as it is: it alone says where the run begins. A journal
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
