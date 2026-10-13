"""Step journal: the checklist of pipeline steps kept for one bead, and the command that edits it.

A step journal is one JSON file per bead (an Epic, a Story or a Task). It lists the steps a
pipeline plans for that bead, grows as a step adds child steps, and each step is marked off right
after its output is written. A restarted run begins at the step :func:`next_step` returns, and a
later step takes an earlier step's outputs from the artifacts recorded here
(:func:`step_artifacts`, :func:`resolve_inputs`).

The journal's shape, its vocabularies and the step plans are defined once, in
``skills/pipeline-contracts/schemas/step-journal.schema.json``; every type, value and schema
check used here comes from ``step_journal_contract``, the module generated from that schema.
This module adds the behaviour, and the three rules a JSON Schema cannot state
(:func:`consistency_problems`).

This module is the only reader and writer of a step journal file: every change is one
read-modify-write under an exclusive lock (:func:`update_journal`), written to a temporary file
in the journal's directory and moved into place, and every document read or written is
validated. Nobody edits the JSON by hand; an agent session or a workflow runs the command
(:func:`main`, one sub-command per operation, one JSON object on stdout).

The step journal is not the workflow run journal (``run_journal_contract.py``) and not the
supervisor's run log (``ledger.jsonl``).
"""

import argparse
import fcntl
import json
import os
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Generator, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from step_journal_contract import (
    ARTIFACT_KINDS,
    BEAD_ID_PATTERN,
    BEAD_TYPES,
    JOURNAL_SUFFIX,
    LOCK_SUFFIX,
    PIPELINES,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PLANNED,
    STATUS_RUNNING,
    STEP_ID_PATTERN,
    VALUE_KINDS,
    Artifact,
    ArtifactKind,
    BeadId,
    BeadType,
    Journal,
    JsonValue,
    Pipeline,
    Step,
    StepId,
    StepJournalError,
    StepPlan,
    StepStatus,
    is_journal,
    json_value,
    schema_problems,
    validate_artifact,
    validate_journal,
    validate_step_plans,
)

TIMESTAMP_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_LOCK_WAIT: Final = 60.0
"""Seconds a change waits for another process's change to the same journal to finish."""
LOCK_POLL: Final = 0.05
STDIN_MARK: Final = "-"
WORKFLOW_RUNS_DIRECTORY: Final = "workflow-runs"
"""The directory of a control repository that holds saved run data, under ``.claude``."""
JOURNALS_DIRECTORY: Final = "step-journals"
"""The one directory, inside the workflow runs directory, that holds every bead's step journal."""
PLANNED_FOR_PREFIX: Final = "for "
"""A value artifact named ``for <step id>`` is held by the step whose result planned that step."""
EXIT_OK: Final = 0
EXIT_REFUSED: Final = 1


class InputArtifacts(TypedDict):
    """The artifacts one of a step's inputs hands it."""

    step: StepId
    description: str
    status: StepStatus
    artifacts: list[Artifact]


class Invalidation(TypedDict):
    """What :func:`invalidate_from` changed: also what ``invalidate`` prints."""

    reset: list[StepId]
    """The steps set back to planned, in walk order."""
    removed: list[StepId]
    """The steps removed because the step whose result added them was reset."""
    pruned: list[StepId]
    """The remaining steps whose inputs named a removed step and lost that id."""


class StepResult(TypedDict):
    """What ``add`` (of one step), ``start``, ``done``, ``fail`` and ``artifact`` print."""

    step: Step


class StepsResult(TypedDict):
    """What ``add`` prints when it adds the steps of ``--steps-json`` or ``--steps-file``."""

    steps: list[Step]


class SessionResult(TypedDict):
    """What ``session`` prints: the step and the agent session id it holds, or null."""

    step: StepId
    session: str | None


class CreateResult(TypedDict):
    """What ``create`` prints."""

    path: str
    journal: Journal


class UnclosedStep(TypedDict):
    """A step whose child steps are all done and that waits only for its own mark."""

    id: StepId
    status: StepStatus
    description: str


class NextResult(TypedDict):
    """What ``next`` prints."""

    step: Step | None
    complete: bool
    unclosed: list[UnclosedStep]


class ArtifactsResult(TypedDict):
    """What ``artifacts`` prints."""

    step: StepId
    status: StepStatus
    artifacts: list[Artifact]


class InputsResult(TypedDict):
    """What ``inputs`` prints."""

    step: StepId
    inputs: list[InputArtifacts]


class ValidationResult(TypedDict):
    """What ``validate`` prints."""

    valid: bool
    problems: list[str]


type CommandResult = (
    StepResult
    | StepsResult
    | SessionResult
    | CreateResult
    | NextResult
    | ArtifactsResult
    | InputsResult
    | Invalidation
    | ValidationResult
)


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one sub-command prints on stdout and the status the process exits with."""

    result: CommandResult
    status: int = EXIT_OK


class StepRefusedError(StepJournalError):
    """The journal refuses the requested change in the state it is in."""


class JournalLockTimeoutError(StepJournalError):
    """Another process held the journal's lock for the whole wait."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def timestamp() -> str:
    """Return the present moment as a journal date-time.

    Returns:
        The UTC time as ``YYYY-MM-DDTHH:MM:SSZ``.

    """
    return datetime.now(UTC).strftime(TIMESTAMP_FORMAT)


def _walk(steps: Sequence[Step]) -> Iterator[Step]:
    """Yield every step in walk order: each step before its child steps, siblings in order.

    Yields:
        Each step of the tree.

    """
    step: Step
    for step in steps:
        yield step
        yield from _walk(step["steps"])


