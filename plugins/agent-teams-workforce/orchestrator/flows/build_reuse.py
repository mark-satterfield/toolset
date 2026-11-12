"""The build's reuse audit: the deterministic reuse check, then a reviewer only for what it cannot rule on.

``build:reuse-audit`` runs ``check-reuse`` (:func:`matrixreuse.check_reuse`) in process against the
matrix ids the Task states (its ``matrix_elements``) and the Story worktree. A line that does itself
what a shared capability provides, and a capability the Task must use that nothing references, are
blocking findings the check settles. A new definition whose name reads like a provided behaviour is
a definition the check cannot rule on: only then is the shared-capability-reviewer started, handed
each such definition once, in text files it can read whole. ``build:reuse-ruled`` then merges the
reviewer's rulings with what the check settled into the review, by script, and fails when a handed
definition has no ruling. With no such definition the audit step records the review itself.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from itertools import starmap
from pathlib import Path
from typing import TYPE_CHECKING, Final

from typeguard import check_type

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import EntryId, MatrixError
from matrixreuse import ReuseItem, ReuseResult, check_reuse
from matrixstore import Matrix, read_matrix

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, file_artifact, value_artifact
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import matrix_file
from orchestrator.flows.build_sessions import OutputContract, reasoned
from orchestrator.flows.build_state import CONTRACTS, artifact_document, artifact_file, new_step, workspace_of

if TYPE_CHECKING:
    from step_journal_contract import Artifact

STAGE: Final = "build:reuse-audit"
RULED_STAGE: Final = "build:reuse-ruled"
REVIEW: Final = "reuseReview"
RULINGS: Final = "reuseRulings"
"""The artifact name of the reviewer's rulings."""
HANDED: Final = "reuseHanded"
"""The artifact name of the record of what was handed to the reviewer, read by ``build:reuse-ruled``."""
REVIEWER: Final = "shared-capability-reviewer"
ELEMENTS: Final = "matrix_elements"
"""The bead field that holds the matrix ids the Task states."""
REVIEW_FILE: Final = "reuse-review.json"
HANDED_FILE: Final = "reuse-handed.json"
DEFINITIONS_STEM: Final = "reuse-definitions"
CAPABILITIES_STEM: Final = "reuse-capabilities"
CHUNK_CHARACTERS: Final = 40_000
"""The most characters one handed text file holds, so the reviewer can read each listed file whole."""
DUPLICATE: Final = "duplicate"
LISTED_UNRULED: Final = 5
"""How many definitions without a ruling the failure names."""


@dataclass(frozen=True)
class _Handed:
    """What the reviewer is handed: one entry per distinct definition, and the behaviours it is matched to."""

    definitions: list[dict[str, JsonValue]]
    behaviours: dict[str, str]


def _item_text(item: ReuseItem) -> str:
    """Describe one finding of the check: where it is, what it is, and the capability it concerns.

    Returns:
        ``<file>:<line> <finding> <feature> <provides>: <detail>``, without the place when it has none.

    """
    file: str | None = item.get("file")
    line: int | None = item.get("line")
    place: str = "" if file is None else f"{file}:{line} " if line is not None else f"{file} "
    return f"{place}{item['finding']} {item['feature']} {item['provides']}: {item['detail']}"


def _finding(item: ReuseItem) -> dict[str, JsonValue]:
    """Turn one violation of the check into a blocking build review finding owned by implementation.

    Returns:
        The finding, with the item's file and line when it has them.

    """
    finding: dict[str, JsonValue] = {"severity": "blocking", "owner": "implementation", "detail": _item_text(item)}
    if "file" in item:
        finding["file"] = item["file"]
    if "line" in item:
        finding["line"] = item["line"]
    return finding


def _review(findings: list[dict[str, JsonValue]], evidence: str) -> dict[str, JsonValue]:
    """Shape a review under ``build-review.schema.json``.

    Returns:
        The review, approved when no finding asks for a change.

    """
    listed: list[JsonValue] = [*findings]
    return {
        "approved": all(finding["severity"] == "note" for finding in findings),
        "findings": listed,
        "evidence": evidence,
    }


