"""Generate matrix_contract.py from schemas/matrix.schema.json, or check that it is current.

The schema is the one definition of the matrix: its document, the row kinds, the link types with
the kinds each may join, the approval and code-trust markers, the roles and the commands each
role may run. This script derives the Python types, the wire constants and the validating
readers from it, and refuses a schema whose parts disagree with each other. With --check it
writes nothing and exits 1 when the generated module differs from what it would write.
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
SCHEMA_PATH: Final[Path] = SCRIPTS_DIR.parent / "schemas" / "matrix.schema.json"
OUTPUT_PATH: Final[Path] = SCRIPTS_DIR / "matrix_contract.py"
# The toolset ruff line length; a longer generated line is wrapped the way ruff format wraps it.
MAX_LINE: Final[int] = 120

DEFINITIONS: Final[str] = "$defs"
REF_PREFIX: Final[str] = "#/$defs/"
ROOT: Final[str] = "#"
KIND_ENTRY: Final[str] = "kind"
NODE_ID_ENTRY: Final[str] = "nodeId"
FIRST_SECTION: Final[int] = 1
LAST_SECTION: Final[int] = 12

# (alias name, constant prefix, collection constant, $defs entry) for every string vocabulary.
VOCABULARIES: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("Kind", "KIND", "KINDS", "kind"),
    ("OwnerKind", "KIND", "OWNER_KINDS", "ownerKind"),
    ("ElementKind", "KIND", "ELEMENT_KINDS", "elementKind"),
    ("LinkType", "LINK", "LINK_TYPES", "linkType"),
    ("ApprovalState", "APPROVAL", "APPROVAL_STATES", "approvalState"),
    ("ApprovalBasis", "BASIS", "APPROVAL_BASES", "approvalBasis"),
    ("CodeState", "CODE", "CODE_STATES", "codeState"),
    ("Status", "STATUS", "STATUSES", "status"),
    ("Coverage", "COVERAGE", "COVERAGES", "coverage"),
    ("FeatureType", "FEATURE", "FEATURE_TYPES", "featureType"),
    ("DocumentClass", "CLASS", "DOCUMENT_CLASSES", "documentClass"),
    ("Lifecycle", "LIFECYCLE", "LIFECYCLES", "lifecycle"),
    ("FactKind", "FACT", "FACT_KINDS", "factKind"),
    ("DisagreementRule", "RULE", "DISAGREEMENT_RULES", "disagreementRule"),
    ("DisagreementStatus", "DISAGREEMENT", "DISAGREEMENT_STATUSES", "disagreementStatus"),
    ("InterfaceKind", "INTERFACE", "INTERFACE_KINDS", "interfaceKind"),
    ("HeadingChange", "HEADING", "HEADING_CHANGES", "headingChange"),
    ("ReuseFinding", "REUSE", "REUSE_FINDINGS", "reuseFinding"),
    ("Role", "ROLE", "ROLES", "role"),
)
# Every vocabulary whose values must all be row kinds.
KIND_SUBSETS: Final[tuple[str, ...]] = ("ownerKind", "elementKind")
# (NewType name, pattern constant, $defs entry) for every identifier string with a pattern.
IDENTIFIERS: Final[tuple[tuple[str, str, str], ...]] = (("NodeId", "NODE_ID_PATTERN", "nodeId"),)
# (pattern constant, $defs entry) for every plain string the contract gives a pattern.
PATTERNS: Final[tuple[tuple[str, str], ...]] = (("RESOURCE_TYPE_PATTERN", "resourceTypeName"),)
# Every $defs entry that is a plain string in Python.
STRINGS: Final[tuple[str, ...]] = ("moment", "resourceTypeName")
# (TypedDict name, $defs entry) for every closed object the module types.
RECORDS: Final[tuple[tuple[str, str], ...]] = (
    ("DocumentsSyncedAt", "DocumentsSyncedAt"),
    ("Claim", "Claim"),
    ("HeadingHash", "HeadingHash"),
    ("Link", "Link"),
    ("Anchor", "Anchor"),
    ("Approval", "Approval"),
    ("Code", "Code"),
    ("Interface", "Interface"),
    ("Provides", "Provides"),
    ("DisputedStatement", "DisputedStatement"),
    ("Change", "Change"),
    ("SendBack", "SendBack"),
    ("ScopeRow", "ScopeRow"),
    ("ScopeHeading", "ScopeHeading"),
    ("HeldHeading", "HeldHeading"),
    ("ReviewScope", "ReviewScope"),
    ("ReviewerScope", "ReviewerScope"),
    ("ReuseItem", "ReuseItem"),
    ("Node", "Node"),
)
# The TypedDict of the schema root.
ROOT_RECORD: Final[str] = "Matrix"
# (constant name, schema key) for every string the contract fixes at the schema root.
ROOT_STRINGS: Final[tuple[tuple[str, str], ...]] = (
    ("MATRIX_ENV", "x-matrixEnv"),
    ("ROLE_ENV", "x-roleEnv"),
    ("LOCK_DIRECTORY", "x-lockDirectory"),
    ("LOCK_SUFFIX", "x-lockSuffix"),
    ("TASK_ELEMENTS_KEY", "x-taskElementsKey"),
)
DEFAULT_PATH_KEY: Final[str] = "x-defaultMatrixPath"
OPERATOR_KEY: Final[str] = "x-operatorRole"
LINK_TYPES_KEY: Final[str] = "x-linkTypes"
COMMANDS_KEY: Final[str] = "x-commands"
FACT_SECTIONS_KEY: Final[str] = "x-factHomeSections"
DOCUMENT_ROOTS_KEY: Final[str] = "x-documentRoots"
PUT_KINDS_KEY: Final[str] = "x-putKinds"
PUT_FIELDS_KEY: Final[str] = "x-putFields"
SETTLE_RULES_KEY: Final[str] = "x-disagreementRules"
# Every $defs entry the generated readers validate against by name.
VALIDATED: Final[tuple[str, ...]] = (
    "Node",
    "Link",
    "Provides",
    "DisputedStatement",
    "ReviewScope",
    "ReviewerScope",
)
# The keys of a schema node that say nothing about the value's type.
ANNOTATIONS: Final[frozenset[str]] = frozenset({"description"})
_CAMEL: Final[re.Pattern[str]] = re.compile(r"(?<=[a-z0-9])([A-Z])")
_SCALARS: Final[dict[str, str]] = {"string": "str", "integer": "int", "boolean": "bool", "null": "None"}


class SchemaShapeError(ValueError):
    """The schema is missing a part of the contract, contradicts itself or uses an untyped construct."""


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
                message: str = "matrix schema holds a non-string object key"
                raise SchemaShapeError(message)
            result[key] = _json_value(item)
        return result
    message = f"matrix schema holds a non-JSON value of type {type(value).__name__}"
    raise SchemaShapeError(message)


def _node(value: JsonValue, where: str) -> dict[str, JsonValue]:
    """Narrow a JSON value to an object.

    Returns:
        The object.

    Raises:
        SchemaShapeError: The value is not a JSON object.

    """
    if not isinstance(value, dict):
        message: str = f"matrix schema: {where} is not an object"
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
        message: str = f"matrix schema: {where} is not a list"
        raise SchemaShapeError(message)
    result: list[str] = []
    item: JsonValue
    for item in value:
        if not isinstance(item, str) or not item:
            message = f"matrix schema: {where} holds a value that is not a nonempty string"
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
        message: str = f"matrix schema: {where} is not a nonempty string"
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
        message: str = f"matrix schema: wire value {name!r} cannot name a constant"
        raise SchemaShapeError(message)
    return result


def _ref_name(node: Mapping[str, JsonValue], where: str) -> str | None:
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
        message: str = f"matrix schema: {where} references {pointer}, not a $defs entry"
        raise SchemaShapeError(message)
    return pointer.removeprefix(REF_PREFIX)


def _scalar_type(kind: JsonValue, where: str) -> str | None:
    """Render a ``type`` that names one scalar or a list of scalars.

    Returns:
        Python source for the type, or None when ``type`` names an array or an object.

    Raises:
        SchemaShapeError: ``type`` is neither a string nor a list of scalar names.

    """
    names: list[str] = [kind] if isinstance(kind, str) else _strings(kind, where + "/type")
    if names in (["array"], ["object"]):
        return None
    unknown: list[str] = [name for name in names if name not in _SCALARS]
    if unknown:
        message: str = f"matrix schema: {where} has type {unknown}, which the generator does not type"
        raise SchemaShapeError(message)
    return " | ".join(_SCALARS[name] for name in names)


def _field_type(node: Mapping[str, JsonValue], where: str, known: Mapping[str, str]) -> str:
    """Render the Python type of one property.

    Returns:
        Python source for the property's type.

    Raises:
        SchemaShapeError: The property uses a construct the generator does not type.

    """
    referenced: str | None = _ref_name(node, where)
    message: str
    if referenced is not None:
        if referenced not in known:
            message = f"matrix schema: {where} references {referenced}, which the generator does not type"
            raise SchemaShapeError(message)
        return known[referenced]
    if "const" in node:
        return f"Literal[{json.dumps(node['const'])}]"
    if not set(node) - ANNOTATIONS:
        return "JsonValue"
    if "type" not in node:
        message = f"matrix schema: {where} declares neither a reference, a const nor a type"
        raise SchemaShapeError(message)
    scalar: str | None = _scalar_type(node["type"], where)
    if scalar is not None:
        return scalar
    if node["type"] == "array":
        items: dict[str, JsonValue] = _node(node.get("items"), where + "/items")
        return f"list[{_field_type(items, where + '/items', known)}]"
    values: dict[str, JsonValue] = _node(node.get("additionalProperties"), where + "/additionalProperties")
    keys: str = "str"
    if "propertyNames" in node:
        keys = _field_type(_node(node["propertyNames"], where + "/propertyNames"), where + "/propertyNames", known)
    return f"dict[{keys}, {_field_type(values, where + '/additionalProperties', known)}]"


def _record(node: Mapping[str, JsonValue], name: str, pointer: str, known: Mapping[str, str]) -> list[str]:
    """Render one closed schema object as a TypedDict.

    Returns:
        The class source lines.

    Raises:
        SchemaShapeError: The object is open or requires a property it does not declare.

    """
    if node.get("additionalProperties") is not False:
        message: str = f"matrix schema: {pointer} must be a closed object"
        raise SchemaShapeError(message)
    properties: dict[str, JsonValue] = _node(node.get("properties"), pointer + "/properties")
    required: list[str] = _strings(node.get("required", []), pointer + "/required")
    missing: set[str] = set(required) - set(properties)
    if missing:
        message = f"matrix schema: {pointer} requires undeclared properties {sorted(missing)}"
        raise SchemaShapeError(message)
    lines: list[str] = [
        f"class {name}(TypedDict):",
        f'    """Typed form of {pointer} in matrix.schema.json."""',
        "",
    ]
    key: str
    spec: JsonValue
    for key, spec in properties.items():
        where: str = pointer + "/properties/" + key
        rendered: str = _field_type(_node(spec, where), where, known)
        lines.append(f"    {key}: {rendered if key in required else f'NotRequired[{rendered}]'}")
    return lines


def _wrapped(head: str, opening: str, members: Sequence[str], closing: str) -> str:
    """Render a bracketed list on one line, or one member per line when the line would be too long.

    Returns:
        The source of the statement.

    """
    line: str = f"{head}{opening}{', '.join(members)}{closing}"
    if len(line) <= MAX_LINE:
        return line
    exploded: str = "".join(f"    {member},\n" for member in members)
    return f"{head}{opening}\n{exploded}{closing}"


def _enum(definitions: Mapping[str, JsonValue], entry: str) -> list[str]:
    """Read the values of one string vocabulary.

    Returns:
        The values in schema order.

    Raises:
        SchemaShapeError: The vocabulary repeats a value.

    """
    where: str = REF_PREFIX + entry
    values: list[str] = _strings(_node(definitions.get(entry), where).get("enum"), where + "/enum")
    if len(set(values)) != len(values):
        message: str = f"matrix schema: {where}/enum repeats a value"
        raise SchemaShapeError(message)
    return values


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
    constants: dict[str, str] = {}
    alias: str
    prefix: str
    collection: str
    entry: str
    for alias, prefix, collection, entry in VOCABULARIES:
        values: list[str] = _enum(definitions, entry)
        known[entry] = alias
        alias_lines.append(_wrapped(f"type {alias} = Literal", "[", [json.dumps(value) for value in values], "]"))
        names: list[str] = [f"{prefix}_{_upper_snake(value)}" for value in values]
        name: str
        value: str
        for name, value in zip(names, values, strict=True):
            if name not in constants:
                value_lines.append(f"{name}: Final[{_literal([value])}] = {json.dumps(value)}")
            if constants.setdefault(name, value) != value:
                message: str = f"matrix schema: the constant {name} would carry two values"
                raise SchemaShapeError(message)
        trailing: list[str] = [*names[:-1], names[-1] + ("," if len(names) == 1 else "")]
        collection_lines.append(_wrapped(f"{collection}: Final[tuple[{alias}, ...]] = ", "(", trailing, ")"))
    return alias_lines, [*value_lines, "", *collection_lines]


def _raw_pattern(definitions: Mapping[str, JsonValue], entry: str) -> str:
    """Read the pattern of one $defs entry, as text that can sit inside a raw string literal.

    Returns:
        The pattern.

    Raises:
        SchemaShapeError: The pattern cannot be written as a raw string literal.

    """
    where: str = REF_PREFIX + entry
    pattern: str = _text(_node(definitions.get(entry), where).get("pattern"), where + "/pattern")
    if '"' in pattern or pattern.endswith("\\") or not pattern.isprintable():
        message: str = f"matrix schema: {where}/pattern cannot be written as a raw string literal"
        raise SchemaShapeError(message)
    return pattern


def _patterns(definitions: Mapping[str, JsonValue], known: dict[str, str]) -> tuple[list[str], list[str]]:
    """Render every identifier string as a NewType, and every pattern as a compiled constant.

    Records each NewType in ``known`` so properties that reference it are typed by it.

    Returns:
        The NewType lines and the pattern lines.

    """
    type_lines: list[str] = []
    named: list[tuple[str, str]] = []
    name: str
    constant: str
    entry: str
    for name, constant, entry in IDENTIFIERS:
        known[entry] = name
        type_lines.append(f'{name} = NewType("{name}", str)')
        named.append((constant, entry))
    pattern_lines: list[str] = []
    for constant, entry in (*named, *PATTERNS):
        pattern: str = _raw_pattern(definitions, entry)
        line: str = f'{constant}: Final[re.Pattern[str]] = re.compile(r"{pattern}")'
        if len(line) > MAX_LINE:
            line = f'{constant}: Final[re.Pattern[str]] = re.compile(\n    r"{pattern}",\n)'
        pattern_lines.append(line)
    return type_lines, pattern_lines


def _subset(values: Sequence[str], allowed: Sequence[str], where: str, what: str) -> None:
    """Require every value to be a member of a vocabulary.

    Raises:
        SchemaShapeError: A value is not in the vocabulary.

    """
    stray: list[str] = [value for value in values if value not in allowed]
    if stray:
        message: str = f"matrix schema: {where} names {stray}, which are not {what}"
        raise SchemaShapeError(message)


def _same(values: Sequence[str], expected: Sequence[str], where: str, what: str) -> None:
    """Require a table to have exactly one entry per value of a vocabulary.

    Raises:
        SchemaShapeError: The table lacks a value or names one the vocabulary does not have.

    """
    if sorted(values) != sorted(expected):
        message: str = f"matrix schema: {where} has the entries {sorted(values)}, but {what} are {sorted(expected)}"
        raise SchemaShapeError(message)


def _kind_constants(condition: Mapping[str, JsonValue], where: str) -> list[str]:
    """Collect the row kinds one ``if`` names by value.

    Returns:
        Every ``const`` under the condition's ``kind`` property, including those inside ``anyOf``.

    """
    properties: JsonValue = condition.get("properties")
    if not isinstance(properties, dict) or KIND_ENTRY not in properties:
        return []
    kind: dict[str, JsonValue] = _node(properties[KIND_ENTRY], where)
    options: JsonValue = kind.get("anyOf", [])
    choices: list[dict[str, JsonValue]] = [kind]
    if isinstance(options, list):
        choices.extend(_node(option, where + "/anyOf") for option in options)
    return [_text(choice["const"], where + "/const") for choice in choices if "const" in choice]


def _check_kinds(definitions: Mapping[str, JsonValue]) -> None:
    """Require every place the schema names row kinds to agree with the kind vocabulary.

    Raises:
        SchemaShapeError: The row id pattern, a kind subset or a conditional names a kind the
            vocabulary does not have, or the pattern lacks one it has.

    """
    kinds: list[str] = _enum(definitions, KIND_ENTRY)
    expected: str = "^(" + "|".join(kinds) + "):.+$"
    if _raw_pattern(definitions, NODE_ID_ENTRY) != expected:
        message: str = f"matrix schema: {REF_PREFIX}{NODE_ID_ENTRY}/pattern must be {expected}"
        raise SchemaShapeError(message)
    entry: str
    for entry in KIND_SUBSETS:
        _subset(_enum(definitions, entry), kinds, REF_PREFIX + entry, "row kinds")
    node: dict[str, JsonValue] = _node(definitions.get("Node"), REF_PREFIX + "Node")
    rules: JsonValue = node.get("allOf", [])
    if not isinstance(rules, list):
        message = f"matrix schema: {REF_PREFIX}Node/allOf is not a list"
        raise SchemaShapeError(message)
    index: int
    rule: JsonValue
    for index, rule in enumerate(rules):
        where: str = f"{REF_PREFIX}Node/allOf/{index}/if"
        condition: dict[str, JsonValue] = _node(_node(rule, where).get("if"), where)
        _subset(_kind_constants(condition, where), kinds, where, "row kinds")


def _check_link_types(schema: Mapping[str, JsonValue], definitions: Mapping[str, JsonValue]) -> None:
    """Require the link table to cover the link vocabulary and name only row kinds.

    Raises:
        SchemaShapeError: The table and the vocabulary differ, a rule names an unknown kind, or
            two link types share a reverse name.

    """
    kinds: list[str] = _enum(definitions, KIND_ENTRY)
    table: dict[str, JsonValue] = _node(schema.get(LINK_TYPES_KEY), LINK_TYPES_KEY)
    _same(list(table), _enum(definitions, "linkType"), LINK_TYPES_KEY, "the link types")
    reverses: list[str] = []
    name: str
    spec: JsonValue
    for name, spec in table.items():
        where: str = f"{LINK_TYPES_KEY}/{name}"
        rule: dict[str, JsonValue] = _node(spec, where)
        reverses.append(_text(rule.get("reverse"), where + "/reverse"))
        _subset(_strings(rule.get("from"), where + "/from"), kinds, where + "/from", "row kinds")
        _subset(_strings(rule.get("to"), where + "/to"), kinds, where + "/to", "row kinds")
    if len(set(reverses)) != len(reverses) or set(reverses) & set(table):
        message: str = f"matrix schema: {LINK_TYPES_KEY} reverse names must differ from each other and from link types"
        raise SchemaShapeError(message)


def _check_commands(schema: Mapping[str, JsonValue], definitions: Mapping[str, JsonValue]) -> None:
    """Require the command table to name only roles the role vocabulary has.

    Raises:
        SchemaShapeError: A command names an unknown role, states no role, or has no ``writes``
            flag; or the operator role is not a role.

    """
    roles: list[str] = _enum(definitions, "role")
    _subset([_text(schema.get(OPERATOR_KEY), OPERATOR_KEY)], roles, OPERATOR_KEY, "roles")
    name: str
    spec: JsonValue
    for name, spec in _node(schema.get(COMMANDS_KEY), COMMANDS_KEY).items():
        where: str = f"{COMMANDS_KEY}/{name}"
        rule: dict[str, JsonValue] = _node(spec, where)
        message: str
        if not isinstance(rule.get("writes"), bool):
            message = f"matrix schema: {where}/writes is not a boolean"
            raise SchemaShapeError(message)
        if rule.get("anyRole") is True and "roles" not in rule:
            continue
        if "anyRole" in rule:
            message = f"matrix schema: {where} must state anyRole true or roles, not both"
            raise SchemaShapeError(message)
        _subset(_strings(rule.get("roles"), where + "/roles"), roles, where + "/roles", "roles")


def _check_tables(schema: Mapping[str, JsonValue], definitions: Mapping[str, JsonValue]) -> None:
    """Require the fact home table and the document root table to agree with their vocabularies.

    Raises:
        SchemaShapeError: A table and its vocabulary differ, or a home section is not an arc42
            section number.

    """
    homes: dict[str, JsonValue] = _node(schema.get(FACT_SECTIONS_KEY), FACT_SECTIONS_KEY)
    _same(list(homes), _enum(definitions, "factKind"), FACT_SECTIONS_KEY, "the fact kinds")
    section: JsonValue
    for section in homes.values():
        if isinstance(section, bool) or not isinstance(section, int) or not FIRST_SECTION <= section <= LAST_SECTION:
            message: str = f"matrix schema: {FACT_SECTIONS_KEY} holds {section!r}, which is not an arc42 section"
            raise SchemaShapeError(message)
    roots: dict[str, JsonValue] = _node(schema.get(DOCUMENT_ROOTS_KEY), DOCUMENT_ROOTS_KEY)
    _subset(list(roots), _enum(definitions, "documentClass"), DOCUMENT_ROOTS_KEY, "document classes")
    _strings(list(roots.values()), DOCUMENT_ROOTS_KEY)


def _check_put(schema: Mapping[str, JsonValue], definitions: Mapping[str, JsonValue]) -> None:
    """Require the tables of what a put may write to name only roles, row kinds and row fields.

    A table that names a role, a kind or a field the schema does not have, or a role that may put
    a kind whose fields no table lists, fails with the ``SchemaShapeError`` of the subset check.
    """
    kinds: list[str] = _enum(definitions, KIND_ENTRY)
    fields: list[str] = list(_node(_node(definitions.get("Node"), "Node").get("properties"), "Node/properties"))
    by_kind: dict[str, JsonValue] = _node(schema.get(PUT_FIELDS_KEY), PUT_FIELDS_KEY)
    _subset(list(by_kind), kinds, PUT_FIELDS_KEY, "row kinds")
    kind: str
    listed: JsonValue
    for kind, listed in by_kind.items():
        where: str = f"{PUT_FIELDS_KEY}/{kind}"
        _subset(_strings(listed, where), fields, where, "row fields")
    by_role: dict[str, JsonValue] = _node(schema.get(PUT_KINDS_KEY), PUT_KINDS_KEY)
    _subset(list(by_role), _enum(definitions, "role"), PUT_KINDS_KEY, "roles")
    role: str
    for role, listed in by_role.items():
        where = f"{PUT_KINDS_KEY}/{role}"
        _subset(_strings(listed, where), list(by_kind), where, f"kinds {PUT_FIELDS_KEY} lists")


def _check_settle_rules(schema: Mapping[str, JsonValue], definitions: Mapping[str, JsonValue]) -> None:
    """Require the table of settlement rules to cover the rule vocabulary and name only roles.

    Raises:
        SchemaShapeError: The table and the vocabulary differ, a rule names an unknown role, or a
            rule does not say whether the command computes its outcome.

    """
    table: dict[str, JsonValue] = _node(schema.get(SETTLE_RULES_KEY), SETTLE_RULES_KEY)
    _same(list(table), _enum(definitions, "disagreementRule"), SETTLE_RULES_KEY, "the disagreement rules")
    roles: list[str] = _enum(definitions, "role")
    name: str
    spec: JsonValue
    for name, spec in table.items():
        where: str = f"{SETTLE_RULES_KEY}/{name}"
        rule: dict[str, JsonValue] = _node(spec, where)
        if not isinstance(rule.get("computed"), bool):
            message: str = f"matrix schema: {where}/computed is not a boolean"
            raise SchemaShapeError(message)
        _subset(_strings(rule.get("roles"), where + "/roles"), roles, where + "/roles", "roles")


def render(schema: Mapping[str, JsonValue]) -> str:
    """Render the generated module for a matrix schema.

    Returns:
        The complete Python source of matrix_contract.py.

    Raises:
        SchemaShapeError: The schema is missing a part of the contract, contradicts itself or
            uses an untyped construct.

    """
    definitions: dict[str, JsonValue] = _node(schema.get(DEFINITIONS), DEFINITIONS)
    absent: list[str] = [entry for entry in VALIDATED if entry not in definitions]
    if absent:
        message: str = f"matrix schema: $defs lacks {absent}, which the readers validate against"
        raise SchemaShapeError(message)
    _check_kinds(definitions)
    _check_link_types(schema, definitions)
    _check_commands(schema, definitions)
    _check_tables(schema, definitions)
    _check_put(schema, definitions)
    _check_settle_rules(schema, definitions)
    known: dict[str, str] = dict.fromkeys(STRINGS, "str")
    known.update({entry: record for record, entry in RECORDS})
    alias_lines: list[str]
    constant_lines: list[str]
    alias_lines, constant_lines = _vocabularies(definitions, known)
    newtype_lines: list[str]
    pattern_lines: list[str]
    newtype_lines, pattern_lines = _patterns(definitions, known)
    string_lines: list[str] = [
        f"{constant}: Final = {json.dumps(_text(schema.get(key), key))}" for constant, key in ROOT_STRINGS
    ]
    parts: list[str] = [json.dumps(part) for part in _strings(schema.get(DEFAULT_PATH_KEY), DEFAULT_PATH_KEY)]
    version: JsonValue = _node(_node(schema.get("properties"), "properties").get("version"), "version").get("const")
    if isinstance(version, bool) or not isinstance(version, int):
        message = "matrix schema: properties/version/const is not an integer"
        raise SchemaShapeError(message)
    record_lines: list[str] = []
    record: str
    entry: str
    for record, entry in RECORDS:
        pointer: str = REF_PREFIX + entry
        record_lines.extend(["", "", *_record(_node(definitions.get(entry), pointer), record, pointer, known)])
    record_lines.extend(["", "", *_record(schema, ROOT_RECORD, ROOT, known)])

    lines: list[str] = [
        '"""GENERATED by generate_matrix_contract.py from schemas/matrix.schema.json. Do not edit.',
        "",
        "The matrix contract: the matrix document, its rows and links, every vocabulary (row kinds,",
        "link types, the approval and code-trust markers, roles), and the tables the schema fixes",
        "(which kinds a link type joins, which roles may run a command). Readers and writers import",
        "every type and value from here and validate documents with the readers below. Regenerate",
        "with `python generate_matrix_contract.py`; `--check` fails when this file is stale.",
        '"""',
        "",
        "import json",
        "import re",
        "from dataclasses import dataclass",
        "from functools import lru_cache",
        "from pathlib import Path",
        "from typing import Final, Literal, NewType, NotRequired, TypedDict, TypeIs",
        "",
        "from jsonschema import Draft202012Validator",
        "",
        "type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None",
        *alias_lines,
        "",
        *newtype_lines,
        "",
        *constant_lines,
        "",
        f"VERSION: Final[Literal[{version}]] = {version}",
        *pattern_lines,
        *string_lines,
        _wrapped("DEFAULT_MATRIX_PARTS: Final[tuple[str, ...]] = ", "(", parts, ")"),
        f"OPERATOR_ROLE: Final[Role] = ROLE_{_upper_snake(_text(schema.get(OPERATOR_KEY), OPERATOR_KEY))}",
        'SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "schemas" / "matrix.schema.json"',
        *record_lines,
        "",
        "",
        TAIL,
    ]
    return "\n".join(lines)


