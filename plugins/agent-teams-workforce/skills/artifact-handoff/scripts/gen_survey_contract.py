"""Generate ``survey_contract.py`` from ``schemas/survey.schema.json``.

The survey schema is the one definition of the architecture survey (``survey.json``) and of the
architecture baseline (``$defs/Baseline``). This script writes the Python view of it: TypedDicts,
Literal aliases, allowed-value constants, key-name constants, the rule mappings and a validating
parser. Run it after changing the schema; ``--check`` exits 1 when the generated module is stale.

Only naming lives here (which constant prefix each enum's values take, which rule becomes which
mapping); every key, type, allowed value, default and rule is read from the schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeIs

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None
type JsonObject = dict[str, Json]

SKILL_DIR: Final[Path] = Path(__file__).resolve().parents[1]
SCHEMA_FILE: Final[Path] = SKILL_DIR / "schemas" / "survey.schema.json"
OUTPUT_FILE: Final[Path] = SKILL_DIR / "survey_contract.py"
ROOT_NAME: Final[str] = "Survey"
BASELINE_DEF: Final[str] = "Baseline"
EVIDENCE_DEF: Final[str] = "EvidenceRef"
IDENTITY_KEY: Final[str] = "id"
WIDTH: Final[int] = 120

#: Enum $def -> (prefix of each value's constant, name of the frozenset of all values).
ENUM_NAMING: Final[dict[str, tuple[str, str]]] = {
    "CoverageStatus": ("STATUS_", "COVERAGE_STATUSES"),
    "CoverageAction": ("ACTION_", "COVERAGE_ACTIONS"),
    "CoverageDisposition": ("COVERAGE_", "COVERAGE_DISPOSITIONS"),
    "DocumentVersion": ("VERSION_", "DOCUMENT_VERSIONS"),
    "DocumentLifecycleState": ("LIFECYCLE_", "DOCUMENT_LIFECYCLE_STATES"),
    "CodeState": ("CODE_", "CODE_STATES"),
    "BaselineKind": ("KIND_", "BASELINE_KINDS"),
    "DesignAction": ("DESIGN_", "DESIGN_ACTIONS"),
    "DocumentationAction": ("DOC_", "DOCUMENTATION_ACTIONS"),
    "ImplementationAction": ("IMPL_", "IMPLEMENTATION_ACTIONS"),
    "BaselineDisposition": ("DISPOSITION_", "BASELINE_DISPOSITIONS"),
}
#: Rule $def (a oneOf of const pairs) -> (mapping constant, key enum, value enum).
RULE_MAPPINGS: Final[dict[str, tuple[str, str, str]]] = {
    "DispositionImplementationAction": ("DISPOSITION_ACTION", "BaselineDisposition", "ImplementationAction"),
    "CodeStateImplementationAction": ("CODE_STATE_ACTION", "CodeState", "ImplementationAction"),
    "CoverageStatusAction": ("COVERAGE_STATUS_ACTION", "CoverageStatus", "CoverageAction"),
}
#: Rule $def giving the values a fresh entry of an object $def carries -> that object $def.
FRESH_RULES: Final[dict[str, str]] = {"FreshBaselineEntry": "BaselineEntry"}
#: Rule $def whose ``then`` names fields required only conditionally (left out of text groups).
CONDITIONAL_RULES: Final[tuple[str, ...]] = ("UnrelatedDebtReason",)
#: Key groups: (constant, alias, object $def, selector).
KEY_GROUPS: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("BASELINE_REF_LISTS", "BaselineRefListKey", "BaselineEntry", "evidence-lists"),
    ("CODE_REF_LISTS", "CodeRefListKey", "BaselineCode", "evidence-lists"),
    ("BASELINE_TEXT_FIELDS", "BaselineTextKey", "BaselineEntry", "free-text"),
    ("COVERAGE_LIST_FIELDS", "CoverageListKey", "CoverageRow", "string-lists"),
    ("COVERAGE_TEXT_FIELDS", "CoverageTextKey", "CoverageRow", "free-text"),
)


class SchemaShapeError(ValueError):
    """The survey schema uses a shape this generator does not translate."""


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


def _texts(value: Json, where: str) -> list[str]:
    if not isinstance(value, list):
        message: str = f"{where}: expected an array"
        raise SchemaShapeError(message)
    return [_text(item, f"{where}[{index}]") for index, item in enumerate(value)]


def _int(value: Json, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        message: str = f"{where}: expected an integer"
        raise SchemaShapeError(message)
    return value


def _snake(name: str) -> str:
    out: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def _const_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).upper()


def _ref_name(schema: JsonObject, where: str) -> str | None:
    ref: Json = schema.get("$ref")
    if ref is None:
        return None
    text: str = _text(ref, where)
    prefix: str = "#/$defs/"
    if not text.startswith(prefix):
        message: str = f"{where}: only local $defs references are supported, got {text}"
        raise SchemaShapeError(message)
    return text[len(prefix) :]


def _doc(text: str, indent: str) -> list[str]:
    summary, _, rest = text.partition(". ")
    summary = summary if summary.endswith(".") or not rest else f"{summary}."
    if len(indent) + len(summary) + 6 > WIDTH:
        message: str = f"description summary is longer than one line: {summary}"
        raise SchemaShapeError(message)
    if not rest:
        return [f'{indent}"""{summary}"""']
    body: list[str] = textwrap.wrap(rest, width=WIDTH - len(indent), break_on_hyphens=False)
    return [f'{indent}"""{summary}', "", *[f"{indent}{line}" for line in body], f'{indent}"""']


@dataclass(frozen=True)
class Field:
    """One property of an object $def, translated."""

    key: str
    annotation: str
    parse: str
    required: bool
    kind: str


@dataclass(frozen=True)
class Model:
    """The translated schema."""

    enums: dict[str, list[str]]
    defaults: dict[str, str]
    objects: dict[str, list[Field]]
    descriptions: dict[str, str]
    arrays: dict[str, tuple[str, int]]
    rules: dict[str, JsonObject]


def _field(owner: str, key: str, schema: JsonObject, required: bool, model_defs: JsonObject) -> Field:
    where: str = f"{owner}.{key}"
    head: str = f'raw, path, "{key}"'
    ref: str | None = _ref_name(schema, where)
    if ref is not None:
        target: JsonObject = _obj(model_defs.get(ref), f"$defs.{ref}")
        if "enum" in target:
            return Field(key, ref, f"_member({head}, {ENUM_NAMING[ref][1]})", required, "enum")
        is_array: bool = target.get("type") == "array"
        annotation: str = f"list[{_array_item(ref, target)}]" if is_array else ref
        return Field(key, annotation, f"_child({head}, _parse_{_snake(ref)})", required, "object")
    kind_name: str = _text(schema.get("type"), f"{where}.type")
    if kind_name == "string":
        minimum: int = _int(schema.get("minLength", 0), f"{where}.minLength")
        return Field(key, "str", f"_string({head}, {minimum})", required, "string")
    if kind_name != "array":
        message: str = f"{where}: unsupported type {kind_name}"
        raise SchemaShapeError(message)
    items: JsonObject = _obj(schema.get("items"), f"{where}.items")
    min_items: int = _int(schema.get("minItems", 0), f"{where}.minItems")
    item_ref: str | None = _ref_name(items, f"{where}.items")
    if item_ref is not None:
        parse: str = f"_objects({head}, {min_items}, _parse_{_snake(item_ref)})"
        return Field(key, f"list[{item_ref}]", parse, required, f"list:{item_ref}")
    if _text(items.get("type"), f"{where}.items.type") != "string":
        message = f"{where}: only arrays of strings or of $defs are supported"
        raise SchemaShapeError(message)
    item_min: int = _int(items.get("minLength", 0), f"{where}.items.minLength")
    return Field(key, "list[str]", f"_strings({head}, {min_items}, {item_min})", required, "list:str")


def _array_item(name: str, schema: JsonObject) -> str:
    item: str | None = _ref_name(_obj(schema.get("items"), f"$defs.{name}.items"), f"$defs.{name}.items")
    if item is None:
        message: str = f"$defs.{name}: an array $def must hold $defs items"
        raise SchemaShapeError(message)
    return item


def _object_fields(name: str, schema: JsonObject, defs: JsonObject) -> list[Field]:
    if schema.get("additionalProperties") is not False:
        message: str = f"{name}: object $defs must set additionalProperties false"
        raise SchemaShapeError(message)
    required: list[str] = _texts(schema.get("required", []), f"{name}.required")
    properties: JsonObject = _obj(schema.get("properties"), f"{name}.properties")
    ordered: list[str] = [*required, *[key for key in properties if key not in required]]
    return [
        _field(name, key, _obj(properties.get(key), f"{name}.properties.{key}"), key in required, defs)
        for key in ordered
    ]


def build_model(schema: JsonObject) -> Model:
    """Translate the survey schema.

    Args:
        schema: The decoded survey schema.

    Returns:
        The translated model.

    Raises:
        SchemaShapeError: The schema uses a shape the generator does not translate.

    """
    defs: JsonObject = _obj(schema.get("$defs"), "$defs")
    model: Model = Model({}, {}, {}, {}, {}, {})
    for name, raw in defs.items():
        definition: JsonObject = _obj(raw, f"$defs.{name}")
        model.descriptions[name] = _text(definition.get("description", name), f"$defs.{name}.description")
        if "enum" in definition:
            if name not in ENUM_NAMING:
                message: str = f"$defs.{name}: enum has no constant naming in ENUM_NAMING"
                raise SchemaShapeError(message)
            model.enums[name] = _texts(definition["enum"], f"$defs.{name}.enum")
            if "default" in definition:
                model.defaults[name] = _text(definition["default"], f"$defs.{name}.default")
        elif definition.get("type") == "array":
            model.arrays[name] = (_array_item(name, definition), _int(definition.get("minItems", 0), name))
        elif definition.get("additionalProperties") is False:
            model.objects[name] = _object_fields(name, definition, defs)
        else:
            model.rules[name] = definition
    model.descriptions[ROOT_NAME] = _text(schema.get("description", ROOT_NAME), "description")
    model.objects[ROOT_NAME] = _object_fields(ROOT_NAME, schema, defs)
    unknown: set[str] = set(ENUM_NAMING) - set(model.enums)
    if unknown:
        message = f"ENUM_NAMING names enums the schema lacks: {sorted(unknown)}"
        raise SchemaShapeError(message)
    return model


def _value_constant(model: Model, enum: str, value: str) -> str:
    if value not in model.enums[enum]:
        message: str = f"{value!r} is not a value of {enum}"
        raise SchemaShapeError(message)
    return ENUM_NAMING[enum][0] + _const_name(value)


def _pairs(model: Model, rule: str) -> list[tuple[str, str]]:
    alternatives: Json = model.rules[rule].get("oneOf")
    if not isinstance(alternatives, list):
        message: str = f"$defs.{rule}: a mapping rule is a oneOf of const pairs"
        raise SchemaShapeError(message)
    pairs: list[tuple[str, str]] = []
    for index, raw in enumerate(alternatives):
        where: str = f"$defs.{rule}.oneOf[{index}]"
        alternative: JsonObject = _obj(raw, where)
        keys: list[str] = _texts(alternative.get("required"), f"{where}.required")
        properties: JsonObject = _obj(alternative.get("properties"), f"{where}.properties")
        source, target = (_text(_obj(properties.get(k), f"{where}.{k}").get("const"), f"{where}.{k}") for k in keys)
        pairs.append((source, target))
    return pairs


def _fresh(model: Model, rule: str, owner: str) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []

    def walk(schema: JsonObject, object_def: str, trail: list[str]) -> None:
        properties: JsonObject = _obj(schema.get("properties"), f"$defs.{rule}")
        fields: dict[str, Field] = {field.key: field for field in model.objects[object_def]}
        for key, raw in properties.items():
            part: JsonObject = _obj(raw, f"$defs.{rule}.{key}")
            field: Field = fields[key]
            if "const" in part:
                value: str = _text(part["const"], f"$defs.{rule}.{key}.const")
                name: str = "FRESH_" + _const_name("_".join([*trail, _snake(key)]))
                found.append((name, field.annotation, _value_constant(model, field.annotation, value)))
            else:
                walk(part, field.annotation, [*trail, _snake(key)])

    walk(model.rules[rule], owner, [])
    return found


def _group(model: Model, owner: str, selector: str) -> list[str]:
    conditional: set[str] = set()
    for rule in CONDITIONAL_RULES:
        then: JsonObject = _obj(model.rules[rule].get("then"), f"$defs.{rule}.then")
        conditional.update(_obj(then.get("properties"), f"$defs.{rule}.then.properties"))
    fields: list[Field] = model.objects[owner]
    if selector == "evidence-lists":
        return [field.key for field in fields if field.kind == f"list:{EVIDENCE_DEF}"]
    if selector == "string-lists":
        return [field.key for field in fields if field.kind == "list:str"]
    if selector == "free-text":
        return [
            field.key
            for field in fields
            if field.kind == "string" and field.key != IDENTITY_KEY and field.key not in conditional
        ]
    message: str = f"unknown key-group selector {selector}"
    raise SchemaShapeError(message)


def _literal(values: list[str]) -> str:
    inner: str = "".join(f"    {json.dumps(value)},\n" for value in values)
    return f"Literal[\n{inner}]"


def _tuple(values: list[str]) -> str:
    if not values:
        return "()"
    inner: str = "".join(f"    {value},\n" for value in values)
    return f"(\n{inner})"


HEADER: Final[str] = '''"""The architecture survey contract (``survey.json``) and the architecture baseline.

