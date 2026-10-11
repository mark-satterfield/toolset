"""Generate checkpoint_contract.py from schemas/checkpoint.schema.json, or check that it is current.

The schema is the one definition of the artifact checkpoint contract. This script derives the
Python types and wire constants from it. With --check it writes nothing and exits 1 when the
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
SCHEMA_PATH: Final[Path] = SCRIPTS_DIR.parent / "schemas" / "checkpoint.schema.json"
OUTPUT_PATH: Final[Path] = SCRIPTS_DIR / "checkpoint_contract.py"

ROOT_POINTER: Final[str] = "#"
PROGRESS_POINTER: Final[str] = "#/$defs/Progress"
REPORT_POINTER: Final[str] = "#/$defs/StatusReport"
RESULT_POINTER: Final[str] = "#/$defs/CommandResult"

# (TypedDict name, schema pointer) for every object the module types.
RECORDS: Final[tuple[tuple[str, str], ...]] = (
    ("CheckpointRecord", ROOT_POINTER),
    ("ProgressInput", PROGRESS_POINTER),
    ("StatusReport", REPORT_POINTER),
    ("CommandResult", RESULT_POINTER),
)
# (alias name, constant prefix, schema pointer of the enum) for every string vocabulary.
VOCABULARIES: Final[tuple[tuple[str, str, str], ...]] = (
    ("CheckpointStatus", "STATUS", ROOT_POINTER + "/properties/status"),
    ("StatusReportStatus", "REPORT", REPORT_POINTER + "/properties/status"),
    ("CommandResultStatus", "RESULT", RESULT_POINTER + "/properties/status"),
)

type SchemaNode = Mapping[str, object]


def _node(value: object, where: str) -> dict[str, object]:
    """Narrow a decoded JSON value to an object.

    Returns:
        The value as a string-keyed dictionary.

    Raises:
        TypeError: The value is not a JSON object.

    """
    if not isinstance(value, dict):
        message: str = f"checkpoint schema: {where} is not an object"
        raise TypeError(message)
    result: dict[str, object] = {}
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            message = f"checkpoint schema: {where} has a non-string key"
            raise TypeError(message)
        result[key] = item
    return result


def _strings(value: object, where: str) -> list[str]:
    """Narrow a decoded JSON value to a list of nonempty strings.

    Returns:
        The strings in their schema order.

    Raises:
        TypeError: The value is not a list.
        ValueError: The list holds a value that is not a nonempty string.

    """
    if not isinstance(value, list):
        message: str = f"checkpoint schema: {where} is not a list"
        raise TypeError(message)
    result: list[str] = []
    item: object
    for item in value:
        if not isinstance(item, str) or not item:
            message = f"checkpoint schema: {where} holds a value that is not a nonempty string"
            raise ValueError(message)
        result.append(item)
    return result


def _text(value: object, where: str) -> str:
    """Narrow a decoded JSON value to a nonempty string.

    Returns:
        The string.

    Raises:
        ValueError: The value is not a nonempty string.

    """
    if not isinstance(value, str) or not value:
        message: str = f"checkpoint schema: {where} is not a nonempty string"
        raise ValueError(message)
    return value


def _resolve(root: SchemaNode, pointer: str) -> dict[str, object]:
    """Resolve a local JSON pointer ('#' or '#/a/b') against the schema.

    Returns:
        The schema object the pointer names.

    Raises:
        ValueError: The pointer is not local or names no object.

    """
    if pointer != ROOT_POINTER and not pointer.startswith(ROOT_POINTER + "/"):
        message: str = f"checkpoint schema: only local pointers are supported, not {pointer}"
        raise ValueError(message)
    current: dict[str, object] = _node(dict(root), ROOT_POINTER)
    part: str
    for part in pointer.split("/")[1:]:
        if part not in current:
            message = f"checkpoint schema: {pointer} does not resolve"
            raise ValueError(message)
        current = _node(current[part], pointer)
    return current


def _follow(root: SchemaNode, node: SchemaNode, where: str) -> dict[str, object]:
    """Follow $ref links until a node with no $ref remains.

    Returns:
        The referenced schema object.

    Raises:
        ValueError: The $ref links form a cycle.

    """
    current: dict[str, object] = dict(node)
    seen: set[str] = set()
    while "$ref" in current:
        pointer: str = _text(current["$ref"], where + "/$ref")
        if pointer in seen:
            message: str = f"checkpoint schema: {where} has a $ref cycle"
            raise ValueError(message)
        seen.add(pointer)
        current = _resolve(root, pointer)
    return current


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
        ValueError: The value cannot form a Python identifier.

    """
    name: str = prefix + "_" + value.upper().replace("-", "_")
    if not name.isidentifier():
        message: str = f"checkpoint schema: wire value {value!r} cannot name a constant"
        raise ValueError(message)
    return name


