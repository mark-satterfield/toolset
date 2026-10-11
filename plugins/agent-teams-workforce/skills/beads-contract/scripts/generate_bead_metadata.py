#!/usr/bin/env python3
"""Generate bead_metadata.py from schemas/bead-metadata.schema.json.

The schema is the one definition of the pipeline's bead metadata keys, their value
vocabularies, the build-contract projection and the content fingerprint fields. This
script renders the typed Python module mypy and every Python producer and consumer use.

Usage:
  generate_bead_metadata.py           Write scripts/bead_metadata.py.
  generate_bead_metadata.py --check   Exit 1 when scripts/bead_metadata.py is stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SCHEMA_PATH: Final[Path] = SCRIPTS_DIR.parent / "schemas" / "bead-metadata.schema.json"
MODULE_PATH: Final[Path] = SCRIPTS_DIR / "bead_metadata.py"

type SetKind = Literal["tuple", "frozenset"]
type ReferenceKind = Literal["tuple", "str"]

_KINDS_TO_TYPE: Final[dict[str, str]] = {
    "text": "str",
    "list": "list[str]",
    "list-or-unknown": "list[str] | None",
    "object-or-unknown": "JsonObject | None",
}
_JSON_TO_TYPE: Final[dict[str, str]] = {"string": "str", "boolean": "bool", "integer": "int"}
_DOC_WIDTH: Final[int] = 110


class SchemaError(ValueError):
    """The schema does not have the shape this generator renders."""


@dataclass(frozen=True)
class Constant:
    """One named scalar constant."""

    name: str
    value: str | int
    doc: str


@dataclass(frozen=True)
class FieldSet:
    """One named collection of record field names."""

    name: str
    kind: SetKind
    values: tuple[str, ...]
    doc: str


@dataclass(frozen=True)
class Reference:
    """A named reference to contract argument names."""

    name: str
    kind: ReferenceKind
    doc: str


@dataclass(frozen=True)
class Vocabulary:
    """One value vocabulary: a Literal alias, named constants and named subsets."""

    literal: str
    tuple_name: str
    constants: tuple[tuple[str, str], ...]
    extra: tuple[tuple[str, str], ...]
    subsets: tuple[tuple[str, tuple[str, ...]], ...]
    doc: str


@dataclass(frozen=True)
class ContractField:
    """One build-contract entry of a metadata key."""

    argument: str
    kind: str
    reference: str
    hashed_when_present: bool


@dataclass(frozen=True)
class Key:
    """One metadata key."""

    key: str
    groups: tuple[str, ...]
    aliases: tuple[str, ...]
    contract: ContractField | None
    artifact: tuple[str, str] | None
    doc: str


@dataclass(frozen=True)
class TypedDictSpec:
    """A TypedDict rendered from a schema object definition."""

    name: str
    fields: tuple[tuple[str, str], ...]
    doc: str


@dataclass(frozen=True)
class Schema:
    """The parsed schema, in the shape the renderer takes."""

    digest: str
    groups: tuple[tuple[str, str], ...]
    constants: tuple[Constant, ...]
    field_sets: tuple[FieldSet, ...]
    references: tuple[Reference, ...]
    artifact_kinds: tuple[str, ...]
    artifact_fields: tuple[str, ...]
    spec_aspects: tuple[tuple[str, str], ...]
    vocabularies: tuple[Vocabulary, ...]
    typeddicts: tuple[TypedDictSpec, ...]
    keys: tuple[Key, ...]


def _obj(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        msg: str = f"{where}: expected an object"
        raise SchemaError(msg)
    result: dict[str, object] = {}
    item_key: object
    item_value: object
    for item_key, item_value in value.items():
        if not isinstance(item_key, str):
            msg = f"{where}: non-string key"
            raise SchemaError(msg)
        result[item_key] = item_value
    return result


def _list(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        msg: str = f"{where}: expected an array"
        raise SchemaError(msg)
    items: list[object] = list(value)
    return items


def _str(value: object, where: str) -> str:
    if not isinstance(value, str):
        msg: str = f"{where}: expected a string"
        raise SchemaError(msg)
    return value


def _strs(value: object, where: str) -> tuple[str, ...]:
    return tuple(_str(item, where) for item in _list(value, where))


def _pair(value: object, where: str) -> tuple[str, str]:
    match _strs(value, where):
        case (name, item):
            return name, item
        case _:
            msg: str = f"{where}: expected a [name, value] pair"
            raise SchemaError(msg)


def _set_kind(value: str, where: str) -> SetKind:
    if value == "tuple":
        return "tuple"
    if value == "frozenset":
        return "frozenset"
    msg: str = f"{where}: kind must be tuple or frozenset"
    raise SchemaError(msg)


def _reference_kind(value: str, where: str) -> ReferenceKind:
    if value == "tuple":
        return "tuple"
    if value == "str":
        return "str"
    msg: str = f"{where}: kind must be tuple or str"
    raise SchemaError(msg)


def _vocabulary(name: str, definition: dict[str, object]) -> Vocabulary:
    where: str = f"$defs.{name}"
    python: dict[str, object] = _obj(definition["x-python"], where)
    enum: tuple[str, ...] = _strs(definition.get("enum"), where)
    constants: tuple[tuple[str, str], ...] = tuple(_pair(item, where) for item in _list(python["constants"], where))
    if tuple(value for _, value in constants) != enum:
        msg: str = f"{where}: x-python constants must name every enum value, in order"
        raise SchemaError(msg)
    subsets: list[tuple[str, tuple[str, ...]]] = []
    for item in _list(python.get("subsets", []), where):
        parts: list[object] = _list(item, where)
        members: tuple[str, ...] = _strs(parts[1], where)
        if not set(members) <= set(enum):
            msg = f"{where}: subset {parts[0]!r} names a value outside the enum"
            raise SchemaError(msg)
        subsets.append((_str(parts[0], where), members))
    return Vocabulary(
        literal=_str(python["literal"], where),
        tuple_name=_str(python["tuple"], where),
        constants=constants,
        extra=tuple(_pair(item, where) for item in _list(python.get("extra", []), where)),
        subsets=tuple(subsets),
        doc=_str(definition.get("description", ""), where),
    )


def _field_type(definition: dict[str, object], where: str) -> str:
    kind: str = _str(definition.get("type"), where)
    if kind == "array":
        item: dict[str, object] = _obj(definition.get("items"), where)
        return f"list[{_JSON_TO_TYPE[_str(item.get('type'), where)]}]"
    if kind not in _JSON_TO_TYPE:
        msg: str = f"{where}: unsupported type {kind!r}"
        raise SchemaError(msg)
    return _JSON_TO_TYPE[kind]


def _typeddict(name: str, definition: dict[str, object]) -> TypedDictSpec:
    where: str = f"$defs.{name}"
    python: dict[str, object] = _obj(definition["x-python"], where)
    properties: dict[str, object] = _obj(definition.get("properties"), where)
    required: tuple[str, ...] = _strs(definition.get("required", []), where)
    if set(required) != set(properties):
        msg: str = f"{where}: every TypedDict field must be required"
        raise SchemaError(msg)
    return TypedDictSpec(
        name=_str(python["typeddict"], where),
        fields=tuple(
            (field, _field_type(_obj(spec, f"{where}.{field}"), f"{where}.{field}"))
            for field, spec in properties.items()
        ),
        doc=_str(definition.get("description", ""), where),
    )


def _key(key: str, definition: dict[str, object]) -> Key:
    where: str = f"properties.{key}"
    contract: ContractField | None = None
    if "x-contract" in definition:
        spec: dict[str, object] = _obj(definition["x-contract"], where)
        kind: str = _str(spec["kind"], where)
        if kind not in _KINDS_TO_TYPE:
            msg: str = f"{where}: unknown contract kind {kind!r}"
            raise SchemaError(msg)
        hashed: object = spec.get("hashedWhenPresent", False)
        if not isinstance(hashed, bool):
            msg = f"{where}: hashedWhenPresent must be a boolean"
            raise SchemaError(msg)
        contract = ContractField(
            argument=_str(spec["argument"], where),
            kind=kind,
            reference=_str(spec.get("reference", ""), where),
            hashed_when_present=hashed,
        )
    artifact: tuple[str, str] | None = _pair(definition["x-artifact"], where) if "x-artifact" in definition else None
    return Key(
        key=key,
        groups=_strs(definition.get("x-groups", []), where),
        aliases=_strs(definition.get("x-aliases", []), where),
        contract=contract,
        artifact=artifact,
        doc=_str(definition.get("description", ""), where),
    )


def _definitions(definitions: dict[str, object]) -> tuple[tuple[Vocabulary, ...], tuple[TypedDictSpec, ...]]:
    vocabularies: list[Vocabulary] = []
    typeddicts: list[TypedDictSpec] = []
    name: str
    raw: object
    for name, raw in definitions.items():
        definition: dict[str, object] = _obj(raw, f"$defs.{name}")
        if "x-python" not in definition:
            continue
        python: dict[str, object] = _obj(definition["x-python"], f"$defs.{name}")
        if "typeddict" in python:
            typeddicts.append(_typeddict(name, definition))
        else:
            vocabularies.append(_vocabulary(name, definition))
    return tuple(vocabularies), tuple(typeddicts)


def parse_schema(text: str) -> Schema:
    """Parse the schema text into the renderer's typed shape.

    Args:
        text: The schema file's text.

    Returns:
        The parsed schema.

    Raises:
        TypeError: An argument violates the declared input contract.
        SchemaError: The schema does not have the shape this generator renders.

    """
    if not isinstance(text, str):
        argument_error: str = "parse_schema: text must be a string"
        raise TypeError(argument_error)
    root: dict[str, object] = _obj(json.loads(text), "schema")
    groups: tuple[tuple[str, str], ...] = tuple(
        (
            _str(_obj(item, "x-key-groups")["name"], "x-key-groups"),
            _str(_obj(item, "x-key-groups")["doc"], "x-key-groups"),
        )
        for item in _list(root["x-key-groups"], "x-key-groups")
    )
    constants: list[Constant] = []
    for item in _list(root["x-constants"], "x-constants"):
        entry: dict[str, object] = _obj(item, "x-constants")
        value: object = entry["value"]
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            msg: str = "x-constants: a value must be a string or an integer"
            raise SchemaError(msg)
        constants.append(Constant(_str(entry["name"], "x-constants"), value, _str(entry["doc"], "x-constants")))
    field_sets: tuple[FieldSet, ...] = tuple(
        FieldSet(
            name=_str(_obj(item, "x-field-sets")["name"], "x-field-sets"),
            kind=_set_kind(_str(_obj(item, "x-field-sets")["kind"], "x-field-sets"), "x-field-sets"),
            values=_strs(_obj(item, "x-field-sets")["values"], "x-field-sets"),
            doc=_str(_obj(item, "x-field-sets")["doc"], "x-field-sets"),
        )
        for item in _list(root["x-field-sets"], "x-field-sets")
    )
    references: tuple[Reference, ...] = tuple(
        Reference(
            name=_str(_obj(item, "x-references")["name"], "x-references"),
            kind=_reference_kind(_str(_obj(item, "x-references")["kind"], "x-references"), "x-references"),
            doc=_str(_obj(item, "x-references")["doc"], "x-references"),
        )
        for item in _list(root["x-references"], "x-references")
    )
    artifacts: dict[str, object] = _obj(root["x-artifacts"], "x-artifacts")
    vocabularies: tuple[Vocabulary, ...]
    typeddicts: tuple[TypedDictSpec, ...]
    vocabularies, typeddicts = _definitions(_obj(root["$defs"], "$defs"))
    keys: tuple[Key, ...] = tuple(
        _key(key, _obj(raw_key, f"properties.{key}")) for key, raw_key in _obj(root["properties"], "properties").items()
    )
    group_names: set[str] = {group for group, _ in groups}
    for key in keys:
        if not key.groups or not set(key.groups) <= group_names:
            msg = f"properties.{key.key}: x-groups must name declared x-key-groups"
            raise SchemaError(msg)
    return Schema(
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        groups=groups,
        constants=tuple(constants),
        field_sets=field_sets,
        references=references,
        artifact_kinds=_strs(artifacts["kinds"], "x-artifacts.kinds"),
        artifact_fields=_strs(artifacts["fields"], "x-artifacts.fields"),
        spec_aspects=tuple(_pair(item, "x-artifacts.specAspects") for item in _list(artifacts["specAspects"], "x")),
        vocabularies=tuple(vocabularies),
        typeddicts=tuple(typeddicts),
        keys=keys,
    )


def constant_name(prefix: str, name: str) -> str:
    """Return the upper-snake constant name for a key or argument name.

    Args:
        prefix: The prefix, such as KEY_ or ARG_.
        name: A snake_case or camelCase name.

    Returns:
        The constant name.

    """
    snake: str = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return prefix + re.sub(r"[^A-Za-z0-9]+", "_", snake).upper()


def _doc(lines: list[str], doc: str) -> None:
    lines.extend(f"#: {line}" for line in textwrap.wrap(doc, width=_DOC_WIDTH))


def _collection(lines: list[str], head: str, items: list[str], opener: str, closer: str) -> None:
    lines.append(f"{head}{opener}")
    lines.extend(f"    {item}," for item in items)
    lines.append(closer)


def _render_vocabulary(lines: list[str], vocabulary: Vocabulary) -> None:
    lines.append("")
    _doc(lines, vocabulary.doc)
    literal_values: str = ", ".join(json.dumps(value) for _, value in vocabulary.constants)
    lines.append(f"type {vocabulary.literal} = Literal[{literal_values}]")
    by_value: dict[str, str] = {}
    for constant, value in vocabulary.constants:
        by_value[value] = constant
        lines.append(f"{constant}: Final[{vocabulary.literal}] = {json.dumps(value)}")
    _collection(
        lines,
        f"{vocabulary.tuple_name}: Final[tuple[{vocabulary.literal}, ...]] = ",
        [constant for constant, _ in vocabulary.constants],
        "(",
        ")",
    )
    for constant, value in vocabulary.extra:
        lines.append(f"{constant}: Final[str] = {json.dumps(value)}")
    for subset, members in vocabulary.subsets:
        _collection(
            lines,
            f"{subset}: Final[frozenset[{vocabulary.literal}]] = frozenset(",
            [by_value[member] for member in members],
            "{",
            "})",
        )


def _contract_keys(schema: Schema) -> list[tuple[Key, ContractField]]:
    return [(key, key.contract) for key in schema.keys if key.contract is not None]


def _render_head(lines: list[str], schema: Schema) -> None:
    lines.extend([
        '"""Pipeline-owned bead metadata: keys, value vocabularies and the build-contract projection.',
        "",
        "GENERATED by generate_bead_metadata.py from schemas/bead-metadata.schema.json. Do not edit:",
        "change the schema and regenerate. check_bead_metadata_generated.py fails when this file is stale.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from types import MappingProxyType",
        "from typing import TYPE_CHECKING, Final, Literal, TypedDict",
        "",
        "if TYPE_CHECKING:",
        "    from collections.abc import Mapping",
        "",
        "type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None",
        "type JsonObject = dict[str, JsonValue]",
        "",
        "#: SHA-256 of the schema text this module was generated from.",
        f"SCHEMA_SHA256: Final[str] = {json.dumps(schema.digest)}",
        "",
    ])
    for constant in schema.constants:
        _doc(lines, constant.doc)
        kind: str = "int" if isinstance(constant.value, int) else "str"
        lines.append(f"{constant.name}: Final[{kind}] = {json.dumps(constant.value)}")
    for vocabulary in schema.vocabularies:
        _render_vocabulary(lines, vocabulary)


