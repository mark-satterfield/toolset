"""Declarations shared by flows, deterministic tools and the session runner."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class StepError(Exception):
    """A failure whose cause is known at its point of origin."""

    def __init__(
        self,
        stage: str,
        cause: str,
        evidence: tuple[str, ...] = (),
        *,
        resume_at: float | None = None,
    ) -> None:
        super().__init__(f"{stage}: {cause}")
        self.stage = stage
        self.cause = cause
        self.evidence = evidence
        self.resume_at = resume_at


@dataclass(frozen=True)
class DeterministicStep:
    stage: str
    inputs: tuple[str, ...]
    outputs: tuple[Path, ...]
    action: Callable[[], Any]
    reusable: bool = True


@dataclass(frozen=True)
class AgentStep:
    stage: str
    agent: str
    inputs: tuple[str, ...]
    output: Path
    outcome: str
    validate: Path | Callable[[Path], None]
    final: Path | None
    model: str
    effort: str
    add_dirs: tuple[Path, ...] = ()
    corrective: bool = True


@dataclass
class RunContext:
    bead: str
    flow: str
    args: dict[str, Any]
    work: Path
    run_id: str
    stage: str = "input"
    sessions: list[dict[str, Any]] = field(default_factory=list)
    cleanup: list[Callable[[], None]] = field(default_factory=list)
