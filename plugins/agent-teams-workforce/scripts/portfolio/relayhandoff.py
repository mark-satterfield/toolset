"""Replace only a bound command runner's StructuredOutput with saved machine bytes."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import relay
from relaycapture import CaptureReceipt, RegisteredResult, registered_result
from relayregistry import RegisteredRequest, validate_request

if TYPE_CHECKING:
    from contracts import JsonInput, JsonObject

PREFIX: Final[str] = "WORKFORCE_RELAY_BINDING_V1 "
REQUEST_PREFIX: Final[str] = "WORKFORCE_RELAY_REQUEST_V1 "
AGENT: Final[str] = "workflow-command-runner"
TOOLS: Final[frozenset[str]] = frozenset({"Bash", "StructuredOutput"})
BINDING_KEYS: Final[frozenset[str]] = frozenset({"executionId", "request", "directory", "operation"})
TASK_FRAME: Final[str] = "[Workflow harness — computed task] "
TASK_FRAME_END: Final[str] = "The computed task text follows:"

type Operation = Literal["registered", "registered-result"]
type HookEvent = Mapping[str, object]


@dataclass(frozen=True, slots=True)
class Binding:
    """The original handoff binding and the registered request it names."""

    execution_id: str
    request: str
    directory: str
    operation: Operation
    document: RegisteredRequest


def _is_runner(event: HookEvent) -> bool:
    """Tell whether the event is a relayed tool call of the command runner.

    Returns:
        True when the tool and agent type are the bound command runner's.

    """
    return (
        event.get("tool_name") in TOOLS
        and str(event.get("agent_type", "")).removeprefix("agent-teams-workforce:") == AGENT
    )


def _document_json(document: RegisteredRequest) -> Mapping[str, JsonInput]:
    """Spell a registered request as a JSON object.

    Returns:
        The request's fields as a JSON mapping.

    """
    return {
        "version": document["version"],
        "executionId": document["executionId"],
        "invocation": document["invocation"],
        "ordinal": document["ordinal"],
        "request": document["request"],
        "commandSha256": document["commandSha256"],
        "argv": document["argv"],
    }


def _runner_transcript(event: HookEvent, agent_id: str) -> Path:
    """Find the one transcript of this command runner and confirm its agent type.

    Returns:
        The path of the runner's transcript.

    Raises:
        TypeError: When the transcript path is not text.
        ValueError: When the transcript is absent, ambiguous or not the command runner's.

    """
    raw_transcript: object = event["transcript_path"]
    if not isinstance(raw_transcript, str):
        message: str = "handoff transcript path is not text"
        raise TypeError(message)
    transcript: Path = Path(raw_transcript)
    expected: str = f"agent-{agent_id}.jsonl"
    candidates: list[Path] = (
        [transcript]
        if transcript.name == expected
        else list(transcript.with_suffix("").glob(f"subagents/**/{expected}"))
    )
    if len(candidates) != 1:
        message = "current command runner transcript is absent or ambiguous"
        raise ValueError(message)
    path: Path = candidates[0]
    meta: object = json.loads(path.with_suffix(".meta.json").read_text())
    if not isinstance(meta, dict) or str(meta.get("agentType", "")).removeprefix("agent-teams-workforce:") != AGENT:
        message = "current transcript is not the command runner"
        raise ValueError(message)
    return path


def _user_text(line: str) -> str | None:
    """Read the text of one transcript line when it is a user message.

    Returns:
        The message text, or None when the line is not a user message.

    Raises:
        TypeError: When the line or its message is not a JSON object, or its content is neither text
            nor a list of text blocks.

    """
    record: object = json.loads(line)
    if not isinstance(record, dict):
        message: str = "transcript line is not a JSON object"
        raise TypeError(message)
    entry: object = record.get("message", {})
    if not isinstance(entry, dict):
        message = "transcript message is not a JSON object"
        raise TypeError(message)
    if entry.get("role") != "user":
        return None
    content: object = entry.get("content")
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if not isinstance(content, list):
        message = "transcript message content is neither text nor a list of blocks"
        raise TypeError(message)
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text: object = block.get("text", "")
            if not isinstance(text, str):
                message = "transcript text block is not text"
                raise TypeError(message)
            parts.append(text)
    return "\n".join(parts)


def _unframe(text: str) -> str:
    """Strip the workflow harness frame from a computed task assignment.

    Returns:
        The assignment text with its frame and indentation removed, or the text unchanged when unframed.

    Raises:
        ValueError: When the frame is unrecognized or a frame line is unindented.

    """
    if not text.startswith(TASK_FRAME):
        return text
    header, separator, body = text.partition("\n")
    if not separator or not header.endswith(TASK_FRAME_END):
        message: str = "unrecognized workflow assignment frame"
        raise ValueError(message)
    lines: list[str] = body.splitlines()
    if any(not line.startswith("  ") for line in lines):
        message = "workflow assignment has an unindented frame line"
        raise ValueError(message)
    return "\n".join(line[2:] for line in lines)


def _binding(text: str) -> Binding | None:
    """Parse the one original binding and its canonical request from an assignment.

    Returns:
        The validated binding, or None for a legacy replay with no registered protocol.

    Raises:
        ValueError: When the binding or its request is missing, ambiguous, invalid or not canonical.

    """
    bindings: list[object] = [
        json.loads(value[len(PREFIX) :]) for value in text.splitlines() if value.startswith(PREFIX)
    ]
    if not bindings:
        return None
    if len(bindings) != 1:
        message: str = "ambiguous original handoff binding"
        raise ValueError(message)
    raw: object = bindings[0]
    if not isinstance(raw, dict) or set(raw) != BINDING_KEYS:
        message = "invalid original handoff binding"
        raise ValueError(message)
    execution_id: object = raw["executionId"]
    request: object = raw["request"]
    directory: object = raw["directory"]
    operation: object = raw["operation"]
    if not (
        isinstance(execution_id, str)
        and execution_id
        and isinstance(request, str)
        and request
        and isinstance(directory, str)
        and directory
        and isinstance(operation, str)
        and operation
        and Path(directory).is_absolute()
    ):
        message = "invalid original handoff binding"
        raise ValueError(message)
    if operation not in {"registered", "registered-result"}:
        message = "invalid registered operation"
        raise ValueError(message)
    requests: list[str] = [
        value[len(REQUEST_PREFIX) :] for value in text.splitlines() if value.startswith(REQUEST_PREFIX)
    ]
    if len(requests) != 1:
        message = "original assignment lacks one canonical command request"
        raise ValueError(message)
    document: RegisteredRequest = validate_request(json.loads(requests[0]), request)
    if requests[0] != relay.canonical(_document_json(document)) or document["executionId"] != execution_id:
        message = "original request is not canonical or belongs to another execution"
        raise ValueError(message)
    checked: Operation = "registered" if operation == "registered" else "registered-result"
    return Binding(execution_id, request, directory, checked, document)


def assignment(event: HookEvent) -> Binding | None:
    """Locate this exact subagent's original assignment, never tool-result text.

    Returns:
        The original binding, or None when the event is not the command runner's or carries no binding.

    Raises:
        ValueError: When the agent id, transcript or original assignment is unsafe or invalid.

    """
    if not _is_runner(event):
        return None
    agent_id: object = event.get("agent_id", "")
    if not isinstance(agent_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", agent_id):
        message: str = "handoff has no safe current agent id"
        raise ValueError(message)
    path: Path = _runner_transcript(event, agent_id)
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            text: str | None = _user_text(line)
            if text is not None:
                return _binding(_unframe(text))
    message = "current command runner has no original user assignment"
    raise ValueError(message)


def stage(binding: Binding) -> None:
    """Atomically register the original machine assignment, never model tool input.

    Raises:
        ValueError: When an existing registered request file differs from the original assignment.

    """
    directory: Path = Path(binding.directory)
    directory.mkdir(parents=True, exist_ok=True)
    path: Path = directory / f"{binding.request}.request.json"
    data: bytes = relay.canonical(_document_json(binding.document)).encode("ascii")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            if path.read_bytes() != data:
                message: str = "registered request file differs from original assignment"
                raise ValueError(message) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _bash_update(binding: Binding) -> JsonObject:
    """Stage the request and rewrite the runner's Bash call to the registered capture.

    Returns:
        The PreToolUse hook output that replaces the Bash input.

    """
    stage(binding)
    helper: Path = Path(__file__).resolve().with_name("relaycapture.py")
    command: str = shlex.join(
        [
            sys.executable,
            str(helper),
            binding.operation,
            "--directory",
            binding.directory,
            "--request",
            binding.request,
        ],
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {
                "command": command,
                "timeout": 600000,
                "run_in_background": False,
                "description": "Execute the registered deterministic workflow request",
            },
        },
    }


def handoff(event: HookEvent) -> JsonObject:
    """Rewrite a tool input as a transport operation, never as semantic acceptance.

    Returns:
        The PreToolUse hook output, or an empty object when the event is not the bound runner's.

    """
    try:
        binding: Binding | None = assignment(event)
        if binding is None:
            return {}
        if event["tool_name"] == "Bash":
            return _bash_update(binding)
        result: RegisteredResult = registered_result(
            Path(binding.directory),
            binding.request,
            binding.execution_id,
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        if not _is_runner(event):
            return {}
        if event.get("tool_name") == "Bash":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"deterministic relay assignment invalid: {exc}",
                },
            }
        result = {
            "state": "unknown",
            "exitCode": 0,
            "stdout": "",
            "receipt": None,
            "bridge": True,
            "error": f"deterministic relay handoff unavailable: {exc}",
        }
    return {
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": _result_json(result)},
    }


def _result_json(result: RegisteredResult) -> JsonObject:
    """Spell a registered result as a JSON object.

    Returns:
        The result's fields, with its receipt as a nested object or null.

    """
    receipt: CaptureReceipt | None = result["receipt"]
    return {
        "state": result["state"],
        "exitCode": result["exitCode"],
        "stdout": result["stdout"],
        "receipt": None
        if receipt is None
        else {
            "request": receipt["request"],
            "commandSha256": receipt["commandSha256"],
            "sha256": receipt["sha256"],
            "bytes": receipt["bytes"],
            "exitCode": receipt["exitCode"],
        },
        "bridge": result["bridge"],
        "error": result["error"],
    }


def _event(raw: object) -> dict[str, object]:
    """Narrow the hook's JSON input to an event object.

    Returns:
        The event with its text keys.

    Raises:
        TypeError: When the hook input is not a JSON object.

    """
    if not isinstance(raw, dict):
        message: str = "hook input is not a JSON object"
        raise TypeError(message)
    return {key: value for key, value in raw.items() if isinstance(key, str)}


if __name__ == "__main__":
    sys.stdout.write(
        json.dumps(
            handoff(_event(json.load(sys.stdin))),
            ensure_ascii=True,
            separators=(",", ":"),
        )
        + "\n",
    )
