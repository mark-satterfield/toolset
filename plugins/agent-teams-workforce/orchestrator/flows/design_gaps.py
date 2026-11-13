"""Open design gaps in a repository's specification documents, and their way back to the solutions architect.

A spec author designs nothing: a detail its Story needs that no approved document states is a gap
in the design, recorded as one row of the table under the heading :data:`HEADING` of the document
that needs it, and settled by nobody in the spec stage. No Story is written and no Task is
decomposed from a document that holds an open gap. The step after the review
(``spec_authoring.story_document``) reads every row (:func:`open_gaps`); when one is left it files
the repository's gaps under the architecture work folder (:func:`file_gaps`) and raises
``DesignGapError``. The repositories' containers running at the same time each go on to their own
gap check first, so every repository's gaps are filed together. The round is local: the journal
runner adds one gap round (:func:`gap_round`) to the end of the Architecture container (the
solutions architect's step that answers the filed gaps, :data:`ANSWER_DESCRIPTION`, the index and
the check), plans the TRD confirmation again, and sets back only the spec steps of each repository
that held a gap. The architect's step writes the answers (``gapAnswers``, :func:`unanswered`, which
checks only the answers to the rows handed now); its accepted result plans the document writes and
moves the gaps to the settled folder, recording each row as answered (:func:`settle`). The check
then plans the promotion of the answered documents, and the TRD write only when the result's TRD
changes differ from those the last TRD write applied. No other repository is specified again, and
no impact analysis runs in the round.

The findings of the architecture completeness review (``architecture_completeness``) take the same
way to the architect, filed as the gaps of :data:`REVIEW_SLUG` before any spec is written.

The gaps converge row by row: a row the architect answered that a repository's documents hold
again fails the step, while a row never handed before gets its own round. A repository whose gaps
went to the architect :data:`MAX_ROUNDS` times fails the step when it holds an open gap again. The
rounds are counted from every record there is: ``answers.json`` in either of its forms (a bare
count, or the rounds with the rows) and the settled folder, which keeps each round's files.
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

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import STATUS_DONE

if TYPE_CHECKING:
    from collections.abc import Sequence
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
REVIEW_SLUG: Final = "completeness-review"
"""The name the architecture completeness review's findings are filed under among the open design gaps."""
REVIEW_SOURCE: Final = "the architecture completeness review"
"""What the filed findings of the completeness review name as their ``repository``."""
REVIEW_DESCRIPTION: Final = "Answer what the architecture completeness review found"
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


def open_file(work: Path, slug: str) -> Path:
    """Name the file one repository's open gaps are filed in.

    Returns:
        ``<slug>.json`` in the folder of the open design gaps.

    """
    return _folder(work, OPEN) / f"{slug}.json"


def gap_round(inputs: list[str], description: str = ANSWER_DESCRIPTION) -> tuple[StepPlan, ...]:
    """Plan the round that takes filed gaps to the solutions architect.

    Args:
        inputs: The steps the architect's step is handed, by id or by ref: the check before it.
        description: What the architect's step does: answer the spec stage's gaps, or the
            completeness review's findings (:data:`REVIEW_DESCRIPTION`).

    Returns:
        The architect's step, the index and the check after it, in the order they run. The
        check starts with no corrections spent, because the answer is a new design change.

    """
    answer: StepPlan = {
        "ref": ANSWER_REF,
        "description": description,
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
        write_json(open_file(run.context.work, slug), payload)
    return filed


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

    Raises:
        DesignGapError: A document holds an open gap: the gaps are filed for the solutions
            architect, one gap round is added to the Architecture container, the TRD is confirmed
            again, and the repository's spec steps alone are set back to planned.
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
    journal: Journal = run.journal()
    first: StepId
    container: StepId
    first, container = _repository_start(run, journal)
    raise DesignGapError(
        run.inputs.stage,
        first,
        tuple(evidence),
        container,
        container=run.step_named(ARCHITECTURE)["id"],
        plans=gap_round([check_writer(run)]),
        reconfirm=tuple(step["id"] for step in journal["steps"] if step.get("script") == CONFIRM_TRD),
    )


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
