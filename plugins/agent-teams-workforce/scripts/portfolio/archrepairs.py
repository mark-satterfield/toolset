"""Persist decision repair progress separately from repeated decision prose."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict

import contracts
from contracts import JsonInput, JsonObject, json_object
from jsonartifact import read_artifact
from roundcontracts import RoundPlan
from typeguard import CollectionCheckStrategy, check_type, typechecked


class HistoricalTeam(TypedDict):
    """The exact legacy writer attribution preserved in the ledger."""

    author: str
    results: list[str]


class RepairAnswer(TypedDict):
    """The response to a named architecture repair."""

    repairId: str
    response: str


class RecordedAnswer(TypedDict):
    """The writer evidence attached to an answered repair."""

    by: str
    result: str
    legacy: bool
    responses: list[RepairAnswer]


class RepairRequest(TypedDict):
    """The exact durable repair record produced by repair_facts."""

    id: str
    agentType: str
    missing: str
    decisionRound: int
    decisionTime: NotRequired[float]
    status: str
    revision: str
    files: list[str]
    warnings: NotRequired[list[str]]
    answeredBy: NotRequired[str]
    answer: NotRequired[RecordedAnswer]
    review: NotRequired[JsonObject]
    bindingError: NotRequired[str]


def _hash(value: JsonInput) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _requests(work: Path, previous: list[RepairRequest]) -> dict[str, RepairRequest]:
    returned: JsonObject
    requests: dict[str, RepairRequest] = {
        r["id"]: check_type(dict(r), RepairRequest, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        for r in previous
    }
    decision_path: Path = work / "decision.json"
    decision: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = (
        read_artifact(decision_path, strict=False) if decision_path.is_file() else {}
    )
    if not isinstance(decision, dict):
        decision = {}
    for returned in check_type(
        decision.get("returnTo") or [],
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ):
        if not isinstance(returned, dict) or not returned.get("missing"):
            continue
        agent: str = str(returned.get("agentType", "")).removeprefix(
            "agent-teams-workforce:",
        )
        key: str = "R" + _hash([agent, returned["missing"]])[:20]
        requests.setdefault(
            key,
            {
                "id": key,
                "agentType": agent,
                "missing": check_type(returned["missing"], str),
                "decisionRound": check_type(decision.get("round", 0), int),
                "decisionTime": decision_path.stat().st_mtime,
                "status": "open",
                "revision": _hash([key, "unbound"]),
                "files": [],
            },
        )
    return requests


def _review(work: Path, request: RepairRequest, name: str, agent: str, checks: list[JsonObject]) -> None:
    check: JsonObject
    for check in checks:
        if isinstance(check, dict) and check.get("repairId") == request["id"] and check.get("evidence"):
            request["review"] = {**check, "by": agent, "result": name}
            if check.get("verdict") == "verified":
                files: list[str] = [
                    f
                    for f in check_type(
                        check.get("files") or [],
                        list[str],
                        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                    )
                    if isinstance(f, str) and f.strip()
                ]
                readable: list[str] = [f for f in files if _readable(work, [f])]
                request.pop("bindingError", None)
                if len(readable) != len(files) or not files:
                    request["warnings"] = [
                        "the verified check names no readable evidence file"
                        if not readable
                        else "some evidence files the verified check names are unreadable",
                    ]
                request["files"] = sorted(set(readable))
                request["revision"] = _revision(
                    work,
                    request["id"],
                    request["files"],
                )
                request["status"] = "resolved"
            elif check.get("verdict") == "revise":
                request["status"] = "open"


@dataclass
class _RepairEvidence:
    work: Path
    historical: HistoricalTeam
    plans: list[RoundPlan]

    def apply(self, request: RepairRequest, name: str) -> None:
        round_name: str
        seq: str
        role: str
        agent: str
        if not (isinstance(request, dict)) or not (isinstance(name, str)):
            argument_error: str = "apply: arguments do not satisfy the declared input contract"
            raise TypeError(argument_error)
        path: Path = Path(name)
        round_name, seq, role, agent = path.stem.split("-", 3)
        n: int = int(round_name[1:])
        result: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = read_artifact(
            path,
            strict=False,
        )
        if not isinstance(result, dict):
            return
        result = json_object(result)
        answers: list[RepairAnswer] = check_type(
            result.get("repairAnswers", []),
            list[RepairAnswer],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        checks: list[contracts.JsonObject] = check_type(
            result.get("repairChecks", []),
            list[JsonObject],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        assigned: set[str] = {
            d.get("agentType")
            for plan in self.plans
            if plan.get("round") == n
            for d in plan.get("dispatches", [])
            if request["id"] in d.get("repairIds", []) and d.get("seq") == int(seq) and d.get("role") == role
        }
        permitted: set[str] = {request["agentType"], *assigned}
        if name in self.historical.get("results", []):
            permitted.add(self.historical.get("author", ""))
        if role in {"proposer", "diagram"}:
            explicit: bool = any(
                a.get("repairId") == request["id"] and a.get("response") for a in answers if isinstance(a, dict)
            )
            legacy: bool = (
                n > request["decisionRound"]
                or (n == request["decisionRound"] and path.stat().st_mtime > request.get("decisionTime", float("inf")))
            ) and agent in permitted
            if request["status"] == "open" and agent in permitted and (explicit or legacy):
                request["status"] = "answered"
                request["answeredBy"] = agent
                request["answer"] = {
                    "by": agent,
                    "result": name,
                    "legacy": not explicit,
                    "responses": [a for a in answers if isinstance(a, dict) and a.get("repairId") == request["id"]],
                }
        elif agent not in {request["agentType"], request.get("answeredBy")}:
            _review(self.work, request, name, agent, checks)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def repair_facts(
    work: Path,
    previous: list[RepairRequest],
    results: list[str],
    historical: HistoricalTeam,
    plans: list[RoundPlan],
) -> list[RepairRequest]:
    """Keep completed repairs reviewable without repeatedly dispatching their maker.

    A check counts for its repair by `repairId`. A verified repair stays resolved when the
    files it was verified against change later (the change is noted in `warnings`), and a
    verified check that names no readable evidence file still resolves it, with a warning.

    Returns:
        The updated repair records.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    request: RepairRequest
    name: str
    if (
        not (isinstance(work, Path))
        or not (isinstance(previous, list))
        or not (isinstance(results, list))
        or not (isinstance(historical, dict))
        or not (isinstance(plans, list))
    ):
        argument_error: str = "repair_facts: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    requests: dict[str, RepairRequest] = _requests(work, previous)
    evidence: _RepairEvidence = _RepairEvidence(work, historical, plans)
    for request in requests.values():
        revision: str = _revision(work, request["id"], request.get("files", []))
        if request["revision"] != revision:
            if request["status"] == "resolved":
                request["warnings"] = [
                    "the files this repair was verified against changed since",
                ]
            request["revision"] = revision
        for name in results:
            evidence.apply(request, name)
    return list(requests.values())


def _revision(work: Path, repair_id: str, files: list[str]) -> str:
    """Bind acceptance only to the views/contracts independently named by its checker.

    Returns:
        The content revision of bound evidence.

    """
    name: str
    if not files:
        return _hash([repair_id, "unbound"])
    evidence: dict[str, str] = {}
    for name in files:
        path: Path = Path(name)
        if not path.is_absolute():
            path = work / "draft" / path
        try:
            evidence[str(path)] = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent or not a regular file"
            )
        except FileNotFoundError:
            evidence[str(path)] = "absent"
        except OSError as exc:
            evidence[str(path)] = f"unreadable: {exc}"
    return _hash(evidence)


def _readable(work: Path, files: list[str]) -> bool:
    """Refuse acceptance bound to an absent or unreadable alleged evidence file.

    Returns:
        Whether all named evidence files can be read.

    """
    name: str
    for name in files:
        path: Path = Path(name)
        if not path.is_absolute():
            path = work / "draft" / path
            if not path.resolve().is_relative_to((work / "draft").resolve()):
                return False
        try:
            if not path.is_file():
                return False
            path.read_bytes()
        except OSError:
            return False
    return True
