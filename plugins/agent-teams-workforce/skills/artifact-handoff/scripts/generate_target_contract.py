"""Generate target_contract.py from schemas/target-report.schema.json, or check that it is current.

The schema is the one definition of the architecture target and delta report contract. This
script derives the Python types, the wire constants and the validating readers from it. With
--check it writes nothing and exits 1 when the generated module differs from what it would write.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SCHEMA_PATH: Final[Path] = SCRIPTS_DIR.parent / "schemas" / "target-report.schema.json"
OUTPUT_PATH: Final[Path] = SCRIPTS_DIR / "target_contract.py"

DEFS: Final[str] = "$defs"
REF_PREFIX: Final[str] = "#/$defs/"

# (alias name, constant prefix, collection constant) for every string vocabulary in $defs.
VOCABULARIES: Final[tuple[tuple[str, str, str], ...]] = (
    ("ArchitectureChange", "CHANGE", "ARCHITECTURE_CHANGES"),
    ("DeltaItemKind", "KIND", "DELTA_ITEM_KINDS"),
    ("ElementState", "STATE", "ELEMENT_STATES"),
)
# Every closed object in $defs the module types, dependencies first.
RECORDS: Final[tuple[str, ...]] = (
    "TargetSummary",
    "TargetResult",
    "DeltaView",
    "DeltaItem",
    "DeltaSummary",
    "DeltaResult",
    "TargetNamesSummary",
    "TargetNames",
)
# (constant name, x-files key) for every file and folder name the contract fixes.
FILE_CONSTANTS: Final[tuple[tuple[str, str], ...]] = (
    ("ARCHITECTURE_WORK_FOLDER", "architectureWork"),
    ("TARGET_REPORT_NAME", "targetReport"),
    ("TARGET_CHECK_FILE", "targetCheck"),
    ("DELTA_ITEMS_FILE", "deltaItems"),
    ("CLOSURE_ROOTS_FILE", "closureRoots"),
    ("TARGET_FOLDER", "targetFolder"),
    ("DELTA_FOLDER", "deltaFolder"),
    ("BASELINE_FILE", "baselineFile"),
    ("CLOSURE_FILE", "closureFile"),
)
# (constant name, schema key, record whose properties the keys must be) for every key tuple.
KEY_TUPLES: Final[tuple[tuple[str, str, str], ...]] = (
    ("TARGET_REFUSAL_KEYS", "x-targetRefusalKeys", "TargetResult"),
    ("TARGET_SUMMARY_KEYS", "x-targetSummaryKeys", "TargetSummary"),
    ("TARGET_SUMMARY_COUNT_KEYS", "x-targetSummaryCountKeys", "TargetSummary"),
    ("TARGET_MANIFEST_SUMMARY_KEYS", "x-targetManifestSummaryKeys", "TargetSummary"),
)
SCALARS: Final[dict[str, str]] = {"string": "str", "boolean": "bool", "integer": "int", "null": "None"}
_CAMEL: Final[re.Pattern[str]] = re.compile(r"(?<=[a-z0-9])([A-Z])")


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
        message: str = f"target report schema: {where} is not an object"
        raise SchemaShapeError(message)
    result: dict[str, object] = {}
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            message = f"target report schema: {where} has a non-string key"
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
        message: str = f"target report schema: {where} is not a list"
        raise SchemaShapeError(message)
    result: list[str] = []
    item: object
    for item in value:
        if not isinstance(item, str) or not item:
            message = f"target report schema: {where} holds a value that is not a nonempty string"
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
        message: str = f"target report schema: {where} is not a nonempty string"
        raise SchemaShapeError(message)
    return value


def _literal(values: Sequence[str]) -> str:
    """Render string values as a Literal type.

    Returns:
        Python source for the Literal.

    """
    return "Literal[" + ", ".join(json.dumps(value) for value in values) + "]"


def _upper_snake(name: str) -> str:
    """Turn a camelCase, snake_case or kebab-case wire name into UPPER_SNAKE.

    Returns:
        The name in upper snake case.

    Raises:
        SchemaShapeError: The name cannot form a Python identifier.

    """
    result: str = _CAMEL.sub(r"_\1", name).replace("-", "_").upper()
    if not result.isidentifier():
        message: str = f"target report schema: wire name {name!r} cannot name a constant"
        raise SchemaShapeError(message)
    return result


def _ref_name(node: Mapping[str, object], where: str) -> str | None:
    """Name the $defs entry a node references.

    Returns:
        The $defs entry name, or None when the node has no $ref.

    Raises:
        SchemaShapeError: The $ref is not a local $defs reference.

    """
    if "$ref" not in node:
        return None
    pointer: str = _text(node["$ref"], where + "/$ref")
    if not pointer.startswith(REF_PREFIX) or "/" in pointer.removeprefix(REF_PREFIX):
        message: str = f"target report schema: {where} references {pointer}, not a $defs entry"
        raise SchemaShapeError(message)
    return pointer.removeprefix(REF_PREFIX)


def _type_names(node: Mapping[str, object], where: str) -> list[str]:
    """Read a node's JSON type or types.

    Returns:
        The JSON type names in schema order.

    Raises:
        SchemaShapeError: The node declares no type.

    """
    declared: object = node.get("type")
    if isinstance(declared, str):
        return [declared]
    if isinstance(declared, list):
        return _strings(declared, where + "/type")
    message: str = f"target report schema: {where} declares no type"
    raise SchemaShapeError(message)


def _field_type(node: Mapping[str, object], where: str, known: Mapping[str, str]) -> str:
    """Render the Python type of one property.

    Returns:
        Python source for the property's type.

    Raises:
        SchemaShapeError: The property uses a construct the generator does not type.

    """
    referenced: str | None = _ref_name(node, where)
    if referenced is not None:
        if referenced not in known:
            message: str = f"target report schema: {where} references {referenced}, which is not typed before it"
            raise SchemaShapeError(message)
        return known[referenced]
    parts: list[str] = []
    kind: str
    for kind in _type_names(node, where):
        if kind in SCALARS:
            parts.append(SCALARS[kind])
        elif kind == "array":
            items: dict[str, object] = _node(node.get("items"), where + "/items")
            parts.append(f"list[{_field_type(items, where + '/items', known)}]")
        elif kind == "object":
            values: dict[str, object] = _node(node.get("additionalProperties"), where + "/additionalProperties")
            parts.append(f"dict[str, {_field_type(values, where + '/additionalProperties', known)}]")
        else:
            message = f"target report schema: {where} has type {kind!r}, which the generator does not type"
            raise SchemaShapeError(message)
    return " | ".join(parts)


def _record(definitions: Mapping[str, object], name: str, known: Mapping[str, str]) -> tuple[list[str], list[str]]:
    """Render one closed $defs object as a TypedDict.

    Returns:
        The class source lines and the object's property names.

    Raises:
        SchemaShapeError: The object is open or requires a property it does not declare.

    """
    where: str = REF_PREFIX + name
    node: dict[str, object] = _node(definitions.get(name), where)
    if node.get("additionalProperties") is not False:
        message: str = f"target report schema: {where} must be a closed object"
        raise SchemaShapeError(message)
    properties: dict[str, object] = _node(node.get("properties"), where + "/properties")
    required: list[str] = _strings(node.get("required", []), where + "/required")
    missing: set[str] = set(required) - set(properties)
    if missing:
        message = f"target report schema: {where} requires undeclared properties {sorted(missing)}"
        raise SchemaShapeError(message)
    lines: list[str] = [
        f"class {name}(TypedDict):",
        f'    """Typed form of {where} in target-report.schema.json."""',
        "",
    ]
    key: str
    spec: object
    for key, spec in properties.items():
        field_where: str = where + "/properties/" + key
        rendered: str = _field_type(_node(spec, field_where), field_where, known)
        lines.append(f"    {key}: {rendered if key in required else f'NotRequired[{rendered}]'}")
    return lines, list(properties)


def _vocabularies(definitions: Mapping[str, object], known: dict[str, str]) -> list[str]:
    """Render every string vocabulary as a type alias, one constant per value and a frozenset.

    Records each alias in ``known`` so properties that reference it are typed by it.

    Returns:
        The source lines: aliases, then value constants, then collections.

    """
    vocab_lines: list[str] = []
    const_lines: list[str] = []
    set_lines: list[str] = []
    alias: str
    prefix: str
    collection: str
    for alias, prefix, collection in VOCABULARIES:
        node: dict[str, object] = _node(definitions.get(alias), REF_PREFIX + alias)
        values: list[str] = _strings(node.get("enum"), REF_PREFIX + alias + "/enum")
        known[alias] = alias
        vocab_lines.append(f"type {alias} = {_literal(values)}")
        names: list[str] = [f"{prefix}_{_upper_snake(value)}" for value in values]
        const_lines.extend(
            f"{const}: Final[{_literal([value])}] = {json.dumps(value)}"
            for const, value in zip(names, values, strict=True)
        )
        set_lines.append(f"{collection}: Final[frozenset[{alias}]] = frozenset({{{', '.join(names)}}})")
    return [*vocab_lines, "", *const_lines, "", *set_lines]


def _files(files: Mapping[str, object]) -> list[str]:
    """Render the file and folder name constants.

    Returns:
        The source lines.

    """
    file_lines: list[str] = [
        f"{constant}: Final = {json.dumps(_text(files.get(file_key), 'x-files/' + file_key))}"
        for constant, file_key in FILE_CONSTANTS
    ]
    work: str = _text(files.get("architectureWork"), "x-files/architectureWork")
    report: str = _text(files.get("targetReport"), "x-files/targetReport")
    file_lines.extend(
        (
            "TARGET_REPORT_PARTS: Final[tuple[str, str]] = (ARCHITECTURE_WORK_FOLDER, TARGET_REPORT_NAME)",
            f"TARGET_REPORT_FILE: Final = {json.dumps(work + '/' + report)}",
        ),
    )
    return file_lines


def _key_tuples(schema: Mapping[str, object], properties: Mapping[str, Sequence[str]]) -> list[str]:
    """Render the key tuples, each checked against the properties of its record.

    Returns:
        The source lines.

    Raises:
        SchemaShapeError: A tuple names a key its record does not declare.

    """
    tuple_lines: list[str] = []
    constant: str
    schema_key: str
    owner: str
    for constant, schema_key, owner in KEY_TUPLES:
        keys: list[str] = _strings(schema.get(schema_key), schema_key)
        stray: set[str] = set(keys) - set(properties[owner])
        if stray:
            message: str = f"target report schema: {schema_key} names {sorted(stray)}, not properties of {owner}"
            raise SchemaShapeError(message)
        members: str = "".join(f"\n    KEY_{_upper_snake(key)}," for key in keys)
        tuple_lines.append(f"{constant}: Final[tuple[str, ...]] = ({members}\n)")
    return tuple_lines


def render(schema: Mapping[str, object]) -> str:
    """Render the generated module for a target report schema.

    Returns:
        The complete Python source of target_contract.py.

    """
    definitions: dict[str, object] = _node(schema.get(DEFS), DEFS)
    known: dict[str, str] = {}
    vocabulary_lines: list[str] = _vocabularies(definitions, known)
    record_lines: list[str] = []
    properties: dict[str, list[str]] = {}
    record: str
    for record in RECORDS:
        lines: list[str]
        lines, properties[record] = _record(definitions, record, known)
        known[record] = record
        record_lines.extend(["", "", *lines])
    key_names: list[str] = sorted({key for keys in properties.values() for key in keys})
    key_lines: list[str] = [f"KEY_{_upper_snake(key)}: Final = {json.dumps(key)}" for key in key_names]

    parts: list[str] = [
        '"""GENERATED by generate_target_contract.py from schemas/target-report.schema.json. Do not edit.',
        "",
        "The architecture target and delta report contract: <epic work>/architecture/target.json (and its",
        "dry-run or seed check file target-check.json), delta-items.json and closure-roots.json, and the",
        "target names report. Producers and consumers import every type, key, value and file name from",
        "here and validate documents with the readers below. Regenerate with",
        "`python generate_target_contract.py`; `python check_target_contract.py` fails when this file is stale.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "from functools import lru_cache",
        "from pathlib import Path",
        "from typing import Final, Literal, NotRequired, TypedDict, TypeIs",
        "",
        "from jsonschema import Draft202012Validator",
        "from jsonschema.exceptions import best_match",
        "",
        "type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None",
        *vocabulary_lines,
        "",
        *key_lines,
        "",
        *_files(_node(schema.get("x-files"), "x-files")),
        "",
        *_key_tuples(schema, properties),
        "",
        'SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "schemas" / "target-report.schema.json"',
        *record_lines,
        "",
        "",
        TAIL,
    ]
    return "\n".join(parts)


