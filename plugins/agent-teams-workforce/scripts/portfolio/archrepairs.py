"""Persist decision repair progress separately from repeated decision prose."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonartifact import read_artifact


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def repair_facts(
    work: Path, previous: list, results: list[str], historical: dict, plans: list
) -> list:
    """Keep completed repairs reviewable without repeatedly dispatching their maker.

    A check counts for its repair by `repairId`. A verified repair stays resolved when the
    files it was verified against change later (the change is noted in `warnings`), and a
    verified check that names no readable evidence file still resolves it, with a warning.
    """
    requests = {r["id"]: dict(r) for r in previous}
    decision_path = work / "decision.json"
    decision = (
        read_artifact(decision_path, strict=False) if decision_path.is_file() else {}
    )
    if not isinstance(decision, dict):
        decision = {}
    for returned in decision.get("returnTo") or []:
        if not isinstance(returned, dict) or not returned.get("missing"):
            continue
        agent = str(returned.get("agentType", "")).removeprefix(
            "agent-teams-workforce:"
        )
        key = "R" + _hash([agent, returned["missing"]])[:20]
        requests.setdefault(
            key,
            {
                "id": key,
                "agentType": agent,
                "missing": returned["missing"],
                "decisionRound": decision.get("round", 0),
                "decisionTime": decision_path.stat().st_mtime,
                "status": "open",
                "revision": _hash([key, "unbound"]),
                "files": [],
            },
        )
    for request in requests.values():
        revision = _revision(work, request["id"], request.get("files", []))
        if request["revision"] != revision:
            if request["status"] == "resolved":
                request["warnings"] = [
                    "the files this repair was verified against changed since"
                ]
            request["revision"] = revision
        for name in results:
            path = Path(name)
            round_name, seq, role, agent = path.stem.split("-", 3)
            n = int(round_name[1:])
            result = read_artifact(path, strict=False)
            if not isinstance(result, dict):
                continue
            assigned = {
                d.get("agentType")
                for plan in plans
                if plan.get("round") == n
                for d in plan.get("dispatches", [])
                if request["id"] in d.get("repairIds", [])
                and d.get("seq") == int(seq)
                and d.get("role") == role
            }
            permitted = {request["agentType"], *assigned}
            if name in historical.get("results", []):
                permitted.add(historical.get("author", ""))
            if role in ("proposer", "diagram"):
                explicit = any(
                    a.get("repairId") == request["id"] and a.get("response")
                    for a in result.get("repairAnswers", [])
                    if isinstance(a, dict)
                )
                legacy = (
                    n > request["decisionRound"]
                    or (
                        n == request["decisionRound"]
                        and path.stat().st_mtime
                        > request.get("decisionTime", float("inf"))
                    )
                ) and agent in permitted
                if (
                    request["status"] == "open"
                    and agent in permitted
                    and (explicit or legacy)
                ):
                    request["status"] = "answered"
                    request["answeredBy"] = agent
                    request["answer"] = {
                        "by": agent,
                        "result": name,
                        "legacy": not explicit,
                        "responses": [
                            a
                            for a in result.get("repairAnswers", [])
                            if isinstance(a, dict)
                            and a.get("repairId") == request["id"]
                        ],
                    }
            elif agent not in (request["agentType"], request.get("answeredBy")):
                for check in result.get("repairChecks", []):
                    if (
                        isinstance(check, dict)
                        and check.get("repairId") == request["id"]
                        and check.get("evidence")
                    ):
                        request["review"] = {**check, "by": agent, "result": name}
                        if check.get("verdict") == "verified":
                            files = [
                                f
                                for f in check.get("files") or []
                                if isinstance(f, str) and f.strip()
                            ]
                            readable = [f for f in files if _readable(work, [f])]
                            request.pop("bindingError", None)
                            if len(readable) != len(files) or not files:
                                request["warnings"] = [
                                    "the verified check names no readable evidence file"
                                    if not readable
                                    else "some evidence files the verified check names are unreadable"
                                ]
                            request["files"] = sorted(set(readable))
                            request["revision"] = _revision(
                                work, request["id"], request["files"]
                            )
                            request["status"] = "resolved"
                        elif check.get("verdict") == "revise":
                            request["status"] = "open"
    return list(requests.values())


def _revision(work: Path, repair_id: str, files: list) -> str:
    """Bind acceptance only to the views/contracts independently named by its checker."""
    if not files:
        return _hash([repair_id, "unbound"])
    evidence = {}
    for name in files:
        path = Path(name)
        if not path.is_absolute():
            path = work / "draft" / path
        try:
            evidence[str(path)] = (
                hashlib.sha256(path.read_bytes()).hexdigest()
                if path.is_file()
                else "absent or not a regular file"
            )
        except FileNotFoundError:
            evidence[str(path)] = "absent"
        except OSError as exc:
            evidence[str(path)] = f"unreadable: {exc}"
    return _hash(evidence)


def _readable(work: Path, files: list[str]) -> bool:
    """Refuse acceptance bound to an absent or unreadable alleged evidence file."""
    for name in files:
        path = Path(name)
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
