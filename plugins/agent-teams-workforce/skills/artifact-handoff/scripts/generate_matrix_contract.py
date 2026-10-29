"""Generate matrix_contract.py from the matrix schema and the kinds registry, or check that it is current.

schemas/matrix.schema.json states the generic shape of the matrix file. schemas/matrix-kinds.json
(the kinds registry) declares what kinds of entry and relationship exist, the attributes of each,
the controlled list of resource types, and each atw-matrix command with the roles that run it.
This script derives the Python vocabulary and the wire constants from both, appends the types and
the validating readers, and refuses a schema or a registry whose parts disagree with each other.
With --check it writes nothing and exits 1 when the generated module differs from what it would
write.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None

SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SCHEMA_PATH: Final[Path] = SCRIPTS_DIR.parent / "schemas" / "matrix.schema.json"
REGISTRY_PATH: Final[Path] = SCRIPTS_DIR.parent / "schemas" / "matrix-kinds.json"
OUTPUT_PATH: Final[Path] = SCRIPTS_DIR / "matrix_contract.py"
# The toolset ruff line length; a longer generated line is wrapped the way ruff format wraps it.
MAX_LINE: Final[int] = 120

DEFINITIONS: Final[str] = "$defs"
REF_KEY: Final[str] = "$ref"
REF_PREFIX: Final[str] = "#/$defs/"
ENTRY_ID_ENTRY: Final[str] = "entryId"
# The $defs entries the generated readers add to the registry's own when they validate attributes.
BUILT_IN_DEFINITIONS: Final[frozenset[str]] = frozenset({ENTRY_ID_ENTRY})
# The $defs entry of the schema that gives the form of a kind name.
KIND_NAME_ENTRY: Final[str] = "kindName"
PURPOSE_MEMBER: Final[str] = "purpose"
# The members the generated dataclasses read from each closed part of the matrix file: ($defs entry, members, required).
SHAPES: Final[tuple[tuple[str, frozenset[str], frozenset[str]], ...]] = (
    (
        "Entry",
        frozenset({"id", "kind", "name", "side", "aliases", "purpose", "approved", "verified"}),
        frozenset({"id", "kind", "name", "side", "aliases", "purpose"}),
    ),
    (
        "Relationship",
        frozenset({"kind", "from", "to", "side", "approved", "verified"}),
        frozenset({"kind", "from", "to", "side"}),
    ),
)
# The $defs entries of the marks, each a plain boolean an entry or a relationship carries as true or omits.
MARKS: Final[tuple[str, ...]] = ("Approved", "Verified")
ROOT_MEMBERS: Final[frozenset[str]] = frozenset({"version", "entries", "relationships"})
# (constant name, schema key) for every string the contract fixes at the schema root.
ROOT_STRINGS: Final[tuple[tuple[str, str], ...]] = (
    ("MATRIX_ENV", "x-matrixEnv"),
    ("ROLE_ENV", "x-roleEnv"),
    ("LOCK_DIRECTORY", "x-lockDirectory"),
    ("LOCK_SUFFIX", "x-lockSuffix"),
    ("TASK_ELEMENTS_KEY", "x-taskElementsKey"),
)
DEFAULT_PATH_KEY: Final[str] = "x-defaultMatrixPath"
ENTRY_KINDS_KEY: Final[str] = "entryKinds"
RELATIONSHIP_KINDS_KEY: Final[str] = "relationshipKinds"
COMMANDS_KEY: Final[str] = "commands"
ROLES_KEY: Final[str] = "roles"
OPERATOR_KEY: Final[str] = "operatorRole"
HOME_KEY: Final[str] = "homeRelationship"
STACK_KEY: Final[str] = "stackKind"
REQUIRED_ONE_KEY: Final[str] = "requiredOne"
# The $defs entry of the schema that lists the sides, and the root key that names the side that is the authority.
SIDE_ENTRY: Final[str] = "side"
AUTHORITY_KEY: Final[str] = "x-authoritySide"
# The member of a kind's declaration that names the one side the kind is always recorded with.
KIND_SIDE_KEY: Final[str] = "side"
ID_PATTERN_KEY: Final[str] = "idPattern"
REPOSITORY_ID_PATTERN_KEY: Final[str] = "repositoryIdPattern"
_CAMEL: Final[re.Pattern[str]] = re.compile(r"(?<=[a-z0-9])([A-Z])")
_KIND_NAME: Final[re.Pattern[str]] = re.compile(r"[a-z][A-Za-z]*")


class SchemaShapeError(ValueError):
    """The schema or the registry is missing a part of the contract or contradicts itself."""


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
                message: str = "matrix contract source holds a non-string object key"
                raise SchemaShapeError(message)
            result[key] = _json_value(item)
        return result
    message = f"matrix contract source holds a non-JSON value of type {type(value).__name__}"
    raise SchemaShapeError(message)


def _node(value: JsonValue, where: str) -> dict[str, JsonValue]:
    """Narrow a JSON value to an object.

    Returns:
        The object.

    Raises:
        SchemaShapeError: The value is not a JSON object.

    """
    if not isinstance(value, dict):
        message: str = f"matrix contract: {where} is not an object"
        raise SchemaShapeError(message)
    return value


def _strings(value: JsonValue, where: str) -> list[str]:
    """Narrow a JSON value to a list of distinct nonempty strings.

    Returns:
        The strings in their source order.

    Raises:
        SchemaShapeError: The value is not a list of distinct nonempty strings.

    """
    if not isinstance(value, list):
        message: str = f"matrix contract: {where} is not a list"
        raise SchemaShapeError(message)
    result: list[str] = []
    item: JsonValue
    for item in value:
        if not isinstance(item, str) or not item or item in result:
            message = f"matrix contract: {where} holds a value that is not a distinct nonempty string"
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
        message: str = f"matrix contract: {where} is not a nonempty string"
        raise SchemaShapeError(message)
    return value


def _flag(value: JsonValue, where: str) -> bool:
    """Narrow a JSON value to a boolean.

    Returns:
        The boolean.

    Raises:
        SchemaShapeError: The value is not a boolean.

    """
    if not isinstance(value, bool):
        message: str = f"matrix contract: {where} is not a boolean"
        raise SchemaShapeError(message)
    return value


def _limit(value: JsonValue, where: str) -> int | None:
    """Narrow an optional JSON value to a positive integer.

    Returns:
        The integer; None when the value is absent.

    Raises:
        SchemaShapeError: The value is present and is not a positive integer.

    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        message: str = f"matrix contract: {where} is not a positive integer"
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
        message: str = f"matrix contract: wire value {name!r} cannot name a constant"
        raise SchemaShapeError(message)
    return result


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


def _raw_pattern(value: JsonValue, where: str) -> str:
    """Read a pattern as text that compiles and can sit inside a raw string literal.

    Returns:
        The pattern.

    Raises:
        SchemaShapeError: The pattern does not compile or cannot be written as a raw string literal.

    """
    pattern: str = _text(value, where)
    message: str
    if '"' in pattern or pattern.endswith("\\") or not pattern.isprintable():
        message = f"matrix contract: {where} cannot be written as a raw string literal"
        raise SchemaShapeError(message)
    try:
        re.compile(pattern)
    except re.error as error:
        message = f"matrix contract: {where} is not a regular expression: {error}"
        raise SchemaShapeError(message) from error
    return pattern


