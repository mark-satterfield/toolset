"""JSON Schema validation whose numeric types match the pipeline's runtime contracts.

jsonschema's stock type checkers accept ``1.0`` as an ``integer`` and ``inf``/``nan`` as a
``number``. The pipeline's typed consumers reject both, so a value a schema accepted could
still fail the consumer it was validated for. This module is the one place every schema site
builds its validator: ``integer`` is exactly ``int`` (never ``bool`` or ``float``) and
``number`` is a finite ``int`` or ``float`` (never ``bool``).

Every ``$ref`` resolves from local disk only. The registry holds every ``*.schema.json`` file in
the plugin, keyed by its ``file:`` URI, so a relative reference such as
``architecture-common.schema.json#/$defs/EvidenceRef`` resolves against the referring file's own
location. Nothing is ever retrieved over the network: a reference the registry cannot resolve
raises ``referencing.exceptions.Unresolvable`` before any value is validated.
"""

from __future__ import annotations

import functools
import json
import math
import re
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, TypeIs
from urllib.parse import urldefrag, urljoin

from jsonschema import Draft202012Validator, SchemaError, TypeChecker, ValidationError, validators
from jsonschema.exceptions import best_match
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

if TYPE_CHECKING:
    from contracts import JsonValue
    from jsonschema.protocols import Validator
    from referencing.jsonschema import Schema, SchemaRegistry, SchemaResource

PLUGIN_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
"""The plugin whose ``*.schema.json`` files make up the reference registry."""
_DATA_KEYWORDS: Final[frozenset[str]] = frozenset({"const", "default", "enum", "examples"})
"""Keywords whose values are instance data, never subschemas, so a ``$ref`` in them is not a reference."""


class _Extend(Protocol):
    """The typed shape of ``jsonschema.validators.extend``, which its stubs leave untyped."""

    def __call__(self, validator: type[Validator], *, type_checker: TypeChecker) -> type[Validator]:
        """Return a validator class that is ``validator`` with ``type_checker`` in place."""
        ...


_EXTEND: _Extend = validators.extend


def _is_integer(_checker: TypeChecker, instance: object) -> bool:
    """Decide the JSON Schema ``integer`` type.

    Returns:
        Whether ``instance`` is an ``int`` that is not a ``bool``.

    """
    return type(instance) is int


def _is_number(_checker: TypeChecker, instance: object) -> bool:
    """Decide the JSON Schema ``number`` type.

    Returns:
        Whether ``instance`` is an ``int`` or a finite ``float``, never a ``bool``.

    """
    if type(instance) is int:
        return True
    return type(instance) is float and math.isfinite(instance)


