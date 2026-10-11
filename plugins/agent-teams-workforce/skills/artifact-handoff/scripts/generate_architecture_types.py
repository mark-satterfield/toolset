"""Generate architecture_artifacts.py from the architecture schemas, or check that it is current.

The schemas in ../schemas are the one definition of the architecture writer result, the architecture
review result and the two conformance results: architecture-common.schema.json holds the shared
$defs, and architecture-writer, architecture-review, conformance and built-conformance reach them
with $ref. This script follows those references and derives the Python TypedDicts, Literal aliases,
value constants, schema paths and parse_* validators from them. With --check it writes nothing and
exits 1 when the generated module differs from what it would write.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SCHEMAS_DIR: Final[Path] = SCRIPTS_DIR.parent / "schemas"
OUTPUT_PATH: Final[Path] = SCRIPTS_DIR / "architecture_artifacts.py"

COMMON: Final[str] = "architecture-common.schema.json"
WRITER: Final[str] = "architecture-writer.schema.json"
REVIEW: Final[str] = "architecture-review.schema.json"
CONFORMANCE: Final[str] = "conformance.schema.json"
BUILT_CONFORMANCE: Final[str] = "built-conformance.schema.json"

# (path constant, schema file) for every schema the module names.
SCHEMA_FILES: Final[tuple[tuple[str, str], ...]] = (
    ("COMMON_SCHEMA_PATH", COMMON),
    ("WRITER_SCHEMA_PATH", WRITER),
    ("REVIEW_SCHEMA_PATH", REVIEW),
    ("CONFORMANCE_SCHEMA_PATH", CONFORMANCE),
    ("BUILT_CONFORMANCE_SCHEMA_PATH", BUILT_CONFORMANCE),
)
# (TypedDict name, schema file, pointer) for every object the module types.
RECORDS: Final[tuple[tuple[str, str, str], ...]] = (
    ("EvidenceRef", COMMON, "#/$defs/EvidenceRef"),
    ("BusinessConflict", COMMON, "#/$defs/BusinessConflict"),
    ("CoverageRow", COMMON, "#/$defs/CoverageRow"),
    ("CoverageCheck", COMMON, "#/$defs/CoverageCheck"),
    ("ConformanceFinding", COMMON, "#/$defs/ConformanceFinding"),
    ("WriterClaim", WRITER, "#/$defs/WriterClaim"),
    ("FindingAnswer", WRITER, "#/$defs/FindingAnswer"),
    ("RepairAnswer", WRITER, "#/$defs/RepairAnswer"),
    ("WriterResult", WRITER, "#"),
    ("ReviewFinding", REVIEW, "#/$defs/ReviewFinding"),
    ("ReviewResolution", REVIEW, "#/$defs/ReviewResolution"),
    ("RepairCheck", REVIEW, "#/$defs/RepairCheck"),
    ("ReviewResult", REVIEW, "#"),
    ("ConformanceResult", CONFORMANCE, "#"),
    ("BuiltConformanceResult", BUILT_CONFORMANCE, "#"),
)
# (alias, constant prefix, tuple name, schema file, pointer of the enum) for every string vocabulary.
VOCABULARIES: Final[tuple[tuple[str, str, str, str, str], ...]] = (
    ("CoverageStatus", "STATUS", "COVERAGE_STATUSES", COMMON, "#/$defs/CoverageStatus"),
    ("CoverageAction", "ACTION", "COVERAGE_ACTIONS", COMMON, "#/$defs/CoverageAction"),
    ("CoverageDisposition", "DISPOSITION", "COVERAGE_DISPOSITIONS", COMMON, "#/$defs/CoverageDisposition"),
    ("ReviewVerdict", "VERDICT", "REVIEW_VERDICTS", COMMON, "#/$defs/ReviewVerdict"),
    ("AnswerResponse", "RESPONSE", "ANSWER_RESPONSES", WRITER, "#/$defs/AnswerResponse"),
    ("ResolutionVerdict", "RESOLUTION", "RESOLUTION_VERDICTS", REVIEW, "#/$defs/ResolutionVerdict"),
    ("RepairVerdict", "REPAIR", "REPAIR_VERDICTS", REVIEW, "#/$defs/RepairVerdict"),
)
# (function, TypedDict, schema path constant, artifact description) for every parser.
PARSERS: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("parse_writer_result", "WriterResult", "WRITER_SCHEMA_PATH", "an architecture writer result"),
    ("parse_review_result", "ReviewResult", "REVIEW_SCHEMA_PATH", "an architecture review result"),
    ("parse_conformance_result", "ConformanceResult", "CONFORMANCE_SCHEMA_PATH", "an integration conformance result"),
    (
        "parse_built_conformance_result",
        "BuiltConformanceResult",
        "BUILT_CONFORMANCE_SCHEMA_PATH",
        "a built-version conformance result",
    ),
)

type Tag = Literal["str", "bool", "alias", "record", "list"]


@dataclass(frozen=True, slots=True)
class Kind:
    """The Python shape of one schema property: a scalar, a named alias or record, or a list."""

    tag: Tag
    name: str = ""
    item: Kind | None = None


def _node(value: object, where: str) -> dict[str, object]:
    """Narrow a decoded JSON value to an object.

    Returns:
        The value as a string-keyed dictionary.

    Raises:
        TypeError: The value is not a JSON object with string keys.

    """
    if not isinstance(value, dict):
        message: str = f"architecture schema: {where} is not an object"
        raise TypeError(message)
    result: dict[str, object] = {}
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            message = f"architecture schema: {where} has a non-string key"
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
        message: str = f"architecture schema: {where} is not a list"
        raise TypeError(message)
    result: list[str] = []
    item: object
    for item in value:
        if not isinstance(item, str) or not item:
            message = f"architecture schema: {where} holds a value that is not a nonempty string"
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
        message: str = f"architecture schema: {where} is not a nonempty string"
        raise ValueError(message)
    return value


class Schemas:
    """The architecture schema documents, loaded once each from SCHEMAS_DIR."""

    def __init__(self) -> None:
        """Start with no document loaded."""
        self._documents: dict[str, dict[str, object]] = {}

    def document(self, name: str) -> dict[str, object]:
        """Load one schema file by its name in SCHEMAS_DIR.

        Returns:
            The decoded schema.

        Raises:
            ValueError: The name leaves SCHEMAS_DIR or names no file.

        """
        if name not in self._documents:
            path: Path = SCHEMAS_DIR / name
            if path.parent != SCHEMAS_DIR or not path.is_file():
                message: str = f"architecture schema: {name} is not a schema file in {SCHEMAS_DIR}"
                raise ValueError(message)
            self._documents[name] = _node(json.loads(path.read_text(encoding="utf-8")), name)
        return self._documents[name]

    def resolve(self, name: str, pointer: str) -> dict[str, object]:
        """Resolve a pointer ('#' or '#/a/b') in one schema file.

        Returns:
            The schema object the pointer names.

        Raises:
            ValueError: The pointer is malformed or names nothing.

        """
        if pointer != "#" and not pointer.startswith("#/"):
            message: str = f"architecture schema: {name}{pointer} is not a JSON pointer"
            raise ValueError(message)
        current: dict[str, object] = self.document(name)
        part: str
        for part in pointer.split("/")[1:]:
            if part not in current:
                message = f"architecture schema: {name}{pointer} does not resolve"
                raise ValueError(message)
            current = _node(current[part], f"{name}{pointer}")
        return current

    @staticmethod
    def target(name: str, reference: str) -> tuple[str, str]:
        """Split a $ref into the schema file and pointer it names, relative to the file holding it.

        Returns:
            The (schema file, pointer) pair.

        """
        file_part: str
        pointer: str
        file_part, _, pointer = reference.partition("#")
        return (file_part or name, "#" + pointer)


def _snake(name: str) -> str:
    """Convert a CamelCase type name to snake case.

    Returns:
        The snake-case name.

    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _constant_name(prefix: str, value: str) -> str:
    """Name the constant that carries one wire value.

    Returns:
        PREFIX_VALUE in upper snake case.

    Raises:
        ValueError: The value cannot form a Python identifier.

    """
    name: str = prefix + "_" + re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    if not name.isidentifier():
        message: str = f"architecture schema: wire value {value!r} cannot name a constant"
        raise ValueError(message)
    return name


