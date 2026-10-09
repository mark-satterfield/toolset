"""Validate one authored JSON artifact and publish a compact, integrity-bound receipt.

The candidate is the producer's only authored output. No model copies its payload
back into the workflow. Legacy artifacts without receipts remain readable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def canonical(value: object) -> bytes:
    """Return deterministic UTF-8 JSON bytes, refusing non-JSON numeric values."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _pairs(items: list) -> dict:
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def decode(text: str) -> object:
    """Parse strict JSON, refusing duplicate fields and nonfinite numbers."""
    value = json.loads(text, object_pairs_hook=_pairs)
    canonical(value)
    return value


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def receipt_path(path: Path) -> Path:
    return path.with_name(path.name + ".receipt")


#: Paths a lenient read accepted although their receipt no longer matched the bytes on disk.
LENIENT_READS: list[str] = []


def read_artifact(path: Path, *, strict: bool = True) -> object:
    """Read a legacy result or verify a sealed result before consuming its value.

    With `strict` False (the architecture step's own readers), a receipt or publication
    record that no longer matches the bytes on disk is noted in LENIENT_READS and the bytes
    on disk are used.
    """
    value = decode(path.read_text(encoding="utf-8"))
    if not strict:
        try:
            return read_artifact(path)
        except ValueError as exc:
            LENIENT_READS.append(f"{path}: {exc}")
            return value
    receipt_file = receipt_path(path)
    pending = path.with_name(path.name + ".publish")
    data = canonical(value)
    if pending.is_file():
        transaction = decode(pending.read_text(encoding="utf-8"))
        if (
            not isinstance(transaction, dict)
            or not isinstance(transaction.get("next"), dict)
            or not (
                transaction.get("previous") is None
                or isinstance(transaction.get("previous"), dict)
            )
        ):
            raise ValueError(f"invalid artifact publication receipt: {pending}")
        receipt = (
            transaction["next"]
            if _sha(data) == transaction["next"].get("sha256")
            else transaction["previous"]
        )
        if not receipt or _sha(data) != receipt.get("sha256"):
            raise ValueError(
                f"interrupted artifact publication has changed bytes: {path}"
            )
    else:
        receipt = (
            decode(receipt_file.read_text(encoding="utf-8"))
            if receipt_file.is_file()
            else None
        )
    if receipt is not None and (
        not isinstance(receipt, dict)
        or receipt.get("artifactPath") != str(path.absolute())
        or receipt.get("sha256") != _sha(data)
        or receipt.get("bytes") != len(data)
    ):
        raise ValueError(f"artifact integrity mismatch: {path}")
    return value


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(data + b"\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def accept(candidate: Path, final: Path, schema: dict, revision: str = "") -> dict:
    """Validate a candidate and publish it as the accepted result.

    A different accepted result already at `final` is replaced; its bytes are kept as
    `<name>.prev`. A prior result whose receipt no longer matches its bytes counts as absent.
    """
    from jsonschema import Draft202012Validator

    candidate, final = candidate.absolute(), final.absolute()
    if candidate.resolve() == final.resolve():
        raise ValueError("candidate and accepted artifact paths must differ")
    Draft202012Validator.check_schema(schema)
    value = decode(candidate.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(value)
    data = canonical(value)
    try:
        previous_value = read_artifact(final) if final.exists() else None
    except ValueError as exc:
        LENIENT_READS.append(f"{final}: {exc}; replaced as absent")
        previous_value = None
    if previous_value is not None and canonical(previous_value) != data:
        _atomic(final.with_name(final.name + ".prev"), canonical(previous_value))
    receipt = {
        "artifactPath": str(final),
        "sha256": _sha(data),
        "bytes": len(data),
        "schemaSha256": _sha(canonical(schema)),
        "revision": revision,
    }
    previous_data = canonical(previous_value) if previous_value is not None else None
    previous = (
        {
            "artifactPath": str(final),
            "sha256": _sha(previous_data),
            "bytes": len(previous_data),
        }
        if previous_data is not None
        else None
    )
    pending = final.with_name(final.name + ".publish")
    _atomic(pending, canonical({"previous": previous, "next": receipt}))
    if previous_data != data:
        _atomic(final, data)
    _atomic(receipt_path(final), canonical(receipt))
    pending.unlink()
    return receipt


def coordinator_facts(path: Path) -> dict:
    """Project routing fields; assigned task prose stays in the authoritative plan."""
    value = read_artifact(path)
    dispatches = []
    for index, item in enumerate(value["dispatches"]):
        reference = f"Read dispatches[{index}] in {path} for the exact assigned task and selectionReason."
        dispatches.append(
            {
                **{
                    key: item[key]
                    for key in (
                        "agentType",
                        "role",
                        "repairIds",
                        "files",
                        "answers",
                        "claimIds",
                        "claimFiles",
                    )
                },
                "coverageIds": item.get("coverageIds", []),
                "task": reference,
                "selectionReason": reference,
            }
        )
    overlaps = [
        {
            **item,
            "reason": f"Read overlaps[{index}].reason in {path}"
            if item["reason"].strip()
            else "",
        }
        for index, item in enumerate(value["overlaps"])
    ]
    return {
        "readyForDecision": value["readyForDecision"],
        "reason": f"Read reason in {path}",
        "dispatches": dispatches,
        "overlaps": overlaps,
    }


def project(value: object, paths: list[str]) -> object:
    """Select explicit dotted control fields, preserving array positions."""
    if "" in paths:
        return value
    if isinstance(value, list):
        return [project(item, paths) for item in value]
    if not isinstance(value, dict):
        return None
    groups = {}
    for item in paths:
        key, _, tail = item.partition(".")
        groups.setdefault(key, []).append(tail)
    return {
        key: project(value[key], nested)
        for key, nested in groups.items()
        if key in value
    }


def document_receipt(path: Path) -> dict:
    """Identify the actual UTF-8 document; semantic review remains independent."""
    data = path.read_bytes()
    if not data.decode("utf-8").strip():
        raise ValueError(f"document is empty: {path}")
    return {
        "artifactPath": str(path.absolute()),
        "sha256": _sha(data),
        "bytes": len(data),
        "format": "text",
    }


def source_receipt(path: Path, *, skipped: list[str] | None = None) -> dict:
    """Fingerprint an explicit source file or corpus without transporting content.

    A path that is neither a file nor a directory fingerprints as `absent`; a symlink or other
    non-regular entry of a corpus is skipped and named in `skipped`.
    """
    if path.is_file():
        data = path.read_bytes()
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
    entries = []
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
                }
            )
    return {
        "artifactPath": str(path.absolute()),
        "sha256": _sha(canonical(entries)),
        "bytes": sum(item["bytes"] for item in entries),
        "format": "directory",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
    args = parser.parse_args()
    if args.document or args.source:
        try:
            skipped: list[str] = []
            receipts = [document_receipt(path) for path in args.document] + [
                source_receipt(path, skipped=skipped) for path in args.source
            ]
            print(
                json.dumps(
                    {"receipts": receipts, **({"skipped": skipped} if skipped else {})}
                )
            )
            return 0
        except (OSError, ValueError) as exc:
            print(json.dumps({"error": str(exc)[:300]}))
            return 2
    if not args.candidate or not args.final or args.schema_json is None:
        parser.error("JSON acceptance requires --candidate, --final and --schema-json")
    try:
        receipt = None
        if args.probe and args.final.is_file() and receipt_path(args.final).is_file():
            try:
                read_artifact(args.final)
                saved = decode(receipt_path(args.final).read_text())
            except ValueError:
                # A saved result whose receipt no longer matches is not reused: it counts as absent.
                saved = {}
            if (
                saved.get("schemaSha256") == _sha(canonical(decode(args.schema_json)))
                and saved.get("revision", "") == args.revision
                and not args.final.with_name(args.final.name + ".publish").exists()
            ):
                receipt = saved
        if args.probe and receipt is None:
            checkpoint_path = Path(str(args.candidate) + ".checkpoint")
            checkpoint = (
                decode(checkpoint_path.read_text()) if checkpoint_path.is_file() else {}
            )
            if (
                isinstance(checkpoint, dict)
                and checkpoint.get("status") == "blocked"
                and checkpoint.get("revision", "") == args.revision
                and checkpoint.get("artifactPath") == str(args.candidate)
                and checkpoint.get("schemaSha256")
                == _sha(canonical(decode(args.schema_json)))
            ):
                from jsonschema import Draft202012Validator

                checkpoint_schema = (
                    Path(__file__).resolve().parents[2]
                    / "skills/artifact-handoff/schemas/checkpoint.schema.json"
                )
                Draft202012Validator(decode(checkpoint_schema.read_text())).validate(
                    checkpoint
                )
                print(
                    json.dumps(
                        {
                            "pending": True,
                            "blocked": True,
                            "candidate": str(args.candidate),
                            "revision": args.revision,
                            "reason": checkpoint.get("reason")
                            or "producer recorded a blocked dependency",
                            "remaining": checkpoint["remaining"],
                        }
                    )
                )
                return 0
            if (
                not isinstance(checkpoint, dict)
                or checkpoint.get("status") != "complete"
                or checkpoint.get("revision", "") != args.revision
            ):
                pending = {"pending": True}
                if args.research_agent and args.research_repo is not None:
                    from researchrecovery import recover

                    research = recover(
                        args.candidate,
                        args.revision,
                        args.research_agent,
                        args.research_repo,
                    )
                    if research:
                        pending["research"] = research
                print(json.dumps(pending))
                return 0
        # A recovered candidate is accepted on its own schema validity, checkpoint or not.
        if receipt is None:
            receipt = accept(
                args.candidate, args.final, decode(args.schema_json), args.revision
            )
    except (ImportError, OSError, ValueError) as exc:
        print(json.dumps({"error": f"{args.candidate}: {str(exc)[:300]}"}))
        return 2
    except Exception as exc:
        # jsonschema exposes validation exceptions only after its optional import.
        if type(exc).__module__.startswith("jsonschema"):
            location = (
                ".".join(str(part) for part in getattr(exc, "absolute_path", []))
                or "(root)"
            )
            print(
                json.dumps(
                    {
                        "error": f"{args.candidate} at {location}: {getattr(exc, 'validator', 'schema')} validation failed; {str(getattr(exc, 'message', exc))[:240]}"
                    }
                )
            )
            return 2
        raise
    if args.projection == "coordinator":
        receipt["facts"] = coordinator_facts(args.final.absolute())
    if args.keys:
        value = read_artifact(args.final.absolute())
        receipt["facts"] = project(value, args.keys.split(","))
    if args.counts:
        value = read_artifact(args.final.absolute())
        receipt["counts"] = {
            key: len(value.get(key, [])) for key in args.counts.split(",")
        }
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