def _render_keys(lines: list[str], schema: Schema) -> None:
    lines.extend(("", "# Metadata keys."))
    for key in schema.keys:
        _doc(lines, key.doc)
        lines.append(f"{constant_name('KEY_', key.key)}: Final[str] = {json.dumps(key.key)}")
        lines.extend(f"{alias}: Final[str] = {constant_name('KEY_', key.key)}" for alias in key.aliases)


def _render_references(lines: list[str], schema: Schema) -> None:
    for reference in schema.references:
        members: list[str] = [
            constant_name("ARG_", field.argument)
            for _, field in _contract_keys(schema)
            if field.reference == reference.name
        ]
        _doc(lines, reference.doc)
        if reference.kind == "tuple":
            _collection(lines, f"{reference.name}: Final[tuple[str, ...]] = ", members, "(", ")")
            continue
        if len(members) != 1:
            msg: str = f"{reference.name}: a str reference names exactly one contract key"
            raise SchemaError(msg)
        lines.append(f"{reference.name}: Final[str] = {members[0]}")


def _render_contract(lines: list[str], schema: Schema) -> None:
    contract_keys: list[tuple[Key, ContractField]] = _contract_keys(schema)
    lines.extend(("", "# Build-contract argument names."))
    lines.extend(
        f"{constant_name('ARG_', field.argument)}: Final[str] = {json.dumps(field.argument)}"
        for _, field in contract_keys
    )
    lines.extend((
        "",
        "#: The build contract a Task carries: metadata key -> (argument name, kind). Lists and objects",
        "#: are stored as compact JSON strings.",
    ))
    _collection(
        lines,
        "CONTRACT_SCHEMA: Final[tuple[tuple[str, str, ContractKind], ...]] = ",
        [
            f"({constant_name('KEY_', key.key)}, {constant_name('ARG_', field.argument)}, "
            f"{constant_name('KIND_', field.kind)})"
            for key, field in contract_keys
        ],
        "(",
        ")",
    )
    lines.append("#: Contract keys the readiness fingerprint covers only on a bead that carries them.")
    _collection(
        lines,
        "CONTRACT_HASHED_WHEN_PRESENT: Final[frozenset[str]] = frozenset(",
        [constant_name("KEY_", key.key) for key, field in contract_keys if field.hashed_when_present],
        "{",
        "})",
    )
    _render_references(lines, schema)