def _recorded(run: StepRun, document: dict[str, JsonValue]) -> tuple[Artifact, ...]:
    """Write a review beside the step and record it as a reviewer's result is recorded.

    Returns:
        The review file, then its ``approved``, ``findings`` and ``evidence`` as values.

    """
    output: Path = run.context.work / "build" / str(run.step["id"]) / REVIEW_FILE
    write_json(output, document)
    return (file_artifact(REVIEW, output), *starmap(value_artifact, document.items()))


def _unknown(matrix: Matrix, ids: list[EntryId]) -> list[EntryId]:
    """List the stated ids the matrix holds no entry for.

    Returns:
        Those ids, in the order stated.

    """
    return [entry_id for entry_id in ids if matrix.find(entry_id) is None]


def _unchecked_note(unchecked: str) -> dict[str, JsonValue]:
    """Note a relied-on behaviour whose use the check could not see.

    Returns:
        The note finding.

    """
    return {"severity": "note", "detail": f"{unchecked} carries no use signal, so its use could not be checked"}


def _checked(run: StepRun, ids: list[EntryId]) -> tuple[ReuseResult | None, list[dict[str, JsonValue]]]:
    """Run the deterministic reuse check on the ids the matrix holds.

    Returns:
        The check's result, or None when no stated id is in the matrix; and a contract finding for
        the stated ids the matrix does not hold.

    Raises:
        StepError: The check could not read the worktree.

    """
    matrix: Matrix = read_matrix(matrix_file())
    unknown: list[EntryId] = _unknown(matrix, ids)
    contract: list[dict[str, JsonValue]] = (
        [
            {
                "severity": "blocking",
                "owner": "contract",
                "detail": f"the Task's {ELEMENTS} name ids the matrix holds no entry for: {', '.join(unknown)}",
            },
        ]
        if unknown
        else []
    )
    known: list[EntryId] = [entry_id for entry_id in ids if entry_id not in unknown]
    if not known:
        return None, contract
    try:
        return check_reuse(matrix, known, workspace_of(run).tree), contract
    except MatrixError as error:
        raise StepError(STAGE, OTHER_CAUSE, (f"check-reuse could not check the worktree: {error}",)) from error


def _settled_findings(result: ReuseResult) -> list[dict[str, JsonValue]]:
    """Turn what the check settles into review findings.

    Returns:
        Each violation as a blocking finding, and each relied-on behaviour with no use signal as a note.

    """
    return [
        *(_finding(item) for item in result["violations"]),
        *(_unchecked_note(unchecked) for unchecked in result["unchecked"]),
    ]


def _check_evidence(result: ReuseResult) -> str:
    """State what the check read and found.

    Returns:
        The files read, the capabilities checked and those left out as this repository's own, and the violations.

    """
    provided: str = f" ({', '.join(result['provided'])} provided by this repository, not checked)"
    return (
        f"check-reuse read {len(result['files'])} changed file(s) against {len(result['capabilities'])} shared "
        f"capability(ies){provided if result['provided'] else ''}: {len(result['violations'])} violation(s)"
    )


def _candidate(item: ReuseItem) -> str:
    """Name the capability item a definition may duplicate.

    Returns:
        ``<feature id>#<provides id>``.

    """
    return f"{item['feature']}#{item['provides']}"


def _handed(judgment: list[ReuseItem]) -> _Handed:
    """Group the check's judgment items by definition, each definition once.

    Returns:
        One entry per distinct file and line, numbered D1, D2, ... in file and line order, with the
        definition's text and each candidate capability item with the words it shares; and each
        candidate's behaviour.

    """
    places: list[tuple[str, int]] = sorted({(item.get("file", ""), item.get("line", 0)) for item in judgment})
    numbered: dict[tuple[str, int], str] = {place: f"D{number}" for number, place in enumerate(places, start=1)}
    definitions: list[dict[str, JsonValue]] = [
        {
            "id": numbered[place],
            "file": place[0],
            "line": place[1],
            "definition": next(item.get("definition", "") for item in judgment if _place(item) == place),
            "candidates": [
                f"{_candidate(item)} (shares {', '.join(item.get('shared', []))})"
                for item in judgment
                if _place(item) == place
            ],
        }
        for place in places
    ]
    return _Handed(definitions, {_candidate(item): item.get("behaviour", "") for item in judgment})


