"""The tokens a step's sessions and their helpers used while the step ran, read from Claude Code's transcripts.

A session writes its own transcript ``<session id>.jsonl`` and one ``agent-<id>.jsonl`` per helper
it started (``agent_process.subagent_transcripts``). Each assistant line carries the usage of the
API request it came from; one request can write several lines, so each request is counted once,
with the largest value each line reports. Only requests made while the step ran count: a session
continued in a later step, or in a later dispatch, is counted in each only for its own turns.

A transcript only grows while its session runs, so each one is read incrementally: a cursor per
file keeps the byte offset of the last complete line read and the requests read so far, and a
later measurement reads only the bytes appended since. A file replaced (another device or inode),
shortened, or whose first bytes changed is read again from its start. A line still being written
(no line end yet) is read for the measurement but not kept. A request whose usage lacks one of the
components is counted with that component as 0 and reported as unknown usage, never hidden.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
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

HEAD_BYTES: Final = 256
"""How many leading bytes of a transcript identify it between incremental reads."""

READ_TOOL: Final = "Read"
"""The tool whose calls count as artifact reads."""


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
    """What the transcripts of a step's sessions hold for the step, and what could not be read.

    ``bytes_read`` is how many transcript bytes this measurement read, ``read_calls`` the file
    reads the sessions requested within the window, and ``unknown_usage`` the requests whose usage
    lacked a component.
    """

    tokens: StepTokens
    problems: tuple[str, ...]
    bytes_read: int = 0
    read_calls: int = 0
    unknown_usage: int = 0


@dataclass(frozen=True)
class _Request:
    """One transcript line of an assistant turn with usage."""

    key: str
    made: float
    usage: dict[str, int]
    unknown: bool
    reads: frozenset[str]


@dataclass
class _Cursor:
    """How far a transcript was read, and the request lines read from it."""

    device: int
    inode: int
    head: bytes
    offset: int = 0
    broken: int = 0
    requests: list[_Request] = field(default_factory=list)


@dataclass(frozen=True)
class _Scan:
    """What one transcript holds now: its kept lines plus a line still being written."""

    requests: tuple[_Request, ...]
    broken: int
    bytes_read: int


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


def _read_ids(message: dict[str, object]) -> frozenset[str]:
    """Collect the ids of the file reads an assistant turn requested.

    Returns:
        The tool-use id of each ``Read`` call in the message content.

    """
    content: object = message.get("content")
    blocks: list[object] = content if isinstance(content, list) else []
    return frozenset(
        str(block.get("id"))
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == READ_TOOL
    )


def _request(line: str) -> _Request | None:
    """Read the request id, time and usage of one transcript line.

    A line that is not JSON, or whose time or a usage component cannot be read, raises
    ``ValueError``.

    Returns:
        The request line, or None for a line that is no assistant turn with usage.

    """
    if '"usage"' not in line:
        return None
    event: object = json.loads(line)
    if not isinstance(event, dict) or event.get("type") != "assistant":
        return None
    message: object = event.get("message")
    usage: object = message.get("usage") if isinstance(message, dict) else None
    made: float = datetime.fromisoformat(str(event.get("timestamp"))).timestamp()
    if not isinstance(message, dict) or not isinstance(usage, dict):
        return None
    key: str = str(message.get("id") or event.get("requestId") or event.get("uuid"))
    unknown: bool = any(usage.get(source) is None for source in COMPONENTS.values())
    components: dict[str, int] = {name: int(usage.get(source) or 0) for name, source in COMPONENTS.items()}
    return _Request(key, made, components, unknown, _read_ids(message))


def _parse(text: str) -> tuple[list[_Request], int]:
    """Read the request lines of transcript text.

    Returns:
        The request lines, and the number of lines that are not JSON (a line cut off when its
        session was stopped), which are not counted.

    """
    found: list[_Request] = []
    broken: int = 0
    line: str
    for line in text.splitlines():
        try:
            held: _Request | None = _request(line)
        except ValueError:
            broken += 1
            continue
        if held is not None:
            found.append(held)
    return found, broken


class _Cursors:
    """The incremental read position of every transcript this process measured."""

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._cursors: dict[Path, _Cursor] = {}

    def scan(self, path: Path) -> _Scan:
        """Read the bytes a transcript gained since its last scan.

        A transcript that cannot be read raises ``OSError``.

        Returns:
            Every request line the file holds, the lines that are not JSON, and the bytes read.

        """
        with self._lock:
            with path.open("rb") as handle:
                status: os.stat_result = os.fstat(handle.fileno())
                head: bytes = handle.read(HEAD_BYTES)
                cursor: _Cursor | None = self._cursors.get(path)
                if cursor is None or not _continues(cursor, status, head):
                    cursor = _Cursor(status.st_dev, status.st_ino, head)
                    self._cursors[path] = cursor
                handle.seek(cursor.offset)
                appended: bytes = handle.read()
            complete: int = appended.rfind(b"\n") + 1
            kept, broken = _parse(appended[:complete].decode("utf-8", errors="replace"))
            pending, pending_broken = _parse(appended[complete:].decode("utf-8", errors="replace"))
            cursor.requests.extend(kept)
            cursor.broken += broken
            cursor.offset += complete
            return _Scan((*cursor.requests, *pending), cursor.broken + pending_broken, len(head) + len(appended))


def _continues(cursor: _Cursor, status: os.stat_result, head: bytes) -> bool:
    """Tell whether a transcript is the same file, grown, since its cursor was taken.

    Returns:
        True when the device and inode match, the file is not shorter than the cursor's offset,
        and its leading bytes still begin with the ones the cursor saw.

    """
    return (
        (cursor.device, cursor.inode) == (status.st_dev, status.st_ino)
        and status.st_size >= cursor.offset
        and head[: len(cursor.head)] == cursor.head
    )


_CURSORS: Final = _Cursors()
"""The process's transcript cursors; disposable, a miss reads the file from its start."""