def _performs(step: Step) -> bool:
    """Tell whether an agent or a script performs ``step``.

    Returns:
        True when the step has ``agent`` or ``script``; False for a step that only contains steps.

    """
    return "agent" in step or "script" in step


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def consistency_problems(journal: Journal) -> list[str]:
    """Check the three rules of the step journal that its JSON Schema cannot state.

    Args:
        journal: A journal that satisfies the schema.

    Returns:
        One sentence per repeated step id, per input that names no step of the journal, and per
        done step that has a child step that is not done; empty when the journal is consistent.

    """
    problems: list[str] = []
    seen: set[StepId] = set()
    step: Step
    for step in _walk(journal["steps"]):
        if step["id"] in seen:
            problems.append(f"step id {step['id']} appears more than once")
        seen.add(step["id"])
    for step in _walk(journal["steps"]):
        problems.extend(
            f"step {step['id']} names the input {named}, which is not a step of this journal"
            for named in step.get("inputs", [])
            if named not in seen
        )
        unfinished: list[StepId] = [child["id"] for child in step["steps"] if child["status"] != STATUS_DONE]
        if step["status"] == STATUS_DONE and unfinished:
            problems.append(f"step {step['id']} is done but its child steps {', '.join(unfinished)} are not")
    return problems


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def checked_journal(journal: Journal, where: str = "step journal") -> Journal:
    """Require a journal to satisfy the schema and the three rules the schema cannot state.

    Args:
        journal: The journal.
        where: What to call the journal in the error.

    Returns:
        The journal.

    Raises:
        StepJournalError: The journal breaks one of the three rules. A journal that does not
            satisfy the schema raises it from ``validate_journal``.

    """
    validate_journal(journal, where)
    problems: list[str] = consistency_problems(journal)
    if problems:
        message: str = f"{where} is not consistent: " + "; ".join(problems)
        raise StepJournalError(message)
    return journal


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def find_step(journal: Journal, step_id: StepId) -> Step:
    """Find the step with ``step_id`` anywhere in the journal.

    Args:
        journal: The journal.
        step_id: The id of the step.

    Returns:
        The step itself, not a copy.

    Raises:
        StepRefusedError: No step of the journal has that id.

    """
    step: Step
    for step in _walk(journal["steps"]):
        if step["id"] == step_id:
            return step
    message: str = f"no step {step_id} in the journal of {journal['bead']}"
    raise StepRefusedError(message)


def _settle_container(step: Step, moment: str) -> None:
    """Set the status of a step that only contains child steps from the statuses of those steps."""
    statuses: set[StepStatus] = {child["status"] for child in step["steps"]}
    step.pop("failure", None)
    if statuses == {STATUS_DONE}:
        step["status"] = STATUS_DONE
        step.setdefault("started", moment)
        step.setdefault("finished", moment)
    elif statuses == {STATUS_PLANNED}:
        step["status"] = STATUS_PLANNED
        step.pop("started", None)
        step.pop("finished", None)
    else:
        step["status"] = STATUS_RUNNING
        step.setdefault("started", moment)
        step.pop("finished", None)


def _settle_steps(steps: Sequence[Step], moment: str) -> None:
    """Settle, child steps first, every step that only contains child steps."""
    step: Step
    for step in steps:
        _settle_steps(step["steps"], moment)
        if step["steps"] and not _performs(step):
            _settle_container(step, moment)


def _settle(journal: Journal, moment: str) -> None:
    """Bring every derived status and the journal's own ``started`` and ``finished`` up to date."""
    _settle_steps(journal["steps"], moment)
    statuses: set[StepStatus] = {step["status"] for step in journal["steps"]}
    if statuses - {STATUS_PLANNED}:
        journal.setdefault("started", moment)
    if statuses == {STATUS_DONE}:
        journal.setdefault("finished", moment)
    else:
        journal.pop("finished", None)


def _plan_inputs(plan: StepPlan, refs: dict[str, StepId], known: set[StepId]) -> list[StepId]:
    """Resolve the inputs of a step plan to step ids.

    Returns:
        The id each entry names: the step an earlier plan of this call gave that ref, or a step
        already in the journal.

    Raises:
        StepRefusedError: An entry names neither.

    """
    inputs: list[StepId] = []
    named: str
    for named in plan.get("inputs", []):
        resolved: StepId | None = refs.get(named)
        if resolved is None and StepId(named) in known:
            resolved = StepId(named)
        if resolved is None:
            message: str = f"the input {named!r} of the step {plan['description']!r} names no earlier step"
            raise StepRefusedError(message)
        inputs.append(resolved)
    return inputs


