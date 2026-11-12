"""Open design gaps in a repository's specification documents, and their way back to the solutions architect.

A spec author designs nothing: a detail its Story needs that no approved document states is a gap
in the design, recorded as one row of the table under the heading :data:`HEADING` of the document
that needs it, and settled by nobody in the spec stage. No Story is written and no Task is
decomposed from a document that holds an open gap. The step after the review
(``spec_authoring.story_document``) reads every row (:func:`open_gaps`); when one is left it files
the repository's gaps under the architecture work folder (:func:`file_gaps`) and sets the last
architecture check and every step after it back to planned (``DesignGapError``, the journal
runner's way back to an earlier step). The repositories' containers running at the same time each
go on to their own gap check before the runner sets the check back, so every repository's gaps are
filed together. The check, run again, finds the filed gaps (:func:`handed`) and plans the solutions
architect's step that answers them (:data:`ANSWER_DESCRIPTION`), then the document writes, the
index, the check, the promotion and the specs, as after any Decide. That step's result answers
every row it was handed under ``gapAnswers`` (:func:`unanswered`, which checks only the answers to
the rows handed now), and its accepted result moves
the gaps to the settled folder and records each row as answered (:func:`settle`).

The gaps converge row by row: a row the architect answered that a repository's documents hold
again fails the step, while a row never handed before gets its own round. A repository whose gaps
went to the architect :data:`MAX_ROUNDS` times fails the step when it holds an open gap again.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, TypedDict

from typeguard import CollectionCheckStrategy, check_type

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import DesignGapError, StepError
from orchestrator.flows.architecture_files import CHECK, architecture_folder

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import STATUS_DONE

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from architecture_work_contract import ArchitectureResult, GapAnswer
    from step_journal_contract import Step, StepId

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
MAX_ROUNDS: Final = 3
"""How many times a repository's gaps go to the architect before an open gap of it fails the step."""
_SECTION: Final = re.compile(rf"^##\s+{re.escape(HEADING)}\s*$", re.IGNORECASE)
_NEXT_SECTION: Final = re.compile(r"^#{1,2}\s")
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


def _section(lines: Sequence[str]) -> list[str]:
    """Find the design gaps section of a document.

    Returns:
        The lines of the section, stripped and without its heading; empty when it has none.

    """
    inside: bool = False
    held: list[str] = []
    for line in lines:
        if _SECTION.match(line):
            inside = True
            continue
        if inside and _NEXT_SECTION.match(line):
            break
        if inside:
            held.append(line.strip())
    return held


def open_gaps(path: Path) -> list[str]:
    """List the open design gaps one spec document records.

    Each data row of a table under the heading :data:`HEADING` is one gap; its first row is the
    table's header. A list item there is one gap too. Prose (for example "None.") is none.

    Returns:
        Each gap as its row's text, in document order; empty when the document has no section or
        the file does not exist.

    """
    if not path.is_file():
        return []
    gaps: list[str] = []
    header_seen: bool = False
    line: str
    for line in _section(path.read_text(encoding="utf-8").splitlines()):
        if line.startswith("|"):
            if _SEPARATOR.match(line):
                continue
            if not header_seen:
                header_seen = True
                continue
            gaps.append(line)
        elif _LIST_ITEM.match(line):
            gaps.append(line)
    return gaps


def _folder(work: Path, state: str) -> Path:
    """Name the folder of the open or the settled design gaps.

    Returns:
        The folder under the architecture work folder.

    """
    return architecture_folder(work) / FOLDER / state


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


def file_gaps(run: StepRun, slug: str, repository: str, documents: Sequence[Path]) -> list[FiledDocument]:
    """Read the open gaps of a repository's spec documents and, when there are any, file them for the architect.

    Returns:
        Each document that holds a gap, with its rows; empty, and nothing filed, when none does.

    """
    filed: list[FiledDocument] = [
        {"document": str(path), "gaps": gaps} for path in documents if (gaps := open_gaps(path))
    ]
    if filed:
        payload: FiledGaps = {"repository": repository, "documents": filed}
        write_json(_folder(run.context.work, OPEN) / f"{slug}.json", payload)
    return filed


def _answers_file(work: Path) -> Path:
    """Name the file that records what the architect answered of each repository's gaps.

    Returns:
        The file in the design gaps folder.

    """
    return architecture_folder(work) / FOLDER / ANSWERS


def _answered(value: JsonValue) -> Answered | None:
    """Read one repository's record of the answers file.

    Returns:
        The record; None for a value of no record, such as the bare count an earlier form of the
        file held, which named no row the architect answered.

    """
    if not isinstance(value, dict):
        return None
    rounds: JsonValue = value.get(KEY_ROUNDS)
    rows: JsonValue = value.get(KEY_ROWS)
    if not isinstance(rounds, int) or not isinstance(rows, list):
        return None
    return Answered(rounds, frozenset(row for row in rows if isinstance(row, str)))


def answers(work: Path) -> dict[str, Answered]:
    """Read what the architect answered of each repository's open design gaps.

    Returns:
        The record of each repository's slug; empty when nothing was answered.

    """
    path: Path = _answers_file(work)
    if not path.is_file():
        return {}
    held: dict[str, JsonValue] = json_object(json.loads(path.read_text(encoding="utf-8")))
    return {slug: record for slug, value in held.items() if (record := _answered(value)) is not None}


def hold_open(run: StepRun, slug: str, repository: str, documents: Sequence[Path]) -> None:
    """Stop a repository whose spec documents hold an open design gap from reaching its Story and Tasks.

    Raises:
        DesignGapError: A document holds an open gap: the gaps are filed for the solutions
            architect, and the last architecture check and every step after it are set back to planned.
        StepError: A document holds a row the architect already answered, or the repository's gaps
            already went to the architect :data:`MAX_ROUNDS` times; the gaps are filed and the step fails.

    """
    filed: list[FiledDocument] = file_gaps(run, slug, repository, documents)
    if not filed:
        return
    record: Answered = answers(run.context.work).get(slug, Answered())
    evidence: list[str] = [f"{held['document']}: {gap}" for held in filed for gap in held["gaps"]]
    returned: list[str] = [f"{held['document']}: {gap}" for held in filed for gap in held["gaps"] if gap in record.rows]
    if returned:
        cause: str = (
            f"the spec documents of {repository} hold again design gaps the solutions architect already answered; "
            "the design does not converge"
        )
        raise StepError(run.inputs.stage, OTHER_CAUSE, (cause, *returned))
    if record.rounds >= MAX_ROUNDS:
        cause = (
            f"the spec documents of {repository} still hold open design gaps after the solutions architect "
            f"answered that repository's design gaps {record.rounds} times; the design does not converge"
        )
        raise StepError(run.inputs.stage, OTHER_CAUSE, (cause, *evidence))
    raise DesignGapError(run.inputs.stage, check_writer(run), tuple(evidence))


def handed(work: Path) -> tuple[tuple[str, Path], ...]:
    """Name each repository's open design gaps, filed for the solutions architect's next session.

    Returns:
        Each filed file under the label :data:`LABEL_GAPS`, in name order.

    """
    folder: Path = _folder(work, OPEN)
    if not folder.is_dir():
        return ()
    return tuple((LABEL_GAPS, path) for path in sorted(folder.glob("*.json")))


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