GENERATED by scripts/gen_survey_contract.py from schemas/survey.schema.json. Never edit this file:
change the schema and run ``python3 scripts/gen_survey_contract.py``. The schema is the one
definition; this module is its typed Python view.
"""

import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal, NotRequired, TypedDict, TypeIs

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None

SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parent / "schemas" / "survey.schema.json"
'''

HELPERS: Final[str] = '''

class SurveyContractError(ValueError):
    """A value or the schema file does not satisfy the survey contract."""


def _is_json(value: object) -> TypeIs[JsonValue]:
    if value is None or isinstance(value, bool | int | float | str):
        return True
    if isinstance(value, list):
        return all(_is_json(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json(item) for key, item in value.items())
    return False


def _is_json_object(value: object) -> TypeIs[dict[str, JsonValue]]:
    return isinstance(value, dict) and _is_json(value)


def load_schema() -> dict[str, JsonValue]:
    """Read the survey schema, the one definition of this contract.

    Returns:
        The decoded ``survey.schema.json``.

    Raises:
        SurveyContractError: The file is not a JSON object.

    """
    value: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not _is_json_object(value):
        message: str = f"{SCHEMA_PATH} is not a JSON object"
        raise SurveyContractError(message)
    return value


def schema_sha256() -> str:
    """Hash the survey schema the way this module was generated from it.

    Returns:
        The SHA-256 of the canonical JSON of ``survey.schema.json``; equal to ``SCHEMA_SHA256`` when current.

    """
    canonical: str = json.dumps(load_schema(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def baseline_schema() -> dict[str, JsonValue]:
    """Build a self-contained JSON Schema for the architecture baseline array.

    Returns:
        A schema whose root is ``$defs/Baseline`` of the survey schema, with every ``$defs``.

    Raises:
        SurveyContractError: The survey schema carries no ``$defs`` object.

    """
    schema: dict[str, JsonValue] = load_schema()
    defs: JsonValue = schema.get("$defs")
    if not _is_json_object(defs):
        message: str = f"{SCHEMA_PATH} carries no $defs object"
        raise SurveyContractError(message)
    return {"$schema": schema.get("$schema"), "$defs": defs, "$ref": BASELINE_REF}


def _mapping(value: object, path: str, required: tuple[str, ...], allowed: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(value, dict):
        message: str = f"{path}: expected an object"
        raise SurveyContractError(message)
    raw: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            message = f"{path}: object keys must be strings"
            raise SurveyContractError(message)
        raw[key] = item
    missing: list[str] = [key for key in required if key not in raw]
    if missing:
        message = f"{path}: missing {', '.join(missing)}"
        raise SurveyContractError(message)
    unknown: list[str] = sorted(key for key in raw if key not in allowed)
    if unknown:
        message = f"{path}: unknown {', '.join(unknown)}"
        raise SurveyContractError(message)
    return raw


def _text(value: object, path: str, min_length: int) -> str:
    if not isinstance(value, str):
        message: str = f"{path}: expected a string"
        raise SurveyContractError(message)
    if len(value) < min_length:
        message = f"{path}: shorter than {min_length}"
        raise SurveyContractError(message)
    return value


def _array(value: object, path: str, min_items: int) -> list[object]:
    if not isinstance(value, list):
        message: str = f"{path}: expected an array"
        raise SurveyContractError(message)
    items: list[object] = list(value)
    if len(items) < min_items:
        message = f"{path}: fewer than {min_items} items"
        raise SurveyContractError(message)
    return items


def _string(raw: dict[str, object], path: str, key: str, min_length: int) -> str:
    return _text(raw[key], f"{path}.{key}", min_length)


def _strings(raw: dict[str, object], path: str, key: str, min_items: int, min_length: int) -> list[str]:
    at: str = f"{path}.{key}"
    return [_text(item, f"{at}[{index}]", min_length) for index, item in enumerate(_array(raw[key], at, min_items))]


def _member[T: str](raw: dict[str, object], path: str, key: str, allowed: frozenset[T]) -> T:
    value: object = raw[key]
    for member in allowed:
        if value == member:
            return member
    message: str = f"{path}.{key}: {value!r} is not one of {sorted(allowed)}"
    raise SurveyContractError(message)


def _child[T](raw: dict[str, object], path: str, key: str, parse: Callable[[object, str], T]) -> T:
    return parse(raw[key], f"{path}.{key}")


def _objects[T](
    raw: dict[str, object],
    path: str,
    key: str,
    min_items: int,
    parse: Callable[[object, str], T],
) -> list[T]:
    at: str = f"{path}.{key}"
    return [parse(item, f"{at}[{index}]") for index, item in enumerate(_array(raw[key], at, min_items))]
'''


def _render_constants(model: Model) -> list[str]:
    lines: list[str] = []
    for enum, values in model.enums.items():
        prefix, set_name = ENUM_NAMING[enum]
        members: str = "".join(f"    {prefix}{_const_name(value)},\n" for value in values)
        lines.extend(["", f"type {enum} = {_literal(values)}"])
        lines.extend(f'{prefix}{_const_name(value)}: Final[{enum}] = "{value}"' for value in values)
        lines.append(f"{set_name}: Final[frozenset[{enum}]] = frozenset((\n{members}))")
        if enum in model.defaults:
            default: str = _value_constant(model, enum, model.defaults[enum])
            lines.append(f"DEFAULT_{_snake(enum).upper()}: Final[{enum}] = {default}")
    lines.append("")
    for constant, alias, owner, selector in KEY_GROUPS:
        keys: list[str] = _group(model, owner, selector)
        lines.extend((
            f"type {alias} = {_literal(keys)}",
            f"{constant}: Final[tuple[{alias}, ...]] = {_tuple([json.dumps(key) for key in keys])}",
        ))
    for name, fields in model.objects.items():
        upper: str = _snake(name).upper()
        required: list[str] = [json.dumps(f.key) for f in fields if f.required]
        lines.extend((
            f"{upper}_KEYS: Final[tuple[str, ...]] = {_tuple([json.dumps(f.key) for f in fields])}",
            f"{upper}_REQUIRED_KEYS: Final[tuple[str, ...]] = {_tuple(required)}",
        ))
    for rule, owner in FRESH_RULES.items():
        fresh: list[tuple[str, str, str]] = _fresh(model, rule, owner)
        lines.extend(f"{name}: Final[{annotation}] = {value}" for name, annotation, value in fresh)
    for rule, (constant, source, target) in RULE_MAPPINGS.items():
        entries: str = "".join(
            f"    {_value_constant(model, source, key)}: {_value_constant(model, target, value)},\n"
            for key, value in _pairs(model, rule)
        )
        lines.append(f"{constant}: Final[Mapping[{source}, {target}]] = MappingProxyType({{\n{entries}}})")
    return lines


def _render_types(model: Model) -> list[str]:
    lines: list[str] = []
    names: list[str] = [name for name in model.objects if name != ROOT_NAME]
    for name in [*names, ROOT_NAME]:
        lines.extend(["", "", f"class {name}(TypedDict):", *_doc(model.descriptions[name], "    "), ""])
        lines.extend(
            f"    {f.key}: {f.annotation if f.required else f'NotRequired[{f.annotation}]'}"
            for f in model.objects[name]
        )
    return lines


def _render_enum_parsers(model: Model) -> list[str]:
    lines: list[str] = []
    for enum in model.enums:
        set_name: str = ENUM_NAMING[enum][1]
        lines.extend([
            "",
            "",
            f"def is_{_snake(enum)}(value: object) -> TypeIs[{enum}]:",
            f'    """Decide whether ``value`` is one of the {enum} values.',
            "",
            "    Returns:",
            f"        Whether ``value`` is in ``{set_name}``.",
            "",
            '    """',
            f"    return value in {set_name}",
        ])
    for name, (item, min_items) in model.arrays.items():
        lines.extend([
            "",
            "",
            f"def _parse_{_snake(name)}(value: object, path: str) -> list[{item}]:",
            f"    items: list[object] = _array(value, path, {min_items})",
            f'    return [_parse_{_snake(item)}(entry, f"{{path}}[{{index}}]") for index, entry in enumerate(items)]',
        ])
    return lines


