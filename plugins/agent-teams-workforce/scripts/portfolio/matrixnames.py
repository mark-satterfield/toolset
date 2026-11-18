"""The AWS resources a design document names that no matrix entry records.

A Story builds what the matrix records for it, so a resource the design states that the matrix
does not hold is built by no Story and reaches the spec stage as a design gap. The architecture
check finds it first with :func:`unrecorded_names`, deterministically:

- A design names a resource by its resource noun followed by its name or a list of names, as in
  "alarm `skillSpoke-document-atsCouldNotCompleteRate`" or "the alarms `a`, `b` and `c`". The
  nouns come from the matrix itself: the last word of each ``resourceType`` its entries hold
  (``alarm`` of ``cloudwatch-alarm``, ``queue`` of ``sqs-queue``).
- A word after the noun is a name of that resource type only when the project's naming command
  (``name identify``) finds it valid as that type, so the plugin holds no naming pattern.
- A name is recorded when an entry answers to it (:meth:`matrixstore.Matrix.named`), when an
  entry's purpose states it, or when a name pattern an entry's name or purpose states, with a
  ``{token}`` for each varying token, matches it (a group entry such as "the alarms
  skillSpoke-accessAuthorization-{purpose}").

Only the text of the headings through which the Epic reaches each document is read.
"""

import re
import sys
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "resource-naming" / "scripts"))
from matrix_contract import KIND_COMPONENT, KIND_INFRASTRUCTURE, Entry
from matrixheadings import document_body
from matrixsync import heading_texts
from naming_command import NamingCommandError, run_naming

if TYPE_CHECKING:
    from matrixstore import Matrix

ATTR_RESOURCE_TYPE: Final = "resourceType"
DOCUMENT_PREFIX: Final = "document:"
RESOURCE_KINDS: Final = (KIND_COMPONENT, KIND_INFRASTRUCTURE)
"""The kinds of matrix entry that record an AWS resource."""
IDENTIFY_WORKERS: Final = 8
"""How many calls of the naming command run at once."""
_NAME: Final = r"`?([A-Za-z][A-Za-z0-9_.:/@-]*[A-Za-z0-9])`?"
_JOIN: Final = r"(?:\s*,\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+)"
_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{[A-Za-z][A-Za-z0-9]*\}")
_PATTERN_WORD: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_./:@{}-]*\{[A-Za-z][A-Za-z0-9]*\}[A-Za-z0-9_./:@{}-]*")
_VARYING: Final = "[A-Za-z0-9]+"
"""What one ``{token}`` of a name pattern matches."""
_EDGE: Final = r"[A-Za-z0-9_-]"


class NamedDocument(TypedDict):
    """One document the Epic reaches, with the headings through which it reaches it."""

    id: str
    """The document's matrix id."""
    headings: list[str]
    """The headings reached; empty reads the whole document."""


class UnrecordedName(TypedDict):
    """One resource name a design document states that no matrix entry records."""

    name: str
    resourceType: str
    """Each resource type the name is valid as and the noun before it names, joined by ``/``."""
    document: str
    heading: str


type Identify = Callable[[str], frozenset[str]]
"""What the naming command finds a name valid as: the kinds ``name identify`` lists."""


def identify(name: str) -> frozenset[str]:
    """Ask the project's naming command which kinds a name is valid as.

    Returns:
        Each kind ``name identify`` lists; empty when it refuses the name. ``NamingCommandError``
        propagates when the naming command is not configured or does not answer by its contract.

    """
    answer = run_naming(["name", "identify", name])
    kinds: object = answer.document.get("kinds") if answer.ok else None
    if not isinstance(kinds, list):
        return frozenset()
    return frozenset(
        str(held["kind"]) for held in kinds if isinstance(held, dict) and isinstance(held.get("kind"), str)
    )


def resource_nouns(matrix: Matrix) -> dict[str, frozenset[str]]:
    """Name the resource noun of each resource type the matrix's entries hold.

    Returns:
        Each noun, the last word of a ``resourceType``, with every resource type it ends.

    """
    nouns: dict[str, set[str]] = {}
    entry: Entry
    for entry in matrix.entries(RESOURCE_KINDS):
        resource_type: object = entry.attributes.get(ATTR_RESOURCE_TYPE)
        if isinstance(resource_type, str):
            nouns.setdefault(resource_type.rsplit("-", 1)[-1], set()).add(resource_type)
    return {noun: frozenset(types) for noun, types in nouns.items()}


def named_after_nouns(text: str, nouns: Iterable[str]) -> list[tuple[str, str]]:
    """Find each name a text states right after a resource noun.

    Returns:
        Each noun and name, in text order: one per name of a list after the noun.

    """
    alternatives: str = "|".join(sorted((re.escape(noun) for noun in nouns), key=len, reverse=True))
    if not alternatives:
        return []
    listed: re.Pattern[str] = re.compile(
        rf"\b({alternatives})s?\s+({_NAME}(?:{_JOIN}{_NAME})*)",
        re.IGNORECASE,
    )
    single: re.Pattern[str] = re.compile(_NAME)
    return [
        (match.group(1).lower(), name.group(1))
        for match in listed.finditer(text)
        for name in single.finditer(match.group(2))
        if name.group(1).lower() not in {"and", "or"}
    ]


