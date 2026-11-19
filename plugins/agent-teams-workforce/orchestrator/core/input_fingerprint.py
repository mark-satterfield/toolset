"""The input fingerprint of an agent step's accepted output, so unchanged work is never run twice.

When an agent step's output is accepted, the runner records beside it, as
``<output>.inputs.json``, the fingerprint of what the session was given and read (the request,
the step's input artifacts with the content of every file and directory they name, the files of
the launch and the directories it may read) and the digest of the output itself. The agent
definition, the output contract and the plugin version are not inputs: an accepted output whose
inputs are unchanged is reused under any plugin version. A record written while the fingerprint
still held the agent definition and contract is matched by the same inputs with the agent
fingerprint of a session that could have written it. Before a later session of the same step
starts (the step was set back by any cause, in this dispatch or a later one, after any
supervisor restart), the runner computes the fingerprint again: when it equals the recorded one
and the output is the file recorded, the output is the step's result and no agent starts. A step
re-runs only when an input changed.

A directory inside a git work tree is fingerprinted by its tree at ``HEAD`` with its uncommitted
changes (``git status`` and ``git diff HEAD``), so a checkout's ignored folders are never read; any
other directory by the content of every file under it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed git argv, no shell.
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, typechecked

from .io import JsonValue, json_object, write_json

INPUTS_SUFFIX: Final = ".inputs.json"
"""The suffix of the file beside an output that records the fingerprint it was accepted with."""
INPUTS_KEY: Final = "inputs"
OUTPUT_KEY: Final = "output"
GIT_DIRECTORY: Final = ".git"
GIT_TIMEOUT_SECONDS: Final = 60
MISSING: Final = b"\0missing"
GIT_STATE_COMMANDS: Final[tuple[tuple[str, ...], ...]] = (
    ("rev-parse", "HEAD:./"),
    ("status", "--porcelain=v1", "--untracked-files=all", "--", "."),
    ("diff", "HEAD", "--binary", "--", "."),
)
"""The git reads that state a directory of a work tree: its committed tree, then its uncommitted changes."""


def _git(directory: Path, arguments: Sequence[str]) -> bytes | None:
    """Run one read-only git command in a directory.

    Returns:
        Its standard output, or None when git is absent or the command fails (not a work tree,
        no commit yet).

    """
    executable: str | None = shutil.which("git")
    if executable is None:
        return None
    done: subprocess.CompletedProcess[bytes] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved argv; no shell.
        [executable, "-C", str(directory), *arguments],
        capture_output=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )
    return done.stdout if done.returncode == 0 else None


def _git_state(directory: Path) -> bytes | None:
    """State a directory of a git work tree by its tree at HEAD and its uncommitted changes.

    Returns:
        The concatenated output of :data:`GIT_STATE_COMMANDS`, or None when the directory is not
        in a work tree with a commit.

    """
    outputs: list[bytes | None] = [_git(directory, command) for command in GIT_STATE_COMMANDS]
    if any(output is None for output in outputs):
        return None
    return b"\0".join(output for output in outputs if output is not None)


def _tree_files(directory: Path) -> list[Path]:
    """List every file under a directory outside a git work tree, in a stable order.

    Returns:
        The files, sorted, leaving out anything inside a ``.git`` folder.

    """
    return sorted(path for path in directory.rglob("*") if path.is_file() and GIT_DIRECTORY not in path.parts)


def _content(path: Path) -> bytes:
    """Read what a path holds for the fingerprint.

    Returns:
        A file's bytes; a directory's git state, or the names and bytes of its files; a marker
        for a missing path.

    """
    if path.is_file():
        return path.read_bytes()
    if not path.is_dir():
        return MISSING
    state: bytes | None = _git_state(path)
    if state is not None:
        return state
    return b"\0".join(
        str(file.relative_to(path)).encode("utf-8") + b"\0" + file.read_bytes() for file in _tree_files(path)
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def input_fingerprint(facts: JsonValue, paths: Sequence[Path]) -> str:
    """Fingerprint what a step's session works from.

    Args:
        facts: Every input that is a value: the request, the outcome, the input artifacts as
            the journal records them.
        paths: Every file and directory the session reads; each is fingerprinted by content.

    Returns:
        The SHA-256 hex digest.

    """
    return input_fingerprints([facts], paths)[0]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def input_fingerprints(facts: Sequence[JsonValue], paths: Sequence[Path]) -> list[str]:
    """Fingerprint the same files under each of several sets of facts, reading every file once.

    Args:
        facts: The sets of facts, as :func:`input_fingerprint` takes one.
        paths: Every file and directory the session reads.

    Returns:
        One SHA-256 hex digest per set of facts, in order; each equals :func:`input_fingerprint` of it.

    """
    files: bytes = b"".join(
        b"\0" + str(path).encode("utf-8") + b"\0" + hashlib.sha256(_content(path)).digest()
        for path in sorted(dict.fromkeys(paths), key=str)
    )
    return [hashlib.sha256(json.dumps(fact, sort_keys=True).encode("utf-8") + files).hexdigest() for fact in facts]


def fingerprint_path(output: Path) -> Path:
    """Name the file that records the fingerprint an output was accepted with.

    Returns:
        ``<output>.inputs.json`` beside the output.

    """
    return output.with_name(output.name + INPUTS_SUFFIX)


def _output_digest(output: Path) -> str:
    """Digest an output file.

    Returns:
        The SHA-256 hex digest of its bytes.

    """
    return hashlib.sha256(output.read_bytes()).hexdigest()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record(output: Path, fingerprint: str) -> None:
    """Record, once an output is accepted, the fingerprint of its inputs and the digest of the output."""
    write_json(fingerprint_path(output), {INPUTS_KEY: fingerprint, OUTPUT_KEY: _output_digest(output)})


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def unchanged(output: Path, fingerprint: str, earlier: Collection[str] = ()) -> bool:
    """Tell whether an output was accepted from the inputs a session would work from now.

    Args:
        output: The accepted output.
        fingerprint: The fingerprint of the inputs now.
        earlier: The same inputs fingerprinted as a record written with the agent definition and
            contract among them would hold them, one per agent fingerprint that record may carry.

    Returns:
        True when the output exists, its recorded fingerprint equals ``fingerprint`` or one of
        ``earlier``, and the file
        is the one recorded. A missing record is no match, and so is a record that cannot be
        read as a JSON object: the step then runs and its acceptance writes the record again.

    """
    recorded_path: Path = fingerprint_path(output)
    if not output.is_file() or not recorded_path.is_file():
        return False
    try:
        recorded: dict[str, JsonValue] = json_object(json.loads(recorded_path.read_text(encoding="utf-8")))
    except OSError, ValueError, TypeError:
        return False
    held: JsonValue = recorded.get(INPUTS_KEY)
    matched: bool = held == fingerprint or (isinstance(held, str) and held in earlier)
    return matched and recorded.get(OUTPUT_KEY) == _output_digest(output)
