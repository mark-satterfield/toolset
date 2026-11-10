"""Carry review findings the build does not correct, so they are recorded rather than stop the build.

A review finding is a judgment that something should change, never an error. The build corrects
the findings its own specialists own (implementation and tests) within the correction allowance.
A finding owned by the contract or the tooling, and a finding still open when its correction
allowance is spent, is carried: recorded on the deciding step as the ``carriedFindings`` value
artifact and reported in the build handback, and the build continues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from typeguard import check_type

from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import value_artifact

if TYPE_CHECKING:
    from step_journal_contract import Step, ValueArtifact

CARRIED: Final = "carriedFindings"
"""The value artifact that holds the review findings a step carried instead of correcting."""
CARRIED_OWNERS: Final = frozenset({"contract", "tooling"})
"""Owners whose corrections no build specialist makes: the governing requirements, and the tooling."""
NOTE: Final = "note"
UNASSIGNED: Final = "unassigned"
KEPT_FIELDS: Final = ("severity", "detail", "file", "line")


def required(findings: list[JsonValue]) -> list[JsonValue]:
    """Select the findings that ask for a change.

    Returns:
        Every finding whose severity is not a note.

    """
    return [finding for finding in findings if json_object(finding)["severity"] != NOTE]


def owned_elsewhere(findings: list[JsonValue]) -> list[JsonValue]:
    """Select the findings whose correction belongs to the contract or the tooling.

    Returns:
        The findings the build carries instead of correcting.

    """
    return [finding for finding in findings if json_object(finding).get("owner") in CARRIED_OWNERS]


def owned_here(findings: list[JsonValue]) -> list[JsonValue]:
    """Select the findings the build's own specialists correct.

    Returns:
        The findings whose owner is not the contract or the tooling.

    """
    return [finding for finding in findings if json_object(finding).get("owner") not in CARRIED_OWNERS]


def carry(review: str, findings: list[JsonValue], reason: str) -> ValueArtifact:
    """Record review findings the build carries instead of correcting.

    Args:
        review: The artifact name of the review that raised the findings.
        findings: The findings carried.
        reason: Why the build carries them rather than corrects them.

    Returns:
        The ``carriedFindings`` value artifact.

    """
    entries: list[JsonValue] = []
    finding: JsonValue
    for finding in findings:
        source: dict[str, JsonValue] = json_object(finding)
        entry: dict[str, JsonValue] = {key: source[key] for key in KEPT_FIELDS if key in source}
        entry["owner"] = source.get("owner") or UNASSIGNED
        entry["review"] = review
        entry["reason"] = reason
        entries.append(entry)
    return value_artifact(CARRIED, entries)


def collected(steps: list[Step]) -> list[JsonValue]:
    """Collect every finding the accepted steps carried, once each.

    Args:
        steps: The accepted journal steps, in walk order.

    Returns:
        The carried findings, the first record of each owner and detail kept.

    """
    seen: set[tuple[str, str]] = set()
    found: list[JsonValue] = []
    step: Step
    for step in steps:
        for artifact in step["artifacts"]:
            if artifact["name"] != CARRIED or artifact["kind"] != "value":
                continue
            entry: JsonValue
            for entry in check_type(artifact["value"], list[JsonValue]):
                record: dict[str, JsonValue] = json_object(entry)
                key: tuple[str, str] = (str(record.get("owner")), str(record.get("detail")))
                if key not in seen:
                    seen.add(key)
                    found.append(entry)
    return found
