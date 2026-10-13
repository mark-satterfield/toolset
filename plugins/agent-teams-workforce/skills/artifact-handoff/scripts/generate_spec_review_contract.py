"""Generate spec_review_contract.py from schemas/spec-review.schema.json, or check that it is current.

The schema is the one definition of the spec review: the reviewer's result, an author's
correction and the decider's ruling. This script derives the Python types, the wire constants and
the validating readers from it, and confirms that spec-correction.schema.json and
spec-ruling.schema.json refer to it. With --check it writes nothing and exits 1 when the
generated module differs from what it would write.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SCHEMA_DIR: Final[Path] = SCRIPTS_DIR.parent / "schemas"
SCHEMA_NAME: Final[str] = "spec-review.schema.json"
SCHEMA_PATH: Final[Path] = SCHEMA_DIR / SCHEMA_NAME
OUTPUT_PATH: Final[Path] = SCRIPTS_DIR / "spec_review_contract.py"
DEFINITIONS: Final[str] = "$defs"
REF_PREFIX: Final[str] = "#/$defs/"

# (alias name, constant prefix, collection constant, $defs entry) for every string vocabulary.
VOCABULARIES: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("SpecDocument", "DOCUMENT", "SPEC_DOCUMENTS", "SpecDocument"),
    ("RulingValue", "RULING", "RULING_VALUES", "RulingValue"),
)
# Every $defs entry the module types as a TypedDict of the same name, each after the ones it uses.
RECORDS: Final[tuple[str, ...]] = ("Finding", "SpecReview", "Dispute", "SpecCorrection", "Ruling", "SpecRuling")
# (constant name, reader suffix, $defs entry, schema file) for every document an agent writes.
DOCUMENTS: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("SPEC_REVIEW_SCHEMA_PATH", "spec_review", "SpecReview", SCHEMA_NAME),
    ("SPEC_CORRECTION_SCHEMA_PATH", "spec_correction", "SpecCorrection", "spec-correction.schema.json"),
    ("SPEC_RULING_SCHEMA_PATH", "spec_ruling", "SpecRuling", "spec-ruling.schema.json"),
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
        message: str = f"spec review schema: {where} is not an object"
        raise SchemaShapeError(message)
    result: dict[str, object] = {}
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            message = f"spec review schema: {where} has a non-string key"
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
        message: str = f"spec review schema: {where} is not a list"
        raise SchemaShapeError(message)
    result: list[str] = []
    item: object
    for item in value:
        if not isinstance(item, str) or not item:
            message = f"spec review schema: {where} holds a value that is not a nonempty string"
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
        message: str = f"spec review schema: {where} is not a nonempty string"
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
        message: str = f"spec review schema: wire value {value!r} cannot name a constant"
        raise SchemaShapeError(message)
    return name


def _referenced(node: Mapping[str, object], where: str, known: Mapping[str, str]) -> str | None:
    """Name the Python type a node's $ref stands for.

    Returns:
        The type name, or None when the node has no $ref.

    Raises:
        SchemaShapeError: The $ref names something the module does not type.

    """
    if "$ref" not in node:
        return None
    pointer: str = _text(node["$ref"], where + "/$ref")
    name: str = pointer.removeprefix(REF_PREFIX)
    if not pointer.startswith(REF_PREFIX) or name not in known:
        message: str = f"spec review schema: {where} refers to {pointer}, which the generator does not type"
        raise SchemaShapeError(message)
    return known[name]


def _field_type(node: Mapping[str, object], where: str, known: Mapping[str, str]) -> str:
    """Render the Python type of one property.

    Returns:
        Python source for the property's type.

    Raises:
        SchemaShapeError: The property uses a construct the generator does not type.

    """
    referenced: str | None = _referenced(node, where, known)
    if referenced is not None:
        return referenced
    kind: str = _text(node.get("type"), where + "/type")
    if kind == "string":
        return "str"
    if kind == "array":
        items: dict[str, object] = _node(node.get("items"), where + "/items")
        return f"list[{_field_type(items, where + '/items', known)}]"
    message: str = f"spec review schema: {where} has type {kind!r}, which the generator does not type"
    raise SchemaShapeError(message)


def _record(definitions: Mapping[str, object], name: str, known: Mapping[str, str]) -> list[str]:
    """Render one closed schema object, every property of which is required, as a TypedDict.

    Returns:
        The class source lines.

    Raises:
        SchemaShapeError: The object is open or leaves a declared property optional.

    """
    pointer: str = REF_PREFIX + name
    node: dict[str, object] = _node(definitions.get(name), pointer)
    properties: dict[str, object] = _node(node.get("properties"), pointer + "/properties")
    required: list[str] = _strings(node.get("required"), pointer + "/required")
    if node.get("additionalProperties") is not False or sorted(required) != sorted(properties):
        message: str = f"spec review schema: {pointer} must be a closed object whose every property is required"
        raise SchemaShapeError(message)
    lines: list[str] = [f"class {name}(TypedDict):", f'    """Typed form of {pointer} in {SCHEMA_NAME}."""', ""]
    key: str
    spec: object
    for key, spec in properties.items():
        where: str = pointer + "/properties/" + key
        lines.append(f"    {key}: {_field_type(_node(spec, where), where, known)}")
    return lines


def _check_wrappers() -> None:
    """Confirm each document's schema file is the root schema or a reference to its definition.

    Raises:
        SchemaShapeError: A schema file does not refer to its definition in the root schema.

    """
    entry: str
    file_name: str
    for _, _, entry, file_name in DOCUMENTS:
        wrapper: dict[str, object] = _node(json.loads((SCHEMA_DIR / file_name).read_text(encoding="utf-8")), file_name)
        expected: str = REF_PREFIX + entry if file_name == SCHEMA_NAME else SCHEMA_NAME + REF_PREFIX + entry
        if wrapper.get("$ref") != expected:
            message: str = f"{file_name}: $ref must be {expected}"
            raise SchemaShapeError(message)


def render(schema: Mapping[str, object]) -> str:
    """Render the generated module for a spec review schema.

    Returns:
        The complete Python source of spec_review_contract.py.

    """
    definitions: dict[str, object] = _node(schema.get(DEFINITIONS), "#/" + DEFINITIONS)
    known: dict[str, str] = {}
    vocab_lines: list[str] = []
    const_lines: list[str] = []
    collection_lines: list[str] = []
    alias: str
    prefix: str
    collection: str
    entry: str
    for alias, prefix, collection, entry in VOCABULARIES:
        where: str = REF_PREFIX + entry
        values: list[str] = _strings(_node(definitions.get(entry), where).get("enum"), where + "/enum")
        known[entry] = alias
        vocab_lines.append(f"type {alias} = {_literal(values)}")
        const_lines.extend(
            f"{_constant_name(prefix, value)}: Final[{_literal([value])}] = {json.dumps(value)}" for value in values
        )
        members: str = "".join(f"\n    {_constant_name(prefix, value)}," for value in values)
        collection_lines.append(f"{collection}: Final[tuple[{alias}, ...]] = ({members}\n)")
    record_lines: list[str] = []
    name: str
    for name in RECORDS:
        record_lines.extend(["", "", *_record(definitions, name, known)])
        known[name] = name
    path_lines: list[str] = []
    reader_lines: list[str] = []
    constant: str
    suffix: str
    file_name: str
    for constant, suffix, entry, file_name in DOCUMENTS:
        path_lines.append(f"{constant}: Final[Path] = SCHEMA_DIR / {json.dumps(file_name)}")
        reader_lines.append(READER.replace("@SUFFIX@", suffix).replace("@RECORD@", entry))
    parts: list[str] = [
        f'"""GENERATED by {Path(__file__).name} from schemas/{SCHEMA_NAME}. Do not edit.',
        "",
        "The spec review contract: the reviewer's result for one repository's specification documents,",
        "an author's correction and the decider's ruling on a dispute. Readers and writers import every",
        "type and value from here and validate documents with the readers below. Regenerate with",
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
        *vocab_lines,
        "",
        *const_lines,
        "",
        *collection_lines,
        'SCHEMA_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "schemas"',
        *path_lines,
        *record_lines,
        "",
        "",
        TAIL.rstrip("\n"),
        *reader_lines,
    ]
    return "\n".join(parts).rstrip("\n") + "\n"


