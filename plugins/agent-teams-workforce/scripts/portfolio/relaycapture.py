"""Capture a checked command once; recover its exact output by execution-bound receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs the digest-bound registered argv without a shell.
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, TypedDict

import relay
from relayregistry import load_request

CHUNK_SIZE: Final[int] = 1024
MAX_BYTES: Final[int] = 1024 * 1024
DIGEST_LENGTH: Final[int] = 64
HEX_DIGITS: Final[str] = "0123456789abcdef"
CAPTURE_TIMEOUT_SECONDS: Final[int] = 600
REGISTRY_WAIT_SECONDS: Final[int] = 10

type Operation = Literal["capture", "manifest", "chunk"]
type ResultState = Literal["unknown", "not-started", "completed"]
type ReportValue = str | int | bool | CaptureReceipt | None


class CaptureReceipt(TypedDict):
    """The compact binding of one saved capture, independent of its output copy."""

    request: str
    commandSha256: str
    sha256: str
    bytes: int
    exitCode: int


class LoadedCapture(CaptureReceipt):
    """A validated saved capture: its receipt fields and the exact output text."""

    stdout: str


class SavedCapture(LoadedCapture):
    """The document written once per capture, including diagnostic stderr."""

    stderr: str


class RegisteredResult(TypedDict):
    """The handoff payload that carries a registered command's outcome."""

    state: ResultState
    exitCode: int
    stdout: str
    receipt: CaptureReceipt | None
    bridge: bool
    error: str


@dataclass(frozen=True, slots=True)
class Options:
    """The validated command line of one invocation."""

    operation: Operation
    registered: bool
    directory: Path
    request: str
    command_sha256: str
    index: int | None
    sha256: str | None
    command: list[str] | None


def digest(text: str) -> str:
    """Hash ASCII transport text, rejecting ambiguous encodings.

    Returns:
        The SHA-256 hex digest of the ASCII bytes.

    """
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def receipt(saved: CaptureReceipt) -> CaptureReceipt:
    """Return the compact binding independent of the large output copy.

    Returns:
        The receipt fields of the saved capture.

    """
    return {
        "request": saved["request"],
        "commandSha256": saved["commandSha256"],
        "sha256": saved["sha256"],
        "bytes": saved["bytes"],
        "exitCode": saved["exitCode"],
    }


def _text_field(document: dict[str, object], key: str) -> str:
    """Read one required text field of a saved capture.

    Returns:
        The field's text.

    Raises:
        ValueError: The field is not text.

    """
    value: object = document[key]
    if not isinstance(value, str):
        message: str = f"saved capture field {key} is not text"
        raise ValueError(message)  # ruff: ignore[type-check-without-type-error] - callers handle ValueError as the invalid-capture signal.
    return value


def _int_field(document: dict[str, object], key: str, message: str) -> int:
    """Read one required integer (not boolean) field of a saved capture.

    Returns:
        The field's integer.

    Raises:
        ValueError: The field is not an integer.

    """
    value: object = document[key]
    if type(value) is not int:
        raise ValueError(message)
    return value


def load(path: Path, request: str, command_sha: str) -> LoadedCapture:
    """Read only the exact invocation and validate all saved byte bindings.

    Returns:
        The validated capture.

    Raises:
        ValueError: The capture is not a JSON object, belongs to another invocation or command,
            or its bytes or process status do not match its receipt.

    """
    parsed: object = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(parsed, dict):
        message: str = "saved capture is not a JSON object"
        raise ValueError(message)  # ruff: ignore[type-check-without-type-error] - callers handle ValueError as the invalid-capture signal.
    document: dict[str, object] = {str(key): value for key, value in parsed.items()}
    if document["request"] != request or document["commandSha256"] != command_sha:
        message = "capture belongs to a different invocation or command"
        raise ValueError(message)
    stdout: object = document["stdout"]
    if (
        not isinstance(stdout, str)
        or len(stdout) > MAX_BYTES
        or document["bytes"] != len(stdout)
        or document["sha256"] != digest(stdout)
    ):
        message = "saved capture bytes do not match their receipt"
        raise ValueError(message)
    exit_code: int = _int_field(document, "exitCode", "saved capture has no integer process status")
    return {
        "request": request,
        "commandSha256": command_sha,
        "sha256": _text_field(document, "sha256"),
        "bytes": _int_field(document, "bytes", "saved capture bytes do not match their receipt"),
        "exitCode": exit_code,
        "stdout": stdout,
    }


