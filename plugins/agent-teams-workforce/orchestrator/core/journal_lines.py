"""Apply the journal changes a workflow script reports on its log to the journal file.

A workflow script cannot read or write a file, so it reports each change to the journal of the
bead it works on as one log line: the contract's change prefix followed by a ``journalChange``
object (``step-journal.schema.json``), or, for an object longer than the contract's chunk, as
part lines whose texts joined in order are that object. The driver reads those lines from the
session's stream while the workflow runs and hands each one to a :class:`ChangeReader`, which
applies it to the journal file at once with the functions of ``step_journal``.

A change is applied once: a reader belongs to one run, ignores a change of another run and a
change whose number it already applied, and refuses a change that skips a number. A step a
change adds is named in later changes of the same run by the ref its plan carried; the reader
keeps the step id each ref was given.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, assert_never

from typeguard import CollectionCheckStrategy, typechecked

from . import step_journal
from .journal_changes import apply_completion
from .journal_steps import AFTER_THIS, UNDER_THIS, Completion, NewStep, StepGroup, Where

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import (
    CHANGE_OP_ADD,
    CHANGE_OP_DONE,
    CHANGE_OP_FAIL,
    CHANGE_OP_START,
    CHANGE_PART_PREFIX,
    CHANGE_PREFIX,
    STEP_ID_PATTERN,
    ChangeOp,
    Journal,
    JournalChange,
    PlannedStep,
    StepId,
    StepJournalError,
    StepPlan,
    validate_journal_change,
)

if TYPE_CHECKING:
    from pathlib import Path

PART_FIELDS: Final = 3
"""A part line holds the change number, ``<i>/<k>`` and the text, separated by single spaces."""


class JournalChangeError(StepJournalError):
    """A reported change cannot be read, skips a number or names a step the run does not know."""


@dataclass(frozen=True, slots=True)
class Applied:
    """One change that was applied to the journal file."""

    n: int
    op: ChangeOp
    step: StepId
    added: tuple[StepId, ...]


@dataclass(slots=True)
class _Parts:
    """The part lines of one change received so far."""

    total: int
    texts: dict[int, str] = field(default_factory=dict)


def _step_ids(journal: Journal) -> list[StepId]:
    """List the id of every step of a journal in walk order.

    Returns:
        The ids.

    """
    return [step["id"] for step in step_journal.steps_in_order(journal)]


@dataclass(slots=True)
class ChangeReader:
    """Applies the changes of one run of a workflow script to one journal file.

    ``run`` is the name the driver gave the run in the workflow's arguments. ``applied`` is the
    number of the last change applied, and ``refs`` the step id of every step the run added,
    by the ref its plan carried.
    """

    path: Path
    run: str
    applied: int = 0
    refs: dict[str, StepId] = field(default_factory=dict)
    _parts: dict[int, _Parts] = field(default_factory=dict)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def feed(self, message: str) -> Applied | None:
        """Read one log line of the workflow and apply the change it completes, if any.

        A line that reports no journal change, a part line that does not complete its change, a
        change of another run and a change already applied all return None and write nothing.
        The harness puts the name of a called workflow script in front of that script's lines, so
        the change is read from where its prefix begins.

        Args:
            message: One log message of the workflow, as the session's stream carries it.

        Returns:
            What was applied, or None.

        Raises:
            JournalChangeError: The line carries the change prefix and no valid change, its
                number skips one, or it names a step the journal and the run do not know. A
                change the journal refuses raises ``StepRefusedError`` from ``step_journal``.

        """
        body: str | None = self._body(message)
        if body is None:
            return None
        try:
            decoded: object = json.loads(body)
        except json.JSONDecodeError as error:
            problem: str = f"a journal change of run {self.run} is not JSON: {error}"
            raise JournalChangeError(problem) from error
        change: JournalChange = validate_journal_change(decoded, f"a journal change of run {self.run}")
        if change["run"] != self.run or change["n"] <= self.applied:
            return None
        if change["n"] != self.applied + 1:
            problem = (
                f"journal change {change['n']} of run {self.run} arrived after change {self.applied}: "
                "a change in between did not arrive"
            )
            raise JournalChangeError(problem)
        applied: Applied = self._apply(change)
        self.applied = change["n"]
        return applied

    def _body(self, message: str) -> str | None:
        """Find the JSON text of the change a log line carries or completes.

        Returns:
            The text, or None when the line carries no change or its change is not complete.

        Raises:
            JournalChangeError: A part line is not ``<n> <i>/<k> <text>``.

        """
        whole: int = message.find(CHANGE_PREFIX)
        if whole >= 0:
            return message[whole + len(CHANGE_PREFIX) :]
        part: int = message.find(CHANGE_PART_PREFIX)
        if part < 0:
            return None
        fields: list[str] = message[part + len(CHANGE_PART_PREFIX) :].split(" ", PART_FIELDS - 1)
        position: list[str] = fields[1].split("/") if len(fields) == PART_FIELDS else []
        if len(position) != len(("index", "total")) or not all(text.isdecimal() for text in (fields[0], *position)):
            problem: str = f"a journal change part line of run {self.run} is not '<n> <i>/<k> <text>'"
            raise JournalChangeError(problem)
        number: int = int(fields[0])
        index: int = int(position[0])
        total: int = int(position[1])
        if number <= self.applied:
            return None
        held: _Parts = self._parts.setdefault(number, _Parts(total))
        held.texts[index] = fields[2]
        if len(held.texts) < held.total:
            return None
        del self._parts[number]
        return "".join(held.texts[key] for key in sorted(held.texts))

    def _resolve(self, named: str) -> StepId:
        """Find the step a change names.

        Returns:
            The step id the run gave that ref, or the name itself when it is a step id.

        Raises:
            JournalChangeError: The name is neither a ref of this run nor a step id.

        """
        found: StepId | None = self.refs.get(named)
        if found is not None:
            return found
        if STEP_ID_PATTERN.search(named) is None:
            problem: str = f"run {self.run} names the step {named!r}, which is no ref of this run and no step id"
            raise JournalChangeError(problem)
        return StepId(named)

    def _new_steps(self, planned: list[PlannedStep]) -> tuple[NewStep, ...]:
        """Turn the steps a change plans into the steps the journal change takes.

        Returns:
            One new step per planned step, its inputs resolved to step ids where they name a ref
            an earlier change of this run carried.

        """
        refs_here: set[str] = {entry["plan"]["ref"] for entry in planned if "ref" in entry["plan"]}
        built: list[NewStep] = []
        entry: PlannedStep
        for entry in planned:
            plan: StepPlan = entry["plan"]
            if "inputs" in plan:
                plan = {
                    **plan,
                    "inputs": [name if name in refs_here else self._resolve(name) for name in plan["inputs"]],
                }
            built.append(NewStep(plan, entry.get("params")))
        return tuple(built)

    def _apply(self, change: JournalChange) -> Applied:
        """Apply one change to the journal file as a single locked read-modify-write.

        Returns:
            The change's number and operation, the step it named and the steps it added.

        Raises:
            JournalChangeError: The steps the journal added are not the steps the change planned.

        """
        step_id: StepId = self._resolve(change["step"])
        op: ChangeOp = change["op"]
        planned: list[PlannedStep] = change.get("add", [])
        new_steps: tuple[NewStep, ...] = self._new_steps(planned)

        def edit(journal: Journal) -> list[StepId]:
            moment: str = step_journal.timestamp()
            before: set[StepId] = set(_step_ids(journal))
            if op == CHANGE_OP_START:
                step_journal.start_step(journal, step_id, moment)
            elif op == CHANGE_OP_FAIL:
                step_journal.fail_step(journal, step_id, change.get("failure", ""), moment)
            elif op in {CHANGE_OP_ADD, CHANGE_OP_DONE}:
                where: Where = UNDER_THIS if op == CHANGE_OP_ADD else AFTER_THIS
                groups: tuple[StepGroup, ...] = (StepGroup(new_steps, where),) if new_steps else ()
                completion: Completion = Completion(tuple(change.get("artifacts", [])), groups)
                apply_completion(journal, step_id, completion, moment)
            else:
                assert_never(op)
            return [held for held in _step_ids(journal) if held not in before]

        added: list[StepId] = step_journal.update_journal(self.path, edit)
        if len(added) != len(planned):
            problem: str = (
                f"journal change {change['n']} of run {self.run} planned {len(planned)} steps and "
                f"the journal added {len(added)}"
            )
            raise JournalChangeError(problem)
        entry: PlannedStep
        new_id: StepId
        for entry, new_id in zip(planned, added, strict=True):
            if "ref" in entry["plan"]:
                self.refs[entry["plan"]["ref"]] = new_id
        return Applied(change["n"], op, step_id, tuple(added))
