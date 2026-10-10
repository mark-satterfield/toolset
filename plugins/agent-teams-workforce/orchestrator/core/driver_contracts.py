"""Exact producer contracts for the dynamically loaded control drivers."""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Protocol, runtime_checkable

from typeguard import CollectionCheckStrategy, check_type, typechecked


@runtime_checkable
class HeadlessEnvironment(Protocol):
    """Control headlessenv module surface consumed by session setup."""

    DENIED_TOOLS: tuple[str, ...]

    def child_env(self, scratch: Path) -> dict[str, str]:
        """Construct the subprocess environment."""
        ...


@runtime_checkable
class FableWall(Protocol):
    """Control fablewall module surface consumed by model fallback."""

    def is_refusal(self, info: object) -> bool:
        """Identify a model-specific refusal."""
        ...

    def reset_of(self, info: object) -> float | None:
        """Read the model-specific reset timestamp."""
        ...


@runtime_checkable
class Breaker(Protocol):
    """Control breaker module surface consumed by quota handling."""

    def exhausted_reset(self, info: object) -> float | None:
        """Read the account quota reset timestamp."""
        ...


@runtime_checkable
class ChildProcess(Protocol):
    """Control childproc module termination policy."""

    TERMINATE_GRACE: float


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def driver_module(name: str) -> ModuleType:
    """Load the configured control repository's named driver module.

    Returns:
        The imported module.

    """
    directory = Path(os.environ["ATW_CONTROL_REPO"]) / "ops" / "sdlc-automation"
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    return importlib.import_module(name)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def denied_tools() -> tuple[str, ...]:
    """Return the exact immutable denied-tool contract from the producer.

    Returns:
        The validated producer value.

    """
    return check_type(
        driver_module("headlessenv").DENIED_TOOLS,
        tuple[str, ...],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def child_environment(scratch: Path) -> dict[str, str]:
    """Return the producer environment, checking every key and value.

    Returns:
        The validated producer value.

    """
    operation: Callable[[Path], dict[str, str]] = check_type(
        driver_module("headlessenv").child_env,
        Callable[[Path], dict[str, str]],
    )
    return operation(scratch)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def is_refusal(info: object) -> bool:
    """Return the producer's model-refusal decision.

    Returns:
        The validated producer value.

    """
    operation: Callable[[object], bool] = check_type(
        driver_module("fablewall").is_refusal,
        Callable[[object], bool],
    )
    return operation(info)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def reset_of(info: object) -> float | None:
    """Return the producer's model-specific reset timestamp.

    Returns:
        The validated producer value.

    """
    operation: Callable[[object], float | None] = check_type(
        driver_module("fablewall").reset_of,
        Callable[[object], float | None],
    )
    return operation(info)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def exhausted_reset(info: object) -> float | None:
    """Return the producer's account quota reset timestamp.

    Returns:
        The validated producer value.

    """
    operation: Callable[[object], float | None] = check_type(
        driver_module("breaker").exhausted_reset,
        Callable[[object], float | None],
    )
    return operation(info)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def terminate_grace() -> float:
    """Return the producer's termination grace interval.

    Returns:
        The validated producer value.

    """
    return check_type(driver_module("childproc").TERMINATE_GRACE, float)
