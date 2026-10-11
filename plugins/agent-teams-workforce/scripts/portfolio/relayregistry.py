"""Validate a canonical command registered by the deterministic workflow host."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import TYPE_CHECKING, Final, Literal, TypedDict

import relay

if TYPE_CHECKING:
    from pathlib import Path

    from contracts import JsonInput

HEX: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}")
FIELDS: Final[frozenset[str]] = frozenset(
    {"version", "executionId", "invocation", "ordinal", "request", "commandSha256", "argv"},
)


class RegisteredRequest(TypedDict):
    """The exact immutable command document the workflow host registers."""

    version: Literal[1]
    executionId: str
    invocation: str
    ordinal: int
    request: str
    commandSha256: str
    argv: list[str]


def checksum(value: JsonInput) -> str:
    """Hash the canonical JSON form of a value.

    Returns:
        The SHA-256 hex digest.

    """
    return hashlib.sha256(relay.canonical(value).encode("ascii")).hexdigest()


def load_request(directory: Path, request: str, wait_seconds: float = 0) -> RegisteredRequest:
    """Read only a complete immutable request; never take argv from model text.

    Returns:
        The validated registered request.

    Raises:
        ValueError: The request id or document is invalid.

    """
    if not HEX.fullmatch(request):
        message = "invalid registered request id"
        raise ValueError(message)
    path: Path = directory / f"{request}.request.json"
    deadline: float = time.monotonic() + wait_seconds
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    document: object = json.loads(path.read_text(encoding="ascii"))
    return validate_request(document, request)


def _exact_int(value: object) -> int | None:
    # JSON booleans and floats compare equal to integers; the contract is an exact integer.
    return value if type(value) is int else None


def _argv(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        message = "invalid registered command argv"
        raise ValueError(message)
    words: list[str] = []
    for word in value:
        if not isinstance(word, str) or "\0" in word:
            message = "invalid registered command argv"
            raise ValueError(message)
        words.append(word)
    return words


def validate_request(document: object, request: str) -> RegisteredRequest:
    """Validate identity and argv independently of their transport or storage.

    Returns:
        The validated registered request.

    Raises:
        ValueError: The document is not the exact registered command contract.

    """
    if not isinstance(document, dict) or set(document) != FIELDS or _exact_int(document["version"]) != 1:
        message = "invalid registered command document"
        raise ValueError(message)
    execution: object = document["executionId"]
    invocation: object = document["invocation"]
    ordinal: int | None = _exact_int(document["ordinal"])
    if (
        not isinstance(execution, str)
        or not execution
        or not isinstance(invocation, str)
        or ordinal is None
        or ordinal < 0
    ):
        message = "invalid registered execution identity"
        raise ValueError(message)
    argv: list[str] = _argv(document["argv"])
    command: object = document["commandSha256"]
    stated: object = document["request"]
    if not isinstance(command, str) or command != checksum(argv):
        message = "registered command argv checksum mismatch"
        raise ValueError(message)
    identity: dict[str, str | int] = {
        "execution": execution,
        "invocation": invocation,
        "ordinal": ordinal,
        "commandSha256": command,
    }
    if not isinstance(stated, str) or stated != request or checksum(identity) != request:
        message = "registered command request identity mismatch"
        raise ValueError(message)
    return {
        "version": 1,
        "executionId": execution,
        "invocation": invocation,
        "ordinal": ordinal,
        "request": stated,
        "commandSha256": command,
        "argv": argv,
    }
