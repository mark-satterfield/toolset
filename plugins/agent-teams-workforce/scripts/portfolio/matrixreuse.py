"""What a Task builds, and whether what it built takes shared behaviour from where it is provided.

- :func:`task_elements` reads the matrix ids of the elements a Task builds from the Task's bead.
- :func:`check_reuse` is the deterministic part of the build pipeline's reuse audit. For the
  files a Task changed it reports a capability the Task must use that nothing references
  (``unused``), a line that does itself what a shared capability provides (``duplicate``), and a
  new definition whose name reads like a provided behaviour, for a reviewer to rule on
  (``judgment``). Every finding is a text match against the signals each ``provides`` entry
  carries; nothing here judges.
"""

import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    REUSE_DUPLICATE,
    REUSE_JUDGMENT,
    REUSE_UNUSED,
    TASK_ELEMENTS_KEY,
    Matrix,
    MatrixError,
    NodeId,
    Provides,
    ReuseItem,
)
from matrixquery import Capability, uses_view, words
from matrixsync import program_output

METADATA_KEY: Final = "metadata"
MIN_SHARED_WORDS: Final = 2
"""How many words of a provided behaviour a new definition's name must share to be put to a reviewer."""
STATUS_PATH_AT: Final = 3
"""Where the path starts in one entry of ``git status --porcelain``."""
_RENAMED: Final = "RC"
_DEFINITION: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:def|class|function|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)",
)


class ReuseResult(TypedDict):
    """What ``check-reuse`` prints."""

    task: str
    worktree: str
    files: list[str]
    """The changed files that were read."""
    capabilities: list[NodeId]
    """The shared capabilities the Task's elements must use."""
    violations: list[ReuseItem]
    judgment: list[ReuseItem]
    unchecked: list[str]
    """Each ``<capability>#<provides id>`` relied on that carries no use signal, so its use could not be checked."""
    clean: bool
    """True when there is no violation."""


def _issue(decoded: object, task: str) -> dict[str, object]:
    """Find one issue in what ``bd show --json`` printed.

    Returns:
        The issue with the Task's id.

    Raises:
        MatrixError: The JSON holds no issue with that id.

    """
    issues: list[object] = decoded if isinstance(decoded, list) else [decoded]
    issue: object
    for issue in issues:
        if isinstance(issue, dict) and issue.get("id") == task:
            return {str(key): value for key, value in issue.items()}
    message: str = f"beads printed no issue {task}"
    raise MatrixError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_task_elements(text: str, task: str) -> list[str]:
    """Read the elements a Task builds from the JSON ``bd show <task> --json`` prints.

    The Task names them in its metadata under the key the matrix contract fixes, as a list of
    matrix ids or as that list written as JSON text.

    Args:
        text: The JSON text.
        task: The Task's id.

    Returns:
        The ids named, in order and without repeats; none when the Task names no element.

    Raises:
        MatrixError: The text is not JSON, holds no such issue, or names its elements as
            something other than a list of strings.

    """
    message: str
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as error:
        message = f"beads did not print JSON: {error}"
        raise MatrixError(message) from error
    metadata: object = _issue(decoded, task).get(METADATA_KEY) or {}
    named: object = metadata.get(TASK_ELEMENTS_KEY) if isinstance(metadata, dict) else None
    if isinstance(named, str) and named.strip():
        try:
            named = json.loads(named)
        except json.JSONDecodeError as error:
            message = f"the {TASK_ELEMENTS_KEY} of {task} is not a JSON list: {error}"
            raise MatrixError(message) from error
    if named is None or (isinstance(named, str) and not named.strip()):
        return []
    if not isinstance(named, list) or not all(isinstance(entry, str) and entry for entry in named):
        message = f"the {TASK_ELEMENTS_KEY} of {task} is not a list of matrix ids"
        raise MatrixError(message)
    return list(dict.fromkeys(str(entry) for entry in named))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def task_elements(control: Path, task: str) -> list[str]:
    """Ask beads which elements a Task builds.

    A ``bd`` that is missing or fails raises ``MatrixError``.

    Args:
        control: The control repository, whose beads database holds the Task.
        task: The Task's id.

    Returns:
        The matrix ids the Task names; none when it names no element.

    """
    return parse_task_elements(program_output("bd", ["show", task, "--json"], control), task)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def changed_files(worktree: Path) -> list[str]:
    """List the files of a worktree that differ from its commit.

    A folder that is no git tree raises ``MatrixError``.

    Args:
        worktree: The worktree.

    Returns:
        Every modified, added or untracked path, relative to the worktree, sorted.

    """
    printed: str = program_output("git", ["status", "--porcelain=v1", "-z", "--untracked-files=all"], worktree)
    entries: list[str] = [entry for entry in printed.split("\0") if entry]
    paths: set[str] = set()
    index: int = 0
    while index < len(entries):
        paths.add(entries[index][STATUS_PATH_AT:])
        index += 2 if set(entries[index][:2]) & set(_RENAMED) else 1
    return sorted(paths)