def _load_registered(directory: Path, request: str, execution: str) -> LoadedCapture | None:
    """Load the saved capture of a registered request that belongs to this execution.

    Returns:
        The validated capture, or None when no result file exists.

    Raises:
        ValueError: The request is invalid or registered for another execution.

    """
    document = load_request(directory, request)
    if document["executionId"] != execution:
        message: str = "registered result belongs to another execution"
        raise ValueError(message)
    path: Path = directory / f"{request}.json"
    if not path.exists():
        return None
    return load(path, request, document["commandSha256"])


def registered_result(directory: Path, request: str, execution: str) -> RegisteredResult:
    """Materialize the exact current registered capture for the handoff hook.

    Returns:
        The completed capture, or the unknown / not-started state with the reason in `error`.

    """
    result: RegisteredResult = {
        "state": "unknown",
        "exitCode": 0,
        "stdout": "",
        "receipt": None,
        "bridge": True,
        "error": "",
    }
    try:
        saved: LoadedCapture | None = _load_registered(directory, request, execution)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["error"] = str(exc)
        return result
    if saved is None:
        claimed: bool = (directory / f"{request}.claim").exists()
        result["state"] = "unknown" if claimed else "not-started"
        result["error"] = (
            "command outcome unknown; claim exists"
            if claimed
            else "registered command never started; no claim or result exists"
        )
        return result
    return {
        **result,
        "state": "completed",
        "exitCode": saved["exitCode"],
        "stdout": saved["stdout"],
        "receipt": receipt(saved),
    }


def _is_digest(value: str) -> bool:
    """Tell whether a value is a lowercase SHA-256 hex digest.

    Returns:
        True when the value has 64 lowercase hex digits.

    """
    return len(value) == DIGEST_LENGTH and all(c in HEX_DIGITS for c in value)


def _parse_command(argv_json: str) -> list[str]:
    """Parse the JSON command line a capture runs.

    Returns:
        The nonempty argv.

    Raises:
        ValueError: The JSON is not a nonempty array of strings.

    """
    parsed: object = json.loads(argv_json)
    if not isinstance(parsed, list) or not parsed:
        message: str = "command must be a nonempty string array"
        raise ValueError(message)
    command: list[str] = []
    for word in parsed:
        if not isinstance(word, str):
            message = "command must be a nonempty string array"
            raise ValueError(message)  # ruff: ignore[type-check-without-type-error] - callers handle ValueError as the invalid-request signal.
        command.append(word)
    return command


def _optional_text(namespace: argparse.Namespace, name: str) -> str | None:
    """Read an optional text option argparse produced.

    Returns:
        The text, or None when the option was not given.

    Raises:
        TypeError: argparse produced a value of another type.

    """
    value: object = getattr(namespace, name)
    if value is None or isinstance(value, str):
        return value
    message: str = f"option {name} is not text"
    raise TypeError(message)


def parse_options(argv: list[str] | None) -> Options:
    """Parse and validate the command line, resolving a registered request.

    Returns:
        The validated options.

    Raises:
        ValueError: The argv checksum, request or command digest is invalid.
        TypeError: argparse produced a value of an unexpected type.

    """
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
    namespace: argparse.Namespace = parser.parse_args(rest)
    raw_operation: object = namespace.operation
    directory: object = namespace.directory
    request: object = namespace.request
    command_sha: object = namespace.command_sha256
    index: object = namespace.index
    if (
        not isinstance(directory, Path)
        or not isinstance(request, str)
        or not isinstance(command_sha, str)
        or not (index is None or isinstance(index, int))
    ):
        message: str = "argparse produced options of unexpected types"
        raise TypeError(message)
    argv_json: str | None = _optional_text(namespace, "argv_json")
    operation: Operation
    registered: bool = raw_operation in {"registered", "registered-result"}
    if registered:
        document = load_request(directory, request, wait_seconds=REGISTRY_WAIT_SECONDS)
        command_sha = document["commandSha256"]
        argv_json = json.dumps(document["argv"])
        operation = "capture" if raw_operation == "registered" else "manifest"
    elif raw_operation in {"capture", "manifest", "chunk"}:
        operation = "capture" if raw_operation == "capture" else "manifest" if raw_operation == "manifest" else "chunk"
    else:
        message = f"unknown operation {raw_operation!r}"
        raise ValueError(message)
    if not _is_digest(request) or not _is_digest(command_sha):
        message = "invalid request or command digest"
        raise ValueError(message)
    command: list[str] | None = None
    if operation == "capture":
        if argv_json is None:
            message = "command must be a nonempty string array"
            raise ValueError(message)
        command = _parse_command(argv_json)
        if digest(relay.canonical(command)) != command_sha:
            message = "command digest mismatch"
            raise ValueError(message)
    return Options(
        operation=operation,
        registered=registered,
        directory=directory,
        request=request,
        command_sha256=command_sha,
        index=index,
        sha256=_optional_text(namespace, "sha256"),
        command=command,
    )