def _subset(values: Sequence[str], allowed: Sequence[str], where: str, what: str) -> None:
    """Require every value to be a member of a vocabulary.

    Raises:
        SchemaShapeError: A value is not in the vocabulary.

    """
    stray: list[str] = [value for value in values if value not in allowed]
    if stray:
        message: str = f"matrix contract: {where} names {stray}, which are not {what}"
        raise SchemaShapeError(message)


def _references(node: JsonValue) -> list[str]:
    """Collect every $ref a schema fragment holds, at any depth.

    Returns:
        The pointers, in source order.

    """
    found: list[str] = []
    if isinstance(node, list):
        item: JsonValue
        for item in node:
            found.extend(_references(item))
    if isinstance(node, dict):
        key: str
        value: JsonValue
        for key, value in node.items():
            if key == REF_KEY and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_references(value))
    return found


def _check_references(fragment: JsonValue, known: Sequence[str], where: str) -> None:
    """Require every $ref of a fragment to name a definition the readers resolve.

    Raises:
        SchemaShapeError: A $ref names something that is neither a registry definition nor built in.

    """
    pointer: str
    for pointer in _references(fragment):
        if not pointer.startswith(REF_PREFIX) or pointer.removeprefix(REF_PREFIX) not in known:
            message: str = f"matrix contract: {where} references {pointer}, which is not one of {sorted(known)}"
            raise SchemaShapeError(message)


def _attributes(rule: Mapping[str, JsonValue], members: frozenset[str], known: Sequence[str], where: str) -> list[str]:
    """Check the attributes one kind declares and name them.

    An attribute whose fragment is a reference to the entry id is an entry reference, which rename
    and remove follow; a reference to the entry id anywhere deeper is refused, because they could
    not follow it.

    Returns:
        The attribute names, in registry order.

    Raises:
        SchemaShapeError: An attribute takes the name of a common member, or holds an entry
            reference below its top level.

    """
    declared: dict[str, JsonValue] = _node(rule.get("attributes"), where + "/attributes")
    clash: list[str] = sorted(set(declared) & members)
    message: str
    if clash:
        message = f"matrix contract: {where}/attributes declares {clash}, which are common members"
        raise SchemaShapeError(message)
    name: str
    fragment: JsonValue
    for name, fragment in declared.items():
        spot: str = f"{where}/attributes/{name}"
        spec: dict[str, JsonValue] = _node(fragment, spot)
        _check_references(spec, known, spot)
        nested: list[str] = [pointer for key, value in spec.items() if key != REF_KEY for pointer in _references(value)]
        if REF_PREFIX + ENTRY_ID_ENTRY in nested:
            message = f"matrix contract: {spot} holds an entry reference below its top level"
            raise SchemaShapeError(message)
    return list(declared)


def _check_shapes(schema: Mapping[str, JsonValue]) -> None:
    """Require the schema's closed parts to have exactly the members the generated dataclasses read.

    Raises:
        SchemaShapeError: The root or a $defs entry declares or requires other members.

    """
    definitions: dict[str, JsonValue] = _node(schema.get(DEFINITIONS), DEFINITIONS)
    message: str
    if set(_node(schema.get("properties"), "properties")) != ROOT_MEMBERS:
        message = f"matrix schema: the root must declare exactly {sorted(ROOT_MEMBERS)}"
        raise SchemaShapeError(message)
    entry: str
    members: frozenset[str]
    required: frozenset[str]
    for entry, members, required in SHAPES:
        where: str = REF_PREFIX + entry
        shape: dict[str, JsonValue] = _node(definitions.get(entry), where)
        if set(_node(shape.get("properties"), where + "/properties")) != members:
            message = f"matrix schema: {where} must declare exactly {sorted(members)}"
            raise SchemaShapeError(message)
        if set(_strings(shape.get("required"), where + "/required")) != required:
            message = f"matrix schema: {where} must require exactly {sorted(required)}"
            raise SchemaShapeError(message)
    mark: str
    for mark in MARKS:
        if _node(definitions.get(mark), REF_PREFIX + mark).get("type") != "boolean":
            message = f"matrix schema: {REF_PREFIX}{mark} must be a boolean"
            raise SchemaShapeError(message)


def _sides(schema: Mapping[str, JsonValue]) -> list[str]:
    """Read the sides the schema lists and require the authority to be one of them.

    Returns:
        The sides, in schema order.

    Raises:
        SchemaShapeError: The schema lists no side, a side cannot name a constant, or the side
            the schema names as the authority is not one it lists.

    """
    where: str = REF_PREFIX + SIDE_ENTRY
    definitions: dict[str, JsonValue] = _node(schema.get(DEFINITIONS), DEFINITIONS)
    sides: list[str] = _strings(_node(definitions.get(SIDE_ENTRY), where).get("enum"), where + "/enum")
    if not sides:
        message: str = f"matrix schema: {where}/enum lists no side"
        raise SchemaShapeError(message)
    _subset([_text(schema.get(AUTHORITY_KEY), AUTHORITY_KEY)], sides, AUTHORITY_KEY, "sides")
    return sides


def _check_kind_side(rule: Mapping[str, JsonValue], sides: Sequence[str], where: str) -> None:
    """Require the one side a kind declares, when it declares one, to be a side.

    A kind that names something that is not a side raises ``SchemaShapeError`` from the check
    that finds it.
    """
    if KIND_SIDE_KEY in rule:
        spot: str = f"{where}/{KIND_SIDE_KEY}"
        _subset([_text(rule[KIND_SIDE_KEY], spot)], sides, spot, "sides")


def _check_id_patterns(kind: str, rule: Mapping[str, JsonValue], where: str) -> None:
    """Require every id pattern of an entry kind to start with the kind.

    Raises:
        SchemaShapeError: A pattern does not start with the kind and a colon, or the kind
            declares both the one side it is recorded with and a second id form.

    """
    message: str
    key: str
    for key in (ID_PATTERN_KEY, REPOSITORY_ID_PATTERN_KEY):
        if key == REPOSITORY_ID_PATTERN_KEY and key not in rule:
            continue
        if not _raw_pattern(rule.get(key), f"{where}/{key}").startswith(f"^{kind}:"):
            message = f"matrix contract: {where}/{key} must start with ^{kind}:"
            raise SchemaShapeError(message)
    if REPOSITORY_ID_PATTERN_KEY in rule and KIND_SIDE_KEY in rule:
        message = f"matrix contract: {where} declares one side and an id form for the other"
        raise SchemaShapeError(message)


def _check_entry_kinds(registry: Mapping[str, JsonValue], known: Sequence[str], sides: Sequence[str]) -> list[str]:
    """Check every entry kind the registry declares.

    Returns:
        The entry kinds, in registry order.

    Raises:
        SchemaShapeError: A kind's name is malformed, an id pattern does not start with the kind,
            it names a side that is not one, it requires something it does not declare, or the
            stack kind is not a kind.

    """
    table: dict[str, JsonValue] = _node(registry.get(ENTRY_KINDS_KEY), ENTRY_KINDS_KEY)
    members: frozenset[str] = SHAPES[0][1]
    message: str
    kind: str
    spec: JsonValue
    for kind, spec in table.items():
        where: str = f"{ENTRY_KINDS_KEY}/{kind}"
        rule: dict[str, JsonValue] = _node(spec, where)
        if _KIND_NAME.fullmatch(kind) is None:
            message = f"matrix contract: {where} is not a kind name"
            raise SchemaShapeError(message)
        _check_id_patterns(kind, rule, where)
        _check_kind_side(rule, sides, where)
        attributes: list[str] = _attributes(rule, members, known, where)
        required: list[str] = _strings(rule.get("required"), where + "/required")
        _subset(required, [*attributes, PURPOSE_MEMBER], where + "/required", "attributes of the kind")
        one: list[str] = _strings(rule.get(REQUIRED_ONE_KEY, []), where + "/" + REQUIRED_ONE_KEY)
        _subset(one, attributes, where + "/" + REQUIRED_ONE_KEY, "attributes of the kind")
    if not table:
        message = f"matrix contract: {ENTRY_KINDS_KEY} declares no kind"
        raise SchemaShapeError(message)
    _subset([_text(registry.get(STACK_KEY), STACK_KEY)], list(table), STACK_KEY, "entry kinds")
    return list(table)


