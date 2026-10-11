"""Generate the recon detailing contract's code views from ``schemas/recon.schema.json``.

The schema is the one definition of ``recon-<slug>.json`` (the per-repository detailing) and of the
detailing session's reply. This script writes the two generated views of it:

- ``scripts/recon_contract.py``: the Literal aliases, value constants, key constants, TypedDicts, field
  tuples, ``recon_file_name`` and the schema validator ``parse_detailing`` the Python code imports;
- ``<plugin>/scripts/shared-blocks/recon-contract.js``: the shared block ``scripts/shared-blocks.mjs``
  inlines into workflows, carrying the schema itself and the values and helpers derived from it.

``--write`` rewrites both; ``--check`` exits 1 when either differs from what the schema generates.
Only naming lives here (which constant prefix each ``$defs`` entry takes); every key and allowed
value is read from the schema.
"""

from __future__ import annotations

import argparse
import json
import keyword
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeIs

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None
type JsonObject = dict[str, Json]

SKILL_DIR: Final[Path] = Path(__file__).resolve().parents[1]
PLUGIN_DIR: Final[Path] = SKILL_DIR.parents[1]
SCHEMA_FILE: Final[Path] = SKILL_DIR / "schemas" / "recon.schema.json"
PY_FILE: Final[Path] = SKILL_DIR / "scripts" / "recon_contract.py"
JS_FILE: Final[Path] = PLUGIN_DIR / "scripts" / "shared-blocks" / "recon-contract.js"
DEFS_PREFIX: Final[str] = "#/$defs/"

#: Enumerations: $defs name -> (member constant prefix or None, collection constant name).
ENUM_NAMING: Final[dict[str, tuple[str | None, str]]] = {
    "ReconStatus": ("STATUS", "STATUSES"),
    "WorkStatus": (None, "WORK_STATUSES"),
    "IdleStatus": (None, "IDLE_STATUSES"),
    "Surface": ("SURFACE", "SURFACES"),
    "DesignSource": ("DESIGN_SOURCE", "DESIGN_SOURCES"),
    "ArtifactKind": ("ARTIFACT_KIND", "ARTIFACT_KINDS"),
}
#: The full status enumeration and the two enumerations that partition it.
STATUS_DEF: Final[str] = "ReconStatus"
PARTITION_DEFS: Final[tuple[str, str]] = ("WorkStatus", "IdleStatus")
#: Single-value constants: $defs name -> Python constant name.
CONST_NAMING: Final[dict[str, str]] = {"FromAbsent": "FROM_ABSENT", "ToRemoved": "TO_REMOVED"}
#: Objects: $defs name -> prefix of its <PREFIX>_FIELDS / <PREFIX>_REQUIRED tuples.
OBJECT_NAMING: Final[dict[str, str]] = {
    "ReconDetailing": "DETAILING",
    "ReconItem": "ITEM",
    "UiAuthority": "UI_AUTHORITY",
    "UiItem": "UI_ITEM",
    "UiArtifact": "UI_ARTIFACT",
    "DependencyChanges": "DEPENDENCY_CHANGES",
    "ChangeFinding": "CHANGE_FINDING",
    "ReconReply": "REPLY",
}
ROOT_DEF: Final[str] = "ReconDetailing"
REPLY_DEF: Final[str] = "ReconReply"
#: Every keyword the generated validator interprets or ignores as an annotation.
SUPPORTED_KEYWORDS: Final[frozenset[str]] = frozenset({
    "$schema",
    "$id",
    "$ref",
    "$defs",
    "title",
    "description",
    "default",
    "x-fileTemplate",
    "x-producerRequired",
    "type",
    "enum",
    "const",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "minLength",
    "pattern",
    "allOf",
    "anyOf",
    "if",
    "then",
    "else",
})
#: Keywords whose value is a map of names to schemas, not a schema.
SCHEMA_MAPS: Final[frozenset[str]] = frozenset({"$defs", "properties"})
#: Keywords whose value is a list of schemas.
SCHEMA_LISTS: Final[frozenset[str]] = frozenset({"allOf", "anyOf"})
#: Keywords whose value is one schema.
SCHEMA_SINGLES: Final[frozenset[str]] = frozenset({"items", "if", "then", "else"})
SCALAR_TYPES: Final[dict[str, str]] = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "null": "None",
}


