#!/usr/bin/env python3
"""Generate driver_surface_types.py from schemas/driver-surface.schema.json.

The schema is the one definition of the driver module surface the plugin orchestrator
imports, the ATW_* environment, and the Claude CLI rate-limit event. This script renders the
typed module mypy and every Python producer and consumer use.

Usage:
  generate_types.py           Write scripts/driver_surface_types.py.
  generate_types.py --check   Exit 1 when scripts/driver_surface_types.py is stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SCHEMA_PATH: Final[Path] = SCRIPTS_DIR.parent / "schemas" / "driver-surface.schema.json"
MODULE_PATH: Final[Path] = SCRIPTS_DIR / "driver_surface_types.py"

_JSON_TO_PYTHON: Final[dict[str, str]] = {"string": "str", "number": "float", "integer": "int", "boolean": "bool"}
_DOC_WIDTH: Final[int] = 100
_LINE_WIDTH: Final[int] = 120

type MemberKind = Literal["attribute", "method"]


class SchemaError(ValueError):
    """The schema does not have the shape this generator renders."""


@dataclass(frozen=True)
class Member:
    """One attribute or method of a driver module protocol."""

    name: str
    kind: MemberKind
    python: str
    params: tuple[tuple[str, str], ...]
    doc: str


@dataclass(frozen=True)
class DriverModule:
    """One driver module the plugin imports and the protocol describing it."""

    module: str
    constant: str
    protocol: str
    doc: str
    members: tuple[Member, ...]


@dataclass(frozen=True)
class Field:
    """One TypedDict field."""

    name: str
    annotation: str
    required: bool
    doc: str


@dataclass(frozen=True)
class Constant:
    """One named module-level constant."""

    name: str
    annotation: str
    value: str
    doc: str


@dataclass(frozen=True)
class Enumeration:
    """A string vocabulary: a Literal alias, its collection and named members."""

    literal: str
    collection: str
    collection_kind: Literal["tuple", "frozenset"]
    values: tuple[str, ...]
    named: tuple[tuple[str, str], ...]
    doc: str


@dataclass(frozen=True)
class Record:
    """A TypedDict rendered from an object definition."""

    name: str
    fields: tuple[Field, ...]
    doc: str


@dataclass(frozen=True)
class Schema:
    """The parsed schema, in the shape the renderer takes."""

    digest: str
    dir_parts: tuple[str, ...]
    dir_doc: str
    modules: tuple[DriverModule, ...]
    constants: tuple[Constant, ...]
    groups: tuple[tuple[str, tuple[str, ...]], ...]
    enumerations: tuple[Enumeration, ...]
    records: tuple[Record, ...]


def _obj(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        msg: str = f"{where}: expected an object"
        raise SchemaError(msg)
    result: dict[str, object] = {}
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            msg = f"{where}: non-string key"
            raise SchemaError(msg)
        result[key] = item
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


def _member(raw: object, where: str) -> Member:
    entry: dict[str, object] = _obj(raw, where)
    kind_text: str = _str(entry["kind"], where)
    params: list[tuple[str, str]] = []
    kind: MemberKind
    if kind_text == "attribute":
        kind = "attribute"
        python: str = _str(entry["python"], where)
    elif kind_text == "method":
        kind = "method"
        python = _str(entry["returns"], where)
        for item in _list(entry["params"], where):
            match _strs(item, where):
                case (param_name, param_type):
                    params.append((param_name, param_type))
                case _:
                    msg: str = f"{where}: a parameter is a [name, type] pair"
                    raise SchemaError(msg)
    else:
        msg = f"{where}: kind must be attribute or method"
        raise SchemaError(msg)
    return Member(_str(entry["name"], where), kind, python, tuple(params), _str(entry["doc"], where))


def _modules(root: dict[str, object]) -> tuple[tuple[str, ...], str, tuple[DriverModule, ...]]:
    driver: dict[str, object] = _obj(root["x-driver"], "x-driver")
    modules: list[DriverModule] = []
    for index, raw in enumerate(_list(driver["modules"], "x-driver.modules")):
        where: str = f"x-driver.modules[{index}]"
        entry: dict[str, object] = _obj(raw, where)
        modules.append(
            DriverModule(
                module=_str(entry["module"], where),
                constant=_str(entry["constant"], where),
                protocol=_str(entry["protocol"], where),
                doc=_str(entry["doc"], where),
                members=tuple(_member(item, f"{where}.members") for item in _list(entry["members"], where)),
            ),
        )
    return _strs(driver["dirParts"], "x-driver.dirParts"), _str(driver["dirDoc"], "x-driver.dirDoc"), tuple(modules)


def _annotation(spec: dict[str, object], where: str) -> str:
    if "$ref" in spec:
        return _str(spec["$ref"], where).rsplit("/", 1)[-1]
    if "const" in spec and spec.get("type") == "string":
        return f"Literal[{json.dumps(_str(spec['const'], where))}]"
    kind: str = _str(spec.get("type"), where)
    if kind == "object":
        values: dict[str, object] = _obj(spec.get("additionalProperties"), where)
        return f"dict[str, {_annotation(values, where)}]"
    if kind not in _JSON_TO_PYTHON:
        msg: str = f"{where}: unsupported type {kind!r}"
        raise SchemaError(msg)
    return _JSON_TO_PYTHON[kind]


def _record_constants(name: str, properties: dict[str, object], constants: list[Constant]) -> None:
    for field_name, raw in properties.items():
        where: str = f"$defs.{name}.{field_name}"
        spec: dict[str, object] = _obj(raw, where)
        doc: str = _str(spec.get("description", ""), where)
        if "x-constant" in spec:
            constants.append(Constant(_str(spec["x-constant"], where), "str", json.dumps(field_name), doc))
        if "x-value-constant" in spec:
            value: str = _str(spec["const"], where)
            constants.append(Constant(_str(spec["x-value-constant"], where), "str", json.dumps(value), doc))
        if "x-key-constant" in spec:
            constants.append(Constant(_str(spec["x-key-constant"], where), "str", json.dumps(field_name), doc))
        if "x-default-constant" in spec:
            default: str = _str(spec["default"], where)
            constants.append(Constant(_str(spec["x-default-constant"], where), "str", json.dumps(default), doc))
        if "x-const-mapping" in spec:
            key_constant: str = _str(spec["x-constant"], where)
            mapping: str = f"MappingProxyType({{{key_constant}: {json.dumps(_str(spec['const'], where))}}})"
            constants.append(Constant(_str(spec["x-const-mapping"], where), "Mapping[str, str]", mapping, doc))
        if "x-values" in spec:
            for constant_name, constant_value in _obj(spec["x-values"], where).items():
                constants.append(Constant(constant_name, "str", json.dumps(_str(constant_value, where)), doc))


def _record(
    name: str,
    definition: dict[str, object],
    constants: list[Constant],
    groups: dict[str, list[str]],
) -> Record:
    where: str = f"$defs.{name}"
    python: dict[str, object] = _obj(definition["x-python"], where)
    properties: dict[str, object] = _obj(definition["properties"], where)
    required: set[str] = set(_strs(definition.get("required", []), where))
    fields: list[Field] = []
    for field_name, raw in properties.items():
        spec: dict[str, object] = _obj(raw, f"{where}.{field_name}")
        fields.append(
            Field(
                field_name,
                _annotation(spec, f"{where}.{field_name}"),
                field_name in required,
                _str(spec.get("description", ""), where),
            ),
        )
        if "x-group" in spec:
            groups.setdefault(_str(spec["x-group"], where), []).append(_str(spec["x-constant"], where))
    if not required <= set(properties):
        msg: str = f"{where}: required names an undeclared property"
        raise SchemaError(msg)
    _record_constants(name, properties, constants)
    return Record(_str(python["typeddict"], where), tuple(fields), _str(definition.get("description", ""), where))


def _enumeration(name: str, definition: dict[str, object]) -> Enumeration:
    where: str = f"$defs.{name}"
    python: dict[str, object] = _obj(definition["x-python"], where)
    values: tuple[str, ...] = _strs(definition["enum"], where)
    if len(set(values)) != len(values):
        msg: str = f"{where}: enum values must be distinct"
        raise SchemaError(msg)
    named: dict[str, object] = _obj(python.get("constants", {}), where)
    if not set(named) <= set(values):
        msg = f"{where}: x-python constants name a value outside the enum"
        raise SchemaError(msg)
    if "tuple" in python:
        return Enumeration(
            _str(python["literal"], where),
            _str(python["tuple"], where),
            "tuple",
            values,
            tuple((_str(constant, where), value) for value, constant in named.items()),
            _str(definition.get("description", ""), where),
        )
    return Enumeration(
        _str(python["literal"], where),
        _str(python["frozenset"], where),
        "frozenset",
        values,
        tuple((_str(constant, where), value) for value, constant in named.items()),
        _str(definition.get("description", ""), where),
    )


def _scalar(name: str, definition: dict[str, object]) -> Constant:
    where: str = f"$defs.{name}"
    python: dict[str, object] = _obj(definition["x-python"], where)
    annotation: str = _str(python["type"], where)
    value: object = definition["const"]
    if annotation == "float" and isinstance(value, (int, float)) and not isinstance(value, bool):
        rendered: str = repr(float(value))
    elif annotation == "int" and isinstance(value, int) and not isinstance(value, bool):
        rendered = _str(python.get("render", str(value)), where)
        if int(rendered, 0) != value:
            msg: str = f"{where}: render does not equal const"
            raise SchemaError(msg)
    else:
        msg = f"{where}: const does not match its x-python type"
        raise SchemaError(msg)
    doc: str = _str(definition.get("description", ""), where)
    return Constant(_str(python["constant"], where), annotation, rendered, doc)


def parse_schema(text: str) -> Schema:
    """Parse the schema text into the renderer's typed shape.

    Args:
        text: The schema file's text.

    Returns:
        The parsed schema.

    Raises:
        TypeError: The text is not a string.
        SchemaError: The schema does not have the shape this generator renders.

    """
    if not isinstance(text, str):
        argument_error: str = "parse_schema: text must be a string"
        raise TypeError(argument_error)
    root: dict[str, object] = _obj(json.loads(text), "schema")
    dir_parts: tuple[str, ...]
    dir_doc: str
    modules: tuple[DriverModule, ...]
    dir_parts, dir_doc, modules = _modules(root)
    constants: list[Constant] = []
    groups: dict[str, list[str]] = {}
    enumerations: list[Enumeration] = []
    records: list[Record] = []
    for name, raw in _obj(root["$defs"], "$defs").items():
        definition: dict[str, object] = _obj(raw, f"$defs.{name}")
        python: dict[str, object] = _obj(definition.get("x-python", {}), f"$defs.{name}")
        if "typeddict" in python:
            records.append(_record(name, definition, constants, groups))
        elif "literal" in python:
            enumerations.append(_enumeration(name, definition))
        elif "constant" in python:
            constants.append(_scalar(name, definition))
        else:
            msg: str = f"$defs.{name}: x-python names no typeddict, literal or constant"
            raise SchemaError(msg)
    names: list[str] = [constant.name for constant in constants]
    if len(set(names)) != len(names):
        msg = "schema: two constants share a name"
        raise SchemaError(msg)
    return Schema(
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        dir_parts=dir_parts,
        dir_doc=dir_doc,
        modules=modules,
        constants=tuple(constants),
        groups=tuple((group, tuple(members)) for group, members in groups.items()),
        enumerations=tuple(enumerations),
        records=tuple(records),
    )


def _doc(lines: list[str], doc: str) -> None:
    lines.extend(f"#: {line}" for line in textwrap.wrap(doc, width=_DOC_WIDTH))


def _summary(doc: str, where: str) -> str:
    if len(doc) > _DOC_WIDTH or not doc.endswith("."):
        msg: str = f"{where}: a docstring summary is one sentence of at most {_DOC_WIDTH} characters"
        raise SchemaError(msg)
    return doc


def _tuple(items: list[str]) -> str:
    if len(items) == 1:
        return f"({items[0]},)"
    return f"({', '.join(items)})"


def _literal(name: str, values: tuple[str, ...]) -> list[str]:
    quoted: list[str] = [json.dumps(value) for value in values]
    single: str = f"type {name} = Literal[{', '.join(quoted)}]"
    if len(single) <= _LINE_WIDTH:
        return [single]
    return [f"type {name} = Literal[", *(f"    {value}," for value in quoted), "]"]


def _render_head(lines: list[str], schema: Schema) -> None:
    lines.extend([
        '"""Driver module surface, ATW_* environment and Claude CLI rate-limit event.',
        "",
        "GENERATED by generate_types.py from schemas/driver-surface.schema.json. Do not edit: change the",
        "schema and regenerate. check_generated.py fails when this file is stale.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "from pathlib import Path",
        "from types import MappingProxyType",
        "from typing import TYPE_CHECKING, Final, Literal, NotRequired, Protocol, TypedDict, runtime_checkable",
        "",
        "if TYPE_CHECKING:",
        "    from collections.abc import Mapping",
        "",
        "#: SHA-256 of the schema text this module was generated from.",
        f"SCHEMA_SHA256: Final[str] = {json.dumps(schema.digest)}",
        "#: The schema this module was generated from.",
        'SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "schemas" / "driver-surface.schema.json"',
        "",
    ])