def _place(item: ReuseItem) -> tuple[str, int]:
    """Name where a judgment item's definition is.

    Returns:
        Its file and line.

    """
    return item.get("file", ""), item.get("line", 0)


def _definition_lines(definitions: list[dict[str, JsonValue]]) -> list[str]:
    """Lay out the handed definitions as text, grouped under a heading per file.

    Returns:
        The lines: ``## <file>``, then per definition ``<id> line <n>: <definition>`` and one
        indented line per candidate.

    """
    lines: list[str] = []
    previous: JsonValue = None
    for definition in definitions:
        heading: list[str] = [] if definition["file"] == previous else [f"## {definition['file']}"]
        previous = definition["file"]
        candidates: list[str] = [
            f"    may duplicate {candidate}" for candidate in check_type(definition["candidates"], list[str])
        ]
        lines.extend([
            *heading,
            f"{definition['id']} line {definition['line']}: {definition['definition']}",
            *candidates,
        ])
    return lines


def _chunks(lines: list[str]) -> list[str]:
    """Split text lines into chunks no longer than :data:`CHUNK_CHARACTERS`.

    A file heading opens a new chunk only when its file's lines do not fit, so a chunk may hold
    the end of one file's definitions and the start of the next's.

    Returns:
        The chunks, each a newline-joined text.

    """
    chunks: list[list[str]] = [[]]
    size: int = 0
    for line in lines:
        if chunks[-1] and size + len(line) + 1 > CHUNK_CHARACTERS:
            chunks.append([])
            size = 0
        chunks[-1].append(line)
        size += len(line) + 1
    return ["\n".join(chunk) + "\n" for chunk in chunks if chunk]


