"""Validate a canonical command registered by the deterministic workflow host."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import relay

HEX = re.compile(r"[0-9a-f]{64}")


def checksum(value: object) -> str:
    return hashlib.sha256(relay.canonical(value).encode("ascii")).hexdigest()


def load_request(directory: Path, request: str, wait_seconds: float = 0) -> dict:
    """Read only a complete immutable request; never take argv from model text."""
    if not HEX.fullmatch(request):
        raise ValueError("invalid registered request id")
    path = directory / f"{request}.request.json"
    deadline = time.monotonic() + wait_seconds
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    document = json.loads(path.read_text(encoding="ascii"))
    return validate_request(document, request)


def validate_request(document: object, request: str) -> dict:
    """Validate identity and argv independently of their transport or storage."""
    fields = {
        "version",
        "executionId",
        "invocation",
        "ordinal",
        "request",
        "commandSha256",
        "argv",
    }
    if (
        not isinstance(document, dict)
        or set(document) != fields
        or document["version"] != 1
    ):
        raise ValueError("invalid registered command document")
    if (
        not isinstance(document["executionId"], str)
        or not document["executionId"]
        or not isinstance(document["invocation"], str)
        or type(document["ordinal"]) is not int
        or document["ordinal"] < 0
    ):
        raise ValueError("invalid registered execution identity")
    argv = document["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(word, str) or "\0" in word for word in argv)
    ):
        raise ValueError("invalid registered command argv")
    if document["commandSha256"] != checksum(argv):
        raise ValueError("registered command argv checksum mismatch")
    identity = {
        "execution": document["executionId"],
        "invocation": document["invocation"],
        "ordinal": document["ordinal"],
        "commandSha256": document["commandSha256"],
    }
    if document["request"] != request or checksum(identity) != request:
        raise ValueError("registered command request identity mismatch")
    return document