def capture_once(options: Options, command: list[str], path: Path) -> None:
    """Run the command once and save its output, unless a capture or claim already exists.

    Raises:
        ValueError: An earlier claim exists with no result, or the output exceeds the bound.

    """
    options.directory.mkdir(parents=True, exist_ok=True)
    # A claim survives interruption: an unknown outcome must never run again.
    claim: Path = path.with_suffix(".claim")
    if path.exists():
        return
    try:
        descriptor: int = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        message: str = "capture outcome unknown; original command will not repeat"
        raise ValueError(message) from exc
    os.close(descriptor)
    done: subprocess.CompletedProcess[bytes] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Digest-bound registered argv; shell disabled.
        command,
        capture_output=True,
        timeout=CAPTURE_TIMEOUT_SECONDS,
        check=False,
    )
    stdout: str = done.stdout.decode("ascii")
    if len(stdout) > MAX_BYTES:
        message = "capture exceeds bounded transport size"
        raise ValueError(message)
    saved: SavedCapture = {
        "request": options.request,
        "commandSha256": options.command_sha256,
        "sha256": digest(stdout),
        "bytes": len(stdout),
        "exitCode": done.returncode,
        "stdout": stdout,
        "stderr": done.stderr.decode("utf-8", errors="replace"),
    }
    temporary: Path = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(saved, ensure_ascii=True), encoding="ascii")
    temporary.replace(path)


def build_report(options: Options, saved: LoadedCapture) -> dict[str, ReportValue]:
    """Build the JSON report the operation prints.

    Returns:
        The report: the receipt, plus the output for a capture or one chunk for a chunk.

    Raises:
        ValueError: The chunk digest or index does not match the capture.

    """
    if options.registered:
        # Payload travels through the command runner's StructuredOutput hook, not tokens.
        return {
            "state": "completed",
            "exitCode": saved["exitCode"],
            "stdout": "",
            "receipt": receipt(saved),
            "bridge": False,
            "error": "",
        }
    report: dict[str, ReportValue] = {"receipt": receipt(saved)}
    if options.operation == "capture":
        report.update(exitCode=saved["exitCode"], stdout=saved["stdout"])
    elif options.operation == "chunk":
        if options.sha256 != saved["sha256"]:
            message: str = "chunk receipt digest mismatch"
            raise ValueError(message)
        count: int = (saved["bytes"] + CHUNK_SIZE - 1) // CHUNK_SIZE
        if options.index is None or options.index < 0 or options.index >= count:
            message = "chunk index out of range"
            raise ValueError(message)
        chunk: str = saved["stdout"][options.index * CHUNK_SIZE : (options.index + 1) * CHUNK_SIZE]
        report.update(index=options.index, chunk=chunk, sha256=digest(chunk))
    return report


def main(argv: list[str] | None = None) -> int:
    """Capture once, or return a manifest/chunk without executing the command.

    An invalid command line, registered request or saved capture raises ValueError from the
    helpers it calls.

    Returns:
        0 after the report is written to stdout.

    """
    options: Options = parse_options(argv)
    path: Path = options.directory / f"{options.request}.json"
    if options.command is not None:
        capture_once(options, options.command, path)
    saved: LoadedCapture = load(path, options.request, options.command_sha256)
    report: dict[str, ReportValue] = build_report(options, saved)
    sys.stdout.write(json.dumps(report, ensure_ascii=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(json.dumps({"error": str(exc)}) + "\n")
        raise SystemExit(2) from exc
