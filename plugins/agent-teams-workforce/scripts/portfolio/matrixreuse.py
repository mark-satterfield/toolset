"""Whether what a Task built takes shared behaviour from where it is provided.

:func:`check_reuse` (``check-reuse``) is the deterministic part of the build pipeline's reuse
audit. It is handed the ids a Task states and the worktree the Task changed. For the files that
changed it reports a shared capability the Task must use that nothing references (``unused``), a
line that does itself what a shared capability provides (``duplicate``), and a new definition
whose name reads like a provided behaviour, for a reviewer to rule on (``judgment``). Every
finding is a text match against the signals each ``provides`` item of a capability carries;
nothing here judges, and nothing here changes the matrix.

A shared capability is a feature that states what it provides. An id that is such a feature is
that capability; any other id stands for the capabilities the work that builds the entry must
use (``matrixtraverse.capabilities``). A capability the Task's own repository provides (an entry
the Task states, or one its stack holds, realizes it) is not checked, since its definitions there
are its implementation; nor is the walk started from a feature that only consumes such a
capability and is realized outside the Task's repository too, since what else that feature is
supported by belongs to those other realizers.

A ``judgment`` item is put to a reviewer only for a product definition: a file of the repository's
test layout (under a ``testpaths`` entry of its ``pyproject.toml``, or ``tests``, ``test`` or
``__tests__`` when it states none, or named as a test file) is not read for definitions. The words
a definition's name shares with a provided behaviour count only when they are not in
``STOP_WORDS``: English function words and the words every SkillSpoke-style name carries, which
say nothing about which capability a definition does. Word frequency is not the rule, because the
words that name a shared capability (token, cache, outbox, identity) are as frequent among provided
behaviours as the noise words.
"""

import re
import sys
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    KIND_FEATURE,
    REL_REALIZED_BY,
    REL_SUPPORTED_BY,
    Entry,
    EntryId,
    EntryKind,
    JsonValue,
    MatrixError,
    Side,
)
from matrixstore import Matrix
from matrixsync import program_output
from matrixtraverse import CapabilityReach, capabilities, holder, words

type ReuseFinding = Literal["unused", "duplicate", "judgment"]

REUSE_UNUSED: Final[ReuseFinding] = "unused"
REUSE_DUPLICATE: Final[ReuseFinding] = "duplicate"
REUSE_JUDGMENT: Final[ReuseFinding] = "judgment"
ATTR_PROVIDES: Final = "provides"
MIN_SHARED_WORDS: Final = 2
"""How many words of a provided behaviour outside ``STOP_WORDS`` a definition's name must share to reach a reviewer."""
STOP_WORDS: Final[frozenset[str]] = frozenset({
    # English function words that occur in provided behaviours and in definition names.
    "about",
    "after",
    "against",
    "all",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "before",
    "but",
    "by",
    "can",
    "do",
    "does",
    "each",
    "else",
    "every",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "must",
    "no",
    "none",
    "not",
    "of",
    "off",
    "on",
    "one",
    "only",
    "or",
    "out",
    "over",
    "own",
    "per",
    "same",
    "so",
    "than",
    "that",
    "the",
    "their",
    "then",
    "these",
    "this",
    "those",
    "through",
    "to",
    "under",
    "up",
    "was",
    "what",
    "when",
    "whether",
    "which",
    "while",
    "who",
    "whose",
    "with",
    "within",
    # Words any definition name or provided behaviour carries, whichever capability it is about.
    "api",
    "body",
    "client",
    "data",
    "error",
    "errors",
    "get",
    "id",
    "ids",
    "json",
    "lib",
    "log",
    "logs",
    "name",
    "secret",
    "secrets",
    "set",
    "skill",
    "spoke",
    "type",
    "value",
})
"""The words a definition's name and a provided behaviour may share without it counting."""
DEFAULT_TEST_ROOTS: Final[frozenset[str]] = frozenset({"tests", "test", "__tests__"})
"""The folders that hold tests when the repository's ``pyproject.toml`` states no ``testpaths``."""
PYPROJECT: Final = "pyproject.toml"
_TEST_NAME: Final[re.Pattern[str]] = re.compile(
    r"^(?:test_.+\.py|.+_test\.py|conftest\.py|.+\.(?:test|spec)\.[cm]?[jt]sx?)$",
)
STATUS_PATH_AT: Final = 3
"""Where the path starts in one entry of ``git status --porcelain``."""
_RENAMED: Final = "RC"
_DEFINITION: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:def|class|function|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)",
)


