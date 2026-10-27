"""The tokens a step's sessions and their helpers used while the step ran, read from Claude Code's transcripts.

A session writes its own transcript ``<session id>.jsonl`` and one ``agent-<id>.jsonl`` per helper
it started (``agent_process.subagent_transcripts``). Each assistant line carries the usage of the
API request it came from; one request can write several lines, so each request is counted once,
with the largest value each line reports. Only requests made while the step ran count: a session
continued in a later step, or in a later dispatch, is counted in each only for its own turns.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

from typeguard import CollectionCheckStrategy, typechecked

from .agent_context import CONFIG_DIR_ENV
from .agent_process import subagent_transcripts

if TYPE_CHECKING:
    from .handback_contract import StepTokens, TokenPart, TokenUsage

COMPONENTS: Final[dict[str, str]] = {
    "input": "input_tokens",
    "cacheCreate": "cache_creation_input_tokens",
    "cacheRead": "cache_read_input_tokens",
    "output": "output_tokens",
}
"""Each usage component of ``TokenUsage`` and the transcript ``usage`` field it is read from."""

META_SUFFIX: Final = ".meta.json"
"""The suffix of the file beside a helper's transcript that names its agent type."""


@dataclass(frozen=True)
class StepSession:
    """A session a step ran or continued: its id, its working directory and its agent."""

    session: str
    cwd: Path
    agent: str


@dataclass(frozen=True)
class Window:
    """The epoch seconds a step started and ended; a request made between them is the step's."""

    start: float
    end: float


@dataclass(frozen=True)
class Measured:
    """What the transcripts of a step's sessions hold for the step, and what could not be read."""

    tokens: StepTokens
    problems: tuple[str, ...]


def config_dir() -> Path:
    """Name the Claude Code configuration directory the sessions write their transcripts under.

    Returns:
        ``CLAUDE_CONFIG_DIR``, or ``~/.claude`` when it is not set.

    """
    return Path(os.environ.get(CONFIG_DIR_ENV, str(Path.home() / ".claude"))).expanduser()


def _main_transcript(config: Path, ran: StepSession) -> Path | None:
    """Find a session's own transcript, by its working directory or else by its id alone.

    Returns:
        The transcript, or None when no projects directory holds one.

    """
    expected: Path = subagent_transcripts(config, ran.cwd, ran.session).parents[1] / f"{ran.session}.jsonl"
    if expected.is_file():
        return expected
    return next(iter((config / "projects").glob(f"*/{ran.session}.jsonl")), None)


def _helper_agent(transcript: Path) -> str:
    """Name a helper's agent type from the file beside its transcript.

    Returns:
        The agent type without the plugin prefix, or ``unknown`` when the file names none.

    """
    meta: Path = transcript.with_name(transcript.name.removesuffix(".jsonl") + META_SUFFIX)
    if not meta.is_file():
        return "unknown"
    fields: object = json.loads(meta.read_text(encoding="utf-8"))
    kind: object = fields.get("agentType") if isinstance(fields, dict) else None
    return str(kind).rsplit(":", maxsplit=1)[-1] if kind else "unknown"


def _transcripts(config: Path, ran: StepSession) -> list[tuple[Path, str, bool]]:
    """List a session's transcripts.

    Returns:
        Its own transcript, then each helper's, each with its agent and whether it is a helper;
        empty when the session has no transcript.

    """
    main: Path | None = _main_transcript(config, ran)
    if main is None:
        return []
    helpers: Path = main.parent / ran.session / "subagents"
    found: list[tuple[Path, str, bool]] = [(main, ran.agent, False)]
    found.extend((path, _helper_agent(path), True) for path in sorted(helpers.glob("*.jsonl")))
    return found


def _request(line: str, window: Window) -> tuple[str, dict[str, int]] | None:
    """Read the request id and usage of one transcript line made within the window.

    Returns:
        The id and the usage components, or None for a line that is no assistant turn with
        usage, or was made outside the window.

    """
    if '"usage"' not in line:
        return None
    event: object = json.loads(line)
    if not isinstance(event, dict) or event.get("type") != "assistant":
        return None
    message: object = event.get("message")
    usage: object = message.get("usage") if isinstance(message, dict) else None
    made: float = datetime.fromisoformat(str(event.get("timestamp"))).timestamp()
    if not isinstance(message, dict) or not isinstance(usage, dict) or not window.start <= made <= window.end:
        return None
    key: str = str(message.get("id") or event.get("requestId") or event.get("uuid"))
    return key, {name: int(usage.get(field) or 0) for name, field in COMPONENTS.items()}


def _usage(path: Path, window: Window) -> tuple[TokenUsage, int]:
    """Sum the usage of one transcript's requests made within the window, each request once.

    Returns:
        The usage, and the number of lines that are not JSON (a line cut off when its session was
        stopped), which are not counted.

    """
    best: dict[str, dict[str, int]] = {}
    broken: int = 0
    line: str
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            found: tuple[str, dict[str, int]] | None = _request(line, window)
        except ValueError:
            broken += 1
            continue
        if found is not None:
            slot: dict[str, int] = best.setdefault(found[0], dict.fromkeys(COMPONENTS, 0))
            slot.update({name: max(slot[name], value) for name, value in found[1].items()})
    sums: dict[str, int] = {name: sum(slot[name] for slot in best.values()) for name in COMPONENTS}
    usage: TokenUsage = {
        "input": sums["input"],
        "cacheCreate": sums["cacheCreate"],
        "cacheRead": sums["cacheRead"],
        "output": sums["output"],
        "total": sum(sums.values()),
        "turns": len(best),
    }
    return usage, broken


def _total(parts: list[TokenPart]) -> TokenUsage:
    """Add the usage of every part.

    Returns:
        The sum of each component, of the totals and of the turns.

    """
    return {
        "input": sum(part["input"] for part in parts),
        "cacheCreate": sum(part["cacheCreate"] for part in parts),
        "cacheRead": sum(part["cacheRead"] for part in parts),
        "output": sum(part["output"] for part in parts),
        "total": sum(part["total"] for part in parts),
        "turns": sum(part["turns"] for part in parts),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def measure(sessions: list[StepSession], window: Window, config: Path) -> Measured:
    """Measure the tokens a step's sessions and their helpers used within the step's window.

    Args:
        sessions: The sessions the step ran or continued, each once.
        window: When the step started and ended.
        config: The Claude Code configuration directory (:func:`config_dir`).

    Returns:
        The step's usage with one part per transcript that made a request within the window,
        and a problem for each session with no transcript and each transcript with lines that
        are not JSON. A transcript that cannot be read raises ``OSError``.

    """
    parts: list[TokenPart] = []
    problems: list[str] = []
    ran: StepSession
    for ran in sessions:
        files: list[tuple[Path, str, bool]] = _transcripts(config, ran)
        if not files:
            problems.append(f"session {ran.session} ({ran.agent}) has no transcript under {config / 'projects'}")
        path: Path
        agent: str
        helper: bool
        for path, agent, helper in files:
            usage: TokenUsage
            broken: int
            usage, broken = _usage(path, window)
            if broken:
                problems.append(f"{path} has {broken} line(s) that are not JSON, not counted")
            if usage["turns"]:
                parts.append({**usage, "session": ran.session, "agent": agent, "helper": helper})
    return Measured({"usage": _total(parts), "parts": parts}, tuple(problems))
