"""JSON Schema validation whose numeric types match the pipeline's runtime contracts.

jsonschema's stock type checkers accept ``1.0`` as an ``integer`` and ``inf``/``nan`` as a
``number``. The pipeline's typed consumers reject both, so a value a schema accepted could
still fail the consumer it was validated for. This module is the one place every schema site
builds its validator: ``integer`` is exactly ``int`` (never ``bool`` or ``float``) and
``number`` is a finite ``int`` or ``float`` (never ``bool``).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol, TypeIs

from jsonschema import Draft202012Validator, SchemaError, TypeChecker, ValidationError, validators
from jsonschema.exceptions import best_match

if TYPE_CHECKING:
    from contracts import JsonValue
    from jsonschema.protocols import Validator


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


def _strict_class(document: dict[str, JsonValue]) -> type[Validator]:
    """Return the dialect class ``document`` declares, with strict numeric type checks.

    Returns:
        A validator class: the declared dialect (Draft 2020-12 when absent) whose
        ``integer`` and ``number`` checks are strict.

    """
    dialect: type[Validator] = validators.validator_for(document, default=Draft202012Validator)
    checker: TypeChecker = dialect.TYPE_CHECKER.redefine_many({"integer": _is_integer, "number": _is_number})
    return _EXTEND(dialect, type_checker=checker)


def validator(schema: Mapping[str, JsonValue]) -> Validator:
    """Build a strict validator for ``schema`` in the dialect the schema declares.

    The dialect comes from the schema's ``$schema`` (Draft 2020-12 when absent). Its type
    checker is replaced for ``integer`` and ``number`` only; every other keyword keeps the
    dialect's own behavior. The schema itself is not checked; call ``validate`` for that.

    Args:
        schema: The JSON Schema document.

    Returns:
        A validator instance for ``schema``.

    """
    document: dict[str, JsonValue] = _document(schema)
    return _strict_class(document)(document)


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


def validate(value: object, schema: Mapping[str, JsonValue]) -> None:
    """Check ``schema`` itself, then validate ``value`` against it with strict numeric types.

    Behaves as ``jsonschema.validate`` does: the schema is checked against its dialect's
    meta-schema first and a ``jsonschema.SchemaError`` is raised for the most relevant schema
    problem; then a ``jsonschema.ValidationError`` is raised for the most relevant problem in
    ``value``. Both are jsonschema's own error objects, with their paths intact.

    Args:
        value: The decoded JSON value to validate.
        schema: The JSON Schema document.

    Raises:
        TypeError: When ``value`` is not a decoded JSON value.

    """
    document: dict[str, JsonValue] = _document(schema)
    if not _is_json(value):
        message: str = f"value must be a decoded JSON value, got {type(value).__name__}"
        raise TypeError(message)
    strict: type[Validator] = _strict_class(document)
    meta: dict[str, JsonValue] = dict(strict.META_SCHEMA)
    meta_checker: Validator = validators.validator_for(meta, default=strict)(meta)
    schema_problem: ValidationError | None = best_match(meta_checker.iter_errors(document))
    if schema_problem is not None:
        schema_error: SchemaError = SchemaError.create_from(schema_problem)
        raise schema_error
    checked: Validator = strict(document)
    problem: ValidationError | None = best_match(checked.iter_errors(value))
    if problem is not None:
        raise problem
