"""Generate step_journal_contract.py from schemas/step-journal.schema.json, or check that it is current.

The schema is the one definition of the step journal: the journal document, its vocabularies and
the step plans the command takes. This script derives the Python types, the wire constants and
the validating readers from it. With --check it writes nothing and exits 1 when the generated
module differs from what it would write.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SCHEMA_PATH: Final[Path] = SCRIPTS_DIR.parent / "schemas" / "step-journal.schema.json"
OUTPUT_PATH: Final[Path] = SCRIPTS_DIR / "step_journal_contract.py"
# The toolset ruff line length; a longer generated line is wrapped the way ruff format wraps it.
MAX_LINE: Final[int] = 120

DEFINITIONS: Final[str] = "definitions"
REF_PREFIX: Final[str] = "#/definitions/"
ROOT: Final[str] = "#"

# (alias name, constant prefix, collection constant, definitions entry) for every string vocabulary.
VOCABULARIES: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("BeadType", "BEAD_TYPE", "BEAD_TYPES", "beadType"),
    ("Pipeline", "PIPELINE", "PIPELINES", "pipeline"),
    ("StepStatus", "STATUS", "STEP_STATUSES", "stepStatus"),
    ("PathKind", "KIND", "PATH_KINDS", "pathKind"),
    ("ValueKind", "KIND", "VALUE_KINDS", "valueKind"),
    ("ChangeOp", "CHANGE_OP", "CHANGE_OPS", "changeOp"),
)
# (alias name, collection constant, member aliases) for a vocabulary that is the union of others.
VOCABULARY_UNIONS: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (
    ("ArtifactKind", "ARTIFACT_KINDS", ("PathKind", "ValueKind")),
)
# (NewType name, pattern constant, definitions entry) for every identifier string with a pattern.
IDENTIFIERS: Final[tuple[tuple[str, str, str], ...]] = (
    ("BeadId", "BEAD_ID_PATTERN", "beadId"),
    ("StepId", "STEP_ID_PATTERN", "stepId"),
)
# Every definitions entry that is a plain string in Python.
STRINGS: Final[tuple[str, ...]] = ("moment", "text", "stepRef")
# (alias name, definitions entry) for every oneOf of typed objects.
UNIONS: Final[tuple[tuple[str, str], ...]] = (("Artifact", "artifact"),)
# (TypedDict name, definitions entry) for every closed object the module types.
RECORDS: Final[tuple[tuple[str, str], ...]] = (
    ("PathArtifact", "pathArtifact"),
    ("ValueArtifact", "valueArtifact"),
    ("Step", "step"),
    ("StepPlan", "stepPlan"),
    ("PlannedStep", "plannedStep"),
    ("JournalChange", "journalChange"),
)
# The TypedDict of the schema root.
ROOT_RECORD: Final[str] = "Journal"
# (constant name, schema key) for every text the contract fixes: file name suffixes and log line prefixes.
SUFFIXES: Final[tuple[tuple[str, str], ...]] = (
    ("JOURNAL_SUFFIX", "x-journalSuffix"),
    ("LOCK_SUFFIX", "x-lockSuffix"),
    ("PLANNED_FOR_PREFIX", "x-plannedForPrefix"),
    ("CHANGE_PREFIX", "x-changePrefix"),
    ("CHANGE_PART_PREFIX", "x-changePartPrefix"),
)
# The Python type of every schema type that needs no further reading: an object typed here declares no properties.
PLAIN_TYPES: Final[dict[str, str]] = {"string": "str", "integer": "int", "object": "dict[str, JsonValue]"}
# (constant name, schema key) for every whole number the contract fixes.
NUMBERS: Final[tuple[tuple[str, str], ...]] = (("CHANGE_CHUNK", "x-changeChunk"),)
# Every definitions entry the generated readers validate against by name.
VALIDATED: Final[tuple[str, ...]] = ("artifact", "stepPlan", "stepPlans", "journalChange")
_CAMEL: Final[re.Pattern[str]] = re.compile(r"(?<=[a-z0-9])([A-Z])")


class SchemaShapeError(ValueError):
    """The schema is missing a part of the contract or uses a construct the generator does not type."""


def _json_value(value: object) -> JsonValue:
    """Narrow a decoded JSON value to the JSON value type.

    Returns:
        The same value, typed.

    Raises:
        SchemaShapeError: The value holds something JSON does not.

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
                message: str = "step journal schema holds a non-string object key"
                raise SchemaShapeError(message)
            result[key] = _json_value(item)
        return result
    message = f"step journal schema holds a non-JSON value of type {type(value).__name__}"
    raise SchemaShapeError(message)