def _lines(worktree: Path, files: Sequence[str]) -> dict[str, list[str]]:
    """Read the text files among some paths of a worktree.

    Returns:
        Each text file's path and its lines. A path that is missing or is a directory is left
        out, and so is a file that is not UTF-8 text: the signals are text, so a binary file
        cannot hold one.

    Raises:
        MatrixError: A file cannot be read.

    """
    read: dict[str, list[str]] = {}
    relative: str
    for relative in files:
        file: Path = worktree / relative
        if not relative or not file.is_file():
            continue
        try:
            content: bytes = file.read_bytes()
        except OSError as error:
            message: str = f"cannot read {file}: {error}"
            raise MatrixError(message) from error
        try:
            read[relative] = content.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            continue
    return read


def _relied(capability: Capability) -> list[Provides]:
    """List the ``provides`` entries of a capability a consumer relies on.

    Returns:
        The entries the consumer's links name, or every entry when the links name none.

    """
    named: set[str] = set(capability["reliedOn"])
    return [entry for entry in capability["provides"] if not named or entry["id"] in named]


def _holds(texts: dict[str, list[str]], signals: Sequence[str]) -> bool:
    """Tell whether some text holds one of some signals.

    Returns:
        True when a line of a file holds a signal.

    """
    return any(signal in line for lines in texts.values() for line in lines for signal in signals if signal)


def _unused(
    must: Sequence[Capability],
    changed: dict[str, list[str]],
    worktree: Path,
) -> tuple[list[ReuseItem], list[str]]:
    """Find the capabilities a Task must use that nothing references.

    The changed files are searched first; the rest of the worktree's tracked files are read only
    when a signal is not in them.

    Returns:
        One item per relied-on ``provides`` entry whose use signals occur nowhere, and the
        entries that carry no use signal.

    """
    items: list[ReuseItem] = []
    unchecked: list[str] = []
    everything: dict[str, list[str]] | None = None
    capability: Capability
    for capability in must:
        entry: Provides
        for entry in _relied(capability):
            signals: list[str] = entry.get("useSignals", [])
            if not signals:
                unchecked.append(f"{capability['feature']['id']}#{entry['id']}")
                continue
            if _holds(changed, signals):
                continue
            if everything is None:
                everything = _lines(worktree, program_output("git", ["ls-files", "-z"], worktree).split("\0"))
            if not _holds(everything, signals):
                items.append({
                    "finding": REUSE_UNUSED,
                    "feature": capability["feature"]["id"],
                    "provides": entry["id"],
                    "detail": f"nothing references {entry['interface']['name']}: none of {signals} occurs",
                })
    return items, unchecked


