"""Build an Epic's elaboration journal with the files an earlier form of the pipeline left for it.

The journal is the one the elaboration flow creates on a first dispatch (``outermost_steps``),
with each piece of earlier work recorded as a done step under the Architecture step and the
solutions architect's step planned after them (``architecture_earlier.carry``). The journal is
printed as JSON; with ``--journal`` it is also written to that file, which must not exist.

The pieces of earlier work are read from a JSON file: a list of objects, each with a
``description``, a ``purpose`` and ``files``, a list of objects with ``what`` (what the file is,
in plain words) and ``path``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict

from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.core import step_journal
from orchestrator.flows.architecture_earlier import EarlierWork, carry
from orchestrator.flows.architecture_files import PLUGIN, ROLE_ARCHITECT, agents_with_role
from orchestrator.flows.prd_to_spec import outermost_steps

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import BEAD_TYPE_EPIC, PIPELINE_ELABORATION, BeadId, Journal


class _File(TypedDict):
    what: str
    path: str


class _Piece(TypedDict):
    description: str
    purpose: str
    files: list[_File]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_work(path: Path) -> list[EarlierWork]:
    """Read the pieces of earlier work from their JSON file.

    Returns:
        The pieces, in file order.

    Raises:
        ValueError: The file cannot be read, is not JSON or is not a list of pieces.

    """
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
        pieces: list[_Piece] = check_type(
            decoded,
            list[_Piece],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    except (OSError, json.JSONDecodeError, TypeCheckError) as exc:
        message: str = f"the earlier work file {path} cannot be used: {exc}"
        raise ValueError(message) from exc
    return [
        EarlierWork(
            piece["description"],
            piece["purpose"],
            tuple((entry["what"], Path(entry["path"])) for entry in piece["files"]),
        )
        for piece in pieces
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def earlier_journal(bead: str, work: list[EarlierWork]) -> Journal:
    """Build the journal of an Epic whose architecture work an earlier form of the pipeline began.

    Args:
        bead: The Epic.
        work: The pieces of earlier work, in the order they were done; at least one.

    Returns:
        The journal: every outermost step planned, the earlier work done under the Architecture
        step, and the architect's step planned after it. A bead id the contract does not allow
        and work that names no file raise ``StepJournalError``.

    """
    journal: Journal = step_journal.new_journal(BeadId(bead), BEAD_TYPE_EPIC, PIPELINE_ELABORATION, outermost_steps())
    carry(journal, work, agents_with_role(PLUGIN, ROLE_ARCHITECT)[0], step_journal.timestamp())
    return journal


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main(argv: list[str] | None = None) -> int:
    """Print the journal of an Epic with its earlier work, and write it when a file is named.

    Returns:
        Zero after the journal is printed; one when the input or the journal file is refused
        (``StepJournalError`` is a ``ValueError``), with the reason on standard error.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bead", required=True, help="the Epic bead id")
    parser.add_argument("--work", required=True, type=Path, help="the JSON file that lists the earlier work")
    parser.add_argument("--journal", type=Path, help="write the journal to this file, which must not exist")
    options: argparse.Namespace = parser.parse_args(argv)
    bead: str = check_type(options.bead, str)
    destination: Path | None = check_type(options.journal, Path | None)
    try:
        journal: Journal = earlier_journal(bead, read_work(check_type(options.work, Path)))
        if destination is not None:
            step_journal.create_journal(destination, journal)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(json.dumps(journal) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