@dataclass(frozen=True, slots=True)
class Provided:
    """One thing a shared capability provides, as its feature's ``provides`` attribute states it."""

    id: str
    behaviour: str
    """What a consumer obtains, in one sentence."""
    consumers_must: str
    """What a consumer must not implement itself."""
    interface: str
    """The name of the package, layer, operation or construct a consumer takes it through."""
    use_signals: tuple[str, ...]
    """Text that shows a consumer uses it."""
    duplicate_signals: tuple[str, ...]
    """Text that shows a consumer is doing it itself."""


@dataclass(frozen=True, slots=True)
class Guarded:
    """One shared capability the changed files are checked against."""

    feature: Entry
    provides: tuple[Provided, ...]
    relied: tuple[Provided, ...]
    """The items the work relies on, which have to be referenced: those named, or every item when none is named."""


class ReuseItem(TypedDict):
    """One finding of the reuse check."""

    finding: ReuseFinding
    feature: EntryId
    provides: str
    """The id of the ``provides`` item the finding is about."""
    detail: str
    file: NotRequired[str]
    line: NotRequired[int]
    definition: NotRequired[str]
    """For a ``judgment`` item: the definition's line, stripped."""
    shared: NotRequired[list[str]]
    """For a ``judgment`` item: the words its name shares with the provided behaviour."""
    behaviour: NotRequired[str]
    """For a ``judgment`` item: the provided behaviour."""


class CapabilityRef(TypedDict):
    """One shared capability the changed files were checked against."""

    id: EntryId
    kind: EntryKind
    name: str
    side: Side


class ReuseResult(TypedDict):
    """What ``check-reuse`` prints."""

    ids: list[EntryId]
    """The ids the check was handed."""
    worktree: str
    files: list[str]
    """The changed files that were read."""
    capabilities: list[CapabilityRef]
    """The shared capabilities checked against."""
    provided: list[EntryId]
    """The shared capabilities the Task's own repository provides, which are not checked.

    Their definitions there are their implementation.
    """
    violations: list[ReuseItem]
    judgment: list[ReuseItem]
    unchecked: list[str]
    """Each ``<capability>#<provides id>`` relied on that carries no use signal, so its use could not be checked."""
    clean: bool
    """True when there is no violation."""


def _text(value: JsonValue) -> str:
    """Narrow a member of a ``provides`` item to text.

    Returns:
        The value when it is a string, otherwise the empty string.

    """
    return value if isinstance(value, str) else ""


def _texts(value: JsonValue) -> tuple[str, ...]:
    """Narrow a member of a ``provides`` item to the non-empty strings it lists.

    Returns:
        The strings, in order; nothing for a value that is not a list.

    """
    return tuple(item for item in value if isinstance(item, str) and item) if isinstance(value, list) else ()


def _provided(feature: Entry) -> tuple[Provided, ...]:
    """Read what a feature states it provides.

    Returns:
        One item per object of the feature's ``provides`` attribute that has an id; empty for a
        feature that states none.

    """
    stated: JsonValue = feature.attributes.get(ATTR_PROVIDES)
    items: list[Provided] = []
    item: JsonValue
    for item in stated if isinstance(stated, list) else []:
        if not isinstance(item, dict) or not _text(item.get("id")):
            continue
        interface: JsonValue = item.get("interface")
        items.append(
            Provided(
                id=_text(item.get("id")),
                behaviour=_text(item.get("behaviour")),
                consumers_must=_text(item.get("consumersMust")),
                interface=_text(interface.get("name")) if isinstance(interface, dict) else "",
                use_signals=_texts(item.get("useSignals")),
                duplicate_signals=_texts(item.get("duplicateSignals")),
            ),
        )
    return tuple(items)


