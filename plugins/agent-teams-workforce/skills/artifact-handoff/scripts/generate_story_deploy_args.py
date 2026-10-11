"""Generate ``story_deploy_args.py`` from ``schemas/story-deploy-args.schema.json``.

The schema is the one definition of the Story deploy workflow arguments. This script writes the
typed Python view of it: one Literal alias, value tuple and value constants per enum definition,
one pattern constant per pattern definition, one TypedDict per object definition, the key-name
constants of the four argument shapes, and ``SCHEMA_PATH``/``SCHEMA_SHA256``. Run it after changing
the schema; ``check_story_deploy_args.py`` exits 1 when the generated module is stale.

Only naming lives here (which constant each definition becomes); every key and allowed value is
read from the schema, or from the schema it references for the bead-metadata deploy states.
"""

from __future__ import annotations

import hashlib
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
SCHEMA_FILE: Final[Path] = SKILL_DIR / "schemas" / "story-deploy-args.schema.json"
OUTPUT_FILE: Final[Path] = SKILL_DIR / "scripts" / "story_deploy_args.py"


@dataclass(frozen=True)
class EnumNaming:
    """How one enum definition is named in the generated module."""

    alias: str
    collection: str
    prefix: str | None
    empty_name: str | None = None


#: Enum definition -> naming. The values themselves come from the schema.
ENUMS: Final[dict[str, EnumNaming]] = {
    "Composite": EnumNaming("Composite", "COMPOSITES", "COMPOSITE_"),
    "DeployState": EnumNaming("DeployState", "DEPLOY_STATES", "STATE_", "STATE_NONE"),
    "FailureStep": EnumNaming("FailureStep", "FAILURE_STEPS", "STEP_"),
    "VerifiedStackStatus": EnumNaming("VerifiedStackStatus", "VERIFIED_STATUSES", None),
}
#: Pattern definition -> constant name.
PATTERNS: Final[dict[str, str]] = {"SubjectFolder": "SUBJECT_FOLDER_PATTERN", "PluginRoot": "PLUGIN_ROOT_PATTERN"}
#: The four argument shapes whose top-level keys become KEY_<NAME> constants.
ARG_SHAPES: Final[tuple[str, ...]] = (
    "StoryDeployInput",
    "BuiltVersionArgs",
    "StoryDeployFixArgs",
    "DeployMechanismArgs",
)
#: The object definition whose keys are ITEM_KEYS.
ITEM_DEF: Final[str] = "BuiltVersionItem"
LOCAL_REF: Final[str] = "#/$defs/"


class SchemaShapeError(ValueError):
    """The story-deploy-args schema uses a shape this generator does not translate."""


@dataclass(frozen=True)
class Field:
    """One property of an object definition, translated."""

    key: str
    annotation: str
    required: bool


@dataclass(frozen=True)
class Shape:
    """One object definition, translated."""

    name: str
    summary: str
    fields: tuple[Field, ...]
    closed: bool


@dataclass(frozen=True)
class Model:
    """The translated schema."""

    enums: dict[str, tuple[str, ...]]
    patterns: dict[str, str]
    shapes: tuple[Shape, ...]


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


def _read(path: Path) -> JsonObject:
    value: Json = json.loads(path.read_text(encoding="utf-8"))
    return _obj(value, str(path))


def _external_enum(ref: str, where: str) -> list[str]:
    """Read the enum an external ``file#/$defs/Name`` reference names.

    Returns:
        The referenced definition's enum values.

    Raises:
        SchemaShapeError: The reference is not of that form.

    """
    file_part, _, pointer = ref.partition("#")
    if not file_part or not pointer.startswith("/$defs/"):
        message: str = f"{where}: unsupported reference {ref!r}"
        raise SchemaShapeError(message)
    target: JsonObject = _read((SCHEMA_FILE.parent / file_part).resolve())
    definition: JsonObject = _obj(_obj(target.get("$defs"), f"{ref} $defs").get(pointer.removeprefix("/$defs/")), ref)
    return _texts(definition.get("enum"), f"{ref}.enum")


def _enum_values(name: str, definition: JsonObject) -> tuple[str, ...]:
    where: str = f"$defs.{name}"
    values: list[str] = []
    if "enum" in definition:
        values = _texts(definition.get("enum"), f"{where}.enum")
    elif "anyOf" in definition:
        branches: Json = definition.get("anyOf")
        if not isinstance(branches, list):
            message: str = f"{where}.anyOf: expected an array"
            raise SchemaShapeError(message)
        for index, raw in enumerate(branches):
            branch: JsonObject = _obj(raw, f"{where}.anyOf[{index}]")
            if "const" in branch:
                values.append(_text(branch.get("const"), f"{where}.anyOf[{index}].const"))
            else:
                values.extend(_external_enum(_text(branch.get("$ref"), f"{where}.anyOf[{index}].$ref"), where))
    else:
        message = f"{where}: expected enum or anyOf"
        raise SchemaShapeError(message)
    if not values or len(set(values)) != len(values):
        message = f"{where}: values are empty or repeat"
        raise SchemaShapeError(message)
    return tuple(values)


