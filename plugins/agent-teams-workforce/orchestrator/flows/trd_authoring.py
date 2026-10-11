"""Author one TRD, verify its architecture citations and mark the Epic."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# The driver surface and the target report are each defined once, in a plugin skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import beadgraph
import beads_contract
import yaml
from bead_metadata import KEY_ARTIFACT_TRD_PATH, KEY_ARTIFACT_TRD_SHA256
from driver_surface_types import CONTROL_REPO_ENV
from target_contract import (
    ARCHITECTURE_WORK_FOLDER,
    DELTA_ITEMS_FILE,
    KEY_ARCHITECTURE_CHANGE,
    KEY_DELTA_DIR,
    KEY_ELEMENT,
    KEY_ITEMS,
    KEY_NOTE,
    KEY_TARGET_DIR,
    TARGET_REPORT_FILE,
    DeltaResult,
    load_delta_report,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE, TRD_PHASE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext, StepError
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.architecture_support import TRD_AUTHORING_PHASE

if TYPE_CHECKING:
    from collections.abc import Mapping

_ARGUMENT_ERROR: str = "Arguments violate the trd_authoring input contract"


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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run(
    context: RunContext,
    store: ArtifactStore,
    runner: AgentRunner,
    tools: Tools,
) -> dict[str, JsonValue]:
    """Produce the TRD and mark its accepted digest on the Epic.

    Returns:
        The validated document result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    args: dict[str, JsonValue]
    work: Path
    prd: Path
    arch: Path
    target: str
    filing: JsonValue
    if (
        not (isinstance(context, RunContext))
        or not (isinstance(store, ArtifactStore))
        or not (isinstance(runner, AgentRunner))
        or not (isinstance(tools, Tools))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    args, work = context.args, context.work
    context.stage = TRD_AUTHORING_PHASE
    prd, arch, target, filing = _locate(args)
    inputs: tuple[str, ...] = _trd_inputs(prd, arch, target, work)
    output: Path = work / "trd.md"
    reused: bool = store.reusable(inputs, (output,))
    facts: Path = work / "trd.context.json"
    feedback: Path = work / "trd.feedback.json"
    ids: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    if reused:
        try:
            ids, warnings = document(output, arch)
        except (ValueError, OSError, UnicodeError) as exc:
            reused = False
            errors = [str(exc)]
    if not reused:
        store.invalidate((output,))
        write_json(
            facts,
            {
                KEY_ARCHITECTURE_CHANGE: args.get(KEY_ARCHITECTURE_CHANGE),
                KEY_TARGET_DIR: target,
                KEY_DELTA_DIR: args.get(KEY_DELTA_DIR),
                KEY_NOTE: args.get(KEY_NOTE),
                "filingPath": filing,
            },
        )
        write_json(feedback, {"errors": errors})
        runner.run(
            AgentStep(
                stage=TRD_PHASE,
                agent="trd-author",
                inputs=(*inputs, str(facts), str(feedback)),
                output=output,
                final=None,
                validate=lambda path: document(path, arch),
                outcome="Technical requirements document with architecture citations.",
                model="fable",
                effort="medium",
                add_dirs=(work, arch, prd.parent),
                corrective=not bool(errors),
            ),
        )
        ids, warnings = document(output, arch)
    store.accept(TRD_PHASE, inputs, (output,))
    _mark_trd(context, tools, output)
    return json_object({
        "ok": True,
        "trdPath": str(output),
        "filingPath": filing,
        "decisionIds": ids,
        "warnings": warnings,
    })


def _locate(args: Mapping[str, JsonValue]) -> tuple[Path, Path, str, JsonValue]:
    """Read the PRD, architecture root, target folder and filing path from the run arguments.

    Returns:
        The PRD path, the architecture root, the target folder and the TRD filing path.

    Raises:
        StepError: The PRD path or the target folder is missing.

    """
    dispatch: DispatchArguments = dispatch_arguments()
    prd_value: JsonValue = json_object(args.get(dispatch.KEY_PRD, {})).get(dispatch.PRD_PATH)
    target: JsonValue = args.get(KEY_TARGET_DIR)
    if not prd_value or not target:
        stage: str = "input"
        raise StepError(stage, OTHER_CAUSE, (f"PRD path and {KEY_TARGET_DIR} are required",))
    prd: Path = Path(check_type(prd_value, str)).resolve()
    arch: Path = Path(check_type(args[dispatch.KEY_ARCH_PATH], str)).resolve()
    return prd, arch, check_type(target, str), args.get(dispatch.KEY_TRD_PATH)


def _mark_trd(context: RunContext, tools: Tools, output: Path) -> None:
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


def _trd_inputs(prd: Path, arch: Path, target: str, work: Path) -> tuple[str, ...]:
    item_path: Path = work / DELTA_ITEMS_FILE
    report: DeltaResult = load_delta_report(item_path)
    if KEY_ITEMS not in report:
        stage: str = "input"
        raise StepError(stage, OTHER_CAUSE, (f"{item_path} has no {KEY_ITEMS}",))
    elements: list[str] = sorted({item[KEY_ELEMENT] for item in report[KEY_ITEMS]})
    return (
        *map(
            str,
            (
                prd,
                item_path,
                work / ARCHITECTURE_WORK_FOLDER / "decision.md",
                work / TARGET_REPORT_FILE,
                work / ARCHITECTURE_WORK_FOLDER / "architecture-update.json",
                work / ARCHITECTURE_WORK_FOLDER / "survey.json",
                target,
                arch / "arc42/02-architecture-constraints",
            ),
        ),
        "arch-views:"
        + json.dumps(
            {"dir": str(arch / "arc42"), "elements": elements},
            sort_keys=True,
        ),
    )