def _kind(
    schemas: Schemas,
    name: str,
    node: dict[str, object],
    where: str,
    named: dict[tuple[str, str], Kind],
) -> Kind:
    """Classify one property schema as the Python shape the module gives it.

    Returns:
        The property's Kind.

    Raises:
        ValueError: The property is an unnamed object or enum, or a type the generator does not type.

    """
    if "$ref" in node:
        target: tuple[str, str] = schemas.target(name, _text(node["$ref"], where + "/$ref"))
        if target in named:
            return named[target]
        return _kind(schemas, target[0], schemas.resolve(*target), f"{target[0]}{target[1]}", named)
    if "enum" in node:
        message: str = f"architecture schema: {where} is an enum with no $defs name the module can alias"
        raise ValueError(message)
    kind: str = _text(node.get("type"), where + "/type")
    if kind == "string":
        return Kind("str")
    if kind == "boolean":
        return Kind("bool")
    if kind == "array":
        item: Kind = _kind(schemas, name, _node(node.get("items"), where + "/items"), where + "/items", named)
        if item.tag == "list":
            message = f"architecture schema: {where} is a list of lists, which the generator does not type"
            raise ValueError(message)
        return Kind("list", item=item)
    message = f"architecture schema: {where} has type {kind!r} with no $defs name the module can type"
    raise ValueError(message)