class SchemaShapeError(ValueError):
    """The recon schema uses a shape this generator does not translate."""


@dataclass(frozen=True)
class Enumeration:
    """One string enumeration of the schema."""

    name: str
    prefix: str | None
    collection: str
    values: tuple[str, ...]
    default: str | None


@dataclass(frozen=True)
class Field:
    """One property of an object definition."""

    key: str
    annotation: str
    required: bool


@dataclass(frozen=True)
class ObjectDef:
    """One object definition of the schema."""

    name: str
    prefix: str
    description: str
    fields: tuple[Field, ...]
    refs: frozenset[str]


@dataclass(frozen=True)
class Model:
    """The translated schema."""

    schema: JsonObject
    file_template: str
    producer_required: tuple[str, ...]
    enums: tuple[Enumeration, ...]
    consts: tuple[tuple[str, str], ...]
    objects: tuple[ObjectDef, ...]


def _is_object(value: Json) -> TypeIs[JsonObject]:
    return isinstance(value, dict)


def _obj(value: Json, where: str) -> JsonObject:
    if not _is_object(value):
        message: str = f"{where}: expected a JSON object"
        raise SchemaShapeError(message)
    return value


def _text(value: Json, where: str) -> str:
    if not isinstance(value, str):
        message: str = f"{where}: expected a string"
        raise SchemaShapeError(message)
    return value


