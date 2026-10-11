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
from collections.abc import Iterator, Mapping
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