def _document(schema: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Copy ``schema`` into a plain dict after checking it is a mapping.

    Returns:
        The schema as a dict.

    Raises:
        TypeError: When ``schema`` is not a mapping.

    """
    if not isinstance(schema, Mapping):
        message: str = f"schema must be a JSON object, got {type(schema).__name__}"
        raise TypeError(message)
    return dict(schema)


def _schema_files(root: Path) -> list[Path]:
    """List the schema files under ``root`` in a stable order.

    Returns:
        Every ``*.schema.json`` file below ``root``, resolved and sorted.

    """
    return sorted(path.resolve() for path in root.rglob("*.schema.json"))


@functools.cache
def registry() -> SchemaRegistry:
    """Build the local reference registry from every schema file in the plugin.

    Each file is registered under its ``file:`` URI, and also under its own ``$id`` when it
    declares one. The registry has no retrieval function, so an unregistered URI is never
    fetched: looking it up raises ``referencing.exceptions.Unresolvable``.

    Returns:
        The registry, built once per process.

    Raises:
        TypeError: A schema file does not hold a JSON object or boolean.

    """
    entries: list[tuple[str, SchemaResource]] = []
    path: Path
    for path in _schema_files(PLUGIN_ROOT):
        contents: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(contents, dict | bool):
            message: str = f"{path}: a schema must be a JSON object or boolean, got {type(contents).__name__}"
            raise TypeError(message)
        resource: SchemaResource = Resource.from_contents(contents, default_specification=DRAFT202012)
        entries.append((path.as_uri(), resource))
        identifier: str | None = resource.id()
        if identifier:
            entries.append((identifier, resource))
    empty: SchemaRegistry = Registry()
    return empty.with_resources(entries)


def _references(node: JsonValue) -> Iterator[str]:
    """Yield every ``$ref`` string in a schema node, skipping instance-data keywords.

    Yields:
        Each reference string, in document order.

    """
    if isinstance(node, dict):
        key: str
        item: JsonValue
        for key, item in node.items():
            if key == "$ref" and isinstance(item, str):
                yield item
            elif key not in _DATA_KEYWORDS:
                yield from _references(item)
    elif isinstance(node, list):
        element: JsonValue
        for element in node:
            yield from _references(element)


def _resolved_json(contents: Schema, reference: str) -> JsonValue:
    """Narrow a resolved schema to a decoded JSON value.

    Returns:
        ``contents`` as a JSON value.

    Raises:
        TypeError: ``contents`` is not a decoded JSON value.

    """
    if not _is_json(contents):
        message: str = f"{reference}: resolved to a non-JSON value of type {type(contents).__name__}"
        raise TypeError(message)
    return contents


def check_references(document: Mapping[str, JsonValue]) -> int:
    """Resolve every ``$ref`` reachable from ``document``, following references across files.

    The document's base URI is its ``$id`` (``validate`` and ``validator`` set it from
    ``location``); without one, only references inside the document itself can resolve. A
    reference that names a file or location the local registry does not hold propagates
    ``referencing.exceptions.Unresolvable`` from the lookup.

    Args:
        document: The root schema.

    Returns:
        The number of distinct references resolved.

    """
    root: dict[str, JsonValue] = _document(document)
    resource: SchemaResource = Resource.from_contents(root, default_specification=DRAFT202012)
    base: str = resource.id() or ""
    local: SchemaRegistry = registry().with_resource(base, resource)
    pending: list[tuple[JsonValue, str]] = [(root, base)]
    seen: set[str] = set()
    while pending:
        node: JsonValue
        node_base: str
        node, node_base = pending.pop()
        reference: str
        for reference in _references(node):
            target: str = urljoin(node_base, reference)
            if target in seen:
                continue
            seen.add(target)
            resolved: Schema = local.resolver(node_base).lookup(reference).contents
            pending.append((_resolved_json(resolved, reference), urldefrag(target).url))
    return len(seen)


def _located(schema: Mapping[str, JsonValue], location: Path | None) -> dict[str, JsonValue]:
    """Copy ``schema`` and give it the base URI of the file it was read from.

    Returns:
        The schema as a dict; with ``location`` and no ``$id`` of its own, its ``$id`` is
        ``location``'s ``file:`` URI, so relative references resolve against that file.

    Raises:
        TypeError: ``location`` is neither a path nor ``None``.

    """
    document: dict[str, JsonValue] = _document(schema)
    if location is None or "$id" in document:
        return document
    if not isinstance(location, Path):
        message: str = f"location must be a Path, got {type(location).__name__}"
        raise TypeError(message)
    return {"$id": location.resolve().as_uri(), **document}


def _strict_class(document: dict[str, JsonValue]) -> type[Validator]:
    """Return the dialect class ``document`` declares, with strict numeric type checks.

    Returns:
        A validator class: the declared dialect (Draft 2020-12 when absent) whose
        ``integer`` and ``number`` checks are strict.

    """
    dialect: type[Validator] = validators.validator_for(document, default=Draft202012Validator)
    checker: TypeChecker = dialect.TYPE_CHECKER.redefine_many({"integer": _is_integer, "number": _is_number})
    return _EXTEND(dialect, type_checker=checker)


def validator(schema: Mapping[str, JsonValue], *, location: Path | None = None) -> Validator:
    """Build a strict validator for ``schema`` in the dialect the schema declares.

    The dialect comes from the schema's ``$schema`` (Draft 2020-12 when absent). Its type
    checker is replaced for ``integer`` and ``number`` only; every other keyword keeps the
    dialect's own behavior. References resolve from the local registry only. The schema itself
    is not checked; call ``validate`` for that.

    Args:
        schema: The JSON Schema document.
        location: The file ``schema`` was read from; relative references resolve against it.

    Returns:
        A validator instance for ``schema``.

    """
    document: dict[str, JsonValue] = _located(schema, location)
    return _strict_class(document)(document, registry=registry())


def _is_json(value: object) -> TypeIs[JsonValue]:
    """Decide whether ``value`` is a decoded JSON value with string object keys.

    Returns:
        Whether ``value`` is ``None``, a ``bool``, ``int``, ``float`` or ``str``, or a list or
        dict made only of such values with ``str`` keys.

    """
    if value is None or isinstance(value, bool | int | float | str):
        return True
    if isinstance(value, list):
        return all(_is_json(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json(item) for key, item in value.items())
    return False


def validate(value: object, schema: Mapping[str, JsonValue], *, location: Path | None = None) -> None:
    """Check ``schema`` itself, then validate ``value`` against it with strict numeric types.

    Behaves as ``jsonschema.validate`` does: the schema is checked against its dialect's
    meta-schema first and a ``jsonschema.SchemaError`` is raised for the most relevant schema
    problem; then every reference reachable from the schema is resolved from the local registry
    (``check_references``), so an unresolvable reference raises
    ``referencing.exceptions.Unresolvable`` before ``value`` is looked at; then a
    ``jsonschema.ValidationError`` is raised for the most relevant problem in ``value``. Only
    that last error is a problem with ``value``; every other exception is a problem with the
    schema or the validation machinery.

    Args:
        value: The decoded JSON value to validate.
        schema: The JSON Schema document.
        location: The file ``schema`` was read from; relative references resolve against it.

    Raises:
        TypeError: When ``value`` is not a decoded JSON value.

    """
    document: dict[str, JsonValue] = _located(schema, location)
    if not _is_json(value):
        message: str = f"value must be a decoded JSON value, got {type(value).__name__}"
        raise TypeError(message)
    strict: type[Validator] = _strict_class(document)
    meta: dict[str, JsonValue] = dict(strict.META_SCHEMA)
    meta_checker: Validator = validators.validator_for(meta, default=strict)(meta, registry=registry())
    schema_problem: ValidationError | None = best_match(meta_checker.iter_errors(document))
    if schema_problem is not None:
        schema_error: SchemaError = SchemaError.create_from(schema_problem)
        raise schema_error
    check_references(document)
    checked: Validator = strict(document, registry=registry())
    problem: ValidationError | None = best_match(checked.iter_errors(value))
    if problem is not None:
        raise problem


class SchemaProblemsError(ValueError):
    """A value fails its schema: a one-line headline, then every problem ``explain_all`` states."""

    def __init__(self, where: str, rule: str, problems: list[str]) -> None:
        """Name what was refused and the rule it fails; the message is the headline, then one problem per line.

        Args:
            where: What was refused, such as the file that holds the value.
            rule: The schema the value fails, such as its file and definition.
            problems: The problems, as ``explain_all`` states them.

        """
        self.headline: str = f"{where} does not satisfy {rule}: {len(problems)} problem(s), one per line below"
        self.problems: list[str] = problems
        super().__init__("\n".join([self.headline, *problems]))


EXPLAINED_IN_FULL: Final[int] = 40
"""The most problems ``explain_all`` states in full; each problem after them keeps its path and field names."""
_QUOTE_LIMIT: Final[int] = 400
"""The most characters of a quoted schema rule or given value one explained problem carries."""
_BRANCHES_STATED: Final[int] = 12
"""The most failures inside ``anyOf`` or ``oneOf`` branches one explained problem names."""
_DEFINITION_KEYS: Final[frozenset[str]] = frozenset({"$defs", "definitions"})
"""The keywords whose entries are a schema's named definitions."""
_PROPERTY_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "additionalProperties",
        "dependentRequired",
        "maxProperties",
        "minProperties",
        "propertyNames",
        "required",
        "unevaluatedProperties",
    },
)
"""The keywords whose failure is about which fields an object holds, so the allowed names help."""