def _field_type(root: SchemaNode, node: SchemaNode, where: str, aliases: Mapping[str, str]) -> str:
    """Render the Python type of one property.

    Returns:
        Python source for the property's type.

    Raises:
        ValueError: The property uses a construct the generator does not type.

    """
    target: dict[str, object] = dict(node)
    pointer: str = where
    while "$ref" in target:
        pointer = _text(target["$ref"], where + "/$ref")
        target = _resolve(root, pointer)
    if pointer in aliases:
        return aliases[pointer]
    if "enum" in target:
        return _literal(_strings(target["enum"], where + "/enum"))
    kind: str = _text(target.get("type"), where + "/type")
    if kind == "string":
        return "str"
    if kind == "array":
        items: dict[str, object] = _follow(root, _node(target.get("items"), where + "/items"), where + "/items")
        if _text(items.get("type"), where + "/items/type") != "string":
            message: str = f"checkpoint schema: {where} is an array of a type the generator does not type"
            raise ValueError(message)
        return "list[str]"
    message = f"checkpoint schema: {where} has type {kind!r}, which the generator does not type"
    raise ValueError(message)


def _record(
    root: SchemaNode,
    name: str,
    pointer: str,
    aliases: Mapping[str, str],
) -> list[str]:
    """Render one closed schema object as a TypedDict.

    Returns:
        The class source lines.

    Raises:
        ValueError: The object is open or requires a property it does not declare.

    """
    node: dict[str, object] = _resolve(root, pointer)
    if node.get("additionalProperties") is not False:
        message: str = f"checkpoint schema: {pointer} must be a closed object"
        raise ValueError(message)
    properties: dict[str, object] = _node(node.get("properties"), pointer + "/properties")
    required: list[str] = _strings(node.get("required", []), pointer + "/required")
    missing: set[str] = set(required) - set(properties)
    if missing:
        message = f"checkpoint schema: {pointer} requires undeclared properties {sorted(missing)}"
        raise ValueError(message)
    description: str = f"{pointer} in checkpoint.schema.json."
    lines: list[str] = [f"class {name}(TypedDict):", f'    """Typed form of {description}"""', ""]
    key: str
    spec: object
    for key, spec in properties.items():
        where: str = pointer + "/properties/" + key
        rendered: str = _field_type(root, _node(spec, where), where, aliases)
        lines.append(f"    {key}: {rendered if key in required else f'NotRequired[{rendered}]'}")
    return lines


def render(schema: SchemaNode) -> str:
    """Render the generated module for a checkpoint schema.

    Returns:
        The complete Python source of checkpoint_contract.py.

    Raises:
        TypeError: The schema is not a JSON object.
        ValueError: The schema is missing a part of the contract or uses an untyped construct.

    """
    if not isinstance(schema, dict):
        message: str = "checkpoint schema must be a JSON object"
        raise TypeError(message)
    sidecar: str = _text(schema.get("x-sidecarSuffix"), "x-sidecarSuffix")
    progress_suffix: str = _text(schema.get("x-progressSuffix"), "x-progressSuffix")
    binding: list[str] = _strings(schema.get("x-bindingKeys"), "x-bindingKeys")
    authored: list[str] = _strings(schema.get("x-authoredStatuses"), "x-authoredStatuses")
    operations: list[str] = _strings(schema.get("x-operations"), "x-operations")
    root_required: list[str] = _strings(schema.get("required"), "required")
    if not set(binding) <= set(root_required):
        message = "checkpoint schema: every x-bindingKeys entry must be a required checkpoint property"
        raise ValueError(message)
    progress_keys: list[str] = list(_node(_resolve(schema, PROGRESS_POINTER).get("properties"), PROGRESS_POINTER))

    aliases: dict[str, str] = {}
    vocab_lines: list[str] = []
    const_lines: list[str] = []
    statuses: list[str] = []
    alias: str
    prefix: str
    pointer: str
    for alias, prefix, pointer in VOCABULARIES:
        values: list[str] = _strings(_resolve(schema, pointer).get("enum"), pointer + "/enum")
        aliases[pointer] = alias
        vocab_lines.append(f"type {alias} = {_literal(values)}")
        const_lines.extend(
            f"{_constant_name(prefix, value)}: Final[{_literal([value])}] = {json.dumps(value)}" for value in values
        )
        if prefix == "STATUS":
            statuses = values
    if not set(authored) <= set(statuses):
        message = "checkpoint schema: x-authoredStatuses must be checkpoint statuses"
        raise ValueError(message)
    vocab_lines.extend((f"type AuthoredStatus = {_literal(authored)}", f"type Operation = {_literal(operations)}"))
    const_lines.extend(
        f"{_constant_name('OPERATION', operation)}: Final[{_literal([operation])}] = {json.dumps(operation)}"
        for operation in operations
    )

    def names(prefix_name: str, items: Sequence[str]) -> str:
        return "".join(f"\n    {_constant_name(prefix_name, item)}," for item in items) + "\n"

    def keyset(items: Sequence[str]) -> str:
        return "frozenset({" + ", ".join(json.dumps(item) for item in sorted(items)) + "})"

    record_lines: list[str] = []
    record: str
    for record, pointer in RECORDS:
        record_lines.extend(["", "", *_record(schema, record, pointer, aliases)])

    parts: list[str] = [
        '"""GENERATED by generate_checkpoint_contract.py from schemas/checkpoint.schema.json. Do not edit.',
        "",
        "The artifact checkpoint contract: the sidecar <candidate>.checkpoint, the agent-authored progress",
        "file it is built from, the status report and the command results of artifactcontract.py.",
        "Regenerate with `python generate_checkpoint_contract.py`; `--check` fails when this file is stale.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "from pathlib import Path",
        "from typing import Final, Literal, NotRequired, TypedDict",
        "",
        "type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None",
        *vocab_lines,
        "",
        *const_lines,
        "",
        f"CHECKPOINT_STATUSES: Final[tuple[CheckpointStatus, ...]] = ({names('STATUS', statuses)})",
        f"AUTHORED_STATUSES: Final[tuple[AuthoredStatus, ...]] = ({names('STATUS', authored)})",
        f"OPERATIONS: Final[tuple[Operation, ...]] = ({names('OPERATION', operations)})",
        f"BINDING_KEYS: Final[frozenset[str]] = {keyset(binding)}",
        f"PROGRESS_KEYS: Final[frozenset[str]] = {keyset(progress_keys)}",
        f"CHECKPOINT_SUFFIX: Final[str] = {json.dumps(sidecar)}",
        f"PROGRESS_SUFFIX: Final[str] = {json.dumps(progress_suffix)}",
        (
            "CHECKPOINT_SCHEMA_PATH: Final[Path] = "
            'Path(__file__).resolve().parent.parent / "schemas" / "checkpoint.schema.json"'
        ),
        *record_lines,
        "",
        "",
        TAIL,
    ]
    return "\n".join(parts)


