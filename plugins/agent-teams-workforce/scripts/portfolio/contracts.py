"""JSON values and architecture records shared by real portfolio boundaries."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, check_type, typechecked

# The architecture change values are generated from the target report schema, their one definition.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]
type JsonInput = str | bool | int | float | Sequence[JsonInput] | Mapping[str, JsonInput] | None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def json_value(value: JsonInput) -> JsonValue:
    """Materialize a read-only JSON input without erasing its scalar or tree types.

    Returns:
        A concrete JSON value with copied containers.

    Raises:
        TypeError: The input is not in the declared JSON scalar/tree domain.

    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (bytes, bytearray)):
        message: str = "Binary data is not a JSON collection"
        raise TypeError(message)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            message = "JSON object keys must be strings"
            raise TypeError(message)
        return {key: json_value(member) for key, member in value.items()}
    if isinstance(value, Sequence):
        return [json_value(member) for member in value]
    message = "Value is not a JSON scalar or collection"
    raise TypeError(message)


type SealForm = Literal["adopted", "v2"]
"""A survey seal form: adopted (a legacy seal migrated in place) or v2 (written by run_survey).

A seal with no form is the legacy JavaScript seal, which binds each repository's main^{tree}.
Neither adopted nor v2 binds a repository tree; for both, the consumer passes the survey
schema SHA as contextSha.
"""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def json_object(value: object) -> JsonObject:
    """Validate every nested value in a JSON object.

    Returns:
        The checked JSON object.

    """
    result: JsonObject = check_type(value, JsonObject, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    return result


class DeltaItem(TypedDict):
    """Catalog element or prerequisite emitted by the architecture delta writer."""

    id: str
    element: str
    matrixId: NotRequired[str]
    views: list[str]
    kind: NotRequired[str]
    state: NotRequired[str]
    repository: NotRequired[str | None]
    baseline: NotRequired[str]
    requires: NotRequired[list[str]]
    requiredBy: NotRequired[list[str]]
    evidence: NotRequired[list[str]]
    reason: NotRequired[str]
    closure: NotRequired[str]
    trigger: NotRequired[str]
    publishedBy: NotRequired[list[str]]


class GitFailureFact(TypedDict):
    """Concrete failed Git invocation."""

    subcommand: str
    exit: int | None
    timedOut: bool


class GitFailureSummary(GitFailureFact):
    """Architecture failure summary."""

    ok: bool
    refusals: list[str]


class GitFailure(GitFailureSummary):
    """Full architecture result when its Git operation fails."""

    summary: GitFailureSummary


class ErrorSummary(TypedDict):
    """A refused architecture operation."""

    ok: bool
    error: str


class ErrorResult(ErrorSummary):
    """Refusal with its consumer summary."""

    summary: ErrorSummary


class FileError(TypedDict):
    """Unavailable input to an architecture file operation."""

    error: str


class ClaimVerdict(TypedDict):
    """One independent review of a specific claim revision."""

    by: str
    verdict: str
    revision: str
    evidence: str


class Claim(TypedDict):
    """A writer's architecture claim folded into the current ledger."""

    id: str
    round: int
    by: str
    claim: str
    file: str
    citation: str
    evidenceRefs: list[JsonObject]
    evidenceState: list[JsonObject]
    evidenceErrors: list[str]
    views: list[str]
    viewState: dict[str, str]
    revision: str
    active: bool
    legacy: bool
    verdicts: list[ClaimVerdict]
    history: list[JsonObject]
    supersededBy: NotRequired[str]


class ClaimAnswer(TypedDict):
    """The owning writer's response to a review finding."""

    round: int
    response: str
    evidence: str


class Finding(TypedDict):
    """A reviewer finding and its owning writer's answer, if supplied."""

    id: str
    round: int
    by: str
    claimId: str
    claimRevision: str
    claim: str
    file: str
    verdict: str
    evidence: str
    owner: str
    answer: ClaimAnswer | None
    initialRevision: NotRequired[str]
    resolutionRevision: NotRequired[str]
    resolution: NotRequired[Resolution | None]


class CatalogRecord(TypedDict):
    """Four normalized fields read from architecture catalog frontmatter."""

    view_type: str
    scope: str
    subject: str
    shows: list[str]


class Resolution(TypedDict):
    """A reviewer resolution of an answered finding."""

    findingId: str
    evidence: str
    verdict: str
    by: str
    round: int


class PathReason(TypedDict):
    """A file that could not be processed and the reason."""

    path: str
    reason: str


class PathState(TypedDict):
    """A file's observed lifecycle state."""

    path: str
    state: str


class StateReport(TypedDict):
    """Observed lifecycle states and failures."""

    states: dict[str, str]
    notEffective: list[PathState]
    refused: list[PathReason]
    failed: list[PathReason]
    summary: dict[str, int]


class PromotionReport(TypedDict):
    """Results of promoting reviewed architecture documents."""

    promoted: list[str]
    unchanged: list[str]
    noFrontmatter: list[str]
    unreviewed: list[str]
    refused: list[PathReason]
    failed: list[PathReason]
    summary: dict[str, int]


class FingerprintSummary(TypedDict):
    """File count and content fingerprint."""

    files: int
    digest: str


class TreeSnapshot(TypedDict):
    """Current contents of the architecture version folders."""

    root: str
    files: dict[str, str]
    digest: str
    summary: FingerprintSummary


class ConstraintSnapshot(TypedDict):
    """Owner constraint contents and Git status before an operation."""

    folder: str
    exists: bool
    files: dict[str, str]
    digest: str
    gitStatus: list[str]
    gitError: str
    summary: FingerprintSummary
    kept: NotRequired[str]


class ConstraintRestore(TypedDict):
    """Paths restored from the owner constraint snapshot."""

    folder: str
    written: list[str]
    deleted: list[str]
    summary: dict[str, int]


class TreeDifference(TypedDict):
    """Changed file names between architecture snapshots."""

    created: list[str]
    changed: list[str]
    deleted: list[str]


class RefusalSummary(TypedDict):
    """Reasons a requested architecture mutation was refused."""

    ok: bool
    refusals: list[str]


class Refusal(RefusalSummary):
    """A refused architecture mutation and its summary."""

    summary: RefusalSummary


class MutationSummary(TypedDict):
    """Completed mutation counts and Git outcome."""

    ok: bool
    commit: str | None
    removed: NotRequired[bool | int]
    gone: NotRequired[int]
    pushed: NotRequired[bool]
    branch: NotRequired[str]


class BuiltRemoval(TypedDict):
    """Result of removing reconciled built files."""

    ok: bool
    refusals: list[str]
    removed: list[str]
    gone: list[str]
    commit: str | None
    summary: MutationSummary


class DeltaView(CatalogRecord):
    """A catalogued view in the target delta."""

    path: str


class DeltaResult(TypedDict):
    """Build scope derived from architecture catalogs and the explicit matrix."""

    ok: bool
    refusals: list[str]
    summary: JsonObject
    warnings: NotRequired[list[str]]
    deltaDir: NotRequired[str]
    deltaExists: NotRequired[bool]
    targetDir: NotRequired[str]
    architectureChange: NotRequired[str]
    note: NotRequired[str]
    views: NotRequired[list[DeltaView]]
    items: NotRequired[list[DeltaItem]]
    baselineValidated: NotRequired[bool]
    implementationWork: NotRequired[int | None]
    implementationComplete: NotRequired[bool]
    prerequisites: NotRequired[int]


class TargetNames(TypedDict):
    """Target text references to repository names."""

    targetDir: str
    named: dict[str, list[str]]
    unnamed: list[str]
    summary: dict[str, int]