def _type_source(kind: Kind) -> str:
    """Render the Python type of a Kind.

    Returns:
        Python source for the type.

    Raises:
        ValueError: A list Kind has no item.

    """
    if kind.tag == "str":
        return "str"
    if kind.tag == "bool":
        return "bool"
    if kind.tag in {"alias", "record"}:
        return kind.name
    if kind.item is None:
        message: str = "architecture schema: a list kind has no item"
        raise ValueError(message)
    return f"list[{_type_source(kind.item)}]"


def _builder(kind: Kind) -> str:
    """Name the generated function that narrows one value of a scalar, alias or record Kind.

    Returns:
        The function name.

    Raises:
        ValueError: The Kind is a list.

    """
    if kind.tag == "str":
        return "_text"
    if kind.tag == "bool":
        return "_flag"
    if kind.tag == "alias":
        return f"_as_{_snake(kind.name)}"
    if kind.tag == "record":
        return f"_build_{_snake(kind.name)}"
    message: str = "architecture schema: a list has no single-value builder"
    raise ValueError(message)


def _field_expression(key: str, kind: Kind) -> str:
    """Render the expression that narrows one field of a validated object.

    Returns:
        Python source reading the field from `node`.

    Raises:
        ValueError: A list Kind has no item.

    """
    if kind.tag == "list":
        if kind.item is None:
            message: str = "architecture schema: a list kind has no item"
            raise ValueError(message)
        return f"_each(node, {json.dumps(key)}, where, {_builder(kind.item)})"
    return f"_one(node, {json.dumps(key)}, where, {_builder(kind)})"


def _literal_block(alias: str, values: Sequence[str]) -> list[str]:
    """Render a Literal type alias, one value per line.

    Returns:
        The alias source lines.

    """
    return [f"type {alias} = Literal[", *(f"    {json.dumps(value)}," for value in values), "]"]