def _render_constants(lines: list[str], schema: Schema) -> None:
    for constant in schema.constants:
        _doc(lines, constant.doc)
        lines.append(f"{constant.name}: Final[{constant.annotation}] = {constant.value}")
    for group, members in schema.groups:
        lines.extend((
            f"#: The {group.lower().replace('_', ' ')}, in order.",
            f"{group}: Final[tuple[str, ...]] = {_tuple(list(members))}",
        ))


def _render_enumerations(lines: list[str], schema: Schema) -> None:
    for enumeration in schema.enumerations:
        lines.append("")
        _doc(lines, enumeration.doc)
        quoted: list[str] = [json.dumps(value) for value in enumeration.values]
        lines.extend(_literal(enumeration.literal, enumeration.values))
        for constant, value in enumeration.named:
            lines.append(f"{constant}: Final[{enumeration.literal}] = {json.dumps(value)}")
        if enumeration.collection_kind == "tuple":
            lines.append(f"{enumeration.collection}: Final[tuple[{enumeration.literal}, ...]] = (")
            lines.extend(f"    {value}," for value in quoted)
            lines.append(")")
        else:
            lines.append(f"{enumeration.collection}: Final[frozenset[{enumeration.literal}]] = frozenset({{")
            lines.extend(f"    {value}," for value in quoted)
            lines.append("})")