def _annotation(schema: JsonObject, where: str, objects: frozenset[str]) -> str:
    ref: Json = schema.get("$ref")
    if isinstance(ref, str):
        if not ref.startswith(LOCAL_REF):
            message: str = f"{where}: only local references are translated: {ref!r}"
            raise SchemaShapeError(message)
        target: str = ref.removeprefix(LOCAL_REF)
        if target in ENUMS:
            return ENUMS[target].alias
        if target in PATTERNS:
            return "str"
        if target in objects:
            return target
        message = f"{where}: reference to an unknown definition {target!r}"
        raise SchemaShapeError(message)
    kind: Json = schema.get("type")
    if kind == "string":
        return "str"
    if kind == "integer":
        return "int"
    if kind == "array":
        return "list[" + _annotation(_obj(schema.get("items"), f"{where}.items"), f"{where}.items", objects) + "]"
    message = f"{where}: untranslated property type {kind!r}"
    raise SchemaShapeError(message)


def _shape(name: str, definition: JsonObject, objects: frozenset[str]) -> Shape:
    where: str = f"$defs.{name}"
    properties: JsonObject = _obj(definition.get("properties"), f"{where}.properties")
    required: list[str] = _texts(definition.get("required"), f"{where}.required")
    unknown: list[str] = [key for key in required if key not in properties]
    if unknown:
        message: str = f"{where}: required names unknown properties {unknown}"
        raise SchemaShapeError(message)
    fields: tuple[Field, ...] = tuple(
        Field(key, _annotation(_obj(raw, f"{where}.{key}"), f"{where}.{key}", objects), key in required)
        for key, raw in properties.items()
    )
    summary: str = _text(definition.get("description"), f"{where}.description").partition(";")[0].rstrip(".")
    return Shape(name, summary, fields, definition.get("additionalProperties") is False)


def build_model(schema: JsonObject) -> Model:
    """Translate the story-deploy-args schema.

    Args:
        schema: The decoded schema.

    Returns:
        The translated model.

    Raises:
        SchemaShapeError: The schema uses a shape the generator does not translate.

    """
    defs: JsonObject = _obj(schema.get("$defs"), "$defs")
    objects: frozenset[str] = frozenset(
        name for name, raw in defs.items() if _is_object(raw) and raw.get("type") == "object"
    )
    missing: list[str] = [name for name in (*ENUMS, *PATTERNS, *ARG_SHAPES, ITEM_DEF) if name not in defs]
    if missing:
        message: str = f"$defs lacks {missing}"
        raise SchemaShapeError(message)
    enums: dict[str, tuple[str, ...]] = {name: _enum_values(name, _obj(defs[name], name)) for name in ENUMS}
    patterns: dict[str, str] = {
        name: _text(_obj(defs[name], name).get("pattern"), f"$defs.{name}.pattern") for name in PATTERNS
    }
    shapes: tuple[Shape, ...] = tuple(_shape(name, _obj(defs[name], name), objects) for name in defs if name in objects)
    return Model(enums, patterns, shapes)


def _snake(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)).strip("_").upper()


LINE_LIMIT: Final[int] = 120


