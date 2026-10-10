"""Durable round plans consumed by archresume and architecture.js; no dispatch here."""

from __future__ import annotations

import hashlib
import json
import os
import typing
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path

import contracts
import roundcontracts
from archevidence import digest
from contracts import Claim, JsonObject, json_object
from jsonartifact import read_artifact
from roundcontracts import CompactPlan, Dispatch, RevisionRef, RoundFacts, RoundLedger, RoundPlan
from typeguard import CollectionCheckStrategy, check_type, typechecked


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def set_aside(path: Path) -> str:
    """Move a saved file that cannot be used out of the way, with its receipt sidecars.

    The file is renamed `<name>.unreadable-<timestamp>`, a name no reader of the working
    directory matches, so the step it belongs to runs again.

    Args:
        path: The file.

    Returns:
        The new path.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    suffix: str | str
    if not (isinstance(path, Path)):
        argument_error: str = "set_aside: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    stamp: str = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    moved: Path = path.with_name(f"{path.name}.unreadable-{stamp}")
    path.rename(moved)
    for suffix in (".receipt", ".publish"):
        sidecar: Path = path.with_name(path.name + suffix)
        if sidecar.is_file():
            sidecar.rename(moved.with_name(moved.name + suffix))
    return str(moved)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def save_ledger(path: Path, payload: JsonObject) -> None:
    """Atomically publish the ledger payload.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(path, Path)) or not (isinstance(payload, Mapping)):
        argument_error: str = "save_ledger: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    temporary: Path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    temporary.replace(path)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def overlap_justified(plan: RoundPlan, claim: Claim, reviewers: list[Dispatch]) -> bool:
    """Return whether the plan states a reason for several reviewers sharing one claim.

    The coordinator states one reason per overlap in the plan's ``overlaps``. A plan
    saved before that field existed counts as justified when any overlapping dispatch
    carries a non-empty ``overlapReason``.

    Returns:
        True when a plan-level overlap entry or a legacy dispatch reason covers it.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    entry: roundcontracts.Overlap
    if not (isinstance(plan, dict)) or not (isinstance(reviewers, list)):
        argument_error: str = "overlap_justified: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    names: set[str] = {d.get("agentType") for d in reviewers}
    for entry in plan.get("overlaps") or []:
        if not isinstance(entry, dict) or not str(entry.get("reason", "")).strip():
            continue
        agents: set[str] = {str(a).strip() for a in entry.get("agentTypes") or [] if a}
        if agents and not names <= agents:
            continue
        files: set[str] = {str(f).strip().lstrip("/") for f in entry.get("files") or [] if f}
        if claim["id"] in (entry.get("claimIds") or []) or claim.get("file") in files:
            return True
    return any(str(d.get("overlapReason", "")).strip() for d in reviewers)


def _recorded_meta(path: Path) -> dict[str, str]:
    """Read a result receipt when it still describes the bytes on disk.

    Returns:
        Its content hash and update timestamp, or no trusted receipt.

    """
    try:
        meta: JsonObject = json_object(json.loads(path.with_name(path.name + ".meta.json").read_text()))
        return (
            {"sha256": check_type(meta["sha256"], str), "updated_at": check_type(meta.get("updated_at", ""), str)}
            if isinstance(meta, dict) and meta.get("sha256") == hashlib.sha256(path.read_bytes()).hexdigest()
            else {}
        )
    except OSError, ValueError:
        return {}


@dataclass(frozen=True)
class RoundInputs:
    """The saved and incoming plans with their roster and coverage bindings."""

    plans: list[RoundPlan]
    incoming: RoundPlan | None
    roles: dict[str, str]
    coverage: Sequence[RevisionRef] | None = None

    def __post_init__(self) -> None:
        """Validate every nested input record.

        Raises:
            TypeError: A configured field violates its declared type.

        """
        if not isinstance(self.plans, list) or any(not isinstance(plan, dict) for plan in self.plans):
            message: str = "Round plans must be a list of plan objects"
            raise TypeError(message)
        if self.incoming is not None and not isinstance(self.incoming, dict):
            message = "Incoming round plan must be an object or None"
            raise TypeError(message)
        if not isinstance(self.roles, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in self.roles.items()
        ):
            message = "Round roles must map strings to strings"
            raise TypeError(message)
        if self.coverage is not None and (
            not isinstance(self.coverage, Sequence) or isinstance(self.coverage, (str, bytes, bytearray))
        ):
            message = "Round coverage must be a sequence of revision references or None"
            raise TypeError(message)
        check_type(self.plans, list[RoundPlan], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.incoming, RoundPlan | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.roles, dict[str, str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(
            self.coverage,
            Sequence[RevisionRef] | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )


@dataclass
class _RoundState:
    work: Path
    inputs: RoundInputs
    ledger: RoundLedger
    notes: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def _resume(self, plans: list[RoundPlan]) -> int | None:
        ledger: RoundLedger
        work: Path
        ledger, work = self.ledger, self.work
        legacy_round: int = ledger.last if not plans else 0
        decision_path: Path = work / "decision.json"
        decision: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = (
            read_artifact(decision_path, strict=False) if decision_path.is_file() else {}
        )
        decision_object: dict[str, contracts.JsonValue] = json_object(decision)
        decision_meta: dict[str, str] = _recorded_meta(decision_path)
        newer_results: bool = any(
            Path(name).name.startswith(f"r{legacy_round}-")
            and (meta := _recorded_meta(Path(name)))
            and (not decision_meta or meta.get("updated_at", "") > decision_meta.get("updated_at", ""))
            for name in ledger.files
        )
        return (
            legacy_round
            if legacy_round and (legacy_round > check_type(decision_object.get("round", 0), int) or newer_results)
            else None
        )

    def _merge(self, plans: list[RoundPlan], incoming: RoundPlan | None, resume_round: int | None) -> str:
        ledger: RoundLedger
        work: Path
        name: str
        rn: str
        saved_seq: str
        saved_role: str
        agent: str
        ledger, work = self.ledger, self.work
        kept: str = ""
        if incoming:
            same: roundcontracts.RoundPlan | None = next(
                (p for p in plans if p["round"] == incoming.get("round")),
                None,
            )
            if same is not None and same is plans[-1] and not _done(work, same):
                # The saved plan of an unfinished round stands; its missing dispatches run.
                kept = (
                    f"round {same['round']} already has a saved plan that is not complete; "
                    "the saved plan is kept and the new plan was not saved"
                )
            elif same is not None:
                kept = (
                    f"round {same['round']} already has a saved plan; "
                    "the saved plan is kept and the new plan was not saved"
                )
            elif plans and not _done(work, plans[-1]):
                kept = (
                    f"round {plans[-1]['round']} is unfinished; its saved plan is kept and the new plan was not saved"
                )
            else:
                if resume_round:
                    incoming = deepcopy(incoming)
                    incoming["round"] = resume_round
                    saved: list[Dispatch] = []
                    for name in ledger.files:
                        path: Path = Path(name)
                        rn, saved_seq, saved_role, agent = path.stem.split("-", 3)
                        if int(rn[1:]) == resume_round:
                            saved.append(
                                {
                                    "seq": int(saved_seq),
                                    "role": saved_role,
                                    "agentType": agent,
                                    "legacySaved": True,
                                    "task": "Preserve completed saved work",
                                    "files": [],
                                    "answers": [],
                                },
                            )
                    incoming["dispatches"] = sorted(saved, key=itemgetter("seq")) + incoming["dispatches"]
                    incoming["legacyContinuation"] = True
                plans.append(incoming)

        return kept

    def _normalize(self, plans: list[RoundPlan]) -> list[RoundPlan]:
        roles: dict[str, str]
        notes: list[str]
        plan: RoundPlan
        d: Dispatch
        roles, notes = self.inputs.roles, self.notes
        usable: list[RoundPlan] = []
        for plan in plans:
            n: int = plan.get("round") if isinstance(plan, dict) else None
            if not isinstance(n, int) or n < 1 or not isinstance(plan.get("dispatches"), list):
                notes.append(f"a saved round plan that is not a plan was dropped: {n!r}")
                continue
            usable.append(plan)
            kept_dispatches: list[roundcontracts.Dispatch] = []
            for d in plan["dispatches"]:
                assigned_role: str | None = roles.get(d.get("agentType")) if isinstance(d, dict) else None
                if assigned_role is None:
                    notes.append(
                        f"round {n}: dispatch {d.get('agentType') if isinstance(d, dict) else d!r} "
                        "is not on the roster and was dropped",
                    )
                    continue
                if d.get("role") != assigned_role:
                    notes.append(
                        f"round {n}: {d['agentType']} runs as {assigned_role}, its roster role",
                    )
                    d["role"] = assigned_role
                kept_dispatches.append(d)
            plan["dispatches"] = kept_dispatches
        return usable

    def _settle(self, plan: RoundPlan) -> list[Dispatch]:
        work: Path
        notes: list[str]
        ordinal: int
        d: Dispatch
        work, notes = self.work, self.notes
        n: int = plan.get("round")
        dispatches: list[roundcontracts.Dispatch] = plan["dispatches"]
        writers: list[roundcontracts.Dispatch] = [d for d in dispatches if d.get("role") in {"proposer", "diagram"}]
        # A plan saved before the last writer was chosen by position may carry this field.
        plan.pop("designOwner", None)
        for ordinal, d in enumerate(dispatches, 1):
            seq: int = (
                d.get("seq", ordinal)
                if d.get("legacySaved")
                else max([x.get("seq", 0) for x in dispatches[: ordinal - 1]] + [0]) + 1
            )
            d["seq"] = seq
            d.pop("designOwner", None)
            file: Path = work / "rounds" / f"r{n}-{seq}-{d['role']}-{d['agentType']}.json"
            d["file"] = str(file)
            d["complete"] = file.is_file()
            if file.is_file():
                try:
                    result: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = (
                        read_artifact(file, strict=False)
                    )
                except OSError, UnicodeDecodeError, ValueError:
                    result = None
                required: tuple[str, ...] = ("files", "claims", "answers") if d in writers else ("findings",)
                if not d.get("legacySaved"):
                    required += ("coverage",) if d in writers else ("coverageChecks",)
                if not isinstance(result, dict) or any(not isinstance(result.get(k), list) for k in required):
                    notes.append(
                        f"malformed saved dispatch result set aside: {set_aside(file)}",
                    )
                    d["complete"] = False
        return writers

    def _assign(self, plan: RoundPlan, writers: list[Dispatch]) -> None:
        ledger: RoundLedger
        notes: list[str]
        n: int
        dispatches: list[Dispatch]
        d: Dispatch
        ids: list[str]
        files: list[str]
        ledger, notes = self.ledger, self.notes
        n, dispatches = plan["round"], plan["dispatches"]
        for d in dispatches:
            if d in writers or "assignedClaims" in d:
                continue
            ids, files = d.get("claimIds", []), d.get("claimFiles", [])
            known: set[str] = {c["id"] for c in ledger.claims}
            unknown: list[str] = [i for i in ids if i not in known]
            if unknown:
                notes.append(
                    f"round {n}: {d.get('agentType')} was assigned unknown claim(s) "
                    f"{', '.join(unknown)}; they were dropped",
                )
                ids = [i for i in ids if i in known]
                d["claimIds"] = ids
            d["assignedClaims"] = [
                {"id": c["id"], "revision": c["revision"]}
                for c in ledger.claims
                if c["active"] and (c["id"] in ids or (c["file"] in files and c["round"] == n))
            ]

    def _gaps(self, plan: RoundPlan) -> None:
        ledger: RoundLedger
        warnings: list[str]
        gaps: list[str]
        n: int
        dispatches: list[Dispatch]
        d: Dispatch
        c: RevisionRef
        reviewers: list[Dispatch]
        cid: str
        _revision: str
        ledger, warnings, gaps = self.ledger, self.warnings, self.gaps
        n, dispatches = plan["round"], plan["dispatches"]
        by_claim: dict[tuple[str, str], list[Dispatch]] = {}
        for d in dispatches:
            for c in d.get("assignedClaims", []):
                by_claim.setdefault((c["id"], c["revision"]), []).append(d)
        for (cid, _revision), reviewers in by_claim.items():
            claim: contracts.Claim = next(c for c in ledger.claims if c["id"] == cid)
            if len(reviewers) > 1 and not overlap_justified(plan, claim, reviewers):
                warning: str = (
                    f"round {n}: claim {cid} is reviewed by "
                    f"{', '.join(d['agentType'] for d in reviewers)} "
                    "with no stated overlap reason"
                )
                if warning not in warnings:
                    warnings.append(warning)
            if not claim["active"]:
                continue
            for d in reviewers:
                if not any(v["by"] == d["agentType"] for v in claim["verdicts"]):
                    gaps.append(
                        f"claim {cid} lacks assigned review by {d['agentType']}",
                    )

    def _revisions(self, plan: RoundPlan, writers: list[Dispatch]) -> None:
        ledger: RoundLedger
        coverage: typing.Sequence[RevisionRef] | None
        d: Dispatch
        ledger, coverage = self.ledger, self.inputs.coverage
        dispatches: list[roundcontracts.Dispatch] = plan["dispatches"]
        for d in dispatches:
            if d in writers:
                continue
            selected: set[str] = {c["id"] for c in d.get("assignedClaims", [])}
            scope: set[str] = set(d.get("coverageIds") or [])
            rows: list[roundcontracts.RevisionRef] = [
                row for row in coverage or [] if not scope or row.get("id") in scope
            ]
            d["reviewInputRevision"] = digest(
                {
                    "task": d.get("task", ""),
                    "selectionReason": d.get("selectionReason", ""),
                    "claims": [
                        {"id": c["id"], "revision": c["revision"]} for c in ledger.claims if c["id"] in selected
                    ],
                    "coverage": [{"id": row["id"], "revision": row["revision"]} for row in rows],
                    "repairs": d.get("repairIds", []),
                    "findings": [
                        json_object(finding)
                        for finding in ledger.findings
                        if d.get("repairIds") or finding.get("claimId") in selected
                    ],
                },
            )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def result(self) -> RoundFacts:
        """Settle all plans and return their durable projection.

        Returns:
            The plans and explicit reconciliation diagnostics.

        """
        inputs: RoundInputs
        ledger: RoundLedger
        plan: RoundPlan
        state: _RoundState = self
        inputs, ledger = self.inputs, self.ledger
        plans: list[roundcontracts.RoundPlan] = deepcopy(inputs.plans)
        resume_round: int | None = state._resume(plans)
        kept: str = state._merge(plans, inputs.incoming, resume_round)
        plans = state._normalize(plans)
        for plan in plans:
            writers: list[roundcontracts.Dispatch] = state._settle(plan)
            if all(dispatch["complete"] for dispatch in writers):
                state._assign(plan, writers)
                state._gaps(plan)
            state._revisions(plan, writers)
            plan["complete"] = all(dispatch["complete"] for dispatch in plan["dispatches"])
        pending: roundcontracts.RoundPlan | None = next((plan for plan in plans if not plan["complete"]), None)
        last: int = max(
            [ledger.last if not pending else pending["round"] - 1]
            + [plan["round"] for plan in plans if plan["complete"]],
        )
        return {
            "plans": plans,
            "resumeRound": resume_round if not plans else None,
            "last": last,
            "pendingPlan": pending,
            "reviewGaps": state.gaps,
            "overlapWarnings": state.warnings,
            "planKept": kept,
            "warnings": state.notes,
        }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def round_facts(work: Path, inputs: RoundInputs, ledger: RoundLedger) -> RoundFacts:
    """Settle durable plans and bind review to the actual writer revisions.

    Returns:
        Saved identities, the pending plan, and reconciliation diagnostics.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(work, Path)) or not (isinstance(inputs, RoundInputs)) or not (isinstance(ledger, RoundLedger)):
        argument_error: str = "round_facts: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    return _RoundState(work, inputs, ledger).result()