def _node(value: JsonValue, where: str) -> dict[str, JsonValue]:
    """Narrow a JSON value to an object.

    Returns:
        The object.

    Raises:
        SchemaShapeError: The value is not a JSON object.

    """
    if not isinstance(value, dict):
        message: str = f"step journal schema: {where} is not an object"
        raise SchemaShapeError(message)
    return value


def _strings(value: JsonValue, where: str) -> list[str]:
    """Narrow a JSON value to a list of nonempty strings.

    Returns:
        The strings in their schema order.

    Raises:
        SchemaShapeError: The value is not a list of nonempty strings.

    """
    if not isinstance(value, list):
        message: str = f"step journal schema: {where} is not a list"
        raise SchemaShapeError(message)
    result: list[str] = []
    item: JsonValue
    for item in value:
        if not isinstance(item, str) or not item:
            message = f"step journal schema: {where} holds a value that is not a nonempty string"
            raise SchemaShapeError(message)
        result.append(item)
    return result


def _text(value: JsonValue, where: str) -> str:
    """Narrow a JSON value to a nonempty string.

    Returns:
        The string.

    Raises:
        SchemaShapeError: The value is not a nonempty string.

    """
    if not isinstance(value, str) or not value:
        message: str = f"step journal schema: {where} is not a nonempty string"
        raise SchemaShapeError(message)
    return value


def _whole(value: JsonValue, where: str) -> int:
    """Narrow a JSON value to a positive whole number.

    Returns:
        The number.

    Raises:
        SchemaShapeError: The value is not a positive whole number.

    """
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        message: str = f"step journal schema: {where} is not a positive whole number"
        raise SchemaShapeError(message)
    return value


def _literal(values: Sequence[str]) -> str:
    """Render string values as a Literal type.

    Returns:
        Python source for the Literal.

    """
    return "Literal[" + ", ".join(json.dumps(value) for value in values) + "]"


def _upper_snake(name: str) -> str:
    """Turn a camelCase, snake_case or kebab-case wire value into UPPER_SNAKE.

    Returns:
        The name in upper snake case.

    Raises:
        SchemaShapeError: The value cannot form a Python identifier.

    """
    result: str = _CAMEL.sub(r"_\1", name).replace("-", "_").upper()
    if not result.isidentifier():
        message: str = f"step journal schema: wire value {name!r} cannot name a constant"
        raise SchemaShapeError(message)
    return result


def _ref_name(node: Mapping[str, JsonValue], where: str) -> str | None:
    """Name the definitions entry a node references.

    Returns:
        The definitions entry name, or None when the node has no $ref.

    Raises:
        SchemaShapeError: The $ref is not a local definitions reference.

    """
    if "$ref" not in node:
        return None
    pointer: str = _text(node["$ref"], where + "/$ref")
    if not pointer.startswith(REF_PREFIX) or "/" in pointer.removeprefix(REF_PREFIX):
        message: str = f"step journal schema: {where} references {pointer}, not a definitions entry"
        raise SchemaShapeError(message)
    return pointer.removeprefix(REF_PREFIX)