def _render_field_sets(lines: list[str], schema: Schema) -> None:
    lines.append("")
    for field_set in schema.field_sets:
        _doc(lines, field_set.doc)
        quoted: list[str] = [json.dumps(value) for value in field_set.values]
        if field_set.kind == "tuple":
            _collection(lines, f"{field_set.name}: Final[tuple[str, ...]] = ", quoted, "(", ")")
        else:
            _collection(lines, f"{field_set.name}: Final[frozenset[str]] = frozenset(", quoted, "{", "})")


_ARTIFACT_KEY_FUNCTION: Final[tuple[str, ...]] = (
    "",
    "",
    "def artifact_key(kind: ArtifactKind, field: ArtifactField) -> str:",
    '    """Return the metadata key recording one field of one authored artifact.',
    "",
    "    Args:",
    "        kind: The artifact kind.",
    "        field: The recorded field.",
    "",
    "    Returns:",
    "        The metadata key.",
    "",
    "    Raises:",
    "        TypeError: An argument is not a string.",
    "        ValueError: The kind does not record that field.",
    "",
    '    """',
    "    if not isinstance(kind, str) or not isinstance(field, str):",
    '        argument_error: str = "artifact_key: kind and field must be strings"',
    "        raise TypeError(argument_error)",
    "    key: str | None = _ARTIFACT_KEY_TABLE.get((kind, field))",
    "    if key is None:",
    '        message: str = f"artifact kind {kind!r} records no {field!r} key"',
    "        raise ValueError(message)",
    "    return key",
    "",
)