@dataclass(frozen=True, slots=True)
class _Own:
    """What the Task's own repository holds: the entries it states and the stacks that hold them."""

    entries: frozenset[EntryId]
    stacks: frozenset[EntryId]

    def provides(self, matrix: Matrix, feature_id: EntryId) -> bool:
        """Tell whether a feature is a shared capability the Task's own repository provides.

        Returns:
            True when the feature states what it provides and an entry the Task states, or an
            entry a stack of the Task holds, realizes it.

        """
        return bool(_provided(matrix.entry(feature_id))) and any(
            self.holds(matrix, realizing.end) for realizing in matrix.outgoing(feature_id, (REL_REALIZED_BY,))
        )

    def holds(self, matrix: Matrix, entry_id: EntryId) -> bool:
        """Tell whether an entry is the Task's own: one it states, or one a stack of the Task holds.

        Returns:
            True when the entry belongs to the Task's repository.

        """
        return entry_id in self.entries or holder(matrix, entry_id) in self.stacks

    def consumer(self, matrix: Matrix, feature_id: EntryId) -> bool:
        """Tell whether a feature only consumes a shared capability the Task's own repository provides.

        Such a feature names an entry of the Task among its realizers because that entry provides
        the capability it is supported by; what else it is supported by belongs to its realizers
        outside the Task's repository. A feature only the Task's repository realizes is its own
        product feature, and is walked.

        Returns:
            True when the feature is not provided here, has a realizer outside the Task's
            repository, and is supported by a capability provided here.

        """
        return (
            not self.provides(matrix, feature_id)
            and any(
                not self.holds(matrix, realizing.end) for realizing in matrix.outgoing(feature_id, (REL_REALIZED_BY,))
            )
            and any(
                self.provides(matrix, supporting.end) for supporting in matrix.outgoing(feature_id, (REL_SUPPORTED_BY,))
            )
        )


def _own(matrix: Matrix, entry_ids: Sequence[EntryId]) -> _Own:
    """Work out what the Task's own repository holds from the ids it states.

    Returns:
        The stated entries that are not features, and the stacks that hold them.

    """
    built: frozenset[EntryId] = frozenset(
        entry_id for entry_id in entry_ids if matrix.entry(entry_id).kind != KIND_FEATURE
    )
    stacks: set[EntryId | None] = {holder(matrix, entry_id) for entry_id in built}
    return _Own(built, frozenset(stack for stack in stacks if stack is not None))


def _walked(matrix: Matrix, others: Sequence[EntryId], own: _Own) -> list[EntryId]:
    """List the features the capability walk starts from.

    Returns:
        Each feature an id realizes, and each feature among the ids, without a feature that only
        consumes a capability the Task's own repository provides and is realized outside it too.

    """
    starts: dict[EntryId, None] = dict.fromkeys(
        feature
        for entry_id in others
        for feature in (
            [entry_id]
            if matrix.entry(entry_id).kind == KIND_FEATURE
            else [realizing.start for realizing in matrix.incoming(entry_id, (REL_REALIZED_BY,))]
        )
    )
    return [feature for feature in starts if not own.consumer(matrix, feature)]


def _guarded(matrix: Matrix, entry_ids: Sequence[EntryId]) -> tuple[list[Guarded], list[EntryId]]:
    """Work out the shared capabilities some ids stand for.

    A capability the Task's own repository provides is not checked: its definitions there are its
    implementation. Nor is the walk started from a feature that only consumes such a capability. An
    id the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``.

    Returns:
        Each capability once, in id order: a feature among the ids that states what it provides,
        with every item relied on; and each capability the work that builds the other ids must
        use, with the items its ``supportedBy`` relationships name, or every item when they name
        none. Then the capabilities left out because the Task's own repository provides them.

    """
    own: _Own = _own(matrix, entry_ids)
    named: dict[EntryId, set[str] | None] = {}
    others: list[EntryId] = []
    entry_id: EntryId
    for entry_id in dict.fromkeys(entry_ids):
        entry: Entry = matrix.entry(entry_id)
        if entry.kind == KIND_FEATURE and _provided(entry):
            named[entry_id] = None
        else:
            others.append(entry_id)
    walked: list[EntryId] = _walked(matrix, others, own)
    reach: CapabilityReach
    for reach in capabilities(matrix, walked) if walked else []:
        if reach.feature in named and named[reach.feature] is None:
            continue
        relied: set[str] | None = named.setdefault(reach.feature, set())
        if not reach.relies:
            named[reach.feature] = None
        elif relied is not None:
            relied.update(reach.relies)
    provided_here: list[EntryId] = sorted(feature for feature in named if own.provides(matrix, feature))
    guarded: list[Guarded] = []
    for entry_id in sorted(set(named) - set(provided_here)):
        feature: Entry = matrix.entry(entry_id)
        provides: tuple[Provided, ...] = _provided(feature)
        wanted: set[str] | None = named[entry_id]
        guarded.append(
            Guarded(
                feature=feature,
                provides=provides,
                relied=provides if wanted is None else tuple(item for item in provides if item.id in wanted),
            ),
        )
    return guarded, provided_here


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def changed_files(worktree: Path) -> list[str]:
    """List the files of a worktree that differ from its commit.

    A folder that is no git tree raises ``MatrixError`` from ``program_output``.

    Args:
        worktree: The worktree.

    Returns:
        Every modified, added or untracked path, relative to the worktree, sorted.

    Raises:
        TypeError: ``worktree`` is not a path.

    """
    if not isinstance(worktree, Path):
        message: str = "the worktree must be a path"
        raise TypeError(message)
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


