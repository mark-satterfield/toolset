"""The element checklist: the values each element an Epic's design adds or changes must state.

``skills/effective-architecture/element-checklist.json`` names, for each class of element (an
interface, a store, an event, a compute element, a parameter, a component), the values the
architecture criteria A15 to A20 of ``review-criteria.json`` require of it; every item quotes its
criterion's text, which :func:`load_checklist` holds it to. :func:`expected_values` lists the values
of the elements it is given, from their matrix entries; ``atw-matrix element-checklist`` prints them
for the solutions architect, who fills each one in its result (``elementValues``) in the session
that decides the design; and :func:`value_problems` finds each value the result leaves empty, or
does not find stated at the heading it cites, which the architecture check sends back to the
architect. A name the naming command builds is listed as such and never left to fill.
"""

import json
import re
import sys
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import Entry, MatrixError
from matrixheadings import document_body
from matrixstore import Matrix, as_entry_id
from matrixsync import heading_texts
from review_criteria import LEVEL_ARCHITECTURE, Criteria, load_criteria

CHECKLIST_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2] / "skills" / "effective-architecture" / "element-checklist.json"
)
ATTR_RESOURCE_TYPE: Final = "resourceType"
ATTR_EXECUTION_USE: Final = "executionUse"
NAMING_COMMAND: Final = "built by the naming command"
"""What the checklist lists for a value the naming command builds, in place of a value to fill."""
DOCUMENT_PREFIX: Final = "document:"
_MARKUP: Final[re.Pattern[str]] = re.compile(r"[`*_|>#]")
_SPACE: Final[re.Pattern[str]] = re.compile(r"\s+")


class ChecklistError(ValueError):
    """The checklist file is malformed, or an item quotes no text of its criterion."""


@dataclass(frozen=True, slots=True)
class Item:
    """One value a class of element states: its criterion, the criterion's phrase that names it, and who builds it."""

    criterion: str
    item: str
    naming_command: bool


@dataclass(frozen=True, slots=True)
class ElementClass:
    """One class of element, how an element is matched to it, and the values it states."""

    id: str
    kinds: frozenset[str]
    resource_types: frozenset[str]
    resource_type_prefixes: tuple[str, ...]
    execution_uses: frozenset[str]
    items: tuple[Item, ...]


class ExpectedValue(TypedDict):
    """One value an element must state: its element, criterion and item, and whether the naming command builds it."""

    element: str
    criterion: str
    item: str
    namingCommand: bool


class UnfilledValue(TypedDict):
    """One value the architect's result leaves unfilled, with the sentence that says why."""

    element: str
    criterion: str
    item: str
    problem: str


class Home(TypedDict):
    """The architecture heading an entry cites."""

    source: str
    heading: str


def _strings(value: object, where: str) -> frozenset[str]:
    """Narrow a decoded value to a set of strings.

    Returns:
        The strings; empty when the value is absent.

    Raises:
        ChecklistError: The value is neither absent nor a list of strings.

    """
    if value is None:
        return frozenset()
    if not isinstance(value, list) or not all(isinstance(text, str) for text in value):
        message: str = f"{where}: expected a list of strings"
        raise ChecklistError(message)
    return frozenset(text for text in value if isinstance(text, str))


def _item(value: object, where: str, criteria: Mapping[str, str]) -> Item:
    """Read one item and hold it to its criterion's text.

    Returns:
        The item.

    Raises:
        ChecklistError: The item is malformed, names no architecture criterion, or quotes no
            phrase of that criterion's text.

    """
    if not isinstance(value, dict):
        message: str = f"{where}: expected an object"
        raise ChecklistError(message)
    criterion: object = value.get("criterion")
    phrase: object = value.get("item")
    naming: object = value.get("namingCommand")
    if not isinstance(criterion, str) or not isinstance(phrase, str) or not isinstance(naming, bool):
        message = f"{where}: needs a criterion, an item and namingCommand"
        raise ChecklistError(message)
    if phrase.casefold() not in criteria.get(criterion, "").casefold():
        message = f"{where}: {phrase!r} is not in the text of the architecture criterion {criterion}"
        raise ChecklistError(message)
    return Item(criterion, phrase, naming)


