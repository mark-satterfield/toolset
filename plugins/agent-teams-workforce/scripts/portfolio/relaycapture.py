"""Capture a checked command once; recover its exact output by execution-bound receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import relay
from relayregistry import load_request

CHUNK_SIZE = 1024
MAX_BYTES = 1024 * 1024


def digest(text: str) -> str:
    """Hash ASCII transport text, rejecting ambiguous encodings."""
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def receipt(saved: dict) -> dict:
    """Return the compact binding independent of the large output copy."""
    return {
        key: saved[key]
        for key in ("request", "commandSha256", "sha256", "bytes", "exitCode")
    }


def load(path: Path, request: str, command_sha: str) -> dict:
    """Read only the exact invocation and validate all saved byte bindings."""
    saved = json.loads(path.read_text(encoding="ascii"))
    if saved["request"] != request or saved["commandSha256"] != command_sha:
        raise ValueError("capture belongs to a different invocation or command")
    stdout = saved["stdout"]
    if (
        not isinstance(stdout, str)
        or len(stdout) > MAX_BYTES
        or saved["bytes"] != len(stdout)
        or saved["sha256"] != digest(stdout)
    ):
        raise ValueError("saved capture bytes do not match their receipt")
    if type(saved["exitCode"]) is not int:
        raise ValueError("saved capture has no integer process status")
    return saved


def registered_result(directory: Path, request: str, execution: str) -> dict:
    """Materialize the exact current registered capture for the handoff hook."""
    result = {
        "state": "unknown",
        "exitCode": 0,
        "stdout": "",
        "receipt": None,
        "bridge": True,
        "error": "",
    }
    try:
        document = load_request(directory, request)
        if document["executionId"] != execution:
            raise ValueError("registered result belongs to another execution")
        path = directory / f"{request}.json"
        if not path.exists():
            result["state"] = (
                "unknown" if path.with_suffix(".claim").exists() else "not-started"
            )
            result["error"] = (
                "command outcome unknown; claim exists"
                if result["state"] == "unknown"
                else "registered command never started; no claim or result exists"
            )
            return result
        saved = load(path, request, document["commandSha256"])
        return {
            **result,
            "state": "completed",
            "exitCode": saved["exitCode"],
            "stdout": saved["stdout"],
            "receipt": receipt(saved),
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["error"] = str(exc)
        return result


def main(argv: list[str] | None = None) -> int:
    """Capture once, or return a manifest/chunk without executing the command."""
    rest, error = relay.argv_mismatch(list(sys.argv[1:] if argv is None else argv))
    if error:
        raise ValueError(error)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=("capture", "manifest", "chunk", "registered", "registered-result"),
    )
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--command-sha256", default="")
    parser.add_argument("--index", type=int)
    parser.add_argument("--sha256")
    parser.add_argument("--argv-json")
    args = parser.parse_args(rest)
    registered = args.operation in {"registered", "registered-result"}
    if registered:
        document = load_request(args.directory, args.request, wait_seconds=10)
        args.command_sha256 = document["commandSha256"]
        args.argv_json = json.dumps(document["argv"])
        args.operation = "capture" if args.operation == "registered" else "manifest"
    if any(
        len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
        for value in (args.request, args.command_sha256)
    ):
        raise ValueError("invalid request or command digest")
    path = args.directory / f"{args.request}.json"
    if args.operation == "capture":
        command = json.loads(args.argv_json)
        if (
            not isinstance(command, list)
            or not command
            or any(not isinstance(word, str) for word in command)
        ):
            raise ValueError("command must be a nonempty string array")
        if digest(relay.canonical(command)) != args.command_sha256:
            raise ValueError("command digest mismatch")
        args.directory.mkdir(parents=True, exist_ok=True)
        # A claim survives interruption: an unknown outcome must never run again.
        claim = path.with_suffix(".claim")
        if not path.exists():
            try:
                descriptor = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as exc:
                raise ValueError(
                    "capture outcome unknown; original command will not repeat"
                ) from exc
            os.close(descriptor)
            done = subprocess.run(
                command, capture_output=True, timeout=600, check=False
            )
            stdout = done.stdout.decode("ascii")
            if len(stdout) > MAX_BYTES:
                raise ValueError("capture exceeds bounded transport size")
            saved = {
                "request": args.request,
                "commandSha256": args.command_sha256,
                "sha256": digest(stdout),
                "bytes": len(stdout),
                "exitCode": done.returncode,
                "stdout": stdout,
                "stderr": done.stderr.decode("utf-8", errors="replace"),
            }
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(saved, ensure_ascii=True), encoding="ascii")
            temporary.replace(path)
    saved = load(path, args.request, args.command_sha256)
    result = {"receipt": receipt(saved)}
    if args.operation == "capture":
        result.update(exitCode=saved["exitCode"], stdout=saved["stdout"])
    elif args.operation == "chunk":
        if args.sha256 != saved["sha256"]:
            raise ValueError("chunk receipt digest mismatch")
        count = (saved["bytes"] + CHUNK_SIZE - 1) // CHUNK_SIZE
        if args.index is None or args.index < 0 or args.index >= count:
            raise ValueError("chunk index out of range")
        chunk = saved["stdout"][args.index * CHUNK_SIZE : (args.index + 1) * CHUNK_SIZE]
        result.update(index=args.index, chunk=chunk, sha256=digest(chunk))
    if registered:
        # Payload travels through the command runner's StructuredOutput hook, not tokens.
        result = {
            "state": "completed",
            "exitCode": saved["exitCode"],
            "stdout": "",
            "receipt": receipt(saved),
            "bridge": False,
            "error": "",
        }
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from exc