def _patterns(matrix: Matrix) -> list[re.Pattern[str]]:
    """Read the name patterns the resource entries state, each ``{token}`` one varying token.

    Returns:
        One full-match pattern per distinct pattern word of an entry's name or purpose.

    """
    words: set[str] = {
        word
        for entry in matrix.entries(RESOURCE_KINDS)
        for text in (entry.name, entry.purpose, *entry.aliases)
        for word in _PATTERN_WORD.findall(text)
    }
    return [
        re.compile(_VARYING.join(re.escape(part) for part in _PLACEHOLDER.split(word.strip(".,;:"))))
        for word in sorted(words)
    ]


def _recorded(matrix: Matrix, purposes: str, patterns: Sequence[re.Pattern[str]], name: str) -> bool:
    """Tell whether the matrix records a resource name.

    Returns:
        True when an entry answers to it, a resource entry's purpose states it, or a name pattern
        a resource entry states matches it.

    """
    if matrix.named(name):
        return True
    if re.search(rf"(?<!{_EDGE}){re.escape(name)}(?!{_EDGE})", purposes):
        return True
    return any(pattern.fullmatch(name) for pattern in patterns)


def _sections(arch: Path, document: NamedDocument) -> list[tuple[str, str]]:
    """Read the text of the headings through which the Epic reaches one document.

    Returns:
        Each heading and its own text; the whole document under an empty heading when none is
        named; empty when the document is not in the working tree.

    """
    path: Path = arch / document["id"].removeprefix(DOCUMENT_PREFIX)
    if not path.is_file():
        return []
    body: list[str] = document_body(path.read_text(encoding="utf-8"))
    if not document["headings"]:
        return [("", "\n".join(body))]
    texts: dict[str, str] = heading_texts(body)
    return [(heading, texts[heading]) for heading in document["headings"] if heading in texts]


def unrecorded_names(
    matrix: Matrix,
    arch: Path,
    documents: Sequence[NamedDocument],
    valid_as: Identify = identify,
) -> list[UnrecordedName]:
    """List each resource name the reached headings of some documents state that no matrix entry records.

    Args:
        matrix: The matrix, as the architect's change file left it.
        arch: The architecture root.
        documents: The documents the Epic reaches, each with the headings reached.
        valid_as: What the naming command finds a name valid as; :func:`identify` by default.

    Returns:
        Each unrecorded name once per document and heading, in document and text order.
        ``NamingCommandError`` propagates from ``valid_as``.

    """
    nouns: dict[str, frozenset[str]] = resource_nouns(matrix)
    found: list[tuple[str, str, str, str]] = [
        (document["id"].removeprefix(DOCUMENT_PREFIX), heading, noun, name)
        for document in documents
        for heading, text in _sections(arch, document)
        for noun, name in named_after_nouns(text, nouns)
    ]
    distinct: list[str] = sorted({name for _document, _heading, _noun, name in found})
    with ThreadPoolExecutor(max_workers=IDENTIFY_WORKERS) as pool:
        kinds: dict[str, frozenset[str]] = dict(zip(distinct, pool.map(valid_as, distinct), strict=True))
    purposes: str = "\n".join(entry.purpose for entry in matrix.entries(RESOURCE_KINDS))
    patterns: list[re.Pattern[str]] = _patterns(matrix)
    unrecorded: list[UnrecordedName] = []
    seen: set[tuple[str, str, str]] = set()
    document: str
    heading: str
    noun: str
    name: str
    for document, heading, noun, name in found:
        types: frozenset[str] = kinds[name] & nouns[noun]
        if not types or (document, heading, name) in seen or _recorded(matrix, purposes, patterns, name):
            continue
        seen.add((document, heading, name))
        unrecorded.append({
            "name": name,
            "resourceType": "/".join(sorted(types)),
            "document": document,
            "heading": heading,
        })
    return unrecorded


def problem(name: UnrecordedName) -> str:
    """Word one unrecorded resource name as a problem of the architecture check.

    Returns:
        The problem, naming the resource, where the design names it and what records it.

    """
    where: str = f"{name['document']}#{name['heading']}" if name["heading"] else name["document"]
    return (
        f"unrecorded resource: {where} names the {name['resourceType']} `{name['name']}` and no matrix entry records "
        "it, so no Story builds it: record it in the change file as an entry with its resourceType, its home stack "
        "and the link that puts it in the Epic's reach (or name it in the purpose of the entry that records it), "
        "or remove it from the design"
    )


__all__ = ["NamedDocument", "NamingCommandError", "UnrecordedName", "identify", "problem", "unrecorded_names"]
