"""Replace only a bound command runner's StructuredOutput with saved machine bytes."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

import relay
from relaycapture import registered_result
from relayregistry import validate_request

PREFIX = "WORKFORCE_RELAY_BINDING_V1 "
REQUEST_PREFIX = "WORKFORCE_RELAY_REQUEST_V1 "
AGENT = "workflow-command-runner"


def assignment(event: dict) -> dict | None:
    """Locate this exact subagent's original assignment, never tool-result text."""
    if (
        event.get("tool_name") not in {"Bash", "StructuredOutput"}
        or str(event.get("agent_type", "")).removeprefix("agent-teams-workforce:")
        != AGENT
    ):
        return None
    agent_id = event.get("agent_id", "")
    if not isinstance(agent_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", agent_id):
        raise ValueError("handoff has no safe current agent id")
    transcript = Path(event["transcript_path"])
    expected = f"agent-{agent_id}.jsonl"
    candidates = (
        [transcript]
        if transcript.name == expected
        else list(transcript.with_suffix("").glob(f"subagents/**/{expected}"))
    )
    if len(candidates) != 1:
        raise ValueError("current command runner transcript is absent or ambiguous")
    path = candidates[0]
    meta = json.loads(path.with_suffix(".meta.json").read_text())
    if str(meta.get("agentType", "")).removeprefix("agent-teams-workforce:") != AGENT:
        raise ValueError("current transcript is not the command runner")
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            message = json.loads(line).get("message", {})
            if message.get("role") != "user":
                continue
            content = message.get("content")
            text = (
                content
                if isinstance(content, str)
                else "\n".join(
                    block.get("text", "")
                    for block in content or []
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            )
            if text.startswith("[Workflow harness — computed task] "):
                header, separator, body = text.partition("\n")
                if not separator or not header.endswith(
                    "The computed task text follows:"
                ):
                    raise ValueError("unrecognized workflow assignment frame")
                lines = body.splitlines()
                if any(not line.startswith("  ") for line in lines):
                    raise ValueError("workflow assignment has an unindented frame line")
                text = "\n".join(line[2:] for line in lines)
            bindings = [
                json.loads(value[len(PREFIX) :])
                for value in text.splitlines()
                if value.startswith(PREFIX)
            ]
            if not bindings:
                return None  # Legacy replay has no registered protocol.
            if len(bindings) != 1:
                raise ValueError("ambiguous original handoff binding")
            binding = bindings[0]
            if (
                not isinstance(binding, dict)
                or set(binding) != {"executionId", "request", "directory", "operation"}
                or not all(
                    isinstance(value, str) and value for value in binding.values()
                )
                or not Path(binding["directory"]).is_absolute()
            ):
                raise ValueError("invalid original handoff binding")
            if binding["operation"] not in {"registered", "registered-result"}:
                raise ValueError("invalid registered operation")
            requests = [
                value[len(REQUEST_PREFIX) :]
                for value in text.splitlines()
                if value.startswith(REQUEST_PREFIX)
            ]
            if len(requests) != 1:
                raise ValueError(
                    "original assignment lacks one canonical command request"
                )
            document = validate_request(json.loads(requests[0]), binding["request"])
            if (
                requests[0] != relay.canonical(document)
                or document["executionId"] != binding["executionId"]
            ):
                raise ValueError(
                    "original request is not canonical or belongs to another execution"
                )
            return {**binding, "document": document}
    raise ValueError("current command runner has no original user assignment")


def stage(binding: dict) -> None:
    """Atomically register the original machine assignment, never model tool input."""
    directory = Path(binding["directory"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{binding['request']}.request.json"
    data = relay.canonical(binding["document"]).encode("ascii")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError(
                    "registered request file differs from original assignment"
                )
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def handoff(event: dict) -> dict:
    """A tool input update is a transport operation, never semantic acceptance."""
    try:
        binding = assignment(event)
        if binding is None:
            return {}
        if event["tool_name"] == "Bash":
            stage(binding)
            helper = Path(__file__).resolve().with_name("relaycapture.py")
            command = shlex.join(
                [
                    sys.executable,
                    str(helper),
                    binding["operation"],
                    "--directory",
                    binding["directory"],
                    "--request",
                    binding["request"],
                ]
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
                }
            }
        result = registered_result(
            Path(binding["directory"]), binding["request"], binding["executionId"]
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        if (
            event.get("tool_name") not in {"Bash", "StructuredOutput"}
            or str(event.get("agent_type", "")).removeprefix("agent-teams-workforce:")
            != AGENT
        ):
            return {}
        if event.get("tool_name") == "Bash":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"deterministic relay assignment invalid: {exc}",
                }
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
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": result}
    }


if __name__ == "__main__":
    print(
        json.dumps(
            handoff(json.load(sys.stdin)), ensure_ascii=True, separators=(",", ":")
        )
    )
