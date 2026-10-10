"""Author one TRD, verify its architecture citations and mark the Epic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import beadgraph
import yaml
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner, strict_json
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext, StepError
from orchestrator.core.tools import Tools, env_path

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
        StepError: The PRD path or architecture target is missing.

    """
    args: dict[str, JsonValue]
    work: Path
    prd_value: int | float | str | list[JsonValue] | dict[str, JsonValue] | None
    target: int | float | str | list[JsonValue] | dict[str, JsonValue] | None
    prd: Path
    arch: Path
    if (
        not (isinstance(context, RunContext))
        or not (isinstance(store, ArtifactStore))
        or not (isinstance(runner, AgentRunner))
        or not (isinstance(tools, Tools))
    ):
        raise TypeError(_ARGUMENT_ERROR)
    stage: str = "input"
    args, work = context.args, context.work
    context.stage = "trd-authoring"
    prd_value, target = json_object(args.get("prd", {})).get("path"), args.get("targetDir")
    if not prd_value or not target:
        raise StepError(stage, "other", ("PRD path and targetDir are required",))
    prd, arch = Path(check_type(prd_value, str)).resolve(), Path(check_type(args["archPath"], str)).resolve()
    inputs: tuple[str, ...] = _trd_inputs(prd, arch, check_type(target, str), work)
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
                "architectureChange": args.get("architectureChange"),
                "targetDir": target,
                "deltaDir": args.get("deltaDir"),
                "note": args.get("note"),
                "filingPath": args.get("trdPath"),
            },
        )
        write_json(feedback, {"errors": errors})
        runner.run(
            AgentStep(
                stage="trd",
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
    store.accept("trd", inputs, (output,))
    _mark_trd(context, tools, output)
    return json_object({
        "ok": True,
        "trdPath": str(output),
        "filingPath": args.get("trdPath"),
        "decisionIds": ids,
        "warnings": warnings,
    })


def _mark_trd(context: RunContext, tools: Tools, output: Path) -> None:
    digest: str = hashlib.sha256(output.read_bytes()).hexdigest()
    relative: str = str(output.resolve().relative_to(env_path("SKILLSPOKE_ROOT")))
    control: Path = env_path("ATW_CONTROL_REPO")

    def mark() -> None:
        raw: object = json.loads(tools.bd(["show", context.bead, "--json"], stage="trd"))
        bead: dict[str, JsonValue] = json_object(raw[0] if isinstance(raw, list) else raw)
        metadata: int | float | str | list[JsonValue] | dict[str, JsonValue] = bead.get("metadata") or {}
        if isinstance(metadata, str):
            decoded: object = json.loads(metadata)
            metadata = json_object(decoded)
        pairs: dict[str, str] = {"artifact_trd_path": relative, "artifact_trd_sha256": digest}
        if all(json_object(metadata).get(key) == value for key, value in pairs.items()):
            return
        tools.portfolio("trd", beadgraph.write_metadata, context.bead, pairs, control)

    tools.operation("trd", mark)


def _trd_inputs(prd: Path, arch: Path, target: str, work: Path) -> tuple[str, ...]:
    item_path: Path = work / "delta-items.json"
    elements: list[str] = sorted({
        check_type(item["element"], str)
        for item in check_type(
            strict_json(item_path)["items"],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    })
    return (
        *map(
            str,
            (
                prd,
                item_path,
                work / "architecture/decision.md",
                work / "architecture/target.json",
                work / "architecture/architecture-update.json",
                work / "architecture/survey.json",
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