def _field_type(node: Mapping[str, JsonValue], where: str, known: Mapping[str, str]) -> str:
    """Render the Python type of one property.

    A property that declares neither a reference nor a type accepts any JSON value.

    Returns:
        Python source for the property's type.

    Raises:
        SchemaShapeError: The property uses a construct the generator does not type.

    """
    referenced: str | None = _ref_name(node, where)
    message: str
    if referenced is not None:
        if referenced not in known:
            message = f"step journal schema: {where} references {referenced}, which the generator does not type"
            raise SchemaShapeError(message)
        return known[referenced]
    if "const" in node:
        return _literal([_text(node["const"], where + "/const")])
    if "enum" in node:
        return _literal(_strings(node["enum"], where + "/enum"))
    if "type" not in node:
        return "JsonValue"
    kind: str = _text(node["type"], where + "/type")
    if kind == "array":
        items: dict[str, JsonValue] = _node(node.get("items"), where + "/items")
        return f"list[{_field_type(items, where + '/items', known)}]"
    plain: str | None = PLAIN_TYPES.get(kind)
    if plain is None or (kind == "object" and "properties" in node):
        message = f"step journal schema: {where} has type {kind!r}, which the generator does not type"
        raise SchemaShapeError(message)
    return plain


def _record(node: Mapping[str, JsonValue], name: str, pointer: str, known: Mapping[str, str]) -> list[str]:
    """Render one closed schema object as a TypedDict.

    Returns:
        The class source lines.

    Raises:
        SchemaShapeError: The object is open or requires a property it does not declare.

    """
    if node.get("additionalProperties") is not False:
        message: str = f"step journal schema: {pointer} must be a closed object"
        raise SchemaShapeError(message)
    properties: dict[str, JsonValue] = _node(node.get("properties"), pointer + "/properties")
    required: list[str] = _strings(node.get("required", []), pointer + "/required")
    missing: set[str] = set(required) - set(properties)
    if missing:
        message = f"step journal schema: {pointer} requires undeclared properties {sorted(missing)}"
        raise SchemaShapeError(message)
    lines: list[str] = [
        f"class {name}(TypedDict):",
        f'    """Typed form of {pointer} in step-journal.schema.json."""',
        "",
    ]
    key: str
    spec: JsonValue
    for key, spec in properties.items():
        where: str = pointer + "/properties/" + key
        rendered: str = _field_type(_node(spec, where), where, known)
        lines.append(f"    {key}: {rendered if key in required else f'NotRequired[{rendered}]'}")
    return lines


def _collection(constant: str, alias: str, members: Sequence[str]) -> str:
    """Render one tuple constant, wrapped the way ruff format wraps a line that is too long.

    Returns:
        The source of the assignment.

    """
    inline: str = ", ".join(members) + ("," if len(members) == 1 else "")
    line: str = f"{constant}: Final[tuple[{alias}, ...]] = ({inline})"
    if len(line) <= MAX_LINE:
        return line
    exploded: str = "".join(f"    {member},\n" for member in members)
    return f"{constant}: Final[tuple[{alias}, ...]] = (\n{exploded})"


def _vocabularies(definitions: Mapping[str, JsonValue], known: dict[str, str]) -> tuple[list[str], list[str]]:
    """Render every string vocabulary as a type alias, one constant per value and a tuple.

    Records each alias in ``known`` so properties that reference it are typed by it.

    Returns:
        The alias lines, and the constant lines: value constants, then collections.

    Raises:
        SchemaShapeError: Two vocabularies give one constant name two different values.

    """
    alias_lines: list[str] = []
    value_lines: list[str] = []
    collection_lines: list[str] = []
    collections: dict[str, str] = {}
    constants: dict[str, str] = {}
    alias: str
    prefix: str
    collection: str
    entry: str
    for alias, prefix, collection, entry in VOCABULARIES:
        where: str = REF_PREFIX + entry
        values: list[str] = _strings(_node(definitions.get(entry), where).get("enum"), where + "/enum")
        known[entry] = alias
        collections[alias] = collection
        alias_lines.append(f"type {alias} = {_literal(values)}")
        names: list[str] = [f"{prefix}_{_upper_snake(value)}" for value in values]
        name: str
        value: str
        for name, value in zip(names, values, strict=True):
            if constants.setdefault(name, value) != value:
                message: str = f"step journal schema: the constant {name} would carry two values"
                raise SchemaShapeError(message)
            value_lines.append(f"{name}: Final[{_literal([value])}] = {json.dumps(value)}")
        collection_lines.append(_collection(collection, alias, names))
    members: tuple[str, ...]
    for alias, collection, members in VOCABULARY_UNIONS:
        alias_lines.append(f"type {alias} = {' | '.join(members)}")
        collection_lines.append(_collection(collection, alias, [f"*{collections[member]}" for member in members]))
    return alias_lines, [*value_lines, "", *collection_lines]