def _element_class(value: object, where: str, criteria: Mapping[str, str]) -> ElementClass:
    """Read one class of element.

    Returns:
        The class.

    Raises:
        ChecklistError: The class is malformed.

    """
    if not isinstance(value, dict) or not isinstance(value.get("id"), str) or not isinstance(value.get("when"), dict):
        message: str = f"{where}: expected an object with an id, when and items"
        raise ChecklistError(message)
    when: dict[str, object] = {str(key): held for key, held in value["when"].items()}
    items: object = value.get("items")
    if not isinstance(items, list) or not items:
        message = f"{where}: items must be a nonempty list"
        raise ChecklistError(message)
    return ElementClass(
        id=str(value["id"]),
        kinds=_strings(when.get("kinds"), f"{where}/when/kinds"),
        resource_types=_strings(when.get("resourceTypes"), f"{where}/when/resourceTypes"),
        resource_type_prefixes=tuple(sorted(_strings(when.get("resourceTypePrefixes"), f"{where}/when/prefixes"))),
        execution_uses=_strings(when.get("executionUse"), f"{where}/when/executionUse"),
        items=tuple(_item(item, f"{where}/items/{index}", criteria) for index, item in enumerate(items)),
    )


def load_checklist(path: Path = CHECKLIST_PATH, criteria: Criteria | None = None) -> tuple[ElementClass, ...]:
    """Read the checklist file, holding every item to the text of its architecture criterion.

    Args:
        path: The checklist file.
        criteria: The review criteria; None reads ``review-criteria.json``.

    Returns:
        The classes of element, in file order.

    Raises:
        ChecklistError: The file is not a well-formed checklist.

    """
    read: Criteria = load_criteria() if criteria is None else criteria
    texts: dict[str, str] = {entry.id: entry.text for entry in read.at_level(LEVEL_ARCHITECTURE)}
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        message: str = f"cannot read the element checklist {path}: {error}"
        raise ChecklistError(message) from error
    classes: object = decoded.get("classes") if isinstance(decoded, dict) else None
    if not isinstance(classes, list):
        message = f"{path}: expected an object with a list of classes"
        raise ChecklistError(message)
    return tuple(_element_class(held, f"{path}/classes/{index}", texts) for index, held in enumerate(classes))


def _matches(element_class: ElementClass, kind: str, resource_type: str, execution_use: str) -> bool:
    """Tell whether an element of a kind, resource type and execution use is of a class.

    Returns:
        True when any one of the class's conditions holds.

    """
    return (
        kind in element_class.kinds
        or resource_type in element_class.resource_types
        or any(resource_type.startswith(prefix) for prefix in element_class.resource_type_prefixes if resource_type)
        or execution_use in element_class.execution_uses
    )


def _items_of(matrix: Matrix, element: str, classes: Sequence[ElementClass]) -> tuple[Item, ...] | None:
    """List the values one element states, by the classes its matrix entry is of.

    Returns:
        Each item once, in class order; None when the matrix holds no entry for the element.

    """
    try:
        found: Entry | None = matrix.find(as_entry_id(element.strip()))
    except MatrixError:
        return None
    if found is None:
        return None
    resource_type: object = found.attributes.get(ATTR_RESOURCE_TYPE)
    execution_use: object = found.attributes.get(ATTR_EXECUTION_USE)
    held: dict[tuple[str, str], Item] = {
        (item.criterion, item.item): item
        for element_class in classes
        if _matches(
            element_class,
            str(found.kind),
            resource_type if isinstance(resource_type, str) else "",
            execution_use if isinstance(execution_use, str) else "",
        )
        for item in element_class.items
    }
    return tuple(held.values())


def expected_values(
    matrix: Matrix,
    elements: Sequence[str],
    classes: Sequence[ElementClass],
) -> tuple[list[ExpectedValue], list[str]]:
    """List the values the elements an Epic's design adds or changes must state.

    Args:
        matrix: The matrix, with the design recorded (or the architect's change file applied).
        elements: The matrix ids of the elements, as the result lists them under ``addedOrChangedElements``.
        classes: The checklist's classes of element (:func:`load_checklist`).

    Returns:
        One expected value per element and item, in element order; and each element the matrix
        holds no entry for.

    """
    expected: list[ExpectedValue] = []
    unknown: list[str] = []
    element: str
    for element in dict.fromkeys(stated.strip() for stated in elements):
        items: tuple[Item, ...] | None = _items_of(matrix, element, classes)
        if items is None:
            unknown.append(element)
            continue
        expected.extend(
            {"element": element, "criterion": item.criterion, "item": item.item, "namingCommand": item.naming_command}
            for item in items
        )
    return expected, unknown


def skeleton(expected: Sequence[ExpectedValue]) -> list[dict[str, object]]:
    """Write the entries of ``elementValues`` the architect fills, one per value it must state.

    Returns:
        One entry per value the naming command does not build, with an empty value and home.

    """
    return [
        {
            "element": value["element"],
            "criterion": value["criterion"],
            "item": value["item"],
            "applies": True,
            "value": "",
            "home": {"source": "", "heading": ""},
        }
        for value in expected
        if not value["namingCommand"]
    ]


def normalized(text: str) -> str:
    """Reduce text to its words, for comparing a value with the heading that states it.

    Returns:
        The text in lower case, without Markdown emphasis, code, table or heading marks, with
        every run of white space one space.

    """
    return _SPACE.sub(" ", _MARKUP.sub("", text)).strip().casefold()


