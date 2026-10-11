"""Generate ``infra_vocabulary.py`` from ``schemas/infra-vocabulary.schema.json``.

The schema is the one definition of the infrastructure routing vocabulary and the only place its
values are written. This script writes the typed Python view of it: the ``InfraType`` and
``InfraLabel`` Literal aliases, the key-name constants, the carrier-key constant, the value
constants, the ``InfraVocabulary`` TypedDict and ``vocabulary()``. Run it after changing the schema;
``check_infra_vocabulary.py`` exits 1 when the generated module is stale.

Only naming lives here (which alias and which collection each property becomes); every key and
allowed value is read from the schema.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, TypeIs

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None
type JsonObject = dict[str, Json]
type Collection = Literal["frozenset", "tuple"]

SKILL_DIR: Final[Path] = Path(__file__).resolve().parents[1]
SCHEMA_FILE: Final[Path] = SKILL_DIR / "schemas" / "infra-vocabulary.schema.json"
OUTPUT_FILE: Final[Path] = SKILL_DIR / "scripts" / "infra_vocabulary.py"
CARRIER_DEF: Final[str] = "carrierKey"
VALUE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9-]+$")

#: Schema property -> (Literal alias of one value, collection the public INFRA_<KEY> constant takes).
NAMING: Final[dict[str, tuple[str, Collection]]] = {
    "types": ("InfraType", "frozenset"),
    "labels": ("InfraLabel", "tuple"),
}


class SchemaShapeError(ValueError):
    """The infra-vocabulary schema uses a shape this generator does not translate."""


@dataclass(frozen=True)
class Property:
    """One property of the vocabulary object, translated."""

    key: str
    alias: str
    collection: Collection
    values: tuple[str, ...]


@dataclass(frozen=True)
class Model:
    """The translated schema."""

    description: str
    properties: tuple[Property, ...]
    carrier_key: str


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


def _values(key: str, schema: JsonObject) -> tuple[str, ...]:
    where: str = f"properties.{key}"
    if schema.get("type") != "array" or schema.get("uniqueItems") is not True:
        message: str = f"{where}: expected a unique-items array"
        raise SchemaShapeError(message)
    items: JsonObject = _obj(schema.get("items"), f"{where}.items")
    if items.get("type") != "string" or items.get("pattern") != VALUE_PATTERN.pattern:
        message = f"{where}.items: expected strings matching {VALUE_PATTERN.pattern}"
        raise SchemaShapeError(message)
    values: list[str] = _texts(schema.get("const"), f"{where}.const")
    min_items: Json = schema.get("minItems")
    if not isinstance(min_items, int) or isinstance(min_items, bool) or len(values) < min_items:
        message = f"{where}: const has fewer values than minItems"
        raise SchemaShapeError(message)
    if len(set(values)) != len(values):
        message = f"{where}: const repeats a value"
        raise SchemaShapeError(message)
    bad: list[str] = [value for value in values if not VALUE_PATTERN.fullmatch(value)]
    if bad:
        message = f"{where}: const values {bad} do not match {VALUE_PATTERN.pattern}"
        raise SchemaShapeError(message)
    return tuple(values)


def build_model(schema: JsonObject) -> Model:
    """Translate the infra-vocabulary schema.

    Args:
        schema: The decoded schema.

    Returns:
        The translated model.

    Raises:
        SchemaShapeError: The schema uses a shape the generator does not translate.

    """
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        message: str = "the root must be an object with additionalProperties false"
        raise SchemaShapeError(message)
    properties: JsonObject = _obj(schema.get("properties"), "properties")
    required: list[str] = _texts(schema.get("required"), "required")
    if list(properties) != list(NAMING) or sorted(required) != sorted(NAMING):
        message = f"properties and required must both be exactly {list(NAMING)}"
        raise SchemaShapeError(message)
    translated: tuple[Property, ...] = tuple(
        Property(key, NAMING[key][0], NAMING[key][1], _values(key, _obj(raw, f"properties.{key}")))
        for key, raw in properties.items()
    )
    defs: JsonObject = _obj(schema.get("$defs"), "$defs")
    carrier: JsonObject = _obj(defs.get(CARRIER_DEF), f"$defs.{CARRIER_DEF}")
    return Model(
        description=_text(schema.get("description"), "description"),
        properties=translated,
        carrier_key=_text(carrier.get("const"), f"$defs.{CARRIER_DEF}.const"),
    )


def _literal(values: tuple[str, ...]) -> str:
    return "Literal[" + ", ".join(json.dumps(value) for value in values) + "]"


def _tuple(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(json.dumps(value) for value in values) + ("," if len(values) == 1 else "") + ")"


HEADER: Final[str] = '''"""The infrastructure routing vocabulary: the bead types and labels marking an infra Task.

GENERATED by scripts/gen_infra_vocabulary.py from schemas/infra-vocabulary.schema.json. Never edit this
file: change the schema and run ``python3 scripts/gen_infra_vocabulary.py``. Run this module as a
program to print the vocabulary object passed as the ``infraVocabulary`` workflow argument.
"""

import json
import sys
from typing import Final, Literal, TypedDict
'''

FOOTER: Final[str] = '''

def vocabulary() -> InfraVocabulary:
    """Build a fresh copy of the vocabulary object, for passing as a workflow argument.

    Returns:
        The types and labels, in schema order, in new lists the caller may keep.

    """
    return @FIELDS@


INFRA_VOCABULARY: Final[InfraVocabulary] = vocabulary()


if __name__ == "__main__":
    sys.stdout.write(json.dumps(vocabulary()) + "\\n")
'''


def render(schema: JsonObject) -> str:
    """Render the generated module for ``schema``.

    Args:
        schema: The decoded infra-vocabulary schema.

    Returns:
        The module source.

    """
    model: Model = build_model(schema)
    lines: list[str] = [HEADER.rstrip("\n"), ""]
    lines.extend(f"type {prop.alias} = {_literal(prop.values)}" for prop in model.properties)
    lines.append("")
    lines.extend(f'KEY_{prop.key.upper()}: Final = "{prop.key}"' for prop in model.properties)
    lines.extend((f'INFRA_VOCABULARY_ARG: Final = "{model.carrier_key}"', ""))
    for prop in model.properties:
        ordered: str = f"_{prop.key.upper()}"
        public: str = f"INFRA_{prop.key.upper()}"
        lines.append(f"{ordered}: Final[tuple[{prop.alias}, ...]] = {_tuple(prop.values)}")
        if prop.collection == "frozenset":
            lines.append(f"{public}: Final[frozenset[{prop.alias}]] = frozenset({ordered})")
        else:
            lines.append(f"{public}: Final[tuple[{prop.alias}, ...]] = {ordered}")
    summary: str = model.description.partition(". ")[0].rstrip(".")
    lines.extend(["", "", "class InfraVocabulary(TypedDict):", f'    """{summary}."""', ""])
    lines.extend(f"    {prop.key}: list[{prop.alias}]" for prop in model.properties)
    fields: str = ", ".join(f'"{prop.key}": list(_{prop.key.upper()})' for prop in model.properties)
    lines.append(FOOTER.replace("@FIELDS@", "{" + fields + "}").rstrip("\n"))
    return "\n".join(lines) + "\n"


def load_schema() -> JsonObject:
    """Read the infra-vocabulary schema.

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


def main() -> int:
    """Write the generated module from the schema.

    Returns:
        0 once the module is written or already current.

    """
    text: str = render(load_schema())
    current: str = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.is_file() else ""
    if current != text:
        OUTPUT_FILE.write_text(text, encoding="utf-8")
    sys.stdout.write(f"wrote {OUTPUT_FILE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
