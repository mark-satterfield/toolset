"""Open design gaps in a repository's specification documents, and their way back to the solutions architect.

A spec author sorts every detail its Story needs that no approved document states into one of
three kinds. A name the project's naming standard produces (kind A) the author builds with the
naming command and writes. A detail local to one repository (kind B) is recorded under the
heading :data:`DECIDED_HEADING`, decided at build, and blocks nothing. A detail that crosses a
boundary, contradicts another document or is invalid (kind C) is a gap in the design, recorded
as one row of the table under the heading :data:`HEADING` of the document that needs it. The
step after the review (``spec_authoring.story_document``) reads every gap row (:func:`open_gaps`)
through :func:`hold_open`; when one is left it files the repository's gaps under the
architecture work folder and raises ``DesignGapError``. The repositories' containers each go on
to their own gap check first, every one of them and not only those running at the same time,
so every repository's gaps go to the architect in one round. The round is local: the journal
runner adds one gap round (:func:`gap_round`) to the end of the Architecture container (the
solutions architect's step that answers the filed gaps, :data:`ANSWER_DESCRIPTION`, the index and
the check), plans the TRD confirmation again, and sets back only the spec steps of each repository
that held a gap. The architect's step writes the answers (``gapAnswers``, :func:`unanswered`, which
checks only the answers to the rows handed now); its accepted result plans the document writes and
moves the gaps to the settled folder, recording each row as answered (:func:`settle`). The check
then plans the promotion of the answered documents, and the TRD write only when the result's TRD
changes differ from those the last TRD write applied. No other repository is specified again, and
no impact analysis runs in the round.

The Epic never carries a design gap to the build, and no row escalates before the architect has
seen it. A row is known across rounds by its exact text, as the spec document states it: the
answers file records the text of every row the architect answered. A row the architect already
answered that a repository's documents hold again escalates for a decision (:func:`escalate`); a
row the architect was never handed goes to it in another round, a row found only after a round
included, until the repository's gaps went to the architect :data:`MAX_ROUNDS` times (two rounds),
after which every row still open escalates, so a design that does not converge cannot loop.
Escalated rows are recorded in the escalated folder, a warning note names them, and the step fails
with the cause ``design-gap``, so the Epic stops until an owner or architecture decision settles
them. The spec documents are not edited. When the Epic resumes, the failed step reads its
documents again: a row escalated earlier that the architect never answered is handed to it like
any other row below the limit, and leaves the escalated folder (:func:`hold_open`). The rounds are
counted from every record there is: ``answers.json`` in either of its forms (a bare count, or the
rounds with the rows) and the settled folder, which keeps each round's files. A repository at the
limit is never handed to the architect again (:func:`handed`). The leftover folder holds the rows
that journals created before escalation carried to the build; the elaboration's buildability gate
reads it (:func:`leftover_rows`) and reports each such repository as a defect.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, NoReturn, TypedDict

from typeguard import CollectionCheckStrategy, check_type

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import DESIGN_GAP_CAUSE, OTHER_CAUSE, warning_note
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import DesignGapError, StepError
from orchestrator.flows.architecture_files import (
    ARCHITECT,
    ARCHITECTURE,
    CHECK,
    CHECK_DESCRIPTION,
    CHECK_PURPOSE,
    CONFIRM_TRD,
    architecture_folder,
)
from orchestrator.flows.architecture_index import index_step
from orchestrator.flows.elaboration_files import SPEC_CONTEXT
from orchestrator.flows.elaboration_support import emit_event

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path, and the orchestrator's bootstrap the
# portfolio scripts directory; the imports from them follow.
from matrixchecklist import UnfilledValue
from step_journal_contract import STATUS_DONE

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence
    from pathlib import Path

    from architecture_work_contract import ArchitectureResult, GapAnswer
    from step_journal_contract import Journal, Step, StepId, StepPlan

    from orchestrator.core.journal_steps import StepRun

HEADING: Final = "Design gaps"
"""The heading, at level 2, of the one section of a spec document that records its open design gaps."""
LABEL_GAPS: Final = "design gaps"
"""The label the solutions architect is handed each repository's open design gaps under."""
ANSWER_REF: Final = "design-gaps"
ANSWER_DESCRIPTION: Final = "Answer the design gaps the spec stage found"
ANSWER_PURPOSE: Final = "Every detail a Story needs is decided in the approved architecture before its spec is written"
FOLDER: Final = "design-gaps"
OPEN: Final = "open"
SETTLED: Final = "settled"
ANSWERS: Final = "answers.json"
"""The file, in the design gaps folder, that records each repository's rounds and the rows the architect answered."""
KEY_ROUNDS: Final = "rounds"
KEY_ROWS: Final = "rows"
MAX_ROUNDS: Final = 2
"""How many times a repository's gaps go to the architect before its open gaps escalate for a decision."""
DECIDED_HEADING: Final = "Decided at build"
"""The heading, at level 2, of the section of a spec document that lists the details the build decides."""
LEFTOVER: Final = "leftover"
"""The folder of the gap rows that journals created before escalation carried to the build."""
ESCALATED: Final = "escalated"
"""The folder, beside the open and the settled ones, of each repository's gap rows escalated for a decision."""
GAP_HEADER: Final = "| Id | Element whose design lacks it | Missing detail (review criterion) |"
GAP_SEPARATOR: Final = "|---|---|---|"
UNFILLED: Final = "unfilled-values.json"
"""The file, in the design gaps folder, of the element values the architecture check carried to the spec stage."""
UNFILLED_DEFECT: Final = "element values left unfilled after the mechanical corrections of the architecture"
"""How the warning note names the pipeline defect a carried element value is."""
UNFILLED_ID: Final = "EV"
"""The prefix of the id of a gap row written for a carried element value."""
DATA_MODEL_CRITERIA: Final[frozenset[str]] = frozenset({"A16", "A20"})
"""The criteria whose carried values are gap rows of the data model; the others are rows of the contracts."""
_SECTION: Final = re.compile(rf"^##\s+{re.escape(HEADING)}\s*$", re.IGNORECASE)
_DECIDED_SECTION: Final = re.compile(rf"^##\s+{re.escape(DECIDED_HEADING)}\s*$", re.IGNORECASE)
_NEXT_SECTION: Final = re.compile(r"^#{1,2}\s")
_LINKS_SECTION: Final = re.compile(r"^##\s+Architecture and design documents\s*$")
_SEPARATOR: Final = re.compile(r"^\|[\s:|-]*\|$")
_LIST_ITEM: Final = re.compile(r"^(?:[-*+]|\d+[.)])\s+\S")