def _render_artifacts(lines: list[str], schema: Schema) -> None:
    lines.extend(("", "# Artifact keys."))
    kinds: str = ", ".join(json.dumps(kind) for kind in schema.artifact_kinds)
    fields: str = ", ".join(json.dumps(field) for field in schema.artifact_fields)
    lines.extend((f"type ArtifactKind = Literal[{kinds}]", f"type ArtifactField = Literal[{fields}]"))
    _collection(
        lines,
        "ARTIFACT_KINDS: Final[tuple[ArtifactKind, ...]] = ",
        [json.dumps(kind) for kind in schema.artifact_kinds],
        "(",
        ")",
    )
    _collection(
        lines,
        "ARTIFACT_FIELDS: Final[tuple[ArtifactField, ...]] = ",
        [json.dumps(field) for field in schema.artifact_fields],
        "(",
        ")",
    )
    table: list[str] = []
    for key in schema.keys:
        if key.artifact is None:
            continue
        kind_name, field_name = key.artifact
        if kind_name not in schema.artifact_kinds or field_name not in schema.artifact_fields:
            msg: str = f"properties.{key.key}: x-artifact names an undeclared kind or field"
            raise SchemaError(msg)
        table.append(f"({json.dumps(kind_name)}, {json.dumps(field_name)}): {constant_name('KEY_', key.key)}")
    _collection(
        lines,
        "_ARTIFACT_KEY_TABLE: Final[Mapping[tuple[ArtifactKind, ArtifactField], str]] = MappingProxyType(",
        table,
        "{",
        "})",
    )
    lines.append("#: The spec-file aspect a Spec document names -> the artifact kind its keys use.")
    _collection(
        lines,
        "SPEC_ASPECT_KIND: Final[Mapping[str, ArtifactKind]] = MappingProxyType(",
        [f"{json.dumps(aspect)}: {json.dumps(kind)}" for aspect, kind in schema.spec_aspects],
        "{",
        "})",
    )
    lines.extend(_ARTIFACT_KEY_FUNCTION)