def _write_chunks(folder: Path, stem: str, lines: list[str]) -> list[Path]:
    """Write text lines to as many files as keep each under :data:`CHUNK_CHARACTERS`.

    Returns:
        The files written, in order.

    """
    written: list[Path] = [folder / f"{stem}-{number}.txt" for number, _ in enumerate(_chunks(lines), start=1)]
    for path, text in zip(written, _chunks(lines), strict=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return written


def _reviewer_request(run: StepRun, handed: _Handed, settled: dict[str, JsonValue]) -> tuple[str, Path]:
    """Write the definitions to rule on, and the behaviours they are matched to, to files the reviewer reads whole.

    Args:
        run: The ``build:reuse-audit`` step.
        handed: The definitions and behaviours.
        settled: What the check settled, kept in the record for ``build:reuse-ruled``: the
            ``settled`` findings and the check's ``evidence``.

    Returns:
        The request, naming those files; and the record of what was handed, for ``build:reuse-ruled``.

    """
    folder: Path = run.context.work / "build" / str(run.step["id"])
    definition_files: list[Path] = _write_chunks(folder, DEFINITIONS_STEM, _definition_lines(handed.definitions))
    behaviour_lines: list[str] = [
        f"{candidate}: {behaviour}" for candidate, behaviour in sorted(handed.behaviours.items())
    ]
    capability_files: list[Path] = _write_chunks(folder, CAPABILITIES_STEM, behaviour_lines)
    record: Path = folder / HANDED_FILE
    write_json(record, {**settled, "definitions": [*handed.definitions]})
    named: str = ", ".join(str(path) for path in definition_files)
    behaviours: str = ", ".join(str(path) for path in capability_files)
    request: str = (
        f"Rule on each of the {len(handed.definitions)} definitions the deterministic reuse check could not rule "
        f"on, listed in {named}: each has an id (D1, D2, ...), its line in the file heading it (relative to the "
        f"work tree) and the shared capability items it may duplicate, as <feature id>#<provides id>, with the "
        f"words it shares with each. What each capability item provides is stated in {behaviours}. Read every "
        "listed file whole. Return exactly one ruling per definition id: duplicate, naming as capability the "
        "candidate it duplicates, or not-duplicate; with one sentence of reason"
    )
    return request, record


def audit(run: StepRun) -> Completion:
    """Check the changed files against the Task's shared capabilities; start the reviewer only when needed.

    Args:
        run: The ``build:reuse-audit`` step.

    Returns:
        The review the step recorded, or the reviewer's session and the step that merges its
        rulings; then the consumer of the review.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    ids: list[EntryId] = [EntryId(entry_id) for entry_id in check_type(bead.get(ELEMENTS, []), list[str])]
    consumer = new_step(
        "build:audit-reviewed",
        "Resolve the shared-capability review",
        {"review": REVIEW, "again": STAGE},
    )
    result: ReuseResult | None = None
    contract: list[dict[str, JsonValue]] = []
    if ids:
        result, contract = _checked(run, ids)
    if result is not None and result["judgment"]:
        request: str
        record: Path
        settled: list[JsonValue] = [*contract, *_settled_findings(result)]
        request, record = _reviewer_request(
            run,
            _handed(result["judgment"]),
            {"settled": settled, "evidence": _check_evidence(result)},
        )
        started: Completion = reasoned(
            run,
            REVIEWER,
            OutputContract(CONTRACTS / "build-reuse-rulings.schema.json", RULINGS),
            request,
            followups=(new_step(RULED_STAGE, "Merge the reviewer's rulings with what the check settled"), consumer),
        )
        return Completion(artifacts=(*started.artifacts, file_artifact(HANDED, record)), add=started.add)
    document: dict[str, JsonValue] = (
        _review(
            [*contract, *_settled_findings(result)],
            f"{_check_evidence(result)}, no definition left for a reviewer to rule on",
        )
        if result is not None
        else _review(contract, f"the Task states no matrix id the reuse check can use: {ids}")
    )
    return Completion(artifacts=_recorded(run, document), add=(StepGroup((consumer,)),))


def _read_record(path: Path) -> dict[str, JsonValue]:
    """Read the record of what was handed to the reviewer.

    Returns:
        Its object.

    """
    return json_object(json.loads(path.read_text(encoding="utf-8")))


def _ruled_finding(definition: dict[str, JsonValue], ruling: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Turn a duplicate ruling into a blocking finding owned by implementation.

    Returns:
        The finding, at the definition's file and line.

    """
    capability: JsonValue = ruling.get("capability") or ", ".join(check_type(definition["candidates"], list[str]))
    return {
        "severity": "blocking",
        "owner": "implementation",
        "file": definition["file"],
        "line": definition["line"],
        "detail": (
            f"{definition['file']}:{definition['line']} duplicates {capability}: {definition['definition']} "
            f"({ruling['reason']})"
        ),
    }


def ruled(run: StepRun) -> Completion:
    """Merge the reviewer's rulings with what the check settled into the review.

    Args:
        run: The ``build:reuse-ruled`` step.

    Returns:
        The review: the settled findings, then a blocking finding per definition ruled a duplicate.

    Raises:
        StepError: The reviewer returned no ruling on a handed definition.

    """
    handed: dict[str, JsonValue] = _read_record(artifact_file(run, HANDED))
    definitions: list[dict[str, JsonValue]] = [
        json_object(definition) for definition in check_type(handed["definitions"], list[JsonValue])
    ]
    rulings: dict[str, dict[str, JsonValue]] = {
        check_type(ruling["definition"], str): ruling
        for ruling in (
            json_object(ruling) for ruling in check_type(artifact_document(run, RULINGS)["rulings"], list[JsonValue])
        )
    }
    unruled: list[dict[str, JsonValue]] = [
        definition for definition in definitions if check_type(definition["id"], str) not in rulings
    ]
    if unruled:
        named: str = "; ".join(
            f"{definition['id']} {definition['file']}:{definition['line']}" for definition in unruled[:LISTED_UNRULED]
        )
        raise StepError(
            RULED_STAGE,
            OTHER_CAUSE,
            (f"{REVIEWER} returned no ruling on {len(unruled)} definition(s): {named}",),
        )
    duplicates: list[dict[str, JsonValue]] = [
        _ruled_finding(definition, rulings[check_type(definition["id"], str)])
        for definition in definitions
        if rulings[check_type(definition["id"], str)]["ruling"] == DUPLICATE
    ]
    settled: list[dict[str, JsonValue]] = [
        json_object(finding) for finding in check_type(handed["settled"], list[JsonValue])
    ]
    evidence: str = (
        f"{handed['evidence']}; {REVIEWER} ruled {len(definitions)} definition(s), {len(duplicates)} duplicate(s)"
    )
    return Completion(artifacts=_recorded(run, _review([*settled, *duplicates], evidence)))