def _identifiers(definitions: Mapping[str, JsonValue], known: dict[str, str]) -> tuple[list[str], list[str]]:
    """Render every identifier string as a NewType and its compiled pattern.

    Records each NewType in ``known`` so properties that reference it are typed by it.

    Returns:
        The NewType lines and the pattern lines.

    Raises:
        SchemaShapeError: A pattern cannot be written as a raw string literal.

    """
    type_lines: list[str] = []
    pattern_lines: list[str] = []
    name: str
    constant: str
    entry: str
    for name, constant, entry in IDENTIFIERS:
        where: str = REF_PREFIX + entry
        pattern: str = _text(_node(definitions.get(entry), where).get("pattern"), where + "/pattern")
        if '"' in pattern or pattern.endswith("\\") or not pattern.isprintable():
            message: str = f"step journal schema: {where}/pattern cannot be written as a raw string literal"
            raise SchemaShapeError(message)
        known[entry] = name
        type_lines.append(f'{name} = NewType("{name}", str)')
        line: str = f'{constant}: Final[re.Pattern[str]] = re.compile(r"{pattern}")'
        if len(line) > MAX_LINE:
            line = f'{constant}: Final[re.Pattern[str]] = re.compile(\n    r"{pattern}"\n)'
        pattern_lines.append(line)
    return type_lines, pattern_lines


def _unions(definitions: Mapping[str, JsonValue], known: Mapping[str, str]) -> list[str]:
    """Render every oneOf of typed objects as a union alias.

    Returns:
        The alias lines.

    Raises:
        SchemaShapeError: An entry has no list of schemas under oneOf.

    """
    lines: list[str] = []
    alias: str
    entry: str
    for alias, entry in UNIONS:
        where: str = REF_PREFIX + entry + "/oneOf"
        options: JsonValue = _node(definitions.get(entry), REF_PREFIX + entry).get("oneOf")
        if not isinstance(options, list) or not options:
            message: str = f"step journal schema: {where} is not a list of schemas"
            raise SchemaShapeError(message)
        members: list[str] = [_field_type(_node(option, where), where, known) for option in options]
        lines.append(f"type {alias} = {' | '.join(members)}")
    return lines


