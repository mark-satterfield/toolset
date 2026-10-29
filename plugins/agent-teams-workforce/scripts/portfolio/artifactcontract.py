"""Producer-side artifact completion; structural validity is never review approval.

The checkpoint sidecar, the progress file it is built from, the status report and the command
results are the artifact checkpoint contract, defined once in
skills/artifact-handoff/schemas/checkpoint.schema.json and generated into checkpoint_contract.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# The artifact checkpoint contract is generated into the artifact-handoff skill, its one place.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))

from checkpoint_contract import (
    AUTHORED_STATUSES,
    OPERATION_COMPLETE,
    OPERATION_STATUS,
    OPERATION_SUBMIT,
    OPERATION_VALIDATE,
    OPERATIONS,
    PROGRESS_KEYS,
    REPORT_BLOCKED,
    REPORT_IN_PROGRESS,
    REPORT_INCOMPLETE,
    RESULT_COMPLETE_UNACCEPTED,
    RESULT_INVALID,
    RESULT_SCHEMA_VALID,
    STATUS_BLOCKED,
    STATUS_COMPLETE,
    STATUS_IN_PROGRESS,
    CheckpointRecord,
    CheckpointStatus,
    CommandResult,
    ProgressInput,
    StatusReport,
    checkpoint_path,
    load_checkpoint_schema,
)
from contracts import JsonObject, JsonValue, json_object
from jsonartifact import (
    binding_matches,
    canonical,
    checkpoint_report,
    decode,
    read_checkpoint,
    require_schema,
    schema_from_option,
    write_atomic,
)
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type


def load_json(path: Path) -> JsonValue:
    """Read one strict JSON file.

    Returns:
        The decoded value.

    """
    return decode(path.read_text(encoding="utf-8"))


def validate_candidate(candidate: Path, schema: JsonObject) -> JsonValue:
    """Validate the candidate artifact against its schema.

    Returns:
        The candidate value; a candidate the schema refuses raises ``SchemaProblemsError`` from
        ``require_schema``, every problem stated in full.

    """
    Draft202012Validator.check_schema(schema)
    value: JsonValue = load_json(candidate)
    require_schema(value, schema, str(candidate))
    return value


def verify_files(paths: JsonValue, root: Path, *, relative_only: bool = True) -> None:
    """Verify explicitly declared written files; never infer paths from arbitrary text.

    Raises:
        ValueError: A declared path is not a nonempty regular file inside `root`.

    """
    if not isinstance(paths, list) or any(not isinstance(x, str) or not x for x in paths):
        message: str = "declared files must be an array of nonempty paths"
        raise ValueError(message)
    resolved_root: Path = root.resolve(strict=True)
    if not resolved_root.is_dir():
        message = "files root must be a directory"
        raise ValueError(message)
    name: JsonValue
    for name in paths:
        path: Path = Path(str(name))
        if ".." in path.parts or (relative_only and path.is_absolute()):
            message = f"file must be relative to its declared root: {name}"
            raise ValueError(message)
        resolved: Path = (resolved_root / path).resolve(strict=True)
        if not resolved.is_relative_to(resolved_root):
            message = f"file escapes its declared root: {name}"
            raise ValueError(message)
        if not resolved.is_file() or resolved.stat().st_size == 0:
            message = f"declared output is not a nonempty regular file: {name}"
            raise ValueError(message)


def artifact_status(candidate: Path, schema: JsonObject, revision: str) -> StatusReport:
    """Report where the producer of `candidate` stands, from its checkpoint sidecar.

    Returns:
        The status report.

    """
    saved: CheckpointRecord | None = read_checkpoint(candidate)
    if saved is None:
        return {"status": REPORT_INCOMPLETE, "reason": "checkpoint missing"}
    report: StatusReport = checkpoint_report(candidate, schema, revision)
    if not binding_matches(saved, report):
        return {"status": REPORT_INCOMPLETE, "reason": "checkpoint binding changed"}
    if saved["status"] == STATUS_IN_PROGRESS:
        return {"status": REPORT_IN_PROGRESS, "remaining": saved["remaining"], "reason": saved.get("reason", "")}
    if saved["status"] == STATUS_BLOCKED:
        return {"status": REPORT_BLOCKED, "remaining": saved["remaining"], "reason": saved.get("reason", "")}
    # A candidate rewritten after its completion is judged as it is now: it is valid
    # against the schema or validate_candidate raises.
    value: JsonValue = validate_candidate(candidate, schema)
    report["candidateSha256"] = hashlib.sha256(canonical(value)).hexdigest()
    return report


@dataclass(frozen=True)
class _Options:
    operation: str
    candidate: Path
    schema: JsonObject
    revision: str
    progress_file: Path | None
    status: CheckpointStatus | None
    files_root: Path | None
    files_field: str | None
    progress_artifacts_root: Path | None


def _progress(path: Path | None, schema: JsonObject) -> ProgressInput:
    """Read the agent-authored progress file, keeping only the keys of PROGRESS_KEYS.

    Returns:
        The validated progress input.

    Raises:
        ValueError: No progress file was given, or it is not a JSON object.

    """
    if path is None:
        message: str = f"--progress-file is required; author {', '.join(sorted(PROGRESS_KEYS))}"
        raise ValueError(message)
    raw: JsonObject = json_object(load_json(path))
    progress: JsonObject = {key: value for key, value in raw.items() if key in PROGRESS_KEYS}
    defs: JsonValue = schema.get("$defs")
    Draft202012Validator({"$defs": defs, "$ref": "#/$defs/Progress"}).validate(progress)
    return check_type(progress, ProgressInput, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _record(options: _Options) -> CommandResult:
    """Write the checkpoint for a checkpoint, complete or submit operation.

    Returns:
        The command result.

    Raises:
        ValueError: The operation's inputs do not satisfy the contract.

    """
    checkpoint_schema: JsonObject = load_checkpoint_schema()
    progress: ProgressInput = _progress(options.progress_file, checkpoint_schema)
    status: CheckpointStatus | None = (
        STATUS_COMPLETE if options.operation in {OPERATION_COMPLETE, OPERATION_SUBMIT} else options.status
    )
    if status is None:
        message: str = f"checkpoint requires --status {' or '.join(AUTHORED_STATUSES)}"
        raise ValueError(message)
    report: StatusReport = checkpoint_report(options.candidate, options.schema, options.revision)
    saved: CheckpointRecord = {
        "task": progress["task"],
        "completed": progress["completed"],
        "remaining": progress["remaining"],
        "artifacts": progress["artifacts"],
        "artifactPath": report.get("artifactPath", ""),
        "schemaSha256": report.get("schemaSha256", ""),
        "revision": report.get("revision", ""),
        "status": status,
    }
    if "reason" in progress:
        saved["reason"] = progress["reason"]
    value: JsonValue = None
    if status == STATUS_COMPLETE:
        saved["remaining"] = []
        value = validate_candidate(options.candidate, options.schema)
        if options.files_root is not None and options.files_field is not None:
            if not isinstance(value, dict) or options.files_field not in value:
                message = "declared files field is missing from candidate"
                raise ValueError(message)
            verify_files(value[options.files_field], options.files_root)
        if options.progress_artifacts_root is not None:
            artifacts: list[JsonValue] = [*progress["artifacts"]]
            verify_files(artifacts, options.progress_artifacts_root, relative_only=False)
        saved["candidateSha256"] = hashlib.sha256(canonical(value)).hexdigest()
    Draft202012Validator(checkpoint_schema).validate(saved)
    if status == STATUS_COMPLETE:
        write_atomic(options.candidate, canonical(value))
    write_atomic(checkpoint_path(options.candidate), canonical(saved))
    if status == STATUS_COMPLETE:
        return {"status": RESULT_COMPLETE_UNACCEPTED, "artifactPath": str(options.candidate)}
    return {"status": status, "artifactPath": str(options.candidate)}


def _execute(options: _Options) -> CommandResult | StatusReport:
    """Run one operation.

    Returns:
        What the operation prints.

    """
    if options.operation == OPERATION_STATUS:
        return artifact_status(options.candidate, options.schema, options.revision)
    if options.operation == OPERATION_VALIDATE:
        validate_candidate(options.candidate, options.schema)
        return {"status": RESULT_SCHEMA_VALID, "artifactPath": str(options.candidate)}
    result: CommandResult = _record(options)
    if options.operation == OPERATION_SUBMIT:
        return {"artifactPath": str(options.candidate)}
    return result


def _authored_status(value: str | None) -> CheckpointStatus | None:
    """Narrow the --status argument to an authored checkpoint status.

    Returns:
        The status, or None when none was given.

    Raises:
        ValueError: The value is not an authored status.

    """
    if value is None:
        return None
    if value == STATUS_IN_PROGRESS:
        return STATUS_IN_PROGRESS
    if value == STATUS_BLOCKED:
        return STATUS_BLOCKED
    message: str = f"--status must be one of {', '.join(AUTHORED_STATUSES)}"
    raise ValueError(message)


def _options(args: argparse.Namespace) -> _Options:
    """Parse the command line into typed options.

    Returns:
        The options.

    Raises:
        ValueError: The schema or the files options are invalid.

    """
    schema_file: Path | None = args.schema_file
    schema_json: str | None = args.schema_json
    contract: str | None = args.schema
    if schema_file is not None:
        if contract is not None or schema_json is not None:
            message_one: str = "--schema-file excludes --schema and --schema-json"
            raise ValueError(message_one)
        schema: JsonObject = json_object(load_json(schema_file))
        Draft202012Validator.check_schema(schema)
    else:
        schema = schema_from_option(contract, schema_json)
    files_root: Path | None = args.files_root
    files_field: str | None = args.files_field
    if (files_root is None) != (files_field is None):
        message: str = "--files-root and --files-field must be supplied together"
        raise ValueError(message)
    candidate: Path = args.candidate
    revision: str = args.revision
    operation: str = args.operation
    progress_file: Path | None = args.progress_file
    status: str | None = args.status
    progress_artifacts_root: Path | None = args.progress_artifacts_root
    return _Options(
        operation=operation,
        candidate=candidate.absolute(),
        schema=schema,
        revision=revision,
        progress_file=progress_file,
        status=_authored_status(status),
        files_root=files_root,
        files_field=files_field,
        progress_artifacts_root=progress_artifacts_root,
    )


def main() -> int:
    """Run the artifact contract command line.

    Returns:
        0 on success, 2 when the operation's inputs are invalid.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--schema", help="the contract file the candidate must satisfy: <path>[#<JSON pointer>]")
    parser.add_argument("--schema-json", help="the schema itself, as one JSON object (the form older workflows pass)")
    parser.add_argument("--schema-file", type=Path, help="a file holding the schema itself")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--progress-file", type=Path)
    parser.add_argument("--status", choices=AUTHORED_STATUSES)
    parser.add_argument("--files-root", type=Path)
    parser.add_argument("--files-field")
    parser.add_argument("--progress-artifacts-root", type=Path)
    args: argparse.Namespace = parser.parse_args()
    result: CommandResult | StatusReport
    code: int
    try:
        result = _execute(_options(args))
        code = 0
    except (OSError, ValueError, TypeError, SchemaError, ValidationError, TypeCheckError) as exc:
        result = {"status": RESULT_INVALID, "error": str(exc)}
        code = 2
    sys.stdout.write(json.dumps(result) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
