"""Generate architecture_work_contract.py and the wrapper schemas from schemas/architecture-result.schema.json.

The schema is the one definition of every file the architecture team of one Epic hands to each
other and to the script. This script derives the Python types, the wire constants and the
validating readers from it, and writes one wrapper schema file for each document other than the
root, so an agent is pointed at one file per document. With --check it writes nothing and exits 1
when the generated module or a wrapper differs from what it would write.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SCHEMA_DIR: Final[Path] = SCRIPTS_DIR.parent / "schemas"
SCHEMA_NAME: Final[str] = "architecture-result.schema.json"
SCHEMA_PATH: Final[Path] = SCHEMA_DIR / SCHEMA_NAME
OUTPUT_PATH: Final[Path] = SCRIPTS_DIR / "architecture_work_contract.py"
DEFINITIONS: Final[str] = "$defs"
REF_PREFIX: Final[str] = "#/$defs/"
DRAFT: Final[str] = "https://json-schema.org/draft/2020-12/schema"

# (constant prefix, collection constant) for every string vocabulary, keyed by its $defs entry.
VOCABULARIES: Final[dict[str, tuple[str, str]]] = {
    "NeedState": ("NEED", "NEED_STATES"),
    "StateConclusion": ("STATE", "STATE_CONCLUSIONS"),
    "Conclusion": ("CONCLUSION", "CONCLUSIONS"),
    "CriterionStatus": ("CRITERION", "CRITERION_STATUSES"),
    "UnsettledKind": ("UNSETTLED", "UNSETTLED_KINDS"),
    "RequestKind": ("REQUEST", "REQUEST_KINDS"),
    "TrdMode": ("TRD_MODE", "TRD_MODES"),
    "TrdChangeKind": ("TRD_CHANGE", "TRD_CHANGE_KINDS"),
    "RequirementKind": ("REQUIREMENT", "REQUIREMENT_KINDS"),
    "Routing": ("ROUTING", "ROUTINGS"),
    "OwnerConcernKind": ("OWNER_CONCERN", "OWNER_CONCERN_KINDS"),
}
# (reader suffix, $defs entry, schema file, who writes it) for every document an agent writes.
DOCUMENTS: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("architecture_result", "ArchitectureResult", SCHEMA_NAME, "The solutions architect's result"),
    ("architecture_state", "ArchitectureState", "architecture-state.schema.json", "The solutions architect's state"),
    ("specialist_request", "SpecialistRequest", "specialist-request.schema.json", "A request to a specialist"),
    ("specialist_answer", "SpecialistAnswer", "specialist-answer.schema.json", "A specialist's answer"),
    ("trd_request", "TrdRequest", "trd-request.schema.json", "A request to trd-author"),
    ("trd_answer", "TrdAnswer", "trd-answer.schema.json", "trd-author's answer"),
    ("write_request", "WriteRequest", "write-request.schema.json", "A write request to architecture-maintainer"),
    ("write_result", "WriteResult", "write-result.schema.json", "architecture-maintainer's write result"),
    ("scope_review", "ScopeReview", "scope-review.schema.json", "A reviewer's result for the unapproved content"),
    ("lead_routing", "LeadRouting", "lead-routing.schema.json", "architecture-team-lead's routing"),
    ("architecture_question", "UnsettledMatter", "architecture-question.schema.json", "The question for the decider"),
    ("architecture_ruling", "ArchitectureRuling", "architecture-ruling.schema.json", "architecture-decider's ruling"),
    ("built_comparison", "BuiltComparison", "built-comparison.schema.json", "built-architecture-comparer's result"),
)


class SchemaShapeError(ValueError):
    """The schema is missing a part of the contract or uses a construct the generator does not type."""


def _node(value: object, where: str) -> dict[str, object]:
    """Narrow a decoded JSON value to an object.

    Returns:
        The value as a string-keyed dictionary.

    Raises:
        SchemaShapeError: The value is not a JSON object with string keys.

    """
    if not isinstance(value, dict):
        message: str = f"architecture work schema: {where} is not an object"
        raise SchemaShapeError(message)
    result: dict[str, object] = {}
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            message = f"architecture work schema: {where} has a non-string key"
            raise SchemaShapeError(message)
        result[key] = item
    return result


def _strings(value: object, where: str) -> list[str]:
    """Narrow a decoded JSON value to a list of nonempty strings.

    Returns:
        The strings in their schema order.

    Raises:
        SchemaShapeError: The value is not a list of nonempty strings.

    """
    if not isinstance(value, list):
        message: str = f"architecture work schema: {where} is not a list"
        raise SchemaShapeError(message)
    result: list[str] = []
    item: object
    for item in value:
        if not isinstance(item, str) or not item:
            message = f"architecture work schema: {where} holds a value that is not a nonempty string"
            raise SchemaShapeError(message)
        result.append(item)
    return result


def _text(value: object, where: str) -> str:
    """Narrow a decoded JSON value to a nonempty string.

    Returns:
        The string.

    Raises:
        SchemaShapeError: The value is not a nonempty string.

    """
    if not isinstance(value, str) or not value:
        message: str = f"architecture work schema: {where} is not a nonempty string"
        raise SchemaShapeError(message)
    return value


def _literal(values: Sequence[str]) -> str:
    """Render string values as a Literal type.

    Returns:
        Python source for the Literal.

    """
    return "Literal[" + ", ".join(json.dumps(value) for value in values) + "]"


def _constant_name(prefix: str, value: str) -> str:
    """Name the constant that carries one wire value.

    Returns:
        PREFIX_VALUE in upper snake case.

    Raises:
        SchemaShapeError: The value cannot form a Python identifier.

    """
    name: str = prefix + "_" + value.upper().replace("-", "_")
    if not name.isidentifier():
        message: str = f"architecture work schema: wire value {value!r} cannot name a constant"
        raise SchemaShapeError(message)
    return name


def _field_type(node: Mapping[str, object], where: str, known: Sequence[str]) -> str:
    """Render the Python type of one property.

    Returns:
        Python source for the property's type.

    Raises:
        SchemaShapeError: The property uses a construct the generator does not type, or refers
            to a definition that is not written before it.

    """
    if "$ref" in node:
        pointer: str = _text(node["$ref"], where + "/$ref")
        name: str = pointer.removeprefix(REF_PREFIX)
        if not pointer.startswith(REF_PREFIX) or name not in known:
            message: str = f"architecture work schema: {where} refers to {pointer}, which is not defined before it"
            raise SchemaShapeError(message)
        return name
    kind: str = _text(node.get("type"), where + "/type")
    if kind == "string":
        return "str"
    if kind == "array":
        items: dict[str, object] = _node(node.get("items"), where + "/items")
        return f"list[{_field_type(items, where + '/items', known)}]"
    message = f"architecture work schema: {where} has type {kind!r}, which the generator does not type"
    raise SchemaShapeError(message)


def _record(name: str, node: Mapping[str, object], known: Sequence[str]) -> list[str]:
    """Render one closed schema object, every property of which is required, as a TypedDict.

    Returns:
        The class source lines.

    Raises:
        SchemaShapeError: The object is open, leaves a declared property optional, or names a
            property that cannot be a Python attribute.

    """
    pointer: str = REF_PREFIX + name
    properties: dict[str, object] = _node(node.get("properties"), pointer + "/properties")
    required: list[str] = _strings(node.get("required"), pointer + "/required")
    if node.get("additionalProperties") is not False or sorted(required) != sorted(properties):
        message: str = f"architecture work schema: {pointer} must be a closed object whose every property is required"
        raise SchemaShapeError(message)
    lines: list[str] = [f"class {name}(TypedDict):", f'    """Typed form of {pointer} in {SCHEMA_NAME}."""', ""]
    key: str
    spec: object
    for key, spec in properties.items():
        where: str = pointer + "/properties/" + key
        if not key.isidentifier() or key in {"from", "class", "import", "global", "pass", "in", "is"}:
            message = f"architecture work schema: {where} cannot name a TypedDict field"
            raise SchemaShapeError(message)
        lines.append(f"    {key}: {_field_type(_node(spec, where), where, known)}")
    return lines


def wrappers() -> dict[str, str]:
    """Render the wrapper schema file of every document other than the root.

    Returns:
        The text of each wrapper file by file name.

    """
    rendered: dict[str, str] = {}
    entry: str
    file_name: str
    what: str
    for _, entry, file_name, what in DOCUMENTS:
        if file_name == SCHEMA_NAME:
            continue
        wrapper: dict[str, str] = {
            "$schema": DRAFT,
            "description": f"{what} is defined once, as {SCHEMA_NAME}{REF_PREFIX}{entry}.",
            "$ref": f"{SCHEMA_NAME}{REF_PREFIX}{entry}",
        }
        rendered[file_name] = json.dumps(wrapper, indent=2) + "\n"
    return rendered


@dataclass(frozen=True, slots=True)
class Sections:
    """The source lines the definitions of the schema give, by the part of the module they go in."""

    vocabularies: list[str]
    constants: list[str]
    collections: list[str]
    records: list[str]


def _sections(definitions: Mapping[str, object]) -> Sections:
    """Render every definition of the schema, in schema order.

    Returns:
        The type aliases, the wire constants, their collections and the TypedDict classes.

    Raises:
        SchemaShapeError: A definition is neither a declared vocabulary nor a closed object, or a
            declared vocabulary or document is not defined.

    """
    sections: Sections = Sections([], [], [], [])
    known: list[str] = []
    name: str
    raw: object
    for name, raw in definitions.items():
        where: str = REF_PREFIX + name
        node: dict[str, object] = _node(raw, where)
        if name in VOCABULARIES:
            prefix: str
            collection: str
            prefix, collection = VOCABULARIES[name]
            values: list[str] = _strings(node.get("enum"), where + "/enum")
            sections.vocabularies.append(f"type {name} = {_literal(values)}")
            sections.constants.extend(
                f"{_constant_name(prefix, value)}: Final[{_literal([value])}] = {json.dumps(value)}" for value in values
            )
            members: str = "".join(f"\n    {_constant_name(prefix, value)}," for value in values)
            sections.collections.append(f"{collection}: Final[tuple[{name}, ...]] = ({members}\n)")
        elif node.get("type") == "object":
            sections.records.extend(["", "", *_record(name, node, known)])
        else:
            message: str = f"architecture work schema: {where} is neither a declared vocabulary nor an object"
            raise SchemaShapeError(message)
        known.append(name)
    undefined: list[str] = sorted((set(VOCABULARIES) | {entry for _, entry, _, _ in DOCUMENTS}) - set(known))
    if undefined:
        message = f"architecture work schema: defines no {undefined}"
        raise SchemaShapeError(message)
    return sections


def render(schema: Mapping[str, object]) -> str:
    """Render the generated module for the architecture work schema.

    A definition the generator cannot type fails with the SchemaShapeError of ``_sections``.

    Returns:
        The complete Python source of architecture_work_contract.py.

    Raises:
        SchemaShapeError: The root of the schema is not the first document.

    """
    if schema.get("$ref") != REF_PREFIX + DOCUMENTS[0][1]:
        message: str = f"architecture work schema: the root must be {REF_PREFIX}{DOCUMENTS[0][1]}"
        raise SchemaShapeError(message)
    sections: Sections = _sections(_node(schema.get(DEFINITIONS), "#/" + DEFINITIONS))
    path_lines: list[str] = []
    reader_lines: list[str] = []
    suffix: str
    entry: str
    file_name: str
    for suffix, entry, file_name, _ in DOCUMENTS:
        path_lines.append(f"{suffix.upper()}_SCHEMA_PATH: Final[Path] = SCHEMA_DIR / {json.dumps(file_name)}")
        reader_lines.append(READER.replace("@SUFFIX@", suffix).replace("@RECORD@", entry))
    parts: list[str] = [
        f'"""GENERATED by {Path(__file__).name} from schemas/{SCHEMA_NAME}. Do not edit.',
        "",
        "The architecture work contract: every file the architecture team of one Epic hands to each",
        "other and to the script. Readers and writers import every type and value from here and",
        "validate documents with the readers below. Regenerate with",
        f"`python {Path(__file__).name}`; `--check` fails when this file is stale.",
        '"""',
        "",
        "import json",
        "from pathlib import Path",
        "from typing import Final, Literal, TypedDict, TypeIs",
        "",
        "from jsonschema import Draft202012Validator",
        "from jsonschema.exceptions import best_match",
        "",
        "type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None",
        *sections.vocabularies,
        "",
        *sections.constants,
        "",
        *sections.collections,
        'SCHEMA_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "schemas"',
        *path_lines,
        *sections.records,
        "",
        "",
        TAIL.rstrip("\n"),
        *reader_lines,
    ]
    return "\n".join(parts).rstrip("\n") + "\n"