def _holds(texts: Mapping[str, Sequence[str]], signals: Sequence[str]) -> bool:
    """Tell whether some text holds one of some signals.

    Returns:
        True when a line of a file holds a signal.

    """
    return any(signal in line for lines in texts.values() for line in lines for signal in signals)


def _unused(
    guarded: Sequence[Guarded],
    changed: Mapping[str, Sequence[str]],
    worktree: Path,
) -> tuple[list[ReuseItem], list[str]]:
    """Find the capabilities a Task must use that nothing references.

    The changed files are searched first; the rest of the worktree's tracked files are read only
    when a signal is not in them.

    Returns:
        One item per relied-on ``provides`` item whose use signals occur nowhere, and the items
        that carry no use signal.

    """
    items: list[ReuseItem] = []
    unchecked: list[str] = []
    everything: dict[str, list[str]] | None = None
    capability: Guarded
    for capability in guarded:
        item: Provided
        for item in capability.relied:
            if not item.use_signals:
                unchecked.append(f"{capability.feature.id}#{item.id}")
                continue
            if _holds(changed, item.use_signals):
                continue
            if everything is None:
                everything = _lines(worktree, program_output("git", ["ls-files", "-z"], worktree).split("\0"))
            if not _holds(everything, item.use_signals):
                items.append({
                    "finding": REUSE_UNUSED,
                    "feature": capability.feature.id,
                    "provides": item.id,
                    "detail": f"nothing references {item.interface}: none of {list(item.use_signals)} occurs",
                })
    return items, unchecked


def _duplicates(guarded: Sequence[Guarded], changed: Mapping[str, Sequence[str]]) -> list[ReuseItem]:
    """Find the changed lines that do themselves what a shared capability provides.

    Returns:
        One item per line of a changed file that holds a duplicate signal of a ``provides`` item.

    """
    items: list[ReuseItem] = []
    capability: Guarded
    for capability in guarded:
        item: Provided
        for item in capability.provides:
            items.extend(
                {
                    "finding": REUSE_DUPLICATE,
                    "feature": capability.feature.id,
                    "provides": item.id,
                    "file": file,
                    "line": number,
                    "detail": f"{signal!r} is what {item.interface} exists to do: {item.consumers_must}",
                }
                for file, lines in changed.items()
                for number, line in enumerate(lines, start=1)
                for signal in item.duplicate_signals
                if signal in line
            )
    return items


def _test_roots(worktree: Path) -> frozenset[str]:
    """Read where the repository keeps its tests.

    Returns:
        The ``testpaths`` the worktree's ``pyproject.toml`` states for pytest, or
        ``DEFAULT_TEST_ROOTS`` when it has none.

    Raises:
        MatrixError: The ``pyproject.toml`` cannot be read or parsed.

    """
    pyproject: Path = worktree / PYPROJECT
    if not pyproject.is_file():
        return DEFAULT_TEST_ROOTS
    try:
        document: dict[str, object] = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        message: str = f"cannot read the test layout in {pyproject}: {error}"
        raise MatrixError(message) from error
    tool: object = document.get("tool")
    pytest_table: object = tool.get("pytest") if isinstance(tool, dict) else None
    options: object = pytest_table.get("ini_options") if isinstance(pytest_table, dict) else None
    stated: object = options.get("testpaths") if isinstance(options, dict) else None
    roots: frozenset[str] = (
        frozenset(str(PurePosixPath(root)) for root in stated if isinstance(root, str) and root)
        if isinstance(stated, list)
        else frozenset()
    )
    return roots or DEFAULT_TEST_ROOTS


