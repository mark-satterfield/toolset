"""The finding record the plugin and the driver both append to an Epic's ``findings.jsonl``.

A finding is a problem a check found that stops nothing. This module is the one definition of its
kinds, its line and its file name. The plugin's ``orchestrator/core/findings.py`` imports it; the
driver (``ops/sdlc-automation/findingrecord.py`` in the control repository) loads it by path from
the installed plugin and builds every line it writes with :func:`finding`. The module imports only
the standard library, so it loads by path with no package context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal, TypedDict, get_args

if TYPE_CHECKING:
    from collections.abc import Sequence

type FindingKind = Literal[
    "matrix-problem",
    "architecture-check-carried",
    "output-schema-carried",
    "trd-carried",
    "span-problem",
    "task-decomposition-carried",
    "done-rule-carried",
    "ownership-race",
    "contract-finding",
    "producer-missing",
    "completion-cycle",
    "prerequisite-unscheduled",
    "regression-carried",
    "prerequisite-carried",
    "respec-request-converted",
    "producer-epic-unordered",
    "deploy-stopped",
    "commit-hook-rejected",
    "dependency-cycle",
]
"""What kind of problem a finding records."""

FINDING_KINDS: Final[frozenset[str]] = frozenset(get_args(FindingKind.__value__))
"""Every finding kind, as the set a writer checks a kind against."""

type FindingSource = Literal["plugin", "driver"]
"""Which repository's code wrote a finding."""

SOURCE_PLUGIN: Final[FindingSource] = "plugin"
SOURCE_DRIVER: Final[FindingSource] = "driver"
FINDING_SOURCES: Final[frozenset[str]] = frozenset(get_args(FindingSource.__value__))

FINDINGS_FILE: Final = "findings.jsonl"
"""The file of one Epic's findings, in that Epic's work directory."""

Finding = TypedDict(
    "Finding",
    {
        "at": str,
        "owner": str,
        "from": str,
        "source": FindingSource,
        "stage": str,
        "kind": FindingKind,
        "detail": str,
        "evidence": list[str],
    },
)
"""One finding: when, whom it is addressed to, which bead's run found it, where, what and on what evidence."""


class FindingError(ValueError):
    """A finding names an unknown kind or an unknown source."""


def owner_epic(owner: str) -> str:
    """Name the Epic a finding's owner belongs to.

    Args:
        owner: The bead the finding is addressed to.

    Returns:
        The owner bead id cut at its first ``.`` (``ssbd-fcund.2.1`` gives ``ssbd-fcund``).

    """
    return owner.split(".", 1)[0]


def one_line(detail: str) -> str:
    """Fold a finding's detail to the one line it is recorded as: whitespace runs become one space.

    Args:
        detail: The detail as the check stated it.

    Returns:
        The detail as ``findings.jsonl`` holds it.

    """
    return " ".join(detail.split())


def parse_kind(value: str) -> FindingKind:
    """Narrow a kind name to a finding kind.

    Args:
        value: The kind name.

    Returns:
        The finding kind.

    Raises:
        FindingError: The name is not a finding kind.

    """
    kinds: tuple[FindingKind, ...] = get_args(FindingKind.__value__)
    match: FindingKind | None = next((kind for kind in kinds if kind == value), None)
    if match is None:
        message: str = f"finding kind {value!r} is not one of {sorted(FINDING_KINDS)}"
        raise FindingError(message)
    return match


def parse_source(value: str) -> FindingSource:
    """Narrow a source name to a finding source.

    Args:
        value: The source name.

    Returns:
        The finding source.

    Raises:
        FindingError: The name is not a finding source.

    """
    if value == SOURCE_PLUGIN:
        return SOURCE_PLUGIN
    if value == SOURCE_DRIVER:
        return SOURCE_DRIVER
    message: str = f"finding source {value!r} is not one of {sorted(FINDING_SOURCES)}"
    raise FindingError(message)


def finding(  # ruff: ignore[too-many-arguments] - One finding names each of its fields.
    owner: str,
    origin: str,
    *,
    at: str,
    source: str,
    stage: str,
    kind: str,
    detail: str,
    evidence: Sequence[str],
) -> Finding:
    """Build one finding line, checking its kind and source.

    ``FindingError`` propagates from :func:`parse_kind` or :func:`parse_source` when the kind or the
    source is unknown.

    Args:
        owner: The bead the finding is addressed to.
        origin: The bead whose run found it (the line's ``from``).
        at: When it was found, as ``YYYY-MM-DDTHH:MM:SSZ``.
        source: ``plugin`` or ``driver``.
        stage: The step that found it.
        kind: What kind of problem it is.
        detail: The detail; whitespace runs, line breaks included, fold to one space.
        evidence: Paths or quoted text.

    Returns:
        The finding.

    """
    return {
        "at": at,
        "owner": owner,
        "from": origin,
        "source": parse_source(source),
        "stage": stage,
        "kind": parse_kind(kind),
        "detail": one_line(detail),
        "evidence": list(evidence),
    }