TAIL: Final[str] = '''class ArchitectureWorkError(ValueError):
    """A document does not satisfy the architecture work schema."""


def _json_value(value: object) -> JsonValue:
    """Narrow a decoded JSON value to the JSON value type.

    Returns:
        The same value, typed.

    Raises:
        TypeError: The value holds something JSON does not.

    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        key: object
        item: object
        for key, item in value.items():
            if not isinstance(key, str):
                message: str = "architecture work schema holds a non-string object key"
                raise TypeError(message)
            result[key] = _json_value(item)
        return result
    message = f"architecture work schema holds a non-JSON value of type {type(value).__name__}"
    raise TypeError(message)


def load_schema() -> dict[str, JsonValue]:
    """Load the architecture work JSON Schema, the one definition of this contract.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The schema document.

    Raises:
        TypeError: The schema file is not a JSON object.

    """
    schema: JsonValue = _json_value(json.loads(ARCHITECTURE_RESULT_SCHEMA_PATH.read_text(encoding="utf-8")))
    if not isinstance(schema, dict):
        message: str = f"{ARCHITECTURE_RESULT_SCHEMA_PATH} is not a JSON object"
        raise TypeError(message)
    return schema


def schema_problems(value: object, definition: str) -> list[str]:
    """Describe every way a value fails one definition of the schema.

    Args:
        value: The decoded document.
        definition: The $defs entry to validate against.

    Returns:
        One "<path>: <message>" per failure, in document order; empty when the value conforms.

    Raises:
        ValueError: The schema defines no such entry.

    """
    definitions: JsonValue = load_schema().get("$defs")
    if not isinstance(definitions, dict) or definition not in definitions:
        message: str = f"architecture work schema defines no {definition!r}"
        raise ValueError(message)
    target: dict[str, JsonValue] = {"$ref": "#/$defs/" + definition, "$defs": definitions}
    problems: list[tuple[list[str], str]] = []
    for error in Draft202012Validator(target).iter_errors(value):
        relevant = best_match([error]) or error
        path: list[str] = [str(part) for part in relevant.absolute_path]
        problems.append((path, f"{'/'.join(path) or '<root>'}: {relevant.message}"))
    return [text for _, text in sorted(problems)]
'''

