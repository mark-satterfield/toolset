"""Persisted round records derived from the coordinator schema and round writer."""

from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, Protocol, TypedDict, runtime_checkable

if TYPE_CHECKING:
    from contracts import Claim, Finding


class RevisionRef(TypedDict):
    """Bind an item to the revision assessed by a reviewer."""

    id: str
    revision: str


class Overlap(TypedDict):
    """The coordinator's explicit reason for overlapping assignments."""

    files: list[str]
    claimIds: list[str]
    agentTypes: list[str]
    reason: str


class Dispatch(TypedDict):
    """A coordinator assignment plus fields added by the durable round writer."""

    agentType: str
    role: str
    task: str
    files: list[str]
    answers: list[str]
    selectionReason: NotRequired[str]
    repairIds: NotRequired[list[str]]
    claimIds: NotRequired[list[str]]
    claimFiles: NotRequired[list[str]]
    coverageIds: NotRequired[list[str]]
    seq: NotRequired[int]
    file: NotRequired[str]
    complete: NotRequired[bool]
    legacySaved: NotRequired[bool]
    overlapReason: NotRequired[str]
    designOwner: NotRequired[bool]
    assignedClaims: NotRequired[list[RevisionRef]]
    reviewInputRevision: NotRequired[str]


class RoundPlan(TypedDict):
    """A saved plan identified by its architecture round."""

    round: int
    dispatches: list[Dispatch]
    readyForDecision: NotRequired[bool]
    reason: NotRequired[str]
    overlaps: NotRequired[list[Overlap]]
    complete: NotRequired[bool]
    legacyContinuation: NotRequired[bool]
    designOwner: NotRequired[str]


class CompactDispatch(TypedDict):
    """The exact dispatch fields published in the compact resume projection."""

    seq: int
    role: str
    agentType: str
    complete: bool
    coverageIds: list[str]
    claimIds: list[str]
    claimFiles: list[str]
    reviewInputRevision: str
    files: list[str]
    answers: list[str]
    assignedClaimCount: int


class CompactPlan(TypedDict):
    """The exact pending-plan projection consumed by architecture orchestration."""

    round: int
    readyForDecision: bool
    complete: bool
    dispatches: list[CompactDispatch]


class RoundFacts(TypedDict):
    """The state and diagnostics produced by settling round plans."""

    plans: list[RoundPlan]
    resumeRound: int | None
    last: int
    pendingPlan: RoundPlan | None
    reviewGaps: list[str]
    overlapWarnings: list[str]
    planKept: str
    warnings: list[str]


@runtime_checkable
class RoundLedger(Protocol):
    """The exact read-only ledger surface consumed by round settlement."""

    @property
    def last(self) -> int:
        """The last observed round."""
        ...

    @property
    def files(self) -> list[str]:
        """Source result paths."""
        ...

    @property
    def claims(self) -> list[Claim]:
        """The ledger's typed claims."""
        ...

    @property
    def findings(self) -> list[Finding]:
        """The ledger's typed findings."""
        ...