def _tuple(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(json.dumps(value) for value in values) + ("," if len(values) == 1 else "") + ")"


def _assign_tuple(target: str, values: tuple[str, ...]) -> list[str]:
    """Render ``target = (values)`` on one line, or one value per line when it would be too long.

    Returns:
        The source lines, in the layout ``ruff format`` keeps.

    """
    line: str = f"{target} = {_tuple(values)}"
    if len(line) <= LINE_LIMIT:
        return [line]
    return [f"{target} = (", *(f"    {json.dumps(value)}," for value in values), ")"]


def _enum_lines(name: str, values: tuple[str, ...]) -> list[str]:
    naming: EnumNaming = ENUMS[name]
    literal: str = "Literal[" + ", ".join(json.dumps(value) for value in values) + "]"
    lines: list[str] = [f"type {naming.alias} = {literal}"]
    if naming.prefix is not None:
        for value in values:
            constant: str = naming.empty_name if not value and naming.empty_name else naming.prefix + _snake(value)
            lines.append(f"{constant}: Final[{naming.alias}] = {json.dumps(value)}")
    ordered: str = f"_{naming.collection}_ORDER"
    lines.extend(_assign_tuple(f"{ordered}: Final[tuple[{naming.alias}, ...]]", values))
    lines.extend((f"{naming.collection}: Final[frozenset[{naming.alias}]] = frozenset({ordered})", ""))
    return lines


def _shape_lines(shape: Shape) -> list[str]:
    def kind(field: Field) -> str:
        return field.annotation if field.required else f"NotRequired[{field.annotation}]"

    if any(keyword.iskeyword(field.key) or not field.key.isidentifier() for field in shape.fields):
        entries: str = "".join(f"\n        {json.dumps(field.key)}: {kind(field)}," for field in shape.fields)
        return [
            "",
            f"# {shape.summary}.",
            f"{shape.name} = TypedDict(",
            f'    "{shape.name}",',
            "    {" + entries,
            "    },",
            ")",
            "",
        ]
    lines: list[str] = ["", f"class {shape.name}(TypedDict):", f'    """{shape.summary}."""', ""]
    lines.extend(f"    {field.key}: {kind(field)}" for field in shape.fields)
    lines.append("")
    return lines


HEADER: Final[str] = '''"""The Story deploy workflow arguments: the story-deploy input and three workflows' arguments.

GENERATED by scripts/generate_story_deploy_args.py from schemas/story-deploy-args.schema.json. Never
edit this file: change the schema and run ``python3 scripts/generate_story_deploy_args.py``.
"""

from pathlib import Path
from typing import Final, Literal, NotRequired, TypedDict

SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "schemas" / "story-deploy-args.schema.json"
'''


def render(schema: JsonObject, digest: str) -> str:
    """Render the generated module for ``schema``.

    Args:
        schema: The decoded story-deploy-args schema.
        digest: The SHA-256 of the schema file's bytes.

    Returns:
        The module source.

    """
    model: Model = build_model(schema)
    lines: list[str] = [HEADER.rstrip("\n"), f'SCHEMA_SHA256: Final = "{digest}"', ""]
    for name, values in model.enums.items():
        lines.extend(_enum_lines(name, values))
    lines.extend(f"{PATTERNS[name]}: Final = {json.dumps(pattern)}" for name, pattern in model.patterns.items())
    lines.append("")
    by_name: dict[str, Shape] = {shape.name: shape for shape in model.shapes}
    arg_keys: list[str] = []
    for name in ARG_SHAPES:
        arg_keys.extend(field.key for field in by_name[name].fields if field.key not in arg_keys)
    lines.extend(f'KEY_{_snake(key)}: Final = "{key}"' for key in arg_keys)
    item_keys: tuple[str, ...] = tuple(field.key for field in by_name[ITEM_DEF].fields)
    lines.extend(_assign_tuple("ARG_KEYS: Final[tuple[str, ...]]", tuple(arg_keys)))
    lines.extend(_assign_tuple("ITEM_KEYS: Final[tuple[str, ...]]", item_keys))
    lines.append("")
    for shape in model.shapes:
        keys: tuple[str, ...] = tuple(field.key for field in shape.fields)
        required: tuple[str, ...] = tuple(field.key for field in shape.fields if field.required)
        prefix: str = _snake(shape.name)
        lines.extend(_assign_tuple(f"{prefix}_KEYS: Final[tuple[str, ...]]", keys))
        lines.extend(_assign_tuple(f"_{prefix}_REQUIRED_ORDER: Final[tuple[str, ...]]", required))
        lines.extend((
            f"{prefix}_REQUIRED: Final[frozenset[str]] = frozenset(_{prefix}_REQUIRED_ORDER)",
            f"{prefix}_CLOSED: Final = {shape.closed}",
        ))
    lines.append("")
    for shape in model.shapes:
        lines.extend(_shape_lines(shape))
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def load_schema() -> tuple[JsonObject, str]:
    """Read the story-deploy-args schema and the digest of its bytes.

    Returns:
        The decoded schema and its SHA-256.

    """
    raw: bytes = SCHEMA_FILE.read_bytes()
    decoded: Json = json.loads(raw)
    return _obj(decoded, str(SCHEMA_FILE)), hashlib.sha256(raw).hexdigest()


def expected() -> str:
    """Render the module the schema currently defines.

    Returns:
        The module source.

    """
    schema, digest = load_schema()
    return render(schema, digest)


def main() -> int:
    """Write the generated module from the schema.

    Returns:
        0 once the module is written or already current.

    """
    text: str = expected()
    current: str = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.is_file() else ""
    if current != text:
        OUTPUT_FILE.write_text(text, encoding="utf-8")
    sys.stdout.write(f"wrote {OUTPUT_FILE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