class FiledDocument(TypedDict):
    """One spec document of a filed repository, with each open gap row it holds."""

    document: str
    gaps: list[str]


class FiledGaps(TypedDict):
    """The open design gaps of one repository, filed for the solutions architect."""

    repository: str
    documents: list[FiledDocument]


@dataclass(frozen=True)
class Answered:
    """What the architect answered of one repository's gaps."""

    rounds: int = 0
    """How many times the repository's gaps went to the architect and were answered."""
    rows: frozenset[str] = frozenset()
    """Each gap row the architect answered."""


def _bounds(lines: Sequence[str], heading: re.Pattern[str]) -> tuple[int, int] | None:
    """Find a level-2 section of a document.

    Returns:
        The index of its heading line and the index after its last line; None when it has none.

    """
    start: int | None = next((index for index, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        return None
    end: int = next(
        (index for index in range(start + 1, len(lines)) if _NEXT_SECTION.match(lines[index])),
        len(lines),
    )
    return start, end


def _table_rows(lines: Sequence[str]) -> list[str]:
    """Read the rows of the lines of one section.

    Each data row of a table is one row; a table's first row is its header. A list item is one
    row too. Prose (for example "None.") is none.

    Returns:
        Each row as its stripped text, in document order.

    """
    rows: list[str] = []
    header_seen: bool = False
    line: str
    for line in (held.strip() for held in lines):
        if line.startswith("|"):
            if _SEPARATOR.match(line):
                continue
            if not header_seen:
                header_seen = True
                continue
            rows.append(line)
        elif _LIST_ITEM.match(line):
            rows.append(line)
    return rows


def _section_rows(path: Path, heading: re.Pattern[str]) -> list[str]:
    """List the rows one section of a spec document records.

    Returns:
        Each row's text, in document order; empty when the document has no such section or the
        file does not exist.

    """
    if not path.is_file():
        return []
    lines: list[str] = path.read_text(encoding="utf-8").splitlines()
    found: tuple[int, int] | None = _bounds(lines, heading)
    return [] if found is None else _table_rows(lines[found[0] + 1 : found[1]])


def open_gaps(path: Path) -> list[str]:
    """List the open design gaps one spec document records, each a row under the heading :data:`HEADING`.

    Returns:
        Each gap as its row's text, in document order; empty when there is none.

    """
    return _section_rows(path, _SECTION)


def decided_at_build(path: Path) -> list[str]:
    """List the details one spec document leaves to the build, each a row under :data:`DECIDED_HEADING`.

    Returns:
        Each detail as its row's text, in document order; empty when there is none.

    """
    return _section_rows(path, _DECIDED_SECTION)


def _folder(work: Path, state: str) -> Path:
    """Name the folder of the open or the settled design gaps.

    Returns:
        The folder under the architecture work folder.

    """
    return architecture_folder(work) / FOLDER / state


def gap_round(inputs: list[str]) -> tuple[StepPlan, ...]:
    """Plan the round that takes filed gaps to the solutions architect.

    Args:
        inputs: The steps the architect's step is handed, by id or by ref: the check before it.

    Returns:
        The architect's step, the index and the check after it, in the order they run. The
        check starts with no corrections spent, because the answer is a new design change.

    """
    answer: StepPlan = {
        "ref": ANSWER_REF,
        "description": ANSWER_DESCRIPTION,
        "purpose": ANSWER_PURPOSE,
        "agent": ARCHITECT,
        "inputs": inputs,
    }
    check: StepPlan = {
        "description": CHECK_DESCRIPTION,
        "purpose": CHECK_PURPOSE,
        "script": CHECK,
        "inputs": [ANSWER_REF],
    }
    return (answer, index_step([ANSWER_REF]).plan, check)


def check_writer(run: StepRun) -> StepId:
    """Find the architecture check that ran last, the step an open design gap sets back.

    Returns:
        The last done architecture check, in walk order.

    Raises:
        ValueError: The journal holds no done architecture check.

    """
    checks: list[Step] = [
        step
        for step in step_journal.steps_in_order(run.journal())
        if step.get("script") == CHECK and step["status"] == STATUS_DONE
    ]
    if not checks:
        message: str = "the journal holds no done architecture check to send the open design gaps back to"
        raise ValueError(message)
    return checks[-1]["id"]


def _held_gaps(documents: Sequence[Path]) -> list[FiledDocument]:
    """Read the open gaps of a repository's spec documents.

    Returns:
        Each document that holds a gap, with its rows; empty when none does.

    """
    return [{"document": str(path), "gaps": gaps} for path in documents if (gaps := open_gaps(path))]


def _only(filed: Sequence[FiledDocument], rows: Collection[str], *, keep: bool) -> list[FiledDocument]:
    """Keep, or leave out, the given rows of each filed document.

    Returns:
        Each document that still holds a row, with those rows.

    """
    return [
        {"document": held["document"], "gaps": kept}
        for held in filed
        if (kept := [gap for gap in held["gaps"] if (gap in rows) == keep])
    ]


def _answers_file(work: Path) -> Path:
    """Name the file that records what the architect answered of each repository's gaps.

    Returns:
        The file in the design gaps folder.

    """
    return architecture_folder(work) / FOLDER / ANSWERS


def _answered(value: JsonValue) -> Answered | None:
    """Read one repository's record of the answers file, in either form the file has had.

    Returns:
        The record: from a bare count, an earlier form of the file, its rounds with no row; None
        for a value that is no record.

    """
    if isinstance(value, int) and not isinstance(value, bool):
        return Answered(value)
    if not isinstance(value, dict):
        return None
    rounds: JsonValue = value.get(KEY_ROUNDS)
    rows: JsonValue = value.get(KEY_ROWS)
    if not isinstance(rounds, int) or not isinstance(rows, list):
        return None
    return Answered(rounds, frozenset(row for row in rows if isinstance(row, str)))


def _settled(work: Path) -> dict[str, Answered]:
    """Count the rounds the settled folder records for each repository, with the rows answered in them.

    Returns:
        For each slug, one round per settled step folder that holds its file, and every row of
        those files.

    """
    folder: Path = _folder(work, SETTLED)
    if not folder.is_dir():
        return {}
    counted: dict[str, Answered] = {}
    path: Path
    for path in sorted(folder.glob("*/*.json")):
        held: Answered = counted.get(path.stem, Answered())
        counted[path.stem] = Answered(held.rounds + 1, held.rows | frozenset(_rows(_filed(path))))
    return counted


def answers(work: Path) -> dict[str, Answered]:
    """Read what the architect answered of each repository's open design gaps.

    A round the answers file lost (its earlier form named no row, and a later write dropped such
    records) is still in the settled folder, so each repository's rounds are the larger of the two
    counts and its rows are those of both.

    Returns:
        The record of each repository's slug; empty when nothing was answered.

    """
    path: Path = _answers_file(work)
    held: dict[str, JsonValue] = json_object(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else {}
    recorded: dict[str, Answered] = {
        slug: record for slug, value in held.items() if (record := _answered(value)) is not None
    }
    settled: dict[str, Answered] = _settled(work)
    return {
        slug: _merged(recorded.get(slug, Answered()), settled.get(slug, Answered()))
        for slug in sorted(recorded.keys() | settled.keys())
    }


def _merged(recorded: Answered, settled: Answered) -> Answered:
    """Join a repository's record of the answers file with the record of the settled folder.

    Returns:
        The larger count of rounds, and the rows of both.

    """
    return Answered(max(recorded.rounds, settled.rounds), recorded.rows | settled.rows)


def _repository_start(run: StepRun, journal: Journal) -> tuple[StepId, StepId]:
    """Name the first spec step of the repository whose gap check runs now, and its container.

    Returns:
        The repository's context step and the container that holds it.

    Raises:
        StepError: The step is in no container, or its container holds no context step.

    """
    container: Step | None = step_journal.parent_step(journal, run.step["id"])
    first: Step | None = next(
        (step for step in ([] if container is None else container["steps"]) if step.get("script") == SPEC_CONTEXT),
        None,
    )
    if container is None or first is None:
        message: str = f"step {run.step['id']} is in no repository container with a {SPEC_CONTEXT} step"
        raise StepError(run.inputs.stage, OTHER_CAUSE, (message,))
    return first["id"], container["id"]


def hold_open(run: StepRun, slug: str, repository: str, documents: Sequence[Path]) -> None:
    """Stop a repository whose spec documents hold an open design gap from reaching its Story and Tasks.

    A row the architect already answered escalates for a decision (:func:`escalate`). Every other
    row goes to the architect, in another round, until the repository's gaps went to it
    :data:`MAX_ROUNDS` times; at the limit every open row escalates. No gap is ever carried to the
    build. A row handed now that an earlier stop escalated (the architect never answered it) leaves
    the escalated folder.

    Raises:
        DesignGapError: A document holds an open gap the architect was not handed before, below
            the round limit: the gaps are filed for the solutions architect, one gap round is added
            to the Architecture container, the TRD is confirmed again, and the repository's spec
            steps alone are set back to planned.

    """
    filed: list[FiledDocument] = _held_gaps(documents)
    if not filed:
        return
    record: Answered = answers(run.context.work).get(slug, Answered())
    repeated: list[FiledDocument] = _only(filed, record.rows, keep=True)
    if repeated:
        escalate(run, slug, repository, repeated)
    if record.rounds >= MAX_ROUNDS:
        escalate(run, slug, repository, filed)
    payload: FiledGaps = {"repository": repository, "documents": filed}
    write_json(_folder(run.context.work, OPEN) / f"{slug}.json", payload)
    _unescalate(run.context.work, slug, _rows(payload))
    journal: Journal = run.journal()
    first: StepId
    container: StepId
    first, container = _repository_start(run, journal)
    raise DesignGapError(
        run.inputs.stage,
        first,
        tuple(f"{held['document']}: {gap}" for held in filed for gap in held["gaps"]),
        container,
        container=run.step_named(ARCHITECTURE)["id"],
        plans=gap_round([check_writer(run)]),
        reconfirm=tuple(step["id"] for step in journal["steps"] if step.get("script") == CONFIRM_TRD),
    )


def _unescalate(work: Path, slug: str, rows: Collection[str]) -> None:
    """Take rows handed to the architect now out of a repository's escalated file.

    A row an earlier stop escalated before the architect ever saw it is no longer escalated once
    it is handed; the file is removed when no row is left in it.
    """
    target: Path = _folder(work, ESCALATED) / f"{slug}.json"
    if not target.is_file():
        return
    held: FiledGaps = _filed(target)
    kept: list[FiledDocument] = _only(held["documents"], rows, keep=False)
    if kept:
        write_json(target, {"repository": held["repository"], "documents": kept})
    else:
        target.unlink()


def escalate(run: StepRun, slug: str, repository: str, filed: Sequence[FiledDocument]) -> NoReturn:
    """Escalate gap rows the architect's round did not settle for a decision, and stop the Epic.

    The rows join the repository's file in the escalated folder (merged with an earlier file); the
    repository's open file, which no architect will be handed again, is removed; a warning note
    names the Epic, the repository and the rows. The spec documents are not edited.

    Raises:
        StepError: Always, with the cause ``design-gap`` and one evidence line per row.

    """
    target: Path = _folder(run.context.work, ESCALATED) / f"{slug}.json"
    earlier: list[FiledDocument] = _filed(target)["documents"] if target.is_file() else []
    merged: dict[str, list[str]] = {held["document"]: list(held["gaps"]) for held in earlier}
    held: FiledDocument
    for held in filed:
        known: list[str] = merged.setdefault(held["document"], [])
        known.extend(gap for gap in held["gaps"] if gap not in known)
    payload: FiledGaps = {
        "repository": repository,
        "documents": [{"document": document, "gaps": gaps} for document, gaps in merged.items()],
    }
    write_json(target, payload)
    (_folder(run.context.work, OPEN) / f"{slug}.json").unlink(missing_ok=True)
    rows: list[str] = [gap for held in filed for gap in held["gaps"]]
    detail: str = f"design gaps escalated for a decision: Epic {run.bead}, repository {repository}: {rows}"
    emit_event(run.agents.emit, warning_note(run.inputs.stage, detail))
    raise StepError(
        run.inputs.stage,
        DESIGN_GAP_CAUSE,
        tuple(f"{held['document']}: {gap}" for held in filed for gap in held["gaps"]),
    )


def _with_rows(
    lines: list[str],
    added: Sequence[str],
    section: re.Pattern[str],
    heading: str,
    header: tuple[str, str],
) -> list[str]:
    """Add rows to the table of a level-2 section of a document, writing the section when it has none.

    A new section goes before the links to the architecture and design documents, or at the end.

    Returns:
        The document's lines.

    """
    found: tuple[int, int] | None = _bounds(lines, section)
    if found is not None:
        last: int = max(
            (index for index in range(found[0], found[1]) if lines[index].strip().startswith("|")),
            default=found[0],
        )
        table: list[str] = [] if last > found[0] else ["", *header]
        return [*lines[: last + 1], *table, *added, *lines[last + 1 :]]
    links: tuple[int, int] | None = _bounds(lines, _LINKS_SECTION)
    at: int = len(lines) if links is None else links[0]
    written: list[str] = [f"## {heading}", "", *header, *added, ""]
    return [*lines[:at], *([""] if at and lines[at - 1].strip() else []), *written, *lines[at:]]


def leftover_rows(work: Path) -> list[tuple[str, str]]:
    """List every gap row a journal created before escalation carried to the build, with its repository.

    Returns:
        Each repository and row, file by file in name order; empty when none was carried.

    """
    folder: Path = _folder(work, LEFTOVER)
    if not folder.is_dir():
        return []
    return [
        (filed["repository"], gap)
        for path in sorted(folder.glob("*.json"))
        for filed in (_filed(path),)
        for gap in _rows(filed)
    ]


def handed(work: Path) -> tuple[tuple[str, Path], ...]:
    """Name each repository's open design gaps, filed for the solutions architect's next session.

    A repository whose gaps already went to the architect :data:`MAX_ROUNDS` times is not handed:
    its spec step escalates its rows for a decision (:func:`hold_open`).

    Returns:
        Each filed file under the label :data:`LABEL_GAPS`, in name order.

    """
    folder: Path = _folder(work, OPEN)
    if not folder.is_dir():
        return ()
    spent: set[str] = {slug for slug, record in answers(work).items() if record.rounds >= MAX_ROUNDS}
    return tuple((LABEL_GAPS, path) for path in sorted(folder.glob("*.json")) if path.stem not in spent)


def _filed(path: Path) -> FiledGaps:
    """Read one repository's filed gaps.

    Returns:
        The file's content, typed; ``check_type`` refuses a file that does not hold filed gaps.

    """
    return check_type(
        json.loads(path.read_text(encoding="utf-8")),
        FiledGaps,
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


def _rows(filed: FiledGaps) -> list[str]:
    """List every gap row of one repository's filed gaps.

    Returns:
        The rows, document by document.

    """
    return [gap for held in filed["documents"] for gap in held["gaps"]]


def _fact_problems(answer: GapAnswer, fact_ids: set[str]) -> list[str]:
    """Refuse an answer that names a fact the result does not hold.

    Returns:
        One problem when a fact id it names is not in the result's ``facts``; empty otherwise.

    """
    missing: list[str] = sorted(set(answer["facts"]) - fact_ids)
    if not missing:
        return []
    problem: str = (
        f"gapAnswers: the answer to the design gap {answer['gap']!r} of {answer['repository']} names fact ids "
        f"{missing} that facts does not hold: state the decision in facts and name those facts"
    )
    return [problem]


def unanswered(work: Path, result: ArchitectureResult) -> list[str]:
    """Find each open design gap row the architect was handed that its result does not answer.

    Only the rows handed now are checked. The result is updated in place, so it may still hold
    answers to rows an earlier round settled; those answers are recorded in ``answers.json`` and
    are not checked again, so a later step may drop the facts they named.

    Returns:
        One problem for each answer to a handed row naming a fact the result does not hold, and one
        for each handed row with no entry of ``gapAnswers`` for its repository and its exact text.

    """
    files: list[tuple[Path, FiledGaps]] = [(path, _filed(path)) for _label, path in handed(work)]
    rows: dict[tuple[str, str], Path] = {
        (filed["repository"], gap): path for path, filed in files for gap in _rows(filed)
    }
    given: list[GapAnswer] = [
        answer for answer in result.get("gapAnswers", []) if (answer["repository"], answer["gap"]) in rows
    ]
    fact_ids: set[str] = {fact["id"] for fact in result["facts"]}
    keys: set[tuple[str, str]] = {(answer["repository"], answer["gap"]) for answer in given}
    problems: list[str] = [problem for answer in given for problem in _fact_problems(answer, fact_ids)]
    problems.extend(
        f"gapAnswers: no answer to the design gap {gap!r} of {repository} ({path}): decide it, state it in facts, "
        "and record it under gapAnswers with its repository and the row exactly as the file states them"
        for (repository, gap), path in rows.items()
        if (repository, gap) not in keys
    )
    return problems


def settle(work: Path, step: StepId) -> None:
    """Move the open design gaps an accepted architect result answered to the settled folder, under its step.

    Each repository whose gaps were moved is counted one more round, and each of its rows is
    recorded as answered (:func:`answers`).
    """
    files: tuple[tuple[str, Path], ...] = handed(work)
    if not files:
        return
    target: Path = _folder(work, SETTLED) / step
    target.mkdir(parents=True, exist_ok=True)
    counted: dict[str, Answered] = answers(work)
    path: Path
    for _label, path in files:
        held: Answered = counted.get(path.stem, Answered())
        counted[path.stem] = Answered(held.rounds + 1, held.rows | frozenset(_rows(_filed(path))))
        shutil.move(str(path), target / path.name)
    write_json(
        _answers_file(work),
        {slug: {KEY_ROUNDS: record.rounds, KEY_ROWS: sorted(record.rows)} for slug, record in sorted(counted.items())},
    )


def _unfilled_file(work: Path) -> Path:
    """Name the file of the element values carried to the spec stage.

    Returns:
        The file in the design gaps folder.

    """
    return architecture_folder(work) / FOLDER / UNFILLED


def unfilled(work: Path) -> list[UnfilledValue]:
    """Read the element values the architecture check carried to the spec stage.

    Returns:
        Each carried value, in the order carried; empty when none was.

    """
    path: Path = _unfilled_file(work)
    if not path.is_file():
        return []
    return check_type(
        json.loads(path.read_text(encoding="utf-8")),
        list[UnfilledValue],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


def carried_values(work: Path) -> set[tuple[str, str, str]]:
    """Name the element values already carried to the spec stage, by element, criterion and item.

    Returns:
        The keys of :func:`unfilled`.

    """
    return {(value["element"], value["criterion"], value["item"]) for value in unfilled(work)}


def carry_unfilled(run: StepRun, values: Sequence[UnfilledValue]) -> None:
    """Carry element values the architect left unfilled to the spec stage, and report the pipeline defect.

    The values join the file :data:`UNFILLED`, which the step after the spec review of each
    repository reads (:func:`add_unfilled`): each value of an element the repository's Story
    builds becomes a kind C row of its design gaps, which goes to the architect in a gap round
    and escalates for a decision when the architect's answer leaves it open. A warning note names
    the Epic and the values.
    """
    if not values:
        return
    held: list[UnfilledValue] = unfilled(run.context.work)
    known: set[tuple[str, str, str]] = {(value["element"], value["criterion"], value["item"]) for value in held}
    held.extend(value for value in values if (value["element"], value["criterion"], value["item"]) not in known)
    write_json(_unfilled_file(run.context.work), held)
    detail: str = (
        f"pipeline defect, {UNFILLED_DEFECT}: Epic {run.bead}: {len(values)} element values carried to the spec "
        f"stage as design gaps: {' ; '.join(_detail(value) for value in values)}"
    )
    emit_event(run.agents.emit, warning_note(run.inputs.stage, detail))


def _detail(value: UnfilledValue) -> str:
    """Name one carried element value in a gap row's cell.

    Returns:
        The item, its criterion and what was wrong, with no table mark.

    """
    return f"{value['item']} ({value['criterion']}): {value['problem']}".replace("|", "/")


def unfilled_row(index: int, value: UnfilledValue) -> str:
    """Write one carried element value as a row of a spec document's design gaps table.

    Returns:
        The row, its id :data:`UNFILLED_ID` and the value's place in the carried file.

    """
    return f"| {UNFILLED_ID}{index} | {value['element']} | {_detail(value)} |"


def add_unfilled(run: StepRun, slug: str, built: Collection[str], contracts: Path, data_model: Path) -> None:
    """Write each carried element value of an element a repository's Story builds as a design gap of its spec.

    A value of the data model's criteria (:data:`DATA_MODEL_CRITERIA`) goes to the data model,
    any other to the contracts; to the one of them that exists when the other does not. A row the
    architect already answered, one a journal created before escalation carried to the build and
    one the document already holds is not written again.

    Args:
        run: The step after the spec review.
        slug: The repository's slug.
        built: The matrix ids of what the repository's Story builds.
        contracts: The repository's contracts document.
        data_model: The repository's data model document.

    """
    answered_rows: frozenset[str] = answers(run.context.work).get(slug, Answered()).rows
    carried_rows: set[str] = {row for _repository, row in leftover_rows(run.context.work)}
    rows: dict[Path, list[str]] = {}
    index: int
    value: UnfilledValue
    for index, value in enumerate(unfilled(run.context.work), start=1):
        row: str = unfilled_row(index, value)
        target: Path | None = _unfilled_target(value, contracts, data_model)
        if value["element"] not in built or target is None or row in answered_rows | carried_rows:
            continue
        rows.setdefault(target, []).append(row)
    for target, added in rows.items():
        fresh: list[str] = [row for row in added if row not in open_gaps(target)]
        lines: list[str] = target.read_text(encoding="utf-8").splitlines()
        written: list[str] = _with_rows(lines, fresh, _SECTION, HEADING, (GAP_HEADER, GAP_SEPARATOR))
        target.write_text("\n".join(written) + "\n", encoding="utf-8")


def _unfilled_target(value: UnfilledValue, contracts: Path, data_model: Path) -> Path | None:
    """Choose the spec document a carried element value is a design gap of.

    Returns:
        The data model for a value of :data:`DATA_MODEL_CRITERIA`, the contracts otherwise; the
        other one when the chosen one does not exist; None when neither exists.

    """
    first, second = (data_model, contracts) if value["criterion"] in DATA_MODEL_CRITERIA else (contracts, data_model)
    return next((path for path in (first, second) if path.is_file()), None)
