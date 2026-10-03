"""Producer-side artifact completion; structural validity is never review approval."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonartifact import _atomic, canonical, decode
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

CHECKPOINT_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "skills/artifact-handoff/schemas/checkpoint.schema.json"
)


def load_json(path: Path) -> object:
    return decode(path.read_text(encoding="utf-8"))


def validate_candidate(candidate: Path, schema: dict) -> object:
    Draft202012Validator.check_schema(schema)
    value = load_json(candidate)
    Draft202012Validator(schema).validate(value)
    return value


def verify_files(paths: object, root: Path, *, relative_only: bool = True) -> None:
    """Verify explicitly declared written files; never infer paths from arbitrary text."""
    if not isinstance(paths, list) or any(
        not isinstance(x, str) or not x for x in paths
    ):
        raise ValueError("declared files must be an array of nonempty paths")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("files root must be a directory")
    for name in paths:
        path = Path(name)
        if ".." in path.parts or (relative_only and path.is_absolute()):
            raise ValueError(f"file must be relative to its declared root: {name}")
        resolved = (root / path).resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError(f"file escapes its declared root: {name}")
        if not resolved.is_file() or resolved.stat().st_size == 0:
            raise ValueError(f"declared output is not a nonempty regular file: {name}")


def checkpoint_binding(candidate: Path, schema: dict, revision: str) -> dict:
    return {
        "artifactPath": str(candidate.absolute()),
        "schemaSha256": hashlib.sha256(canonical(schema)).hexdigest(),
        "revision": revision,
    }


def artifact_status(candidate: Path, schema: dict, revision: str) -> dict:
    checkpoint = Path(str(candidate) + ".checkpoint")
    if not checkpoint.exists():
        return {"status": "incomplete", "reason": "checkpoint missing"}
    saved = load_json(checkpoint)
    Draft202012Validator(load_json(CHECKPOINT_SCHEMA)).validate(saved)
    expected = checkpoint_binding(candidate, schema, revision)
    if any(saved.get(key) != value for key, value in expected.items()):
        return {"status": "incomplete", "reason": "checkpoint binding changed"}
    if saved["status"] != "complete":
        return {
            "status": saved["status"],
            "remaining": saved["remaining"],
            "reason": saved.get("reason", ""),
        }
    value = validate_candidate(candidate, schema)
    digest = hashlib.sha256(canonical(value)).hexdigest()
    if saved.get("candidateSha256") != digest:
        return {"status": "incomplete", "reason": "candidate changed after completion"}
    return {"status": "complete-unaccepted", **expected, "candidateSha256": digest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", choices=["validate", "checkpoint", "complete", "submit", "status"]
    )
    parser.add_argument("--candidate", type=Path, required=True)
    schemas = parser.add_mutually_exclusive_group(required=True)
    schemas.add_argument("--schema-file", type=Path)
    schemas.add_argument("--schema-json")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--progress-file", type=Path)
    parser.add_argument("--status", choices=["in-progress", "blocked"])
    parser.add_argument("--files-root", type=Path)
    parser.add_argument("--files-field")
    parser.add_argument("--progress-artifacts-root", type=Path)
    args = parser.parse_args()
    try:
        schema = (
            load_json(args.schema_file)
            if args.schema_file is not None
            else decode(args.schema_json)
        )
        Draft202012Validator.check_schema(schema)
        if (args.files_root is None) != (args.files_field is None):
            raise ValueError("--files-root and --files-field must be supplied together")
        candidate = args.candidate.absolute()
        if args.operation == "status":
            result = artifact_status(candidate, schema, args.revision)
        elif args.operation == "validate":
            validate_candidate(candidate, schema)
            result = {"status": "schema-valid", "artifactPath": str(candidate)}
        else:
            if args.progress_file is None:
                raise ValueError(
                    "--progress-file is required; author task, completed, remaining and artifacts"
                )
            progress = load_json(args.progress_file)
            allowed = {"task", "completed", "remaining", "artifacts", "reason"}
            if not isinstance(progress, dict) or set(progress) - allowed:
                raise ValueError(
                    "progress accepts only task, completed, remaining, artifacts and reason"
                )
            status = (
                "complete" if args.operation in {"complete", "submit"} else args.status
            )
            if status is None:
                raise ValueError("checkpoint requires --status in-progress or blocked")
            saved = {
                **progress,
                **checkpoint_binding(candidate, schema, args.revision),
                "status": status,
            }
            if status == "complete":
                if progress.get("remaining") != []:
                    raise ValueError(
                        "completion requires an explicitly empty remaining list"
                    )
                value = validate_candidate(candidate, schema)
                if args.files_field is not None:
                    if not isinstance(value, dict) or args.files_field not in value:
                        raise ValueError(
                            "declared files field is missing from candidate"
                        )
                    verify_files(value[args.files_field], args.files_root)
                if args.progress_artifacts_root is not None:
                    verify_files(
                        progress.get("artifacts"),
                        args.progress_artifacts_root,
                        relative_only=False,
                    )
                saved["candidateSha256"] = hashlib.sha256(canonical(value)).hexdigest()
            Draft202012Validator(load_json(CHECKPOINT_SCHEMA)).validate(saved)
            if status == "complete":
                _atomic(candidate, canonical(value))
            _atomic(Path(str(candidate) + ".checkpoint"), canonical(saved))
            result = {
                "status": "complete-unaccepted" if status == "complete" else status,
                "artifactPath": str(candidate),
            }
        if args.operation == "submit":
            result = {"artifactPath": str(candidate)}
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, TypeError, SchemaError, ValidationError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