TAIL: Final[str] = '''class SpecReviewError(ValueError):
    """A document does not satisfy the spec review schema."""


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
                message: str = "spec review schema holds a non-string object key"
                raise TypeError(message)
            result[key] = _json_value(item)
        return result
    message = f"spec review schema holds a non-JSON value of type {type(value).__name__}"
    raise TypeError(message)


def load_schema() -> dict[str, JsonValue]:
    """Load the spec review JSON Schema, the one definition of this contract.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The schema document.

    Raises:
        TypeError: The schema file is not a JSON object.

    """
    schema: JsonValue = _json_value(json.loads(SPEC_REVIEW_SCHEMA_PATH.read_text(encoding="utf-8")))
    if not isinstance(schema, dict):
        message: str = f"{SPEC_REVIEW_SCHEMA_PATH} is not a JSON object"
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
        message: str = f"spec review schema defines no {definition!r}"
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
        SpecReviewError: The value does not satisfy the @RECORD@ definition.

    """
    if is_@SUFFIX@(value):
        return value
    message: str = f"{where} does not satisfy @RECORD@: " + "; ".join(schema_problems(value, "@RECORD@"))
    raise SpecReviewError(message)'''


def main() -> int:
    """Write the generated module, or with --check report whether it is current.

    Returns:
        0 when written or current, 1 when --check finds it stale or missing.

    Raises:
        TypeError: The parsed --check flag is not a boolean.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when spec_review_contract.py is stale")
    args: argparse.Namespace = parser.parse_args()
    check: object = args.check
    if not isinstance(check, bool):
        message: str = "--check must be a flag"
        raise TypeError(message)
    _check_wrappers()
    decoded: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    expected: str = render(_node(decoded, "#"))
    if check:
        current: str | None = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.is_file() else None
        if current != expected:
            sys.stderr.write(f"{OUTPUT_PATH} is stale against {SCHEMA_PATH}; run {Path(__file__).name}\n")
            return 1
        return 0
    OUTPUT_PATH.write_text(expected, encoding="utf-8")
    sys.stdout.write(f"wrote {OUTPUT_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
