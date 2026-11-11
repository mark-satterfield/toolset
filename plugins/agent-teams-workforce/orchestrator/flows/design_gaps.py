"""Open design gaps in a repository's specification documents, and their way back to the solutions architect.

A spec author designs nothing: a detail its Story needs that no approved document states is a gap
in the design, recorded as one row of the table under the heading :data:`HEADING` of the document
that needs it, and settled by nobody in the spec stage. No Story is written and no Task is
decomposed from a document that holds an open gap. The step after the review
(``spec_authoring.story_document``) reads every row (:func:`open_gaps`); when one is left it files
the repository's gaps under the architecture work folder (:func:`file_gaps`) and sets the
solutions architect's last result step and every step after it back to planned
(``DesignGapError``, the journal runner's way back to an earlier step): the architect's next
session is handed every repository's open gaps (:func:`handed`) and designs what fills them, the
architecture maintainer writes the decisions into the documents, which are promoted, and the specs
are written again against the settled design. The architect's accepted result moves the gaps it
was handed to the settled folder and counts one answer for each repository (:func:`settle`).
A repository whose documents still hold an open gap after :data:`MAX_ANSWERS` answers fails the
step: the gaps do not converge.
"""

from __future__ import annotations

import json
import re
import shutil
from typing import TYPE_CHECKING, Final

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import DesignGapError, StepError
from orchestrator.flows.architecture_files import ARCHITECT, LABEL_RESULT, architecture_folder

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import STATUS_DONE

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from step_journal_contract import Step, StepId

    from orchestrator.core.journal_steps import StepRun

HEADING: Final = "Design gaps"
"""The heading, at level 2, of the one section of a spec document that records its open design gaps."""
LABEL_GAPS: Final = "design gaps"
"""The label the solutions architect is handed each repository's open design gaps under."""
FOLDER: Final = "design-gaps"
OPEN: Final = "open"
SETTLED: Final = "settled"
ANSWERS: Final = "answers.json"
"""The file, in the design gaps folder, that counts the architect's answers to each repository's gaps."""
MAX_ANSWERS: Final = 2
"""The number of the architect's answers a repository's open gaps may survive before the step fails."""
_SECTION: Final = re.compile(rf"^##\s+{re.escape(HEADING)}\s*$", re.IGNORECASE)
_NEXT_SECTION: Final = re.compile(r"^#{1,2}\s")
_SEPARATOR: Final = re.compile(r"^\|[\s:|-]*\|$")
_LIST_ITEM: Final = re.compile(r"^(?:[-*+]|\d+[.)])\s+\S")


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


def architect_writer(run: StepRun) -> StepId:
    """Find the solutions architect's step that wrote its result last.

    Returns:
        The last done step of the architect, in walk order, that recorded the architecture result.

    Raises:
        ValueError: The journal holds no such step.

    """
    found: StepId | None = None
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        if (
            step.get("agent") == ARCHITECT
            and step["status"] == STATUS_DONE
            and any(held["name"] == LABEL_RESULT for held in step["artifacts"])
        ):
            found = step["id"]
    if found is None:
        message: str = "the journal holds no step of the solutions architect that recorded its result"
        raise ValueError(message)
    return found


def file_gaps(run: StepRun, slug: str, repository: str, documents: Sequence[Path]) -> list[str]:
    """Read the open gaps of a repository's spec documents and, when there are any, file them for the architect.

    Returns:
        Each gap as ``<document>: <row>``; empty, and nothing filed, when no document holds one.

    """
    rows: list[dict[str, JsonValue]] = []
    evidence: list[str] = []
    path: Path
    for path in documents:
        gaps: list[str] = open_gaps(path)
        if gaps:
            rows.append({"document": str(path), "gaps": list(gaps)})
            evidence.extend(f"{path}: {gap}" for gap in gaps)
    if rows:
        write_json(
            _folder(run.context.work, OPEN) / f"{slug}.json",
            {"repository": repository, "documents": rows},
        )
    return evidence


def _answers_file(work: Path) -> Path:
    """Name the file that counts the architect's answers to each repository's gaps.

    Returns:
        The file in the design gaps folder.

    """
    return architecture_folder(work) / FOLDER / ANSWERS


def answers(work: Path) -> dict[str, int]:
    """Read how many times the architect answered each repository's open design gaps.

    Returns:
        The count of each repository's slug; empty when no answer was counted.

    """
    path: Path = _answers_file(work)
    if not path.is_file():
        return {}
    counted: dict[str, JsonValue] = json_object(json.loads(path.read_text(encoding="utf-8")))
    return {slug: value for slug, value in counted.items() if isinstance(value, int)}


def hold_open(run: StepRun, slug: str, repository: str, documents: Sequence[Path]) -> None:
    """Stop a repository whose spec documents hold an open design gap from reaching its Story and Tasks.

    Raises:
        DesignGapError: A document holds an open gap: the gaps are filed for the solutions
            architect, and its last result step and every step after it are set back to planned.
        StepError: A document holds an open gap after the architect answered the repository's
            gaps :data:`MAX_ANSWERS` times; the gaps are filed and the step fails.

    """
    evidence: list[str] = file_gaps(run, slug, repository, documents)
    if not evidence:
        return
    answered: int = answers(run.context.work).get(slug, 0)
    if answered >= MAX_ANSWERS:
        cause: str = (
            f"the spec documents of {repository} still hold open design gaps after the solutions architect "
            f"answered that repository's design gaps {answered} times; the design does not converge"
        )
        raise StepError(run.inputs.stage, OTHER_CAUSE, (cause, *evidence))
    raise DesignGapError(run.inputs.stage, architect_writer(run), tuple(evidence))


def handed(work: Path) -> tuple[tuple[str, Path], ...]:
    """Name each repository's open design gaps, filed for the solutions architect's next session.

    Returns:
        Each filed file under the label :data:`LABEL_GAPS`, in name order.

    """
    folder: Path = _folder(work, OPEN)
    if not folder.is_dir():
        return ()
    return tuple((LABEL_GAPS, path) for path in sorted(folder.glob("*.json")))


def settle(work: Path, step: StepId) -> None:
    """Move the open design gaps an accepted architect result was handed to the settled folder, under its step.

    Each repository whose gaps were moved is counted one more answer of the architect
    (:func:`answers`).
    """
    folder: Path = _folder(work, OPEN)
    if not folder.is_dir():
        return
    target: Path = _folder(work, SETTLED) / step
    target.mkdir(parents=True, exist_ok=True)
    counted: dict[str, int] = answers(work)
    path: Path
    for path in sorted(folder.glob("*.json")):
        counted[path.stem] = counted.get(path.stem, 0) + 1
        shutil.move(str(path), target / path.name)
    write_json(_answers_file(work), dict(sorted(counted.items())))
