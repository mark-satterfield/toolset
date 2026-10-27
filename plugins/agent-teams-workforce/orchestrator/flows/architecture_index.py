"""The script step that re-indexes the project's graph index of its architecture documents, once per pass.

The project names the command in ``$ATW_DOCS_INDEX_COMMAND``; with none, the step runs nothing. It
runs after every document of the pass is written and before the check, outside any agent session,
so no session waits on a rebuild. A pass that changed no file under the architecture root since the
last index this journal records runs nothing: the index already holds what the documents say.
A failed re-index is recorded with its output and does not fail the run: the documents stand, and
the next pass re-indexes them.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Final

from driver_surface_types import DOCS_INDEX_ENV
from step_journal_contract import KIND_VALUE, STATUS_DONE

from orchestrator.core import step_journal
from orchestrator.core.io import write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, NewStep, StepRun, file_artifact, value_artifact
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import ARCHITECTURE_FOLDER, INDEX, read_context

if TYPE_CHECKING:
    from step_journal_contract import Artifact, Step, StepPlan

    from orchestrator.core.io import JsonValue
    from orchestrator.core.tools import CommandResult

INDEX_DESCRIPTION: Final = "Re-index the graph index of the architecture documents"
INDEX_PURPOSE: Final = "The architecture agents query the documents as written, and no agent session waits on a rebuild"
INDEXED: Final = "indexed documents"
"""The artifact that holds the fingerprint of the architecture root the index was built from."""
INDEX_OUTCOME: Final = "index run"
"""The artifact that holds what the command printed and its exit status."""
INDEX_TIMEOUT: Final = 900
"""Seconds one run of the index command may take."""


def index_step(inputs: list[str]) -> NewStep:
    """Plan one index step.

    Args:
        inputs: The steps whose writes the index follows, by id or by ref.

    Returns:
        The planned step.

    """
    plan: StepPlan = {"description": INDEX_DESCRIPTION, "purpose": INDEX_PURPOSE, "script": INDEX, "inputs": inputs}
    return NewStep(plan)


def fingerprint(arch: Path) -> str:
    """Fingerprint every file under the architecture root by its path, size and modification time.

    Returns:
        The SHA-256 of the sorted file facts.

    """
    digest = hashlib.sha256()
    path: Path
    for path in sorted(entry for entry in arch.rglob("*") if entry.is_file()):
        facts = path.stat()
        digest.update(f"{path.relative_to(arch)}\0{facts.st_size}\0{facts.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def _last_indexed(run: StepRun) -> str | None:
    """Find the fingerprint the latest finished index of this journal was built from.

    Returns:
        The fingerprint the last done index step recorded, None when no index step recorded one.

    """
    found: str | None = None
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        if step.get("script") != INDEX or step["status"] != STATUS_DONE:
            continue
        held: Artifact
        for held in step["artifacts"]:
            if held["name"] == INDEXED and held["kind"] == KIND_VALUE and isinstance(held["value"], str):
                found = held["value"]
    return found


@script_step(INDEX)
def reindex(run: StepRun) -> Completion:
    """Run the project's index command when the documents changed since the last index.

    Returns:
        The fingerprint the index now holds, when the command ran and exited 0 or nothing changed;
        the command's output file whenever it ran.

    """
    command: str = os.environ.get(DOCS_INDEX_ENV, "").strip()
    if not command:
        return Completion()
    arch: Path = Path(read_context(run)["architectureRoot"])
    current: str = fingerprint(arch)
    if current == _last_indexed(run):
        return Completion(artifacts=(value_artifact(INDEXED, current),))
    outcome: dict[str, JsonValue]
    indexed: bool
    try:
        done: CommandResult = run.tools.command([command], stage=INDEX, timeout=INDEX_TIMEOUT, check=False)
        outcome = {"argv": [command], "exit": done.exit, "stdout": done.stdout, "stderr": done.stderr}
        indexed = done.exit == 0
    except StepError as exc:
        outcome = {"argv": [command], "cause": exc.cause, "evidence": list(exc.evidence)}
        indexed = False
    path: Path = run.context.work / ARCHITECTURE_FOLDER / "index" / run.step["id"] / "index.json"
    write_json(path, outcome)
    recorded: list[Artifact] = [file_artifact(INDEX_OUTCOME, path)]
    if indexed:
        recorded.append(value_artifact(INDEXED, current))
    return Completion(artifacts=tuple(recorded))


__all__ = ["INDEX_DESCRIPTION", "fingerprint", "index_step", "reindex"]