def _quoted(value: object) -> str:
    """Quote a schema rule or a given value as compact JSON, cut at ``_QUOTE_LIMIT`` characters.

    Returns:
        The JSON text, ending in ``…`` when it was cut.

    """
    text: str = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return text if len(text) <= _QUOTE_LIMIT else text[: _QUOTE_LIMIT - 1] + "…"


def _pointer_part(part: str | int) -> str:
    """Escape one JSON pointer segment.

    Returns:
        The segment with ``~`` and ``/`` escaped.

    """
    return str(part).replace("~", "~0").replace("/", "~1")


def _schema_nodes(root: JsonValue) -> dict[int, str]:
    """Index every object node of a schema document by identity.

    Returns:
        The JSON pointer of each dict in ``root``, keyed by ``id()``; the first pointer wins.

    """
    found: dict[int, str] = {}
    pending: list[tuple[JsonValue, str]] = [(root, "")]
    while pending:
        node: JsonValue
        pointer: str
        node, pointer = pending.pop()
        if isinstance(node, dict):
            found.setdefault(id(node), pointer)
            pending.extend((item, f"{pointer}/{_pointer_part(key)}") for key, item in node.items())
        elif isinstance(node, list):
            pending.extend((item, f"{pointer}/{index}") for index, item in enumerate(node))
    return found