READER: Final[str] = '''

def is_@SUFFIX@(value: object) -> TypeIs[@RECORD@]:
    """Tell whether a value satisfies the @RECORD@ definition.

    Returns:
        True when the schema accepts the value.

    """
    return not schema_problems(value, "@RECORD@")


def validate_@SUFFIX@(value: object, where: str = "@RECORD@") -> @RECORD@:
    """Validate a decoded @RECORD@ document.

    Returns:
        The value, typed.

    Raises:
        ArchitectureWorkError: The value does not satisfy the @RECORD@ definition.

    """
    if is_@SUFFIX@(value):
        return value
    problems: str = "; ".join(schema_problems(value, "@RECORD@"))
    message: str = f"{where} does not satisfy @RECORD@: {problems}"
    raise ArchitectureWorkError(message)'''


def main() -> int:
    """Write the generated module and the wrapper schemas, or with --check report whether they are current.

    Returns:
        0 when written or current, 1 when --check finds a file stale or missing.

    Raises:
        TypeError: The parsed --check flag is not a boolean.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when a generated file is stale")
    args: argparse.Namespace = parser.parse_args()
    check: object = args.check
    if not isinstance(check, bool):
        message: str = "--check must be a flag"
        raise TypeError(message)
    decoded: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    expected: dict[Path, str] = {OUTPUT_PATH: render(_node(decoded, "#"))}
    expected.update({SCHEMA_DIR / name: text for name, text in wrappers().items()})
    path: Path
    text: str
    if check:
        stale: list[str] = [
            str(path)
            for path, text in expected.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != text
        ]
        if stale:
            sys.stderr.write(f"stale against {SCHEMA_PATH}: {stale}; run {Path(__file__).name}\n")
            return 1
        return 0
    for path, text in expected.items():
        path.write_text(text, encoding="utf-8")
        sys.stdout.write(f"wrote {path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
