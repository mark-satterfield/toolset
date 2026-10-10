"""Explicit structural contract for the control repository's artifact producer."""

from pathlib import Path
from typing import Protocol, TypedDict, Unpack, runtime_checkable

from typeguard import CollectionCheckStrategy, typechecked

from .io import JsonValue


class RecordFields(TypedDict):
    """Required provenance supplied when accepting an output."""

    epic: str
    phase: str
    inputs: list[str]
    producer: str
    run_id: str
    root: Path


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
@runtime_checkable
class ArtifactProducer(Protocol):
    """Operations consumed by the orchestrator, with exact argument contracts."""

    INPUT_KINDS: frozenset[str]

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def record(file: Path, **options: Unpack[RecordFields]) -> dict[str, JsonValue]:
        """Accept an output with its complete provenance."""
        ...

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def hashed_inputs(inputs: list[str], base: Path) -> list[dict[str, JsonValue]]:
        """Fingerprint every declared input."""
        ...

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def input_problem(entry: object, root: Path, artifact: Path | None = None) -> str | None:
        """Explain any mismatch with recorded input provenance."""
        ...

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def complete_step(directory: Path, step: str) -> None:
        """Record an accepted step."""
        ...

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def working_dir(epic_id: str, base: Path | None = None) -> Path:
        """Resolve the artifact directory for an Epic."""
        ...

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def sha256_file(path: Path) -> str:
        """Hash an output file."""
        ...

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def safe_key(identifier: str) -> str:
        """Normalize a filesystem identifier."""
        ...

    @staticmethod
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def from_record(recorded: str, root: Path) -> Path:
        """Resolve a recorded input path."""
        ...