def _render_driver(lines: list[str], schema: Schema) -> None:
    lines.extend(("", "# Driver modules."))
    _doc(lines, schema.dir_doc)
    parts: str = _tuple([json.dumps(part) for part in schema.dir_parts])
    lines.append(f"DRIVER_DIR_PARTS: Final[tuple[str, ...]] = {parts}")
    lines.extend(_literal("DriverModule", tuple(module.module for module in schema.modules)))
    lines.extend(f"{module.constant}: Final[DriverModule] = {json.dumps(module.module)}" for module in schema.modules)
    lines.extend((
        "#: Driver module -> the attributes the plugin reads from it.",
        "DRIVER_MODULES: Final[Mapping[DriverModule, tuple[str, ...]]] = MappingProxyType({",
    ))
    for module in schema.modules:
        members: str = _tuple([json.dumps(member.name) for member in module.members])
        lines.append(f"    {module.constant}: {members},")
    lines.append("})")
    for module in schema.modules:
        lines.extend((
            "",
            "",
            "@runtime_checkable",
            f"class {module.protocol}(Protocol):",
            f'    """{_summary(module.doc, module.protocol)}"""',
            "",
        ))
        for member in module.members:
            where: str = f"{module.protocol}.{member.name}"
            if member.kind == "attribute":
                lines.extend((f"    {member.name}: {member.python}", f'    """{_summary(member.doc, where)}"""', ""))
                continue
            params: str = "".join(f", {name}: {annotation}" for name, annotation in member.params)
            lines.extend((
                f"    def {member.name}(self{params}) -> {member.python}:",
                f'        """{_summary(member.doc, where)}"""',
                "        ...",
                "",
            ))
        while not lines[-1]:
            lines.pop()