def _record(
    schemas: Schemas,
    record: tuple[str, str, str],
    named: dict[tuple[str, str], Kind],
) -> tuple[list[str], list[str]]:
    """Render one closed schema object as a TypedDict and its builder.

    Returns:
        The class source lines and the builder source lines.

    Raises:
        ValueError: The object is open or requires a property it does not declare.

    """
    name: str
    file_name: str
    pointer: str
    name, file_name, pointer = record
    where: str = f"{file_name}{pointer}"
    node: dict[str, object] = schemas.resolve(file_name, pointer)
    if node.get("additionalProperties") is not False:
        message: str = f"architecture schema: {where} must be a closed object"
        raise ValueError(message)
    properties: dict[str, object] = _node(node.get("properties"), where + "/properties")
    required: list[str] = _strings(node.get("required", []), where + "/required")
    missing: set[str] = set(required) - set(properties)
    if missing:
        message = f"architecture schema: {where} requires undeclared properties {sorted(missing)}"
        raise ValueError(message)
    fields: list[tuple[str, Kind]] = [
        (key, _kind(schemas, file_name, _node(spec, f"{where}/properties/{key}"), f"{where}/properties/{key}", named))
        for key, spec in properties.items()
    ]
    class_lines: list[str] = [f"class {name}(TypedDict):", f'    """Typed form of {where}."""', ""]
    class_lines.extend(
        f"    {key}: {_type_source(kind) if key in required else f'NotRequired[{_type_source(kind)}]'}"
        for key, kind in fields
    )
    builder_lines: list[str] = [
        f"def _build_{_snake(name)}(value: object, where: str) -> {name}:",
        f'    """Narrow a value validated against {where} to {name}.',
        "",
        "    Returns:",
        f"        The value as {name}.",
        "",
        '    """',
        "    node: dict[str, object] = _object(value, where)",
        f"    result: {name} = {{",
        *(f"        {json.dumps(key)}: {_field_expression(key, kind)}," for key, kind in fields if key in required),
        "    }",
    ]
    key: str
    kind: Kind
    for key, kind in fields:
        if key not in required:
            builder_lines.extend(
                (
                    f"    if {json.dumps(key)} in node:",
                    f"        result[{json.dumps(key)}] = {_field_expression(key, kind)}",
                ),
            )
    builder_lines.append("    return result")
    return class_lines, builder_lines


def _alias_narrower(alias: str, tuple_name: str) -> list[str]:
    """Render the function that narrows a wire value to one Literal alias.

    Returns:
        The function source lines.

    """
    return [
        f"def _as_{_snake(alias)}(value: object, where: str) -> {alias}:",
        f'    """Narrow a wire value to {alias}.',
        "",
        "    Returns:",
        f"        The value as one of {tuple_name}.",
        "",
        "    Raises:",
        f"        ValueError: The value is not one of {tuple_name}.",
        "",
        '    """',
        f"    option: {alias}",
        f"    for option in {tuple_name}:",
        "        if value == option:",
        "            return option",
        f'    message: str = f"{{where}} is not one of {{{tuple_name}}}"',
        "    raise ValueError(message)",
    ]


def _parser(parser: tuple[str, str, str, str]) -> list[str]:
    """Render one public parse_* function.

    Returns:
        The function source lines.

    """
    function: str
    record: str
    path_constant: str
    description: str
    function, record, path_constant, description = parser
    return [
        f"def {function}(path: Path) -> {record}:",
        f'    """Read {description} file, validate it against {path_constant} and type it.',
        "",
        "    A read failure (OSError) propagates unchanged.",
        "",
        "    Returns:",
        f"        The validated {record}.",
        "",
        "    Raises:",
        "        TypeError: path is not a Path.",
        "        ValueError: The file is not JSON or breaks the schema; the message names the file.",
        "",
        '    """',
        "    if not isinstance(path, Path):",
        f'        message: str = "{function} requires a Path"',
        "        raise TypeError(message)",
        f"    decoded: object = _validated(path, {path_constant})",
        "    try:",
        f"        return _build_{_snake(record)}(decoded, str(path))",
        "    except TypeError as error:",
        '        message = f"{path}: {error}"',
        "        raise ValueError(message) from error",
    ]