def _definition_of(pointer: str) -> str | None:
    """Name the definition a JSON pointer into a schema lies in.

    Returns:
        The last ``$defs`` (or ``definitions``) entry the pointer passes through, or None.

    """
    parts: list[str] = pointer.split("/")
    named: list[str] = [parts[index + 1] for index, part in enumerate(parts[:-1]) if part in _DEFINITION_KEYS]
    return named[-1].replace("~1", "/").replace("~0", "~") if named else None


def _object_names(error: ValidationError) -> list[str]:
    """Name the fields an object-shape failure is about, as the schema rule decides them.

    Returns:
        For ``additionalProperties`` and ``unevaluatedProperties``, every field the object holds
        that the subschema's ``properties`` and ``patternProperties`` do not allow; for
        ``required``, every required field the object lacks; otherwise nothing.

    """
    instance: object = error.instance
    schema: object = error.schema
    if not isinstance(instance, dict) or not isinstance(schema, dict):
        return []
    if error.validator == "required" and isinstance(error.validator_value, list):
        return [str(name) for name in error.validator_value if name not in instance]
    if error.validator in {"additionalProperties", "unevaluatedProperties"}:
        properties: object = schema.get("properties") or {}
        patterns: object = schema.get("patternProperties") or {}
        known: set[str] = set(properties) if isinstance(properties, dict) else set()
        expressions: list[str] = [str(pattern) for pattern in patterns] if isinstance(patterns, dict) else []
        return [
            str(name)
            for name in instance
            if name not in known and not any(re.search(expression, str(name)) for expression in expressions)
        ]
    return []


def _allowed(error: ValidationError) -> str:
    """State the field names an object at the failing path may hold.

    Returns:
        ``allowed fields here: ...`` with the subschema's ``properties`` (and the patterns of its
        ``patternProperties``), or an empty string when the failure is not about fields or the
        subschema names none.

    """
    schema: object = error.schema
    if error.validator not in _PROPERTY_KEYWORDS or not isinstance(schema, dict):
        return ""
    properties: object = schema.get("properties") or {}
    patterns: object = schema.get("patternProperties") or {}
    names: list[str] = sorted(str(name) for name in properties) if isinstance(properties, dict) else []
    matching: list[str] = sorted(str(pattern) for pattern in patterns) if isinstance(patterns, dict) else []
    if not names and not matching:
        return ""
    stated: str = ", ".join(names) or "(none by name)"
    return f"allowed fields here: {stated}" + (f"; and any field matching {', '.join(matching)}" if matching else "")


def _path_order(error: ValidationError) -> list[tuple[int, int, str]]:
    """Order failures by their path in the value, array indexes numerically.

    Returns:
        The sort key of the error's path.

    """
    return [(0, part, "") if isinstance(part, int) else (1, 0, str(part)) for part in error.absolute_path]


def _branches(error: ValidationError) -> list[str]:
    """Name how each branch of a failed ``anyOf`` or ``oneOf`` failed, when ``best_match`` kept the whole rule.

    Returns:
        ``option <n>: <what failed>`` with the fields that option allows, once for each distinct
        failure inside the branches, at most ``_BRANCHES_STATED``, with how many more there are;
        empty for any other failure.

    """
    inner: list[str] = list(
        dict.fromkeys(
            f"option {child.schema_path[0] if child.schema_path else '?'}: {_short(child)}"
            + (f" ({_allowed(child)})" if _allowed(child) else "")
            for child in error.context or []
        ),
    )
    stated: list[str] = inner[:_BRANCHES_STATED]
    if len(inner) > _BRANCHES_STATED:
        stated.append(f"{len(inner) - _BRANCHES_STATED} more")
    return stated