def heading_text(arch: Path, home: Home) -> str | None:
    """Read the own text of one heading of an architecture document, as the vault's working tree holds it.

    Args:
        arch: The architecture root.
        home: The document's path under the root (or absolute inside it) and the heading's key.

    Returns:
        The heading line and everything up to the next heading; None when the document or the
        heading does not exist.

    """
    stated: str = home["source"].strip().removeprefix(DOCUMENT_PREFIX)
    given: Path = Path(stated)
    path: Path = given if given.is_absolute() else arch / given
    if not stated or not path.is_file():
        return None
    texts: dict[str, str] = heading_texts(document_body(path.read_text(encoding="utf-8")))
    return texts.get(home["heading"].strip().lstrip("#").strip())


def states_value(arch: Path, home: Home, value: str) -> bool:
    """Tell whether a heading states a value, word for word.

    Returns:
        True when the heading exists and its text holds the value, compared by :func:`normalized`.

    """
    text: str | None = heading_text(arch, home)
    return text is not None and normalized(value) in normalized(text)


def _text(entry: Mapping[str, object], key: str) -> str:
    """Read one text member of an entry of ``elementValues``.

    Returns:
        The member, stripped; empty when it is absent or not text.

    """
    held: object = entry.get(key)
    return held.strip() if isinstance(held, str) else ""


def _home(entry: Mapping[str, object]) -> Home | None:
    """Read the home an entry of ``elementValues`` cites.

    Returns:
        The home; None when the entry names none, or names it without a source or a heading.

    """
    held: object = entry.get("home")
    if not isinstance(held, Mapping):
        return None
    source: object = held.get("source")
    heading: object = held.get("heading")
    if not isinstance(source, str) or not isinstance(heading, str) or not source.strip() or not heading.strip():
        return None
    return {"source": source, "heading": heading}


def _entry_problem(arch: Path, entry: Mapping[str, object]) -> str | None:
    """Find what is wrong with one entry of ``elementValues``.

    Returns:
        The sentence that says why the entry does not state its value; None when it does.

    """
    value: str = _text(entry, "value")
    if entry.get("applies") is False:
        return None if value else "is marked as not applying and gives no reason in value"
    home: Home | None = _home(entry)
    if not value:
        return "is empty: state the value in value"
    if home is None:
        return "names no home: cite the architecture heading that states the value"
    if heading_text(arch, home) is None:
        return f"cites {home['source']}#{home['heading']}, which does not exist"
    if not states_value(arch, home, value):
        return f"cites {home['source']}#{home['heading']}, which does not state the value {value!r} word for word"
    return None


def value_problems(
    expected: Sequence[ExpectedValue],
    given: Sequence[Mapping[str, object]],
    arch: Path,
    carried: Collection[tuple[str, str, str]] = (),
) -> list[UnfilledValue]:
    """Find each value the architect's result leaves unfilled or does not find stated where it says.

    Args:
        expected: The values the elements must state (:func:`expected_values`).
        given: The result's ``elementValues``.
        arch: The architecture root, whose working tree the cited headings are read from.
        carried: The values already carried to the spec stage, by element, criterion and item;
            they are not reported again.

    Returns:
        One unfilled value for each value the naming command does not build that has no entry,
        an empty entry, an entry citing a heading that does not exist, or a heading that does not
        state the value word for word; in the order of ``expected``.

    """
    entries: dict[tuple[str, str, str], Mapping[str, object]] = {
        (_text(entry, "element"), _text(entry, "criterion"), _text(entry, "item")): entry for entry in given
    }
    unfilled: list[UnfilledValue] = []
    value: ExpectedValue
    for value in expected:
        key: tuple[str, str, str] = (value["element"], value["criterion"], value["item"])
        if value["namingCommand"] or key in carried:
            continue
        entry: Mapping[str, object] | None = entries.get(key)
        problem: str | None = "has no entry in elementValues" if entry is None else _entry_problem(arch, entry)
        if problem is not None:
            unfilled.append({**value_key(value), "problem": problem})
    return unfilled


def value_key(value: ExpectedValue | UnfilledValue) -> UnfilledValue:
    """Name one value by its element, criterion and item.

    Returns:
        The value with an empty problem.

    """
    return {"element": value["element"], "criterion": value["criterion"], "item": value["item"], "problem": ""}


def sentence(unfilled: UnfilledValue) -> str:
    """State one unfilled value as a problem of the architecture check.

    Returns:
        One sentence naming the element, the criterion, the item and what is wrong.

    """
    return (
        f"elementValues: {unfilled['element']} {unfilled['criterion']} {unfilled['item']!r} {unfilled['problem']} "
        "(atw-matrix element-checklist lists every value an element must state)"
    )