def _check_relationship_kinds(
    registry: Mapping[str, JsonValue],
    known: Sequence[str],
    sides: Sequence[str],
) -> tuple[list[str], list[str]]:
    """Check every relationship kind the registry declares.

    A declaration names no entry kinds: any entry may link to any other.

    Returns:
        The relationship kinds and the families they name, each in registry order.

    Raises:
        SchemaShapeError: A name is malformed or used twice, a kind names a side that is not
            one, a key or required attribute is undeclared, or the home relationship is not a kind.

    """
    table: dict[str, JsonValue] = _node(registry.get(RELATIONSHIP_KINDS_KEY), RELATIONSHIP_KINDS_KEY)
    members: frozenset[str] = SHAPES[1][1]
    names: list[str] = list(table)
    families: list[str] = []
    message: str
    kind: str
    spec: JsonValue
    for kind, spec in table.items():
        where: str = f"{RELATIONSHIP_KINDS_KEY}/{kind}"
        rule: dict[str, JsonValue] = _node(spec, where)
        reverse: str = _text(rule.get("reverse"), where + "/reverse")
        if _KIND_NAME.fullmatch(kind) is None or _KIND_NAME.fullmatch(reverse) is None or reverse in names:
            message = f"matrix contract: {where} and its reverse must be kind names no other relationship uses"
            raise SchemaShapeError(message)
        names.append(reverse)
        _check_kind_side(rule, sides, where)
        attributes: list[str] = _attributes(rule, members, known, where)
        _subset(_strings(rule.get("required"), where + "/required"), attributes, where + "/required", "its attributes")
        _subset(_strings(rule.get("key"), where + "/key"), attributes, where + "/key", "its attributes")
        _limit(rule.get("maxPerStart"), where + "/maxPerStart")
        if "family" in rule and _text(rule["family"], where + "/family") not in families:
            families.append(_text(rule["family"], where + "/family"))
    _subset([_text(registry.get(HOME_KEY), HOME_KEY)], list(table), HOME_KEY, "relationship kinds")
    return list(table), families


def _check_commands(registry: Mapping[str, JsonValue]) -> list[str]:
    """Check the roles and the command table.

    Returns:
        The roles, in registry order.

    Raises:
        SchemaShapeError: A command states both every role and a list of roles.

    """
    roles: list[str] = _strings(registry.get(ROLES_KEY), ROLES_KEY)
    _subset([_text(registry.get(OPERATOR_KEY), OPERATOR_KEY)], roles, OPERATOR_KEY, "roles")
    name: str
    spec: JsonValue
    for name, spec in _node(registry.get(COMMANDS_KEY), COMMANDS_KEY).items():
        where: str = f"{COMMANDS_KEY}/{name}"
        rule: dict[str, JsonValue] = _node(spec, where)
        _flag(rule.get("writes"), where + "/writes")
        if rule.get("anyRole") is True and "roles" not in rule:
            continue
        if "anyRole" in rule:
            message: str = f"matrix contract: {where} must state anyRole true or roles, not both"
            raise SchemaShapeError(message)
        _subset(_strings(rule.get("roles"), where + "/roles"), roles, where + "/roles", "roles")
    return roles


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """The names the registry declares, each list in registry order."""

    entry_kinds: list[str]
    relationship_kinds: list[str]
    families: list[str]
    roles: list[str]
    sides: list[str]


def _checked(schema: Mapping[str, JsonValue], registry: Mapping[str, JsonValue]) -> Vocabulary:
    """Check the schema and the registry against each other and name what they declare.

    A schema or a registry that is missing a part of the contract or contradicts itself raises
    ``SchemaShapeError`` from the check that finds it.

    Returns:
        The entry kinds, relationship kinds, families, roles and sides.

    Raises:
        SchemaShapeError: The registry defines one of the built-in definitions.

    """
    _check_shapes(schema)
    sides: list[str] = _sides(schema)
    own: list[str] = list(_node(registry.get(DEFINITIONS), DEFINITIONS))
    if BUILT_IN_DEFINITIONS & set(own):
        message: str = f"matrix contract: the registry must not define {sorted(BUILT_IN_DEFINITIONS)}"
        raise SchemaShapeError(message)
    known: list[str] = [*own, *sorted(BUILT_IN_DEFINITIONS)]
    _check_references(registry.get(DEFINITIONS), known, DEFINITIONS)
    entry_kinds: list[str] = _check_entry_kinds(registry, known, sides)
    relationship_kinds: list[str]
    families: list[str]
    relationship_kinds, families = _check_relationship_kinds(registry, known, sides)
    return Vocabulary(
        entry_kinds=entry_kinds,
        relationship_kinds=relationship_kinds,
        families=families,
        roles=_check_commands(registry),
        sides=sides,
    )


def _tuple_line(head: str, names: Sequence[str]) -> str:
    """Render names as a tuple constant.

    Returns:
        The source of the statement; a tuple of one name keeps its trailing comma.

    """
    members: list[str] = [names[0] + ","] if len(names) == 1 else list(names)
    return _wrapped(head, "(", members, ")")


def _strings_vocabulary(alias: str, prefix: str, collection: str, values: Sequence[str]) -> tuple[str, list[str]]:
    """Render one string vocabulary as a type alias, one constant per value and a tuple.

    Returns:
        The alias line, and the constant lines with the collection last.

    """
    names: list[str] = [f"{prefix}_{_upper_snake(value)}" for value in values]
    constants: list[str] = [
        f"{name}: Final[{_literal([value])}] = {json.dumps(value)}" for name, value in zip(names, values, strict=True)
    ]
    return (
        _wrapped(f"type {alias} = Literal", "[", [json.dumps(value) for value in values], "]"),
        [*constants, _tuple_line(f"{collection}: Final[tuple[{alias}, ...]] = ", names)],
    )


def _open_vocabulary(alias: str, prefix: str, collection: str, values: Sequence[str]) -> tuple[str, list[str]]:
    """Render one open vocabulary: a NewType over str, one constant per declared value and a tuple.

    A value outside the declared ones is accepted by its form, so the type is not a Literal.

    Returns:
        The alias line, and the constant lines with the collection last.

    """
    names: list[str] = [f"{prefix}_{_upper_snake(value)}" for value in values]
    constants: list[str] = [
        f"{name}: Final[{alias}] = {alias}({json.dumps(value)})" for name, value in zip(names, values, strict=True)
    ]
    return (
        f"{alias} = NewType({json.dumps(alias)}, str)",
        [*constants, _tuple_line(f"{collection}: Final[tuple[{alias}, ...]] = ", names)],
    )