def render(schemas: Schemas) -> str:
    """Render the generated module from the architecture schemas.

    Returns:
        The complete Python source of architecture_artifacts.py.

    """
    named: dict[tuple[str, str], Kind] = {}
    alias_lines: list[str] = []
    constant_lines: list[str] = []
    tuple_lines: list[str] = []
    narrower_lines: list[str] = []
    alias: str
    prefix: str
    tuple_name: str
    file_name: str
    pointer: str
    for alias, prefix, tuple_name, file_name, pointer in VOCABULARIES:
        values: list[str] = _strings(schemas.resolve(file_name, pointer).get("enum"), f"{file_name}{pointer}/enum")
        named[file_name, pointer] = Kind("alias", alias)
        alias_lines.extend(_literal_block(alias, values))
        constant_lines.extend(
            f"{_constant_name(prefix, value)}: Final[Literal[{json.dumps(value)}]] = {json.dumps(value)}"
            for value in values
        )
        tuple_lines.extend(
            (
                f"{tuple_name}: Final[tuple[{alias}, ...]] = (",
                *(f"    {_constant_name(prefix, value)}," for value in values),
                ")",
            ),
        )
        narrower_lines.extend(("", "", *_alias_narrower(alias, tuple_name)))
    record: tuple[str, str, str]
    for record in RECORDS:
        named[record[1], record[2]] = Kind("record", record[0])
    class_lines: list[str] = []
    builder_lines: list[str] = []
    for record in RECORDS:
        record_class: list[str]
        record_builder: list[str]
        record_class, record_builder = _record(schemas, record, named)
        class_lines.extend(("", "", *record_class))
        builder_lines.extend(("", "", *record_builder))
    path_lines: list[str] = [
        f'{constant}: Final[Path] = SCHEMAS_DIR / "{schema_file}"' for constant, schema_file in SCHEMA_FILES
    ]
    parser_lines: list[str] = []
    parser: tuple[str, str, str, str]
    for parser in PARSERS:
        parser_lines.extend(("", "", *_parser(parser)))
    parts: list[str] = [
        '"""GENERATED by generate_architecture_types.py from the architecture schemas. Do not edit.',
        "",
        "The architecture writer result, architecture review result, integration conformance result and",
        "built-version conformance result, as defined by skills/artifact-handoff/schemas/architecture-*.schema.json,",
        "conformance.schema.json and built-conformance.schema.json. Regenerate with",
        "`python generate_architecture_types.py`; `--check` fails when this file is stale.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "from pathlib import Path",
        "from typing import TYPE_CHECKING, Final, Literal, NotRequired, TypedDict",
        "",
        "from jsonschema import Draft202012Validator",
        "from jsonschema.exceptions import ValidationError, best_match",
        "",
        "if TYPE_CHECKING:",
        "    from collections.abc import Callable, Mapping",
        "",
        *alias_lines,
        "",
        *constant_lines,
        "",
        *tuple_lines,
        "",
        'SCHEMAS_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "schemas"',
        *path_lines,
        *class_lines,
        "",
        "",
        TAIL.rstrip("\n"),
        *narrower_lines,
        *builder_lines,
        *parser_lines,
        "",
    ]
    return "\n".join(parts)