@dataclass(frozen=True)
class _Usage:
    """One transcript's usage within a window, with what its reading found."""

    usage: TokenUsage
    broken: int
    bytes_read: int
    read_calls: int
    unknown: int


def _usage(path: Path, window: Window) -> _Usage:
    """Sum the usage of one transcript's requests made within the window, each request once.

    Returns:
        The usage, the lines that are not JSON (not counted), the bytes read, the file reads
        requested and the requests with unknown usage.

    """
    scan: _Scan = _CURSORS.scan(path)
    best: dict[str, dict[str, int]] = {}
    unknown: set[str] = set()
    reads: set[str] = set()
    held: _Request
    for held in (request for request in scan.requests if window.start <= request.made <= window.end):
        slot: dict[str, int] = best.setdefault(held.key, dict.fromkeys(COMPONENTS, 0))
        slot.update({name: max(slot[name], value) for name, value in held.usage.items()})
        unknown.update({held.key} if held.unknown else set())
        reads.update(held.reads)
    sums: dict[str, int] = {name: sum(slot[name] for slot in best.values()) for name in COMPONENTS}
    usage: TokenUsage = {
        "input": sums["input"],
        "cacheCreate": sums["cacheCreate"],
        "cacheRead": sums["cacheRead"],
        "output": sums["output"],
        "total": sum(sums.values()),
        "turns": len(best),
    }
    return _Usage(usage, scan.broken, scan.bytes_read, len(reads), len(unknown))


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
    totals: list[_Usage] = []
    ran: StepSession
    for ran in sessions:
        files: list[tuple[Path, str, bool]] = _transcripts(config, ran)
        if not files:
            problems.append(f"session {ran.session} ({ran.agent}) has no transcript under {config / 'projects'}")
        path: Path
        agent: str
        helper: bool
        for path, agent, helper in files:
            read: _Usage = _usage(path, window)
            totals.append(read)
            if read.broken:
                problems.append(f"{path} has {read.broken} line(s) that are not JSON, not counted")
            if read.unknown:
                problems.append(f"{path} has {read.unknown} request(s) whose usage lacks a component, counted as 0")
            if read.usage["turns"]:
                parts.append({**read.usage, "session": ran.session, "agent": agent, "helper": helper})
    return Measured(
        {"usage": _total(parts), "parts": parts},
        tuple(problems),
        bytes_read=sum(read.bytes_read for read in totals),
        read_calls=sum(read.read_calls for read in totals),
        unknown_usage=sum(read.unknown for read in totals),
    )
