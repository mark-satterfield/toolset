"""A spec author's own run of the scripted checks its documents must pass, before it hands them over.

``atw-spec-check --context <repository context> <document>=<path> ...``, where ``<document>`` is
``spec`` (the contracts), ``data-model`` or ``criteria``, runs on each named file the same check the
step runs when the author hands the documents over (:func:`spec_authoring.document_checker`): the
citations against the matrix (``ATW_MATRIX`` or the control repository's) and the architecture root
(``ATW_ARCH_PATH``), the criteria document's structure, and ``usedAsBuilt`` against the context's
``addition`` entries. It prints one JSON object, ``{"ok": ..., "problems": [...]}``, and exits 1
when a document fails.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.core import portfolio_bootstrap  # ruff: ignore[unused-import] - Install shared contract paths.

# isort: split
from driver_surface_types import ARCH_PATH_ENV
from matrixstore import Matrix, matrix_path, read_matrix

from orchestrator.core.agents import CONTENT_FAILURES
from orchestrator.flows.elaboration_files import CRITERIA, DATA_MODEL, SPEC
from orchestrator.flows.spec_authoring import addition_entries, document_checker

if TYPE_CHECKING:
    from collections.abc import Sequence

    from orchestrator.core.models import OutputValidator

DOCUMENTS: Final[dict[str, str]] = {"spec": SPEC, "data-model": DATA_MODEL, "criteria": CRITERIA}
"""The document names the command takes, each with its artifact name."""


def _named(value: str) -> tuple[str, Path]:
    """Parse one ``<document>=<path>`` argument.

    Returns:
        The artifact name and the file.

    Raises:
        argparse.ArgumentTypeError: The document is not one the command checks.

    """
    document, _, path = value.partition("=")
    if document not in DOCUMENTS or not path:
        message: str = f"expected <document>=<path> with <document> one of {', '.join(DOCUMENTS)}: {value!r}"
        raise argparse.ArgumentTypeError(message)
    return DOCUMENTS[document], Path(path).resolve()


def problems(context: Path | None, documents: Sequence[tuple[str, Path]]) -> list[str]:
    """Run the check of each document and collect what fails.

    Args:
        context: The repository context file, or None.
        documents: Each document's artifact name and file.

    Returns:
        Every problem, each naming its file; empty when every document passes.

    Raises:
        ValueError: A contracts or data-model document is named and ``ATW_ARCH_PATH`` is not set.

    """
    additions: set[str] | None = None if context is None else addition_entries(context)
    cited: bool = any(name != CRITERIA for name, _ in documents)
    arch_value: str = os.environ.get(ARCH_PATH_ENV, "")
    if cited and not arch_value:
        message: str = f"{ARCH_PATH_ENV} names no architecture root"
        raise ValueError(message)
    matrix: Matrix | None = read_matrix(matrix_path(None, os.environ)) if cited else None
    found: list[str] = []
    for name, path in documents:
        check: OutputValidator = document_checker(name, additions, matrix, Path(arch_value))
        try:
            check(path)
        except CONTENT_FAILURES as failed:
            found.append(f"{path}: {failed}")
    return found


def main(argv: Sequence[str] | None = None) -> int:
    """Check the named spec documents and print the result.

    Returns:
        0 when every document passes, 1 otherwise.

    """
    parser = argparse.ArgumentParser(prog="atw-spec-check", description=__doc__.splitlines()[0])
    parser.add_argument("--context", type=Path, help="the repository context file (spec-<slug>.context.json)")
    parser.add_argument("documents", nargs="+", type=_named, help="<document>=<path>")
    args: argparse.Namespace = parser.parse_args(argv)
    found: list[str] = problems(args.context, args.documents)
    sys.stdout.write(json.dumps({"ok": not found, "problems": found}) + "\n")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