def _done(work: Path, plan: RoundPlan) -> bool:
    """Return whether every dispatch of a saved plan has its result file on disk.

    Returns:
        True when each dispatch's result file exists (an empty plan is done).

    """
    n: int = plan.get("round")
    return all(
        (work / "rounds" / f"r{n}-{d.get('seq', seq)}-{d.get('role')}-{d.get('agentType')}.json").is_file()
        for seq, d in enumerate(plan.get("dispatches") or [], 1)
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def compact_plan(plan: RoundPlan | None) -> CompactPlan | None:
    """Return the pending plan as the few facts architecture.js branches on.

    The full plan (each dispatch's task, claim assignments and result file) stays in
    ledger.json, where the dispatched sessions read it; printing it would pass tens of
    kilobytes through the runner that relays this output.

    Returns:
        None for no plan, else round, readyForDecision and each dispatch's identity.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(plan, dict) or plan is None):
        argument_error: str = "compact_plan: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    if not plan:
        return None
    return {
        "round": plan["round"],
        "readyForDecision": bool(plan.get("readyForDecision")),
        "complete": bool(plan.get("complete")),
        "dispatches": [
            {
                "seq": d["seq"],
                "role": d.get("role"),
                "agentType": d.get("agentType"),
                "complete": bool(d.get("complete")),
                "coverageIds": list(d.get("coverageIds") or []),
                "claimIds": list(d.get("claimIds") or []),
                "claimFiles": list(d.get("claimFiles") or []),
                "reviewInputRevision": d.get("reviewInputRevision", ""),
                "files": list(d.get("files") or []),
                "answers": list(d.get("answers") or []),
                "assignedClaimCount": len(d.get("assignedClaims") or []),
            }
            for d in plan["dispatches"]
        ],
    }