def _build_steps(plans: Sequence[StepPlan], refs: dict[str, StepId], known: set[StepId]) -> list[Step]:
    """Turn validated step plans into planned steps with new ids.

    Returns:
        The new steps in plan order.

    Raises:
        StepRefusedError: Two plans of the call carry the same ref.

    """
    built: list[Step] = []
    plan: StepPlan
    for plan in plans:
        inputs: list[StepId] = _plan_inputs(plan, refs, known)
        step: Step = {
            "id": StepId(str(uuid.uuid4())),
            "description": plan["description"],
            "purpose": plan["purpose"],
            "status": STATUS_PLANNED,
            "artifacts": [],
            "steps": [],
        }
        if "agent" in plan:
            step["agent"] = plan["agent"]
        if "script" in plan:
            step["script"] = plan["script"]
        if inputs:
            step["inputs"] = inputs
        if "ref" in plan:
            if plan["ref"] in refs:
                message: str = f"the ref {plan['ref']!r} is given to more than one step"
                raise StepRefusedError(message)
            refs[plan["ref"]] = step["id"]
        step["steps"] = _build_steps(plan.get("steps", []), refs, known)
        built.append(step)
    return built


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def new_journal(bead: BeadId, bead_type: BeadType, pipeline: Pipeline, plans: Sequence[StepPlan]) -> Journal:
    """Build the journal of a bead from its outermost steps.

    The plans are validated against the schema's ``stepPlans`` and the finished journal against
    the journal schema, so a bead id, a plan or a ref the contract does not allow raises
    ``StepJournalError``.

    Args:
        bead: The bead id.
        bead_type: The kind of bead.
        pipeline: The pipeline whose steps the journal lists.
        plans: The outermost steps in the order they run; at least one.

    Returns:
        The journal, every step planned.

    """
    checked: list[StepPlan] = validate_step_plans(list(plans), "the outermost steps")
    journal: Journal = {
        "bead": bead,
        "beadType": bead_type,
        "pipeline": pipeline,
        "steps": _build_steps(checked, {}, set()),
    }
    return checked_journal(journal, f"the new journal of {bead}")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def add_steps(
    journal: Journal,
    plans: Sequence[StepPlan],
    moment: str,
    *,
    parent: StepId | None = None,
    after: StepId | None = None,
) -> list[Step]:
    """Add planned steps, each with a new id, to one place in the journal as one change.

    Adding every child step a result calls for in one change means a run that stops can never
    leave only some of them in the journal. The plans are validated against the schema's
    ``stepPlans``; plans it does not allow raise ``StepJournalError``.

    Args:
        journal: The journal; changed in place.
        plans: The steps to add, in the order they run; at least one.
        moment: The present date-time, as :func:`timestamp` gives it.
        parent: The step to add them under; None adds them among the outermost steps.
        after: The sibling they follow immediately; None adds them after the last sibling.

    Returns:
        The added steps in order.

    Raises:
        StepRefusedError: ``parent`` or ``after`` names no step, ``after`` is not a sibling in the
            place chosen, the parent has an agent or a script and is not running (its child steps
            come from its result, and it stays running until they are added and done), a ref is
            repeated, or an input names no step.

    """
    checked: list[StepPlan] = validate_step_plans(list(plans), "the steps to add")
    siblings: list[Step] = journal["steps"]
    message: str
    if parent is not None:
        owner: Step = find_step(journal, parent)
        if _performs(owner) and owner["status"] != STATUS_RUNNING:
            message = (
                f"step {parent} has an agent or a script and is {owner['status']}; its child steps come "
                "from its result, so they are added while it is running"
            )
            raise StepRefusedError(message)
        siblings = owner["steps"]
    position: int = len(siblings)
    if after is not None:
        find_step(journal, after)
        found: int | None = next((index for index, step in enumerate(siblings) if step["id"] == after), None)
        if found is None:
            message = f"step {after} is not a sibling in the place the new step goes"
            raise StepRefusedError(message)
        position = found + 1
    known: set[StepId] = {step["id"] for step in _walk(journal["steps"])}
    added: list[Step] = _build_steps(checked, {}, known)
    siblings[position:position] = added
    _settle(journal, moment)
    return added


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def add_step(
    journal: Journal,
    plan: StepPlan,
    moment: str,
    *,
    parent: StepId | None = None,
    after: StepId | None = None,
) -> Step:
    """Add one planned step, with a new id, to the journal.

    This is :func:`add_steps` for a single plan, and refuses what it refuses.

    Args:
        journal: The journal; changed in place.
        plan: The step to add.
        moment: The present date-time, as :func:`timestamp` gives it.
        parent: The step to add it under; None adds it among the outermost steps.
        after: The sibling it follows immediately; None adds it after the last sibling.

    Returns:
        The added step.

    """
    return add_steps(journal, [plan], moment, parent=parent, after=after)[0]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def start_step(journal: Journal, step_id: StepId, moment: str, *, session: str | None = None) -> Step:
    """Mark a step running, from its beginning.

    A planned step starts; a running or failed step starts again, which drops the failure and the
    artifacts its earlier, unfinished run recorded and keeps its agent session id, so the restart
    can resume that agent's conversation. Every step above it that only contains child steps
    becomes running.

    Args:
        journal: The journal; changed in place.
        step_id: The step to start.
        moment: The present date-time, as :func:`timestamp` gives it.
        session: The agent session id of the session performing the step; None leaves the one
            the step holds, if any.

    Returns:
        The step, running with ``started`` set.

    Raises:
        StepRefusedError: No such step; the step has child steps (they are run, not the step);
            the step is done (invalidate from it to run it again); or ``session`` is given for a
            step no agent performs.

    """
    step: Step = find_step(journal, step_id)
    message: str
    if session is not None and "agent" not in step:
        message = f"step {step_id} has no agent, so it holds no agent session id"
        raise StepRefusedError(message)
    if step["steps"]:
        message = f"step {step_id} has child steps; its child steps are run, not the step itself"
        raise StepRefusedError(message)
    if step["status"] == STATUS_DONE:
        message = f"step {step_id} is done; invalidate from it to run it again"
        raise StepRefusedError(message)
    step["status"] = STATUS_RUNNING
    step["started"] = moment
    step.pop("finished", None)
    step.pop("failure", None)
    step["artifacts"] = []
    if session is not None:
        step["session"] = session
    _settle(journal, moment)
    return step


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def set_session(journal: Journal, step_id: StepId, session: str) -> Step:
    """Record the agent session id of the session performing a step.

    Args:
        journal: The journal; changed in place.
        step_id: The step an agent is performing.
        session: The agent session id; it replaces the one the step holds.

    Returns:
        The step, holding the session id.

    Raises:
        StepRefusedError: No such step; no agent performs the step; or the step is planned or
            done, so no session is performing it.

    """
    step: Step = find_step(journal, step_id)
    message: str
    if "agent" not in step:
        message = f"step {step_id} has no agent, so it holds no agent session id"
        raise StepRefusedError(message)
    if step["status"] not in {STATUS_RUNNING, STATUS_FAILED}:
        message = f"step {step_id} is {step['status']}; a session id is recorded on a running or failed step"
        raise StepRefusedError(message)
    step["session"] = session
    return step


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def step_session(journal: Journal, step_id: StepId) -> str | None:
    """Read the agent session id a step holds.

    A step that is not in the journal raises ``StepRefusedError`` from :func:`find_step`.

    Args:
        journal: The journal.
        step_id: The step.

    Returns:
        The session id, or None when the step holds none.

    """
    return find_step(journal, step_id).get("session")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def finish_step(journal: Journal, step_id: StepId, moment: str) -> Step:
    """Mark a running step done.

    Marking the last child step done completes a parent that only contains child steps, and
    never a parent that has an agent or a script: that parent is marked done by its own call.

    Args:
        journal: The journal; changed in place.
        step_id: The step to mark done.
        moment: The present date-time, as :func:`timestamp` gives it.

    Returns:
        The step, done with ``finished`` set.

    Raises:
        StepRefusedError: No such step; the step is not running; or a child step is not done.

    """
    step: Step = find_step(journal, step_id)
    message: str
    if step["status"] != STATUS_RUNNING:
        message = f"step {step_id} is {step['status']}; only a running step is marked done"
        raise StepRefusedError(message)
    unfinished: list[StepId] = [child["id"] for child in step["steps"] if child["status"] != STATUS_DONE]
    if unfinished:
        message = f"step {step_id} has child steps that are not done: {', '.join(unfinished)}"
        raise StepRefusedError(message)
    step["status"] = STATUS_DONE
    step["finished"] = moment
    _settle(journal, moment)
    return step


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def fail_step(journal: Journal, step_id: StepId, failure: str, moment: str) -> Step:
    """Mark a step failed, with the reason.

    Args:
        journal: The journal; changed in place.
        step_id: The step that failed.
        failure: Why it failed.
        moment: The present date-time, as :func:`timestamp` gives it.

    Returns:
        The step, failed with ``failure`` set.

    Raises:
        StepRefusedError: No such step; ``failure`` is blank; the step is done; or the step only
            contains child steps, so its status follows theirs.

    """
    step: Step = find_step(journal, step_id)
    message: str
    if not failure.strip():
        message = f"step {step_id} cannot be marked failed without a reason"
        raise StepRefusedError(message)
    if step["status"] == STATUS_DONE:
        message = f"step {step_id} is done; a done step is not marked failed"
        raise StepRefusedError(message)
    if step["steps"] and not _performs(step):
        message = f"step {step_id} only contains child steps; its status follows theirs"
        raise StepRefusedError(message)
    step["status"] = STATUS_FAILED
    step["failure"] = failure
    step.pop("finished", None)
    _settle(journal, moment)
    return step


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_artifact(journal: Journal, step_id: StepId, artifact: Artifact) -> Step:
    """Record something a running step produced.

    An artifact with the name of one the step already holds replaces it. The artifact is
    validated against the schema's ``artifact``; one it does not allow raises ``StepJournalError``.

    Args:
        journal: The journal; changed in place.
        step_id: The step that produced the artifact.
        artifact: The file, directory or value.

    Returns:
        The step, holding the artifact.

    Raises:
        StepRefusedError: No such step, or the step is not running.

    """
    checked: Artifact = validate_artifact(artifact, "the artifact")
    step: Step = find_step(journal, step_id)
    if step["status"] != STATUS_RUNNING:
        message: str = f"step {step_id} is {step['status']}; an artifact is recorded while the step is running"
        raise StepRefusedError(message)
    step["artifacts"] = [held for held in step["artifacts"] if held["name"] != checked["name"]]
    step["artifacts"].append(checked)
    return step


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def next_step(journal: Journal) -> Step | None:
    """Find the step a run does next.

    The walk goes through the steps in order, each step before its child steps. A step that has
    child steps is never returned: the walk goes into its child steps. The first step that has no
    child steps and is not done is returned, whether it is planned, running or failed; a restart
    runs a running or failed step again from its beginning.

    Args:
        journal: The journal.

    Returns:
        The next step, or None when no step without child steps is left to run.

    """
    step: Step
    for step in _walk(journal["steps"]):
        if not step["steps"] and step["status"] != STATUS_DONE:
            return step
    return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def unclosed_steps(journal: Journal) -> list[Step]:
    """Find the steps that wait only for their own mark.

    These are the steps that have child steps, every one done, and are not done themselves: a
    step with an agent or a script whose child steps finished and that has not been marked done.
    :func:`next_step` never returns them.

    Args:
        journal: The journal.

    Returns:
        Those steps in walk order.

    """
    return [
        step
        for step in _walk(journal["steps"])
        if step["steps"]
        and step["status"] != STATUS_DONE
        and all(child["status"] == STATUS_DONE for child in step["steps"])
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def is_complete(journal: Journal) -> bool:
    """Tell whether every step of the journal is done.

    Args:
        journal: The journal.

    Returns:
        True when the journal has at least one step and every outermost step is done (a done
        step has no child step that is not done).

    """
    return bool(journal["steps"]) and all(step["status"] == STATUS_DONE for step in journal["steps"])


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def step_artifacts(journal: Journal, step_id: StepId) -> list[Artifact]:
    """Read what a step itself produced.

    A step that is not in the journal raises ``StepRefusedError`` from :func:`find_step`.

    Args:
        journal: The journal.
        step_id: The step.

    Returns:
        The step's artifacts in the order recorded; its child steps' artifacts are not included.

    """
    return list(find_step(journal, step_id)["artifacts"])


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def resolve_inputs(journal: Journal, step_id: StepId) -> list[InputArtifacts]:
    """Hand a step the artifacts of the steps its ``inputs`` name.

    A step that is not in the journal raises ``StepRefusedError`` from :func:`find_step`.

    Args:
        journal: The journal.
        step_id: The step whose inputs are wanted.

    Returns:
        One entry per input, in the order of ``inputs``: the input step's id, description, status
        and artifacts. Empty when the step names no input.

    """
    resolved: list[InputArtifacts] = []
    named: StepId
    for named in find_step(journal, step_id).get("inputs", []):
        source: Step = find_step(journal, named)
        resolved.append({
            "step": source["id"],
            "description": source["description"],
            "status": source["status"],
            "artifacts": list(source["artifacts"]),
        })
    return resolved


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def planned_for_name(step_id: StepId) -> str:
    """Name the value artifact a step records for a step its result planned.

    The artifact holds the parameters the planned step is handed, and is the record that the
    step holding it planned that step: :func:`invalidate_from` removes the planned step when the
    step that planned it is reset.

    Args:
        step_id: The planned step.

    Returns:
        ``for <step id>``.

    """
    return f"{PLANNED_FOR_PREFIX}{step_id}"


def _planned_by(step: Step) -> list[StepId]:
    """List the steps a step's artifacts record as planned by its result.

    Returns:
        The step id of every value artifact named as :func:`planned_for_name` names it.

    """
    planned: list[StepId] = []
    artifact: Artifact
    for artifact in step["artifacts"]:
        named: str = artifact["name"].removeprefix(PLANNED_FOR_PREFIX)
        if (
            artifact["kind"] in VALUE_KINDS
            and artifact["name"].startswith(PLANNED_FOR_PREFIX)
            and STEP_ID_PATTERN.search(named) is not None
        ):
            planned.append(StepId(named))
    return planned


def _remove_steps(steps: list[Step], gone: set[StepId], removed: list[StepId]) -> None:
    """Take every step whose id is in ``gone`` out of the tree, with the steps below it."""
    kept: list[Step] = []
    step: Step
    for step in steps:
        if step["id"] in gone:
            removed.extend(below["id"] for below in _walk([step]) if below["id"] not in removed)
            continue
        _remove_steps(step["steps"], gone, removed)
        kept.append(step)
    steps[:] = kept


def _reset(step: Step, reset: list[StepId], removed: list[StepId], planned: list[StepId]) -> None:
    """Set a step back to planned; drop the child steps of a performed step, reset the others."""
    planned.extend(_planned_by(step))
    step["status"] = STATUS_PLANNED
    step.pop("started", None)
    step.pop("finished", None)
    step.pop("failure", None)
    step.pop("session", None)
    step["artifacts"] = []
    reset.append(step["id"])
    if _performs(step):
        below: Step
        for below in _walk(step["steps"]):
            planned.extend(_planned_by(below))
            removed.append(below["id"])
        step["steps"] = []
        return
    child: Step
    for child in step["steps"]:
        _reset(child, reset, removed, planned)


def _invalidate(
    steps: Sequence[Step],
    target: StepId,
    reset: list[StepId],
    removed: list[StepId],
    planned: list[StepId],
) -> bool:
    """Reset ``target`` and every step after it in walk order within ``steps``.

    Returns:
        True when ``target`` was found in ``steps`` or below them.

    """
    found: bool = False
    step: Step
    for step in steps:
        if found or step["id"] == target:
            _reset(step, reset, removed, planned)
            found = True
            continue
        found = _invalidate(step["steps"], target, reset, removed, planned)
        if found and _performs(step) and step["status"] == STATUS_DONE:
            step["status"] = STATUS_RUNNING
            step.pop("finished", None)
    return found


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def invalidate_from(journal: Journal, step_id: StepId, moment: str) -> Invalidation:
    """Set a step and every step after it in walk order back to planned.

    Each reset step loses ``started``, ``finished``, ``failure``, ``session`` and its artifacts. A reset step
    that has an agent or a script loses its child steps, which came from its result; a reset step
    that only contains child steps keeps them, reset the same way. A step that a reset step's
    result planned anywhere else in the journal, recorded by that step's artifact named as
    :func:`planned_for_name` names it, is removed with the steps below it, so the step plans it
    again when it runs again. A step above the named step
    comes before it in walk order and is not reset: one that only contains child steps takes its
    status from them, and one with an agent or a script that was done becomes running, since a
    child step of it is no longer done. An id of a removed step is dropped from the ``inputs`` of
    the steps that remain. No file on disk is deleted or moved.

    A step that is not in the journal raises ``StepRefusedError`` from :func:`find_step`.

    Args:
        journal: The journal; changed in place.
        step_id: The first step to reset.
        moment: The present date-time, as :func:`timestamp` gives it.

    Returns:
        The ids reset, the ids removed, and the ids of the steps whose inputs lost a removed id.

    """
    find_step(journal, step_id)
    reset: list[StepId] = []
    removed: list[StepId] = []
    planned: list[StepId] = []
    _invalidate(journal["steps"], step_id, reset, removed, planned)
    _remove_steps(journal["steps"], set(planned), removed)
    gone: set[StepId] = set(removed)
    reset = [held for held in reset if held not in gone]
    pruned: list[StepId] = []
    step: Step
    for step in _walk(journal["steps"]):
        held: list[StepId] = step.get("inputs", [])
        kept: list[StepId] = [named for named in held if named not in gone]
        if len(kept) == len(held):
            continue
        pruned.append(step["id"])
        if kept:
            step["inputs"] = kept
        else:
            step.pop("inputs", None)
    _settle(journal, moment)
    return {"reset": reset, "removed": removed, "pruned": pruned}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def journal_path(directory: Path, bead: BeadId) -> Path:
    """Name the journal file of a bead inside a directory the caller chose.

    Args:
        directory: The directory that holds step journals.
        bead: The bead id.

    Returns:
        The file named for the bead with the contract's journal suffix, inside ``directory``.

    Raises:
        StepJournalError: The bead id is not one the contract allows.

    """
    if BEAD_ID_PATTERN.search(bead) is None:
        message: str = f"the bead id {bead!r} does not match {BEAD_ID_PATTERN.pattern}"
        raise StepJournalError(message)
    return directory / f"{bead}{JOURNAL_SUFFIX}"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def journals_directory(location: Path) -> Path:
    """Name the one directory that holds the step journal of every bead.

    This is the only place that names it: the orchestrator and the driver both call it, and
    :func:`journal_path` names a bead's file inside it.

    Args:
        location: An Epic work directory (``<workflow runs>/artifacts/<bead>``), or the workflow
            runs directory itself.

    Returns:
        ``<workflow runs>/step-journals``.

    Raises:
        StepJournalError: ``location`` is neither of the two.

    """
    if location.name == WORKFLOW_RUNS_DIRECTORY:
        return location / JOURNALS_DIRECTORY
    runs: Path = location.parent.parent
    if runs.name == WORKFLOW_RUNS_DIRECTORY:
        return runs / JOURNALS_DIRECTORY
    message: str = (
        f"{location} is neither an Epic work directory under {WORKFLOW_RUNS_DIRECTORY} nor that directory, "
        "so it does not say where step journals are held"
    )
    raise StepJournalError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def steps_in_order(journal: Journal) -> list[Step]:
    """List every step of a journal in walk order.

    Args:
        journal: The journal.

    Returns:
        Each step before its child steps, siblings in order; the steps themselves, not copies.

    """
    return list(_walk(journal["steps"]))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def steps_in_order_from(step: Step) -> list[Step]:
    """List a step and every step below it in walk order.

    Args:
        step: The step to start from.

    Returns:
        The step, then each step below it before its own child steps, siblings in order; the
        steps themselves, not copies.

    """
    return list(_walk([step]))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parent_step(journal: Journal, step_id: StepId) -> Step | None:
    """Find the step that directly contains a step.

    A step that is not in the journal raises ``StepRefusedError`` from :func:`find_step`.

    Args:
        journal: The journal.
        step_id: The contained step.

    Returns:
        The containing step itself, or None for an outermost step.

    """
    find_step(journal, step_id)
    step: Step
    for step in _walk(journal["steps"]):
        if any(child["id"] == step_id for child in step["steps"]):
            return step
    return None


def _read_text(path: Path) -> str:
    """Read a journal file.

    Returns:
        The file's text.

    Raises:
        StepJournalError: The file is missing or unreadable.

    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        message: str = f"cannot read the step journal {path}: {error}"
        raise StepJournalError(message) from error


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_journal(path: Path) -> Journal:
    """Read and validate a journal file.

    A read takes no lock: a write replaces the file in one move, so a reader sees the journal
    before the change or after it. A file that does not satisfy the schema or the three rules
    the schema cannot state raises ``StepJournalError``.

    Args:
        path: The journal file.

    Returns:
        The validated journal.

    Raises:
        StepJournalError: The file is missing, unreadable or not JSON.

    """
    text: str = _read_text(path)
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as error:
        message: str = f"the step journal {path} is not JSON: {error}"
        raise StepJournalError(message) from error
    return checked_journal(validate_journal(decoded, str(path)), str(path))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def file_problems(path: Path) -> list[str]:
    """Describe every way a journal file fails the contract.

    Args:
        path: The journal file.

    Returns:
        The schema's problems when the file does not satisfy it, otherwise the problems
        :func:`consistency_problems` finds; empty when the file conforms.

    Raises:
        StepJournalError: The file is missing, unreadable or not JSON.

    """
    text: str = _read_text(path)
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as error:
        message: str = f"the step journal {path} is not JSON: {error}"
        raise StepJournalError(message) from error
    if not is_journal(decoded):
        return schema_problems(decoded)
    return consistency_problems(decoded)


def _write_journal(path: Path, journal: Journal) -> None:
    """Validate a journal and put it in place of the file in one move.

    Raises:
        StepJournalError: The file cannot be written. A journal that does not conform raises it
            from :func:`checked_journal`.

    """
    checked_journal(journal, f"the step journal to write to {path}")
    text: str = json.dumps(journal, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    message: str
    descriptor: int
    temporary: str
    try:
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    except OSError as error:
        message = f"cannot write the step journal {path}: {error}"
        raise StepJournalError(message) from error
    scratch: Path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        scratch.replace(path)
    except OSError as error:
        scratch.unlink(missing_ok=True)
        message = f"cannot write the step journal {path}: {error}"
        raise StepJournalError(message) from error


@contextmanager
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def journal_lock(path: Path, wait: float = DEFAULT_LOCK_WAIT) -> Generator[None]:
    """Hold the exclusive lock of a journal file.

    The lock is an advisory lock on the journal's lock file, which sits beside the journal under
    the contract's lock suffix and is left in place afterwards.

    Args:
        path: The journal file.
        wait: Seconds to wait for another holder before giving up.

    Yields:
        Control while the lock is held.

    Raises:
        ValueError: ``wait`` is not a positive, finite number.
        StepJournalError: The lock file cannot be opened.
        JournalLockTimeoutError: Another process held the lock for the whole wait.

    """
    message: str
    if not 0 < wait < float("inf"):
        message = f"step journal: the lock wait {wait!r} is not a positive, finite number of seconds"
        raise ValueError(message)
    lock_path: Path = path.with_name(path.name + LOCK_SUFFIX)
    deadline: float = time.monotonic() + wait
    try:
        descriptor: int = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as error:
        message = f"cannot open the step journal lock {lock_path}: {error}"
        raise StepJournalError(message) from error
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    message = f"the step journal {path} stayed locked by another process for {wait} seconds"
                    raise JournalLockTimeoutError(message) from error
                time.sleep(LOCK_POLL)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def create_journal(path: Path, journal: Journal, *, wait: float = DEFAULT_LOCK_WAIT) -> None:
    """Write a new journal file, creating its directory when it does not exist.

    A journal that does not conform, or a lock another process holds for the whole wait, raises
    ``StepJournalError``.

    Args:
        path: The journal file to create.
        journal: The journal, as :func:`new_journal` builds it.
        wait: Seconds to wait for the journal's lock.

    Raises:
        StepRefusedError: A journal file already exists at ``path``.
        StepJournalError: The directory cannot be created.

    """
    message: str
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        message = f"cannot create the step journal directory {path.parent}: {error}"
        raise StepJournalError(message) from error
    with journal_lock(path, wait):
        if path.exists():
            message = f"a step journal already exists at {path}"
            raise StepRefusedError(message)
        _write_journal(path, journal)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def update_journal[T](path: Path, change: Callable[[Journal], T], *, wait: float = DEFAULT_LOCK_WAIT) -> T:
    """Apply one change to a journal file as a single locked read-modify-write.

    The journal is read under the lock, ``change`` edits it in place, and the result is validated
    and moved into place before the lock is released. When ``change`` raises (a refused change
    raises ``StepRefusedError``), or the changed journal does not conform, the file is left as it
    was.

    Args:
        path: The journal file.
        change: The edit; it receives the journal and returns whatever the caller wants back.
        wait: Seconds to wait for the journal's lock.

    Returns:
        What ``change`` returned.

    Raises:
        StepJournalError: There is no journal at ``path``.

    """
    if not path.is_file():
        message: str = f"there is no step journal at {path}"
        raise StepJournalError(message)
    with journal_lock(path, wait):
        journal: Journal = read_journal(path)
        result: T = change(journal)
        _write_journal(path, journal)
    return result


def _option(args: argparse.Namespace, name: str) -> str | None:
    """Read a string option of the parsed command line.

    Returns:
        The option's value, or None when it was not given.

    """
    value: object = getattr(args, name, None)
    return value if isinstance(value, str) else None


def _required(args: argparse.Namespace, name: str) -> str:
    """Read a string option the sub-command cannot do without.

    Returns:
        The option's value.

    Raises:
        StepJournalError: The option was not given.

    """
    value: str | None = _option(args, name)
    if value is None:
        message: str = f"--{name.replace('_', '-')} is required"
        raise StepJournalError(message)
    return value


def _choice[T: str](value: str, choices: tuple[T, ...], what: str) -> T:
    """Narrow a command-line value to the member of a contract vocabulary it equals.

    Returns:
        The matching member.

    Raises:
        StepJournalError: The value is none of ``choices``.

    """
    member: T
    for member in choices:
        if member == value:
            return member
    message: str = f"{what} {value!r} is not one of {', '.join(choices)}"
    raise StepJournalError(message)


def _step_option(args: argparse.Namespace, name: str) -> StepId | None:
    """Read an option that holds a step id.

    Returns:
        The step id, or None when the option was not given.

    Raises:
        StepJournalError: The value is not a step id.

    """
    value: str | None = _option(args, name)
    if value is None:
        return None
    if STEP_ID_PATTERN.search(value) is None:
        message: str = f"--{name.replace('_', '-')} {value!r} is not a step id (a lowercase UUID)"
        raise StepJournalError(message)
    return StepId(value)


def _step_argument(args: argparse.Namespace) -> StepId:
    """Read the required ``--step`` option.

    Returns:
        The step id.

    Raises:
        StepJournalError: ``--step`` was not given.

    """
    value: StepId | None = _step_option(args, "step")
    if value is None:
        message: str = "--step is required"
        raise StepJournalError(message)
    return value


def _journal_argument(args: argparse.Namespace) -> Path:
    """Resolve the journal file the command line names.

    Returns:
        ``--journal``, or the file of ``--bead`` inside ``--dir``.

    Raises:
        StepJournalError: Neither ``--journal`` nor ``--dir`` with ``--bead`` was given, or both.

    """
    journal: str | None = _option(args, "journal")
    directory: str | None = _option(args, "dir")
    message: str
    if journal is not None and directory is not None:
        message = "give --journal or --dir, not both"
        raise StepJournalError(message)
    if journal is not None:
        return Path(journal)
    if directory is None:
        message = "give the journal file with --journal, or its directory and bead with --dir and --bead"
        raise StepJournalError(message)
    return journal_path(Path(directory), BeadId(_required(args, "bead")))


def _wait_argument(args: argparse.Namespace) -> float:
    """Read the ``--lock-wait`` option.

    Returns:
        The seconds to wait for the journal's lock.

    """
    value: object = getattr(args, "lock_wait", None)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else DEFAULT_LOCK_WAIT


def _decode(text: str, what: str) -> JsonValue:
    """Decode JSON given on the command line.

    Returns:
        The decoded value.

    Raises:
        StepJournalError: ``text`` is not JSON.

    """
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as error:
        message: str = f"{what} is not JSON: {error}"
        raise StepJournalError(message) from error
    return json_value(decoded)


def _plans_argument(args: argparse.Namespace) -> list[StepPlan]:
    """Read the step plans of ``create`` or ``add`` from ``--steps-json`` or ``--steps-file``.

    Returns:
        The plans in order.

    Raises:
        StepJournalError: Neither option or both were given, or the file cannot be read.

    """
    inline: str | None = _option(args, "steps_json")
    file: str | None = _option(args, "steps_file")
    message: str
    if inline is not None and file is None:
        return validate_step_plans(_decode(inline, "--steps-json"), "--steps-json")
    if file is None or inline is not None:
        message = "give the outermost steps with exactly one of --steps-json and --steps-file"
        raise StepJournalError(message)
    if file == STDIN_MARK:
        return validate_step_plans(_decode(sys.stdin.read(), "standard input"), "the steps on standard input")
    try:
        text: str = Path(file).read_text(encoding="utf-8")
    except OSError as error:
        message = f"cannot read --steps-file {file}: {error}"
        raise StepJournalError(message) from error
    return validate_step_plans(_decode(text, f"--steps-file {file}"), f"--steps-file {file}")


def _plan_argument(args: argparse.Namespace) -> StepPlan:
    """Build the step plan the ``add`` sub-command adds.

    Returns:
        The plan; :func:`add_step` validates it.

    """
    plan: StepPlan = {"description": _required(args, "description"), "purpose": _required(args, "purpose")}
    agent: str | None = _option(args, "agent")
    script: str | None = _option(args, "script")
    inputs: object = getattr(args, "input", None)
    if agent is not None:
        plan["agent"] = agent
    if script is not None:
        plan["script"] = script
    if isinstance(inputs, list):
        plan["inputs"] = [item for item in inputs if isinstance(item, str)]
    return plan


def _artifact_argument(args: argparse.Namespace) -> Artifact:
    """Build the artifact the ``artifact`` sub-command records.

    Returns:
        The artifact, validated against the schema.

    """
    kind: ArtifactKind = _choice(_required(args, "kind"), ARTIFACT_KINDS, "--kind")
    raw: dict[str, JsonValue] = {"name": _required(args, "name"), "kind": kind}
    path: str | None = _option(args, "path")
    value: str | None = _option(args, "value")
    if path is not None:
        raw["path"] = path
    if value is not None:
        raw["value"] = _decode(value, "--value")
    return validate_artifact(raw, "the artifact")


def _run_create(args: argparse.Namespace) -> Outcome:
    """Run ``create``.

    Returns:
        The path of the new journal file and the journal.

    """
    path: Path = _journal_argument(args)
    journal: Journal = new_journal(
        BeadId(_required(args, "bead")),
        _choice(_required(args, "bead_type"), BEAD_TYPES, "--bead-type"),
        _choice(_required(args, "pipeline"), PIPELINES, "--pipeline"),
        _plans_argument(args),
    )
    create_journal(path, journal, wait=_wait_argument(args))
    return Outcome({"path": str(path), "journal": journal})


def _run_add(args: argparse.Namespace) -> Outcome:
    """Run ``add``.

    Returns:
        The added step, or the added steps when they came from ``--steps-json`` or ``--steps-file``.

    Raises:
        StepJournalError: Both one step's options and a steps option were given.

    """
    parent: StepId | None = _step_option(args, "parent")
    after: StepId | None = _step_option(args, "after")
    moment: str = timestamp()
    if _option(args, "steps_json") is not None or _option(args, "steps_file") is not None:
        if _option(args, "description") is not None or _option(args, "purpose") is not None:
            message: str = (
                "give one step with --description and --purpose, or several with --steps-json or --steps-file"
            )
            raise StepJournalError(message)
        plans: list[StepPlan] = _plans_argument(args)
        steps: list[Step] = update_journal(
            _journal_argument(args),
            lambda journal: add_steps(journal, plans, moment, parent=parent, after=after),
            wait=_wait_argument(args),
        )
        return Outcome({"steps": steps})
    plan: StepPlan = _plan_argument(args)
    step: Step = update_journal(
        _journal_argument(args),
        lambda journal: add_step(journal, plan, moment, parent=parent, after=after),
        wait=_wait_argument(args),
    )
    return Outcome({"step": step})


def _run_start(args: argparse.Namespace) -> Outcome:
    """Run ``start``.

    Returns:
        The started step.

    """
    step_id: StepId = _step_argument(args)
    session: str | None = _option(args, "session")
    moment: str = timestamp()
    step: Step = update_journal(
        _journal_argument(args),
        lambda journal: start_step(journal, step_id, moment, session=session),
        wait=_wait_argument(args),
    )
    return Outcome({"step": step})


def _run_session(args: argparse.Namespace) -> Outcome:
    """Run ``session``: record the agent session id given with ``--session``, or read the one held.

    Returns:
        The step's id and the agent session id it holds, or null.

    """
    step_id: StepId = _step_argument(args)
    session: str | None = _option(args, "session")
    if session is None:
        return Outcome({"step": step_id, "session": step_session(read_journal(_journal_argument(args)), step_id)})
    given: str = session
    step: Step = update_journal(
        _journal_argument(args),
        lambda journal: set_session(journal, step_id, given),
        wait=_wait_argument(args),
    )
    return Outcome({"step": step_id, "session": step.get("session")})


def _run_done(args: argparse.Namespace) -> Outcome:
    """Run ``done``.

    Returns:
        The step marked done.

    """
    step_id: StepId = _step_argument(args)
    moment: str = timestamp()
    step: Step = update_journal(
        _journal_argument(args),
        lambda journal: finish_step(journal, step_id, moment),
        wait=_wait_argument(args),
    )
    return Outcome({"step": step})


def _run_fail(args: argparse.Namespace) -> Outcome:
    """Run ``fail``.

    Returns:
        The step marked failed.

    """
    step_id: StepId = _step_argument(args)
    failure: str = _required(args, "failure")
    moment: str = timestamp()
    step: Step = update_journal(
        _journal_argument(args),
        lambda journal: fail_step(journal, step_id, failure, moment),
        wait=_wait_argument(args),
    )
    return Outcome({"step": step})


def _run_artifact(args: argparse.Namespace) -> Outcome:
    """Run ``artifact``.

    Returns:
        The step holding the recorded artifact.

    """
    step_id: StepId = _step_argument(args)
    artifact: Artifact = _artifact_argument(args)
    step: Step = update_journal(
        _journal_argument(args),
        lambda journal: record_artifact(journal, step_id, artifact),
        wait=_wait_argument(args),
    )
    return Outcome({"step": step})


def _run_next(args: argparse.Namespace) -> Outcome:
    """Run ``next``.

    Returns:
        The next step or null, whether every step is done, and the steps whose child steps are
        all done and that wait only for their own mark.

    """
    journal: Journal = read_journal(_journal_argument(args))
    unclosed: list[UnclosedStep] = [
        {"id": waiting["id"], "status": waiting["status"], "description": waiting["description"]}
        for waiting in unclosed_steps(journal)
    ]
    return Outcome({"step": next_step(journal), "complete": is_complete(journal), "unclosed": unclosed})


def _run_artifacts(args: argparse.Namespace) -> Outcome:
    """Run ``artifacts``.

    Returns:
        The named step's id, status and artifacts.

    """
    journal: Journal = read_journal(_journal_argument(args))
    step: Step = find_step(journal, _step_argument(args))
    return Outcome({"step": step["id"], "status": step["status"], "artifacts": step_artifacts(journal, step["id"])})


def _run_inputs(args: argparse.Namespace) -> Outcome:
    """Run ``inputs``.

    Returns:
        The named step's id and, per input, the input step's id, description, status and artifacts.

    """
    journal: Journal = read_journal(_journal_argument(args))
    step_id: StepId = _step_argument(args)
    return Outcome({"step": step_id, "inputs": resolve_inputs(journal, step_id)})


def _run_invalidate(args: argparse.Namespace) -> Outcome:
    """Run ``invalidate``.

    Returns:
        The ids reset, the ids removed, and the ids of the steps whose inputs lost a removed id.

    """
    step_id: StepId = _step_argument(args)
    moment: str = timestamp()
    result: Invalidation = update_journal(
        _journal_argument(args),
        lambda journal: invalidate_from(journal, step_id, moment),
        wait=_wait_argument(args),
    )
    return Outcome(result)


def _run_validate(args: argparse.Namespace) -> Outcome:
    """Run ``validate``.

    Returns:
        Whether the journal file conforms and every problem found; the status is the refusal
        status when it does not conform.

    """
    problems: list[str] = file_problems(_journal_argument(args))
    return Outcome({"valid": not problems, "problems": problems}, EXIT_REFUSED if problems else EXIT_OK)


_COMMANDS: Final[dict[str, Callable[[argparse.Namespace], Outcome]]] = {
    "create": _run_create,
    "add": _run_add,
    "start": _run_start,
    "session": _run_session,
    "done": _run_done,
    "fail": _run_fail,
    "artifact": _run_artifact,
    "next": _run_next,
    "artifacts": _run_artifacts,
    "inputs": _run_inputs,
    "invalidate": _run_invalidate,
    "validate": _run_validate,
}


def _parser() -> argparse.ArgumentParser:
    """Build the command line: one sub-command per journal operation.

    Returns:
        The argument parser.

    """
    where: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    where.add_argument("--journal", help="the journal file")
    where.add_argument("--dir", help="the directory that holds step journals; used with --bead")
    where.add_argument("--bead", help="the bead id; with --dir it names the journal file")
    where.add_argument("--lock-wait", type=float, default=DEFAULT_LOCK_WAIT, help="seconds to wait for the lock")
    step: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    step.add_argument("--step", required=True, help="the id of the step")
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="atw-step-journal",
        description="Read and change the step journal of one bead. Prints one JSON object on stdout.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create: argparse.ArgumentParser = commands.add_parser(
        "create",
        parents=[where],
        help="create the journal of a bead",
    )
    create.add_argument("--bead-type", required=True, choices=BEAD_TYPES)
    create.add_argument("--pipeline", required=True, choices=PIPELINES)
    create.add_argument("--steps-json", help="the outermost steps, a JSON array of step plans")
    create.add_argument("--steps-file", help=f"a file holding that JSON array; {STDIN_MARK} reads standard input")
    add: argparse.ArgumentParser = commands.add_parser("add", parents=[where], help="add a planned step")
    add.add_argument("--description", help="what the step does, in plain words")
    add.add_argument("--purpose", help="why the step exists")
    add.add_argument("--steps-json", help="several steps to add in one change, a JSON array of step plans")
    add.add_argument("--steps-file", help=f"a file holding that JSON array; {STDIN_MARK} reads standard input")
    add.add_argument("--agent", help="the agent that performs the step")
    add.add_argument("--script", help="the script that performs the step")
    add.add_argument("--parent", help="the id of the step to add it under; omit for an outermost step")
    add.add_argument("--after", help="the id of the sibling it follows; omit to add it last")
    add.add_argument("--input", action="append", help="the id of a step whose artifacts it reads; repeatable")
    start: argparse.ArgumentParser = commands.add_parser("start", parents=[where, step], help="mark a step running")
    start.add_argument("--session", help="the agent session id of the session performing the step")
    session: argparse.ArgumentParser = commands.add_parser(
        "session",
        parents=[where, step],
        help="print the agent session id a step holds, or record the one given with --session",
    )
    session.add_argument("--session", help="the agent session id to record on a running or failed step")
    commands.add_parser("done", parents=[where, step], help="mark a running step done")
    fail: argparse.ArgumentParser = commands.add_parser("fail", parents=[where, step], help="mark a step failed")
    fail.add_argument("--failure", required=True, help="why the step failed")
    artifact: argparse.ArgumentParser = commands.add_parser(
        "artifact",
        parents=[where, step],
        help="record something a running step produced",
    )
    artifact.add_argument("--name", required=True, help="the name a later step asks for it by")
    artifact.add_argument("--kind", required=True, choices=ARTIFACT_KINDS)
    artifact.add_argument("--path", help="where the file or directory is")
    artifact.add_argument("--value", help="the value, as JSON")
    commands.add_parser("next", parents=[where], help="print the step a run does next")
    commands.add_parser("artifacts", parents=[where, step], help="print what a step produced")
    commands.add_parser("inputs", parents=[where, step], help="print the artifacts of a step's inputs")
    commands.add_parser(
        "invalidate",
        parents=[where, step],
        help="set a step and every step after it back to planned",
    )
    commands.add_parser("validate", parents=[where], help="check a journal file against the contract")
    return parser


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main(argv: Sequence[str] | None = None) -> int:
    """Run one step journal sub-command.

    Args:
        argv: The arguments after the program name; None reads the process's own.

    Returns:
        0 after printing the result as one JSON object on stdout; 1 after printing why the
        journal refused, or what does not conform, on stderr. ``validate`` prints its JSON
        object either way and returns 1 for a journal that does not conform.

    """
    args: argparse.Namespace = _parser().parse_args(argv)
    command: str = _required(args, "command")
    try:
        outcome: Outcome = _COMMANDS[command](args)
    except StepJournalError as error:
        sys.stderr.write(f"atw-step-journal {command}: {error}\n")
        return EXIT_REFUSED
    sys.stdout.write(json.dumps(outcome.result, ensure_ascii=False) + "\n")
    if outcome.status != EXIT_OK:
        sys.stderr.write(f"atw-step-journal {command}: the journal does not conform; see the problems on stdout\n")
    return outcome.status


if __name__ == "__main__":
    sys.exit(main())