def _vocabulary_lines(vocabulary: Vocabulary) -> tuple[list[str], list[str]]:
    """Render every vocabulary the registry declares.

    Relationship kinds are an open vocabulary (``_open_vocabulary``): the registry declares the
    named ones, and any other name of the kind-name form is accepted.

    Returns:
        The type alias lines and the constant lines.

    """
    aliases: list[str] = []
    constants: list[str] = []
    alias: str
    prefix: str
    collection: str
    values: list[str]
    for alias, prefix, collection, values in (
        ("EntryKind", "KIND", "ENTRY_KINDS", vocabulary.entry_kinds),
        ("Role", "ROLE", "ROLES", vocabulary.roles),
        ("Side", "SIDE", "SIDES", vocabulary.sides),
    ):
        alias_line: str
        lines: list[str]
        alias_line, lines = _strings_vocabulary(alias, prefix, collection, values)
        aliases.append(alias_line)
        constants.extend(lines)
    open_alias: str
    open_lines: list[str]
    open_alias, open_lines = _open_vocabulary(
        "RelationshipKind",
        "REL",
        "RELATIONSHIP_KINDS",
        vocabulary.relationship_kinds,
    )
    aliases.append(open_alias)
    constants.extend(open_lines)
    names: list[str] = [f"FAMILY_{_upper_snake(family)}" for family in vocabulary.families]
    constants.extend(
        f"{name}: Final = {json.dumps(family)}" for name, family in zip(names, vocabulary.families, strict=True)
    )
    if names:
        constants.append(_tuple_line("FAMILIES: Final[tuple[str, ...]] = ", names))
    else:
        constants.append("FAMILIES: Final[tuple[str, ...]] = ()")
    return aliases, constants


def _members_line(constant: str, members: frozenset[str]) -> str:
    """Render a set of member names as a frozenset constant.

    Returns:
        The source of the statement.

    """
    return _wrapped(
        f"{constant}: Final[frozenset[str]] = frozenset(",
        "{",
        [json.dumps(name) for name in sorted(members)],
        "})",
    )


def _fixed_lines(schema: Mapping[str, JsonValue], registry: Mapping[str, JsonValue]) -> list[str]:
    """Render the values the schema and the registry fix outside the vocabularies.

    Returns:
        The constant lines.

    Raises:
        SchemaShapeError: The schema's version is not an integer.

    """
    definitions: dict[str, JsonValue] = _node(schema.get(DEFINITIONS), DEFINITIONS)
    entry_id: dict[str, JsonValue] = _node(definitions.get(ENTRY_ID_ENTRY), REF_PREFIX + ENTRY_ID_ENTRY)
    pattern: str = _raw_pattern(entry_id.get("pattern"), REF_PREFIX + ENTRY_ID_ENTRY + "/pattern")
    kind_name: dict[str, JsonValue] = _node(definitions.get(KIND_NAME_ENTRY), REF_PREFIX + KIND_NAME_ENTRY)
    kind_pattern: str = _raw_pattern(kind_name.get("pattern"), REF_PREFIX + KIND_NAME_ENTRY + "/pattern")
    version: JsonValue = _node(_node(schema.get("properties"), "properties").get("version"), "version").get("const")
    if isinstance(version, bool) or not isinstance(version, int):
        message: str = "matrix schema: properties/version/const is not an integer"
        raise SchemaShapeError(message)
    parts: list[str] = [json.dumps(part) for part in _strings(schema.get(DEFAULT_PATH_KEY), DEFAULT_PATH_KEY)]
    return [
        f"VERSION: Final[Literal[{version}]] = {version}",
        f'ENTRY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"{pattern}")',
        f'KIND_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"{kind_pattern}")',
        *[f"{constant}: Final = {json.dumps(_text(schema.get(key), key))}" for constant, key in ROOT_STRINGS],
        _wrapped("DEFAULT_MATRIX_PARTS: Final[tuple[str, ...]] = ", "(", parts, ")"),
        f"OPERATOR_ROLE: Final[Role] = ROLE_{_upper_snake(_text(registry.get(OPERATOR_KEY), OPERATOR_KEY))}",
        f"HOME_RELATIONSHIP: Final[RelationshipKind] = REL_{_upper_snake(_text(registry.get(HOME_KEY), HOME_KEY))}",
        f"STACK_KIND: Final[EntryKind] = KIND_{_upper_snake(_text(registry.get(STACK_KEY), STACK_KEY))}",
        f"AUTHORITY_SIDE: Final[Side] = SIDE_{_upper_snake(_text(schema.get(AUTHORITY_KEY), AUTHORITY_KEY))}",
        _members_line("ENTRY_MEMBERS", SHAPES[0][1]),
        _members_line("RELATIONSHIP_MEMBERS", SHAPES[1][1]),
        f"PURPOSE_MEMBER: Final = {json.dumps(PURPOSE_MEMBER)}",
        f"ENTRY_ID_REFERENCE: Final = {json.dumps(REF_PREFIX + ENTRY_ID_ENTRY)}",
        'SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "schemas" / "matrix.schema.json"',
        'REGISTRY_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "schemas" / "matrix-kinds.json"',
    ]


def render(schema: Mapping[str, JsonValue], registry: Mapping[str, JsonValue]) -> str:
    """Render the generated module for a matrix schema and a kinds registry.

    A schema or a registry that is missing a part of the contract or contradicts itself raises
    ``SchemaShapeError`` from the check that finds it.

    Returns:
        The complete Python source of matrix_contract.py.

    """
    aliases: list[str]
    constants: list[str]
    aliases, constants = _vocabulary_lines(_checked(schema, registry))
    lines: list[str] = [
        '"""GENERATED by generate_matrix_contract.py from schemas/matrix.schema.json and schemas/matrix-kinds.json.',
        "",
        "Do not edit. The matrix contract: the entry kinds, the relationship kinds and the roles the",
        "kinds registry declares, the sides, the typed form of a matrix file, and the readers that validate a file",
        "against the schema and each entry and relationship against its kind. Readers and writers import",
        "every type and value from here. Regenerate with `python generate_matrix_contract.py`; `--check`",
        "fails when this file is stale.",
        '"""',
        "",
        "import json",
        "import re",
        "import sys",
        "from dataclasses import dataclass, field",
        "from functools import cache",
        "from pathlib import Path",
        "from typing import TYPE_CHECKING, Final, Literal, NewType",
        "",
        "from jsonschema import Draft202012Validator",
        "",
        'sys.path.append(str(Path(__file__).resolve().parents[3] / "scripts" / "portfolio"))',
        "",
        "import strictschema",
        "",
        "if TYPE_CHECKING:",
        "    from collections.abc import Mapping, Sequence",
        "",
        "type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None",
        *aliases,
        "",
        'EntryId = NewType("EntryId", str)',
        "",
        *constants,
        "",
        *_fixed_lines(schema, registry),
        "",
        "",
        TAIL,
    ]
    return "\n".join(lines)


