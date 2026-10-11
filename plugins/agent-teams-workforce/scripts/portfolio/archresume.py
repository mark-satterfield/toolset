"""Read the architecture step's saved work on disk and report only what its control flow needs.

`depscore.py arch-resume` runs `resume_facts`. The architecture step saves every session's
result under the Epic's working directory: `survey.json`, `rounds/r<n>-<seq>-<role>-<agent>.json`,
`decision.json`, `architecture-update.json`, `integrate-before.json` and `conformance-<n>.json`.
This command reads them, folds the round results into the claim and finding ledger, writes the
whole ledger to `ledger.json` in that directory for the sessions that need it, and prints the
compact facts the workflow branches on: which steps finished, the last round, the open
findings by id, the number of unreviewed claims of each writer, the decision verdict,
and the integration file lists.
No saved content travels back to the workflow: sessions read the files by path.

A saved file that cannot be read or parsed, or is not a JSON object, is set aside
(`<name>.unreadable-<timestamp>`) and named in `warnings`; only the step that wrote it runs
again. A sealed file whose receipt no longer matches its bytes is read as it is on disk.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict

import archcoverage
import archrepairs
import contracts
import portfolio_path  # ruff: ignore[unused-import] - imported for its sys.path side effect before the from-imports below
import roundcontracts
from archbaseline import baseline_facts
from archcoverage import CoverageSummary, RoundCoverage, coverage_facts
from archevidence import digest, evidence_state, load_repository_paths, view_bindings, view_content
from architecture_artifacts import (
    RESOLUTION_ACCEPTED,
    RESOLUTION_REJECTED,
    RESPONSE_DISPUTED,
    VERDICT_VERIFIED,
    ConformanceResult,
    FindingAnswer,
    ReviewResult,
    WriterClaim,
    WriterResult,
    parse_conformance_result,
    parse_review_result,
    parse_writer_result,
)
from archrepairs import HistoricalTeam, RepairRequest, repair_facts
from archrounds import RoundInputs, compact_plan, round_facts, save_ledger, set_aside
from contracts import BaselineFacts, Claim, Finding, JsonObject, JsonValue, Resolution, json_object
from jsonartifact import LENIENT_READS, read_artifact
from roundcontracts import CompactPlan, RoundPlan
from survey_contract import SURVEY_FILE, BaselineEntry, Survey, SurveyContractError, parse_survey
from typeguard import CollectionCheckStrategy, check_type, typechecked


class DecisionFacts(TypedDict):
    """Decision fields consumed by architecture branching."""

    verdict: str
    round: int
    returnTo: list[str]
    ownerConcerns: int
    ownerConcernKinds: list[str]
    ownerOnly: bool
    choices: int
    repairChecksNeeded: NotRequired[list[str]]


class UpdateFacts(TypedDict):
    """Saved architecture integration changes."""

    changedFiles: list[str]
    createdFiles: list[str]
    deletedFiles: list[str]
    constraintIssues: int
    contradictions: int


class ReviewFacts(TypedDict):
    """Last saved integration conformance review."""

    n: int
    path: str
    conforms: bool
    coverageChecks: int
    reviewedFiles: int
    findings: int


class IntegrationFacts(TypedDict):
    """Saved integration checkpoints."""

    update: UpdateFacts | None
    beforeSaved: bool
    reviews: int
    lastReview: ReviewFacts | None


class SurveyFacts(TypedDict):
    """Availability and scope of the saved survey."""

    saved: bool
    readable: bool
    subject: str
    capabilities: int
    coverageSaved: bool


class OpenFinding(TypedDict):
    """Unresolved finding needing writer or reviewer work."""

    id: str
    verdict: str
    owner: str
    file: str
    answered: bool


class ResumeRounds(TypedDict):
    """Compact round state consumed by the architecture flow."""

    last: int
    resumeRound: int | None
    pendingPlan: CompactPlan | None
    pendingRound: int | None
    pendingDispatches: int
    planKept: str
    readyForDecision: bool
    results: int
    saved: list[str]
    writers: list[str]
    reviewers: list[str]
    proposersWithoutClaims: list[str]
    claims: int
    findings: int
    openFindings: list[OpenFinding]
    unreviewedClaims: dict[str, int]
    overlapWarnings: list[str]


class ResumeFacts(TypedDict):
    """Saved architecture state and precise branching inputs."""

    contractVersion: int
    dir: str
    exists: bool
    ledger: str | None
    survey: SurveyFacts | None
    baseline: JsonObject
    coverage: CoverageSummary
    historicalAuthoring: HistoricalTeam
    rounds: ResumeRounds
    decision: DecisionFacts | None
    repairs: dict[str, list[str]]
    integration: IntegrationFacts
    warnings: list[str]
    summary: JsonObject


ROUND_FILE = re.compile(
    r"^r(\d+)-(\d+)-(proposer|diagram|reviewer|cost)-([a-z0-9-]+)\.json$",
)
REVIEW_FILE = re.compile(r"^conformance-(\d+)\.json$")
WRITER_ROLES = ("proposer", "diagram")
OWNER_CONCERN_KINDS = ("business-conflict", "architecture-conflict")
AGENT_PREFIX = "agent-teams-workforce:"
LEDGER_NAME = "ledger.json"


class ResumeError(Exception):
    """A saved file of the architecture step cannot be read or parsed."""


def _text(value: JsonValue) -> str:
    """Return a value as stripped text, or empty when it is not a string.

    Args:
        value: Any JSON value.

    Returns:
        The stripped string, or "".

    """
    return value.strip() if isinstance(value, str) else ""


def _load(path: Path) -> JsonValue:
    """Parse one saved JSON file.

    Args:
        path: The file.

    Returns:
        The parsed value.

    Raises:
        ResumeError: The file cannot be read or is not JSON.

    """
    try:
        return read_artifact(path, strict=False)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        message: str = f"{path}: {exc}"
        raise ResumeError(message) from exc


def _saved_files(work: Path) -> list[Path]:
    """Every saved JSON file arch-resume reads.

    Args:
        work: The architecture working directory.

    Returns:
        The files that exist.

    """
    fixed: list[Path] = [
        work / name
        for name in (
            SURVEY_FILE,
            LEDGER_NAME,
            "decision.json",
            "architecture-update.json",
            "integrate-before.json",
        )
    ]
    reviews: list[Path] = [p for p in work.iterdir() if REVIEW_FILE.match(p.name)] if work.is_dir() else []
    folder: Path = work / "rounds"
    rounds: list[Path] = [p for p in folder.iterdir() if ROUND_FILE.match(p.name)] if folder.is_dir() else []
    return [p for p in [*fixed, *sorted(reviews), *sorted(rounds)] if p.is_file()]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def sweep_unreadable(work: Path) -> list[str]:
    """Set aside every saved file that cannot be read as a JSON object.

    Args:
        work: The architecture working directory.

    Returns:
        One warning per file set aside.

    Raises:
        TypeError: The input violates the declared contract.

    """
    path: Path
    if not isinstance(work, Path):
        message: str = "sweep_unreadable requires its declared work input type"
        raise TypeError(message)
    notes: list[str] = []
    for path in _saved_files(work):
        value: JsonValue | OSError | ValueError
        try:
            value = read_artifact(path, strict=False)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            value = exc
        if isinstance(value, dict):
            continue
        why: OSError | ValueError | str = value if isinstance(value, Exception) else "not a JSON object"
        notes.append(
            f"{path} could not be used ({why}); set aside as {set_aside(path)}",
        )
    return notes


def _paths(value: JsonValue) -> list[str]:
    """Return the non-empty strings of a list value.

    Args:
        value: Any JSON value.

    Returns:
        The stripped strings, in order.

    """
    return [_text(x) for x in value if _text(x)] if isinstance(value, list) else []


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_roster(spec: str) -> dict[str, str]:
    """Parse `role=a,b;role=c` into each agent's role.

    Args:
        spec: The roster as the workflow passes it.

    Returns:
        The role of each agent named.

    Raises:
        TypeError: The input violates the declared contract.

    """
    part: str
    role: str
    names: str
    name: str
    if not isinstance(spec, str):
        message: str = "parse_roster requires its declared spec input type"
        raise TypeError(message)
    roles: dict[str, str] = {}
    for part in spec.split(";"):
        role, _, names = part.partition("=")
        for name in names.split(","):
            if name.strip() and role.strip():
                roles[name.strip()] = role.strip()
    return roles


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def parse_assign(spec: str) -> dict[str, str]:
    """Parse `F1.2.3=agent,F2.1.1=agent` into each finding's assigned owner.

    Args:
        spec: The assignments as the workflow passes them.

    Returns:
        The owner the coordinator assigned to each finding id.

    Raises:
        TypeError: The input violates the declared contract.

    """
    part: str
    fid: str
    owner: str
    if not isinstance(spec, str):
        message: str = "parse_assign requires its declared spec input type"
        raise TypeError(message)
    out: dict[str, str] = {}
    for part in spec.split(","):
        fid, _, owner = part.partition("=")
        if fid.strip() and owner.strip():
            out[fid.strip()] = owner.strip()
    return out


@dataclass(frozen=True)
class RoundSource:
    """The identity and origin of one saved round result."""

    round: int
    sequence: int
    role: str
    agent: str
    file: str

    def __post_init__(self) -> None:
        """Validate the saved dispatch identity.

        Raises:
            TypeError: A field has the wrong type.
            ValueError: A round or sequence number is not positive.

        """
        if not isinstance(self.round, int) or not isinstance(self.sequence, int):
            message: str = "RoundSource round and sequence must be integers"
            raise TypeError(message)
        if self.round < 1 or self.sequence < 1:
            message = "RoundSource round and sequence must be positive"
            raise ValueError(message)
        if not all(isinstance(value, str) for value in (self.role, self.agent, self.file)):
            message = "RoundSource role, agent, and file must be strings"
            raise TypeError(message)


class Ledger:
    """The claims and findings of the rounds, folded in round order."""

    def __init__(self, assign: dict[str, str], *, repository_paths: dict[str, str] | None = None) -> None:
        """Start an empty ledger.

        Args:
            assign: Owners the coordinator assigned to findings that had none.
            repository_paths: Named checkout paths from the saved repository menu.

        Raises:
            TypeError: The input violates the declared contract.

        """
        if not isinstance(assign, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in assign.items()
        ):
            message: str = "__init__ requires its declared assign input type"
            raise TypeError(message)
        self.repository_paths: dict[str, str] = repository_paths or {}
        self.assign: dict[str, str] = assign
        self.claims: list[Claim] = []
        self.findings: list[Finding] = []
        self.writers: list[str] = []
        self.reviewers: list[str] = []
        self.proposer_claims: dict[str, int] = {}
        self.files: list[str] = []
        self.coverage: list[RoundCoverage] = []
        self.saved: list[str] = []
        self.last: int = 0
        self.resolutions: list[Resolution] = []

    def _record(self, source: RoundSource) -> None:
        """Record that one round result was folded.

        Raises:
            TypeError: The source has the wrong type.

        """
        if not isinstance(source, RoundSource):
            message: str = "Ledger requires a RoundSource"
            raise TypeError(message)
        self.files.append(source.file)
        self.saved.append(f"r{source.round}-{source.sequence}")
        self.last = max(self.last, source.round)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def absorb_review(self, source: RoundSource, result: ReviewResult) -> None:
        """Fold one review result, parsed with the artifact-handoff review schema, into the ledger.

        Raises:
            TypeError: The source or result has the wrong type.

        """
        k: int
        if not isinstance(result, dict):
            message: str = "Ledger.absorb_review requires a parsed review result"
            raise TypeError(message)
        self._record(source)
        self.coverage.append(RoundCoverage(source.agent, checks=tuple(result["coverageChecks"])))
        if source.agent not in self.reviewers:
            self.reviewers.append(source.agent)
        self.resolutions.extend(
            {
                "findingId": r["findingId"],
                "evidence": r["evidence"],
                "verdict": r["verdict"],
                "by": source.agent,
                "round": source.round,
            }
            for r in result["resolutions"]
        )
        for k, x in enumerate(result["findings"]):
            claim_id: str = x["claimId"].strip()
            claim: contracts.Claim | None = (
                next((c for c in self.claims if c["id"] == claim_id), None) if claim_id else None
            )
            if claim and source.agent != claim["by"] and x["evidence"].strip():
                claim["verdicts"].append(
                    {
                        "by": source.agent,
                        "verdict": x["verdict"],
                        "revision": claim["revision"],
                        "evidence": x["evidence"],
                    },
                )
            named: str = x["owner"].strip()
            owner: str = claim["by"] if claim else named if named in self.writers else ""
            fid: str = f"F{source.round}.{source.sequence}.{k + 1}"
            self.findings.append(
                {
                    "id": fid,
                    "round": source.round,
                    "by": source.agent,
                    "claimId": claim["id"] if claim else "",
                    "claimRevision": claim["revision"] if claim else "",
                    "claim": x["claim"],
                    "file": x["file"],
                    "verdict": x["verdict"],
                    "evidence": x["evidence"],
                    "owner": self.assign.get(fid) or owner,
                    "answer": None,
                },
            )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def absorb_writer(self, source: RoundSource, result: WriterResult) -> None:
        """Fold one writer result, parsed with the artifact-handoff writer schema, into the ledger.

        Raises:
            TypeError: The source or result has the wrong type.

        """
        k: int
        c: WriterClaim
        if not isinstance(result, dict):
            message: str = "Ledger.absorb_writer requires a parsed writer result"
            raise TypeError(message)
        self._record(source)
        self.coverage.append(RoundCoverage(source.agent, rows=tuple(result["coverage"])))
        if source.agent not in self.writers:
            self.writers.append(source.agent)
        stated: int = 0
        for k, c in enumerate(result["claims"]):
            if c["claim"].strip():
                stated += 1
                self._absorb_claim(source, k, c)
        if source.role == "proposer":
            self.proposer_claims[source.agent] = self.proposer_claims.get(source.agent, 0) + stated
        self._answers(source, result["answers"])

    def _absorb_claim(self, source: RoundSource, k: int, c: WriterClaim) -> None:
        """Fold one stated writer claim into the ledger, superseding the claims it names."""
        evidence: list[JsonObject]
        errors: list[str]
        superseded: str
        cid: str = c["claimId"].strip() or f"C{source.round}.{source.sequence}.{k + 1}"
        old: contracts.Claim | None = next((x for x in self.claims if x["id"] == cid), None)
        if c["claimId"] and not old:
            cid = f"C{source.round}.{source.sequence}.{k + 1}"
            old = next((x for x in self.claims if x["id"] == cid), None)
        refs: list[contracts.JsonObject] = [json_object(ref) for ref in c["evidenceRefs"]]
        evidence, errors = evidence_state(refs, repository_paths=self.repository_paths)
        file: str = c["file"]
        view: str = str(Path(self.files[-1]).parent.parent / "draft" / file) if file else ""
        views: list[str] = [view] if view else []
        state: dict[str, str] = view_bindings(views, refs)
        revision: str = digest(
            {
                "claim": c["claim"],
                "citation": c["citation"],
                "evidence": evidence,
                "views": state,
            },
        )
        fresh: Claim = {
            "id": cid,
            "round": source.round,
            "by": source.agent,
            "claim": c["claim"],
            "file": file,
            "citation": c["citation"],
            "evidenceRefs": refs,
            "evidenceState": evidence,
            "evidenceErrors": errors,
            "views": views,
            "viewState": state,
            "revision": revision,
            "active": True,
            "legacy": False,
            "verdicts": [],
            "history": [],
        }
        if old:
            fresh["history"] = old["history"] + [
                json_object({key: v for key, v in old.items() if key != "history"}),
            ]
            if old["claim"] == c["claim"]:
                fresh["verdicts"] = old["verdicts"]
            self.claims[self.claims.index(old)] = fresh
        else:
            self.claims.append(fresh)
        for superseded in c["supersedes"]:
            target: contracts.Claim | None = next(
                (x for x in self.claims if x["id"] == superseded),
                None,
            )
            if not target or target["id"] == cid:
                continue
            target["active"] = False
            target["supersededBy"] = cid

    def _answers(self, source: RoundSource, answers: list[FindingAnswer]) -> None:
        ans: FindingAnswer
        n: int = source.round
        agent: str = source.agent
        for ans in answers:
            f: contracts.Finding | None = next(
                (x for x in self.findings if x["id"] == ans["findingId"]),
                None,
            )
            if not f or (f["owner"] and f["owner"] != agent):
                continue
            f["owner"] = agent
            f["answer"] = {
                "round": n,
                "response": ans["response"],
                "evidence": ans["evidence"],
            }


def _rounds(work: Path, roles: dict[str, str], assign: dict[str, str]) -> Ledger:
    """Fold every saved round result, in round order.

    Args:
        work: The architecture working directory.
        roles: Each roster agent's role.
        assign: Owners the coordinator assigned to findings.

    Returns:
        The ledger.

    Raises:
        ResumeError: A saved round result breaks its artifact-handoff schema.

    """
    p: Path
    n: int
    seq: int
    role: str
    agent: str
    ledger: Ledger = Ledger(assign, repository_paths=load_repository_paths(work))
    folder: Path = work / "rounds"
    found: list[tuple[int, int, str, str, Path]] = []
    for p in folder.iterdir() if folder.is_dir() else []:
        m: re.Match[str] | None = ROUND_FILE.match(p.name)
        if p.is_file() and m and roles.get(m.group(4)) == m.group(3):
            found.append((int(m.group(1)), int(m.group(2)), m.group(3), m.group(4), p))
    for n, seq, role, agent, p in sorted(found):
        source: RoundSource = RoundSource(n, seq, role, agent, str(p))
        try:
            if role in WRITER_ROLES:
                ledger.absorb_writer(source, parse_writer_result(p))
            else:
                ledger.absorb_review(source, parse_review_result(p))
        except (OSError, ValueError) as exc:
            message: str = f"round result {p}: {exc}"
            raise ResumeError(message) from exc
    return ledger


def _decision(work: Path, roles: dict[str, str]) -> DecisionFacts | None:
    """Read the saved decision's verdict and the fields branching uses.

    Args:
        work: The architecture working directory.
        roles: Each roster agent's role.

    Returns:
        The verdict, its round, the proposers it returned the target to and its owner-concern
        kinds; None when no decision is saved.

    Raises:
        ResumeError: Saved evidence cannot be decoded or validated.

    """
    r: JsonObject
    path: Path = work / "decision.json"
    if not path.is_file():
        return None
    dec: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = _load(path)
    if not isinstance(dec, dict):
        message: str = f"{path}: not a JSON object"
        raise ResumeError(message)
    returned: list[str] = []
    for r in check_type(
        dec.get("returnTo", []),
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        name: str = _text(r.get("agentType")).replace(AGENT_PREFIX, "") if isinstance(r, dict) else ""
        if roles.get(name) == "proposer" and name not in returned:
            returned.append(name)
    concerns: list[
        dict[str, bool | int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None]
    ] = [
        c
        for c in (
            check_type(
                dec.get("ownerConcerns", []),
                list[JsonObject],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        )
        if isinstance(c, dict) and _text(c.get("concern"))
    ]
    kinds: list[str] = [_text(c.get("kind")) for c in concerns]
    return {
        "verdict": _text(dec.get("verdict")),
        "round": check_type(dec.get("round", 0), int),
        "returnTo": returned,
        "ownerConcerns": len(concerns),
        "ownerConcernKinds": kinds,
        "ownerOnly": bool(kinds) and all(k in OWNER_CONCERN_KINDS for k in kinds),
        "choices": len(
            check_type(
                dec.get("choices", []),
                list[JsonValue],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            ),
        ),
    }


def _integration(work: Path) -> IntegrationFacts:
    """Read what the integration saved: its report's file lists, its fingerprint, its reviews.

    Args:
        work: The architecture working directory.

    Returns:
        The report's changed, created and deleted files with counts of its open items (None
        when no report is saved), whether a fingerprint was saved before it, and the number of
        reviews with the last one's verdict and reviewed files.

    Raises:
        ResumeError: Saved evidence cannot be decoded or validated.

    """
    n: int
    p: Path
    update: UpdateFacts | None = None
    path: Path = work / "architecture-update.json"
    if path.is_file():
        u: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = _load(path)
        if not isinstance(u, dict):
            message: str = f"{path}: not a JSON object"
            raise ResumeError(message)
        update = {
            "changedFiles": _paths(u.get("changedFiles")),
            "createdFiles": _paths(u.get("createdFiles")),
            "deletedFiles": _paths(u.get("deletedFiles")),
            "constraintIssues": len(_paths(u.get("constraintIssues"))),
            "contradictions": len(_paths(u.get("contradictions"))),
        }
    before: Path = work / "integrate-before.json"
    saved_before: bool = False
    if before.is_file():
        b: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = _load(before)
        saved_before = isinstance(b, dict) and isinstance(b.get("files"), dict)
    reviews: list[tuple[int, Path]] = sorted(
        (int(m.group(1)), p)
        for p in (work.iterdir() if work.is_dir() else [])
        if p.is_file() and (m := REVIEW_FILE.match(p.name))
    )
    last: ReviewFacts | None = None
    if reviews:
        n, p = reviews[-1]
        try:
            r: ConformanceResult = parse_conformance_result(p)
        except (OSError, ValueError) as exc:
            message = f"conformance review {p}: {exc}"
            raise ResumeError(message) from exc
        last = {
            "n": n,
            "path": str(p),
            "conforms": r["conforms"],
            "coverageChecks": len(r["coverageChecks"]),
            "reviewedFiles": len([f for f in r["reviewedFiles"] if f.strip()]),
            "findings": len(r["findings"]),
        }
    return {
        "update": update,
        "beforeSaved": saved_before,
        "reviews": len(reviews),
        "lastReview": last,
    }


def _baseline_out(baseline: BaselineFacts) -> JsonObject:
    """Project the survey assessment used by workflow branches.

    The entries stay in `survey.json`, which the sessions read; the workflow gets their
    count, and for each capability with design, documentation or unresolved work the
    requirement ids it serves (the text before the first colon of each requirement) and the
    kind of obligation it is.

    Args:
        baseline: `archbaseline.baseline_facts` of the survey.

    Returns:
        The facts.

    """
    scope: set[str] = set(baseline["designWork"]) | set(baseline["docWork"]) | set(baseline["unknowns"])
    entries: list[BaselineEntry] = [e for e in baseline["entries"] if e["id"] in scope]
    return json_object(
        {k: v for k, v in baseline.items() if k != "entries"}
        | {
            "entries": len(baseline["entries"]),
            "requirementsOf": {
                e["id"]: [str(r).split(":", 1)[0].strip() for r in e["requirements"] if str(r).split(":", 1)[0].strip()]
                for e in entries
            },
            "kindOf": {e["id"]: e["kind"] for e in entries},
        },
    )


@dataclass(frozen=True)
class ResumeOptions:
    """Explicit configuration for resume facts."""

    roster: str
    assign: str = ""
    team: str = ""
    plan: str = ""
    matrix_snapshot: JsonObject | None = None

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate every configured field before the operation.

        Raises:
            TypeError: A configured field violates its declared type.

        """
        if not all(isinstance(value, str) for value in (self.roster, self.assign, self.team, self.plan)):
            message: str = "Resume roster, assignment, team and plan must be strings"
            raise TypeError(message)
        if self.matrix_snapshot is not None and not isinstance(self.matrix_snapshot, dict):
            message = "Resume matrix snapshot must be a JSON object or None"
            raise TypeError(message)
        check_type(self.roster, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.assign, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.team, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.plan, str, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.matrix_snapshot, JsonObject | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _saved_survey(work: Path, warnings: list[str]) -> tuple[JsonObject, SurveyFacts | None]:
    """Read the current saved survey projection.

    Args:
        work: The architecture working directory.
        warnings: The resume warnings; a survey that breaks its contract is named here.

    Returns:
        The survey payload and its compact saved-state facts.

    """
    sj: Path = work / SURVEY_FILE
    if not sj.is_file():
        return {}, None
    raw: JsonValue = _load(sj)
    readable: bool = (work / "survey.md").is_file()
    try:
        saved: Survey = parse_survey(raw)
    except SurveyContractError as exc:
        warnings.append(f"{sj} breaks the survey contract and is treated as not saved: {exc}")
        return {}, {"saved": False, "readable": readable, "subject": "", "capabilities": 0, "coverageSaved": False}
    facts: SurveyFacts = {
        "saved": bool(saved["subject"]),
        "readable": readable,
        "subject": saved["subject"],
        "capabilities": len(saved["capabilities"]),
        "coverageSaved": bool(saved["coverage"]),
    }
    return json_object(raw), facts


def _historical_team(previous: JsonObject, work: Path) -> HistoricalTeam:
    """Read current historical author metadata or its explicit legacy predecessor.

    Returns:
        The author and exact saved result paths.

    """
    historical_raw: JsonValue = previous.get("historicalAuthoring")
    historical: HistoricalTeam
    if historical_raw is None:
        historical = {
            "author": check_type(json_object(previous.get("proposalTeam") or {}).get("lead", ""), str),
            "results": [str(path) for path in (work / "rounds").glob("r*-*.json")]
            if json_object(previous.get("proposalTeam") or {}).get("lead")
            else [],
        }
    else:
        historical = check_type(
            historical_raw,
            HistoricalTeam,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    return historical


def _finding_state(previous: JsonObject, ledger: Ledger, work: Path) -> tuple[list[OpenFinding], dict[str, int]]:
    """Reconcile findings with saved answers and current claim revisions.

    Returns:
        Open finding facts and the count of unreviewed claims by author.

    """
    finding: Finding
    c: Claim
    previous_findings: dict[str, contracts.Finding] = {
        f["id"]: f
        for f in check_type(
            previous.get("findings", []),
            list[Finding],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    }
    for finding in ledger.findings:
        claim: contracts.Claim | None = next((c for c in ledger.claims if c["id"] == finding["claimId"]), None)
        current_revision: str = claim["revision"] if claim else view_content(str(work / "draft" / finding["file"]))
        finding["initialRevision"] = (
            previous_findings[finding["id"]].get("initialRevision", finding["claimRevision"] or current_revision)
            if finding["id"] in previous_findings
            else finding["claimRevision"] or current_revision
        )
        finding["resolutionRevision"] = current_revision
        finding["resolution"] = next(
            (
                r
                for r in reversed(ledger.resolutions)
                if r.get("findingId") == finding["id"]
                and r.get("evidence")
                and r["by"] != finding["owner"]
                and finding["answer"]
                and r["round"] >= finding["answer"]["round"]
                and (
                    finding["answer"].get("response") == RESPONSE_DISPUTED
                    or current_revision != finding["initialRevision"]
                )
            ),
            None,
        )
    open_findings: list[OpenFinding] = [
        {
            "id": f["id"],
            "verdict": f["verdict"],
            "owner": f["owner"],
            "file": f["file"],
            "answered": bool(f["answer"])
            and not (f["resolution"] and f["resolution"].get("verdict") == RESOLUTION_REJECTED),
        }
        for f in ledger.findings
        if f["verdict"] != VERDICT_VERIFIED
        and not (f["resolution"] and f["resolution"].get("verdict") == RESOLUTION_ACCEPTED)
    ]
    unreviewed: dict[str, int] = {}
    for c in ledger.claims:
        if c["active"] and not c["verdicts"]:
            unreviewed[c["by"]] = unreviewed.get(c["by"], 0) + 1
    return open_findings, unreviewed


@dataclass(frozen=True)
class _ResumeInputs:
    roles: dict[str, str]
    warnings: list[str]
    raw_survey: JsonObject
    survey: SurveyFacts | None
    previous: JsonObject
    historical: HistoricalTeam
    assignments: dict[str, str]
    ledger: Ledger


def _resume_inputs(work: Path, options: ResumeOptions) -> _ResumeInputs:
    s: JsonObject
    survey: SurveyFacts | None
    roles: dict[str, str] = parse_roster(options.roster)
    LENIENT_READS.clear()
    warnings: list[str] = sweep_unreadable(work)
    s, survey = _saved_survey(work, warnings)
    ledger_path: Path = work / LEDGER_NAME
    previous: dict[str, contracts.JsonValue] = json_object(_load(ledger_path)) if ledger_path.is_file() else {}
    historical: HistoricalTeam = _historical_team(previous, work)
    assignments: dict[str, str] = check_type(
        previous.get("assignments", {}),
        dict[str, str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    assignments.update(parse_assign(options.assign))
    ledger: Ledger = _rounds(work, roles, assignments)
    return _ResumeInputs(roles, warnings, s, survey, previous, historical, assignments, ledger)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def resume_facts(work_dir: str, options: ResumeOptions) -> ResumeFacts:
    """Read the architecture step's saved work and return the facts its control flow needs.

    Writes the whole claim and finding ledger to `ledger.json` in the working directory, for the
    sessions that read it; prints none of it.

    Args:
        work_dir: The architecture working directory of one Epic.
        options: Validated roster, assignments, plan, and matrix snapshot inputs.

    Returns:
        The compact facts: survey, rounds, decision and integration, and `warnings` naming every
        saved file set aside or read past a receipt that no longer matched.

    Raises:
        TypeError: The directory or options argument has the wrong type.

    """
    coverage: archcoverage.CoverageFacts
    coverage_summary: CoverageSummary
    open_findings: list[OpenFinding]
    unreviewed: dict[str, int]
    if not isinstance(work_dir, str) or not isinstance(options, ResumeOptions):
        message: str = "resume_facts requires a directory string and ResumeOptions"
        raise TypeError(message)
    work: Path = Path(work_dir)
    inputs: _ResumeInputs = _resume_inputs(work, options)
    ledger_path: Path = work / LEDGER_NAME
    coverage, coverage_summary = coverage_facts(
        parse_survey(inputs.raw_survey) if inputs.raw_survey else None,
        inputs.ledger.coverage,
        repository_paths=inputs.ledger.repository_paths,
    )
    rounds: roundcontracts.RoundFacts = round_facts(
        work,
        RoundInputs(
            plans=check_type(
                inputs.previous.get("roundPlans", []),
                list[RoundPlan],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            ),
            incoming=check_type(
                json.loads(options.plan),
                RoundPlan,
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
            if options.plan
            else None,
            roles=inputs.roles,
            coverage=[{"id": row["id"], "revision": row["revision"]} for row in coverage["coverage"]],
        ),
        inputs.ledger,
    )
    open_findings, unreviewed = _finding_state(inputs.previous, inputs.ledger, work)
    baseline: contracts.BaselineFacts = baseline_facts(
        inputs.raw_survey,
        options.matrix_snapshot,
        repository_paths=inputs.ledger.repository_paths,
    )
    # Bind approval to the assessed baseline and claims; per-row checks stay reusable.
    coverage_summary["revision"] = digest(
        {
            "coverage": coverage_summary["revision"],
            "baseline": baseline["revision"],
            "claims": [{"id": c["id"], "revision": c["revision"]} for c in inputs.ledger.claims if c["active"]],
        },
    )
    coverage["coverageRevision"] = coverage_summary["revision"]
    coverage_summary["gaps"].extend(rounds["reviewGaps"])
    repairs: list[archrepairs.RepairRequest] = repair_facts(
        work,
        check_type(
            inputs.previous.get("repairRequests", []),
            list[RepairRequest],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        ),
        inputs.ledger.files,
        inputs.historical,
        rounds["plans"],
    )
    repair_summary: dict[str, list[str]] = {
        "open": [r["id"] for r in repairs if r["status"] == "open"],
        "checksNeeded": [r["id"] for r in repairs if r["status"] == "answered"],
    }
    if work.is_dir():
        save_ledger(
            ledger_path,
            json_object({
                "contractVersion": 2,
                "historicalAuthoring": inputs.historical,
                "assignments": inputs.assignments,
                "roundPlans": rounds["plans"],
                "claims": inputs.ledger.claims,
                "findings": inputs.ledger.findings,
                "savedResults": inputs.ledger.files,
                "repairRequests": repairs,
                **coverage,
            }),
        )
    integration: IntegrationFacts = _integration(work)
    decision: DecisionFacts | None = _decision(work, inputs.roles)
    if decision:
        decision["returnTo"] = sorted(
            {r["agentType"] for r in repairs if r["status"] == "open"},
        )
        decision["repairChecksNeeded"] = repair_summary["checksNeeded"]
    return {
        "contractVersion": check_type(inputs.previous.get("contractVersion", 1), int),
        "dir": str(work),
        "exists": work.is_dir(),
        "ledger": str(ledger_path) if work.is_dir() else None,
        "survey": inputs.survey,
        "baseline": _baseline_out(baseline),
        "coverage": coverage_summary,
        "historicalAuthoring": inputs.historical,
        "rounds": {
            "last": rounds["last"],
            "resumeRound": rounds["resumeRound"],
            "pendingPlan": compact_plan(rounds["pendingPlan"]),
            "pendingRound": rounds["pendingPlan"]["round"] if rounds["pendingPlan"] else None,
            "pendingDispatches": len(rounds["pendingPlan"]["dispatches"]) if rounds["pendingPlan"] else 0,
            "planKept": rounds["planKept"],
            "readyForDecision": bool(
                rounds["plans"] and rounds["plans"][-1].get("complete") and rounds["plans"][-1].get("readyForDecision"),
            ),
            "results": len(inputs.ledger.files),
            "saved": inputs.ledger.saved,
            "writers": inputs.ledger.writers,
            "reviewers": inputs.ledger.reviewers,
            "proposersWithoutClaims": sorted(
                w
                for w, count in inputs.ledger.proposer_claims.items()
                if not count
                and any(
                    w == Path(name).stem.split("-", 3)[3] and name not in inputs.historical.get("results", [])
                    for name in inputs.ledger.files
                )
            ),
            "claims": len(inputs.ledger.claims),
            "findings": len(inputs.ledger.findings),
            "openFindings": open_findings,
            "unreviewedClaims": unreviewed,
            "overlapWarnings": rounds["overlapWarnings"],
        },
        "decision": decision,
        "repairs": repair_summary,
        "integration": integration,
        "warnings": inputs.warnings
        + rounds["warnings"]
        + [f"read as saved, receipt not matching: {w}" for w in LENIENT_READS],
        "summary": {
            "survey": bool(inputs.survey and inputs.survey["saved"]),
            "lastRound": inputs.ledger.last,
            "claims": len(inputs.ledger.claims),
            "findings": len(inputs.ledger.findings),
            "openFindings": len(open_findings),
            "decision": decision["verdict"] if decision else None,
            "update": integration["update"] is not None,
            "reviews": integration["reviews"],
        },
    }
