"""Post-integration completion receipts and survey generation retirement."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Final, TypedDict

# The survey and target contracts are generated into the artifact-handoff skill, their one definitions.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import archclosure
import archevidence
import archrevision
import archstate
from contracts import SurveySeal, read_survey_seal, survey_seal_path
from survey_contract import SURVEY_FILE
from target_contract import (
    CLOSURE_FILE,
    CLOSURE_ROOTS_FILE,
    KEY_DELTA_DIR,
    KEY_ITEMS,
    KEY_TARGET_DIR,
    KEY_TARGET_HASHES,
    TARGET_REPORT_NAME,
    DeltaResult,
    TargetResult,
    load_delta_report,
    load_target_report,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.handback_contract import InvalidatedNote, ReusedNote, invalidated_note, reused_note
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.matrix import element_id
from orchestrator.flows.architecture_projection import project
from orchestrator.flows.architecture_support import Architecture, read, value_input
from orchestrator.flows.elaboration_support import emit_event

ARCHITECTURE_RESULT_FILE: Final = "architecture-result.json"
ARCHITECTURE_APPROVED_FILE: Final = "architecture-approved.json"
KEY_APPROVAL_TARGET: Final = "target"
KEY_APPROVAL_DECISION: Final = "decision"
KEY_APPROVAL_SUBJECT: Final = "subject"
RESULT_KEY_OK: Final = "ok"
RESULT_KEY_SUBJECT: Final = "subject"
RESULT_KEY_TARGET_DIR: Final = "targetDir"


def result_target_dir(result: dict[str, JsonValue]) -> str:
    """Read the target directory an architecture-result.json record names.

    Returns:
        The target directory path.

    Raises:
        TypeError: The record is not an object or its target directory is not a non-empty string.

    """
    if not isinstance(result, dict):
        argument_error: str = "result_target_dir: the architecture result is not a JSON object"
        raise TypeError(argument_error)
    target_dir: JsonValue = result.get(RESULT_KEY_TARGET_DIR)
    if not isinstance(target_dir, str) or not target_dir:
        target_error: str = f"result_target_dir: the architecture result's {RESULT_KEY_TARGET_DIR} is not a path"
        raise TypeError(target_error)
    return target_dir


class ApprovalRecord(TypedDict):
    """The architecture-approved.json record save_approval writes and approved reads."""

    target: dict[str, JsonValue]
    decision: dict[str, JsonValue]
    subject: str


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_approval(value: dict[str, JsonValue]) -> ApprovalRecord:
    """Validate an architecture-approved.json record.

    Returns:
        The typed approval record.

    Raises:
        TypeError: The record is not an object or a field has the wrong type.
        ValueError: A required field is missing.

    """
    if not isinstance(value, dict):
        argument_error: str = "parse_approval: the approval record is not a JSON object"
        raise TypeError(argument_error)
    missing: list[str] = [
        key for key in (KEY_APPROVAL_TARGET, KEY_APPROVAL_DECISION, KEY_APPROVAL_SUBJECT) if key not in value
    ]
    if missing:
        missing_error: str = f"parse_approval: the approval record lacks {', '.join(missing)}"
        raise ValueError(missing_error)
    subject: JsonValue = value[KEY_APPROVAL_SUBJECT]
    if not isinstance(subject, str):
        subject_error: str = "parse_approval: the approval subject is not a string"
        raise TypeError(subject_error)
    return {
        KEY_APPROVAL_TARGET: json_object(value[KEY_APPROVAL_TARGET]),
        KEY_APPROVAL_DECISION: json_object(value[KEY_APPROVAL_DECISION]),
        KEY_APPROVAL_SUBJECT: subject,
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def completion_inputs(flow: Architecture, result: dict[str, JsonValue]) -> tuple[str, ...]:
    # Capture canonical views after integration, not the survey's pre-integration seal.
    # Matrix rows deliberately remain Closure's separate, deterministic dependency.
    """Completion inputs.

    Returns:
        The validated architecture artifact result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    element: dict[str, JsonValue]
    view: str
    if not (isinstance(flow, Architecture)) or not (isinstance(result, dict)):
        argument_error: str = "completion_inputs: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    paths: list[Path] = [
        flow.prd,
        flow.arch / "reference/architecture-documentation-model.md",
        flow.arch / "reference/diagram-and-model-types.md",
        flow.arch / "arc42/02-architecture-constraints",
        flow.schemas,
        flow.context_path,
        flow.work / "draft",
        flow.work / SURVEY_FILE,
        flow.work / "decision.json",
        flow.work / TARGET_REPORT_NAME,
        flow.work / "architecture-update.json",
        flow.work / "closure-walk.json",
        flow.work / CLOSURE_ROOTS_FILE,
        Path(result_target_dir(result)),
    ]
    revision: dict[str, JsonValue] = read(flow.work / "arc42-revision.json")
    paths.extend(flow.arch / "arc42" / name for name in json_object(revision.get("views", {})))
    for element in check_type(
        read(flow.work / "closure-walk.json").get("elements", []),
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        for view in check_type(
            element.get("views", []),
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ):
            path: Path = Path(view)
            if not path.is_absolute():
                path = flow.arch / path if path.parts[0] == "arc42" else flow.arch / "arc42" / path
            paths.append(path)
    warnings: list[str] = []
    seal: SurveySeal | None = read_survey_seal(survey_seal_path(flow.work / SURVEY_FILE), warnings)
    if seal is not None:
        paths.extend(Path(path) for path in seal["inputs"])
    return (*tuple(sorted(set(map(str, paths)))), value_input("cited-sources", archevidence.source_binding(flow.work)))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def save_completion(flow: Architecture, result: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Save completion.

    Returns:
        The validated architecture artifact result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)) or not (isinstance(result, dict)):
        argument_error: str = "save_completion: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    path: Path = flow.work / ARCHITECTURE_RESULT_FILE
    write_json(path, result)
    flow.store.accept("architecture:complete", completion_inputs(flow, result), (path,))
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def completed(flow: Architecture) -> dict[str, JsonValue] | None:
    """Completed.

    Returns:
        The validated architecture artifact result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)):
        argument_error: str = "completed: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    path: Path = flow.work / ARCHITECTURE_RESULT_FILE
    result: dict[str, JsonValue] = read(path)
    target_dir: JsonValue = result.get(RESULT_KEY_TARGET_DIR)
    if result.get(RESULT_KEY_OK) is not True or not isinstance(target_dir, str) or not target_dir:
        return None
    if archevidence.source_binding(flow.work)["errors"]:
        return None
    if not flow.store.reusable(completion_inputs(flow, result), (path,)):
        return None
    flow.subject = check_type(result[RESULT_KEY_SUBJECT], str)
    note: ReusedNote = reused_note(step="architecture:complete")
    emit_event(flow.runner.emit, note)
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def retire_generation(flow: Architecture) -> None:
    """Retain evidence but remove every downstream result of a stale survey.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    path: Path
    if not (isinstance(flow, Architecture)):
        argument_error: str = "retire_generation: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    destination: Path = flow.work.parent / f"stale-survey-{time.time_ns()}" / "architecture"
    destination.mkdir(parents=True)
    for path in tuple(flow.work.iterdir()):
        path.rename(destination / path.name)
    note: InvalidatedNote = invalidated_note(step="architecture:survey", path=str(destination))
    emit_event(flow.runner.emit, note)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def refresh_closure(flow: Architecture, result: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Reclassify the accepted future-set walk without another session.

    Returns:
        The completed architecture result with refreshed closure evidence.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)) or not (isinstance(result, dict)):
        argument_error: str = "refresh_closure: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    walk_path: Path = flow.work / "closure-walk.json"
    walk: dict[str, JsonValue] = read(walk_path)
    target: TargetResult = load_target_report(flow.work / TARGET_REPORT_NAME)
    delta_dir: str = target[KEY_DELTA_DIR]
    delta: DeltaResult = load_delta_report(flow.work / CLOSURE_ROOTS_FILE)
    roots: dict[str, JsonValue] = json_object(delta)
    current_roots: dict[str, JsonValue] = json_object(
        flow.call(
            "closure",
            archstate.delta_items,
            delta_dir,
            with_closure=False,
            matrix_snapshot=flow.matrix_data,
        ),
    )
    classified: dict[str, JsonValue] = project(walk, roots, current_roots, flow.matrix_data)
    flow.checked(
        flow.call(
            "closure",
            archclosure.write_closure,
            classified,
            delta_dir,
            matrix_snapshot=flow.matrix_data,
        ),
        "closure",
    )
    path: Path = flow.work / CLOSURE_FILE
    canonical: Path = Path(result_target_dir(result)) / CLOSURE_FILE
    write_json(path, classified)
    binding: str = "matrix-rows:" + json.dumps(
        {
            "matrix": str(flow.matrix),
            "elements": sorted(
                {
                    *(
                        element_id(check_type(row["element"], str))
                        for row in check_type(
                            walk["elements"],
                            list[dict[str, JsonValue]],
                            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                        )
                    ),
                    *(element_id(item["element"]) for item in delta.get(KEY_ITEMS, [])),
                },
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    flow.store.accept(
        "architecture:closure",
        (str(walk_path), binding),
        (path, canonical),
    )
    result["closure"] = {
        "path": str(canonical),
        "workPath": str(path),
        "prerequisites": len(
            check_type(
                classified["prerequisites"],
                list[JsonValue],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            ),
        ),
    }
    return save_completion(flow, result)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def approval_inputs(flow: Architecture) -> tuple[str, ...]:
    """Approval inputs.

    Returns:
        The validated architecture artifact result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)):
        argument_error: str = "approval_inputs: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    target_path: Path = flow.work / TARGET_REPORT_NAME
    # Closure is a downstream output: its publication cannot revoke approval.
    target_inputs: tuple[str, ...] = ()
    if target_path.is_file():
        target: TargetResult = load_target_report(target_path)
        target_inputs = tuple(sorted(target.get(KEY_TARGET_HASHES, {})))
        target_dir: str | None = target.get(KEY_TARGET_DIR)
        if target_dir:
            target_inputs = tuple(
                sorted(
                    set(target_inputs)
                    | {
                        str(path)
                        for path in Path(target_dir).rglob("*")
                        if path.is_file() and path.name != CLOSURE_FILE and not path.name.endswith(".meta.json")
                    },
                ),
            )
    return (
        value_input("cited-sources", approval_sources(flow)),
        *target_inputs,
        *map(
            str,
            (
                flow.prd,
                flow.arch / "reference/architecture-documentation-model.md",
                flow.arch / "reference/diagram-and-model-types.md",
                flow.arch / "arc42/02-architecture-constraints",
                flow.schemas,
                flow.context_path,
                flow.work / SURVEY_FILE,
                flow.work / "decision.json",
                flow.work / "draft",
                flow.work / TARGET_REPORT_NAME,
            ),
        ),
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def approval_sources(flow: Architecture) -> archevidence.SourceBinding:
    """Bind cited sources outside the canonical views the integration record governs.

    Returns:
        The cited source binding that approval reuse requires to be unchanged and error-free.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(flow, Architecture):
        argument_error: str = "approval_sources: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    return archevidence.source_binding(flow.work, governed=flow.arch / "arc42")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def save_approval(flow: Architecture, target: dict[str, JsonValue], decision: dict[str, JsonValue]) -> None:
    """Save approval.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)) or not (isinstance(target, dict)) or not (isinstance(decision, dict)):
        argument_error: str = "save_approval: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    path: Path = flow.work / ARCHITECTURE_APPROVED_FILE
    record: ApprovalRecord = {
        KEY_APPROVAL_TARGET: target,
        KEY_APPROVAL_DECISION: decision,
        KEY_APPROVAL_SUBJECT: flow.subject,
    }
    write_json(path, json_object(record))
    flow.store.accept("architecture:approved", approval_inputs(flow), (path,))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def approved(flow: Architecture) -> dict[str, JsonValue] | None:
    """Approved.

    Returns:
        The validated architecture artifact result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)):
        argument_error: str = "approved: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    path: Path = flow.work / ARCHITECTURE_APPROVED_FILE
    if approval_sources(flow)["errors"]:
        return None
    if not flow.store.reusable(approval_inputs(flow), (path,)):
        return None
    # While integrating, this record explicitly permits the maintainer's own writes.
    # After integration, it again checks cited canonical views against accepted hashes.
    problem: str | None = flow.call("resume", archrevision.record_problem, str(flow.work), str(flow.arch))
    if problem:
        return None
    record: ApprovalRecord = parse_approval(read(path))
    flow.subject = record[KEY_APPROVAL_SUBJECT]
    return json_object(record)
