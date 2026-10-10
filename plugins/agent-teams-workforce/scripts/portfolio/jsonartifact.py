"""Validate one authored JSON artifact and publish a compact, integrity-bound receipt.

The candidate is the producer's only authored output. No model copies its payload
back into the workflow. Legacy artifacts without receipts remain readable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

import contracts
import researchrecovery
from contracts import JsonObject, JsonValue, json_object
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from researchrecovery import recover
from roundcontracts import Overlap
from typeguard import CollectionCheckStrategy, check_type, typechecked


class ArtifactReceipt(TypedDict):
    """The integrity record written beside an accepted artifact."""

    artifactPath: str
    sha256: str
    bytes: int
    schemaSha256: NotRequired[str]
    revision: NotRequired[str]
    format: NotRequired[str]
    facts: NotRequired[JsonValue]
    counts: NotRequired[dict[str, int]]


class SourceEntry(TypedDict):
    """A source corpus member included in the content fingerprint."""

    path: str
    sha256: str
    bytes: int


class CoordinatorDispatch(TypedDict):
    """Required fields of one authored coordinator-plan assignment."""

    agentType: str
    role: Literal["proposer", "diagram", "reviewer", "cost"]
    task: str
    selectionReason: str
    repairIds: list[str]
    files: list[str]
    answers: list[str]
    claimIds: list[str]
    claimFiles: list[str]
    coverageIds: list[str]


class CoordinatorDocument(TypedDict):
    """The actual coordinator-plan schema fields before round enrichment."""

    readyForDecision: bool
    reason: str
    dispatches: list[CoordinatorDispatch]
    overlaps: list[Overlap]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def canonical(value: object) -> bytes:
    """Return deterministic UTF-8 JSON bytes, refusing non-JSON numeric values.

    Returns:
        Canonical JSON bytes.

    """
    validated: JsonValue = check_type(value, JsonValue, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    return json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def _pairs(items: list[tuple[str, JsonValue]]) -> JsonObject:
    key: str
    value: JsonValue
    out: JsonObject = {}
    for key, value in items:
        if key in out:
            message: str = f"duplicate JSON key: {key}"
            raise ValueError(message)
        out[key] = value
    return out


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def decode(text: str) -> JsonValue:
    """Parse strict JSON, refusing duplicate fields and nonfinite numbers.

    Returns:
        The validated JSON value.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(text, str)):
        argument_error: str = "decode: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    value: JsonValue = check_type(
        json.loads(text, object_pairs_hook=_pairs),
        JsonValue,
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    canonical(value)
    return value


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def receipt_path(path: Path) -> Path:
    """Locate the integrity receipt beside its artifact.

    Returns:
        The artifact's receipt path.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(path, Path)):
        argument_error: str = "receipt_path: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    return path.with_name(path.name + ".receipt")


#: Paths a lenient read accepted although their receipt no longer matched the bytes on disk.
LENIENT_READS: list[str] = []


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_artifact(path: Path, *, strict: bool = True) -> JsonValue:
    """Read a legacy result or verify a sealed result before consuming its value.

    With `strict` False (the architecture step's own readers), a receipt or publication
    record that no longer matches the bytes on disk is noted in LENIENT_READS and the bytes
    on disk are used.

    Returns:
        The accepted artifact JSON value.

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: The input does not satisfy the required contract.

    """
    if not (isinstance(path, Path)) or not (isinstance(strict, bool)):
        argument_error: str = "read_artifact: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    value: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = decode(
        path.read_text(encoding="utf-8"),
    )
    if not strict:
        try:
            return read_artifact(path)
        except ValueError as exc:
            LENIENT_READS.append(f"{path}: {exc}")
            return value
    receipt_file: Path = receipt_path(path)
    pending: Path = path.with_name(path.name + ".publish")
    data: bytes = canonical(value)
    if pending.is_file():
        transaction: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = decode(
            pending.read_text(encoding="utf-8"),
        )
        if (
            not isinstance(transaction, dict)
            or not isinstance(transaction.get("next"), dict)
            or not (transaction.get("previous") is None or isinstance(transaction.get("previous"), dict))
        ):
            message: str = f"invalid artifact publication receipt: {pending}"
            raise ValueError(message)
        next_receipt: dict[str, contracts.JsonValue] = json_object(transaction["next"])
        receipt: dict[str, contracts.JsonValue] | int | float | str | list[contracts.JsonValue] | None = (
            next_receipt if _sha(data) == next_receipt.get("sha256") else transaction["previous"]
        )
        if not isinstance(receipt, dict) or _sha(data) != receipt.get("sha256"):
            message = f"interrupted artifact publication has changed bytes: {path}"
            raise ValueError(message)
    else:
        receipt = decode(receipt_file.read_text(encoding="utf-8")) if receipt_file.is_file() else None
    if receipt is not None and (
        not isinstance(receipt, dict)
        or receipt.get("artifactPath") != str(path.absolute())
        or receipt.get("sha256") != _sha(data)
        or receipt.get("bytes") != len(data)
    ):
        message = f"artifact integrity mismatch: {path}"
        raise ValueError(message)
    return value


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(data + b"\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def accept(candidate: Path, final: Path, schema: JsonObject, revision: str = "") -> ArtifactReceipt:
    """Validate a candidate and publish it as the accepted result.

    A different accepted result already at `final` is replaced; its bytes are kept as
    `<name>.prev`. A prior result whose receipt no longer matches its bytes counts as absent.

    Returns:
        The published artifact receipt.

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: The input does not satisfy the required contract.

    """
    if (
        not (isinstance(candidate, Path))
        or not (isinstance(final, Path))
        or not (isinstance(schema, dict))
        or not (isinstance(revision, str))
    ):
        argument_error: str = "accept: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    candidate, final = candidate.absolute(), final.absolute()
    if candidate.resolve() == final.resolve():
        message: str = "candidate and accepted artifact paths must differ"
        raise ValueError(message)
    Draft202012Validator.check_schema(schema)
    value: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = decode(
        candidate.read_text(encoding="utf-8"),
    )
    Draft202012Validator(schema).validate(value)
    data: bytes = canonical(value)
    try:
        previous_value: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = (
            read_artifact(final) if final.exists() else None
        )
    except ValueError as exc:
        LENIENT_READS.append(f"{final}: {exc}; replaced as absent")
        previous_value = None
    if previous_value is not None and canonical(previous_value) != data:
        _atomic(final.with_name(final.name + ".prev"), canonical(previous_value))
    receipt: ArtifactReceipt = {
        "artifactPath": str(final),
        "sha256": _sha(data),
        "bytes": len(data),
        "schemaSha256": _sha(canonical(schema)),
        "revision": revision,
    }
    previous_data: bytes | None = canonical(previous_value) if previous_value is not None else None
    previous: JsonObject | None = (
        {
            "artifactPath": str(final),
            "sha256": _sha(previous_data),
            "bytes": len(previous_data),
        }
        if previous_data is not None
        else None
    )
    pending: Path = final.with_name(final.name + ".publish")
    _atomic(pending, canonical({"previous": previous, "next": receipt}))
    if previous_data != data:
        _atomic(final, data)
    _atomic(receipt_path(final), canonical(receipt))
    pending.unlink()
    return receipt


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def coordinator_facts(path: Path) -> CoordinatorDocument:
    """Project routing fields; assigned task prose stays in the authoritative plan.

    Returns:
        The schema-derived coordinator projection.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    index: int
    item: CoordinatorDispatch
    if not (isinstance(path, Path)):
        argument_error: str = "coordinator_facts: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    value: CoordinatorDocument = check_type(
        read_artifact(path),
        CoordinatorDocument,
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    dispatches: list[CoordinatorDispatch] = []
    for index, item in enumerate(value["dispatches"]):
        reference: str = f"Read dispatches[{index}] in {path} for the exact assigned task and selectionReason."
        dispatches.append(
            {
                "agentType": item["agentType"],
                "role": item["role"],
                "repairIds": item["repairIds"],
                "files": item["files"],
                "answers": item["answers"],
                "claimIds": item["claimIds"],
                "claimFiles": item["claimFiles"],
                "coverageIds": item.get("coverageIds", []),
                "task": reference,
                "selectionReason": reference,
            },
        )
    overlaps: list[Overlap] = [
        {
            **item,
            "reason": f"Read overlaps[{index}].reason in {path}" if item["reason"].strip() else "",
        }
        for index, item in enumerate(value["overlaps"])
    ]
    return {
        "readyForDecision": value["readyForDecision"],
        "reason": f"Read reason in {path}",
        "dispatches": dispatches,
        "overlaps": overlaps,
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def project(value: JsonValue, paths: list[str]) -> JsonValue:
    """Select explicit dotted control fields, preserving array positions.

    Returns:
        The selected JSON fields.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    item: str
    key: str
    tail: str
    if not (isinstance(paths, list)):
        argument_error: str = "project: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    if "" in paths:
        return value
    if isinstance(value, list):
        return [project(item, paths) for item in value]
    if not isinstance(value, dict):
        return None
    groups: dict[str, list[str]] = {}
    for item in paths:
        key, _, tail = item.partition(".")
        groups.setdefault(key, []).append(tail)
    return {key: project(value[key], nested) for key, nested in groups.items() if key in value}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def document_receipt(path: Path) -> ArtifactReceipt:
    """Identify the actual UTF-8 document; semantic review remains independent.

    Returns:
        The document receipt.

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: The input does not satisfy the required contract.

    """
    if not (isinstance(path, Path)):
        argument_error: str = "document_receipt: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    data: bytes = path.read_bytes()
    if not data.decode("utf-8").strip():
        message: str = f"document is empty: {path}"
        raise ValueError(message)
    return {
        "artifactPath": str(path.absolute()),
        "sha256": _sha(data),
        "bytes": len(data),
        "format": "text",
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def source_receipt(path: Path, *, skipped: list[str] | None = None) -> ArtifactReceipt:
    """Fingerprint an explicit source file or corpus without transporting content.

    A path that is neither a file nor a directory fingerprints as `absent`; a symlink or other
    non-regular entry of a corpus is skipped and named in `skipped`.

    Returns:
        The source collection receipt.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    item: Path
    if not (isinstance(path, Path)) or not (isinstance(skipped, list) or skipped is None):
        argument_error: str = "source_receipt: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    if path.is_file():
        data: bytes = path.read_bytes()
        return {
            "artifactPath": str(path.absolute()),
            "sha256": _sha(data),
            "bytes": len(data),
            "format": "file",
        }
    if not path.is_dir():
        return {
            "artifactPath": str(path.absolute()),
            "sha256": _sha(b"absent"),
            "bytes": 0,
            "format": "absent",
        }
    entries: list[SourceEntry] = []
    for item in sorted(path.rglob("*")):
        if item.is_symlink() or not (item.is_file() or item.is_dir()):
            if skipped is not None:
                skipped.append(str(item))
            continue
        if item.is_file():
            data = item.read_bytes()
            entries.append(
                {
                    "path": str(item.relative_to(path)),
                    "sha256": _sha(data),
                    "bytes": len(data),
                },
            )
    return {
        "artifactPath": str(path.absolute()),
        "sha256": _sha(canonical(entries)),
        "bytes": sum(item["bytes"] for item in entries),
        "format": "directory",
    }


@dataclass(frozen=True)
class _Acceptance:
    candidate: Path
    final: Path
    schema: JsonObject
    revision: str
    probe: bool
    research_agent: str
    research_repo: Path | None

    def saved(self) -> ArtifactReceipt | None:
        if not self.probe or not self.final.is_file() or not receipt_path(self.final).is_file():
            return None
        try:
            read_artifact(self.final)
            saved: dict[str, contracts.JsonValue] = json_object(
                decode(receipt_path(self.final).read_text(encoding="utf-8")),
            )
        except ValueError:
            return None
        if (
            saved.get("schemaSha256") == _sha(canonical(self.schema))
            and saved.get("revision", "") == self.revision
            and not self.final.with_name(self.final.name + ".publish").exists()
        ):
            return check_type(saved, ArtifactReceipt, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        return None

    def pending(self) -> JsonObject | None:
        checkpoint_path: Path = Path(str(self.candidate) + ".checkpoint")
        checkpoint: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = (
            decode(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.is_file() else {}
        )
        if (
            isinstance(checkpoint, dict)
            and checkpoint.get("status") == "blocked"
            and checkpoint.get("revision", "") == self.revision
            and checkpoint.get("artifactPath") == str(self.candidate)
            and checkpoint.get("schemaSha256") == _sha(canonical(self.schema))
        ):
            schema_path: Path = (
                Path(__file__).resolve().parents[2] / "skills/artifact-handoff/schemas/checkpoint.schema.json"
            )
            Draft202012Validator(json_object(decode(schema_path.read_text(encoding="utf-8")))).validate(checkpoint)
            return {
                "pending": True,
                "blocked": True,
                "candidate": str(self.candidate),
                "revision": self.revision,
                "reason": checkpoint.get("reason") or "producer recorded a blocked dependency",
                "remaining": checkpoint["remaining"],
            }
        if (
            isinstance(checkpoint, dict)
            and checkpoint.get("status") == "complete"
            and checkpoint.get("revision", "") == self.revision
        ):
            return None
        pending: JsonObject = {"pending": True}
        if self.research_agent and self.research_repo is not None:
            research: researchrecovery.ResearchReceipt | None = recover(
                self.candidate,
                self.revision,
                self.research_agent,
                self.research_repo,
            )
            if research:
                pending["research"] = json_object(research)
        return pending


@dataclass(frozen=True)
class _CliOptions:
    """Validated immutable artifact CLI input, independent of argparse storage."""

    document: tuple[Path, ...]
    source: tuple[Path, ...]
    candidate: Path | None
    final: Path | None
    schema_json: str | None
    revision: str
    projection: Literal["coordinator"] | None
    keys: str
    counts: str
    probe: bool
    research_agent: str
    research_repo: Path | None


def _cli_options(args: argparse.Namespace) -> _CliOptions:
    """Narrow argparse's untyped attributes before they enter artifact operations.

    Returns:
        Immutable, validated arguments for artifact operations.

    """
    return _CliOptions(
        tuple(check_type(args.document, list[Path], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)),
        tuple(check_type(args.source, list[Path], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)),
        check_type(args.candidate, Path | None),
        check_type(args.final, Path | None),
        check_type(args.schema_json, str | None),
        check_type(args.revision, str),
        check_type(args.projection, Literal["coordinator"] | None),
        check_type(args.keys, str),
        check_type(args.counts, str),
        check_type(args.probe, bool),
        check_type(args.research_agent, str),
        check_type(args.research_repo, Path | None),
    )


def _receipt_options(receipt: ArtifactReceipt, final: Path, args: _CliOptions) -> ArtifactReceipt:
    if args.projection == "coordinator":
        receipt["facts"] = json_object(coordinator_facts(final.absolute()))
    keys: str = check_type(args.keys, str)
    counts: str = check_type(args.counts, str)
    if keys:
        receipt["facts"] = project(read_artifact(final.absolute()), keys.split(","))
    if counts:
        value: dict[str, contracts.JsonValue] = json_object(read_artifact(final.absolute()))
        receipt["counts"] = {
            key: len(
                check_type(
                    value.get(key, []),
                    list[JsonValue],
                    collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                ),
            )
            for key in counts.split(",")
        }
    return receipt


def _execute_cli(args: _CliOptions, parser: argparse.ArgumentParser) -> JsonObject | ArtifactReceipt:
    documents: tuple[Path, ...] = args.document
    sources: tuple[Path, ...] = args.source
    if documents or sources:
        skipped: list[str] = []
        receipts: list[ArtifactReceipt] = [document_receipt(path) for path in documents] + [
            source_receipt(path, skipped=skipped) for path in sources
        ]
        return json_object({"receipts": receipts, **({"skipped": skipped} if skipped else {})})
    if not args.candidate or not args.final or args.schema_json is None:
        parser.error("JSON acceptance requires --candidate, --final and --schema-json")
    options: _Acceptance = _Acceptance(
        check_type(args.candidate, Path),
        check_type(args.final, Path),
        json_object(decode(check_type(args.schema_json, str))),
        check_type(args.revision, str),
        check_type(args.probe, bool),
        check_type(args.research_agent, str),
        check_type(args.research_repo, Path | None),
    )
    receipt: ArtifactReceipt | None = options.saved()
    if options.probe and receipt is None:
        pending: contracts.JsonObject | None = options.pending()
        if pending is not None:
            return pending
    if receipt is None:
        receipt = accept(options.candidate, options.final, options.schema, options.revision)
    return _receipt_options(receipt, options.final, args)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> int:
    """Validate CLI arguments and publish one artifact or receipt set.

    Returns:
        Zero on acceptance or pending evidence, two on a visible validation error.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--final", type=Path)
    parser.add_argument("--schema-json")
    parser.add_argument("--document", type=Path, action="append", default=[])
    parser.add_argument("--source", type=Path, action="append", default=[])
    parser.add_argument("--revision", default="")
    parser.add_argument("--projection", choices=["coordinator"], default=None)
    parser.add_argument("--keys", default="")
    parser.add_argument("--counts", default="")
    parser.add_argument("--recover", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--research-agent", default="")
    parser.add_argument("--research-repo", type=Path)
    args: _CliOptions = _cli_options(parser.parse_args())
    try:
        result: JsonObject | ArtifactReceipt = _execute_cli(args, parser)
    except (ImportError, OSError, ValueError) as exc:
        prefix: str = "" if args.document or args.source else f"{args.candidate}: "
        sys.stdout.write(json.dumps({"error": prefix + str(exc)[:300]}) + "\n")
        return 2
    except ValidationError as exc:
        location: str = ".".join(str(part) for part in exc.absolute_path) or "(root)"
        message: str = f"{args.candidate} at {location}: {exc.validator} validation failed; {exc.message[:240]}"
        sys.stdout.write(json.dumps({"error": message}) + "\n")
        return 2
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