TAIL: Final[str] = '''def _json_value(value: object) -> JsonValue:
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
                message: str = "checkpoint schema holds a non-string object key"
                raise TypeError(message)
            result[key] = _json_value(item)
        return result
    message = f"checkpoint schema holds a non-JSON value of type {type(value).__name__}"
    raise TypeError(message)


def load_checkpoint_schema() -> dict[str, JsonValue]:
    """Load the checkpoint JSON Schema, the one definition of this contract.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The schema document.

    Raises:
        TypeError: The schema file is not a JSON object.

    """
    decoded: object = json.loads(CHECKPOINT_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema: JsonValue = _json_value(decoded)
    if not isinstance(schema, dict):
        message: str = f"{CHECKPOINT_SCHEMA_PATH} is not a JSON object"
        raise TypeError(message)
    return schema


def checkpoint_path(candidate: Path) -> Path:
    """Name the checkpoint sidecar of a candidate artifact.

    Returns:
        The candidate path with CHECKPOINT_SUFFIX appended.

    Raises:
        TypeError: The candidate is not a path.

    """
    if not isinstance(candidate, Path):
        message: str = "checkpoint_path requires a Path"
        raise TypeError(message)
    return Path(str(candidate) + CHECKPOINT_SUFFIX)


def progress_path(candidate: Path) -> Path:
    """Name the agent-authored progress file of a candidate artifact.

    Returns:
        The candidate path with PROGRESS_SUFFIX appended.

    Raises:
        TypeError: The candidate is not a path.

    """
    if not isinstance(candidate, Path):
        message: str = "progress_path requires a Path"
        raise TypeError(message)
    return Path(str(candidate) + PROGRESS_SUFFIX)
'''


def main() -> int:
    """Write the generated module, or with --check report whether it is current.

    Returns:
        0 when written or current, 1 when --check finds it stale or missing.

    Raises:
        TypeError: The parsed --check flag is not a boolean.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when checkpoint_contract.py is stale")
    args: argparse.Namespace = parser.parse_args()
    check: object = args.check
    if not isinstance(check, bool):
        message: str = "--check must be a flag"
        raise TypeError(message)
    decoded: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    expected: str = render(_node(decoded, ROOT_POINTER))
    if check:
        current: str | None = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.is_file() else None
        if current != expected:
            sys.stderr.write(
                f"{OUTPUT_PATH} is stale against {SCHEMA_PATH}; run {Path(__file__).name} to regenerate it\n",
            )
            return 1
        return 0
    OUTPUT_PATH.write_text(expected, encoding="utf-8")
    sys.stdout.write(f"wrote {OUTPUT_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