def _short(error: ValidationError) -> str:
    """State what failed at an error's path, with every field name the failure is about.

    Returns:
        ``<path>: <what failed>``.

    """
    path: str = "/".join(str(part) for part in error.absolute_path) or "<root>"
    names: list[str] = _object_names(error)
    if error.validator == "required" and names:
        return f"{path}: missing required field(s) {', '.join(repr(name) for name in names)}"
    if names:
        return f"{path}: field(s) {', '.join(repr(name) for name in names)} not allowed"
    message: str = error.message
    return f"{path}: {message if len(message) <= _QUOTE_LIMIT else message[: _QUOTE_LIMIT - 1] + '…'}"


def explain(error: ValidationError, *, nodes: Mapping[int, str], location: Path | None, definition: str | None) -> str:
    """State one schema failure so the writer of the value can correct it without guessing.

    The line carries the path in the value, the field names the failure is about (the fields
    not allowed, or the required fields missing), the field names allowed at that path, the
    schema rule that failed quoted from the schema, the value given when it is not an object or
    an array, and the schema file with the JSON pointer of the failing keyword and the
    definition it lies in.

    Args:
        error: The failure, as ``best_match`` narrowed it.
        nodes: ``_schema_nodes`` of the schema the value was validated against.
        location: The schema file.
        definition: The definition validated against, when the pointer names none.

    Returns:
        One line.

    """
    parts: list[str] = [_short(error)]
    allowed: str = _allowed(error)
    if allowed:
        parts.append(allowed)
    parts.append(f"rule: {_quoted({str(error.validator): error.validator_value})}")
    branches: list[str] = _branches(error)
    if branches:
        parts.append("why each option failed: " + " | ".join(branches))
    if not isinstance(error.instance, dict | list):
        parts.append(f"value given: {_quoted(error.instance)}")
    node: str | None = nodes.get(id(error.schema))
    pointer: str = f"#{node}/{_pointer_part(str(error.validator))}" if node is not None else ""
    named: str | None = _definition_of(pointer) or definition
    where: str = f"schema: {location}{pointer}" if location is not None else f"schema pointer: {pointer or '#'}"
    parts.append(where + (f" (definition {named})" if named else ""))
    return "; ".join(parts)


def explain_all(
    errors: Iterable[ValidationError],
    *,
    root: JsonValue,
    location: Path | None,
    definition: str | None = None,
) -> list[str]:
    """State every schema failure of one value, in path order, each one fully up to a limit.

    Each failure is narrowed with ``best_match`` first, so a failure inside ``anyOf`` or
    ``oneOf`` is stated at the branch that came closest. The first ``EXPLAINED_IN_FULL`` are
    stated by ``explain``; each one after them keeps its path and the field names it is about.
    A line stated twice (``required`` fails once per missing field, and each line names them all)
    is kept once.

    Args:
        errors: The failures, as a validator's ``iter_errors`` yields them.
        root: The schema the validator was built from.
        location: The schema file.
        definition: The definition validated against, when a failure's pointer names none.

    Returns:
        One line per failure; empty when there is none.

    """
    narrowed: list[ValidationError] = [best_match([error]) or error for error in errors]
    if not narrowed:
        return []
    narrowed.sort(key=_path_order)
    nodes: dict[int, str] = _schema_nodes(root)
    stated: list[str] = [
        explain(error, nodes=nodes, location=location, definition=definition)
        if index < EXPLAINED_IN_FULL
        else _short(error)
        for index, error in enumerate(narrowed)
    ]
    return list(dict.fromkeys(stated))


def problems(value: JsonValue, schema: Mapping[str, JsonValue], *, location: Path | None = None) -> list[str]:
    """State every way ``value`` fails ``schema``, validated with strict numeric types.

    Args:
        value: The decoded JSON value.
        schema: The JSON Schema document.
        location: The file ``schema`` was read from.

    Returns:
        ``explain_all`` of every failure; empty when ``value`` satisfies ``schema``.

    """
    document: dict[str, JsonValue] = _located(schema, location)
    checked: Validator = _strict_class(document)(document, registry=registry())
    return explain_all(checked.iter_errors(value), root=document, location=location)
