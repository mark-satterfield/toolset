"""Exact producer contracts for the dynamically loaded control drivers."""

from __future__ import annotations

import functools
import importlib
import os
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Protocol, runtime_checkable

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


@dataclass(frozen=True, slots=True)
class DispatchArguments:
    """Control dispatchargs values: the orchestrator command line and its dispatch-arguments file.

    Built from the dispatchargs module by ``dispatch_arguments()``, which checks every value's
    type, so annotated locals and parameters hold a concrete class rather than a module.
    """

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
    parse_arguments: Callable[[object], Mapping[str, object]]
    command: Callable[[str, Path, str, str, Path], list[str]]


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


def _attribute(module: ModuleType, name: str) -> object:
    """Read one contract name from the producer module.

    Returns:
        The module's value for ``name``.

    Raises:
        TypeError: The module does not define ``name``.

    """
    if not hasattr(module, name):
        message: str = f"{module.__file__} does not provide the dispatch-arguments name {name}"
        raise TypeError(message)
    value: object = getattr(module, name)
    return value


def _text(module: ModuleType, name: str) -> str:
    """Read one text contract name, checking its type.

    Returns:
        The validated text value.

    """
    return check_type(_attribute(module, name), str)


def _names(module: ModuleType, name: str) -> frozenset[str]:
    """Read one frozen name-set contract value, checking every member.

    Returns:
        The validated set of names.

    """
    return check_type(
        _attribute(module, name),
        frozenset[str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


@functools.cache
def dispatch_arguments() -> DispatchArguments:
    """Return the producer's dispatch-arguments values, checking every name's type.

    A missing name raises ``TypeError``; a name of the wrong type raises typeguard's
    ``TypeCheckError``.

    Returns:
        The control repository's dispatchargs values as a frozen ``DispatchArguments``.

    """
    module: ModuleType = driver_module("dispatchargs")
    return DispatchArguments(
        FLOW_PRD_TO_SPEC=_text(module, "FLOW_PRD_TO_SPEC"),
        ORCHESTRATED_FLOWS=_names(module, "ORCHESTRATED_FLOWS"),
        OPT_BEAD=_text(module, "OPT_BEAD"),
        OPT_ARGS=_text(module, "OPT_ARGS"),
        OPT_HANDBACK=_text(module, "OPT_HANDBACK"),
        ARGUMENTS_FILE=_text(module, "ARGUMENTS_FILE"),
        HANDBACK_FILE=_text(module, "HANDBACK_FILE"),
        KEY_PRD=_text(module, "KEY_PRD"),
        KEY_EPIC=_text(module, "KEY_EPIC"),
        KEY_OWNER=_text(module, "KEY_OWNER"),
        KEY_RECLAIM=_text(module, "KEY_RECLAIM"),
        KEY_BEADS_REPO_PATH=_text(module, "KEY_BEADS_REPO_PATH"),
        KEY_ARCH_PATH=_text(module, "KEY_ARCH_PATH"),
        KEY_TRD_PATH=_text(module, "KEY_TRD_PATH"),
        KEY_DESIGN_SYSTEM=_text(module, "KEY_DESIGN_SYSTEM"),
        KEY_SKILLSPOKE_ROOT=_text(module, "KEY_SKILLSPOKE_ROOT"),
        KEY_EXECUTION_ID=_text(module, "KEY_EXECUTION_ID"),
        KEY_SUPERVISOR_INVOCATION_ID=_text(module, "KEY_SUPERVISOR_INVOCATION_ID"),
        KEY_FABLE_UNTIL=_text(module, "KEY_FABLE_UNTIL"),
        ARGUMENT_KEYS=_names(module, "ARGUMENT_KEYS"),
        PRD_ID=_text(module, "PRD_ID"),
        PRD_TITLE=_text(module, "PRD_TITLE"),
        PRD_PATH=_text(module, "PRD_PATH"),
        EPIC_KEY=_text(module, "EPIC_KEY"),
        EPIC_ID=_text(module, "EPIC_ID"),
        EPIC_TYPE=_text(module, "EPIC_TYPE"),
        EPIC_TITLE=_text(module, "EPIC_TITLE"),
        EPIC_PRD_REF=_text(module, "EPIC_PRD_REF"),
        EPIC_TYPE_VALUE=_text(module, "EPIC_TYPE_VALUE"),
        DS_PACKAGES_DIR=_text(module, "DS_PACKAGES_DIR"),
        DS_MOCKS_DIR=_text(module, "DS_MOCKS_DIR"),
        DS_SHELLS_DIR=_text(module, "DS_SHELLS_DIR"),
        OWNER_TOKEN=check_type(_attribute(module, "OWNER_TOKEN"), re.Pattern[str]),
        parse_arguments=check_type(
            _attribute(module, "parse_arguments"),
            Callable[[object], Mapping[str, object]],
        ),
        command=check_type(
            _attribute(module, "command"),
            Callable[[str, Path, str, str, Path], list[str]],
        ),
    )
