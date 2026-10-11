"""Explicit failures shared by existing isolated checks."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

from typeguard import CollectionCheckStrategy, typechecked

if TYPE_CHECKING:
    from collections.abc import Generator


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def require(condition: object, message: str) -> None:
    """Reject a false condition even when Python optimization is enabled.

    Raises:
        AssertionError: The checked condition is false.

    """
    if not condition:
        raise AssertionError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def report(message: str) -> None:
    """Write one check result without configuring application logging."""
    sys.stdout.write(message + "\n")


@contextmanager
def expected_error[E: Exception](kind: type[E]) -> Generator[list[E]]:
    """Capture the specific exception expected by an existing check.

    Yields:
        A list containing the caught exception after the context exits.

    Raises:
        AssertionError: The operation did not raise its expected exception.
        TypeError: The expected exception is not an exception class.

    """
    if not isinstance(kind, type) or not issubclass(kind, Exception):
        message: str = "Expected error must be an Exception subclass"
        raise TypeError(message)
    captured: list[E] = []
    try:
        yield captured
    except kind as exc:
        captured.append(exc)
    else:
        message = f"expected {kind.__name__} was not raised"
        raise AssertionError(message)