def _render_object_parsers(model: Model) -> list[str]:
    lines: list[str] = []
    for name, fields in model.objects.items():
        snake: str = _snake(name)
        upper: str = snake.upper()
        lines.extend([
            "",
            "",
            f"def _parse_{snake}(value: object, path: str) -> {name}:",
            f"    raw: dict[str, object] = _mapping(value, path, {upper}_REQUIRED_KEYS, {upper}_KEYS)",
            f"    result: {name} = {{",
        ])
        lines.extend(f'        "{f.key}": {f.parse},' for f in fields if f.required)
        lines.append("    }")
        for f in fields:
            if not f.required:
                lines.extend([f'    if "{f.key}" in raw:', f'        result["{f.key}"] = {f.parse}'])
        lines.append("    return result")
    return lines


def _render_entry_points(model: Model) -> list[str]:
    baseline_item: str = model.arrays[BASELINE_DEF][0]
    return [
        "",
        "",
        f"def parse_survey(value: object) -> {ROOT_NAME}:",
        '    """Validate a decoded ``survey.json`` against the contract.',
        "",
        "    A value that breaks the contract raises ``SurveyContractError`` naming where.",
        "",
        "    Returns:",
        "        The survey, typed.",
        "",
        '    """',
        f'    return _parse_{_snake(ROOT_NAME)}(value, "survey")',
        "",
        "",
        f"def parse_baseline(value: object) -> list[{baseline_item}]:",
        '    """Validate a decoded architecture baseline array against the contract.',
        "",
        "    A value that breaks the contract raises ``SurveyContractError`` naming where.",
        "",
        "    Returns:",
        "        The baseline entries, typed.",
        "",
        '    """',
        f'    return _parse_{_snake(BASELINE_DEF)}(value, "baseline")',
        "",
    ]