TAIL: Final[str] = '''def _object(value: object, where: str) -> dict[str, object]:
    """Narrow a decoded JSON value to an object.

    Returns:
        The value as a string-keyed dictionary.

    Raises:
        TypeError: The value is not a JSON object with string keys.

    """
    if not isinstance(value, dict):
        message: str = f"{where} is not an object"
        raise TypeError(message)
    result: dict[str, object] = {}
    key: object
    item: object
    for key, item in value.items():
        if not isinstance(key, str):
            message = f"{where} has a non-string key"
            raise TypeError(message)
        result[key] = item
    return result


def _text(value: object, where: str) -> str:
    """Narrow a value to a string.

    Returns:
        The string.

    Raises:
        TypeError: The value is not a string.

    """
    if not isinstance(value, str):
        message: str = f"{where} is not a string"
        raise TypeError(message)
    return value


def _flag(value: object, where: str) -> bool:
    """Narrow a value to a boolean.

    Returns:
        The boolean.

    Raises:
        TypeError: The value is not a boolean.

    """
    if not isinstance(value, bool):
        message: str = f"{where} is not a boolean"
        raise TypeError(message)
    return value


def _one[T](node: Mapping[str, object], key: str, where: str, build: Callable[[object, str], T]) -> T:
    """Narrow one required field of an object.

    Returns:
        The field's value, narrowed by build.

    Raises:
        ValueError: The field is missing.

    """
    if key not in node:
        message: str = f"{where} has no {key}"
        raise ValueError(message)
    return build(node[key], f"{where}.{key}")


def _each[T](node: Mapping[str, object], key: str, where: str, build: Callable[[object, str], T]) -> list[T]:
    """Narrow one list field of an object, item by item.

    Returns:
        The items, each narrowed by build.

    Raises:
        ValueError: The field is missing.
        TypeError: The field is not a list.

    """
    if key not in node:
        message: str = f"{where} has no {key}"
        raise ValueError(message)
    items: object = node[key]
    if not isinstance(items, list):
        message = f"{where}.{key} is not a list"
        raise TypeError(message)
    return [build(item, f"{where}.{key}[{index}]") for index, item in enumerate(items)]


def _document(name: str, documents: dict[str, dict[str, object]]) -> dict[str, object]:
    """Load one schema file of SCHEMAS_DIR by its name, once.

    A read failure (OSError) propagates unchanged.

    Returns:
        The decoded schema.

    Raises:
        ValueError: The name leaves SCHEMAS_DIR.

    """
    if name not in documents:
        path: Path = SCHEMAS_DIR / name
        if path.parent != SCHEMAS_DIR:
            message: str = f"{name} is not a schema file in {SCHEMAS_DIR}"
            raise ValueError(message)
        documents[name] = _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    return documents[name]


def _inline(value: object, name: str, documents: dict[str, dict[str, object]]) -> object:
    """Replace every $ref in a schema value with the schema it names, and drop $defs.

    Returns:
        The value with no $ref left.

    Raises:
        ValueError: A $ref names nothing.

    """
    if isinstance(value, list):
        return [_inline(item, name, documents) for item in value]
    if not isinstance(value, dict):
        return value
    node: dict[str, object] = _object(value, name)
    reference: object = node.get("$ref")
    if isinstance(reference, str):
        file_part: str
        pointer: str
        file_part, _, pointer = reference.partition("#")
        target_name: str = file_part or name
        current: object = _document(target_name, documents)
        part: str
        for part in pointer.split("/")[1:]:
            step: dict[str, object] = _object(current, reference)
            if part not in step:
                message: str = f"{name}: $ref {reference} names nothing"
                raise ValueError(message)
            current = step[part]
        return _inline(current, target_name, documents)
    return {key: _inline(item, name, documents) for key, item in node.items() if key != "$defs"}


def resolved_schema(schema_path: Path) -> dict[str, object]:
    """Load one architecture schema with every $ref replaced by the schema it names.

    A read failure (OSError) propagates unchanged.

    Returns:
        The self-contained schema.

    Raises:
        TypeError: schema_path is not a Path.
        ValueError: schema_path is not in SCHEMAS_DIR, or a $ref names nothing.

    """
    if not isinstance(schema_path, Path):
        message: str = "resolved_schema requires a Path"
        raise TypeError(message)
    if schema_path.parent != SCHEMAS_DIR:
        message = f"{schema_path} is not a schema file in {SCHEMAS_DIR}"
        raise ValueError(message)
    documents: dict[str, dict[str, object]] = {}
    return _object(_inline(_document(schema_path.name, documents), schema_path.name, documents), str(schema_path))


def _validated(path: Path, schema_path: Path) -> object:
    """Read one JSON artifact and validate it against one architecture schema.

    A read failure (OSError) propagates unchanged.

    Returns:
        The decoded artifact.

    Raises:
        ValueError: The file is not JSON or breaks the schema; the message names the file.

    """
    text: str = path.read_text(encoding="utf-8")
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as error:
        message: str = f"{path}: not JSON: {error}"
        raise ValueError(message) from error
    validator: Draft202012Validator = Draft202012Validator(resolved_schema(schema_path))
    problem: ValidationError | None = best_match(validator.iter_errors(decoded))
    if problem is not None:
        message = f"{path}: breaks {schema_path.name} at {problem.json_path}: {problem.message}"
        raise ValueError(message) from problem
    return decoded
'''


def main() -> int:
    """Write the generated module, or with --check report whether it is current.

    Returns:
        0 when written or current, 1 when --check finds it stale or missing.

    Raises:
        TypeError: The parsed --check flag is not a boolean.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when architecture_artifacts.py is stale")
    args: argparse.Namespace = parser.parse_args()
    check: object = args.check
    if not isinstance(check, bool):
        message: str = "--check must be a flag"
        raise TypeError(message)
    expected: str = render(Schemas())
    if check:
        current: str | None = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.is_file() else None
        if current != expected:
            sys.stderr.write(
                f"{OUTPUT_PATH} is stale against {SCHEMAS_DIR}; run {Path(__file__).name} to regenerate it\n",
            )
            return 1
        return 0
    OUTPUT_PATH.write_text(expected, encoding="utf-8")
    sys.stdout.write(f"wrote {OUTPUT_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
