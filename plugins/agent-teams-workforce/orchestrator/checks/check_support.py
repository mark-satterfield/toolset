"""Explicit failures shared by existing isolated checks."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager

from typeguard import CollectionCheckStrategy, typechecked


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
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def expected_error[E: Exception](kind: type[E]) -> Iterator[list[E]]:
    """Capture the specific exception expected by an existing check.

    Yields:
        A list containing the caught exception after the context exits.

    Raises:
        AssertionError: The operation did not raise its expected exception.

    """
    captured: list[E] = []
    try:
        yield captured
    except kind as exc:
        captured.append(exc)
    else:
        message = f"expected {kind.__name__} was not raised"
        raise AssertionError(message)