TAIL: Final[str] = '''class MatrixError(ValueError):
    """A matrix document, row or link does not satisfy the contract, or the matrix refuses a request."""


@dataclass(frozen=True, slots=True)
class LinkRule:
    """What the schema fixes for one link type."""

    reverse: str
    """The name the reverse direction is reported under; it is computed, never stored."""
    sources: frozenset[Kind]
    """The kinds of row the link may start from."""
    targets: frozenset[Kind]
    """The kinds of row the link may point at."""


@dataclass(frozen=True, slots=True)
class CommandRule:
    """What the schema fixes for one sub-command of atw-matrix."""

    writes: bool
    """Whether the command changes the matrix file."""
    roles: frozenset[Role]
    """The roles that may run it."""


@dataclass(frozen=True, slots=True)
class SettleRule:
    """What the schema fixes for one rule a disagreement is settled by."""

    computed: bool
    """Whether the command works out which statement stands, so the caller names none."""
    roles: frozenset[Role]
    """The roles that may settle by it."""


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
    """Load the matrix JSON Schema, the one definition of this contract.

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


def _table(key: str) -> dict[str, JsonValue]:
    """Read one table the schema keeps at its root.

    Returns:
        The table.

    Raises:
        TypeError: The schema has no such table.

    """
    table: JsonValue = load_schema().get(key)
    if not isinstance(table, dict):
        message: str = f"matrix schema: {key} is not an object"
        raise TypeError(message)
    return table


def _members[T: str](value: JsonValue, choices: tuple[T, ...], where: str) -> frozenset[T]:
    """Narrow a list of wire values to members of one vocabulary.

    Returns:
        The members named.

    Raises:
        TypeError: The value is not a list, or names something the vocabulary does not have.

    """
    if not isinstance(value, list):
        message: str = f"matrix schema: {where} is not a list"
        raise TypeError(message)
    found: frozenset[T] = frozenset(choice for choice in choices if choice in value)
    if len(found) != len(value):
        message = f"matrix schema: {where} names a value outside {choices}"
        raise TypeError(message)
    return found


def _link_rules() -> dict[LinkType, LinkRule]:
    """Build the link rules from the schema's link table.

    Returns:
        One rule per link type.

    Raises:
        TypeError: The table lacks a link type or a rule is malformed.

    """
    table: dict[str, JsonValue] = _table("x-linkTypes")
    rules: dict[LinkType, LinkRule] = {}
    link_type: LinkType
    for link_type in LINK_TYPES:
        rule: JsonValue = table.get(link_type)
        reverse: JsonValue = rule.get("reverse") if isinstance(rule, dict) else None
        if not isinstance(rule, dict) or not isinstance(reverse, str):
            message: str = f"matrix schema: x-linkTypes/{link_type} is malformed"
            raise TypeError(message)
        rules[link_type] = LinkRule(
            reverse=reverse,
            sources=_members(rule.get("from"), KINDS, f"x-linkTypes/{link_type}/from"),
            targets=_members(rule.get("to"), KINDS, f"x-linkTypes/{link_type}/to"),
        )
    return rules


def _command_rules() -> dict[str, CommandRule]:
    """Build the command rules from the schema's command table.

    Returns:
        One rule per sub-command the design names, built or not.

    Raises:
        TypeError: A rule is malformed.

    """
    rules: dict[str, CommandRule] = {}
    name: str
    rule: JsonValue
    for name, rule in _table("x-commands").items():
        writes: JsonValue = rule.get("writes") if isinstance(rule, dict) else None
        if not isinstance(rule, dict) or not isinstance(writes, bool):
            message: str = f"matrix schema: x-commands/{name} is malformed"
            raise TypeError(message)
        everyone: bool = rule.get("anyRole") is True
        roles: frozenset[Role] = frozenset(ROLES) if everyone else _members(rule.get("roles"), ROLES, name)
        rules[name] = CommandRule(writes=writes, roles=roles)
    return rules


def _fact_home_sections() -> dict[FactKind, int]:
    """Build the home section of each fact kind from the schema's table.

    Returns:
        The arc42 section number that is the home of each kind of fact.

    Raises:
        TypeError: The table lacks a fact kind or holds a value that is not an integer.

    """
    table: dict[str, JsonValue] = _table("x-factHomeSections")
    sections: dict[FactKind, int] = {}
    fact_kind: FactKind
    for fact_kind in FACT_KINDS:
        section: JsonValue = table.get(fact_kind)
        if isinstance(section, bool) or not isinstance(section, int):
            message: str = f"matrix schema: x-factHomeSections/{fact_kind} is not an integer"
            raise TypeError(message)
        sections[fact_kind] = section
    return sections


def _document_roots() -> dict[DocumentClass, str]:
    """Build the folder of each synced document class from the schema's table.

    Returns:
        The folder, under the architecture root, that holds each class of document the vault read covers.

    Raises:
        TypeError: A folder is not a string.

    """
    table: dict[str, JsonValue] = _table("x-documentRoots")
    roots: dict[DocumentClass, str] = {}
    document_class: DocumentClass
    for document_class in DOCUMENT_CLASSES:
        if document_class not in table:
            continue
        folder: JsonValue = table[document_class]
        if not isinstance(folder, str):
            message: str = f"matrix schema: x-documentRoots/{document_class} is not a string"
            raise TypeError(message)
        roots[document_class] = folder
    return roots


def _put_kinds() -> dict[Role, frozenset[Kind]]:
    """Build the kinds of row each role may put from the schema's table.

    Returns:
        The kinds each role that may put a row may put.

    """
    table: dict[str, JsonValue] = _table("x-putKinds")
    return {role: _members(table[role], KINDS, f"x-putKinds/{role}") for role in ROLES if role in table}


def _put_fields() -> dict[Kind, frozenset[str]]:
    """Build the fields a put may state for each kind of row from the schema's table.

    Returns:
        The row fields a caller may state for each kind a put may write.

    Raises:
        TypeError: A kind's fields are not a list of strings.

    """
    table: dict[str, JsonValue] = _table("x-putFields")
    fields: dict[Kind, frozenset[str]] = {}
    kind: Kind
    for kind in KINDS:
        if kind not in table:
            continue
        listed: JsonValue = table[kind]
        if not isinstance(listed, list):
            message: str = f"matrix schema: x-putFields/{kind} is not a list"
            raise TypeError(message)
        fields[kind] = frozenset(name for name in listed if isinstance(name, str))
    return fields


def _settle_rules() -> dict[DisagreementRule, SettleRule]:
    """Build the settlement rules from the schema's table.

    Returns:
        One rule per way a disagreement is settled.

    Raises:
        TypeError: The table lacks a rule or a rule is malformed.

    """
    table: dict[str, JsonValue] = _table("x-disagreementRules")
    rules: dict[DisagreementRule, SettleRule] = {}
    name: DisagreementRule
    for name in DISAGREEMENT_RULES:
        rule: JsonValue = table.get(name)
        computed: JsonValue = rule.get("computed") if isinstance(rule, dict) else None
        if not isinstance(rule, dict) or not isinstance(computed, bool):
            message: str = f"matrix schema: x-disagreementRules/{name} is malformed"
            raise TypeError(message)
        rules[name] = SettleRule(computed=computed, roles=_members(rule.get("roles"), ROLES, name))
    return rules


LINK_RULES: Final[dict[LinkType, LinkRule]] = _link_rules()
COMMAND_RULES: Final[dict[str, CommandRule]] = _command_rules()
PUT_KINDS: Final[dict[Role, frozenset[Kind]]] = _put_kinds()
PUT_FIELDS: Final[dict[Kind, frozenset[str]]] = _put_fields()
SETTLE_RULES: Final[dict[DisagreementRule, SettleRule]] = _settle_rules()
FACT_HOME_SECTIONS: Final[dict[FactKind, int]] = _fact_home_sections()
DOCUMENT_ROOTS: Final[dict[DocumentClass, str]] = _document_roots()
PLACED_KINDS: Final[frozenset[Kind]] = frozenset({KIND_STACK, *ELEMENT_KINDS})
"""The kinds of row that live in a repository."""
CODED_KINDS: Final[frozenset[Kind]] = frozenset({*OWNER_KINDS, *PLACED_KINDS})
"""The kinds of row that carry the code-trust marker."""
MESSAGE_LIMIT: Final = 300
"""The most characters of one schema failure a problem line carries."""
PROBLEMS_SHOWN: Final = 20
"""The most schema failures an error message lists."""


@lru_cache(maxsize=8)
def _validator(definition: str | None) -> Draft202012Validator:
    """Build the validator of the matrix, or of one $defs entry of it.

    Returns:
        The validator.

    Raises:
        ValueError: The schema defines no such entry.

    """
    schema: dict[str, JsonValue] = load_schema()
    if definition is None:
        return Draft202012Validator(schema)
    definitions: JsonValue = schema.get("$defs")
    if not isinstance(definitions, dict) or definition not in definitions:
        message: str = f"matrix schema defines no {definition!r}"
        raise ValueError(message)
    return Draft202012Validator({"$ref": "#/$defs/" + definition, "$defs": definitions})


def schema_problems(value: object, definition: str | None = None) -> list[str]:
    """Describe every way a value fails the schema, or one $defs entry of it.

    Args:
        value: The decoded document.
        definition: The $defs entry to validate against; None validates a matrix.

    Returns:
        One "<path>: <message>" per failure, in document order; empty when the value conforms.

    """
    problems: list[tuple[list[str], str]] = []
    for error in _validator(definition).iter_errors(value):
        path: list[str] = [str(part) for part in error.absolute_path]
        detail: str = error.message if len(error.message) <= MESSAGE_LIMIT else error.message[:MESSAGE_LIMIT] + "..."
        problems.append((path, f"{'/'.join(path) or '<root>'}: {detail}"))
    return [text for _, text in sorted(problems)]


def is_matrix(value: object) -> TypeIs[Matrix]:
    """Tell whether a value satisfies the matrix schema.

    Returns:
        True when the schema accepts the value as a matrix.

    """
    return _validator(None).is_valid(value)


def is_node(value: object) -> TypeIs[Node]:
    """Tell whether a value satisfies the Node definition.

    Returns:
        True when the schema accepts the value as one row.

    """
    return _validator("Node").is_valid(value)


def validate_matrix(value: object, where: str = "matrix") -> Matrix:
    """Validate a matrix document.

    Returns:
        The value, typed.

    Raises:
        MatrixError: The value does not satisfy the matrix schema.

    """
    if is_matrix(value):
        return value
    problems: list[str] = schema_problems(value)
    shown: str = "; ".join(problems[:PROBLEMS_SHOWN])
    message: str = f"{where} does not satisfy the matrix schema ({len(problems)} problems): {shown}"
    raise MatrixError(message)


def is_review_scope(value: object) -> TypeIs[ReviewScope]:
    """Tell whether a value satisfies the ReviewScope definition.

    Returns:
        True when the schema accepts the value as a review scope.

    """
    return _validator("ReviewScope").is_valid(value)


def validate_review_scope(value: object, where: str = "review scope") -> ReviewScope:
    """Validate a review scope.

    Returns:
        The value, typed.

    Raises:
        MatrixError: The value does not satisfy the ReviewScope definition.

    """
    if is_review_scope(value):
        return value
    shown: str = "; ".join(schema_problems(value, "ReviewScope")[:PROBLEMS_SHOWN])
    message: str = f"{where} does not satisfy ReviewScope: {shown}"
    raise MatrixError(message)


def is_reviewer_scope(value: object) -> TypeIs[ReviewerScope]:
    """Tell whether a value satisfies the ReviewerScope definition.

    Returns:
        True when the schema accepts the value as one reviewer's scope.

    """
    return _validator("ReviewerScope").is_valid(value)


def validate_reviewer_scope(value: object, where: str = "reviewer scope") -> ReviewerScope:
    """Validate the review scope one reviewer is handed.

    Returns:
        The value, typed.

    Raises:
        MatrixError: The value does not satisfy the ReviewerScope definition.

    """
    if is_reviewer_scope(value):
        return value
    shown: str = "; ".join(schema_problems(value, "ReviewerScope")[:PROBLEMS_SHOWN])
    message: str = f"{where} does not satisfy ReviewerScope: {shown}"
    raise MatrixError(message)


def is_statements(value: object) -> TypeIs[list[DisputedStatement]]:
    """Tell whether a value is a list of disputed statements.

    Returns:
        True when the value is a list and the schema accepts each entry as a disputed statement.

    """
    return isinstance(value, list) and all(_validator("DisputedStatement").is_valid(entry) for entry in value)


def is_provides(value: object) -> TypeIs[list[Provides]]:
    """Tell whether a value is a list of provides entries.

    Returns:
        True when the value is a list and the schema accepts each entry as a provides entry.

    """
    return isinstance(value, list) and all(_validator("Provides").is_valid(entry) for entry in value)


def validate_node(value: object, where: str = "row") -> Node:
    """Validate one row.

    Returns:
        The value, typed.

    Raises:
        MatrixError: The value does not satisfy the Node definition.

    """
    if is_node(value):
        return value
    message: str = f"{where} does not satisfy Node: " + "; ".join(schema_problems(value, "Node")[:PROBLEMS_SHOWN])
    raise MatrixError(message)
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
    parser.add_argument("--check", action="store_true", help="exit 1 when matrix_contract.py is stale")
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