def _duplicates(scope: Sequence[Capability], changed: dict[str, list[str]]) -> list[ReuseItem]:
    """Find the changed lines that do themselves what a shared capability provides.

    Returns:
        One item per line of a changed file that holds a duplicate signal of a ``provides`` entry.

    """
    items: list[ReuseItem] = []
    capability: Capability
    for capability in scope:
        entry: Provides
        for entry in capability["provides"]:
            signals: list[str] = [signal for signal in entry.get("duplicateSignals", []) if signal]
            items.extend(
                {
                    "finding": REUSE_DUPLICATE,
                    "feature": capability["feature"]["id"],
                    "provides": entry["id"],
                    "file": file,
                    "line": number,
                    "detail": f"{signal!r} is what {entry['interface']['name']} exists to do: {entry['consumersMust']}",
                }
                for file, lines in changed.items()
                for number, line in enumerate(lines, start=1)
                for signal in signals
                if signal in line
            )
    return items


def _judgment(scope: Sequence[Capability], changed: dict[str, list[str]]) -> list[ReuseItem]:
    """Find the definitions in changed files whose name reads like a provided behaviour.

    Returns:
        One item per definition and ``provides`` entry that share enough words for a reviewer to
        be asked whether the definition duplicates the behaviour.

    """
    behaviours: list[tuple[NodeId, Provides, set[str]]] = [
        (capability["feature"]["id"], entry, set(words(entry["behaviour"])))
        for capability in scope
        for entry in capability["provides"]
    ]
    items: list[ReuseItem] = []
    file: str
    lines: list[str]
    for file, lines in changed.items():
        number: int
        line: str
        for number, line in enumerate(lines, start=1):
            match: re.Match[str] | None = _DEFINITION.match(line)
            named: set[str] = set(words(match.group(1).replace("_", " "))) if match is not None else set()
            items.extend(
                {
                    "finding": REUSE_JUDGMENT,
                    "feature": feature,
                    "provides": entry["id"],
                    "file": file,
                    "line": number,
                    "detail": f"{line.strip()} shares {sorted(named & behaviour)} with: {entry['behaviour']}",
                }
                for feature, entry, behaviour in behaviours
                if len(named & behaviour) >= MIN_SHARED_WORDS
            )
    return items


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_reuse(
    matrix: Matrix,
    built: Sequence[NodeId],
    scope: Sequence[NodeId],
    worktree: Path,
    files: Sequence[str],
) -> ReuseResult:
    """Check the files a Task changed against the shared capabilities its repository must use.

    An id that names no row raises ``MatrixRefusedError``; a worktree that is no git tree raises
    ``MatrixError``.

    Args:
        matrix: The matrix.
        built: The ids of the elements the Task builds; every capability they must use has to
            be referenced.
        scope: The ids of the elements whose capabilities must not be duplicated: the Task's,
            or all of its repository's.
        worktree: The worktree the Task changed.
        files: The changed files, relative to the worktree.

    Returns:
        The violations (a capability nothing references, a line that duplicates one), the
        definitions for a reviewer to rule on, and what could not be checked. The Task id is
        left empty for the caller to fill.

    Raises:
        MatrixError: ``worktree`` is not a directory.

    """
    if not worktree.is_dir():
        message: str = f"the worktree {worktree} is not a directory"
        raise MatrixError(message)
    must: list[Capability] = uses_view(matrix, list(built))["capabilities"]
    guarded: list[Capability] = uses_view(matrix, list(dict.fromkeys([*built, *scope])))["capabilities"]
    changed: dict[str, list[str]] = _lines(worktree, files)
    unused: list[ReuseItem]
    unchecked: list[str]
    unused, unchecked = _unused(must, changed, worktree)
    violations: list[ReuseItem] = [*unused, *_duplicates(guarded, changed)]
    return {
        "task": "",
        "worktree": str(worktree),
        "files": sorted(changed),
        "capabilities": [capability["feature"]["id"] for capability in must],
        "violations": violations,
        "judgment": _judgment(guarded, changed),
        "unchecked": unchecked,
        "clean": not violations,
    }