def _render_records(lines: list[str], schema: Schema) -> None:
    for record in schema.records:
        lines.extend(("", "", f"class {record.name}(TypedDict):", f'    """{_summary(record.doc, record.name)}"""', ""))
        for field in record.fields:
            annotation: str = field.annotation if field.required else f"NotRequired[{field.annotation}]"
            lines.append(f"    {field.name}: {annotation}")


_LOAD_SCHEMA: Final[tuple[str, ...]] = (
    "",
    "",
    "def load_schema() -> dict[str, object]:",
    '    """Load the driver-surface JSON Schema this module was generated from.',
    "",
    "    Returns:",
    "        The schema document.",
    "",
    "    Raises:",
    "        TypeError: The file is not a JSON object.",
    "",
    '    """',
    '    document: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))',
    "    if not isinstance(document, dict):",
    '        message: str = "the driver-surface schema is not a JSON object"',
    "        raise TypeError(message)",
    "    return {str(key): value for key, value in document.items()}",
)


def render(schema: Schema) -> str:
    """Render the typed module text for a parsed schema.

    Args:
        schema: The parsed schema.

    Returns:
        The module text.

    Raises:
        TypeError: The argument is not a parsed Schema.

    """
    if not isinstance(schema, Schema):
        argument_error: str = "render: schema must be a parsed Schema"
        raise TypeError(argument_error)
    lines: list[str] = []
    _render_head(lines, schema)
    _render_constants(lines, schema)
    _render_enumerations(lines, schema)
    _render_driver(lines, schema)
    _render_records(lines, schema)
    lines.extend(_LOAD_SCHEMA)
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
    parser.add_argument("--check", action="store_true", help="exit 1 when driver_surface_types.py is stale")
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