def render(schema: Mapping[str, JsonValue]) -> str:
    """Render the generated module for a step journal schema.

    Returns:
        The complete Python source of step_journal_contract.py.

    Raises:
        SchemaShapeError: The schema is missing a part of the contract or uses an untyped construct.

    """
    definitions: dict[str, JsonValue] = _node(schema.get(DEFINITIONS), DEFINITIONS)
    absent: list[str] = [entry for entry in VALIDATED if entry not in definitions]
    if absent:
        message: str = f"step journal schema: definitions lacks {absent}, which the readers validate against"
        raise SchemaShapeError(message)
    known: dict[str, str] = dict.fromkeys(STRINGS, "str")
    known.update({entry: alias for alias, entry in UNIONS})
    known.update({entry: record for record, entry in RECORDS})
    alias_lines: list[str]
    constant_lines: list[str]
    alias_lines, constant_lines = _vocabularies(definitions, known)
    newtype_lines: list[str]
    pattern_lines: list[str]
    newtype_lines, pattern_lines = _identifiers(definitions, known)
    suffix_lines: list[str] = [
        f"{constant}: Final = {json.dumps(_text(schema.get(key), key))}" for constant, key in SUFFIXES
    ]
    suffix_lines.extend(f"{constant}: Final = {_whole(schema.get(key), key)}" for constant, key in NUMBERS)
    record_lines: list[str] = []
    record: str
    entry: str
    for record, entry in RECORDS:
        pointer: str = REF_PREFIX + entry
        record_lines.extend(["", "", *_record(_node(definitions.get(entry), pointer), record, pointer, known)])
    record_lines.extend(["", "", *_record(schema, ROOT_RECORD, ROOT, known)])

    parts: list[str] = [
        '"""GENERATED by generate_step_journal_contract.py from schemas/step-journal.schema.json. Do not edit.',
        "",
        "The step journal contract: the journal document of one bead, its vocabularies, and the step",
        "plans the create and add operations take. Readers and writers import every type and value",
        "from here and validate documents with the readers below. Regenerate with",
        "`python generate_step_journal_contract.py`; `--check` fails when this file is stale.",
        '"""',
        "",
        "import json",
        "import re",
        "import sys",
        "from functools import lru_cache",
        "from pathlib import Path",
        "from typing import Final, Literal, NewType, NotRequired, TypedDict, TypeIs",
        "",
        "from jsonschema import Draft7Validator",
        "",
        'sys.path.append(str(Path(__file__).resolve().parents[3] / "scripts" / "portfolio"))',
        "",
        "import strictschema",
        "",
        "type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None",
        *alias_lines,
        *_unions(definitions, known),
        "",
        *newtype_lines,
        "",
        *constant_lines,
        "",
        *pattern_lines,
        *suffix_lines,
        'SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "schemas" / "step-journal.schema.json"',
        *record_lines,
        "",
        "",
        TAIL,
    ]
    return "\n".join(parts)


