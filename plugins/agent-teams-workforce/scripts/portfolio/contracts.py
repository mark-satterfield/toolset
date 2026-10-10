"""JSON values and architecture records shared by real portfolio boundaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, check_type, typechecked

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


class FreshnessResult(TypedDict):
    """The exact survey seal comparison emitted by survey_freshness."""

    valid: bool
    current: bool
    revision: str
    errors: list[str]
    warnings: list[str]


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


class RevisionRecord(TypedDict):
    """Current revision record written by architecture revision tracking."""

    archRoot: str
    revision: str
    files: dict[str, str]
    views: dict[str, str]
    integrating: bool
    recordedAt: str


class RevisionSummary(TypedDict):
    """Result of checking the effective architecture against saved work."""

    ok: bool
    revision: str
    movedTo: str | None
    moved: int
    reason: str
    status: str
    views: int


class RevisionCheck(RevisionSummary):
    """Detailed check and its identical summary."""

    summary: RevisionSummary


class ErrorSummary(TypedDict):
    """A refused architecture operation."""

    ok: bool
    error: str


class ErrorResult(ErrorSummary):
    """Refusal with its consumer summary."""

    summary: ErrorSummary


class RevisionMarkSummary(TypedDict):
    """A recorded integration state."""

    ok: bool
    state: str
    revision: str


class RevisionMark(RevisionMarkSummary):
    """Integration state and its identical summary."""

    summary: RevisionMarkSummary


class FileError(TypedDict):
    """Unavailable input to an architecture file operation."""

    error: str


class IntegrationFiles(TypedDict):
    """Measured and reported integration file sets."""

    touched: list[str]
    deleted: list[str]
    all: list[str]
    unreported: list[str]
    section2: list[str]
    outside: list[str]
    changedSinceLast: list[str]
    reportedTouched: list[str]
    reportedDeleted: list[str]
    constraintIssues: int
    contradictions: int
    filesOut: str


class IntegrationReview(TypedDict):
    """Conformance coverage of the actual integration file sets."""

    missed: list[str]
    coverageUnverified: list[str]
    conforms: bool
    findings: int
    review: str


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


class TargetRemoval(TypedDict):
    """Result of removing an integrated target folder."""

    ok: bool
    refusals: list[str]
    targetDir: str
    commit: str | None
    removed: bool
    summary: MutationSummary


class BuiltRemoval(TypedDict):
    """Result of removing reconciled built files."""

    ok: bool
    refusals: list[str]
    removed: list[str]
    gone: list[str]
    commit: str | None
    summary: MutationSummary


class IntegrationCommit(TypedDict):
    """Committed and pushed integration paths."""

    ok: bool
    refusals: list[str]
    files: list[str]
    branch: str
    commit: str | None
    pushed: bool
    summary: MutationSummary


class BaselineDocument(TypedDict):
    """Normalized citation of an architecture document."""

    path: str
    version: str
    lifecycle_state: str


class BaselineCode(TypedDict):
    """Historical implementation evidence retained as assessment context."""

    state: str
    behaviorEvidenceRefs: list[JsonObject]
    infrastructureEvidenceRefs: list[JsonObject]


class BaselineEntry(TypedDict):
    """Normalized architecture baseline assessment."""

    id: str
    requirements: list[str]
    subjects: list[str]
    documents: list[BaselineDocument]
    conflicts: list[JsonValue]
    awsGuidance: list[JsonObject]
    suitabilityEvidenceRefs: list[JsonObject]
    rationale: str
    current: str
    target: str
    code: BaselineCode
    kind: str
    designAction: str
    documentationAction: str
    disposition: str
    implementationAction: str


class BaselineFacts(TypedDict):
    """Baseline actions derived from the explicit assessment and matrix."""

    valid: bool
    revision: str
    errors: list[str]
    warnings: list[str]
    designWork: list[str]
    designReview: list[str]
    docWork: list[str]
    implementationWork: list[str]
    unknowns: list[str]
    entries: list[BaselineEntry]


class BaselineManifest(TypedDict):
    """Baseline handoff written into an approved target."""

    version: int
    arc42Revision: str | None
    survey: str
    surveySha256: str
    designChanged: bool
    documentationChanged: bool
    entries: list[BaselineEntry]
    implementationWork: list[str]
    approvalFiles: list[str]
    architectureChange: NotRequired[str]
    note: NotRequired[str]


class TargetResult(TypedDict):
    """Target creation or baseline seeding result, including refusal branches."""

    ok: bool
    refusals: list[str]
    summary: JsonObject
    subjectRefusals: NotRequired[list[str]]
    subject: NotRequired[str]
    subjectName: NotRequired[str]
    targetDir: NotRequired[str]
    deltaDir: NotRequired[str]
    files: NotRequired[list[str]]
    deltaFiles: NotRequired[list[str]]
    warnings: NotRequired[list[str]]
    dryRun: NotRequired[bool]
    draftWritten: NotRequired[bool]
    architectureChange: NotRequired[str]
    note: NotRequired[str]
    designChanged: NotRequired[bool]
    documentationChanged: NotRequired[bool]
    implementationWork: NotRequired[int]
    approvalFiles: NotRequired[list[str]]
    seeded: NotRequired[list[str]]


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


class RootItem(TypedDict):
    """Root delta identity consumed by prerequisite closure."""

    id: str
    element: str


class Prerequisite(TypedDict):
    """Resolved prerequisite with explicit dependencies and matrix evidence."""

    element: str
    state: str
    views: list[str]
    evidence: list[str]
    repository: str | None
    requiredBy: list[str]
    reason: str
    requires: list[str]


class ClosureFacts(TypedDict):
    """Validated prerequisite graph, or its refusal reasons."""

    valid: bool
    refusals: list[str]
    warnings: NotRequired[list[str]]
    prerequisites: NotRequired[list[Prerequisite]]
    rootRequires: NotRequired[dict[str, list[str]]]
    satisfied: NotRequired[int]


class PrerequisiteState(TypedDict):
    """Prerequisite identity and matrix state published after writing closure."""

    element: str
    state: str


class ClosureResult(TypedDict):
    """Saved prerequisite closure and diagnostics."""

    ok: bool
    refusals: list[str]
    warnings: list[str]
    closurePath: str | None
    prerequisites: list[PrerequisiteState]
    summary: JsonObject
