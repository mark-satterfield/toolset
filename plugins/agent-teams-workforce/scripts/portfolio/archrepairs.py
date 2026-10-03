"""Persist decision repair progress separately from repeated decision prose."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def repair_facts(work: Path, previous: list, results: list[str], lead: str) -> list:
    """Keep completed repairs reviewable without repeatedly dispatching their maker."""
    draft = work / "draft"
    revision = _hash(
        {
            str(p.relative_to(draft)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(draft.rglob("*"))
            if p.is_file()
        }
    )
    requests = {r["id"]: dict(r) for r in previous}
    decision_path = work / "decision.json"
    decision = json.loads(decision_path.read_text()) if decision_path.is_file() else {}
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
                "revision": revision,
            },
        )
    for request in requests.values():
        if request["revision"] != revision:
            # Changed content requires independent confirmation, not automatic maker rework.
            if request["status"] == "resolved":
                request["status"] = "answered"
            request["revision"] = revision
        for name in results:
            path = Path(name)
            round_name, _, role, agent = path.stem.split("-", 3)
            n = int(round_name[1:])
            result = json.loads(path.read_text())
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
                ) and agent in (
                    request["agentType"],
                    lead,
                )
                if (
                    request["status"] == "open"
                    and agent in (request["agentType"], lead)
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
                        and check.get("revision") == revision
                        and check.get("evidence")
                    ):
                        request["review"] = {**check, "by": agent, "result": name}
                        if check.get("verdict") == "verified":
                            request["status"] = "resolved"
                        elif check.get("verdict") == "revise":
                            request["status"] = "open"
    return list(requests.values())