TAIL: Final[str] = '''class StepJournalError(ValueError):
    """A step journal document, step plan or artifact does not satisfy the contract."""


def json_value(value: object) -> JsonValue:
    """Narrow a decoded JSON value to the JSON value type.

    Returns:
        The same value, typed.

    Raises:
        TypeError: The value holds something JSON does not.

    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        key: object
        item: object
        for key, item in value.items():
            if not isinstance(key, str):
                message: str = "a JSON object holds a non-string key"
                raise TypeError(message)
            result[key] = json_value(item)
        return result
    message = f"a value of type {type(value).__name__} is not JSON"
    raise TypeError(message)


@lru_cache(maxsize=1)
def load_schema() -> dict[str, JsonValue]:
    """Load the step journal JSON Schema, the one definition of this contract.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The schema document.

    Raises:
        TypeError: The schema file is not a JSON object.

    """
    schema: JsonValue = json_value(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    if not isinstance(schema, dict):
        message: str = f"{SCHEMA_PATH} is not a JSON object"
        raise TypeError(message)
    return schema


def schema_problems(value: object, definition: str | None = None) -> list[str]:
    """Describe every way a value fails the schema, or one definitions entry of it.

    Args:
        value: The decoded document.
        definition: The definitions entry to validate against; None validates a journal.

    Returns:
        One line per failure, in path order, as ``strictschema.explain_all`` states it: the path,
        the field names it is about, the fields allowed there, the schema rule quoted and the
        schema file with the pointer and definition of the rule; empty when the value conforms.

    Raises:
        ValueError: The schema defines no such entry.

    """
    schema: dict[str, JsonValue] = load_schema()
    target: dict[str, JsonValue] = schema
    if definition is not None:
        definitions: JsonValue = schema.get("definitions")
        if not isinstance(definitions, dict) or definition not in definitions:
            message: str = f"step journal schema defines no {definition!r}"
            raise ValueError(message)
        target = {"$ref": "#/definitions/" + definition, "definitions": definitions}
    return strictschema.explain_all(
        Draft7Validator(target).iter_errors(value),
        root=target,
        location=SCHEMA_PATH,
        definition=definition,
    )


def _refusal(where: str, definition: str | None, problems: list[str]) -> str:
    """State why a value was refused: the rule it fails, then each problem on its own line.

    Returns:
        The message of the ``StepJournalError``.

    """
    rule: str = f"{SCHEMA_PATH.name}#/definitions/{definition}" if definition is not None else SCHEMA_PATH.name
    return f"{where} does not satisfy {rule}: {len(problems)} problem(s), one per line below\\n" + "\\n".join(problems)


def is_journal(value: object) -> TypeIs[Journal]:
    """Tell whether a value satisfies the journal schema.

    Returns:
        True when the schema accepts the value as a step journal.

    """
    return not schema_problems(value)


def is_artifact(value: object) -> TypeIs[Artifact]:
    """Tell whether a value satisfies the artifact definition.

    Returns:
        True when the schema accepts the value as an artifact.

    """
    return not schema_problems(value, "artifact")


def is_step_plan(value: object) -> TypeIs[StepPlan]:
    """Tell whether a value satisfies the stepPlan definition.

    Returns:
        True when the schema accepts the value as one step plan.

    """
    return not schema_problems(value, "stepPlan")


def is_step_plans(value: object) -> TypeIs[list[StepPlan]]:
    """Tell whether a value satisfies the stepPlans definition.

    Returns:
        True when the schema accepts the value as the outermost step plans of a new journal.

    """
    return not schema_problems(value, "stepPlans")


def validate_journal(value: object, where: str = "step journal") -> Journal:
    """Validate a step journal document.

    Returns:
        The value, typed.

    Raises:
        StepJournalError: The value does not satisfy the journal schema.

    """
    if is_journal(value):
        return value
    message: str = _refusal(where, None, schema_problems(value))
    raise StepJournalError(message)


def validate_artifact(value: object, where: str = "artifact") -> Artifact:
    """Validate an artifact.

    Returns:
        The value, typed.

    Raises:
        StepJournalError: The value does not satisfy the artifact definition.

    """
    if is_artifact(value):
        return value
    message: str = _refusal(where, "artifact", schema_problems(value, "artifact"))
    raise StepJournalError(message)


def validate_step_plan(value: object, where: str = "step plan") -> StepPlan:
    """Validate one step plan.

    Returns:
        The value, typed.

    Raises:
        StepJournalError: The value does not satisfy the stepPlan definition.

    """
    if is_step_plan(value):
        return value
    message: str = _refusal(where, "stepPlan", schema_problems(value, "stepPlan"))
    raise StepJournalError(message)


def validate_step_plans(value: object, where: str = "step plans") -> list[StepPlan]:
    """Validate the outermost step plans of a new journal.

    Returns:
        The value, typed.

    Raises:
        StepJournalError: The value does not satisfy the stepPlans definition.

    """
    if is_step_plans(value):
        return value
    message: str = _refusal(where, "stepPlans", schema_problems(value, "stepPlans"))
    raise StepJournalError(message)


def is_journal_change(value: object) -> TypeIs[JournalChange]:
    """Tell whether a value satisfies the journalChange definition.

    Returns:
        True when the schema accepts the value as one journal change.

    """
    return not schema_problems(value, "journalChange")


def validate_journal_change(value: object, where: str = "journal change") -> JournalChange:
    """Validate one journal change a workflow script reported.

    Returns:
        The value, typed.

    Raises:
        StepJournalError: The value does not satisfy the journalChange definition.

    """
    if is_journal_change(value):
        return value
    message: str = _refusal(where, "journalChange", schema_problems(value, "journalChange"))
    raise StepJournalError(message)
'''


def load_schema() -> dict[str, JsonValue]:
    """Read the schema file.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The schema document.

    """
    decoded: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _node(_json_value(decoded), ROOT)


def main() -> int:
    """Write the generated module, or with --check report whether it is current.

    Returns:
        0 when written or current, 1 when --check finds it stale or missing.

    Raises:
        TypeError: The parsed --check flag is not a boolean.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when step_journal_contract.py is stale")
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