def render(schema: JsonObject) -> str:
    """Render the generated module for ``schema``.

    Args:
        schema: The decoded survey schema.

    Returns:
        The module source.

    """
    model: Model = build_model(schema)
    digest: str = hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    title: str = _text(schema.get("title"), "title")
    lines: list[str] = [
        HEADER.rstrip("\n"),
        f'SCHEMA_SHA256: Final[str] = "{digest}"',
        f'SURVEY_FILE: Final[str] = "{title}"',
        f'BASELINE_REF: Final[str] = "#/$defs/{BASELINE_DEF}"',
        "",
        *_render_constants(model),
        *_render_types(model),
        HELPERS.rstrip("\n"),
        *_render_enum_parsers(model),
        *_render_object_parsers(model),
        *_render_entry_points(model),
    ]
    return "\n".join(lines)


def _load(path: Path) -> JsonObject:
    value: Json = json.loads(path.read_text(encoding="utf-8"))
    return _obj(value, str(path))


def main(argv: list[str]) -> int:
    """Write the generated module, or with ``--check`` report whether it is current.

    Args:
        argv: Command-line arguments after the program name.

    Returns:
        0 when written or current, 1 when ``--check`` finds the module stale.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when survey_contract.py is stale")
    check: bool = bool(parser.parse_args(argv).check)
    text: str = render(_load(SCHEMA_FILE))
    current: str = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.is_file() else ""
    if check:
        if current != text:
            sys.stderr.write(f"{OUTPUT_FILE} is stale: run python3 {Path(__file__).name}\n")
            return 1
        sys.stdout.write(f"{OUTPUT_FILE.name} is current\n")
        return 0
    if current != text:
        OUTPUT_FILE.write_text(text, encoding="utf-8")
    sys.stdout.write(f"wrote {OUTPUT_FILE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
