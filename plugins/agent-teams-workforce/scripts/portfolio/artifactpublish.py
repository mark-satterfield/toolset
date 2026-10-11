"""Accept an artifact and record its provenance in one deterministic invocation.

The artifact-handoff skill owns this operation. Acceptance remains delegated to
jsonartifact.py; a rejected or pending candidate never invokes the recorder.
A recording failure is an error: the command exits 2 and names the failed recording.
"""

from __future__ import annotations

import argparse
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs the acceptor and the caller's recorder argv without a shell.
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from contracts import JsonObject, JsonValue, json_object

if TYPE_CHECKING:
    from collections.abc import Sequence

_TIMEOUT_SECONDS: Final[int] = 120
_TAIL: Final[int] = 1000
_ACCEPTOR: Final[Path] = Path(__file__).with_name("jsonartifact.py")
_RECORD_VERB_START: Final[int] = 2
_RECORD_VERB_END: Final[int] = 4
_RECORD_VERB: Final[str] = "record"


class AcceptanceError(ValueError):
    """The artifact acceptance command failed or returned an unusable result."""


class RecordingError(RuntimeError):
    """The provenance recorder could not run, timed out, or exited non-zero."""


def _tail(result: subprocess.CompletedProcess[str]) -> str:
    combined: str = (result.stdout + result.stderr).strip()
    return combined[-_TAIL:]


def _accept(accept_args: Sequence[str]) -> JsonObject:
    """Run jsonartifact.py with `accept_args` and parse its one result object.

    Returns:
        The acceptance result: a receipt or a pending probe result.

    Raises:
        AcceptanceError: Acceptance exited non-zero or printed something other than one JSON object.

    """
    accepted: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - This interpreter, a fixed sibling script and checked string args; shell disabled.
        [sys.executable, str(_ACCEPTOR), *accept_args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )
    if accepted.returncode:
        message: str = f"artifact acceptance exited {accepted.returncode}: {_tail(accepted)}"
        raise AcceptanceError(message)
    try:
        return json_object(json.loads(accepted.stdout))
    except (ValueError, TypeError) as exc:
        message = f"artifact acceptance did not return one JSON object: {exc}"
        raise AcceptanceError(message) from exc


def _record(record_argv: Sequence[str]) -> None:
    """Run the provenance recorder.

    Raises:
        RecordingError: The recorder could not start, timed out, or exited non-zero.

    """
    try:
        recorded: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - The caller's recorder argv, checked to record the accepted path; shell disabled.
            list(record_argv),
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        message: str = f"artifact recording failed to run: {str(exc)[-_TAIL:]}"
        raise RecordingError(message) from exc
    if recorded.returncode:
        message = f"artifact recording exited {recorded.returncode}: {_tail(recorded)}"
        raise RecordingError(message)


def publish(accept_args: Sequence[str], record_argv: Sequence[str]) -> JsonObject:
    """Accept the artifact, then record the accepted path's provenance.

    A recorder that cannot run, times out or exits non-zero raises RecordingError from `_record`;
    the failure is never downgraded into the returned receipt.

    Returns:
        The pending probe result unchanged, or the acceptance receipt marked recorded.

    Raises:
        TypeError: An argument violates the declared input contract.
        ValueError: The record argv is empty or does not name the accepted artifact.
        AcceptanceError: Acceptance returned no artifact path.

    """
    if not all(isinstance(item, str) for item in accept_args):
        argument_error: str = "publish: accept args must be strings"
        raise TypeError(argument_error)
    if not record_argv or not all(isinstance(item, str) and item for item in record_argv):
        message: str = "record argv must be a nonempty array of nonempty strings"
        raise ValueError(message)
    receipt: JsonObject = _accept(accept_args)
    if receipt.get("pending") is True:
        return receipt
    artifact: JsonValue = receipt.get("artifactPath")
    if not isinstance(artifact, str) or not artifact:
        message = "artifact acceptance did not return an artifact path"
        raise AcceptanceError(message)
    if list(record_argv[_RECORD_VERB_START:_RECORD_VERB_END]) != [_RECORD_VERB, artifact]:
        message = "record argv must name the accepted artifact"
        raise ValueError(message)
    _record(record_argv)
    return {**receipt, "recorded": True}


def _cli_inputs(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """Narrow argparse's untyped attributes into the acceptance args and the recorder argv.

    Returns:
        The acceptance args (a leading ``--`` removed) and the recorder argv.

    Raises:
        TypeError: An argument is not a string or the recorder JSON is not an array of strings.

    """
    record_json: object = args.record_argv_json
    forwarded: object = args.accept_args
    if not isinstance(record_json, str):
        message: str = "--record-argv-json must be a string"
        raise TypeError(message)
    if not isinstance(forwarded, list) or not all(isinstance(item, str) for item in forwarded):
        message = "acceptance arguments must be strings"
        raise TypeError(message)
    parsed: object = json.loads(record_json)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        message = "record argv must be an array of strings"
        raise TypeError(message)
    accept_args: list[str] = [item for item in forwarded if isinstance(item, str)]
    if accept_args[:1] == ["--"]:
        accept_args = accept_args[1:]
    return accept_args, [item for item in parsed if isinstance(item, str)]


def main() -> int:
    """Forward acceptance options after -- and emit one result object.

    Returns:
        Zero with the result object, or two with an error object (acceptance or recording failed).

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-argv-json", required=True)
    parser.add_argument("accept_args", nargs=argparse.REMAINDER)
    args: argparse.Namespace = parser.parse_args()
    try:
        result: JsonObject = publish(*_cli_inputs(args))
    except (OSError, TypeError, ValueError, RecordingError, subprocess.TimeoutExpired) as exc:
        sys.stdout.write(json.dumps({"error": str(exc)}) + "\n")
        return 2
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