def _render_groups(lines: list[str], schema: Schema) -> None:
    lines.extend(("", "# Key groups."))
    for group, doc in schema.groups:
        _doc(lines, doc)
        _collection(
            lines,
            f"{group}: Final[tuple[str, ...]] = ",
            [constant_name("KEY_", key.key) for key in schema.keys if group in key.groups],
            "(",
            ")",
        )
    lines.append("#: Every metadata key this pipeline writes; `metadata get` lists other keys as unrecognized.")
    _collection(
        lines,
        "KNOWN_KEYS: Final[frozenset[str]] = frozenset(",
        [f"*{group}" for group, _ in schema.groups],
        "(",
        "))",
    )


def _render_typeddicts(lines: list[str], schema: Schema) -> None:
    lines.extend((
        "",
        "",
        "class BeadMetadata(TypedDict, total=False):",
        '    """Every pipeline-owned metadata key; every value is stored as a string."""',
        "",
    ))
    lines.extend(f"    {key.key}: str" for key in schema.keys)
    lines.extend((
        "",
        "",
        "class BuildContract(TypedDict, total=False):",
        '    """The build contract read_contract projects, keyed by argument name."""',
        "",
    ))
    lines.extend(f"    {field.argument}: {_KINDS_TO_TYPE[field.kind]}" for _, field in _contract_keys(schema))
    for typeddict in schema.typeddicts:
        lines.extend(("", "", f"class {typeddict.name}(TypedDict):", f'    """{typeddict.doc}"""', ""))
        lines.extend(f"    {field}: {annotation}" for field, annotation in typeddict.fields)


