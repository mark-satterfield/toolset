"""Exact producer contracts for the dynamically loaded control drivers."""

from __future__ import annotations

import functools
import importlib
import os
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Protocol, get_type_hints, runtime_checkable

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from driver_surface_types import CONTROL_REPO_ENV


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


@runtime_checkable
class DispatchArgumentsContract(Protocol):
    """Control dispatchargs module: the orchestrator command line and its dispatch-arguments file."""

    FLOW_PRD_TO_SPEC: str
    ORCHESTRATED_FLOWS: frozenset[str]
    OPT_BEAD: str
    OPT_ARGS: str
    OPT_HANDBACK: str
    ARGUMENTS_FILE: str
    HANDBACK_FILE: str
    KEY_PRD: str
    KEY_EPIC: str
    KEY_OWNER: str
    KEY_RECLAIM: str
    KEY_BEADS_REPO_PATH: str
    KEY_ARCH_PATH: str
    KEY_TRD_PATH: str
    KEY_DESIGN_SYSTEM: str
    KEY_SKILLSPOKE_ROOT: str
    KEY_EXECUTION_ID: str
    KEY_SUPERVISOR_INVOCATION_ID: str
    KEY_FABLE_UNTIL: str
    ARGUMENT_KEYS: frozenset[str]
    PRD_ID: str
    PRD_TITLE: str
    PRD_PATH: str
    EPIC_KEY: str
    EPIC_ID: str
    EPIC_TYPE: str
    EPIC_TITLE: str
    EPIC_PRD_REF: str
    EPIC_TYPE_VALUE: str
    DS_PACKAGES_DIR: str
    DS_MOCKS_DIR: str
    DS_SHELLS_DIR: str
    OWNER_TOKEN: re.Pattern[str]

    def parse_arguments(self, raw: object) -> Mapping[str, object]:
        """Parse a decoded dispatch-arguments document, raising ValueError or TypeError on drift."""
        ...

    def command(self, executable: str, entry: Path, flow: str, bead: str, scratch: Path) -> list[str]:
        """Build the run.py command line."""
        ...


_DISPATCH_HINTS: dict[str, object] = get_type_hints(DispatchArgumentsContract)
_DISPATCH_TEXT_NAMES: tuple[str, ...] = tuple(name for name, hint in _DISPATCH_HINTS.items() if hint is str)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def driver_module(name: str) -> ModuleType:
    """Load the configured control repository's named driver module.

    Returns:
        The imported module.

    """
    directory = Path(os.environ[CONTROL_REPO_ENV]) / "ops" / "sdlc-automation"
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


@functools.cache
def dispatch_arguments() -> DispatchArgumentsContract:
    """Return the producer's dispatch-arguments contract, checking every name's type.

    The body checks each name itself: typeguard's protocol check inspects a module's type,
    not the module, so it cannot check a module against this protocol.

    Returns:
        The control repository's dispatchargs module.

    Raises:
        TypeError: The module lacks a contract name or a name has the wrong type.

    """
    module: ModuleType = driver_module("dispatchargs")
    if not isinstance(module, DispatchArgumentsContract):
        message: str = f"{module.__file__} does not provide the dispatch-arguments contract"
        raise TypeError(message)
    name: str
    for name in _DISPATCH_TEXT_NAMES:
        check_type(getattr(module, name), str)
    check_type(module.ORCHESTRATED_FLOWS, frozenset[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    check_type(module.ARGUMENT_KEYS, frozenset[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    check_type(module.OWNER_TOKEN, re.Pattern[str])
    check_type(module.parse_arguments, Callable[[object], Mapping[str, object]])
    check_type(module.command, Callable[[str, Path, str, str, Path], list[str]])
    return module