def _texts(value: Json, where: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        message: str = f"{where}: expected an array"
        raise SchemaShapeError(message)
    return tuple(_text(item, f"{where}[{index}]") for index, item in enumerate(value))


def _check_keywords(node: Json, where: str) -> None:
    """Fail on any keyword the generated validator would not interpret.

    Raises:
        SchemaShapeError: A keyword outside ``SUPPORTED_KEYWORDS`` is used.

    """
    if not _is_object(node):
        return
    unknown: list[str] = sorted(key for key in node if key not in SUPPORTED_KEYWORDS)
    if unknown:
        message: str = f"{where}: unsupported keywords {unknown}"
        raise SchemaShapeError(message)
    for key, value in node.items():
        if key in SCHEMA_MAPS:
            for name, child in _obj(value, f"{where}.{key}").items():
                _check_keywords(child, f"{where}.{key}.{name}")
        elif key in SCHEMA_LISTS and isinstance(value, list):
            for index, child in enumerate(value):
                _check_keywords(child, f"{where}.{key}[{index}]")
        elif key in SCHEMA_SINGLES:
            _check_keywords(value, f"{where}.{key}")


def _ref_name(node: JsonObject, defs: JsonObject, where: str) -> str | None:
    ref: Json = node.get("$ref")
    if ref is None:
        return None
    text: str = _text(ref, f"{where}.$ref")
    name: str = text.removeprefix(DEFS_PREFIX)
    if not text.startswith(DEFS_PREFIX) or name not in defs:
        message: str = f"{where}: $ref {text} names no $defs entry"
        raise SchemaShapeError(message)
    return name


def _annotation(node: JsonObject, defs: JsonObject, where: str, refs: set[str]) -> str:
    name: str | None = _ref_name(node, defs, where)
    if name is not None:
        refs.add(name)
        return name
    branches: Json = node.get("anyOf")
    if isinstance(branches, list):
        parts: list[str] = [
            _annotation(_obj(branch, f"{where}.anyOf[{index}]"), defs, where, refs)
            for index, branch in enumerate(branches)
        ]
        return " | ".join(sorted(parts, key=lambda part: part == "None"))
    kind: Json = node.get("type")
    kinds: tuple[str, ...] = (
        _texts(kind, f"{where}.type") if isinstance(kind, list) else (_text(kind, f"{where}.type"),)
    )
    rendered: list[str] = []
    for one in kinds:
        if one == "array":
            rendered.append(f"list[{_annotation(_obj(node.get('items'), f'{where}.items'), defs, where, refs)}]")
        elif one in SCALAR_TYPES:
            rendered.append(SCALAR_TYPES[one])
        else:
            message: str = f"{where}: type {one} has no Python annotation here"
            raise SchemaShapeError(message)
    return " | ".join(sorted(rendered, key=lambda part: part == "None"))


def _enumeration(name: str, node: JsonObject) -> Enumeration:
    values: tuple[str, ...] = _texts(node.get("enum"), f"$defs.{name}.enum")
    if not values or len(set(values)) != len(values):
        message: str = f"$defs.{name}.enum: expected unique values"
        raise SchemaShapeError(message)
    default: Json = node.get("default")
    if default is not None and default not in values:
        message = f"$defs.{name}.default: {default!r} is not an allowed value"
        raise SchemaShapeError(message)
    prefix, collection = ENUM_NAMING[name]
    return Enumeration(name, prefix, collection, values, default if isinstance(default, str) else None)


def _object(name: str, node: JsonObject, defs: JsonObject) -> ObjectDef:
    where: str = f"$defs.{name}"
    if node.get("type") != "object" or node.get("additionalProperties") is not False:
        message: str = f"{where}: expected an object with additionalProperties false"
        raise SchemaShapeError(message)
    properties: JsonObject = _obj(node.get("properties"), f"{where}.properties")
    required: tuple[str, ...] = _texts(node.get("required", []), f"{where}.required")
    missing: list[str] = [key for key in required if key not in properties]
    if missing:
        message = f"{where}: required names unknown properties {missing}"
        raise SchemaShapeError(message)
    refs: set[str] = set()
    fields: tuple[Field, ...] = tuple(
        Field(key, _annotation(_obj(raw, f"{where}.{key}"), defs, f"{where}.{key}", refs), key in required)
        for key, raw in properties.items()
    )
    description: str = _text(node.get("description"), f"{where}.description")
    return ObjectDef(name, OBJECT_NAMING[name], description, fields, frozenset(refs & set(OBJECT_NAMING)))


def _ordered(objects: dict[str, ObjectDef]) -> tuple[ObjectDef, ...]:
    """Order object definitions so each follows every object it references.

    Returns:
        The definitions in dependency order; a reference cycle raises ``SchemaShapeError``.

    """
    done: list[str] = []

    def visit(name: str, path: tuple[str, ...]) -> None:
        if name in done:
            return
        if name in path:
            message: str = f"$defs: recursive object reference {[*path, name]}"
            raise SchemaShapeError(message)
        for ref in sorted(objects[name].refs):
            visit(ref, (*path, name))
        done.append(name)

    for name in objects:
        visit(name, ())
    return tuple(objects[name] for name in done)


def build_model(schema: JsonObject) -> Model:
    """Translate the recon schema.

    Args:
        schema: The decoded schema.

    Returns:
        The translated model.

    Raises:
        SchemaShapeError: The schema uses a shape the generator does not translate.

    """
    _check_keywords(schema, "$")
    defs: JsonObject = _obj(schema.get("$defs"), "$defs")
    named: set[str] = set(ENUM_NAMING) | set(CONST_NAMING) | set(OBJECT_NAMING)
    if set(defs) != named:
        message: str = f"$defs must name exactly {sorted(named)}; it names {sorted(defs)}"
        raise SchemaShapeError(message)
    if _ref_name(schema, defs, "$") != ROOT_DEF:
        message = f"the root must $ref {DEFS_PREFIX}{ROOT_DEF}"
        raise SchemaShapeError(message)
    enums: tuple[Enumeration, ...] = tuple(_enumeration(name, _obj(defs[name], name)) for name in ENUM_NAMING)
    by_name: dict[str, Enumeration] = {enum.name: enum for enum in enums}
    work, idle = (set(by_name[name].values) for name in PARTITION_DEFS)
    if work & idle or work | idle != set(by_name[STATUS_DEF].values):
        message = f"{PARTITION_DEFS} must partition {STATUS_DEF}"
        raise SchemaShapeError(message)
    consts: tuple[tuple[str, str], ...] = tuple(
        (constant, _text(_obj(defs[name], name).get("const"), f"$defs.{name}.const"))
        for name, constant in CONST_NAMING.items()
    )
    objects: dict[str, ObjectDef] = {name: _object(name, _obj(defs[name], name), defs) for name in OBJECT_NAMING}
    return Model(
        schema=schema,
        file_template=_text(schema.get("x-fileTemplate"), "x-fileTemplate"),
        producer_required=_texts(schema.get("x-producerRequired"), "x-producerRequired"),
        enums=enums,
        consts=consts,
        objects=_ordered(objects),
    )


def _member(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def _snake(key: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).upper()


def _tuple_lines(name: str, annotation: str, items: tuple[str, ...]) -> list[str]:
    if len(items) <= 1:
        return [f"{name}: Final[tuple[{annotation}, ...]] = ({''.join(f'{item},' for item in items)})"]
    return [f"{name}: Final[tuple[{annotation}, ...]] = (", *(f"    {item}," for item in items), ")"]


PY_HEADER: Final[str] = '''"""The per-repository detailing contract: recon-<slug>.json, its values, types and validator.

GENERATED by scripts/gen_recon_contract.py from schemas/recon.schema.json. Never edit this file:
change the schema and run ``python3 scripts/gen_recon_contract.py --write``. The schema is the one
definition; every value, key and type below is generated from it, and ``parse_detailing`` validates
against the schema file itself.
"""

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, NotRequired, TypedDict, TypeIs

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "schemas" / "recon.schema.json"
DEFS_PREFIX: Final = "#/$defs/"
'''

PY_RUNTIME: Final[str] = r'''


#: At most this many violations are named in one error message.
MAX_REPORTED: Final = 20

_TYPES: Final[dict[str, Callable[[object], bool]]] = {
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, int | float) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
    "array": lambda value: isinstance(value, list),
    "object": lambda value: isinstance(value, dict),
}


class ReconContractError(ValueError):
    """A value, the schema or a file does not conform to the recon contract."""


def _node(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        message: str = f"{where}: expected a JSON object"
        raise ReconContractError(message)
    out: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            message = f"{where}: expected string keys"
            raise ReconContractError(message)
        out[key] = item
    return out


def load_schema() -> dict[str, object]:
    """Read the recon schema.

    Returns:
        The decoded schema.

    Raises:
        ReconContractError: The schema file cannot be read or is not a JSON object.

    """
    try:
        raw: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        message: str = f"{SCHEMA_PATH}: cannot read the recon schema: {exc}"
        raise ReconContractError(message) from exc
    return _node(raw, str(SCHEMA_PATH))


@cache
def _defs() -> Mapping[str, dict[str, object]]:
    schema: dict[str, object] = load_schema()
    return {name: _node(node, f"$defs.{name}") for name, node in _node(schema.get("$defs"), "$defs").items()}


def _target(ref: str) -> dict[str, object]:
    node: dict[str, object] | None = _defs().get(ref.removeprefix(DEFS_PREFIX))
    if not ref.startswith(DEFS_PREFIX) or node is None:
        message: str = f"{SCHEMA_PATH}: $ref {ref} names no $defs entry"
        raise ReconContractError(message)
    return node


def _matches_type(value: object, kind: object) -> bool:
    names: list[object] = list(kind) if isinstance(kind, list) else [kind]
    for name in names:
        check: Callable[[object], bool] | None = _TYPES.get(name) if isinstance(name, str) else None
        if check is None:
            message: str = f"{SCHEMA_PATH}: unsupported type {name!r}"
            raise ReconContractError(message)
        if check(value):
            return True
    return False


def _check_string(value: str, node: Mapping[str, object], where: str, errors: list[str]) -> None:
    min_length: object = node.get("minLength")
    if isinstance(min_length, int) and len(value) < min_length:
        errors.append(f"{where}: shorter than {min_length} character(s)")
    pattern: object = node.get("pattern")
    if isinstance(pattern, str) and re.search(pattern, value) is None:
        errors.append(f"{where}: {value!r} does not match {pattern}")


def _check_array(value: list[object], node: Mapping[str, object], where: str, errors: list[str]) -> None:
    min_items: object = node.get("minItems")
    if isinstance(min_items, int) and len(value) < min_items:
        errors.append(f"{where}: fewer than {min_items} entr(ies)")
    max_items: object = node.get("maxItems")
    if isinstance(max_items, int) and len(value) > max_items:
        errors.append(f"{where}: more than {max_items} entr(ies)")
    items: object = node.get("items")
    if items is not None:
        schema: dict[str, object] = _node(items, f"{where}.items")
        for index, item in enumerate(value):
            _check(item, schema, f"{where}[{index}]", errors)


def _check_object(value: Mapping[str, object], node: Mapping[str, object], where: str, errors: list[str]) -> None:
    required: object = node.get("required")
    if isinstance(required, list):
        errors.extend(f"{where}.{key}: required and missing" for key in required if key not in value)
    properties: dict[str, object] = _node(node.get("properties", {}), f"{where}.properties")
    if node.get("additionalProperties") is False:
        errors.extend(f"{where}.{key}: not a field of this object" for key in value if key not in properties)
    for key, schema in properties.items():
        if key in value:
            _check(value[key], _node(schema, f"{where}.{key}"), f"{where}.{key}", errors)


def _violations_of(value: object, node: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    _check(value, node, "$", errors)
    return errors


def _check_combinators(value: object, node: Mapping[str, object], where: str, errors: list[str]) -> None:
    every: object = node.get("allOf")
    if isinstance(every, list):
        for index, branch in enumerate(every):
            _check(value, _node(branch, f"{where}.allOf[{index}]"), where, errors)
    some: object = node.get("anyOf")
    if isinstance(some, list) and all(
        _violations_of(value, _node(branch, f"{where}.anyOf[{index}]")) for index, branch in enumerate(some)
    ):
        errors.append(f"{where}: matches none of the allowed shapes")
    condition: object = node.get("if")
    if condition is not None:
        branch_key: str = "else" if _violations_of(value, _node(condition, f"{where}.if")) else "then"
        chosen: object = node.get(branch_key)
        if chosen is not None:
            _check(value, _node(chosen, f"{where}.{branch_key}"), where, errors)


def _check(value: object, node: Mapping[str, object], where: str, errors: list[str]) -> None:
    ref: object = node.get("$ref")
    if isinstance(ref, str):
        _check(value, _target(ref), where, errors)
    kind: object = node.get("type")
    if kind is not None and not _matches_type(value, kind):
        errors.append(f"{where}: expected {kind}, got {json.dumps(value)[:80]}")
        return
    if "const" in node and value != node["const"]:
        errors.append(f"{where}: must be {json.dumps(node['const'])}")
    allowed: object = node.get("enum")
    if isinstance(allowed, list) and value not in allowed:
        errors.append(f"{where}: {json.dumps(value)[:80]} is not one of {allowed}")
    if isinstance(value, str):
        _check_string(value, node, where, errors)
    elif isinstance(value, list):
        _check_array(value, node, where, errors)
    elif isinstance(value, dict):
        _check_object(_node(value, where), node, where, errors)
    _check_combinators(value, node, where, errors)


def violations(value: object, definition: str) -> list[str]:
    """Validate ``value`` against one ``$defs`` entry of the schema.

    Args:
        value: The decoded JSON value.
        definition: The ``$defs`` name, for example ``ReconDetailing``.

    Returns:
        Every violation, each naming the field path; empty when the value conforms. A definition
        the schema does not name, or an unreadable schema, raises ``ReconContractError``.

    """
    return _violations_of(value, _target(DEFS_PREFIX + definition))


def _is_detailing(value: object, errors: list[str]) -> TypeIs[ReconDetailing]:
    errors.extend(violations(value, "ReconDetailing"))
    return not errors


def _is_reply(value: object, errors: list[str]) -> TypeIs[ReconReply]:
    errors.extend(violations(value, "ReconReply"))
    return not errors


def _refusal(source: str, what: str, errors: list[str]) -> str:
    shown: str = "; ".join(errors[:MAX_REPORTED])
    more: str = f" (and {len(errors) - MAX_REPORTED} more)" if len(errors) > MAX_REPORTED else ""
    return f"{source}: not {what}: {shown}{more}"


def parse_detailing(value: object, *, source: str = "recon detailing") -> ReconDetailing:
    """Validate a decoded detailing against the schema.

    Args:
        value: The decoded ``recon-<slug>.json`` content.
        source: What the value came from (usually the file path), named in the error.

    Returns:
        The value, typed as the detailing.

    Raises:
        ReconContractError: The value does not conform; the message names the source and each field.

    """
    errors: list[str] = []
    if not _is_detailing(value, errors):
        raise ReconContractError(_refusal(source, "a recon detailing", errors))
    return value


def parse_reply(value: object, *, source: str = "recon session reply") -> ReconReply:
    """Validate a detailing session's reply against the schema.

    Args:
        value: The decoded reply.
        source: What the value came from, named in the error.

    Returns:
        The value, typed as the reply.

    Raises:
        ReconContractError: The value does not conform; the message names the source and each field.

    """
    errors: list[str] = []
    if not _is_reply(value, errors):
        raise ReconContractError(_refusal(source, "a recon session reply", errors))
    return value


def read_detailing(path: Path) -> ReconDetailing:
    """Read and validate a saved detailing.

    Args:
        path: The ``recon-<slug>.json`` file.

    Returns:
        The validated detailing.

    Raises:
        ReconContractError: The file cannot be read, is not JSON, or does not conform.

    """
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        message: str = f"{path}: cannot read the saved detailing: {exc}"
        raise ReconContractError(message) from exc
    return parse_detailing(raw, source=str(path))


def recon_file_name(slug: str) -> str:
    """Name the detailing file of one repository.

    Args:
        slug: The repository's artifact slug.

    Returns:
        The file name, ``RECON_FILE_TEMPLATE`` with the slug filled in.

    Raises:
        ValueError: The slug is empty, padded or holds a path separator.

    """
    if not isinstance(slug, str) or not slug or slug != slug.strip() or "/" in slug:
        message: str = f"recon slug must be a non-empty name with no path separator, got {slug!r}"
        raise ValueError(message)
    return RECON_FILE_TEMPLATE.format(slug=slug)
'''


def _render_enums(model: Model) -> list[str]:
    lines: list[str] = []
    for enum in model.enums:
        literal: str = ", ".join(json.dumps(value) for value in enum.values)
        lines.extend(["", f"type {enum.name} = Literal[{literal}]"])
        if enum.prefix is not None:
            lines.extend(
                f"{enum.prefix}_{_member(value)}: Final[{enum.name}] = {json.dumps(value)}" for value in enum.values
            )
            members: tuple[str, ...] = tuple(f"{enum.prefix}_{_member(value)}" for value in enum.values)
        else:
            members = tuple(json.dumps(value) for value in enum.values)
        lines.extend(_tuple_lines(enum.collection, enum.name, members))
        if enum.default is not None and enum.prefix is not None:
            lines.append(f"DEFAULT_{enum.prefix}: Final[{enum.name}] = {enum.prefix}_{_member(enum.default)}")
    return lines


def _render_objects(model: Model) -> list[str]:
    lines: list[str] = []
    for obj in model.objects:
        lines.extend(["", ""])
        typed: list[str] = [
            f"{field.annotation}" if field.required else f"NotRequired[{field.annotation}]" for field in obj.fields
        ]
        if all(field.key.isidentifier() and not keyword.iskeyword(field.key) for field in obj.fields):
            lines.extend([f"class {obj.name}(TypedDict):", f'    """{obj.description}"""', ""])
            lines.extend(f"    {field.key}: {annotation}" for field, annotation in zip(obj.fields, typed, strict=True))
        else:
            lines.extend([f"{obj.name} = TypedDict(", f'    "{obj.name}",', "    {"])
            lines.extend(
                f'        "{field.key}": {annotation},' for field, annotation in zip(obj.fields, typed, strict=True)
            )
            lines.extend(["    },", ")"])
    lines.append("")
    for obj in model.objects:
        lines.extend(["", *_tuple_lines(f"{obj.prefix}_FIELDS", "str", tuple(json.dumps(f.key) for f in obj.fields))])
        required: tuple[str, ...] = tuple(json.dumps(f.key) for f in obj.fields if f.required)
        lines.extend(_tuple_lines(f"{obj.prefix}_REQUIRED", "str", required))
    return lines


def _value_fields(model: Model) -> list[tuple[str, str, str]]:
    """List the ``ReconValues`` fields.

    Returns:
        One (field name, annotation, module constant it reads) per field.

    """
    fields: list[tuple[str, str, str]] = [
        ("schema_path", "Path", "SCHEMA_PATH"),
        ("file_template", "str", "RECON_FILE_TEMPLATE"),
    ]
    for enum in model.enums:
        if enum.prefix is not None:
            for value in enum.values:
                constant: str = f"{enum.prefix}_{_member(value)}"
                fields.append((constant.lower(), enum.name, constant))
            if enum.default is not None:
                fields.append((f"default_{enum.prefix.lower()}", enum.name, f"DEFAULT_{enum.prefix}"))
        fields.append((enum.collection.lower(), f"tuple[{enum.name}, ...]", enum.collection))
    fields.extend((constant.lower(), "str", constant) for constant, _ in model.consts)
    return fields


def _render_values(model: Model) -> list[str]:
    fields: list[tuple[str, str, str]] = _value_fields(model)
    lines: list[str] = [
        "",
        "",
        "@dataclass(frozen=True)",
        "class ReconValues:",
        '    """Every allowed value of the contract, read-only, for callers that load this module by path."""',
        "",
    ]
    lines.extend(f"    {name}: {annotation}" for name, annotation, _ in fields)
    lines.extend(["", "", "VALUES: Final[ReconValues] = ReconValues("])
    lines.extend(f"    {name}={constant}," for name, _, constant in fields)
    lines.extend([
        ")",
        "",
        "",
        "def values() -> ReconValues:",
        '    """Read every allowed value of the contract.',
        "",
        "    Returns:",
        "        The contract's values.",
        "",
        '    """',
        "    return VALUES",
    ])
    return lines


def render_python(model: Model) -> str:
    """Render ``recon_contract.py``.

    Args:
        model: The translated schema.

    Returns:
        The module source.

    """
    lines: list[str] = [PY_HEADER.rstrip("\n")]
    lines.append(f"RECON_FILE_TEMPLATE: Final = {json.dumps(model.file_template)}")
    lines.extend(_tuple_lines("PRODUCER_REQUIRED", "str", tuple(json.dumps(key) for key in model.producer_required)))
    lines.extend(_render_enums(model))
    lines.append("")
    lines.extend(f"{constant}: Final = {json.dumps(value)}" for constant, value in model.consts)
    lines.append("")
    keys: list[str] = sorted({field.key for obj in model.objects for field in obj.fields})
    lines.extend(f"KEY_{_snake(key)}: Final = {json.dumps(key)}" for key in keys)
    lines.extend(_render_objects(model))
    lines.extend(_render_values(model))
    return "\n".join(lines) + PY_RUNTIME


JS_TEMPLATE: Final[str] = """// GENERATED by skills/artifact-handoff/scripts/gen_recon_contract.py from
// skills/artifact-handoff/schemas/recon.schema.json, the one definition of recon-<slug>.json and of the
// detailing session's reply. Never edit: change the schema, then run
// python3 skills/artifact-handoff/scripts/gen_recon_contract.py --write and node scripts/shared-blocks.mjs --write.
const RECON_SCHEMA = @SCHEMA@
const RECON_REPLY_SCHEMA = @REPLY@
const reconEnum = (name) => Object.freeze([...RECON_SCHEMA.$defs[name].enum])
const RECON_STATUSES = reconEnum('ReconStatus')
const RECON_WORK_STATUSES = reconEnum('WorkStatus')
const RECON_IDLE_STATUSES = reconEnum('IdleStatus')
const RECON_SURFACES = reconEnum('Surface')
const DESIGN_SOURCES = reconEnum('DesignSource')
const reconConstName = (v) => v.toUpperCase().replace(/[^A-Z0-9]+/g, '_')
const DESIGN_SOURCE = Object.freeze(Object.fromEntries(DESIGN_SOURCES.map((v) => [reconConstName(v), v])))
const ARTIFACT_KINDS = reconEnum('ArtifactKind')
const RECON_FROM_ABSENT = RECON_SCHEMA.$defs.FromAbsent.const
const RECON_TO_REMOVED = RECON_SCHEMA.$defs.ToRemoved.const
/** The detailing file name of one repository, from the schema's file template. */
const reconFileName = (slug) => {
  if (typeof slug !== 'string' || !slug || slug !== slug.trim() || slug.includes('/')) {
    const got = JSON.stringify(slug)
    throw new Error(`recon slug must be a non-empty name with no path separator, got ${got}`)
  }
  return RECON_SCHEMA['x-fileTemplate'].replace('{slug}', slug)
}
/** The detailing's fields as prompt text, rendered from RECON_SCHEMA so no prompt restates them. */
const reconFieldList = () => {
  const defs = RECON_SCHEMA.$defs
  const refName = (node) => (node && typeof node.$ref === 'string' ? node.$ref.split('/').pop() : null)
  const resolve = (node) => (refName(node) ? resolve(defs[refName(node)]) : node)
  const describe = (node) => {
    const name = refName(node)
    const n = resolve(node)
    if (n.anyOf) return n.anyOf.map(describe).join(' or ')
    if (n.enum) return n.enum.join(' | ')
    if (n.const !== undefined) return JSON.stringify(n.const)
    if (n.type === 'object') return name ? `${name} object` : 'object'
    if (n.type === 'array') return `list of ${describe(n.items)}`
    const t = Array.isArray(n.type) ? n.type.join(' or ') : n.type
    return n.pattern ? `${t} matching ${n.pattern}` : t
  }
  const objectOf = (node) => {
    const n = resolve(node)
    if (n.type === 'object') return n
    if (n.type === 'array') return objectOf(n.items)
    if (n.anyOf) return n.anyOf.map(objectOf).find(Boolean) || null
    return null
  }
  const lines = []
  const walk = (obj, depth, required) => {
    for (const [key, raw] of Object.entries(obj.properties || {})) {
      const description = raw.description || resolve(raw).description || ''
      const need = required.includes(key) ? 'required' : 'optional'
      lines.push(`${'  '.repeat(depth)}- \\`${key}\\` (${describe(raw)}, ${need}): ${description}`)
      const child = objectOf(raw)
      if (child) walk(child, depth + 1, child.required || [])
    }
  }
  const root = defs.ReconDetailing
  walk(root, 0, [...new Set([...(root.required || []), ...(RECON_SCHEMA['x-producerRequired'] || [])])])
  return lines.join('\\n')
}
"""


def render_js(model: Model) -> str:
    """Render ``shared-blocks/recon-contract.js``.

    Args:
        model: The translated schema.

    Returns:
        The shared block source.

    """
    defs: JsonObject = _obj(model.schema.get("$defs"), "$defs")
    schema_text: str = json.dumps(model.schema, ensure_ascii=False)
    reply_text: str = json.dumps(_obj(defs.get(REPLY_DEF), REPLY_DEF), ensure_ascii=False)
    return JS_TEMPLATE.replace("@SCHEMA@", schema_text).replace("@REPLY@", reply_text)


def load_schema() -> JsonObject:
    """Read the recon schema.

    Returns:
        The decoded schema.

    Raises:
        SchemaShapeError: The file is not a JSON object.

    """
    value: Json = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    if not _is_object(value):
        message: str = f"{SCHEMA_FILE}: expected a JSON object"
        raise SchemaShapeError(message)
    return value


def main(argv: list[str] | None = None) -> int:
    """Write or check the generated views.

    Args:
        argv: Command-line arguments; ``--write`` or ``--check``.

    Returns:
        0 when written or current; 1 when ``--check`` finds a stale view.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__.partition("\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="rewrite the generated views")
    mode.add_argument("--check", action="store_true", help="exit 1 when a generated view is stale")
    args: argparse.Namespace = parser.parse_args(argv)
    write: bool = bool(args.write)
    model: Model = build_model(load_schema())
    stale: list[str] = []
    for path, text in ((PY_FILE, render_python(model)), (JS_FILE, render_js(model))):
        current: str = path.read_text(encoding="utf-8") if path.is_file() else ""
        if current == text:
            continue
        if write:
            path.write_text(text, encoding="utf-8")
            sys.stdout.write(f"wrote {path}\n")
        else:
            stale.append(str(path))
    for path_text in stale:
        sys.stderr.write(f"{path_text} is stale: run python3 {Path(__file__).name} --write\n")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