TAIL: Final[str] = '''class TargetContractError(ValueError):
    """A document does not satisfy the target report schema."""


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
                message: str = "target report schema holds a non-string object key"
                raise TypeError(message)
            result[key] = _json_value(item)
        return result
    message = f"target report schema holds a non-JSON value of type {type(value).__name__}"
    raise TypeError(message)


@lru_cache(maxsize=1)
def load_schema() -> dict[str, JsonValue]:
    """Load the target report JSON Schema, the one definition of this contract.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The schema document.

    Raises:
        TypeError: The schema file is not a JSON object.

    """
    schema: JsonValue = _json_value(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    if not isinstance(schema, dict):
        message: str = f"{SCHEMA_PATH} is not a JSON object"
        raise TypeError(message)
    return schema


def schema_error(value: object, definition: str) -> str | None:
    """Describe the most relevant way a value fails one $defs entry of the schema.

    Args:
        value: The decoded document.
        definition: The $defs entry: TargetResult, DeltaResult or TargetNames.

    Returns:
        The failure as "<path>: <message>", or None when the value satisfies the entry.

    Raises:
        ValueError: The schema defines no such entry.

    """
    schema: dict[str, JsonValue] = load_schema()
    definitions: JsonValue = schema.get("$defs")
    if not isinstance(definitions, dict) or definition not in definitions:
        message: str = f"target report schema defines no {definition!r}"
        raise ValueError(message)
    wrapper: dict[str, JsonValue] = {**schema, "$ref": "#/$defs/" + definition}
    error = best_match(Draft202012Validator(wrapper).iter_errors(value))
    if error is None:
        return None
    location: str = "/".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{location}: {error.message}"


def is_target_result(value: object) -> TypeIs[TargetResult]:
    """Tell whether a value satisfies TargetResult.

    Returns:
        True when the schema accepts the value as a target report.

    """
    return schema_error(value, "TargetResult") is None


def is_delta_result(value: object) -> TypeIs[DeltaResult]:
    """Tell whether a value satisfies DeltaResult.

    Returns:
        True when the schema accepts the value as a delta report.

    """
    return schema_error(value, "DeltaResult") is None


def is_target_names(value: object) -> TypeIs[TargetNames]:
    """Tell whether a value satisfies TargetNames.

    Returns:
        True when the schema accepts the value as a target names report.

    """
    return schema_error(value, "TargetNames") is None


def validate_target_report(value: object, where: str = "target report") -> TargetResult:
    """Validate a target report.

    Returns:
        The value, typed.

    Raises:
        TargetContractError: The value does not satisfy TargetResult.

    """
    if is_target_result(value):
        return value
    message: str = f"{where} does not satisfy TargetResult: {schema_error(value, 'TargetResult')}"
    raise TargetContractError(message)


def validate_delta_report(value: object, where: str = "delta report") -> DeltaResult:
    """Validate a delta report.

    Returns:
        The value, typed.

    Raises:
        TargetContractError: The value does not satisfy DeltaResult.

    """
    if is_delta_result(value):
        return value
    message: str = f"{where} does not satisfy DeltaResult: {schema_error(value, 'DeltaResult')}"
    raise TargetContractError(message)


def validate_target_names(value: object, where: str = "target names report") -> TargetNames:
    """Validate a target names report.

    Returns:
        The value, typed.

    Raises:
        TargetContractError: The value does not satisfy TargetNames.

    """
    if is_target_names(value):
        return value
    message: str = f"{where} does not satisfy TargetNames: {schema_error(value, 'TargetNames')}"
    raise TargetContractError(message)


def _read(path: Path) -> object:
    """Read and decode one report file.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The decoded document.

    Raises:
        TypeError: The path is not a Path.

    """
    if not isinstance(path, Path):
        message: str = "a report path must be a Path"
        raise TypeError(message)
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    return decoded


def load_target_report(path: Path) -> TargetResult:
    """Read target.json or target-check.json and validate it against TargetResult.

    A file that does not satisfy TargetResult raises TargetContractError; a read or decode
    failure (OSError, json.JSONDecodeError) propagates unchanged.

    Returns:
        The validated target report.

    """
    return validate_target_report(_read(path), str(path))


def load_delta_report(path: Path) -> DeltaResult:
    """Read delta-items.json or closure-roots.json and validate it against DeltaResult.

    A file that does not satisfy DeltaResult raises TargetContractError; a read or decode
    failure (OSError, json.JSONDecodeError) propagates unchanged.

    Returns:
        The validated delta report.

    """
    return validate_delta_report(_read(path), str(path))


def target_report_path(epic_work: Path) -> Path:
    """Name the target report of an Epic's work directory.

    Returns:
        <epic work>/architecture/target.json.

    Raises:
        TypeError: The work directory is not a Path.

    """
    if not isinstance(epic_work, Path):
        message: str = "target_report_path requires a Path"
        raise TypeError(message)
    return epic_work.joinpath(*TARGET_REPORT_PARTS)
'''


def load_schema() -> dict[str, object]:
    """Read the schema file.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The schema document.

    """
    decoded: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _node(decoded, "#")


def main() -> int:
    """Write the generated module, or with --check report whether it is current.

    Returns:
        0 when written or current, 1 when --check finds it stale or missing.

    Raises:
        TypeError: The parsed --check flag is not a boolean.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when target_contract.py is stale")
    args: argparse.Namespace = parser.parse_args()
    check: object = args.check
    if not isinstance(check, bool):
        message: str = "--check must be a flag"
        raise TypeError(message)
    expected: str = render(load_schema())
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