def render(schema: Schema) -> str:
    """Render the typed module text for a parsed schema.

    Args:
        schema: The parsed schema.

    Returns:
        The module text, already in `ruff format` style.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(schema, Schema):
        argument_error: str = "render: schema must be a parsed Schema"
        raise TypeError(argument_error)
    lines: list[str] = []
    _render_head(lines, schema)
    _render_keys(lines, schema)
    _render_contract(lines, schema)
    _render_field_sets(lines, schema)
    _render_artifacts(lines, schema)
    _render_groups(lines, schema)
    _render_typeddicts(lines, schema)
    return "\n".join(lines) + "\n"


def generated_text() -> str:
    """Render the module text from the schema file on disk.

    Returns:
        The module text.

    """
    return render(parse_schema(SCHEMA_PATH.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    """Write the generated module, or check it is current.

    Args:
        argv: Command-line arguments, or None for sys.argv.

    Returns:
        0 when written or current; 1 when --check finds the module stale.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when bead_metadata.py is stale")
    check: bool = bool(parser.parse_args(argv).check)
    text: str = generated_text()
    if check:
        current: str = MODULE_PATH.read_text(encoding="utf-8") if MODULE_PATH.is_file() else ""
        if current != text:
            sys.stderr.write(f"{MODULE_PATH} is stale: run {Path(__file__).name} to regenerate it\n")
            return 1
        sys.stdout.write(f"{MODULE_PATH.name} is current\n")
        return 0
    MODULE_PATH.write_text(text, encoding="utf-8")
    sys.stdout.write(f"wrote {MODULE_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
