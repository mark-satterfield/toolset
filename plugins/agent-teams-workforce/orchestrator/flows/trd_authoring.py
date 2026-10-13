"""Confirm the Epic's TRD: verify its architecture citations and mark it on the Epic bead.

The solutions architect has the TRD drafted and updated in place, and it is reviewed with the
architecture. This step starts no session. It reads the TRD at the path the open-run step chose
and recorded in the context file, checks that every source it cites resolves, and records its
path and digest on the Epic bead.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

# The driver surface is defined once, in the pipeline-contracts skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
import beadgraph
import beads_contract
import yaml
from bead_metadata import KEY_ARTIFACT_TRD_PATH, KEY_ARTIFACT_TRD_SHA256
from driver_surface_types import CONTROL_REPO_ENV
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.handback_contract import TRD_PHASE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, StepRun, file_artifact, value_artifact
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.architecture_files import (
    ARTIFACT_TRD,
    CONFIRM_TRD,
    ArchitectureContext,
    ArchitectureStepError,
    read_context,
)
from orchestrator.flows.elaboration_support import TRD_AUTHORING_PHASE, enter_phase

if TYPE_CHECKING:
    from orchestrator.core.models import RunContext

_ARGUMENT_ERROR: str = "Arguments violate the trd_authoring input contract"
TRD_HASH: Final = "TRD hash on the Epic bead"
TRD_WARNINGS: Final = "TRD warnings"


class DocumentValidationError(ValueError):
    """An authored document fails its content contract."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def document(path: Path, arch: Path) -> tuple[list[str], list[str]]:
    """Validate document frontmatter and resolve architecture citations.

    Returns:
        The validated document result.

    Raises:
        TypeError: An argument violates the declared input contract.
        DocumentValidationError: Frontmatter or architecture citations are invalid.

    """
    relative: str
    candidates: tuple[Path, Path]
    entry: str
    if not (isinstance(path, Path)) or not (isinstance(arch, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    arch = arch.resolve()
    text: str = path.read_text(encoding="utf-8")
    if not text.strip():
        message: str = f"missing or empty document: {path}"
        raise DocumentValidationError(message)
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        message = f"{path}: YAML frontmatter is missing"
        raise DocumentValidationError(message)
    try:
        raw_front: object = yaml.safe_load(text[4:].split("\n---", 1)[0]) or {}
    except yaml.YAMLError as exc:
        message = f"{path}: invalid YAML frontmatter: {exc}"
        raise DocumentValidationError(message) from exc
    if not isinstance(raw_front, dict):
        message = f"{path}: frontmatter must be an object"
        raise DocumentValidationError(message)
    front: dict[str, JsonValue] = json_object(raw_front)
    raw_ids: JsonValue = front.get("decisionIds", [])
    if not isinstance(raw_ids, list) or any(not isinstance(item, str) for item in raw_ids):
        message = f"{path}: decisionIds must be a list of strings"
        raise DocumentValidationError(message)
    ids: list[str] = check_type(raw_ids, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    unresolved: list[str] = []
    for entry in ids:
        relative = entry.split("#", 1)[0]
        candidates = (
            (arch / relative).resolve(),
            (arch / "arc42" / relative).resolve(),
        )
        if (
            not relative
            or Path(relative).is_absolute()
            or not any(candidate.is_relative_to(arch) and candidate.is_file() for candidate in candidates)
        ):
            unresolved.append(entry)
    if unresolved:
        message = f"unresolved decisionIds: {unresolved}"
        raise DocumentValidationError(message)
    warnings: list[str] = [] if ids else ["decisionIds is absent or empty"]
    return ids, warnings


def _mark_trd(context: RunContext, tools: Tools, output: Path) -> str:
    """Record the TRD's path and digest on the Epic bead, unless the bead already holds them.

    Returns:
        The SHA-256 digest of the TRD.

    """
    digest: str = hashlib.sha256(output.read_bytes()).hexdigest()
    relative: str = str(output.resolve().relative_to(env_path("SKILLSPOKE_ROOT")))
    control: Path = env_path(CONTROL_REPO_ENV)

    def mark() -> None:
        raw: object = json.loads(tools.bd(["show", context.bead, "--json"], stage=TRD_PHASE))
        bead: dict[str, JsonValue] = json_object(raw[0] if isinstance(raw, list) else raw)
        metadata: dict[str, JsonValue] = json_object(beads_contract.metadata_of(bead))
        pairs: dict[str, str] = {
            KEY_ARTIFACT_TRD_PATH: relative,
            KEY_ARTIFACT_TRD_SHA256: digest,
        }
        if all(metadata.get(key) == value for key, value in pairs.items()):
            return
        tools.portfolio(TRD_PHASE, beadgraph.write_metadata, context.bead, pairs, control)

    tools.operation(TRD_PHASE, mark)
    return digest


@script_step(CONFIRM_TRD)
def confirm(run: StepRun) -> Completion:
    """Confirm the reviewed TRD: every source it cites resolves, and the Epic bead carries it.

    Returns:
        The TRD file and the digest recorded on the Epic bead.

    Raises:
        ArchitectureStepError: The TRD is missing, or its front matter or a citation is invalid.

    """
    enter_phase(run.context, run.agents.emit, TRD_AUTHORING_PHASE, CONFIRM_TRD)
    context: ArchitectureContext = read_context(run)
    trd: Path = Path(context["trdPath"])
    try:
        warnings: list[str] = document(trd, Path(context["architectureRoot"]))[1]
    except (OSError, UnicodeError, DocumentValidationError) as exc:
        raise ArchitectureStepError(run, f"{trd}: {exc}") from None
    digest: str = _mark_trd(run.context, run.tools, trd)
    warned: list[JsonValue] = list(warnings)
    return Completion(
        artifacts=(
            file_artifact(ARTIFACT_TRD, trd),
            value_artifact(TRD_HASH, digest),
            *((value_artifact(TRD_WARNINGS, warned),) if warned else ()),
        ),
    )