def _is_test(relative: str, roots: Iterable[str]) -> bool:
    """Tell whether a changed file belongs to the repository's tests.

    Returns:
        True when the file lies under a test root, or a folder of its path is named like one of
        ``DEFAULT_TEST_ROOTS``, or its name is a test file's.

    """
    path: PurePosixPath = PurePosixPath(relative)
    return (
        any(path.is_relative_to(root) for root in roots)
        or bool(DEFAULT_TEST_ROOTS & set(path.parts[:-1]))
        or _TEST_NAME.match(path.name) is not None
    )


def _judgment(
    guarded: Sequence[Guarded],
    changed: Mapping[str, Sequence[str]],
) -> list[ReuseItem]:
    """Find the product definitions in changed files whose name reads like a provided behaviour.

    Returns:
        One item per definition and ``provides`` item that share at least ``MIN_SHARED_WORDS`` words
        outside ``STOP_WORDS``, for a reviewer to be asked whether the definition duplicates the
        behaviour.

    """
    behaviours: list[tuple[EntryId, Provided, set[str]]] = [
        (capability.feature.id, item, set(words(item.behaviour)) - STOP_WORDS)
        for capability in guarded
        for item in capability.provides
    ]
    items: list[ReuseItem] = []
    file: str
    lines: Sequence[str]
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
                    "provides": item.id,
                    "file": file,
                    "line": number,
                    "detail": f"{line.strip()} shares {sorted(named & behaviour)} with: {item.behaviour}",
                    "definition": line.strip(),
                    "shared": sorted(named & behaviour),
                    "behaviour": item.behaviour,
                }
                for feature, item, behaviour in behaviours
                if len(named & behaviour) >= MIN_SHARED_WORDS
            )
    return items


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_reuse(
    matrix: Matrix,
    entry_ids: Sequence[EntryId],
    worktree: Path,
    files: Sequence[str] | None = None,
) -> ReuseResult:
    """Check the files a Task changed against the shared capabilities the Task states.

    An id the matrix does not hold raises ``MatrixError`` from ``Matrix.entry``, and a worktree
    that is no git tree raises ``MatrixError`` from ``program_output``. Nothing is changed.

    Args:
        matrix: The matrix.
        entry_ids: The ids the Task states. A feature that states what it provides is a shared
            capability and every item it provides has to be referenced; any other id stands for
            the capabilities the work that builds the entry must use.
        worktree: The worktree the Task changed.
        files: The changed files, relative to the worktree; None reads them from ``git status``.

    Returns:
        The violations (a capability nothing references, a line that duplicates one), the
        product definitions for a reviewer to rule on, and what could not be checked.

    Raises:
        ValueError: No id is given.
        MatrixError: ``worktree`` is not a directory, or its ``pyproject.toml`` cannot be parsed.

    """
    message: str
    if not entry_ids:
        message = "check-reuse needs the id of at least one entry"
        raise ValueError(message)
    if not worktree.is_dir():
        message = f"the worktree {worktree} is not a directory"
        raise MatrixError(message)
    guarded: list[Guarded]
    provided_here: list[EntryId]
    guarded, provided_here = _guarded(matrix, entry_ids)
    changed: dict[str, list[str]] = _lines(worktree, changed_files(worktree) if files is None else files)
    unused: list[ReuseItem]
    unchecked: list[str]
    unused, unchecked = _unused(guarded, changed, worktree)
    violations: list[ReuseItem] = [*unused, *_duplicates(guarded, changed)]
    roots: frozenset[str] = _test_roots(worktree)
    product: dict[str, list[str]] = {file: lines for file, lines in changed.items() if not _is_test(file, roots)}
    return {
        "ids": list(dict.fromkeys(entry_ids)),
        "worktree": str(worktree),
        "files": sorted(changed),
        "capabilities": [
            {
                "id": capability.feature.id,
                "kind": capability.feature.kind,
                "name": capability.feature.name,
                "side": capability.feature.side,
            }
            for capability in guarded
        ],
        "provided": provided_here,
        "violations": violations,
        "judgment": _judgment(guarded, product),
        "unchecked": unchecked,
        "clean": not violations,
    }