TAIL: Final[str] = '''class MatrixError(ValueError):
    """A matrix file, entry or relationship does not satisfy the contract, or the matrix refuses a request."""


@dataclass(frozen=True, slots=True)
class EntryRule:
    """What the registry declares for one entry kind."""

    id_pattern: re.Pattern[str]
    """The form of an id of the kind; for a kind with two id forms, of an entry on the side that is the authority."""
    repository_id_pattern: re.Pattern[str] | None
    """The form of the id of an entry of the kind on the other side, when the kind has two id forms."""
    side: Side | None
    """The one side an entry of the kind is always recorded with; None when it may carry either."""
    attributes: frozenset[str]
    """The attributes an entry of the kind may carry beside the common members."""
    required: frozenset[str]
    """The attributes an entry of the kind must carry."""
    purpose_required: bool
    """Whether an entry of the kind must state its purpose."""


@dataclass(frozen=True, slots=True)
class RelationshipRule:
    """What the registry declares for one relationship kind; it names no entry kinds, so it joins any two entries."""

    reverse: str
    """The name the relationship is reported under from the entry it ends at; it is computed, never stored."""
    side: Side | None
    """The one side a relationship of the kind is always recorded with; None when it may carry either."""
    attributes: frozenset[str]
    """The attributes a relationship of the kind may carry."""
    required: frozenset[str]
    """The attributes a relationship of the kind must carry."""
    key: tuple[str, ...]
    """The attributes that tell two relationships of the kind between the same two entries apart."""
    references: frozenset[str]
    """The attributes whose value is the id of an entry."""
    family: str | None
    """The group of kinds a lookup follows together, when the kind is in one."""
    max_per_start: int | None
    """The most relationships of the kind an entry may start on one side; None when there is no limit."""


@dataclass(frozen=True, slots=True)
class CommandRule:
    """What the registry declares for one sub-command of atw-matrix."""

    writes: bool
    """Whether the command changes the matrix file."""
    roles: frozenset[Role]
    """The roles that may run it."""


@dataclass(frozen=True, slots=True)
class Entry:
    """One entry of the matrix."""

    id: EntryId
    """The kind, a colon and the rest."""
    kind: EntryKind
    name: str
    side: Side
    """Which side the entry came from."""
    aliases: tuple[str, ...] = ()
    """Other names the entry is known by."""
    purpose: str = ""
    """One or two sentences that identify the entry."""
    attributes: Mapping[str, JsonValue] = field(default_factory=dict)
    """The attributes the entry's kind declares."""
    approved: bool = False
    """The approved mark: the solutions architect approved the architecture it is part of."""
    verified: bool = False
    """The verified mark: the architecture it is part of was built and its test passed."""


@dataclass(frozen=True, slots=True)
class Relationship:
    """One relationship of the matrix as one side states it, read from both ends."""

    kind: RelationshipKind
    start: EntryId
    """The entry the relationship starts from: ``from`` in the file."""
    end: EntryId
    """The entry the relationship ends at: ``to`` in the file."""
    side: Side
    """Which side states the relationship."""
    attributes: Mapping[str, JsonValue] = field(default_factory=dict)
    """The attributes the relationship's kind declares."""
    approved: bool = False
    """The approved mark: the solutions architect approved the architecture it is part of."""
    verified: bool = False
    """The verified mark: the architecture it is part of was built and its test passed."""


@dataclass(frozen=True, slots=True)
class MatrixDocument:
    """A matrix file, typed."""

    entries: tuple[Entry, ...] = ()
    relationships: tuple[Relationship, ...] = ()


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


def _load(path: Path) -> dict[str, JsonValue]:
    """Read one of the two files this contract is defined by.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The decoded file.

    Raises:
        TypeError: The file is not a JSON object.

    """
    decoded: JsonValue = json_value(json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(decoded, dict):
        message: str = f"{path} is not a JSON object"
        raise TypeError(message)
    return decoded


@cache
def load_schema() -> dict[str, JsonValue]:
    """Load the matrix JSON Schema, the generic shape of a matrix file.

    Returns:
        The schema document.

    """
    return _load(SCHEMA_PATH)


@cache
def load_registry() -> dict[str, JsonValue]:
    """Load the kinds registry, the declaration of every entry kind and relationship kind.

    Returns:
        The registry document.

    """
    return _load(REGISTRY_PATH)


def _object(value: JsonValue, where: str) -> dict[str, JsonValue]:
    """Narrow a part of the registry or the schema to an object.

    Returns:
        The object.

    Raises:
        TypeError: The part is not an object.

    """
    if not isinstance(value, dict):
        message: str = f"matrix contract: {where} is not an object"
        raise TypeError(message)
    return value


def _names(value: JsonValue, where: str) -> list[str]:
    """Narrow a part of the registry to a list of strings.

    Returns:
        The strings, in registry order.

    Raises:
        TypeError: The part is not a list of strings.

    """
    if not isinstance(value, list):
        message: str = f"matrix contract: {where} is not a list"
        raise TypeError(message)
    names: list[str] = [name for name in value if isinstance(name, str)]
    if len(names) != len(value):
        message = f"matrix contract: {where} holds a value that is not a string"
        raise TypeError(message)
    return names


def _members[T: str](value: JsonValue, choices: tuple[T, ...], where: str) -> frozenset[T]:
    """Narrow a list of wire values to members of one vocabulary.

    Returns:
        The members named.

    Raises:
        TypeError: The value names something the vocabulary does not have.

    """
    named: list[str] = _names(value, where)
    found: frozenset[T] = frozenset(choice for choice in choices if choice in named)
    if len(found) != len(set(named)):
        message: str = f"matrix contract: {where} names a value outside {choices}"
        raise TypeError(message)
    return found


def _declared_side(value: JsonValue, where: str) -> Side | None:
    """Read the one side a kind declares.

    Returns:
        The side, or None when the kind declares none.

    Raises:
        TypeError: The kind names something that is not a side.

    """
    if value is None:
        return None
    side: Side
    for side in SIDES:
        if side == value:
            return side
    message: str = f"matrix contract: {where}/side names a value outside {SIDES}"
    raise TypeError(message)


def _entry_rules() -> dict[EntryKind, EntryRule]:
    """Build the entry rules from the registry.

    Returns:
        One rule per entry kind.

    Raises:
        TypeError: A declaration is malformed.

    """
    table: dict[str, JsonValue] = _object(load_registry().get("entryKinds"), "entryKinds")
    rules: dict[EntryKind, EntryRule] = {}
    kind: EntryKind
    for kind in ENTRY_KINDS:
        where: str = f"entryKinds/{kind}"
        rule: dict[str, JsonValue] = _object(table.get(kind), where)
        pattern: JsonValue = rule.get("idPattern")
        other: JsonValue = rule.get("repositoryIdPattern")
        if not isinstance(pattern, str) or not (other is None or isinstance(other, str)):
            message: str = f"matrix contract: {where} is malformed"
            raise TypeError(message)
        required: list[str] = _names(rule.get("required"), where + "/required")
        rules[kind] = EntryRule(
            id_pattern=re.compile(pattern),
            repository_id_pattern=None if other is None else re.compile(other),
            side=_declared_side(rule.get("side"), where),
            attributes=frozenset(_object(rule.get("attributes"), where + "/attributes")),
            required=frozenset(name for name in required if name != PURPOSE_MEMBER),
            purpose_required=PURPOSE_MEMBER in required,
        )
    return rules


def _relationship_rules() -> dict[RelationshipKind, RelationshipRule]:
    """Build the relationship rules from the registry.

    Returns:
        One rule per relationship kind.

    Raises:
        TypeError: A declaration is malformed.

    """
    table: dict[str, JsonValue] = _object(load_registry().get("relationshipKinds"), "relationshipKinds")
    rules: dict[RelationshipKind, RelationshipRule] = {}
    kind: RelationshipKind
    for kind in RELATIONSHIP_KINDS:
        where: str = f"relationshipKinds/{kind}"
        rule: dict[str, JsonValue] = _object(table.get(kind), where)
        reverse: JsonValue = rule.get("reverse")
        family: JsonValue = rule.get("family")
        limit: JsonValue = rule.get("maxPerStart")
        if (
            not isinstance(reverse, str)
            or not (limit is None or (isinstance(limit, int) and not isinstance(limit, bool)))
            or not (family is None or isinstance(family, str))
        ):
            message: str = f"matrix contract: {where} is malformed"
            raise TypeError(message)
        attributes: dict[str, JsonValue] = _object(rule.get("attributes"), where + "/attributes")
        rules[kind] = RelationshipRule(
            reverse=reverse,
            side=_declared_side(rule.get("side"), where),
            attributes=frozenset(attributes),
            required=frozenset(_names(rule.get("required"), where + "/required")),
            key=tuple(_names(rule.get("key"), where + "/key")),
            references=frozenset(
                name
                for name, fragment in attributes.items()
                if isinstance(fragment, dict) and fragment.get("$ref") == ENTRY_ID_REFERENCE
            ),
            family=family,
            max_per_start=limit,
        )
    return rules


def _command_rules() -> dict[str, CommandRule]:
    """Build the command rules from the registry's command table.

    Returns:
        One rule per sub-command of atw-matrix.

    Raises:
        TypeError: A rule is malformed.

    """
    rules: dict[str, CommandRule] = {}
    name: str
    rule: JsonValue
    for name, rule in _object(load_registry().get("commands"), "commands").items():
        writes: JsonValue = rule.get("writes") if isinstance(rule, dict) else None
        if not isinstance(rule, dict) or not isinstance(writes, bool):
            message: str = f"matrix contract: commands/{name} is malformed"
            raise TypeError(message)
        everyone: bool = rule.get("anyRole") is True
        roles: frozenset[Role] = frozenset(ROLES) if everyone else _members(rule.get("roles"), ROLES, name)
        rules[name] = CommandRule(writes=writes, roles=roles)
    return rules


ENTRY_RULES: Final[dict[EntryKind, EntryRule]] = _entry_rules()
RELATIONSHIP_RULES: Final[dict[RelationshipKind, RelationshipRule]] = _relationship_rules()
COMMAND_RULES: Final[dict[str, CommandRule]] = _command_rules()
REVERSE_NAMES: Final[dict[str, RelationshipKind]] = {rule.reverse: kind for kind, rule in RELATIONSHIP_RULES.items()}
"""The relationship kind each reverse name of a declared kind reports."""
UNDECLARED_REVERSE_SUFFIX: Final = "Reverse"
"""What follows the name of a relationship kind the registry does not declare in its reverse name."""


def entry_kind(text: str) -> EntryKind:
    """Accept a string as an entry kind when the registry declares it.

    Returns:
        The kind.

    Raises:
        MatrixError: The registry declares no such entry kind.

    """
    kind: EntryKind
    for kind in ENTRY_KINDS:
        if kind == text:
            return kind
    message: str = f"{text!r} is not an entry kind; the kinds are {', '.join(ENTRY_KINDS)}"
    raise MatrixError(message)


def relationship_kind(text: str) -> RelationshipKind:
    """Accept a string as a relationship kind by its form.

    The registry declares the named kinds, with their reverse names and attributes; any other
    name of the kind-name form is a kind too, so a link of a new type needs no declaration. A
    reverse name of a declared kind is not accepted: the link is stated from its other end.

    Returns:
        The kind.

    Raises:
        MatrixError: The text is not of the kind-name form, or it is the reverse name of a
            declared kind.

    """
    message: str
    if KIND_NAME_PATTERN.fullmatch(text) is None:
        message = (
            f"{text!r} is not a relationship kind: a kind is lowerCamelCase letters ({KIND_NAME_PATTERN.pattern}); "
            f"the declared kinds are {', '.join(RELATIONSHIP_KINDS)}"
        )
        raise MatrixError(message)
    if text in REVERSE_NAMES:
        declared: RelationshipKind = REVERSE_NAMES[text]
        message = f"{text!r} is the reverse name of {declared}; state the link from its other end as {declared}"
        raise MatrixError(message)
    return RelationshipKind(text)


def relationship_rule(kind: RelationshipKind) -> RelationshipRule:
    """Name what the registry declares for a relationship kind.

    Returns:
        The declared rule; for a kind the registry does not declare, a rule with no attributes,
        no key, no side, no family and no limit, reported from its end under the kind's name
        followed by ``UNDECLARED_REVERSE_SUFFIX``.

    """
    declared: RelationshipRule | None = RELATIONSHIP_RULES.get(kind)
    if declared is not None:
        return declared
    return RelationshipRule(
        reverse=kind + UNDECLARED_REVERSE_SUFFIX,
        side=None,
        attributes=frozenset(),
        required=frozenset(),
        key=(),
        references=frozenset(),
        family=None,
        max_per_start=None,
    )


def as_side(text: str) -> Side:
    """Accept a string as a side when the schema lists it.

    Returns:
        The side.

    Raises:
        MatrixError: The schema lists no such side.

    """
    side: Side
    for side in SIDES:
        if side == text:
            return side
    message: str = f"{text!r} is not a side; the sides are {', '.join(SIDES)}"
    raise MatrixError(message)


def id_pattern(kind: EntryKind, side: Side) -> re.Pattern[str]:
    """Name the form the id of an entry has.

    Returns:
        The kind's id pattern; for a kind with two id forms and an entry that is not on the side
        that is the authority, the kind's other pattern.

    """
    rule: EntryRule = ENTRY_RULES[kind]
    if side != AUTHORITY_SIDE and rule.repository_id_pattern is not None:
        return rule.repository_id_pattern
    return rule.id_pattern


def family_kinds(family: str) -> frozenset[RelationshipKind]:
    """Name the relationship kinds of one family.

    Returns:
        Every kind the registry declares with that family; empty when it declares none.

    """
    return frozenset(kind for kind, rule in RELATIONSHIP_RULES.items() if rule.family == family)


def _definitions() -> dict[str, JsonValue]:
    """Assemble the definitions an attribute of a kind may reference.

    Returns:
        The registry's own definitions and the entry id.

    """
    return {
        **_object(load_registry().get("$defs"), "$defs"),
        "entryId": _object(load_schema().get("$defs"), "$defs").get("entryId"),
    }


def _attribute_validator(table: str, kind: str, required: Sequence[str]) -> Draft202012Validator:
    """Build the validator of the attributes one kind declares.

    Returns:
        A validator that accepts exactly the declared attributes, with the required ones present;
        for a relationship kind the registry does not declare, one that accepts no attribute.

    """
    declared: JsonValue = _object(load_registry().get(table), table).get(kind, {"attributes": {}})
    rule: dict[str, JsonValue] = _object(declared, f"{table}/{kind}")
    schema: dict[str, JsonValue] = {
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": _object(rule.get("attributes"), f"{table}/{kind}/attributes"),
        "$defs": _definitions(),
    }
    one: list[str] = _names(rule.get("requiredOne", []), f"{table}/{kind}/requiredOne")
    if one:
        schema["oneOf"] = [{"required": [name]} for name in one]
    schema["title"] = f"{REGISTRY_PATH.name}#/{table}/{kind}/attributes"
    return Draft202012Validator(schema)


@cache
def _entry_validator(kind: EntryKind) -> Draft202012Validator:
    """Build the validator of the attributes of one entry kind.

    Returns:
        The validator.

    """
    return _attribute_validator("entryKinds", kind, sorted(ENTRY_RULES[kind].required))


@cache
def _relationship_validator(kind: RelationshipKind) -> Draft202012Validator:
    """Build the validator of the attributes of one relationship kind.

    Returns:
        The validator.

    """
    return _attribute_validator("relationshipKinds", kind, sorted(relationship_rule(kind).required))


@cache
def _shape_validator(definition: str | None) -> Draft202012Validator:
    """Build the validator of a matrix file, or of one $defs entry of its schema.

    Returns:
        The validator.

    Raises:
        ValueError: The schema defines no such entry.

    """
    schema: dict[str, JsonValue] = load_schema()
    if definition is None:
        return Draft202012Validator(schema)
    definitions: dict[str, JsonValue] = _object(schema.get("$defs"), "$defs")
    if definition not in definitions:
        message: str = f"matrix schema defines no {definition!r}"
        raise ValueError(message)
    return Draft202012Validator({"$ref": "#/$defs/" + definition, "$defs": definitions})


def _failures(
    validator: Draft202012Validator,
    value: object,
    location: Path | None,
    definition: str | None,
) -> list[str]:
    """Describe every way a value fails a validator, as ``strictschema.explain_all`` states each one.

    Args:
        validator: The validator; its schema is the one the failures are located in.
        value: The decoded value.
        location: The schema file the validator's schema is, or None for a schema assembled here.
        definition: The definition validated against, named when a failure's pointer names none.

    Returns:
        One line per failure, in path order: the path, the field names it is about, the fields
        allowed there, the schema rule quoted and where the rule is; empty when the value conforms.

    """
    root: JsonValue = validator.schema if isinstance(validator.schema, dict) else None
    return strictschema.explain_all(validator.iter_errors(value), root=root, location=location, definition=definition)


def _attribute_failures(validator: Draft202012Validator, value: object) -> list[str]:
    """Describe every way the attributes of an entry or a relationship fail their kind.

    The validator's schema is assembled from the kinds registry, so each failure names the
    registry's attributes of the kind (the schema's ``title``) as its definition.

    Returns:
        One line per failure, as :func:`_failures` states it.

    """
    title: object = validator.schema.get("title") if isinstance(validator.schema, dict) else None
    return _failures(validator, value, None, title if isinstance(title, str) else None)


def schema_problems(value: object, definition: str | None = None) -> list[str]:
    """Describe every way a value fails the schema, or one $defs entry of it.

    Args:
        value: The decoded document.
        definition: The $defs entry to validate against; None validates a matrix file.

    Returns:
        One line per failure, in path order, as ``strictschema.explain_all`` states it; empty when
        the value conforms.

    """
    return _failures(_shape_validator(definition), value, SCHEMA_PATH, definition)


def definition_problems(name: str, value: object) -> list[str]:
    """Check a value against one definition of the kinds registry, such as ``resourceType``.

    Args:
        name: The definition's name under the registry's ``$defs``.
        value: The decoded value.

    Returns:
        One line per failure, as ``strictschema.explain_all`` states it; empty when the value conforms.

    Raises:
        ValueError: The registry defines no such definition.

    """
    definitions: dict[str, JsonValue] = _definitions()
    if name not in definitions:
        message: str = f"the matrix kinds registry defines no {name!r}"
        raise ValueError(message)
    validator: Draft202012Validator = Draft202012Validator({"$ref": "#/$defs/" + name, "$defs": definitions})
    return _failures(validator, value, REGISTRY_PATH, name)


def entry_problems(entry: Entry) -> list[str]:
    """Check one entry against the kind the registry declares for it.

    Returns:
        One sentence per way the entry breaks its kind: an id of another form or another kind, or
        of the form the kind's entries have on the other side; a side the kind is never recorded
        with; an empty name, an empty or repeated alias, a missing purpose, an attribute the kind
        does not declare or a value it does not allow. Empty when the entry conforms.

    """
    rule: EntryRule = ENTRY_RULES[entry.kind]
    pattern: re.Pattern[str] = id_pattern(entry.kind, entry.side)
    problems: list[str] = []
    if pattern.search(entry.id) is None:
        problems.append(f"{entry.id}: the id of a {entry.kind} on the {entry.side} side must match {pattern.pattern}")
    if rule.side is not None and entry.side != rule.side:
        problems.append(f"{entry.id}: a {entry.kind} is always on the {rule.side} side, not the {entry.side} side")
    if not entry.name.strip():
        problems.append(f"{entry.id}: the name is empty")
    if len(set(entry.aliases)) != len(entry.aliases) or not all(alias.strip() for alias in entry.aliases):
        problems.append(f"{entry.id}: an alias is empty or repeated")
    if rule.purpose_required and not entry.purpose.strip():
        problems.append(f"{entry.id}: a {entry.kind} must state its purpose")
    problems.extend(
        f"{entry.id}: {failure}"
        for failure in _attribute_failures(_entry_validator(entry.kind), dict(entry.attributes))
    )
    return problems


def relationship_key(relationship: Relationship) -> str:
    """Render the values of the key attributes of one relationship.

    Returns:
        Text that is equal for two relationships of one kind exactly when their key attributes are.

    """
    values: list[JsonValue] = [relationship.attributes.get(name) for name in relationship_rule(relationship.kind).key]
    return json.dumps(values, sort_keys=True, ensure_ascii=False)


def relationship_label(relationship: Relationship) -> str:
    """Name one relationship in a message.

    Returns:
        The start, the kind, the end and the side that states it.

    """
    return f"{relationship.start} {relationship.kind} {relationship.end} ({relationship.side})"


def relationship_problems(relationship: Relationship) -> list[str]:
    """Check one relationship against the kind the registry declares for it.

    Whether its ends exist is the store's to check; it joins any two entries.

    Returns:
        One sentence per attribute the kind does not declare or value it does not allow, for a
        side the kind is never recorded with. Empty when the relationship conforms.

    """
    rule: RelationshipRule = relationship_rule(relationship.kind)
    label: str = relationship_label(relationship)
    problems: list[str] = []
    if rule.side is not None and relationship.side != rule.side:
        problems.append(f"{label}: a {relationship.kind} relationship is always on the {rule.side} side")
    problems.extend(
        f"{label}: {failure}"
        for failure in _attribute_failures(_relationship_validator(relationship.kind), dict(relationship.attributes))
    )
    return problems


def _raise_unless_shaped(value: object, definition: str | None, where: str) -> dict[str, JsonValue]:
    """Require a decoded value to have one of the schema's shapes, and type it.

    Returns:
        The value as a JSON object.

    Raises:
        MatrixError: The value does not have the shape, or holds something JSON does not.

    """
    problems: list[str] = schema_problems(value, definition)
    message: str
    if problems:
        rule: str = SCHEMA_PATH.name + (f"#/$defs/{definition}" if definition else "")
        message = (
            f"{where} does not satisfy the matrix schema ({rule}): "
            f"{len(problems)} problem(s), one per line below\\n" + "\\n".join(problems)
        )
        raise MatrixError(message)
    try:
        typed: JsonValue = json_value(value)
    except TypeError as error:
        message = f"{where} is not JSON: {error}"
        raise MatrixError(message) from error
    if not isinstance(typed, dict):
        message = f"{where} is not a JSON object"
        raise MatrixError(message)
    return typed


def _string(value: JsonValue, where: str) -> str:
    """Narrow a member of a matrix file to a string.

    Returns:
        The string.

    Raises:
        MatrixError: The member is not a string.

    """
    if not isinstance(value, str):
        message: str = f"{where} is not a string"
        raise MatrixError(message)
    return value


def _string_tuple(value: JsonValue, where: str) -> tuple[str, ...]:
    """Narrow a member of a matrix file to a list of strings.

    Returns:
        The strings, in file order.

    Raises:
        MatrixError: The member is not a list.

    """
    if not isinstance(value, list):
        message: str = f"{where} is not a list"
        raise MatrixError(message)
    return tuple(_string(item, where) for item in value)


def _mark(value: JsonValue, where: str, name: str) -> bool:
    """Read the approved or the verified mark of an entry or a relationship.

    Returns:
        Whether the mark is set; an absent member is not set.

    Raises:
        MatrixError: The member is present and is not a boolean.

    """
    if value is None:
        return False
    if not isinstance(value, bool):
        message: str = f"{where}: {name} is not a boolean"
        raise MatrixError(message)
    return value


def _typed_entry(raw: Mapping[str, JsonValue], where: str) -> Entry:
    """Build an entry from a JSON object that has the schema's Entry shape.

    Returns:
        The entry.

    """
    return Entry(
        id=EntryId(_string(raw.get("id"), f"{where}: id")),
        kind=entry_kind(_string(raw.get("kind"), f"{where}: kind")),
        name=_string(raw.get("name"), f"{where}: name"),
        side=as_side(_string(raw.get("side"), f"{where}: side")),
        aliases=_string_tuple(raw.get("aliases"), f"{where}: aliases"),
        purpose=_string(raw.get("purpose"), f"{where}: purpose"),
        attributes={name: value for name, value in raw.items() if name not in ENTRY_MEMBERS},
        approved=_mark(raw.get("approved"), where, "approved"),
        verified=_mark(raw.get("verified"), where, "verified"),
    )


def _typed_relationship(raw: Mapping[str, JsonValue], where: str) -> Relationship:
    """Build a relationship from a JSON object that has the schema's Relationship shape.

    Returns:
        The relationship.

    """
    return Relationship(
        kind=relationship_kind(_string(raw.get("kind"), f"{where}: kind")),
        start=EntryId(_string(raw.get("from"), f"{where}: from")),
        end=EntryId(_string(raw.get("to"), f"{where}: to")),
        side=as_side(_string(raw.get("side"), f"{where}: side")),
        attributes={name: value for name, value in raw.items() if name not in RELATIONSHIP_MEMBERS},
        approved=_mark(raw.get("approved"), where, "approved"),
        verified=_mark(raw.get("verified"), where, "verified"),
    )


def parse_entry(value: object, where: str = "entry") -> Entry:
    """Read one entry from decoded JSON.

    The entry has the generic shape and a kind the registry declares; whether it satisfies that
    kind is for :func:`entry_problems` to say. A value of another shape, or of an undeclared
    kind, raises ``MatrixError``.

    Args:
        value: The decoded entry, as a matrix file holds it.
        where: What to call the entry in an error.

    Returns:
        The entry.

    """
    return _typed_entry(_raise_unless_shaped(value, "Entry", where), where)


def parse_relationship(value: object, where: str = "relationship") -> Relationship:
    """Read one relationship from decoded JSON.

    The relationship has the generic shape and a kind the registry declares; whether it satisfies
    that kind is for :func:`relationship_problems` to say. A value of another shape, or of an
    undeclared kind, raises ``MatrixError``.

    Args:
        value: The decoded relationship, as a matrix file holds it.
        where: What to call the relationship in an error.

    Returns:
        The relationship.

    """
    return _typed_relationship(_raise_unless_shaped(value, "Relationship", where), where)


def parse_document(value: object, where: str = "matrix") -> MatrixDocument:
    """Read a matrix file from decoded JSON.

    The file has the generic shape and every entry and relationship is of a kind the registry
    declares; a file of another shape or with an undeclared kind raises ``MatrixError`` from the
    reader that finds it. Whether each entry and relationship satisfies its kind is for
    :func:`entry_problems` and :func:`relationship_problems` to say.

    Args:
        value: The decoded file.
        where: What to call the file in an error.

    Returns:
        The file, typed.

    Raises:
        MatrixError: An entry is filed under an id that is not its own.

    """
    raw: dict[str, JsonValue] = _raise_unless_shaped(value, None, where)
    entries: list[Entry] = []
    key: str
    item: JsonValue
    for key, item in _object(raw.get("entries"), "entries").items():
        entry: Entry = _typed_entry(_object(item, key), f"{where}: the entry {key}")
        if entry.id != key:
            message: str = f"{where}: the entry filed under {key} says its id is {entry.id}"
            raise MatrixError(message)
        entries.append(entry)
    listed: JsonValue = raw.get("relationships")
    relationships: list[Relationship] = [
        _typed_relationship(_object(item, "relationships"), f"{where}: relationship {index}")
        for index, item in enumerate(listed if isinstance(listed, list) else [])
    ]
    return MatrixDocument(entries=tuple(entries), relationships=tuple(relationships))


def entry_json(entry: Entry) -> dict[str, JsonValue]:
    """Render one entry as a matrix file holds it.

    Returns:
        The common members, the entry's attributes and, when set, the approved and verified marks.

    """
    aliases: list[JsonValue] = list(entry.aliases)
    rendered: dict[str, JsonValue] = {
        **entry.attributes,
        "id": entry.id,
        "kind": entry.kind,
        "name": entry.name,
        "side": entry.side,
        "aliases": aliases,
        "purpose": entry.purpose,
    }
    if entry.approved:
        rendered["approved"] = True
    if entry.verified:
        rendered["verified"] = True
    return rendered


def relationship_json(relationship: Relationship) -> dict[str, JsonValue]:
    """Render one relationship as a matrix file holds it.

    Returns:
        The kind, both ends, the side, the relationship's attributes and, when set, the approved and
        verified marks.

    """
    rendered: dict[str, JsonValue] = {
        **relationship.attributes,
        "kind": relationship.kind,
        "from": relationship.start,
        "to": relationship.end,
        "side": relationship.side,
    }
    if relationship.approved:
        rendered["approved"] = True
    if relationship.verified:
        rendered["verified"] = True
    return rendered


def relationship_order(relationship: Relationship) -> tuple[str, str, str, str, str]:
    """Give the position of one relationship in a matrix file.

    Returns:
        The start, the kind, the end, the key and the side, which a file's relationships are sorted by.

    """
    return (
        relationship.start,
        relationship.kind,
        relationship.end,
        relationship_key(relationship),
        relationship.side,
    )


def document_json(document: MatrixDocument) -> dict[str, JsonValue]:
    """Render a matrix as its file holds it.

    Returns:
        The three members of the file, with the relationships in file order.

    """
    entries: dict[str, JsonValue] = {entry.id: entry_json(entry) for entry in document.entries}
    relationships: list[JsonValue] = [
        relationship_json(relationship) for relationship in sorted(document.relationships, key=relationship_order)
    ]
    return {"version": VERSION, "entries": entries, "relationships": relationships}
'''


def _load(path: Path) -> dict[str, JsonValue]:
    """Read one of the two source files.

    A read failure (OSError) or a decode failure (json.JSONDecodeError) propagates unchanged.

    Returns:
        The decoded file.

    """
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    return _node(_json_value(decoded), str(path))


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
    expected: str = render(_load(SCHEMA_PATH), _load(REGISTRY_PATH))
    if check:
        current: str | None = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.is_file() else None
        if current != expected:
            sys.stderr.write(f"{OUTPUT_PATH} is stale against its sources; run {Path(__file__).name}\n")
            return 1
        return 0
    OUTPUT_PATH.write_text(expected, encoding="utf-8")
    sys.stdout.write(f"wrote {OUTPUT_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
